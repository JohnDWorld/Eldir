"""Schemas SystemPrompt (prompts Eldir éditables par l'utilisateur)."""

from __future__ import annotations

from pydantic import Field

from app.schemas.common import EldirModel


class SystemPromptRead(EldirModel):
    slug: str
    title: str
    description: str
    content: str
    is_overridden: bool
    default_content: str


class SystemPromptWrite(EldirModel):
    content: str = Field(min_length=1)
