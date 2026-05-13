"""WebSocketManager — track les connexions WS par session pour fanout."""

from __future__ import annotations

from collections import defaultdict

from fastapi import WebSocket

from app.core.logging import get_logger

logger = get_logger(__name__)


class WebSocketManager:
    """Tient un registre {session_id: set[WebSocket]} pour broadcast ciblé."""

    def __init__(self) -> None:
        self._connections: dict[str, set[WebSocket]] = defaultdict(set)

    async def connect(self, session_id: str, ws: WebSocket) -> None:
        await ws.accept()
        self._connections[session_id].add(ws)
        logger.info(
            "ws.connect", session_id=session_id, total=len(self._connections[session_id])
        )

    def disconnect(self, session_id: str, ws: WebSocket) -> None:
        self._connections[session_id].discard(ws)
        if not self._connections[session_id]:
            self._connections.pop(session_id, None)
        logger.info("ws.disconnect", session_id=session_id)

    async def broadcast(self, session_id: str, payload: dict[str, object]) -> None:
        dead: list[WebSocket] = []
        for ws in self._connections.get(session_id, set()):
            try:
                await ws.send_json(payload)
            except Exception:  # noqa: BLE001
                dead.append(ws)
        for ws in dead:
            self.disconnect(session_id, ws)


ws_manager = WebSocketManager()
