"""Event bus Redis pubsub — passerelle entre les hooks SDK et les WS clients."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any

from redis.asyncio import Redis

from app.core.constants import REDIS_SESSION_CHANNEL_TEMPLATE


class EventBus:
    """Pub/sub léger autour de Redis pour les events de session."""

    def __init__(self, redis: Redis) -> None:
        self._redis = redis

    @staticmethod
    def session_channel(session_id: str) -> str:
        return REDIS_SESSION_CHANNEL_TEMPLATE.format(session_id=session_id)

    async def publish(
        self,
        session_id: str,
        *,
        event_type: str,
        data: dict[str, Any],
    ) -> None:
        payload = {
            "type": event_type,
            "session_id": session_id,
            "timestamp": datetime.now(UTC).isoformat(),
            "data": data,
        }
        await self._redis.publish(
            self.session_channel(session_id),
            json.dumps(payload, separators=(",", ":")),
        )

    async def subscribe(self, session_id: str) -> AsyncIterator[dict[str, Any]]:
        pubsub = self._redis.pubsub()
        await pubsub.subscribe(self.session_channel(session_id))
        try:
            async for message in pubsub.listen():
                if message.get("type") != "message":
                    continue
                data = message.get("data")
                if isinstance(data, bytes):
                    data = data.decode()
                if isinstance(data, str):
                    yield json.loads(data)
        finally:
            await pubsub.unsubscribe(self.session_channel(session_id))
            await pubsub.aclose()
