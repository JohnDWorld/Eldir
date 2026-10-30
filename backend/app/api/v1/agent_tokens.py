"""Routes /agent-tokens - les jetons des agents externes branchés sur /api/mcp/.

Un jeton qu'on ne peut pas révoquer est un jeton qu'on ne peut pas émettre :
l'émission et la révocation vivent donc ensemble, ici.
"""

from __future__ import annotations

from fastapi import APIRouter, status

from app.core.deps import CurrentUserId, DbDep
from app.schemas.agent_token import AgentTokenCreated, AgentTokenInput, AgentTokenRead
from app.services import agent_token_service

router = APIRouter(prefix="/agent-tokens", tags=["agent-tokens"])


@router.get("", response_model=list[AgentTokenRead])
async def list_agent_tokens(user_id: CurrentUserId, db: DbDep) -> list[AgentTokenRead]:
    lignes = await agent_token_service.lister(db, user_id=user_id)
    return [AgentTokenRead.model_validate(ligne) for ligne in lignes]


@router.post("", response_model=AgentTokenCreated, status_code=status.HTTP_201_CREATED)
async def create_agent_token(
    payload: AgentTokenInput, user_id: CurrentUserId, db: DbDep
) -> AgentTokenCreated:
    ligne, clair = await agent_token_service.emettre(db, user_id=user_id, label=payload.label)
    await db.commit()
    return AgentTokenCreated(**AgentTokenRead.model_validate(ligne).model_dump(), token=clair)


@router.delete("/{token_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_agent_token(token_id: str, user_id: CurrentUserId, db: DbDep) -> None:
    await agent_token_service.revoquer(db, user_id=user_id, token_id=token_id)
    # Le service ne commit pas. Sans ce commit la route répondrait 204 et le jeton
    # resterait valide : l'objet en mémoire porte déjà `revoked_at`, la base non.
    await db.commit()
