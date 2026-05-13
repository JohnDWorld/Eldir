"""Schemas pour le setup wizard et le bootstrap."""

from __future__ import annotations

from pydantic import EmailStr, Field

from app.schemas.common import EldirModel


class SetupStatusResponse(EldirModel):
    needs_bootstrap: bool
    bootstrap_completed: bool
    has_admin: bool
    has_claude_credentials: bool
    eldir_version: str


class BootstrapClaudeCredentialIn(EldirModel):
    """Credential injecté au bootstrap (token Pro/Max ou API key)."""

    kind: str = Field(pattern="^(oauth_token|api_key)$")
    value: str = Field(min_length=8, max_length=4096)
    label: str | None = Field(default=None, max_length=120)


class BootstrapRequest(EldirModel):
    bootstrap_token: str = Field(min_length=20, max_length=512)
    admin_email: EmailStr
    admin_password: str = Field(min_length=8, max_length=256)
    admin_display_name: str | None = Field(default=None, max_length=120)
    claude_credentials: list[BootstrapClaudeCredentialIn] = Field(default_factory=list)


class BootstrapResponse(EldirModel):
    user_id: str
    access_token: str
    token_type: str = "bearer"
    expires_in: int
