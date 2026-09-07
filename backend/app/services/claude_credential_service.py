"""ClaudeCredentialService - gestion des credentials Anthropic chiffrés.

Précédence (cf. recherche faite en Phase 1) :
1. oauth_token (Pro/Max) - utilisé en priorité
2. api_key (Console) - fallback si pas de token ou token invalide

Le token Pro/Max est injecté via `CLAUDE_CODE_OAUTH_TOKEN` dans l'env du
process SDK ; l'API key via `ANTHROPIC_API_KEY`.
"""

from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Final

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.constants import CREDENTIAL_TEST_TIMEOUT_S
from app.core.exceptions import ConflictError, NotFoundError
from app.core.logging import get_logger
from app.core.security import decrypt_secret, encrypt_secret
from app.db.models import ClaudeCredential
from app.schemas.claude_credential import (
    ClaudeCredentialCreate,
    ClaudeCredentialKind,
)

logger = get_logger(__name__)

MASK_TAIL = 4
MASK_PREFIX = "…"

_ENV_VAR_BY_KIND: Final[dict[str, str]] = {
    "oauth_token": "CLAUDE_CODE_OAUTH_TOKEN",
    "api_key": "ANTHROPIC_API_KEY",
}

# Marqueurs d'échec dans la sortie du CLI : il sort en code 0 même quand
# l'API refuse le credential, son erreur arrive comme une réponse normale.
_FAILURE_MARKERS: Final[tuple[str, ...]] = (
    "Failed to authenticate",
    "API Error",
    "Invalid API key",
    "invalid x-api-key",
    "OAuth",
)


@dataclass(slots=True, frozen=True)
class CredentialTestResult:
    ok: bool
    detail: str


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

    async def list_for_user(self, db: AsyncSession, user_id: str) -> list[ClaudeCredential]:
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

    async def test(
        self, db: AsyncSession, credential_id: str, user_id: str
    ) -> CredentialTestResult:
        """Demande au CLI Claude si ce credential est accepté.

        Le seul juge fiable est le CLI lui-même : un token peut avoir le bon
        préfixe, la bonne longueur, aucun espace parasite, et être refusé par
        l'API quand même. On lui pose une question triviale et on renvoie sa
        réponse telle quelle, sans jamais exposer le secret.
        """
        cred = await self.get(db, credential_id, user_id)
        env = {k: v for k, v in os.environ.items() if k not in _ENV_VAR_BY_KIND.values()}
        env[_ENV_VAR_BY_KIND[cred.kind]] = decrypt_secret(cred.encrypted_value)

        cwd = get_settings().workspaces_root
        cwd.mkdir(parents=True, exist_ok=True)
        try:
            process = await asyncio.create_subprocess_exec(
                "claude",
                "-p",
                "Réponds exactement OK, rien d'autre.",
                cwd=str(cwd),
                env=env,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            raw_out, raw_err = await asyncio.wait_for(
                process.communicate(), timeout=CREDENTIAL_TEST_TIMEOUT_S
            )
        except TimeoutError:
            return CredentialTestResult(
                ok=False,
                detail=(f"Le CLI n'a pas répondu en {CREDENTIAL_TEST_TIMEOUT_S:.0f}s."),
            )
        except FileNotFoundError:
            return CredentialTestResult(
                ok=False, detail="CLI `claude` introuvable dans le container."
            )

        output = (raw_out.decode(errors="replace") + raw_err.decode(errors="replace")).strip()
        failed = process.returncode != 0 or any(m in output for m in _FAILURE_MARKERS)
        if not failed:
            cred.last_validated_at = datetime.now(UTC)
            await db.flush()
        logger.info(
            "claude_credential.test",
            credential_id=credential_id,
            ok=not failed,
            returncode=process.returncode,
        )
        return CredentialTestResult(
            ok=not failed,
            detail=output[:500] or f"(aucune sortie, code {process.returncode})",
        )

    async def delete(self, db: AsyncSession, credential_id: str, user_id: str) -> None:
        cred = await self.get(db, credential_id, user_id)
        await db.delete(cred)

    async def resolve_active(self, db: AsyncSession, user_id: str) -> ResolvedCredential | None:
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

    async def inject_active_into_env(self, db: AsyncSession, *, user_id: str) -> ResolvedCredential:
        """Injecte le credential actif dans os.environ pour le SDK Claude.

        Raise AuthenticationError si aucun credential n'est actif.
        Centralisé ici pour éviter la duplication entre SessionService et
        TemplateGeneratorService.
        """
        from app.core.exceptions import AuthenticationError

        resolved = await self.resolve_active(db, user_id)
        if resolved is None:
            raise AuthenticationError("Aucun credential Claude configuré. Settings > Claude.")
        os.environ.pop("CLAUDE_CODE_OAUTH_TOKEN", None)
        os.environ.pop("ANTHROPIC_API_KEY", None)
        os.environ[resolved.env_var_name] = resolved.value
        return resolved

    async def reveal_masked(self, cred: ClaudeCredential) -> str:
        """Retourne uniquement la queue masquée - ne JAMAIS exposer le clair."""
        try:
            plain = decrypt_secret(cred.encrypted_value)
        except Exception:
            return MASK_PREFIX
        return mask_value(plain)


claude_credential_service = ClaudeCredentialService()


# Garde-fou : si on tente de créer deux fois le même kind sans replace
# Pas levé en pratique grâce à `replace_existing=True` par défaut.
_ = ConflictError
