"""TemplateGeneratorService - génère un Mission Template via Claude.

La génération prend 1 à 3 minutes selon la taille du repo, donc elle tourne
en **tâche de fond** : `start()` rend la main tout de suite avec un
`session_id`, le client interroge `result()` jusqu'à obtenir le preset. Tenir
une requête HTTP ouverte pendant tout ce temps ne marchait pas (navigateur qui
abandonne, écran de téléphone qui s'éteint, proxy qui coupe : le travail était
fait, payé, et la réponse perdue).

Flow :
1. `start()` : prompt système + row Session (`is_system=True`,
   `system_kind='template_generator'`) commitée tout de suite, puis une tâche
   asyncio détachée ; renvoie le `session_id`.
2. La tâche lance un ClaudeSDKClient en lecture seule (Read/Glob/Grep) sur le
   clone principal du projet et attend la fin du tour via pubsub Redis.
3. `result()` : relit les events `text` déjà persistés en base et y cherche le
   bloc `<preset>...</preset>`. Aucun état en mémoire à conserver : le résultat
   est reconstruit depuis la DB, donc il survit à la perte du client.

Les coûts du tour sont capturés normalement (cf. `cost_service`) - rien
n'est masqué dans le dashboard.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import re
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.constants import EVENT_TYPE_STOP, EVENT_TYPE_TEXT
from app.core.exceptions import EldirError, NotFoundError
from app.core.logging import get_logger
from app.db.models import MissionTemplate, Project, SessionEvent
from app.db.models import Session as SessionRow
from app.schemas.mission_template import (
    TemplatePresetDetail,
    TemplatePresetSkill,
    TemplatePresetSubAgent,
)
from app.services.claude_credential_service import claude_credential_service
from app.services.event_bus import EventBus
from app.services.mission_template_service import mission_template_service
from app.services.session_manager import SessionManager
from app.services.system_prompt_service import system_prompt_service
from app.services.template_preset_service import template_preset_service

logger = get_logger(__name__)

# Outils en lecture seule - le générateur ne doit RIEN modifier dans le repo
_READONLY_TOOLS: list[str] = ["Read", "Glob", "Grep"]

# Timeout dur sur la génération (Claude n'aura pas plus de N secondes)
_GENERATION_TIMEOUT_S: float = 180.0

_PRESET_RE = re.compile(r"<preset>(.*?)</preset>", re.DOTALL)

ALLOWED_MODELS = (
    "claude-haiku-4-5",
    "claude-sonnet-5",
    "claude-opus-5",
)
DEFAULT_MODEL = "claude-haiku-4-5"


@dataclass(slots=True, frozen=True)
class _PreparedRun:
    """Tout ce qu'il faut pour faire tourner une génération, session créée."""

    session_id: str
    project_id: str
    project_name: str
    cwd: str
    prompt: str
    model: str


@dataclass(slots=True)
class BatchItem:
    project_id: str
    project_name: str
    # pending | running | done | error
    state: str = "pending"
    session_id: str | None = None
    detail: str | None = None


@dataclass(slots=True)
class BatchState:
    """Avancement d'une génération en lot, en mémoire du process."""

    running: bool
    items: list[BatchItem]

    @property
    def done_count(self) -> int:
        return sum(1 for i in self.items if i.state in ("done", "error"))


@dataclass(slots=True, frozen=True)
class GenerationStatus:
    """État d'une génération, reconstruit depuis la DB à chaque appel."""

    status: str  # running | done | error
    preset: TemplatePresetDetail | None = None
    detail: str | None = None


