"""Schemas d'authentification."""

from __future__ import annotations

from pydantic import EmailStr, Field

from app.schemas.common import EldirModel
from app.schemas.user import UserRead


class LoginRequest(EldirModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=256)


class TokenResponse(EldirModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int  # secondes


class LoginResponse(TokenResponse):
    user: UserRead
