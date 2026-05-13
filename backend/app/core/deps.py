"""Dépendances FastAPI : DB session, Redis, utilisateur courant."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Annotated

from fastapi import Depends, Header
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.exceptions import AuthenticationError
from app.core.security import decode_access_token


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Fournit une session SQLAlchemy par requête (rollback auto sur exception)."""
    from app.db.session import async_session_factory  # local pour éviter cycle

    async with async_session_factory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise


async def get_redis() -> AsyncGenerator[Redis, None]:
    """Fournit un client Redis async."""
    settings = get_settings()
    client: Redis = Redis.from_url(
        str(settings.redis_url),
        encoding="utf-8",
        decode_responses=True,
    )
    try:
        yield client
    finally:
        await client.aclose()


async def get_current_user_id(
    authorization: Annotated[str | None, Header()] = None,
) -> str:
    """Décode le JWT et retourne le `sub` (user id)."""
    if not authorization or not authorization.lower().startswith("bearer "):
        raise AuthenticationError("Header Authorization manquant ou invalide.")
    token = authorization.split(" ", 1)[1]
    payload = decode_access_token(token)
    sub = payload.get("sub")
    if not isinstance(sub, str):
        raise AuthenticationError("Token sans sujet valide.")
    return sub


SettingsDep = Annotated[Settings, Depends(get_settings)]
DbDep = Annotated[AsyncSession, Depends(get_db)]
RedisDep = Annotated[Redis, Depends(get_redis)]
CurrentUserId = Annotated[str, Depends(get_current_user_id)]
