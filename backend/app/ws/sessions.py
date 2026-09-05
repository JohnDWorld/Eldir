"""WebSocket /ws/sessions/{session_id} - stream live des events.

Auth via query param `?token=<jwt>` (les WS browser ne supportent pas les
headers Authorization personnalisés sans hacks). Le token est validé avant
de joindre le pubsub.
"""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect, status
from sqlalchemy import select

from app.core.exceptions import AuthenticationError
from app.core.logging import get_logger
from app.core.security import decode_access_token
from app.db.models import Session
from app.db.session import async_session_factory
from app.services.event_bus import EventBus
from app.services.singletons import get_redis_client
from app.services.ws_manager import ws_manager

logger = get_logger(__name__)
router = APIRouter()


@router.websocket("/ws/sessions/{session_id}")
async def session_stream(
    ws: WebSocket,
    session_id: str,
    token: str = Query(..., description="JWT access token"),
) -> None:
    # 1. Auth
    try:
        payload = decode_access_token(token)
    except AuthenticationError:
        await ws.close(code=status.WS_1008_POLICY_VIOLATION)
        return
    user_id = payload.get("sub")
    if not isinstance(user_id, str):
        await ws.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    # 2. Autorisation : la session appartient bien à cet user
    async with async_session_factory() as db:
        result = await db.execute(
            select(Session).where(Session.id == session_id, Session.user_id == user_id)
        )
        if result.scalar_one_or_none() is None:
            await ws.close(code=status.WS_1008_POLICY_VIOLATION)
            return

    # 3. Branchement pubsub
    try:
        redis = get_redis_client()
    except RuntimeError:
        await ws.close(code=status.WS_1011_INTERNAL_ERROR)
        return

    bus = EventBus(redis)
    await ws_manager.connect(session_id, ws)
    relay_task = asyncio.create_task(_relay(bus, session_id, ws))
    try:
        # Keepalive : on lit les pings du client (sinon WebSocketDisconnect)
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        logger.info("ws.session.disconnect", session_id=session_id)
    finally:
        relay_task.cancel()
        ws_manager.disconnect(session_id, ws)


async def _relay(bus: EventBus, session_id: str, ws: WebSocket) -> None:
    try:
        async for event in bus.subscribe(session_id):
            try:
                await ws.send_json(event)
            except Exception:
                break
    except asyncio.CancelledError:
        raise
    except Exception:
        logger.exception("ws.relay.error", session_id=session_id)
