"""Les deux portes lisent l'en-tête `Authorization` de la même façon.

L'API REST (`get_current_user_id`) et la garde MCP (`GardeJeton`) décident chacune
si un en-tête est un Bearer complet. Deux lectures qui ne seraient pas la même
fonction finissent par diverger : une forme que l'une tolère et que l'autre
refuse, sans que personne l'ait voulu. Ici chaque forme passe par les deux portes
avec un jeton valide POUR cette porte ; seule la forme de l'en-tête varie, donc
tout refus vient de la lecture de l'en-tête et de rien d'autre.
"""

from __future__ import annotations

import pytest
from app import mcp_http
from app.core.security import create_access_token
from app.mcp_http import GardeJeton
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from starlette.types import Receive, Scope, Send

# (forme de l'en-tête, acceptée ?). `{jeton}` est remplacé par un jeton valide.
FORMES = [
    ("Bearer {jeton}", True),
    ("bearer {jeton}", True),
    ("BEARER {jeton}", True),
    ("Bearer", False),
    ("Bearer ", False),
    ("{jeton}", False),
    ("Basic {jeton}", False),
    ("Token {jeton}", False),
    ("Bearer {jeton} {jeton}", False),
    ("Bearer\t{jeton}", False),
    ("", False),
]


async def _app_atteinte(scope: Scope, receive: Receive, send: Send) -> None:
    """L'app derrière la garde : si elle répond, la garde a laissé passer."""
    await send({"type": "http.response.start", "status": 204, "headers": []})
    await send({"type": "http.response.body", "body": b""})


async def _statut_rest(client: AsyncClient, valeur: str) -> int:
    reponse = await client.get("/api/v1/system-prompts", headers={"Authorization": valeur})
    return reponse.status_code


async def _statut_mcp(valeur: str) -> int:
    transport = ASGITransport(app=GardeJeton(_app_atteinte))
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        reponse = await client.post("/", headers={"Authorization": valeur})
    return reponse.status_code


@pytest.fixture(autouse=True)
def base_de_test(
    monkeypatch: pytest.MonkeyPatch, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    monkeypatch.setattr(mcp_http, "async_session_factory", session_factory)


@pytest.mark.parametrize(("forme", "acceptee"), FORMES)
async def test_la_porte_rest_lit_l_en_tete_comme_prevu(
    client: AsyncClient, forme: str, acceptee: bool
) -> None:
    jeton = create_access_token("u-test")
    statut = await _statut_rest(client, forme.format(jeton=jeton))
    assert statut == (200 if acceptee else 401)


@pytest.mark.parametrize(("forme", "acceptee"), FORMES)
async def test_la_garde_mcp_lit_l_en_tete_comme_prevu(
    jeton_agent: str, forme: str, acceptee: bool
) -> None:
    statut = await _statut_mcp(forme.format(jeton=jeton_agent))
    assert statut == (204 if acceptee else 401)


async def test_l_absence_d_en_tete_est_refusee_par_les_deux_portes(client: AsyncClient) -> None:
    assert (await client.get("/api/v1/system-prompts")).status_code == 401
    transport = ASGITransport(app=GardeJeton(_app_atteinte))
    async with AsyncClient(transport=transport, base_url="http://test") as mcp:
        assert (await mcp.post("/")).status_code == 401


@pytest.mark.parametrize("valeur", ["Basic x", "Bearer", "Bearer ", "x"])
async def test_les_deux_portes_refusent_un_en_tete_mal_forme_avec_le_meme_motif(
    client: AsyncClient, valeur: str
) -> None:
    """Un seul texte d'erreur, et c'est celui de l'en-tête : sans le contrôle de
    forme, `Bearer` sans jeton irait jusqu'au décodeur et dirait « Jeton invalide »,
    ce qui renverrait l'intéressé chercher le mauvais défaut."""
    rest = await client.get("/api/v1/system-prompts", headers={"Authorization": valeur})
    transport = ASGITransport(app=GardeJeton(_app_atteinte))
    async with AsyncClient(transport=transport, base_url="http://test") as mcp:
        garde = await mcp.post("/", headers={"Authorization": valeur})
    attendu = "Header Authorization manquant ou mal formé."
    assert (rest.json()["message"], garde.json()["message"]) == (attendu, attendu)
