"""Schemas Coûts (Phase 5 - Optimisation tokens)."""

from __future__ import annotations

from datetime import date

from app.schemas.common import EldirModel


class CostTotalsRead(EldirModel):
    input_tokens: int
    output_tokens: int
    cache_read_tokens: int
    cache_write_tokens: int
    cost_usd: float
    num_turns: int

    @property
    def total_tokens(self) -> int:  # pragma: no cover - convenience
        return (
            self.input_tokens
            + self.output_tokens
            + self.cache_read_tokens
            + self.cache_write_tokens
        )


class DailyCostRead(EldirModel):
    day: date
    input_tokens: int
    output_tokens: int
    cache_read_tokens: int
    cache_write_tokens: int
    cost_usd: float


class ProjectCostRead(EldirModel):
    project_id: str
    project_name: str | None = None
    input_tokens: int
    output_tokens: int
    cost_usd: float


class CostDashboard(EldirModel):
    """Snapshot complet pour le dashboard 'Coûts'."""

    today: CostTotalsRead
    last_7_days: CostTotalsRead
    last_30_days: CostTotalsRead
    daily: list[DailyCostRead]
    by_project: list[ProjectCostRead]
