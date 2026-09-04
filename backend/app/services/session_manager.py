"""SessionManager - pool de ClaudeSDKClient actifs.

Cycle de vie :
- start_session(): clone du repo OK, credentials Claude OK → instancie SDK,
  attache les hooks Redis, démarre une tâche asyncio qui consomme
  client.receive_response() et émet des events sur EventBus.
- send_message(): client.query(content). Une nouvelle iteration de receive
  reprend automatiquement.
- stop_session(): await client.disconnect().

⚠️ L'authentification Claude est globale au process (env vars).
En V1 mono-user, on injecte le credential dans os.environ au boot.
En V2 multi-user il faudra spawn des subprocesses isolés.
"""

from __future__ import annotations

import asyncio
import os
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from app.core.constants import (
    EVENT_TYPE_ERROR,
    EVENT_TYPE_STATE,
    EVENT_TYPE_STOP,
    EVENT_TYPE_TEXT,
    EVENT_TYPE_TOOL_RESULT,
    EVENT_TYPE_TOOL_USE,
    EVENT_TYPE_USAGE,
    EVENT_TYPE_USER_MESSAGE,
    MAX_CONCURRENT_SESSIONS,
    SESSION_STATE_IDLE,
    SESSION_STATE_THINKING,
    SESSION_STATE_TOOL_USE,
)
from app.core.exceptions import SessionLimitError, SessionNotFoundError
from app.core.logging import get_logger
from app.services.event_bus import EventBus

if TYPE_CHECKING:
    from claude_agent_sdk import ClaudeSDKClient

logger = get_logger(__name__)

# ── Porte de validation humaine ─────────────────────────────────
# Les sessions tournent en `bypassPermissions` (pas de TTY côté serveur),
# donc rien n'empêcherait un agent de pousser tout seul. La publication est
# la seule action irréversible et non relisible : on la refuse au niveau du
# hook, pas dans le prompt (une consigne se contourne, un hook non).
# John relit le diff dans Eldir puis déclenche commit & push / PR lui-même.
_PUBLISH_DENY_RE: re.Pattern[str] = re.compile(
    r"""\bgit\b[^;&|]*\b(?:push|commit)\b   # git push / git commit (et variantes -C, -c…)
      | \bgh\b\s+pr\b                     # gh pr create / gh pr merge
      | \bglab\b\s+mr\b                    # équivalent GitLab
    """,
    re.IGNORECASE | re.VERBOSE,
)
_PUBLISH_DENY_REASON = (
    "Refusé par Eldir : la publication est validée par un humain. "
    "Laisse tes modifications non commitées dans le worktree, John relit le "
    "diff dans le dashboard puis déclenche lui-même le commit et le push. "
    "Termine ton tour avec ton bloc <cr>."
)


def _denies_publish(tool_name: str | None, tool_input: Any) -> bool:
    """True si l'appel outil tente de commiter ou publier."""
    if tool_name not in ("Bash", "BashOutput"):
        return False
    if not isinstance(tool_input, dict):
        return False
    command = tool_input.get("command")
    return isinstance(command, str) and bool(_PUBLISH_DENY_RE.search(command))


@dataclass(slots=True)
class ActiveSession:
    session_id: str
    # None pour la session superviseur (aucun repo rattaché).
    project_id: str | None
    user_id: str
    cwd: str
    state: str = SESSION_STATE_IDLE
    sdk_session_id: str | None = None
    started_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    client: "ClaudeSDKClient | None" = None
    reader_task: asyncio.Task[None] | None = None
    message_lock: asyncio.Lock = field(default_factory=asyncio.Lock)


