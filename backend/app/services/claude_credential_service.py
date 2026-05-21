"""ClaudeCredentialService - gestion des credentials Anthropic chiffrés.

Précédence (cf. recherche faite en Phase 1) :
1. oauth_token (Pro/Max) - utilisé en priorité
2. api_key (Console) - fallback si pas de token ou token invalide

Le token Pro/Max est injecté via `CLAUDE_CODE_OAUTH_TOKEN` dans l'env du
process SDK ; l'API key via `ANTHROPIC_API_KEY`.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError
from app.core.security import decrypt_secret, encrypt_secret
from app.db.models import ClaudeCredential
from app.schemas.claude_credential import (
    ClaudeCredentialCreate,
    ClaudeCredentialKind,
)

MASK_TAIL = 4
MASK_PREFIX = "…"


@dataclass(slots=True, frozen=True)
class ResolvedCredential:
    """Credential déchiffré + env var name pour le SDK."""

    kind: ClaudeCredentialKind
    env_var_name: str
    value: str


def mask_value(value: str) -> str:
    """Masque tout sauf les `MASK_TAIL` derniers caractères."""
    if len(value) <= MASK_TAIL:
        return MASK_PREFIX
    return f"{MASK_PREFIX}{value[-MASK_TAIL:]}"


class ClaudeCredentialService:
    """Service métier autour de ClaudeCredential.

    Toutes les méthodes prennent une session SQLAlchemy en argument explicite
    pour rester découplé des deps FastAPI (testable en unitaire).
    """

    async def list_for_user(
        self, db: AsyncSession, user_id: str
    ) -> list[ClaudeCredential]:
        result = await db.execute(
            select(ClaudeCredential)
            .where(ClaudeCredential.user_id == user_id)
            .order_by(ClaudeCredential.created_at.desc())
        )
        return list(result.scalars().all())

    async def get(self, db: AsyncSession, credential_id: str, user_id: str) -> ClaudeCredential:
        result = await db.execute(
            select(ClaudeCredential).where(
                ClaudeCredential.id == credential_id,
                ClaudeCredential.user_id == user_id,
            )
        )
        cred = result.scalar_one_or_none()
        if cred is None:
            raise NotFoundError(f"Credential {credential_id} introuvable.")
        return cred

    async def create(
        self,
        db: AsyncSession,
        user_id: str,
        payload: ClaudeCredentialCreate,
        *,
        replace_existing: bool = True,
    ) -> ClaudeCredential:
        """Crée (ou remplace) un credential du même kind pour cet user.

        En mono-user V1 on n'a qu'un seul credential actif par kind. Si
        `replace_existing` est vrai, on désactive les anciens du même kind.
        """
        if replace_existing:
            existing = await db.execute(
                select(ClaudeCredential).where(
                    ClaudeCredential.user_id == user_id,
                    ClaudeCredential.kind == payload.kind,
                    ClaudeCredential.is_active.is_(True),
                )
            )
            for cred in existing.scalars().all():
                cred.is_active = False

        cred = ClaudeCredential(
            user_id=user_id,
            kind=payload.kind,
            label=payload.label,
            encrypted_value=encrypt_secret(payload.value),
            is_active=True,
        )
        db.add(cred)
        await db.flush()
        return cred

    async def delete(self, db: AsyncSession, credential_id: str, user_id: str) -> None:
        cred = await self.get(db, credential_id, user_id)
        await db.delete(cred)

    async def resolve_active(
        self, db: AsyncSession, user_id: str
    ) -> ResolvedCredential | None:
        """Retourne le credential le plus prioritaire (oauth_token > api_key)."""
        result = await db.execute(
            select(ClaudeCredential).where(
                ClaudeCredential.user_id == user_id,
                ClaudeCredential.is_active.is_(True),
            )
        )
        creds = list(result.scalars().all())
        if not creds:
            return None

        # Priorité : oauth_token d'abord, sinon api_key.
        for kind, env_var in (
            ("oauth_token", "CLAUDE_CODE_OAUTH_TOKEN"),
            ("api_key", "ANTHROPIC_API_KEY"),
        ):
            for cred in creds:
                if cred.kind == kind:
                    return ResolvedCredential(
                        kind=kind,
                        env_var_name=env_var,
                        value=decrypt_secret(cred.encrypted_value),
                    )
        return None

    async def inject_active_into_env(
        self, db: AsyncSession, *, user_id: str
    ) -> "ResolvedCredential":
        """Injecte le credential actif dans os.environ pour le SDK Claude.

        Raise AuthenticationError si aucun credential n'est actif.
        Centralisé ici pour éviter la duplication entre SessionService et
        TemplateGeneratorService.
        """
        from app.core.exceptions import AuthenticationError

        resolved = await self.resolve_active(db, user_id)
        if resolved is None:
            raise AuthenticationError(
                "Aucun credential Claude configuré. Settings > Claude."
            )
        os.environ.pop("CLAUDE_CODE_OAUTH_TOKEN", None)
        os.environ.pop("ANTHROPIC_API_KEY", None)
        os.environ[resolved.env_var_name] = resolved.value
        return resolved

    async def reveal_masked(self, cred: ClaudeCredential) -> str:
        """Retourne uniquement la queue masquée - ne JAMAIS exposer le clair."""
        try:
            plain = decrypt_secret(cred.encrypted_value)
        except Exception:  # noqa: BLE001
            return MASK_PREFIX
        return mask_value(plain)


claude_credential_service = ClaudeCredentialService()


# Garde-fou : si on tente de créer deux fois le même kind sans replace
# Pas levé en pratique grâce à `replace_existing=True` par défaut.
_ = ConflictError
