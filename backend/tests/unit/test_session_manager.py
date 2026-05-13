"""Tests unitaires du SessionManager.

L'instanciation réelle d'un `ClaudeSDKClient` requiert un token Anthropic
et lance un sous-process Node. On mocke `ClaudeSDKClient` et `ClaudeAgentOptions`
pour tester la mécanique du pool sans dépendance externe.
"""

from __future__ import annotations

import sys
import types
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.constants import MAX_CONCURRENT_SESSIONS
from app.core.exceptions import SessionLimitError, SessionNotFoundError
from app.services.event_bus import EventBus
from app.services.session_manager import SessionManager


@pytest.fixture
def fake_sdk(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    """Remplace le module `claude_agent_sdk` par un stub minimal."""
    module = types.ModuleType("claude_agent_sdk")

    class FakeClient:
        def __init__(self, *_: object, **__: object) -> None:
            self.connect = AsyncMock()
            self.disconnect = AsyncMock()
            self.query = AsyncMock()

        async def receive_response(self):
            if False:
                yield None  # noqa: SIM301

    class FakeOptions:
        def __init__(self, *args: object, **kwargs: object) -> None:
            self.args = args
            self.kwargs = kwargs

    class HookMatcher:
        def __init__(self, *args: object, **kwargs: object) -> None:
            self.args = args
            self.kwargs = kwargs

    module.ClaudeSDKClient = FakeClient  # type: ignore[attr-defined]
    module.ClaudeAgentOptions = FakeOptions  # type: ignore[attr-defined]
    module.HookMatcher = HookMatcher  # type: ignore[attr-defined]
    module.AssistantMessage = type("AssistantMessage", (), {})  # type: ignore[attr-defined]
    module.ResultMessage = type("ResultMessage", (), {})  # type: ignore[attr-defined]
    module.SystemMessage = type("SystemMessage", (), {})  # type: ignore[attr-defined]
    module.TextBlock = type("TextBlock", (), {})  # type: ignore[attr-defined]
    module.ToolUseBlock = type("ToolUseBlock", (), {})  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "claude_agent_sdk", module)
    return module  # type: ignore[return-value]


@pytest.fixture
def manager() -> SessionManager:
    bus = EventBus(redis=AsyncMock())
    return SessionManager(event_bus=bus)


async def test_start_registers_session(
    manager: SessionManager, fake_sdk: MagicMock
) -> None:
    session = await manager.start(
        session_id="s1",
        project_id="p1",
        user_id="u1",
        cwd="/tmp",
    )
    assert session.session_id == "s1"
    assert manager.active_count == 1
    assert manager.get("s1") is session


async def test_start_enforces_concurrent_limit(
    manager: SessionManager, fake_sdk: MagicMock
) -> None:
    for i in range(MAX_CONCURRENT_SESSIONS):
        await manager.start(
            session_id=f"s{i}",
            project_id="p",
            user_id="u",
            cwd="/tmp",
        )
    with pytest.raises(SessionLimitError):
        await manager.start(
            session_id="s_overflow",
            project_id="p",
            user_id="u",
            cwd="/tmp",
        )


async def test_get_unknown_raises(manager: SessionManager) -> None:
    with pytest.raises(SessionNotFoundError):
        manager.get("ghost")


async def test_stop_unknown_raises(manager: SessionManager) -> None:
    with pytest.raises(SessionNotFoundError):
        await manager.stop("ghost")


async def test_stop_disconnects_client(
    manager: SessionManager, fake_sdk: MagicMock
) -> None:
    await manager.start(
        session_id="s1",
        project_id="p1",
        user_id="u1",
        cwd="/tmp",
    )
    active = manager.get("s1")
    await manager.stop("s1")
    assert manager.is_active("s1") is False
    assert active.client is not None
    active.client.disconnect.assert_awaited()  # type: ignore[attr-defined]
