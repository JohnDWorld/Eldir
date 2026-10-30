"""Schémas des jetons d'agent.

`AgentTokenCreated` porte le clair, `AgentTokenRead` jamais : c'est la
différence qui garantit qu'on ne le réaffiche pas par accident. Le clair n'est
pas stocké, il n'existe qu'au moment de la création.
"""

from __future__ import annotations

from datetime import datetime

from app.schemas.common import EldirModel


class AgentTokenInput(EldirModel):
    # Pas de borne ici : c'est `agent_token_service.emettre` qui la fixe et qui la
    # dit en français dans l'enveloppe d'erreur d'Eldir. Une borne répétée dans ce
    # schéma ferait répondre FastAPI avant, en `detail` brut, sans le message.
    label: str


class AgentTokenRead(EldirModel):
    id: str
    label: str
    created_at: datetime
    last_used_at: datetime | None
    revoked_at: datetime | None


class AgentTokenCreated(AgentTokenRead):
    # Rendu une seule fois, à la création. Non stocké.
    token: str
