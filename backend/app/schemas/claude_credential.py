"""Schemas Claude credentials."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal

from pydantic import Field, StringConstraints

from app.schemas.common import EldirModel, TimestampedModel

ClaudeCredentialKind = Literal["oauth_token", "api_key"]

# Cf. app.schemas.git_credential : un secret collé depuis un navigateur
# arrive régulièrement avec un saut de ligne. On le retire à l'entrée.
SecretInput = Annotated[str, StringConstraints(strip_whitespace=True)]


class ClaudeCredentialCreate(EldirModel):
    kind: ClaudeCredentialKind
    value: SecretInput = Field(min_length=8, max_length=4096)
    label: str | None = Field(default=None, max_length=120)


class ClaudeCredentialRead(TimestampedModel):
    """Vue safe - JAMAIS le secret en clair."""

    id: str
    kind: ClaudeCredentialKind
    label: str | None
    is_active: bool
    last_validated_at: datetime | None
    masked_value: str  # ex. "sk-ant-…aB12" (4 derniers chars)


class ClaudeCredentialUpdate(EldirModel):
    label: str | None = Field(default=None, max_length=120)
    is_active: bool | None = None
