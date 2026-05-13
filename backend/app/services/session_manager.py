"""SessionManager — pool de ClaudeSDKClient actifs.

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


@dataclass(slots=True)
class ActiveSession:
    session_id: str
    project_id: str
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
        project_id: str,
        user_id: str,
        cwd: str,
        system_prompt: str | None = None,
        model: str | None = None,
        resume_sdk_id: str | None = None,
        allowed_tools: list[str] | None = None,
    ) -> ActiveSession:
        if self.active_count >= MAX_CONCURRENT_SESSIONS:
            raise SessionLimitError(
                f"Limite de {MAX_CONCURRENT_SESSIONS} sessions actives atteinte."
            )

        # Lazy import — `claude_agent_sdk` n'est nécessaire qu'au boot d'une session.
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
            await self._publish(
                session_id,
                EVENT_TYPE_TOOL_USE,
                {
                    "tool_name": input_data.get("tool_name"),
                    "tool_input": input_data.get("tool_input"),
                    "tool_use_id": tool_use_id,
                },
            )
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

        async def _stop_hook(
            input_data: dict[str, Any],
            _tool_use_id: str | None,
            _context: Any,
        ) -> dict[str, Any]:
            await self._publish(
                session_id,
                EVENT_TYPE_STOP,
                {"reason": input_data.get("reason", "stop")},
            )
            return {}

        options_kwargs: dict[str, Any] = {
            "cwd": cwd,
            "hooks": {
                "PreToolUse": [HookMatcher(hooks=[_pre_tool_hook])],
                "PostToolUse": [HookMatcher(hooks=[_post_tool_hook])],
                "Stop": [HookMatcher(hooks=[_stop_hook])],
            },
        }
        if system_prompt:
            options_kwargs["system_prompt"] = system_prompt
        if model:
            options_kwargs["model"] = model
        if resume_sdk_id:
            options_kwargs["resume"] = resume_sdk_id
        if allowed_tools:
            options_kwargs["allowed_tools"] = allowed_tools

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
        assert active.client is not None  # noqa: S101 — invariant
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
