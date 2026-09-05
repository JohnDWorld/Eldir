"""SetupService - pilote l'installation initiale (bootstrap one-shot).

Flow :
1. Au boot, si aucun admin n'existe : génère un `bootstrap_token` aléatoire,
   stocke son hash en DB (table `setup_state`), affiche le clair dans stdout.
2. Le script d'install (`scripts/install-eldir.sh`) lit ce token dans les
   logs du container backend, demande email/password à l'utilisateur, lance
   `claude setup-token` pour récupérer le token Pro/Max, puis POST
   `/api/v1/setup/bootstrap` avec tout ça.
3. La route vérifie le bootstrap_token, crée l'admin, persiste les
   credentials Claude (chiffrés), marque le setup comme complété et
   désactive le bootstrap_token définitivement.
"""

from __future__ import annotations

import hashlib
import secrets
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.exceptions import AuthenticationError, ConflictError
from app.core.logging import get_logger
from app.core.security import hash_password
from app.db.models import ClaudeCredential, SetupState, User
from app.schemas.setup import BootstrapRequest

logger = get_logger(__name__)

_SETUP_STATE_ID = "singleton"


def _hash_token(token: str) -> str:
    """SHA-256 du token - on ne stocke jamais le clair en DB."""
    return hashlib.sha256(token.encode()).hexdigest()


class SetupService:
    async def get_or_create_state(self, db: AsyncSession) -> SetupState:
        result = await db.execute(select(SetupState).where(SetupState.id == _SETUP_STATE_ID))
        state = result.scalar_one_or_none()
        if state is None:
            state = SetupState(id=_SETUP_STATE_ID, bootstrap_completed=False)
            db.add(state)
            await db.flush()
        return state

    async def admin_exists(self, db: AsyncSession) -> bool:
        result = await db.execute(
            select(func.count()).select_from(User).where(User.is_admin.is_(True))
        )
        count = result.scalar_one()
        return count > 0

    async def claude_credentials_exist(self, db: AsyncSession) -> bool:
        result = await db.execute(
            select(func.count())
            .select_from(ClaudeCredential)
            .where(ClaudeCredential.is_active.is_(True))
        )
        return result.scalar_one() > 0

    async def needs_bootstrap(self, db: AsyncSession) -> bool:
        state = await self.get_or_create_state(db)
        if state.bootstrap_completed:
            return False
        return not await self.admin_exists(db)

    async def ensure_bootstrap_token(self, db: AsyncSession) -> str | None:
        """Crée et retourne un bootstrap token EN CLAIR si nécessaire.

        ⚠️ Le clair n'est retourné que la première fois. Stocké en hash en DB.
        Retourne None si le bootstrap est déjà terminé.
        """
        state = await self.get_or_create_state(db)
        if state.bootstrap_completed:
            return None
        if state.bootstrap_token_hash:
            # Token déjà émis lors d'un boot précédent - on ne peut pas le
            # ressortir en clair, il faut que l'opérateur l'ait conservé.
            # Pour le dev, on régénère pour éviter de bloquer.
            settings = get_settings()
            if not settings.is_dev:
                return None
        token = secrets.token_urlsafe(48)
        state.bootstrap_token_hash = _hash_token(token)
        await db.flush()
        return token

    async def verify_bootstrap_token(self, db: AsyncSession, token: str) -> None:
        state = await self.get_or_create_state(db)
        if state.bootstrap_completed:
            raise ConflictError("Bootstrap déjà effectué.")
        if not state.bootstrap_token_hash:
            raise AuthenticationError("Aucun bootstrap token n'a été émis.")
        if not secrets.compare_digest(state.bootstrap_token_hash, _hash_token(token)):
            raise AuthenticationError("Bootstrap token invalide.")

    async def perform_bootstrap(
        self,
        db: AsyncSession,
        payload: BootstrapRequest,
    ) -> User:
        """Vérifie le token, crée l'admin et les credentials Claude.

        Caller responsable de commit. Retourne l'admin créé.
        """
        from app.schemas.claude_credential import ClaudeCredentialCreate
        from app.services.claude_credential_service import (  # local import: cycle
            claude_credential_service,
        )

        await self.verify_bootstrap_token(db, payload.bootstrap_token)

        # Sécurité : refuser si un admin existe déjà (cas pathologique).
        if await self.admin_exists(db):
            raise ConflictError("Un administrateur existe déjà.")

        user = User(
            email=str(payload.admin_email),
            hashed_password=hash_password(payload.admin_password),
            display_name=payload.admin_display_name,
            is_active=True,
            is_admin=True,
        )
        db.add(user)
        await db.flush()

        for cred_in in payload.claude_credentials:
            await claude_credential_service.create(
                db,
                user_id=user.id,
                payload=ClaudeCredentialCreate(
                    kind=cred_in.kind,  # type: ignore[arg-type]
                    value=cred_in.value,
                    label=cred_in.label,
                ),
            )

        state = await self.get_or_create_state(db)
        state.bootstrap_completed = True
        state.bootstrap_completed_at = datetime.now(UTC)
        state.bootstrap_token_hash = None
        state.eldir_version = get_settings().app_version
        await db.flush()

        logger.info("setup.bootstrap.completed", user_id=user.id)
        return user


setup_service = SetupService()
