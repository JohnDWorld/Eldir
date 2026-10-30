"""Les deux portes lisent l'en-tête `Authorization` de la même façon.

L'API REST (`get_current_user_id`) et la garde MCP (`GardeJeton`) décident chacune
si un en-tête est un Bearer complet. Deux lectures qui ne seraient pas la même
fonction finissent par diverger : une forme que l'une tolère et que l'autre
refuse, sans que personne l'ait voulu. Ici chaque forme passe par les deux portes
avec un jeton valide POUR cette porte ; seule la forme de l'en-tête varie. Un
statut 401 ne dit pas qui a refusé (la lecture de l'en-tête, ou le décodeur du
jeton) : c'est le motif qui le dit, et `test_tout_refus_de_forme_vient_de_la_lecture_de_l_en_tete`
le contrôle pour chaque forme refusée.
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


REFUSEES = [forme for forme, acceptee in FORMES if not acceptee]


@pytest.mark.parametrize("forme", REFUSEES)
async def test_tout_refus_de_forme_vient_de_la_lecture_de_l_en_tete(
    client: AsyncClient, jeton_agent: str, forme: str
) -> None:
    """Chaque forme refusée l'est par la lecture de l'en-tête, avec le même motif sur les
    deux portes : si c'était le décodeur du jeton, le motif serait « Jeton invalide » et
    renverrait l'intéressé chercher le mauvais défaut. Le jeton est valide pour chaque
    porte : seule la forme est en cause."""
    rest = await client.get(
        "/api/v1/system-prompts",
        headers={"Authorization": forme.format(jeton=create_access_token("u-test"))},
    )
    transport = ASGITransport(app=GardeJeton(_app_atteinte))
    async with AsyncClient(transport=transport, base_url="http://test") as mcp:
        garde = await mcp.post("/", headers={"Authorization": forme.format(jeton=jeton_agent)})
    attendu = "Header Authorization manquant ou mal formé."
    assert (rest.json()["message"], garde.json()["message"]) == (attendu, attendu)
