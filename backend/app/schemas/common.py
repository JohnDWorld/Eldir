"""Schémas Pydantic communs (réponses, pagination)."""

from __future__ import annotations

from datetime import datetime
from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")


class EldirModel(BaseModel):
    """Base model pour toute la couche schemas (mode strict)."""

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
        str_strip_whitespace=True,
    )


class TimestampedModel(EldirModel):
    created_at: datetime
    updated_at: datetime


class HealthResponse(EldirModel):
    status: str = "ok"
    app_name: str
    version: str
    env: str


class ErrorResponse(EldirModel):
    code: str
    message: str
    details: dict[str, object] = Field(default_factory=dict)


class Page(EldirModel, Generic[T]):
    items: list[T]
    total: int
    limit: int
    offset: int
