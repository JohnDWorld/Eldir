"""Résolution de la cible d'un dispatch.

Sans `nouveau_chantier`, on reprend la session la plus récente du projet :
c'est ce qui évite d'ouvrir une session par consigne. Avec, on en ouvre une
seconde, sinon deux chantiers parallèles sur un même repo sont impossibles
depuis un agent, alors que les worktrees les isolent déjà.
"""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from tests.unit.conftest_supervisor import pose_projet_et_session, service_superviseur


@pytest.mark.asyncio
async def test_sans_nouveau_chantier_on_reprend_la_session_existante(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as db:
        user_id, project_id, session_id = await pose_projet_et_session(db)

    service = service_superviseur(session_factory)
    cible, nom, cree = await service._resolve_target(
        user_id=user_id, project_id=project_id, session_id=None
    )
    assert nom == "Munin"
    assert cree is False
    assert cible == session_id


@pytest.mark.asyncio
async def test_nouveau_chantier_ouvre_une_seconde_session(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as db:
        user_id, project_id, session_id = await pose_projet_et_session(db)

    service = service_superviseur(session_factory)
    cible, nom, cree = await service._resolve_target(
        user_id=user_id,
        project_id=project_id,
        session_id=None,
        nouveau_chantier=True,
    )
    assert cree is True, "un second chantier doit ouvrir sa propre session"
    assert cible != session_id, "et ce doit être une AUTRE session"
    assert nom == "Munin"


@pytest.mark.asyncio
async def test_une_session_nommee_reste_prioritaire_sur_nouveau_chantier(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Demander une session précise ET un nouveau chantier est contradictoire.
    On honore la session nommée : c'est le choix le plus explicite des deux,
    et ouvrir une session de plus perdrait le travail que l'agent visait."""
    async with session_factory() as db:
        user_id, project_id, session_id = await pose_projet_et_session(db)

    service = service_superviseur(session_factory)
    cible, _, cree = await service._resolve_target(
        user_id=user_id,
        project_id=project_id,
        session_id=session_id,
        nouveau_chantier=True,
    )
    assert cible == session_id
    assert cree is False
