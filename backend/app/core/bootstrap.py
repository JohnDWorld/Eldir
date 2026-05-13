"""Hook de démarrage : émet le bootstrap token si l'installation est neuve."""

from __future__ import annotations

from app.core.logging import get_logger
from app.db.session import async_session_factory
from app.services.setup_service import setup_service

logger = get_logger(__name__)


async def emit_bootstrap_token_if_needed() -> None:
    """Au boot, si admin absent, génère et logue un token de bootstrap.

    Le clair est imprimé une seule fois sur stdout, formaté pour être
    facilement parsé par `scripts/install-eldir.sh`.
    """
    async with async_session_factory() as db:
        try:
            needs = await setup_service.needs_bootstrap(db)
            if not needs:
                return
            token = await setup_service.ensure_bootstrap_token(db)
            await db.commit()
        except Exception:  # noqa: BLE001
            await db.rollback()
            logger.exception("bootstrap.emit.failed")
            return

    if token:
        # Marqueur stable pour parsing par install-eldir.sh
        logger.warning("bootstrap.token.ready", token_marker="ELDIR_BOOTSTRAP_TOKEN")
        # Ligne dédiée scriptable
        print(f"ELDIR_BOOTSTRAP_TOKEN={token}", flush=True)  # noqa: T201
