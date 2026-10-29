"""Les corps d'outils du superviseur, appelés directement.

Ils étaient des closures dans `_build_mcp_server`, donc intestables et
impossibles à servir par un second transport sans les réécrire. Deux
comportements qui divergent, c'est la panne qu'on paie six mois plus tard.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from app.core.constants import (
    SESSION_STATE_BLOCKED,
    SESSION_STATE_IDLE,
    SESSION_STATE_THINKING,
    SESSION_STATE_TOOL_USE,
    SESSION_STATE_WAITING_INPUT,
)
from app.core.exceptions import NotFoundError
from app.db.models import Project, User
from app.db.models import Session as SessionRow
from app.services.supervisor_service import SCHEMAS_OUTILS, SupervisorService
from mcp import types
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from tests.unit.conftest_supervisor import pose_projet_et_session, service_superviseur

# Un utilisateur qui ne ressemble à aucune valeur codée en dur dans le service :
# si l'adaptateur oubliait de passer le `user_id` capturé, ça se verrait.
UTILISATEUR = "u-capture-42"


async def _appelle(service: SupervisorService, nom: str, args: dict[str, Any], user_id: str) -> str:
    """Appelle un outil par l'adaptateur MCP in-process, comme le fait le SDK.

    Traverse les closures de `_build_mcp_server` (clés lues dans `args`,
    `user_id` capturé), que les appels directs aux méthodes `outil_*` ne
    touchent pas. Le `user_id` est obligatoire : une valeur par défaut qui
    coïnciderait avec l'attendu d'un test le rendrait inoffensif.
    """
    instance = service._build_mcp_server(user_id)["instance"]
    requete = types.CallToolRequest(
        method="tools/call",
        params=types.CallToolRequestParams(name=nom, arguments=args),
    )
    reponse = await instance.request_handlers[types.CallToolRequest](requete)
    return str(reponse.root.content[0].text)


async def _vieillit(
    db: AsyncSession, session_id: str, *, age: timedelta, state: str = SESSION_STATE_IDLE
) -> None:
    """Règle l'état ET l'âge d'une session posée par `pose_projet_et_session`.

    Les deux dans la même écriture : changer `state` seul déclencherait le
    `onupdate` de `updated_at` et rajeunirait la session à l'instant.
    """
    row = await db.get_one(SessionRow, session_id)
    row.state = state
    row.updated_at = datetime.now(UTC) - age
    await db.commit()


def _session(
    project_id: str,
    user_id: str,
    *,
    age: timedelta,
    state: str,
    is_system: bool = False,
) -> SessionRow:
    return SessionRow(
        project_id=project_id,
        user_id=user_id,
        branch="claude/x",
        model="claude-sonnet-5",
        state=state,
        is_system=is_system,
        updated_at=datetime.now(UTC) - age,
    )


def test_chaque_outil_a_une_description_et_un_schema_objet() -> None:
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
async def test_adaptateur_list_projects_filtre_sur_le_user_id_capture(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Le nom `list_projects` est câblé sur sa closure, avec le bon utilisateur."""
    async with session_factory() as db:
        proprio, project_id, _ = await pose_projet_et_session(db)
    service = service_superviseur(session_factory)

    texte = await _appelle(service, "list_projects", {}, proprio)
    assert f"Munin (id={project_id})" in texte
    assert "### " not in texte  # pas le rendu de list_sessions

    autre = await _appelle(service, "list_projects", {}, UTILISATEUR)
    assert autre == "Aucun projet branché sur Eldir."


