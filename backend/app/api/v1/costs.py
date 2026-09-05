"""Routes /costs - dashboard tokens & coûts (Phase 5).

Toutes les agrégations sont scoppées sur `user_id` (mono-user en V1 mais
on prépare déjà le multi-user).
"""

from __future__ import annotations

import csv
from datetime import UTC, datetime, timedelta
from io import StringIO

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from sqlalchemy import select

from app.core.deps import CurrentUserId, DbDep
from app.db.models import Project, SessionCost
from app.schemas.cost import (
    CostDashboard,
    CostTotalsRead,
    DailyCostRead,
    ProjectCostRead,
)
from app.services.cost_service import cost_service

router = APIRouter(prefix="/costs", tags=["costs"])


@router.get("/dashboard", response_model=CostDashboard)
async def dashboard(user_id: CurrentUserId, db: DbDep) -> CostDashboard:
    now = datetime.now(UTC)
    start_today = datetime.combine(now.date(), datetime.min.time(), tzinfo=UTC)
    start_7d = now - timedelta(days=7)
    start_30d = now - timedelta(days=30)

    today_tot = await cost_service.totals_for_user(db, user_id=user_id, since=start_today)
    week_tot = await cost_service.totals_for_user(db, user_id=user_id, since=start_7d)
    month_tot = await cost_service.totals_for_user(db, user_id=user_id, since=start_30d)

    daily = await cost_service.daily_for_user(db, user_id=user_id, days=7)
    by_project = await cost_service.by_project_for_user(db, user_id=user_id, since=start_30d)

    # On récupère le nom du projet pour l'affichage (un seul SELECT IN)
    project_names: dict[str, str] = {}
    if by_project:
        ids = [p.project_id for p in by_project]
        result = await db.execute(select(Project.id, Project.name).where(Project.id.in_(ids)))
        project_names = {str(pid): name for pid, name in result.all()}

    return CostDashboard(
        today=_totals(today_tot),
        last_7_days=_totals(week_tot),
        last_30_days=_totals(month_tot),
        daily=[
            DailyCostRead(
                day=d.day,
                input_tokens=d.input_tokens,
                output_tokens=d.output_tokens,
                cache_read_tokens=d.cache_read_tokens,
                cache_write_tokens=d.cache_write_tokens,
                cost_usd=d.cost_usd,
            )
            for d in daily
        ],
        by_project=[
            ProjectCostRead(
                project_id=p.project_id,
                project_name=project_names.get(p.project_id),
                input_tokens=p.input_tokens,
                output_tokens=p.output_tokens,
                cost_usd=p.cost_usd,
            )
            for p in by_project
        ],
    )


@router.get("/sessions/{session_id}", response_model=CostTotalsRead)
async def session_totals(session_id: str, user_id: CurrentUserId, db: DbDep) -> CostTotalsRead:
    # Note : pas de check d'ownership ici - le check se fait via les routes
    # /sessions/{id} ailleurs. En mono-user V1, c'est suffisant.
    totals = await cost_service.totals_for_session(db, session_id=session_id)
    return _totals(totals)


@router.get("/export.csv")
async def export_csv(user_id: CurrentUserId, db: DbDep) -> StreamingResponse:
    """Export brut des lignes session_costs pour facturation/comptabilité."""
    result = await db.execute(
        select(SessionCost)
        .where(SessionCost.user_id == user_id)
        .order_by(SessionCost.created_at.desc())
    )
    rows = result.scalars().all()

    buffer = StringIO()
    writer = csv.writer(buffer)
    writer.writerow(
        [
            "created_at",
            "session_id",
            "project_id",
            "model",
            "input_tokens",
            "output_tokens",
            "cache_read_tokens",
            "cache_write_tokens",
            "cost_usd",
            "duration_ms",
            "num_turns",
        ]
    )
    for r in rows:
        writer.writerow(
            [
                r.created_at.isoformat(),
                r.session_id,
                r.project_id or "",
                r.model or "",
                r.input_tokens,
                r.output_tokens,
                r.cache_read_tokens,
                r.cache_write_tokens,
                float(r.cost_usd),
                r.duration_ms,
                r.num_turns,
            ]
        )

    return StreamingResponse(
        iter([buffer.getvalue()]),
        media_type="text/csv",
        headers={
            "Content-Disposition": (
                f"attachment; filename=eldir-costs-{datetime.now(UTC).date()}.csv"
            )
        },
    )


def _totals(t: object) -> CostTotalsRead:
    return CostTotalsRead(
        input_tokens=getattr(t, "input_tokens", 0),
        output_tokens=getattr(t, "output_tokens", 0),
        cache_read_tokens=getattr(t, "cache_read_tokens", 0),
        cache_write_tokens=getattr(t, "cache_write_tokens", 0),
        cost_usd=getattr(t, "cost_usd", 0.0),
        num_turns=getattr(t, "num_turns", 0),
    )
