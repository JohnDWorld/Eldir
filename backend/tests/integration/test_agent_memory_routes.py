"""Routes de la mémoire des agents : John voit ce que ses agents ont écrit dans le
prompt de son superviseur, et en fait le ménage.

L'agent ne peut pas s'en charger lui-même : quand la mémoire est pleine il reçoit un
refus que lui seul lit, et ces routes ne s'ouvrent qu'avec un jeton de connexion.
"""

from __future__ import annotations

import pytest
from app.api.v1 import supervisor as route_supervisor
from app.services import singletons
from app.services.supervisor_service import (
    PREFERENCE_LONGUEUR_MAX,
    PREFERENCES_AGENT_MAX,
    SUPERVISOR_PREFS_SLUG,
    SupervisorService,
)
from app.services.system_prompt_service import system_prompt_service
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from tests.unit.conftest_supervisor import service_superviseur

Fabrique = async_sessionmaker[AsyncSession]
MEMOIRE = "/api/v1/supervisor/agent-memory"


@pytest.fixture
def service(session_factory: Fabrique, monkeypatch: pytest.MonkeyPatch) -> SupervisorService:
    """Le superviseur que les routes obtiennent par `get_supervisor_service()`."""
    instance = service_superviseur(session_factory)
    monkeypatch.setattr(singletons, "_supervisor", instance)
    return instance


async def _prompt(factory: Fabrique) -> str:
    async with factory() as db:
        return (await system_prompt_service.get(db, SUPERVISOR_PREFS_SLUG)).content


async def test_la_memoire_vide_dit_ses_bornes_telles_que_remember_les_applique(
    client: AsyncClient, entetes_john: dict[str, str], service: SupervisorService
) -> None:
    reponse = await client.get(MEMOIRE, headers=entetes_john)
    assert reponse.status_code == 200
    # Lues sur les constantes de `remember`, pas recopiées : un seul endroit où les changer.
    assert reponse.json() == {
        "entries": [],
        "max_entries": PREFERENCES_AGENT_MAX,
        "max_length": PREFERENCE_LONGUEUR_MAX,
    }


async def test_les_bornes_viennent_des_constantes_et_non_d_une_copie(
    client: AsyncClient,
    entetes_john: dict[str, str],
    service: SupervisorService,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(route_supervisor, "PREFERENCES_AGENT_MAX", 7)
    monkeypatch.setattr(route_supervisor, "PREFERENCE_LONGUEUR_MAX", 123)
    corps = (await client.get(MEMOIRE, headers=entetes_john)).json()
    assert (corps["max_entries"], corps["max_length"]) == (7, 123)


async def test_la_memoire_dit_qui_a_ecrit_quoi_et_ne_montre_pas_les_lignes_de_john(
    client: AsyncClient, entetes_john: dict[str, str], service: SupervisorService
) -> None:
    await service.remember_preference("Toujours une PR.")
    await service.remember_preference("Sur Munin, une PR.", libelle_agent="assistant de bureau")

    corps = (await client.get(MEMOIRE, headers=entetes_john)).json()

    assert corps["entries"] == [
        {
            "agent": "assistant de bureau",
            "text": "Sur Munin, une PR.",
            "line": "- [agent « assistant de bureau »] Sur Munin, une PR.",
        }
    ]


async def test_oublier_retire_la_ligne_et_rend_la_memoire_restante(
    client: AsyncClient,
    entetes_john: dict[str, str],
    service: SupervisorService,
    session_factory: Fabrique,
) -> None:
    await service.remember_preference("Toujours une PR.")
    await service.remember_preference("Fait A.", libelle_agent="A")
    await service.remember_preference("Fait B.", libelle_agent="B")

    reponse = await client.post(
        f"{MEMOIRE}/forget", json={"line": "- [agent « A »] Fait A."}, headers=entetes_john
    )

    assert reponse.status_code == 200
    assert [e["agent"] for e in reponse.json()["entries"]] == ["B"]
    # Relu depuis une autre session de base : c'est le prompt qui a changé, pas la réponse.
    assert (await _prompt(session_factory)).splitlines() == [
        "- Toujours une PR.",
        "- [agent « B »] Fait B.",
    ]
    relue = (await client.get(MEMOIRE, headers=entetes_john)).json()
    assert [e["agent"] for e in relue["entries"]] == ["B"]


async def test_oublier_ne_touche_pas_a_une_ligne_de_john(
    client: AsyncClient,
    entetes_john: dict[str, str],
    service: SupervisorService,
    session_factory: Fabrique,
) -> None:
    await service.remember_preference("Toujours une PR.")
    avant = await _prompt(session_factory)

    reponse = await client.post(
        f"{MEMOIRE}/forget", json={"line": "- Toujours une PR."}, headers=entetes_john
    )

    assert reponse.status_code == 404
    assert reponse.json()["code"] == "not_found"
    assert await _prompt(session_factory) == avant


async def test_oublier_une_ligne_deja_retiree_est_un_404(
    client: AsyncClient, entetes_john: dict[str, str], service: SupervisorService
) -> None:
    reponse = await client.post(
        f"{MEMOIRE}/forget", json={"line": "- [agent « A »] Fait A."}, headers=entetes_john
    )
    assert reponse.status_code == 404


async def test_le_menage_par_la_route_libere_une_place_pour_l_agent(
    client: AsyncClient, entetes_john: dict[str, str], service: SupervisorService
) -> None:
    """Le scénario de bout en bout : mémoire pleine, l'agent refusé, John retire une
    ligne depuis l'écran, l'agent peut de nouveau noter."""
    for i in range(PREFERENCES_AGENT_MAX):
        await service.remember_preference(f"Fait {i}.", libelle_agent="A")
    assert (await service.remember_preference("De trop.", libelle_agent="A")).startswith("Erreur")
    corps = (await client.get(MEMOIRE, headers=entetes_john)).json()
    assert len(corps["entries"]) == corps["max_entries"]

    await client.post(
        f"{MEMOIRE}/forget", json={"line": corps["entries"][0]["line"]}, headers=entetes_john
    )

    assert await service.remember_preference("De trop.", libelle_agent="A") == "Noté : De trop."


async def test_un_jeton_d_agent_ne_lit_ni_ne_nettoie_la_memoire(
    client: AsyncClient, jeton_agent: str, service: SupervisorService, session_factory: Fabrique
) -> None:
    """Un agent qui pourrait effacer les lignes des autres, ou les siennes une fois
    refusé, contournerait la borne qui existe justement pour lui."""
    await service.remember_preference("Fait A.", libelle_agent="A")
    avant = await _prompt(session_factory)
    entetes = {"Authorization": f"Bearer {jeton_agent}"}

    assert (await client.get(MEMOIRE, headers=entetes)).status_code == 401
    oubli = await client.post(
        f"{MEMOIRE}/forget", json={"line": "- [agent « A »] Fait A."}, headers=entetes
    )
    assert oubli.status_code == 401
    assert await _prompt(session_factory) == avant


async def test_sans_jeton_de_connexion_la_memoire_est_fermee(client: AsyncClient) -> None:
    assert (await client.get(MEMOIRE)).status_code == 401
    assert (await client.post(f"{MEMOIRE}/forget", json={"line": "x"})).status_code == 401
