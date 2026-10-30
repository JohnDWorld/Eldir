"""Un vrai SessionManager, avec un client SDK factice.

`send_message`, `_consume_response` et `stop` sont ceux de production : les events
que le superviseur reçoit (`user_message`, STOP avec ou sans raison) sont donc ceux
que le manager publie vraiment, pas ceux qu'un test croit qu'il publie. Un test qui
publie lui-même `STOP {}` pour décrire la fin d'un tour décrit en réalité une
interruption : c'est déjà arrivé.
"""

from __future__ import annotations

import asyncio
import sys
from collections import deque
from collections.abc import AsyncIterator
from typing import Any
from unittest.mock import AsyncMock

from app.services.event_bus import EventBus
from app.services.session_manager import ActiveSession, SessionManager


class ClientFactice:
    """Un client SDK sans CLI. Chaque tour attend une porte, dans l'ordre où on les pose.

    Sans porte posée, le tour se termine aussitôt. `reponses` donne le texte que Claude écrit
    à chaque tour, dans l'ordre (`None` : le tour ne dit rien) : c'est là qu'un bloc `<cr>`
    apparaît, ou non.
    """

    def __init__(self) -> None:
        self.disconnect = AsyncMock()
        self.demandes: list[str] = []
        self.portes: deque[asyncio.Event] = deque()
        self.reponses: deque[str | None] = deque()

    async def query(self, texte: str) -> None:
        self.demandes.append(texte)

    async def receive_response(self) -> AsyncIterator[Any]:
        if self.portes:
            await self.portes.popleft().wait()
        sdk = sys.modules["claude_agent_sdk"]
        texte = self.reponses.popleft() if self.reponses else None
        if texte is not None:
            bloc, message = sdk.TextBlock(), sdk.AssistantMessage()
            bloc.text, message.content = texte, [bloc]
            yield message
        yield sdk.ResultMessage()


class ManagerReel(SessionManager):
    def __init__(self) -> None:
        super().__init__(event_bus=EventBus(redis=AsyncMock()))
        self.clients: dict[str, ClientFactice] = {}

    def installer(self, session_id: str, project_id: str | None, user_id: str) -> ClientFactice:
        """Rend la session active, comme après un `start` ou un `resume`."""
        client = ClientFactice()
        self._sessions[session_id] = ActiveSession(
            session_id=session_id,
            project_id=project_id,
            user_id=user_id,
            cwd="/tmp",
            client=client,  # type: ignore[arg-type]
        )
        self.clients[session_id] = client
        return client

    async def start(self, **kwargs: Any) -> ActiveSession:  # type: ignore[override]
        self.installer(kwargs["session_id"], kwargs.get("project_id"), kwargs["user_id"])
        return self._sessions[kwargs["session_id"]]
