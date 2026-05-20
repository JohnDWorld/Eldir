"""Routes /auth - login, /me."""

from __future__ import annotations

from fastapi import APIRouter
from sqlalchemy import select

from app.core.config import get_settings
from app.core.deps import CurrentUserId, DbDep
from app.core.exceptions import AuthenticationError
from app.core.security import create_access_token, verify_password
from app.db.models import User
from app.schemas.auth import LoginRequest, LoginResponse
from app.schemas.user import UserRead

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=LoginResponse)
async def login(payload: LoginRequest, db: DbDep) -> LoginResponse:
    result = await db.execute(select(User).where(User.email == str(payload.email)))
    user = result.scalar_one_or_none()
    if user is None or not verify_password(payload.password, user.hashed_password):
        raise AuthenticationError("Identifiants invalides.")
    if not user.is_active:
        raise AuthenticationError("Compte désactivé.")

    settings = get_settings()
    token = create_access_token(user.id)
    return LoginResponse(
        access_token=token,
        expires_in=settings.jwt_expire_minutes * 60,
        user=UserRead.model_validate(user),
    )


@router.get("/me", response_model=UserRead)
async def me(user_id: CurrentUserId, db: DbDep) -> User:
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise AuthenticationError("Utilisateur introuvable.")
    return user
