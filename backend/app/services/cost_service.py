"""CostService - persiste et agrège les coûts SDK Claude (Phase 5).

Une ligne `SessionCost` par tour (= un `ResultMessage` SDK). Les services
appellent `record_turn(...)` pour persister, et les routes API utilisent
les méthodes d'agrégation pour le dashboard.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.db.models import Session as SessionRow
from app.db.models import SessionCost

logger = get_logger(__name__)


@dataclass(slots=True, frozen=True)
class CostTotals:
    input_tokens: int
    output_tokens: int
    cache_read_tokens: int
    cache_write_tokens: int
    cost_usd: float
    num_turns: int

    @property
    def total_tokens(self) -> int:
        return (
            self.input_tokens
            + self.output_tokens
            + self.cache_read_tokens
            + self.cache_write_tokens
        )


@dataclass(slots=True, frozen=True)
class DailyCost:
    day: date
    input_tokens: int
    output_tokens: int
    cache_read_tokens: int
    cache_write_tokens: int
    cost_usd: float


@dataclass(slots=True, frozen=True)
class ProjectCost:
    project_id: str
    input_tokens: int
    output_tokens: int
    cost_usd: float


class CostService:
    """Stateless. Toutes les méthodes prennent une `AsyncSession` SQLA."""

    async def record_turn(
        self,
        db: AsyncSession,
        *,
        session_id: str,
        data: dict[str, Any],
    ) -> SessionCost | None:
        """Persiste un tour à partir d'un payload event `usage`.

        On retrouve project_id / user_id via la table sessions plutôt que
        de les exiger en paramètre (le callback Manager ne les connaît pas).
        """
        row = await db.execute(
            select(SessionRow.project_id, SessionRow.user_id).where(SessionRow.id == session_id)
        )
        ctx = row.one_or_none()
        if ctx is None:
            logger.warning("cost.record.session_not_found", session_id=session_id)
            return None
        project_id, user_id = ctx

        cost = SessionCost(
            session_id=session_id,
            project_id=project_id,
            user_id=user_id,
            model=data.get("model") if isinstance(data.get("model"), str) else None,
            input_tokens=int(data.get("input_tokens", 0) or 0),
            output_tokens=int(data.get("output_tokens", 0) or 0),
            cache_read_tokens=int(data.get("cache_read_tokens", 0) or 0),
            cache_write_tokens=int(data.get("cache_write_tokens", 0) or 0),
            cost_usd=float(data.get("cost_usd", 0.0) or 0.0),
            duration_ms=int(data.get("duration_ms", 0) or 0),
            num_turns=int(data.get("num_turns", 1) or 1),
        )
        db.add(cost)
        return cost

    async def totals_for_session(self, db: AsyncSession, *, session_id: str) -> CostTotals:
        stmt = select(
            func.coalesce(func.sum(SessionCost.input_tokens), 0),
            func.coalesce(func.sum(SessionCost.output_tokens), 0),
            func.coalesce(func.sum(SessionCost.cache_read_tokens), 0),
            func.coalesce(func.sum(SessionCost.cache_write_tokens), 0),
            func.coalesce(func.sum(SessionCost.cost_usd), 0),
            func.coalesce(func.sum(SessionCost.num_turns), 0),
        ).where(SessionCost.session_id == session_id)
        result = await db.execute(stmt)
        row = result.one()
        return CostTotals(
            input_tokens=int(row[0]),
            output_tokens=int(row[1]),
            cache_read_tokens=int(row[2]),
            cache_write_tokens=int(row[3]),
            cost_usd=float(row[4]),
            num_turns=int(row[5]),
        )

    async def totals_for_user(
        self,
        db: AsyncSession,
        *,
        user_id: str,
        since: datetime | None = None,
    ) -> CostTotals:
        conditions = [SessionCost.user_id == user_id]
        if since is not None:
            conditions.append(SessionCost.created_at >= since)
        stmt = select(
            func.coalesce(func.sum(SessionCost.input_tokens), 0),
            func.coalesce(func.sum(SessionCost.output_tokens), 0),
            func.coalesce(func.sum(SessionCost.cache_read_tokens), 0),
            func.coalesce(func.sum(SessionCost.cache_write_tokens), 0),
            func.coalesce(func.sum(SessionCost.cost_usd), 0),
            func.coalesce(func.sum(SessionCost.num_turns), 0),
        ).where(*conditions)
        result = await db.execute(stmt)
        row = result.one()
        return CostTotals(
            input_tokens=int(row[0]),
            output_tokens=int(row[1]),
            cache_read_tokens=int(row[2]),
            cache_write_tokens=int(row[3]),
            cost_usd=float(row[4]),
            num_turns=int(row[5]),
        )

    async def daily_for_user(
        self,
        db: AsyncSession,
        *,
        user_id: str,
        days: int = 7,
    ) -> list[DailyCost]:
        """Renvoie une liste de `days` jours (du plus ancien au plus récent),
        remplie de zéros si pas de données ce jour-là.
        """
        today = datetime.now(UTC).date()
        start = today - timedelta(days=days - 1)
        start_dt = datetime.combine(start, datetime.min.time(), tzinfo=UTC)

        bucket = func.date(SessionCost.created_at).label("d")
        stmt = (
            select(
                bucket,
                func.coalesce(func.sum(SessionCost.input_tokens), 0),
                func.coalesce(func.sum(SessionCost.output_tokens), 0),
                func.coalesce(func.sum(SessionCost.cache_read_tokens), 0),
                func.coalesce(func.sum(SessionCost.cache_write_tokens), 0),
                func.coalesce(func.sum(SessionCost.cost_usd), 0),
            )
            .where(
                SessionCost.user_id == user_id,
                SessionCost.created_at >= start_dt,
            )
            .group_by(bucket)
            .order_by(bucket)
        )
        result = await db.execute(stmt)
        rows = {
            _to_date(r[0]): DailyCost(
                day=_to_date(r[0]),
                input_tokens=int(r[1]),
                output_tokens=int(r[2]),
                cache_read_tokens=int(r[3]),
                cache_write_tokens=int(r[4]),
                cost_usd=float(r[5]),
            )
            for r in result.all()
        }
        out: list[DailyCost] = []
        for i in range(days):
            d = start + timedelta(days=i)
            out.append(
                rows.get(
                    d,
                    DailyCost(
                        day=d,
                        input_tokens=0,
                        output_tokens=0,
                        cache_read_tokens=0,
                        cache_write_tokens=0,
                        cost_usd=0.0,
                    ),
                )
            )
        return out

    async def by_project_for_user(
        self,
        db: AsyncSession,
        *,
        user_id: str,
        since: datetime | None = None,
    ) -> list[ProjectCost]:
        conditions = [
            SessionCost.user_id == user_id,
            SessionCost.project_id.is_not(None),
        ]
        if since is not None:
            conditions.append(SessionCost.created_at >= since)
        stmt = (
            select(
                SessionCost.project_id,
                func.coalesce(func.sum(SessionCost.input_tokens), 0),
                func.coalesce(func.sum(SessionCost.output_tokens), 0),
                func.coalesce(func.sum(SessionCost.cost_usd), 0),
            )
            .where(*conditions)
            .group_by(SessionCost.project_id)
            .order_by(func.sum(SessionCost.cost_usd).desc())
        )
        result = await db.execute(stmt)
        return [
            ProjectCost(
                project_id=str(r[0]),
                input_tokens=int(r[1]),
                output_tokens=int(r[2]),
                cost_usd=float(r[3]),
            )
            for r in result.all()
        ]


def _to_date(v: Any) -> date:
    """SQLite renvoie une string, Postgres un date - on harmonise."""
    if isinstance(v, date):
        return v
    return datetime.fromisoformat(str(v)).date()


cost_service = CostService()