@pytest.mark.asyncio
async def test_adaptateur_list_sessions_filtre_sur_le_user_id_capture(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Le nom `list_sessions` est câblé sur sa closure, avec le bon utilisateur."""
    async with session_factory() as db:
        proprio, project_id, session_id = await pose_projet_et_session(db)
    service = service_superviseur(session_factory)

    texte = await _appelle(service, "list_sessions", {}, proprio)
    assert f"### Munin · session {session_id}" in texte
    assert "dormante" in texte
    assert f"(id={project_id})" not in texte  # pas le rendu de list_projects

    autre = await _appelle(service, "list_sessions", {}, UTILISATEUR)
    assert autre == "Aucune session projet ouverte."


@pytest.mark.asyncio
async def test_dispatch_refuse_une_consigne_vide(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    service = service_superviseur(session_factory)
    texte = await service.outil_dispatch("u1", project_id="p1", consigne="  ")
    assert "obligatoire" in texte


@pytest.mark.asyncio
async def test_adaptateur_dispatch_sur_un_projet_inconnu_rend_une_erreur_lisible(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    service = service_superviseur(session_factory)
    texte = await _appelle(
        service, "dispatch", {"project_id": "p-fantome", "consigne": "fais x"}, UTILISATEUR
    )
    assert texte == "Erreur : Projet p-fantome introuvable."


@pytest.mark.parametrize(
    ("args", "session_attendue", "chantier_attendu"),
    [
        ({}, None, False),
        ({"session_id": "s1", "nouveau_chantier": True}, "s1", True),
        ({"session_id": "  ", "nouveau_chantier": False}, None, False),
    ],
)
@pytest.mark.asyncio
async def test_adaptateur_dispatch_transmet_session_et_nouveau_chantier(
    session_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
    args: dict[str, Any],
    session_attendue: str | None,
    chantier_attendu: bool,
) -> None:
    """`nouveau_chantier` et `session_id` doivent arriver jusqu'à la résolution.

    Sans ce test, supprimer la lecture de `nouveau_chantier` dans l'adaptateur
    laisserait toute la suite verte et ferait disparaître la fonction en silence.
    """
    recu: dict[str, Any] = {}

    async def espion(**kwargs: Any) -> tuple[str, str, bool]:
        recu.update(kwargs)
        raise NotFoundError("arret")

    service = service_superviseur(session_factory)
    monkeypatch.setattr(service, "_resolve_target", espion)

    texte = await _appelle(
        service, "dispatch", {"project_id": "p1", "consigne": "x", **args}, UTILISATEUR
    )

    assert texte == "Erreur : arret"
    assert recu == {
        "user_id": UTILISATEUR,
        "project_id": "p1",
        "session_id": session_attendue,
        "nouveau_chantier": chantier_attendu,
    }


@pytest.mark.asyncio
async def test_adaptateur_allow_publish_refuse_une_session_vide(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    # Refusée avant d'ouvrir la base : la double de SessionService n'a pas
    # `set_publish_allowed`, ce test échouerait donc si la garde sautait.
    service = service_superviseur(session_factory)
    texte = await _appelle(
        service, "allow_publish", {"session_id": " ", "autoriser": True}, UTILISATEUR
    )
    assert texte == "Erreur : session_id est obligatoire."


@pytest.mark.parametrize(
    ("autoriser", "etat"), [(True, "autorisée"), (False, "de nouveau bloquée")]
)
@pytest.mark.asyncio
async def test_adaptateur_allow_publish_transmet_autoriser(
    session_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
    autoriser: bool,
    etat: str,
) -> None:
    recu: dict[str, Any] = {}

    async def espion(_db: AsyncSession, **kwargs: Any) -> None:
        recu.update(kwargs)

    service = service_superviseur(session_factory)
    monkeypatch.setattr(service._sessions, "set_publish_allowed", espion, raising=False)

    texte = await _appelle(
        service, "allow_publish", {"session_id": "s1", "autoriser": autoriser}, UTILISATEUR
    )

    assert recu == {"user_id": UTILISATEUR, "session_id": "s1", "allowed": autoriser}
    assert texte.startswith(f"Publication {etat} pour la session s1.")


@pytest.mark.asyncio
async def test_adaptateur_remember_transmet_le_fait(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    service = service_superviseur(session_factory)
    texte = await _appelle(service, "remember", {"fait": "Toujours une PR."}, UTILISATEUR)
    assert texte == "Noté : Toujours une PR."


@pytest.mark.asyncio
async def test_remember_refuse_un_fait_vide(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    service = service_superviseur(session_factory)
    assert await service.outil_remember("u1", fait=" ") == "Erreur : 'fait' est vide."


def test_la_description_de_list_projects_annonce_qu_elle_sert_a_trier_ce_qui_dort() -> None:
    """Sans ces mots, l'agent ne saurait pas que l'outil porte la date."""
    description = SCHEMAS_OUTILS["list_projects"][0]
    assert "dernière activité" in description
    assert "dorment" in description


@pytest.mark.parametrize(
    ("age", "attendu"),
    [
        (timedelta(seconds=30), "à l'instant"),
        (timedelta(minutes=-5), "à l'instant"),  # horloge en avance : jamais d'âge négatif
        (timedelta(minutes=1), "il y a 1 min"),
        (timedelta(minutes=35), "il y a 35 min"),
        (timedelta(minutes=59, seconds=30), "il y a 59 min"),
        (timedelta(minutes=60), "il y a 1 h"),
        (timedelta(hours=3), "il y a 3 h"),
        (timedelta(hours=23, minutes=30), "il y a 23 h"),
        (timedelta(hours=24), "hier"),
        (timedelta(hours=47, minutes=30), "hier"),
        (timedelta(hours=48), "il y a 2 j"),
        (timedelta(days=12), "il y a 12 j"),
    ],
)
async def test_list_projects_dit_depuis_quand_un_projet_dort(
    session_factory: async_sessionmaker[AsyncSession],
    age: timedelta,
    attendu: str,
) -> None:
    """Sans date, « relance-moi sur un projet oublié » n'a aucune donnée pour
    tenir. `endswith` : une session au repos n'ajoute aucun suffixe d'attente."""
    async with session_factory() as db:
        proprio, _, session_id = await pose_projet_et_session(db)
        await _vieillit(db, session_id, age=age)
    service = service_superviseur(session_factory)

    texte = await _appelle(service, "list_projects", {}, proprio)
    assert texte.endswith(f"dernière activité : {attendu}")


async def test_list_projects_dit_qu_un_projet_sans_session_na_jamais_travaille(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as db:
        proprio, _, session_id = await pose_projet_et_session(db)
        await _vieillit(db, session_id, age=timedelta(days=3))
        db.add(
            Project(
                user_id=proprio,
                name="Hugin",
                slug="hugin",
                provider="github",
                repo_full_name="exemple/hugin",
                default_branch="main",
                workspace_path="/tmp/hugin",
            )
        )
        await db.commit()
    service = service_superviseur(session_factory)

    texte = await _appelle(service, "list_projects", {}, proprio)
    lignes = {ligne.split(" (")[0]: ligne for ligne in texte.splitlines()}
    assert lignes["- Hugin"].endswith("dernière activité : jamais travaillé")
    assert lignes["- Munin"].endswith("dernière activité : il y a 3 j")


async def test_list_projects_retient_la_session_la_plus_recente(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as db:
        proprio, projet, session_id = await pose_projet_et_session(db)
        await _vieillit(db, session_id, age=timedelta(days=12))
        db.add(_session(projet, proprio, age=timedelta(days=2), state=SESSION_STATE_IDLE))
        await db.commit()
    service = service_superviseur(session_factory)

    texte = await _appelle(service, "list_projects", {}, proprio)
    assert texte.endswith("dernière activité : il y a 2 j")


async def test_list_projects_dit_qu_une_session_attend_un_geste(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as db:
        proprio, _, session_id = await pose_projet_et_session(db)
        await _vieillit(db, session_id, age=timedelta(days=12), state=SESSION_STATE_WAITING_INPUT)
    service = service_superviseur(session_factory)

    texte = await _appelle(service, "list_projects", {}, proprio)
    assert texte.endswith("dernière activité : il y a 12 j · 1 session attend un geste de ta part")


async def test_list_projects_ne_compte_que_ce_qui_attend_un_geste(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """`waiting_input` et `blocked` comptent ; le travail en cours, le repos,
    la session d'un autre utilisateur et celle du superviseur ne comptent pas."""
    async with session_factory() as db:
        proprio, projet, session_id = await pose_projet_et_session(db)
        await _vieillit(db, session_id, age=timedelta(days=1), state=SESSION_STATE_WAITING_INPUT)
        autre = User(email="autre@exemple.lan", hashed_password="x")
        db.add(autre)
        await db.flush()
        un_jour = timedelta(days=1)
        db.add_all(
            [
                _session(projet, proprio, age=un_jour, state=SESSION_STATE_BLOCKED),
                _session(projet, proprio, age=un_jour, state=SESSION_STATE_IDLE),
                _session(projet, proprio, age=un_jour, state=SESSION_STATE_THINKING),
                _session(projet, proprio, age=un_jour, state=SESSION_STATE_TOOL_USE),
                _session(projet, autre.id, age=un_jour, state=SESSION_STATE_WAITING_INPUT),
                _session(projet, proprio, age=un_jour, state=SESSION_STATE_BLOCKED, is_system=True),
            ]
        )
        await db.commit()
    service = service_superviseur(session_factory)

    texte = await _appelle(service, "list_projects", {}, proprio)
    assert texte.endswith("· 2 sessions attendent un geste de ta part")
