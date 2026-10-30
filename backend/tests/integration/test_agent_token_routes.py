"""Routes des jetons d'agent : le clair n'apparaît qu'une fois, et révoquer coupe pour de vrai.

Chaque requête de ces tests ouvre sa propre session de base (cf. la fixture
`client`), et les vérifications « la base a bien changé » passent par une session
encore autre. C'est ce qui distingue une route qui commit d'une route qui répond
204 sans rien écrire : dans une seule session, l'objet en mémoire porterait déjà
`revoked_at` et le test réussirait quand même.
"""

from __future__ import annotations

import pytest
from app.core.exceptions import AuthenticationError
from app.db.models import AgentToken
from app.services import agent_token_service
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

Fabrique = async_sessionmaker[AsyncSession]


async def _creer(
    client: AsyncClient, entetes: dict[str, str], label: str = "agent du test"
) -> dict:
    reponse = await client.post("/api/v1/agent-tokens", json={"label": label}, headers=entetes)
    assert reponse.status_code == 201, reponse.text
    return reponse.json()


async def _nombre_de_jetons(factory: Fabrique) -> int:
    async with factory() as db:
        return (await db.execute(select(func.count()).select_from(AgentToken))).scalar_one()


async def test_le_clair_est_rendu_a_la_creation_puis_jamais(
    client: AsyncClient, entetes_john: dict[str, str]
) -> None:
    cree = await _creer(client, entetes_john, "eldir du village")
    assert cree["token"], "le clair est rendu à la création"
    assert cree["label"] == "eldir du village"
    assert cree["revoked_at"] is None
    assert cree["last_used_at"] is None

    reponse = await client.get("/api/v1/agent-tokens", headers=entetes_john)
    assert reponse.status_code == 200
    liste = reponse.json()
    assert [ligne["id"] for ligne in liste] == [cree["id"]]
    assert "token" not in liste[0], "on ne stocke pas le clair, donc on ne le réaffiche pas"
    assert cree["token"] not in reponse.text


async def test_le_jeton_cree_ouvre_la_porte_depuis_une_autre_session(
    client: AsyncClient, entetes_john: dict[str, str], session_factory: Fabrique
) -> None:
    """Le clair rendu est le vrai : sans commit à la création, la ligne serait perdue
    et l'agent recevrait « jeton inconnu » avec un jeton que John vient de copier."""
    cree = await _creer(client, entetes_john, "eldir du village")
    async with session_factory() as db:
        user_id, label = await agent_token_service.authentifier(db, jeton=cree["token"])
    assert (user_id, label) == ("u-test", "eldir du village")


async def test_revoquer_coupe_le_jeton_pour_une_autre_session(
    client: AsyncClient, entetes_john: dict[str, str], session_factory: Fabrique
) -> None:
    """Le service ne commit pas : c'est la route qui le fait. Sans son commit, le
    bouton « Révoquer » affichait un succès et ne coupait rien."""
    cree = await _creer(client, entetes_john)

    reponse = await client.delete(f"/api/v1/agent-tokens/{cree['id']}", headers=entetes_john)

    assert reponse.status_code == 204
    async with session_factory() as db:
        with pytest.raises(AuthenticationError, match="révoqué"):
            await agent_token_service.authentifier(db, jeton=cree["token"])
    liste = (await client.get("/api/v1/agent-tokens", headers=entetes_john)).json()
    assert liste[0]["revoked_at"] is not None


async def test_la_liste_dit_quand_le_jeton_a_servi(
    client: AsyncClient, entetes_john: dict[str, str], session_factory: Fabrique
) -> None:
    """C'est ce qui permet de repérer un jeton qui ne sert plus avant de le couper."""
    cree = await _creer(client, entetes_john)
    async with session_factory() as db:
        await agent_token_service.authentifier(db, jeton=cree["token"])
        await db.commit()
    liste = (await client.get("/api/v1/agent-tokens", headers=entetes_john)).json()
    assert liste[0]["last_used_at"] is not None


async def test_chacun_ne_voit_et_ne_coupe_que_ses_jetons(
    client: AsyncClient, entetes_john: dict[str, str], session_factory: Fabrique
) -> None:
    async with session_factory() as db:
        _, clair_d_un_autre = await agent_token_service.emettre(
            db, user_id="u-autre", label="agent d'un autre"
        )
        await db.commit()
        ligne_d_un_autre = (await db.execute(select(AgentToken))).scalar_one()

    liste = (await client.get("/api/v1/agent-tokens", headers=entetes_john)).json()
    assert liste == []

    reponse = await client.delete(
        f"/api/v1/agent-tokens/{ligne_d_un_autre.id}", headers=entetes_john
    )
    assert reponse.status_code == 404
    assert reponse.json()["code"] == "not_found"
    async with session_factory() as db:
        _, label = await agent_token_service.authentifier(db, jeton=clair_d_un_autre)
    assert label == "agent d'un autre", "le jeton d'un autre n'a pas été coupé"


async def test_revoquer_un_jeton_inconnu_est_un_404(
    client: AsyncClient, entetes_john: dict[str, str]
) -> None:
    reponse = await client.delete("/api/v1/agent-tokens/inconnu", headers=entetes_john)
    assert reponse.status_code == 404


@pytest.mark.parametrize("libelle", ["", "   ", "x" * 81])
async def test_un_libelle_vide_ou_trop_long_est_refuse_en_francais(
    client: AsyncClient,
    entetes_john: dict[str, str],
    session_factory: Fabrique,
    libelle: str,
) -> None:
    reponse = await client.post(
        "/api/v1/agent-tokens", json={"label": libelle}, headers=entetes_john
    )
    assert reponse.status_code == 422
    corps = reponse.json()
    # L'enveloppe d'Eldir et son message, pas le `detail` brut de FastAPI : c'est
    # `message` que l'interface affiche.
    assert corps["code"] == "validation_error"
    assert "80" in corps["message"]
    assert await _nombre_de_jetons(session_factory) == 0


async def test_un_libelle_de_80_caracteres_est_accepte(
    client: AsyncClient, entetes_john: dict[str, str]
) -> None:
    cree = await _creer(client, entetes_john, "x" * 80)
    assert len(cree["label"]) == 80


async def test_un_jeton_d_agent_ne_gere_pas_les_jetons(
    client: AsyncClient, jeton_agent: str, session_factory: Fabrique
) -> None:
    """Un agent dont le jeton fuit ne doit pas pouvoir en émettre un autre, ni couper
    celui de John : ces routes ne s'ouvrent qu'avec un jeton de connexion."""
    entetes = {"Authorization": f"Bearer {jeton_agent}"}
    assert (await client.get("/api/v1/agent-tokens", headers=entetes)).status_code == 401
    cree = await client.post("/api/v1/agent-tokens", json={"label": "rebond"}, headers=entetes)
    assert cree.status_code == 401
    assert (await client.delete("/api/v1/agent-tokens/x", headers=entetes)).status_code == 401
    assert await _nombre_de_jetons(session_factory) == 1


async def test_sans_jeton_de_connexion_la_porte_est_fermee(client: AsyncClient) -> None:
    assert (await client.get("/api/v1/agent-tokens")).status_code == 401
