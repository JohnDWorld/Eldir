"""Résolution de la cible d'un dispatch.

Sans `nouveau_chantier`, on reprend la session la plus récente du projet :
c'est ce qui évite d'ouvrir une session par consigne. Avec, on en ouvre une
seconde, sinon deux chantiers parallèles sur un même repo sont impossibles
depuis un agent, alors que les worktrees les isolent déjà.
"""

from __future__ import annotations

import pytest
from app.core.exceptions import NotFoundError, SessionLimitError
from app.db.models import Session as SessionRow
from app.db.models import User
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


@pytest.mark.asyncio
async def test_un_projet_d_un_autre_utilisateur_est_introuvable(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """L'isolation entre utilisateurs : un projet d'autrui ne se dispatche pas.

    Sans la garde, la résolution ouvrirait une session sur le projet d'un autre.
    """
    async with session_factory() as db:
        _, project_id, _ = await pose_projet_et_session(db)

    service = service_superviseur(session_factory)
    with pytest.raises(NotFoundError, match=project_id):
        await service._resolve_target(user_id="u-autre", project_id=project_id, session_id=None)


@pytest.mark.asyncio
async def test_une_session_d_un_autre_utilisateur_est_introuvable(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Même avec un projet à soi, on ne reprend pas la session de quelqu'un d'autre."""
    async with session_factory() as db:
        user_id, project_id, _ = await pose_projet_et_session(db)
        autre = User(email="autre@exemple.lan", hashed_password="x")
        db.add(autre)
        await db.flush()
        etrangere = SessionRow(
            project_id=project_id,
            user_id=autre.id,
            branch="claude/etrangere",
            worktree_path="/tmp/munin-wt3",
            model="claude-sonnet-5",
            sdk_session_id="sdk-3",
        )
        db.add(etrangere)
        await db.commit()
        session_etrangere = etrangere.id

    service = service_superviseur(session_factory)
    with pytest.raises(NotFoundError, match=session_etrangere):
        await service._resolve_target(
            user_id=user_id, project_id=project_id, session_id=session_etrangere
        )


@pytest.mark.asyncio
async def test_le_plafond_de_sessions_actives_arrive_a_l_agent_en_francais(
    session_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """C'est le premier refus qu'un dispatcheur autonome rencontre.

    `outil_dispatch` n'attrapait que `NotFoundError` : une `SessionLimitError`
    sortait de l'outil et arrivait à l'agent enveloppée en anglais par la
    bibliothèque MCP, alors que cette surface promet des refus en français qui
    commencent par « Erreur : ».
    """
    async with session_factory() as db:
        user_id, project_id, _ = await pose_projet_et_session(db)
    service = service_superviseur(session_factory)

    async def plein(*_args: object, **_kwargs: object) -> None:
        raise SessionLimitError("Limite de 8 sessions actives atteinte.")

    monkeypatch.setattr(service._sessions, "create_and_start", plein)

    texte = await service.outil_dispatch(
        user_id,
        project_id=project_id,
        consigne="Range le garage.",
        nouveau_chantier=True,
    )
    assert texte == "Erreur : Limite de 8 sessions actives atteinte."


@pytest.mark.asyncio
async def test_une_session_systeme_ne_se_dispatche_pas(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Un agent ne délivre pas une consigne dans la session superviseur.

    C'est la seule des quatre gardes `is_system` dont l'agent choisit la
    valeur : `list_projects`, `list_sessions` et la reprise de la session la
    plus récente filtrent déjà. Livrée là, la consigne arriverait comme un tour
    utilisateur sans marque d'auteur, donc indistinguable pour le modèle de ce
    que John aurait tapé, alors que c'est exactement le trou que la marque
    d'auteur ferme sur `remember`.
    """
    async with session_factory() as db:
        user_id, project_id, _ = await pose_projet_et_session(db)
        superviseur = SessionRow(
            project_id=project_id,
            user_id=user_id,
            branch="claude/superviseur",
            worktree_path="/tmp/munin-wt4",
            model="claude-sonnet-5",
            sdk_session_id="sdk-4",
            is_system=True,
            system_kind="supervisor",
        )
        db.add(superviseur)
        await db.commit()
        session_systeme = superviseur.id

    service = service_superviseur(session_factory)
    with pytest.raises(NotFoundError, match=session_systeme):
        await service._resolve_target(
            user_id=user_id, project_id=project_id, session_id=session_systeme
        )
