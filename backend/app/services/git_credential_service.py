"""GitCredentialService — CRUD des PAT GitHub/Forgejo chiffrés."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import SUPPORTED_PROVIDERS
from app.core.exceptions import GitProviderError, NotFoundError
from app.core.security import decrypt_secret, encrypt_secret
from app.db.models import GitCredential
from app.schemas.git_credential import GitCredentialCreate
from app.services.claude_credential_service import mask_value


class GitCredentialService:
    async def list_for_user(
        self, db: AsyncSession, user_id: str
    ) -> list[GitCredential]:
        result = await db.execute(
            select(GitCredential)
            .where(GitCredential.user_id == user_id)
            .order_by(GitCredential.created_at.desc())
        )
        return list(result.scalars().all())

    async def get(
        self, db: AsyncSession, credential_id: str, user_id: str
    ) -> GitCredential:
        result = await db.execute(
            select(GitCredential).where(
                GitCredential.id == credential_id,
                GitCredential.user_id == user_id,
            )
        )
        cred = result.scalar_one_or_none()
        if cred is None:
            raise NotFoundError(f"Credential {credential_id} introuvable.")
        return cred

    async def get_active(
        self, db: AsyncSession, user_id: str, provider: str
    ) -> GitCredential | None:
        result = await db.execute(
            select(GitCredential)
            .where(
                GitCredential.user_id == user_id,
                GitCredential.provider == provider,
            )
            .order_by(GitCredential.created_at.desc())
        )
        return result.scalars().first()

    async def get_active_token(
        self, db: AsyncSession, user_id: str, provider: str
    ) -> str | None:
        cred = await self.get_active(db, user_id, provider)
        if cred is None:
            return None
        return decrypt_secret(cred.encrypted_token)

    async def upsert(
        self,
        db: AsyncSession,
        user_id: str,
        payload: GitCredentialCreate,
    ) -> GitCredential:
        if payload.provider not in SUPPORTED_PROVIDERS:
            raise GitProviderError(f"Provider non supporté : {payload.provider}")
        if payload.provider == "forgejo" and not payload.base_url:
            raise GitProviderError("Forgejo nécessite une base_url.")

        # Remplace l'existant du même provider (mono-user V1).
        existing = await self.get_active(db, user_id, payload.provider)
        if existing is not None:
            await db.delete(existing)
            await db.flush()

        cred = GitCredential(
            user_id=user_id,
            provider=payload.provider,
            base_url=str(payload.base_url) if payload.base_url else None,
            label=payload.label,
            encrypted_token=encrypt_secret(payload.token),
        )
        db.add(cred)
        await db.flush()
        return cred

    async def delete(
        self, db: AsyncSession, credential_id: str, user_id: str
    ) -> None:
        cred = await self.get(db, credential_id, user_id)
        await db.delete(cred)

    async def reveal_masked(self, cred: GitCredential) -> str:
        try:
            plain = decrypt_secret(cred.encrypted_token)
        except Exception:  # noqa: BLE001
            return "…"
        return mask_value(plain)


git_credential_service = GitCredentialService()
