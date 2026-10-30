"""GitCredentialService - CRUD des PAT GitHub/Forgejo chiffrés."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import SUPPORTED_PROVIDERS
from app.core.exceptions import GitProviderError, NotFoundError
from app.core.security import decrypt_secret, encrypt_secret
from app.db.models import GitCredential
from app.schemas.git_credential import GitCredentialCreate
from app.services.claude_credential_service import mask_value


class GitCredentialService:
    async def list_for_user(self, db: AsyncSession, user_id: str) -> list[GitCredential]:
        result = await db.execute(
            select(GitCredential)
            .where(GitCredential.user_id == user_id)
            .order_by(GitCredential.created_at.desc())
        )
        return list(result.scalars().all())

    async def get(self, db: AsyncSession, credential_id: str, user_id: str) -> GitCredential:
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
        self,
        db: AsyncSession,
        user_id: str,
        provider: str,
        project_id: str | None = None,
    ) -> GitCredential | None:
        """Le jeton à utiliser : celui du projet s'il existe, sinon le global.

        Un jeton par projet borne ce qu'une fuite expose, à condition qu'il soit
        lui-même restreint côté provider (PAT fine-grained GitHub, jeton par
        dépôt Forgejo). Le repli sur le jeton global garde l'installation
        existante fonctionnelle : personne n'a à recréer ses jetons pour que la
        synchronisation reparte.
        """
        if project_id is not None:
            propre = await self._premier(
                db,
                GitCredential.user_id == user_id,
                GitCredential.provider == provider,
                GitCredential.project_id == project_id,
            )
            if propre is not None:
                return propre
        return await self._premier(
            db,
            GitCredential.user_id == user_id,
            GitCredential.provider == provider,
            GitCredential.project_id.is_(None),
        )

    async def _premier(self, db: AsyncSession, *conditions: Any) -> GitCredential | None:
        result = await db.execute(
            select(GitCredential).where(*conditions).order_by(GitCredential.created_at.desc())
        )
        return result.scalars().first()

    async def get_active_token(
        self,
        db: AsyncSession,
        user_id: str,
        provider: str,
        project_id: str | None = None,
    ) -> str | None:
        cred = await self.get_active(db, user_id, provider, project_id)
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

        # Remplace l'existant de même portée : un jeton de projet ne chasse
        # pas le jeton global, et inversement. Sans cette condition, poser le
        # jeton d'un projet supprimait celui qui sert tous les autres.
        existing = await self._premier(
            db,
            GitCredential.user_id == user_id,
            GitCredential.provider == payload.provider,
            GitCredential.project_id == payload.project_id
            if payload.project_id is not None
            else GitCredential.project_id.is_(None),
        )
        if existing is not None:
            await db.delete(existing)
            await db.flush()

        cred = GitCredential(
            user_id=user_id,
            project_id=payload.project_id,
            provider=payload.provider,
            base_url=str(payload.base_url) if payload.base_url else None,
            label=payload.label,
            encrypted_token=encrypt_secret(payload.token),
        )
        db.add(cred)
        await db.flush()
        return cred

    async def delete(self, db: AsyncSession, credential_id: str, user_id: str) -> None:
        cred = await self.get(db, credential_id, user_id)
        await db.delete(cred)

    async def reveal_masked(self, cred: GitCredential) -> str:
        try:
            plain = decrypt_secret(cred.encrypted_token)
        except Exception:
            return "…"
        return mask_value(plain)


git_credential_service = GitCredentialService()
