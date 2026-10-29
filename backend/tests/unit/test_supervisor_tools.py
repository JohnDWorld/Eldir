"""Les corps d'outils du superviseur, appelés directement.

Ils étaient des closures dans `_build_mcp_server`, donc intestables et
impossibles à servir par un second transport sans les réécrire. Deux
comportements qui divergent, c'est la panne qu'on paie six mois plus tard.
"""

from __future__ import annotations

from typing import Any

import pytest
from app.core.exceptions import NotFoundError
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
