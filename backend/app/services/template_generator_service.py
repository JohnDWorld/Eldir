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
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import EVENT_TYPE_STOP, EVENT_TYPE_TEXT
from app.core.exceptions import EldirError, NotFoundError
from app.core.logging import get_logger
from app.db.models import Project, SessionEvent
from app.db.models import Session as SessionRow
from app.schemas.mission_template import (
    TemplatePresetDetail,
    TemplatePresetSkill,
    TemplatePresetSubAgent,
)
from app.services.claude_credential_service import claude_credential_service
from app.services.event_bus import EventBus
from app.services.session_manager import SessionManager
from app.services.system_prompt_service import system_prompt_service

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
class GenerationStatus:
    """État d'une génération, reconstruit depuis la DB à chaque appel."""

    status: str  # running | done | error
    preset: TemplatePresetDetail | None = None
    detail: str | None = None


class TemplateGeneratorService:
    def __init__(self, manager: SessionManager, event_bus: EventBus) -> None:
        self._manager = manager
        self._bus = event_bus
        # Générations en cours dans ce process. Perdu au redémarrage, et c'est
        # voulu : `result()` retombe alors sur la relecture des events.
        self._running: set[str] = set()
        self._errors: dict[str, str] = {}
        self._tasks: set[asyncio.Task[None]] = set()

    async def start(
        self,
        db: AsyncSession,
        *,
        user_id: str,
        project_id: str,
        model: str | None = None,
    ) -> str:
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

        # 5. La génération part en tâche de fond : la requête HTTP appelante
        #    n'attend pas (cf. docstring du module).
        self._running.add(session.id)
        self._errors.pop(session.id, None)
        task = asyncio.create_task(
            self._run_in_background(
                session_id=session.id,
                project_id=project_id,
                user_id=user_id,
                cwd=project.workspace_path,
                prompt=meta_prompt,
                model=chosen_model,
                project_name=project.name,
            )
        )
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)
        return session.id

    async def _run_in_background(
        self,
        *,
        session_id: str,
        project_id: str,
        user_id: str,
        cwd: str,
        prompt: str,
        model: str,
        project_name: str,
    ) -> None:
        """Fait tourner Claude jusqu'au bout, quoi qu'il advienne du client."""
        try:
            await self._manager.start(
                session_id=session_id,
                project_id=project_id,
                user_id=user_id,
                cwd=cwd,
                system_prompt=prompt,
                model=model,
                allowed_tools=_READONLY_TOOLS,
            )
            await asyncio.wait_for(
                self._run_generation(session_id, project_name),
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
