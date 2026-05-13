"""Routes /setup — bootstrap one-shot de l'installation."""

from __future__ import annotations

from fastapi import APIRouter, status

from app.core.config import get_settings
from app.core.deps import DbDep
from app.core.security import create_access_token
from app.schemas.setup import (
    BootstrapRequest,
    BootstrapResponse,
    SetupStatusResponse,
)
from app.services.setup_service import setup_service

router = APIRouter(prefix="/setup", tags=["setup"])


@router.get("/status", response_model=SetupStatusResponse)
async def status_(db: DbDep) -> SetupStatusResponse:
    """Public — utilisé par le frontend pour décider où rediriger."""
    state = await setup_service.get_or_create_state(db)
    has_admin = await setup_service.admin_exists(db)
    has_creds = await setup_service.claude_credentials_exist(db)
    settings = get_settings()
    needs = (not state.bootstrap_completed) and (not has_admin)
    await db.commit()
    return SetupStatusResponse(
        needs_bootstrap=needs,
        bootstrap_completed=state.bootstrap_completed,
        has_admin=has_admin,
        has_claude_credentials=has_creds,
        eldir_version=settings.app_version,
    )


@router.post(
    "/bootstrap",
    response_model=BootstrapResponse,
    status_code=status.HTTP_201_CREATED,
)
async def bootstrap(payload: BootstrapRequest, db: DbDep) -> BootstrapResponse:
    """One-shot — crée l'admin + injecte les credentials Claude.

    Protégée par le `bootstrap_token` émis dans les logs au 1er boot.
    Refuse si le bootstrap a déjà été effectué.
    """
    user = await setup_service.perform_bootstrap(db, payload)
    await db.commit()

    settings = get_settings()
    token = create_access_token(user.id)
    return BootstrapResponse(
        user_id=user.id,
        access_token=token,
        expires_in=settings.jwt_expire_minutes * 60,
    )