class SessionManager:
    """Singleton process-wide qui orchestre les ClaudeSDKClient."""

    def __init__(self, event_bus: EventBus) -> None:
        self._sessions: dict[str, ActiveSession] = {}
        self._bus = event_bus
        # Callbacks branchés par l'API au démarrage : (session_id, event_type, data)
        self._on_event_persist: list = []

    @property
    def active_count(self) -> int:
        return len(self._sessions)

    def get(self, session_id: str) -> ActiveSession:
        try:
            return self._sessions[session_id]
        except KeyError as exc:
            raise SessionNotFoundError(f"Session {session_id} introuvable.") from exc

    def list_active(self) -> list[ActiveSession]:
        return list(self._sessions.values())

    def is_active(self, session_id: str) -> bool:
        return session_id in self._sessions

    def register_persist_callback(self, callback) -> None:  # type: ignore[no-untyped-def]
        """Le service Session enregistre un callback pour persister les events en DB."""
        self._on_event_persist.append(callback)

    async def start(
        self,
        *,
        session_id: str,
        project_id: str | None,
        user_id: str,
        cwd: str,
        system_prompt: str | None = None,
        model: str | None = None,
        resume_sdk_id: str | None = None,
        allowed_tools: list[str] | None = None,
        disallowed_tools: list[str] | None = None,
        mcp_servers: dict[str, Any] | None = None,
    ) -> ActiveSession:
        if self.active_count >= MAX_CONCURRENT_SESSIONS:
            raise SessionLimitError(
                f"Limite de {MAX_CONCURRENT_SESSIONS} sessions actives atteinte."
            )

        # Lazy import - `claude_agent_sdk` n'est nécessaire qu'au boot d'une session.
        from claude_agent_sdk import (
            ClaudeAgentOptions,
            ClaudeSDKClient,
            HookMatcher,
        )

        active = ActiveSession(
            session_id=session_id,
            project_id=project_id,
            user_id=user_id,
            cwd=cwd,
            sdk_session_id=resume_sdk_id,
        )

        async def _pre_tool_hook(
            input_data: dict[str, Any],
            tool_use_id: str | None,
            _context: Any,
        ) -> dict[str, Any]:
            tool_name = input_data.get("tool_name")
            tool_input = input_data.get("tool_input")
            await self._publish(
                session_id,
                EVENT_TYPE_TOOL_USE,
                {
                    "tool_name": tool_name,
                    "tool_input": tool_input,
                    "tool_use_id": tool_use_id,
                },
            )
            if _denies_publish(tool_name, tool_input):
                logger.info(
                    "session.publish.denied",
                    session_id=session_id,
                    tool_name=tool_name,
                )
                return {
                    "hookSpecificOutput": {
                        "hookEventName": "PreToolUse",
                        "permissionDecision": "deny",
                        "permissionDecisionReason": _PUBLISH_DENY_REASON,
                    }
                }
            return {}

        async def _post_tool_hook(
            input_data: dict[str, Any],
            tool_use_id: str | None,
            _context: Any,
        ) -> dict[str, Any]:
            await self._publish(
                session_id,
                EVENT_TYPE_TOOL_RESULT,
                {
                    "tool_name": input_data.get("tool_name"),
                    "tool_response": input_data.get("tool_response"),
                    "tool_use_id": tool_use_id,
                },
            )
            return {}

        # Note : pas de Stop hook ici - `_consume_response` publie déjà un
        # EVENT_TYPE_STOP {"reason": "turn_complete"} quand un ResultMessage
        # arrive. Doubler la publication faisait apparaître "TOUR TERMINÉ"
        # deux fois côté UI.
        options_kwargs: dict[str, Any] = {
            "cwd": cwd,
            # Pas de TTY côté serveur → le mode "default" bloque toute action
            # qui demande approbation. Chaque session vit dans son worktree
            # isolé et l'UI Eldir streame chaque tool_use en temps réel, donc
            # on bypass pour rester utilisable. Un vrai flow d'approbation
            # via WS arrivera en Phase 4.
            "permission_mode": "bypassPermissions",
            "hooks": {
                "PreToolUse": [HookMatcher(hooks=[_pre_tool_hook])],
                "PostToolUse": [HookMatcher(hooks=[_post_tool_hook])],
            },
        }
        # Prompt caching (Phase 5) : on attache le system_prompt UNE seule fois
        # au boot. Le CLI Claude Code injecte automatiquement les marqueurs
        # `cache_control` sur ce bloc + sur la liste d'outils, ce qui rend les
        # tours suivants jusqu'à 90% moins coûteux côté tokens d'entrée (visible
        # dans la métrique `cache_read_tokens` du dashboard /costs).
        if system_prompt:
            options_kwargs["system_prompt"] = system_prompt
        if model:
            options_kwargs["model"] = model
        if resume_sdk_id:
            options_kwargs["resume"] = resume_sdk_id
        if allowed_tools:
            options_kwargs["allowed_tools"] = allowed_tools
        if disallowed_tools:
            # `allowed_tools` ne restreint rien en bypassPermissions (c'est une
            # liste de pré-approbation) : pour retirer vraiment un outil il faut
            # l'interdire explicitement.
            options_kwargs["disallowed_tools"] = disallowed_tools
        if mcp_servers:
            # Outils in-process (superviseur). `strict_mcp_config` évite de
            # charger en plus les serveurs MCP éventuels de la machine hôte.
            options_kwargs["mcp_servers"] = mcp_servers
            options_kwargs["strict_mcp_config"] = True

        options = ClaudeAgentOptions(**options_kwargs)
        client = ClaudeSDKClient(options=options)
        await client.connect()
        active.client = client

        self._sessions[session_id] = active
        logger.info(
            "session.started",
            session_id=session_id,
            project_id=project_id,
            cwd=cwd,
            resume=resume_sdk_id,
        )
        await self._publish_state(session_id, SESSION_STATE_IDLE)
        return active

    async def send_message(self, session_id: str, content: str) -> None:
        active = self.get(session_id)
        if active.client is None:
            raise SessionNotFoundError(
                f"Session {session_id} sans client SDK actif."
            )

        # Une seule réception en cours à la fois par session.
        async with active.message_lock:
            # Trace le message utilisateur (WS + DB) AVANT d'interroger
            # Claude, pour que l'historique soit lisible même si la session
            # est rechargée en cours de réponse.
            await self._publish(
                session_id, EVENT_TYPE_USER_MESSAGE, {"text": content}
            )
            await self._publish_state(session_id, SESSION_STATE_THINKING)
            await active.client.query(content)
            await self._consume_response(active)
            await self._publish_state(session_id, SESSION_STATE_IDLE)

    async def stop(self, session_id: str) -> None:
        active = self._sessions.pop(session_id, None)
        if active is None:
            raise SessionNotFoundError(f"Session {session_id} introuvable.")
        try:
            if active.reader_task is not None:
                active.reader_task.cancel()
            if active.client is not None:
                await active.client.disconnect()
        finally:
            await self._publish(session_id, EVENT_TYPE_STOP, {})
            logger.info("session.stopped", session_id=session_id)

    # ── internals ───────────────────────────────────────────────
    async def _consume_response(self, active: ActiveSession) -> None:
        """Boucle de lecture du stream Claude. Capture session_id, publie events."""
        assert active.client is not None  # noqa: S101 - invariant
        from claude_agent_sdk import (
            AssistantMessage,
            ResultMessage,
            SystemMessage,
            TextBlock,
            ToolUseBlock,
        )

        sdk_session_id_captured = active.sdk_session_id

        try:
            async for message in active.client.receive_response():
                if isinstance(message, SystemMessage):
                    subtype = getattr(message, "subtype", None)
                    data = getattr(message, "data", {}) or {}
                    if subtype == "init":
                        sdk_id = data.get("session_id")
                        if isinstance(sdk_id, str) and sdk_id != sdk_session_id_captured:
                            active.sdk_session_id = sdk_id
                            sdk_session_id_captured = sdk_id
                            await self._publish(
                                active.session_id,
                                EVENT_TYPE_STATE,
                                {"sdk_session_id": sdk_id},
                            )

                elif isinstance(message, AssistantMessage):
                    content = getattr(message, "content", []) or []
                    for block in content:
                        if isinstance(block, TextBlock):
                            await self._publish(
                                active.session_id,
                                EVENT_TYPE_TEXT,
                                {"text": getattr(block, "text", "")},
                            )
                        elif isinstance(block, ToolUseBlock):
                            await self._publish_state(
                                active.session_id, SESSION_STATE_TOOL_USE
                            )

                elif isinstance(message, ResultMessage):
                    # Capture usage / coût du tour avant de signaler la fin.
                    usage = getattr(message, "usage", None) or {}
                    model_usage = getattr(message, "model_usage", None) or {}
                    primary_model: str | None = None
                    if isinstance(model_usage, dict) and model_usage:
                        # Le SDK renvoie {"claude-opus-4-7": {...}} : on prend
                        # la clé qui totalise le plus de tokens output.
                        try:
                            primary_model = max(
                                model_usage.items(),
                                key=lambda kv: int(
                                    (kv[1] or {}).get("output_tokens", 0)
                                ),
                            )[0]
                        except (TypeError, ValueError):  # pragma: no cover
                            primary_model = next(iter(model_usage.keys()), None)
                    await self._publish(
                        active.session_id,
                        EVENT_TYPE_USAGE,
                        {
                            "input_tokens": int(usage.get("input_tokens", 0) or 0),
                            "output_tokens": int(usage.get("output_tokens", 0) or 0),
                            "cache_read_tokens": int(
                                usage.get("cache_read_input_tokens", 0) or 0
                            ),
                            "cache_write_tokens": int(
                                usage.get("cache_creation_input_tokens", 0) or 0
                            ),
                            "cost_usd": float(
                                getattr(message, "total_cost_usd", 0.0) or 0.0
                            ),
                            "duration_ms": int(
                                getattr(message, "duration_ms", 0) or 0
                            ),
                            "num_turns": int(getattr(message, "num_turns", 1) or 1),
                            "model": primary_model,
                        },
                    )
                    # Fin de tour
                    await self._publish(
                        active.session_id,
                        EVENT_TYPE_STOP,
                        {"reason": "turn_complete"},
                    )
                    break

        except Exception as exc:  # noqa: BLE001
            logger.exception("session.consume.error", session_id=active.session_id)
            await self._publish(
                active.session_id,
                EVENT_TYPE_ERROR,
                {"message": str(exc), "type": type(exc).__name__},
            )

    async def _publish_state(self, session_id: str, state: str) -> None:
        active = self._sessions.get(session_id)
        if active is not None:
            active.state = state
        await self._publish(session_id, EVENT_TYPE_STATE, {"state": state})

    async def _publish(
        self, session_id: str, event_type: str, data: dict[str, Any]
    ) -> None:
        await self._bus.publish(session_id, event_type=event_type, data=data)
        for cb in self._on_event_persist:
            try:
                await cb(session_id, event_type, data)
            except Exception:  # noqa: BLE001
                logger.exception("session.persist.callback.error")