class TemplateGeneratorService:
    def __init__(self, manager: SessionManager, event_bus: EventBus) -> None:
        self._manager = manager
        self._bus = event_bus
        # Génération en lot : une seule à la fois sur le serveur, et son
        # avancement vit en mémoire (perdu au redémarrage, comme le lot).
        self._batch: BatchState | None = None
        self._factory: async_sessionmaker[AsyncSession] | None = None
        # Générations en cours dans ce process. Perdu au redémarrage, et c'est
        # voulu : `result()` retombe alors sur la relecture des events.
        self._running: set[str] = set()
        self._errors: dict[str, str] = {}
        self._tasks: set[asyncio.Task[None]] = set()

    async def _prepare(
        self,
        db: AsyncSession,
        *,
        user_id: str,
        project_id: str,
        model: str | None = None,
    ) -> _PreparedRun:
        """Valide, crée la row session et la commit (visible dans le dashboard)."""
        # Validation modèle
        chosen_model = model or DEFAULT_MODEL
        if chosen_model not in ALLOWED_MODELS:
            raise EldirError(
                f"Modèle '{chosen_model}' non supporté. Valeurs : {', '.join(ALLOWED_MODELS)}."
            )

        # 1. Récupère le projet
        result = await db.execute(
            select(Project).where(Project.id == project_id, Project.user_id == user_id)
        )
        project = result.scalar_one_or_none()
        if project is None:
            raise NotFoundError(f"Projet {project_id} introuvable.")
        if not project.workspace_path:
            raise NotFoundError(f"Projet {project_id} sans workspace cloné.")

        # 2. Injecte les credentials Claude
        await claude_credential_service.inject_active_into_env(db, user_id=user_id)

        # 3. Récupère le prompt système (avec override utilisateur si présent)
        meta_prompt = await system_prompt_service.resolve(db, "template_generator")

        # 4. Crée la row Session marquée 'is_system'
        session = SessionRow(
            project_id=project_id,
            user_id=user_id,
            branch=project.default_branch,
            worktree_path=project.workspace_path,
            model=chosen_model,
            system_prompt=meta_prompt,
            is_system=True,
            system_kind="template_generator",
            summary=f"Génération de template pour {project.name}",
        )
        db.add(session)
        await db.flush()
        # Commit immédiat pour que la session soit visible dans le dashboard
        # AVANT que la génération longue n'aille au bout (l'utilisateur peut
        # voir le live en ouvrant /sessions/{id}).
        await db.commit()

        return _PreparedRun(
            session_id=session.id,
            project_id=project_id,
            project_name=project.name,
            cwd=project.workspace_path,
            prompt=meta_prompt,
            model=chosen_model,
        )

    def attach_session_factory(self, factory: async_sessionmaker[AsyncSession]) -> None:
        """Nécessaire au lot : il vit hors requête et gère ses transactions."""
        self._factory = factory

    async def start(
        self,
        db: AsyncSession,
        *,
        user_id: str,
        project_id: str,
        model: str | None = None,
    ) -> str:
        """Prépare la session et lance la génération en tâche de fond."""
        run = await self._prepare(db, user_id=user_id, project_id=project_id, model=model)
        self._running.add(run.session_id)
        self._errors.pop(run.session_id, None)
        task = asyncio.create_task(self._run_in_background(run, user_id=user_id))
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)
        return run.session_id

    async def _run_in_background(self, run: _PreparedRun, *, user_id: str) -> None:
        """Fait tourner Claude jusqu'au bout, quoi qu'il advienne du client."""
        session_id = run.session_id
        try:
            await self._manager.start(
                session_id=session_id,
                project_id=run.project_id,
                user_id=user_id,
                cwd=run.cwd,
                system_prompt=run.prompt,
                model=run.model,
                allowed_tools=_READONLY_TOOLS,
            )
            await asyncio.wait_for(
                self._run_generation(session_id, run.project_name),
                timeout=_GENERATION_TIMEOUT_S,
            )
        except TimeoutError:
            self._errors[session_id] = (
                f"Claude n'a pas fini l'analyse en {int(_GENERATION_TIMEOUT_S)}s. "
                "Réessaye, ou configure le template à la main."
            )
            logger.warning("template_generator.timeout", session_id=session_id)
        except Exception as exc:
            self._errors[session_id] = str(exc) or type(exc).__name__
            logger.exception("template_generator.failed", session_id=session_id)
        finally:
            # Toujours stopper la session SDK (mais on garde la row DB
            # pour traçabilité des coûts)
            try:
                if self._manager.is_active(session_id):
                    await self._manager.stop(session_id)
            except Exception:
                logger.exception(
                    "template_generator.stop.failed",
                    session_id=session_id,
                )
            self._running.discard(session_id)

    # ── génération en lot ───────────────────────────────────────
    def batch_state(self) -> BatchState | None:
        """Avancement du lot en cours, ou du dernier terminé. None si jamais lancé."""
        return self._batch

    async def start_batch(self, db: AsyncSession, *, user_id: str) -> BatchState:
        """Génère et applique le template des projets qui n'en ont pas.

        Séquentiel : une génération = un process `claude` résident, les
        enchaîner en parallèle ferait tomber le serveur. Les projets qui ont
        déjà un Mission Template sont sautés, on ne remplace jamais un
        template existant sans demande explicite.
        """
        if self._factory is None:
            raise EldirError("Génération en lot indisponible (factory non attachée).")
        if self._batch is not None and self._batch.running:
            return self._batch

        result = await db.execute(
            select(Project.id, Project.name)
            .outerjoin(MissionTemplate, MissionTemplate.project_id == Project.id)
            .where(
                Project.user_id == user_id,
                Project.workspace_path.is_not(None),
                MissionTemplate.id.is_(None),
            )
            .order_by(Project.name.asc())
        )
        targets = [BatchItem(project_id=pid, project_name=name) for pid, name in result.all()]
        self._batch = BatchState(running=bool(targets), items=targets)
        if not targets:
            return self._batch

        task = asyncio.create_task(self._run_batch(user_id))
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)
        return self._batch

    async def _run_batch(self, user_id: str) -> None:
        batch = self._batch
        if batch is None:
            return
        try:
            for item in batch.items:
                item.state = "running"
                try:
                    await self._generate_and_apply(user_id, item)
                except Exception as exc:  # un repo cassé n'arrête pas le lot
                    item.state = "error"
                    item.detail = str(exc) or type(exc).__name__
                    logger.exception(
                        "template_generator.batch.project.failed",
                        project_id=item.project_id,
                    )
        finally:
            batch.running = False
            logger.info(
                "template_generator.batch.done",
                total=len(batch.items),
                erreurs=sum(1 for i in batch.items if i.state == "error"),
            )

    async def _generate_and_apply(self, user_id: str, item: BatchItem) -> None:
        if self._factory is None:
            raise EldirError("Génération en lot indisponible (factory non attachée).")
        async with self._factory() as db:
            run = await self._prepare(db, user_id=user_id, project_id=item.project_id)
        item.session_id = run.session_id

        # Attendu ici, contrairement à `start()` : on veut le résultat avant
        # de passer au projet suivant.
        self._running.add(run.session_id)
        self._errors.pop(run.session_id, None)
        await self._run_in_background(run, user_id=user_id)

        async with self._factory() as db:
            status = await self.result(db, user_id=user_id, session_id=run.session_id)
            if status.status != "done" or status.preset is None:
                item.state = "error"
                item.detail = status.detail or "génération sans preset exploitable"
                return
            await mission_template_service.snapshot(
                db,
                project_id=item.project_id,
                user_id=user_id,
                note=f"avant génération en lot ({status.preset.slug})",
            )
            await template_preset_service.apply_detail(
                db,
                project_id=item.project_id,
                user_id=user_id,
                preset=status.preset,
                overwrite=True,
            )
            await db.commit()
        item.state = "done"
        item.detail = status.preset.title

    async def result(self, db: AsyncSession, *, user_id: str, session_id: str) -> GenerationStatus:
        """État d'une génération : running, done (avec preset) ou error.

        Le preset est reconstruit depuis les events `text` persistés, donc un
        client qui a perdu la connexion pendant l'analyse retrouve le résultat
        (et son coût n'est pas perdu).
        """
        row = await db.get(SessionRow, session_id)
        if row is None or row.user_id != user_id or row.system_kind != "template_generator":
            raise NotFoundError(f"Génération {session_id} introuvable.")
        if session_id in self._running:
            return GenerationStatus(status="running")
        failure = self._errors.get(session_id)
        if failure is not None:
            return GenerationStatus(status="error", detail=failure)

        events = await db.execute(
            select(SessionEvent.payload)
            .where(SessionEvent.session_id == session_id, SessionEvent.type == EVENT_TYPE_TEXT)
            .order_by(SessionEvent.created_at.asc())
        )
        full_text = "".join(
            str(payload.get("text", "")) for (payload,) in events.all() if isinstance(payload, dict)
        )
        try:
            return GenerationStatus(status="done", preset=_parse_preset(full_text))
        except EldirError as exc:
            return GenerationStatus(status="error", detail=str(exc))

    async def _run_generation(self, session_id: str, project_name: str) -> TemplatePresetDetail:
        """Envoie le message et collecte la réponse text + détecte le STOP."""
        message = (
            f"Analyse le repo `{project_name}` cloné dans ton cwd. "
            "Produis un Mission Template au format JSON enveloppé dans "
            "`<preset>...</preset>` exactement comme spécifié dans ton "
            "system prompt."
        )

        # On souscrit AVANT d'envoyer le message pour ne rien rater
        collected_text: list[str] = []
        stop_received = asyncio.Event()

        async def consumer() -> None:
            async for event in self._bus.subscribe(session_id):
                etype = event.get("type")
                data = event.get("data") or {}
                if etype == EVENT_TYPE_TEXT:
                    text = data.get("text")
                    if isinstance(text, str):
                        collected_text.append(text)
                elif etype == EVENT_TYPE_STOP:
                    stop_received.set()
                    return

        consumer_task = asyncio.create_task(consumer())

        try:
            await self._manager.send_message(session_id, message)
            # send_message bloque déjà jusqu'à la fin du tour côté
            # SessionManager (cf. message_lock + _consume_response), donc
            # quand on revient ici, le STOP a déjà été publié. On laisse
            # quand même 2s au consumer pour drainer la queue Redis.
            try:
                await asyncio.wait_for(stop_received.wait(), timeout=2.0)
            except TimeoutError:
                logger.warning(
                    "template_generator.stop_event_missed",
                    session_id=session_id,
                )
        finally:
            consumer_task.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await consumer_task

        full_text = "".join(collected_text)
        return _parse_preset(full_text)


