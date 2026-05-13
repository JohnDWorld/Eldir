"""Schemas User."""

from __future__ import annotations

from pydantic import EmailStr, Field

from app.schemas.common import EldirModel, TimestampedModel


class UserCreate(EldirModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=256)
    display_name: str | None = Field(default=None, max_length=120)


class UserRead(TimestampedModel):
    id: str
    email: EmailStr
    display_name: str | None
    is_active: bool
    is_admin: bool
