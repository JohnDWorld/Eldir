"""OllamaSettingsService - singleton accès aux préférences UI Ollama."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import OllamaSettings

_SINGLETON_ID = "singleton"


class OllamaSettingsService:
    async def get(self, db: AsyncSession) -> OllamaSettings:
        result = await db.execute(select(OllamaSettings).where(OllamaSettings.id == _SINGLETON_ID))
        existing = result.scalar_one_or_none()
        if existing is not None:
            return existing
        # Self-heal si la ligne n'existe pas (la migration la seed, mais
        # un env fraîchement reset peut être vide).
        row = OllamaSettings(id=_SINGLETON_ID, expose_to_sessions=False)
        db.add(row)
        await db.flush()
        return row

    async def set_expose(self, db: AsyncSession, *, value: bool) -> OllamaSettings:
        row = await self.get(db)
        row.expose_to_sessions = value
        await db.flush()
        return row


ollama_settings_service = OllamaSettingsService()