def _parse_preset(raw: str) -> TemplatePresetDetail:
    """Extrait le bloc <preset>...</preset> et le valide."""
    match = _PRESET_RE.search(raw)
    if match is None:
        # On essaye un fallback : peut-être que Claude a renvoyé du JSON pur
        stripped = raw.strip()
        if stripped.startswith("{") and stripped.endswith("}"):
            json_text = stripped
        else:
            raise EldirError(
                "Claude n'a pas renvoyé de bloc <preset>...</preset>. "
                "Vérifie le prompt système (Settings > Prompts > Génération de Mission Template)."
            )
    else:
        json_text = match.group(1).strip()

    try:
        data: dict[str, Any] = json.loads(json_text)
    except json.JSONDecodeError as exc:
        raise EldirError(f"Le bloc <preset> n'est pas un JSON valide : {exc.msg}") from exc

    # Validation + normalisation
    skills_raw = data.get("skills") or []
    sub_agents_raw = data.get("sub_agents") or []
    try:
        return TemplatePresetDetail(
            slug=str(data.get("slug", "generated")),
            title=str(data.get("title", "Template généré")),
            description=str(data.get("description", "")),
            tags=list(data.get("tags") or []),
            model=data.get("model"),
            allowed_tools=data.get("allowed_tools"),
            setup_commands=[str(c) for c in (data.get("setup_commands") or []) if str(c).strip()][
                :20
            ]
            or None,
            system_prompt=str(data.get("system_prompt", "")),
            skills=[
                TemplatePresetSkill(
                    name=str(s["name"]),
                    description=str(s.get("description", "")),
                    content=str(s.get("content", "")),
                )
                for s in skills_raw
                if isinstance(s, dict) and s.get("name")
            ],
            sub_agents=[
                TemplatePresetSubAgent(
                    name=str(a["name"]),
                    description=str(a.get("description", "")),
                    system_prompt=str(a.get("system_prompt", "")),
                    allowed_tools=a.get("allowed_tools"),
                )
                for a in sub_agents_raw
                if isinstance(a, dict) and a.get("name")
            ],
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise EldirError(f"Preset généré invalide : {exc}") from exc
