"""Schemas Git credentials (PAT GitHub, PAT Forgejo)."""

from __future__ import annotations

from typing import Literal

from pydantic import Field, HttpUrl

from app.schemas.common import EldirModel, TimestampedModel

GitProviderName = Literal["github", "forgejo"]


class GitCredentialCreate(EldirModel):
    provider: GitProviderName
    token: str = Field(min_length=8, max_length=2048)
    base_url: HttpUrl | None = None  # uniquement pour Forgejo
    label: str | None = Field(default=None, max_length=120)


class GitCredentialRead(TimestampedModel):
    id: str
    provider: GitProviderName
    base_url: str | None
    label: str | None
    masked_token: str
