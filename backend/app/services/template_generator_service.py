"""TemplateGeneratorService - génère un Mission Template via Claude.

Flow :
1. Récupère le prompt système `template_generator` (depuis fichier + override DB)
2. Crée une row Session marquée `is_system=True`, `system_kind='template_generator'`
3. Lance un ClaudeSDKClient en lecture seule (Read/Glob/Grep uniquement) sur
   le clone principal du projet
4. Envoie un message d'analyse, attend la fin du tour via pubsub Redis
5. Parse le bloc `<preset>...</preset>` de la réponse → JSON → TemplatePresetDetail
6. Stoppe la session

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
from app.db.models import Project
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
    "claude-haiku-4-5-20251001",
    "claude-sonnet-4-6",
    "claude-opus-4-7",
)
DEFAULT_MODEL = "claude-haiku-4-5-20251001"


@dataclass(slots=True, frozen=True)
class GenerationResult:
    preset: TemplatePresetDetail
    session_id: str  # session système conservée en DB pour audit des coûts


class TemplateGeneratorService:
    def __init__(
        self, manager: SessionManager, event_bus: EventBus
    ) -> None:
        self._manager = manager
        self._bus = event_bus

    async def generate(
        self,
        db: AsyncSession,
        *,
        user_id: str,
        project_id: str,
        model: str | None = None,
    ) -> GenerationResult:
        # Validation modèle
        chosen_model = model or DEFAULT_MODEL
        if chosen_model not in ALLOWED_MODELS:
            raise EldirError(
                f"Modèle '{chosen_model}' non supporté. "
                f"Valeurs : {', '.join(ALLOWED_MODELS)}."
            )

        # 1. Récupère le projet
        result = await db.execute(
            select(Project).where(
                Project.id == project_id, Project.user_id == user_id
            )
        )
        project = result.scalar_one_or_none()
        if project is None:
            raise NotFoundError(f"Projet {project_id} introuvable.")
        if not project.workspace_path:
            raise NotFoundError(
                f"Projet {project_id} sans workspace cloné."
            )

        # 2. Injecte les credentials Claude
        await claude_credential_service.inject_active_into_env(
            db, user_id=user_id
        )

        # 3. Récupère le prompt système (avec override utilisateur si présent)
        meta_prompt = await system_prompt_service.resolve(
            db, "template_generator"
        )

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

        try:
            # 5. Démarre le SDK Claude en lecture seule sur le clone principal
            await self._manager.start(
                session_id=session.id,
                project_id=project_id,
                user_id=user_id,
                cwd=project.workspace_path,
                system_prompt=meta_prompt,
                model=chosen_model,
                allowed_tools=_READONLY_TOOLS,
            )

            # 6. Lance le tour + attend la fin via pubsub
            preset = await asyncio.wait_for(
                self._run_generation(session.id, project.name),
                timeout=_GENERATION_TIMEOUT_S,
            )
        finally:
            # Toujours stopper la session SDK (mais on garde la row DB
            # pour traçabilité des coûts)
            try:
                if self._manager.is_active(session.id):
                    await self._manager.stop(session.id)
            except Exception:
                logger.exception(
                    "template_generator.stop.failed",
                    session_id=session.id,
                )

        return GenerationResult(preset=preset, session_id=session.id)

    async def _run_generation(
        self, session_id: str, project_name: str
    ) -> TemplatePresetDetail:
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
        raise EldirError(
            f"Le bloc <preset> n'est pas un JSON valide : {exc.msg}"
        ) from exc

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
        raise EldirError(
            f"Preset généré invalide : {exc}"
        ) from exc
