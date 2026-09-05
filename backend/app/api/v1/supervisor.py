"""Route /supervisor - la session Eldir qui orchestre les autres.

Volontairement minuscule : une fois la session obtenue, le chat, le stream WS
et les coûts passent par les routes /sessions existantes.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.core.deps import CurrentUserId, DbDep
from app.schemas.session import SessionRead
from app.services.singletons import get_supervisor_service

router = APIRouter(prefix="/supervisor", tags=["supervisor"])


@router.post("/session", response_model=SessionRead)
async def ensure_supervisor_session(user_id: CurrentUserId, db: DbDep) -> SessionRead:
    """Démarre (ou reprend) la session superviseur et la renvoie. Idempotent."""
    session = await get_supervisor_service().ensure_session(db, user_id)
    await db.commit()
    return SessionRead.model_validate(session)
