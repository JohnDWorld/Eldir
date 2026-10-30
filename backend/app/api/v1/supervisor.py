"""Routes /supervisor - la session Eldir qui orchestre les autres.

Volontairement minuscules : une fois la session obtenue, le chat, le stream WS
et les coûts passent par les routes /sessions existantes. S'y ajoute la mémoire
des agents extérieurs, que John doit pouvoir lire et nettoyer : lui seul le peut.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.core.deps import CurrentUserId, DbDep
from app.schemas.agent_memory import AgentMemoryEntry, AgentMemoryForget, AgentMemoryRead
from app.schemas.session import SessionRead
from app.services.singletons import get_supervisor_service
from app.services.supervisor_service import (
    PREFERENCE_LONGUEUR_MAX,
    PREFERENCES_AGENT_MAX,
    decouper_ligne_d_agent,
)

router = APIRouter(prefix="/supervisor", tags=["supervisor"])


@router.post("/session", response_model=SessionRead)
async def ensure_supervisor_session(user_id: CurrentUserId, db: DbDep) -> SessionRead:
    """Démarre (ou reprend) la session superviseur et la renvoie. Idempotent."""
    session = await get_supervisor_service().ensure_session(db, user_id)
    await db.commit()
    return SessionRead.model_validate(session)


def _memoire(lignes: list[str]) -> AgentMemoryRead:
    entries = []
    for ligne in lignes:
        agent, fait = decouper_ligne_d_agent(ligne)
        entries.append(AgentMemoryEntry(agent=agent, text=fait, line=ligne))
    return AgentMemoryRead(
        entries=entries, max_entries=PREFERENCES_AGENT_MAX, max_length=PREFERENCE_LONGUEUR_MAX
    )


@router.get("/agent-memory", response_model=AgentMemoryRead)
async def read_agent_memory(user_id: CurrentUserId) -> AgentMemoryRead:
    """Les préférences que des agents extérieurs ont écrites dans le prompt du superviseur."""
    return _memoire(await get_supervisor_service().preferences_d_agents())


@router.post("/agent-memory/forget", response_model=AgentMemoryRead)
async def forget_agent_memory(
    payload: AgentMemoryForget, user_id: CurrentUserId
) -> AgentMemoryRead:
    """Retire une préférence d'agent (désignée par sa ligne exacte) et rend la mémoire restante."""
    service = get_supervisor_service()
    await service.oublier_preference_d_agent(payload.line)
    return _memoire(await service.preferences_d_agents())
