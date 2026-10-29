"""Les corps d'outils du superviseur, appelés directement.

Ils étaient des closures dans `_build_mcp_server`, donc intestables et
impossibles à servir par un second transport sans les réécrire. Deux
comportements qui divergent, c'est la panne qu'on paie six mois plus tard.
"""

from __future__ import annotations

import pytest
from app.services.supervisor_service import SCHEMAS_OUTILS
from mcp import types
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from tests.unit.conftest_supervisor import pose_projet_et_session, service_superviseur


def test_les_cinq_outils_sont_decrits_une_seule_fois() -> None:
    assert set(SCHEMAS_OUTILS) == {
        "list_projects",
        "list_sessions",
        "dispatch",
        "allow_publish",
        "remember",
    }
    for nom, (description, schema) in SCHEMAS_OUTILS.items():
        assert description.strip(), nom
        assert schema["type"] == "object", nom


@pytest.mark.asyncio
async def test_le_serveur_in_process_publie_exactement_la_table(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Ce que le modèle lit vient de la table, pas d'une seconde copie."""
    service = service_superviseur(session_factory)
    instance = service._build_mcp_server("u1")["instance"]
    requete = types.ListToolsRequest(method="tools/list")
    reponse = await instance.request_handlers[types.ListToolsRequest](requete)

    publies = {t.name: (t.description, t.inputSchema) for t in reponse.root.tools}
    assert publies == SCHEMAS_OUTILS


@pytest.mark.asyncio
async def test_sans_projet_list_projects_le_dit(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    service = service_superviseur(session_factory)
    assert "Aucun projet" in await service.outil_list_projects("u-inconnu")


@pytest.mark.asyncio
async def test_list_projects_et_list_sessions_listent_ce_qui_existe(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as db:
        user_id, project_id, session_id = await pose_projet_et_session(db)
    service = service_superviseur(session_factory)

    projets = await service.outil_list_projects(user_id)
    assert f"Munin (id={project_id})" in projets

    sessions = await service.outil_list_sessions(user_id)
    assert f"session {session_id}" in sessions
    assert "dormante" in sessions


@pytest.mark.asyncio
async def test_dispatch_refuse_une_consigne_vide(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    service = service_superviseur(session_factory)
    texte = await service.outil_dispatch("u1", project_id="p1", consigne="  ")
    assert "obligatoire" in texte


@pytest.mark.asyncio
async def test_dispatch_sur_un_projet_inconnu_rend_une_erreur_lisible(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    service = service_superviseur(session_factory)
    texte = await service.outil_dispatch("u1", project_id="p-fantome", consigne="fais x")
    assert texte == "Erreur : Projet p-fantome introuvable."


@pytest.mark.asyncio
async def test_allow_publish_refuse_une_session_vide(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    # Refusée avant d'ouvrir la base : la double de SessionService n'a pas
    # `set_publish_allowed`, ce test échouerait donc si la garde sautait.
    service = service_superviseur(session_factory)
    texte = await service.outil_allow_publish("u1", session_id=" ", autoriser=True)
    assert "obligatoire" in texte


@pytest.mark.asyncio
async def test_remember_refuse_un_fait_vide(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    service = service_superviseur(session_factory)
    assert await service.outil_remember("u1", fait=" ") == "Erreur : 'fait' est vide."
