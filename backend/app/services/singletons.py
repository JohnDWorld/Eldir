"""Singletons globaux instanciés au boot du process FastAPI."""

from __future__ import annotations

from redis.asyncio import Redis

from app.core.config import get_settings
from app.db.session import async_session_factory
from app.services.event_bus import EventBus
from app.services.session_manager import SessionManager
from app.services.session_service import SessionService

_redis: Redis | None = None
_session_manager: SessionManager | None = None
_session_service: SessionService | None = None


async def init_singletons() -> None:
    """À appeler dans le lifespan startup."""
    global _redis, _session_manager, _session_service
    settings = get_settings()
    _redis = Redis.from_url(
        str(settings.redis_url),
        encoding="utf-8",
        decode_responses=True,
    )
    bus = EventBus(_redis)
    _session_manager = SessionManager(event_bus=bus)
    _session_service = SessionService(manager=_session_manager)
    _session_service.attach_session_factory(async_session_factory)


async def shutdown_singletons() -> None:
    global _redis, _session_manager, _session_service
    if _session_manager is not None:
        for active in _session_manager.list_active():
            try:
                await _session_manager.stop(active.session_id)
            except Exception:  # noqa: BLE001
                pass
    if _redis is not None:
        await _redis.aclose()
    _redis = None
    _session_manager = None
    _session_service = None


def get_session_manager() -> SessionManager:
    if _session_manager is None:
        raise RuntimeError("SessionManager non initialisé.")
    return _session_manager


def get_session_service() -> SessionService:
    if _session_service is None:
        raise RuntimeError("SessionService non initialisé.")
    return _session_service


def get_redis_client() -> Redis:
    if _redis is None:
        raise RuntimeError("Redis client non initialisé.")
    return _redis
