"""Schemas Ollama (Phase 6)."""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from app.schemas.common import EldirModel


class OllamaModelInfo(EldirModel):
    name: str
    size_bytes: int
    modified_at: str | None = None


class OllamaStatus(EldirModel):
    enabled: bool
    base_url: str | None
    reachable: bool
    error: str | None
    default_model: str
    available_models: list[OllamaModelInfo]


class OllamaTransformRequest(EldirModel):
    text: str = Field(min_length=1)
    mode: Literal["mask", "anonymize", "summarize"]
    model: str | None = None


class OllamaTransformResponse(EldirModel):
    text: str
    mode: str
    model_used: str
