"""Singletons globaux instanciés au boot du process FastAPI."""

from __future__ import annotations

from redis.asyncio import Redis

from app.core.config import get_settings
from app.db.session import async_session_factory
from app.services.event_bus import EventBus
from app.services.session_manager import SessionManager
from app.services.session_service import SessionService
from app.services.template_generator_service import TemplateGeneratorService

_redis: Redis | None = None
_event_bus: EventBus | None = None
_session_manager: SessionManager | None = None
_session_service: SessionService | None = None
_template_generator: TemplateGeneratorService | None = None


async def init_singletons() -> None:
    """À appeler dans le lifespan startup."""
    global _redis, _event_bus, _session_manager, _session_service, _template_generator
    settings = get_settings()
    _redis = Redis.from_url(
        str(settings.redis_url),
        encoding="utf-8",
        decode_responses=True,
    )
    _event_bus = EventBus(_redis)
    _session_manager = SessionManager(event_bus=_event_bus)
    _session_service = SessionService(manager=_session_manager)
    _session_service.attach_session_factory(async_session_factory)
    _template_generator = TemplateGeneratorService(
        manager=_session_manager, event_bus=_event_bus
    )


async def shutdown_singletons() -> None:
    global _redis, _event_bus, _session_manager, _session_service, _template_generator
    if _session_manager is not None:
        for active in _session_manager.list_active():
            try:
                await _session_manager.stop(active.session_id)
            except Exception:  # noqa: BLE001
                pass
    if _redis is not None:
        await _redis.aclose()
    _redis = None
    _event_bus = None
    _session_manager = None
    _session_service = None
    _template_generator = None


def get_session_manager() -> SessionManager:
    if _session_manager is None:
        raise RuntimeError("SessionManager non initialisé.")
    return _session_manager


def get_session_service() -> SessionService:
    if _session_service is None:
        raise RuntimeError("SessionService non initialisé.")
    return _session_service


def get_template_generator() -> TemplateGeneratorService:
    if _template_generator is None:
        raise RuntimeError("TemplateGeneratorService non initialisé.")
    return _template_generator


def get_redis_client() -> Redis:
    if _redis is None:
        raise RuntimeError("Redis client non initialisé.")
    return _redis
