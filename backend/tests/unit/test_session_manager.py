"""Tests unitaires du SessionManager.

L'instanciation réelle d'un `ClaudeSDKClient` requiert un token Anthropic
et lance un sous-process Node. On mocke `ClaudeSDKClient` et `ClaudeAgentOptions`
pour tester la mécanique du pool sans dépendance externe.
"""

from __future__ import annotations

import asyncio
import errno
import os
import sys
import threading
import types
from collections.abc import Iterator
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from app.core.config import get_settings
from app.core.exceptions import (
    EldirError,
    SessionAlreadyStartingError,
    SessionLimitError,
    SessionNotFoundError,
    SessionStartTimeoutError,
)
from app.services import session_container
from app.services.event_bus import EventBus
from app.services.remote_access_service import remote_access_service
from app.services.session_manager import (
    CHEMIN_ENROBAGE,
    MESSAGE_FLUX_SANS_RESULTAT,
    ActiveSession,
    SessionManager,
    options_de_conteneur,
)


@pytest.fixture
def fake_sdk(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    """Remplace le module `claude_agent_sdk` par un stub minimal."""
    module = types.ModuleType("claude_agent_sdk")

    class FakeClient:
        def __init__(self, *_: object, **__: object) -> None:
            self.connect = AsyncMock()
            self.disconnect = AsyncMock()
            self.query = AsyncMock()

        async def receive_response(self):
            if False:
                yield None

    class FakeOptions:
        def __init__(self, *args: object, **kwargs: object) -> None:
            self.args = args
            self.kwargs = kwargs

    class HookMatcher:
        def __init__(self, *args: object, **kwargs: object) -> None:
            self.args = args
            self.kwargs = kwargs

    module.ClaudeSDKClient = FakeClient  # type: ignore[attr-defined]
    module.ClaudeAgentOptions = FakeOptions  # type: ignore[attr-defined]
    module.HookMatcher = HookMatcher  # type: ignore[attr-defined]
    module.AssistantMessage = type("AssistantMessage", (), {})  # type: ignore[attr-defined]
    module.ResultMessage = type("ResultMessage", (), {})  # type: ignore[attr-defined]
    module.SystemMessage = type("SystemMessage", (), {})  # type: ignore[attr-defined]
    module.TextBlock = type("TextBlock", (), {})  # type: ignore[attr-defined]
    module.ToolUseBlock = type("ToolUseBlock", (), {})  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "claude_agent_sdk", module)
    return module  # type: ignore[return-value]


@pytest.fixture
def manager() -> SessionManager:
    bus = EventBus(redis=AsyncMock())
    return SessionManager(event_bus=bus)


async def test_start_registers_session(manager: SessionManager, fake_sdk: MagicMock) -> None:
    session = await manager.start(
        session_id="s1",
        project_id="p1",
        user_id="u1",
        cwd="/tmp",
    )
    assert session.session_id == "s1"
    assert manager.active_count == 1
    assert manager.get("s1") is session


async def test_start_enforces_concurrent_limit(
    manager: SessionManager, fake_sdk: MagicMock
) -> None:
    for i in range(get_settings().max_concurrent_sessions):
        await manager.start(
            session_id=f"s{i}",
            project_id="p",
            user_id="u",
            cwd="/tmp",
        )
    with pytest.raises(SessionLimitError):
        await manager.start(
            session_id="s_overflow",
            project_id="p",
            user_id="u",
            cwd="/tmp",
        )


async def test_start_donne_au_sdk_un_env_masque_et_complete(
    manager: SessionManager, fake_sdk: MagicMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Le masque arrive jusqu'au SDK, même quand le projet apporte des variables.

    `env_pour_la_session` est testée seule dans `test_env_sessions.py` ; ce
    test-ci garde le branchement, là où `update()` écrasait la clé `env`.
    """
    recus: list[dict[str, object]] = []
    options_d_origine = fake_sdk.ClaudeAgentOptions

    class OptionsEspion(options_d_origine):  # type: ignore[valid-type,misc]
        def __init__(self, *args: object, **kwargs: object) -> None:
            super().__init__(*args, **kwargs)
            recus.append(kwargs)

    monkeypatch.setattr(fake_sdk, "ClaudeAgentOptions", OptionsEspion)
    monkeypatch.setenv("JWT_SECRET", "valeur-sensible-du-backend")

    await manager.start(
        session_id="s1",
        project_id="p1",
        user_id="u1",
        cwd="/tmp",
        remote_host="eldir-machine",
    )

    env = recus[0]["env"]
    assert isinstance(env, dict)
    assert env["ELDIR_REMOTE_HOST"] == "eldir-machine"
    assert env["JWT_SECRET"] == ""


async def test_deux_demarrages_concurrents_ne_montent_qu_un_client(
    manager: SessionManager, fake_sdk: MagicMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Le second démarrage de la même session est refusé, pas doublé.

    Avant, les deux passaient : deux clients SDK montés, un seul gardé dans le
    pool, donc un processus orphelin, un compteur de sessions actives faux et
    deux tours concurrents dans le même arbre de travail. Il fallait une main
    rapide sur la souris ; un agent extérieur envoie deux dispatches dans la
    même milliseconde.
    """
    montes: list[object] = []

    class ClientLent:
        def __init__(self, *_: object, **__: object) -> None:
            montes.append(self)
            self.disconnect = AsyncMock()
            self.query = AsyncMock()

        async def connect(self) -> None:
            # Le vrai `connect` lance un sous-process : il rend la main, et
            # c'est pendant ce temps que le second démarrage arrive.
            await asyncio.sleep(0.01)

    monkeypatch.setattr(fake_sdk, "ClaudeSDKClient", ClientLent)

    resultats = await asyncio.gather(
        manager.start(session_id="s1", project_id="p1", user_id="u1", cwd="/tmp"),
        manager.start(session_id="s1", project_id="p1", user_id="u1", cwd="/tmp"),
        return_exceptions=True,
    )

    refus = [r for r in resultats if isinstance(r, BaseException)]
    assert len(refus) == 1, resultats
    assert isinstance(refus[0], SessionAlreadyStartingError)
    assert manager.active_count == 1
    assert len(montes) == 1, "un second client SDK laisserait un processus orphelin"

    # Et le marqueur est rendu : la session se reprend après un arrêt.
    await manager.stop("s1")
    await manager.start(session_id="s1", project_id="p1", user_id="u1", cwd="/tmp")
    assert manager.active_count == 1


async def test_get_unknown_raises(manager: SessionManager) -> None:
    with pytest.raises(SessionNotFoundError):
        manager.get("ghost")


async def test_stop_unknown_raises(manager: SessionManager) -> None:
    with pytest.raises(SessionNotFoundError):
        await manager.stop("ghost")


async def test_stop_disconnects_client(manager: SessionManager, fake_sdk: MagicMock) -> None:
    await manager.start(
        session_id="s1",
        project_id="p1",
        user_id="u1",
        cwd="/tmp",
    )
    active = manager.get("s1")
    await manager.stop("s1")
    assert manager.is_active("s1") is False
    assert active.client is not None
    active.client.disconnect.assert_awaited()  # type: ignore[attr-defined]


# ── Fin du flux d'un tour ───────────────────────────────────────
# Un tour finit par un résultat (STOP `turn_complete`), une erreur ou un arrêt. Le flux
# qui se ferme proprement sans résultat ne publiait rien : personne ne savait que le tour
# avait fini.


def _active_avec_flux(flux: object) -> ActiveSession:
    class Client:
        def receive_response(self) -> object:
            return flux

    return ActiveSession(
        session_id="s1",
        project_id="p1",
        user_id="u1",
        cwd="/tmp",
        client=Client(),  # type: ignore[arg-type]
    )


async def _evenements_du_tour(
    manager: SessionManager, fake_sdk: MagicMock, flux: object
) -> list[tuple[str, dict[str, object]]]:
    publies: list[tuple[str, dict[str, object]]] = []

    async def noter(_session_id: str, type_: str, data: dict[str, object]) -> None:
        publies.append((type_, data))

    manager.register_persist_callback(noter)
    await manager._consume_response(_active_avec_flux(flux))
    return [(t, d) for t, d in publies if t in ("stop", "error")]


async def test_un_flux_qui_se_ferme_sans_resultat_publie_une_erreur(
    manager: SessionManager, fake_sdk: MagicMock
) -> None:
    async def flux_vide():  # type: ignore[no-untyped-def]
        if False:
            yield None

    terminaux = await _evenements_du_tour(manager, fake_sdk, flux_vide())

    assert terminaux == [
        (
            "error",
            {"message": MESSAGE_FLUX_SANS_RESULTAT, "type": "StreamEndedWithoutResult"},
        )
    ]


async def test_un_flux_qui_finit_par_un_resultat_ne_publie_pas_d_erreur(
    manager: SessionManager, fake_sdk: MagicMock
) -> None:
    async def flux_complet():  # type: ignore[no-untyped-def]
        yield fake_sdk.ResultMessage()

    terminaux = await _evenements_du_tour(manager, fake_sdk, flux_complet())

    assert terminaux == [("stop", {"reason": "turn_complete"})]


async def test_un_flux_qui_leve_ne_publie_qu_une_erreur(
    manager: SessionManager, fake_sdk: MagicMock
) -> None:
    async def flux_qui_leve():  # type: ignore[no-untyped-def]
        raise RuntimeError("CLI coupé")
        yield None

    terminaux = await _evenements_du_tour(manager, fake_sdk, flux_qui_leve())

    assert terminaux == [("error", {"message": "CLI coupé", "type": "RuntimeError"})]


# ── Le mode conteneur ───────────────────────────────────────────
# La suite tourne en mode `processus` (son conftest l'exporte). Ces tests
# basculent en `conteneur` sur des racines jetables, sans démon : ils vérifient la
# décision et le branchement, pas le `docker run`. Un démarrage qui échoue à ce
# `docker run` est vérifié, avec un vrai démon, dans
# `tests/integration/test_isolement_sessions.py`.


@pytest.fixture
def mode_conteneur(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    """Le mode `conteneur` sur des racines jetables ; rend le worktree de `s1`.

    Le worktree et son clone suivent le layout de `WorktreeService`
    (`<user>/<repo>` et `<user>/<repo>.<session_id>`), sous `workspaces_root`.
    """
    worktree = tmp_path / "workspaces" / "u1" / "depot.s1"
    (tmp_path / "workspaces" / "u1" / "depot").mkdir(parents=True)
    worktree.mkdir()
    monkeypatch.setenv("SESSION_RUNTIME", "conteneur")
    monkeypatch.setenv("WORKSPACES_ROOT", str(tmp_path / "workspaces"))
    monkeypatch.setenv("CLAUDE_HOME_ROOT", str(tmp_path / "maisons"))
    # Sans ça, `materiel_de_session` lirait le vrai `config` SSH de la machine.
    monkeypatch.setenv("SSH_HOME", str(tmp_path / "ssh"))
    get_settings.cache_clear()
    yield worktree
    get_settings.cache_clear()


@pytest.fixture
def options_recues(fake_sdk: MagicMock, monkeypatch: pytest.MonkeyPatch) -> list[dict[str, object]]:
    """Les kwargs que le SDK reçoit à chaque `ClaudeAgentOptions(...)`."""
    recus: list[dict[str, object]] = []
    options_d_origine = fake_sdk.ClaudeAgentOptions

    class OptionsEspion(options_d_origine):  # type: ignore[valid-type,misc]
        def __init__(self, *args: object, **kwargs: object) -> None:
            super().__init__(*args, **kwargs)
            recus.append(kwargs)

    monkeypatch.setattr(fake_sdk, "ClaudeAgentOptions", OptionsEspion)
    return recus


async def test_en_mode_processus_rien_ne_change() -> None:
    """L'invariant que la suite entière prouve déjà, nommé une fois.

    La suite tourne en mode `processus` parce que son conftest l'exporte (le
    défaut du code, lui, est `conteneur`, cf. `Settings.session_runtime`). Elle
    prouve donc ce comportement à chaque exécution, et ce test le nomme pour que
    personne ne l'abîme sans le voir : en mode `processus`, aucune option de
    conteneur n'est posée, et le CLI reste celui que le SDK trouve tout seul.
    """
    assert get_settings().session_runtime == "processus"
    assert await options_de_conteneur(project_id="p1", session_id="s1", cwd="/tmp/x") == {}


async def test_en_mode_conteneur_le_cli_devient_l_enrobage(
    mode_conteneur: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    maison = tmp_path / "maisons" / "p1" / "tmp"
    vue_par_l_enrobage: list[bool] = []
    env_d_origine = session_container.env_pour_enrobage

    def espion(**kwargs: object) -> dict[str, str]:
        vue_par_l_enrobage.append(maison.is_dir())
        return env_d_origine(**kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(session_container, "env_pour_enrobage", espion)

    options = await options_de_conteneur(project_id="p1", session_id="s1", cwd=str(mode_conteneur))

    assert options["cli_path"] == str(CHEMIN_ENROBAGE)
    assert options["env"]["ELDIR_WORKTREE_SUBPATH"] == "u1/depot.s1"
    # la maison a été créée : `volume-subpath` l'exige
    assert maison.is_dir()
    # et avant le calcul de l'enrobage, comme le contrat de `session_container` le veut
    assert vue_par_l_enrobage == [True]


def test_l_enrobage_existe_et_est_executable() -> None:
    """Un `cli_path` qui ne pointe sur rien donne une erreur illisible du SDK."""
    assert CHEMIN_ENROBAGE.is_file()
    assert os.access(CHEMIN_ENROBAGE, os.X_OK)


async def test_start_en_mode_conteneur_pose_l_enrobage_et_garde_le_masque(
    manager: SessionManager,
    fake_sdk: MagicMock,
    options_recues: list[dict[str, object]],
    mode_conteneur: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Le branchement dans `start` : `cli_path` posé, et le masque intact.

    Les variables de l'enrobage s'ajoutent à l'environnement de la session. Si
    cette fusion écrasait la clé `env` au lieu de la compléter, c'est le défaut
    de `test_start_donne_au_sdk_un_env_masque_et_complete`, dans l'autre mode.
    """
    monkeypatch.setenv("JWT_SECRET", "valeur-sensible-du-backend")

    await manager.start(session_id="s1", project_id="p1", user_id="u1", cwd=str(mode_conteneur))

    recu = options_recues[0]
    assert recu["cli_path"] == str(CHEMIN_ENROBAGE)
    env = recu["env"]
    assert isinstance(env, dict)
    assert env["ELDIR_WORKTREE_SUBPATH"] == "u1/depot.s1"
    assert env["JWT_SECRET"] == ""


async def test_start_en_mode_processus_ne_pose_pas_de_cli_path(
    manager: SessionManager, fake_sdk: MagicMock, options_recues: list[dict[str, object]]
) -> None:
    await manager.start(session_id="s1", project_id="p1", user_id="u1", cwd="/tmp")

    assert "cli_path" not in options_recues[0]


async def test_une_decision_de_conteneur_qui_echoue_ne_retombe_pas_en_mode_processus(
    manager: SessionManager, fake_sdk: MagicMock, mode_conteneur: Path
) -> None:
    """Le repli silencieux est exactement ce qu'un attaquant veut provoquer.

    Un cwd hors de `workspaces_root` fait lever le calcul des montages. La
    session ne doit ni démarrer sans conteneur (aucun client SDK monté), ni
    rester dans le pool, ni garder le marqueur de démarrage : on peut réessayer.

    Mutation qui le fait tomber (mesurée) : que `options_de_conteneur` rende
    `{}` quand son calcul échoue.
    """
    montes: list[object] = []
    client_d_origine = fake_sdk.ClaudeSDKClient

    class ClientEspion(client_d_origine):  # type: ignore[valid-type,misc]
        def __init__(self, *args: object, **kwargs: object) -> None:
            super().__init__(*args, **kwargs)
            montes.append(self)

    fake_sdk.ClaudeSDKClient = ClientEspion

    with pytest.raises(ValueError):
        await manager.start(session_id="s1", project_id="p1", user_id="u1", cwd="/tmp")

    assert montes == [], "un client monté ici serait le repli vers le mode non isolé"
    assert manager.active_count == 0
    assert not manager.is_active("s1")

    # Le marqueur de démarrage est rendu : le même identifiant se réessaie.
    await manager.start(session_id="s1", project_id="p1", user_id="u1", cwd=str(mode_conteneur))
    assert len(montes) == 1
    assert manager.active_count == 1


async def test_stop_efface_la_matiere_ssh_de_la_session(
    manager: SessionManager, fake_sdk: MagicMock, mode_conteneur: Path, tmp_path: Path
) -> None:
    """La copie de clé d'une session arrêtée ne reste pas sur le disque."""
    dossier = tmp_path / "maisons" / "p1-ssh" / "s1"
    dossier.mkdir(parents=True)
    (dossier / "cle").write_text("copie-de-cle", encoding="utf-8")
    voisine = tmp_path / "maisons" / "p1-ssh" / "s2"
    voisine.mkdir()
    await manager.start(session_id="s1", project_id="p1", user_id="u1", cwd=str(mode_conteneur))

    await manager.stop("s1")

    assert not dossier.exists()
    assert voisine.is_dir(), "la matière d'une autre session du projet n'est pas touchée"


async def test_stop_efface_la_matiere_meme_si_la_publication_echoue(
    fake_sdk: MagicMock, mode_conteneur: Path, tmp_path: Path
) -> None:
    """Redis qui coupe fait lever `_publish` : la copie de clé part quand même."""
    redis = AsyncMock()
    manager = SessionManager(event_bus=EventBus(redis=redis))
    dossier = tmp_path / "maisons" / "p1-ssh" / "s1"
    dossier.mkdir(parents=True)
    (dossier / "cle").write_text("copie-de-cle", encoding="utf-8")
    await manager.start(session_id="s1", project_id="p1", user_id="u1", cwd=str(mode_conteneur))
    redis.publish.side_effect = ConnectionError("redis coupé")

    with pytest.raises(ConnectionError):
        await manager.stop("s1")

    assert not dossier.exists()


# ── Un démarrage qui tombe ne laisse pas de clé derrière lui ────
# Un démarrage qui échoue n'entre jamais dans le pool : `stop` ne passera pas,
# et rien d'autre ne balaie la copie de clé que `options_de_conteneur` vient
# d'écrire. `start` la retire lui-même.


@pytest.fixture
def projet_distant(mode_conteneur: Path) -> None:
    """`p1` a un accès distant : sa session aura une copie de clé à écrire."""
    cle = remote_access_service.key_path("p1")
    cle.parent.mkdir(parents=True, exist_ok=True)
    cle.write_text("cle-factice-p1", encoding="utf-8")
    os.chmod(cle, 0o600)
    remote_access_service._write_block("p1", "eldir-un", "un.exemple.lan", "deploy", 22)


@pytest.fixture
def connexion_qui_echoue(fake_sdk: MagicMock, monkeypatch: pytest.MonkeyPatch) -> SimpleNamespace:
    """Un client SDK dont le `connect` échoue, comme un `docker run` qui échoue.

    Rend `rappels`, la liste des fonctions appelées au moment du `connect`
    juste avant l'échec, et `construits`, les clients montés.
    """
    etat = SimpleNamespace(rappels=[], construits=[])

    class ClientQuiEchoue:
        def __init__(self, *_: object, **__: object) -> None:
            etat.construits.append(self)
            self.disconnect = AsyncMock()

        async def connect(self) -> None:
            for rappel in etat.rappels:
                rappel()
            raise RuntimeError("docker run a échoué")

    monkeypatch.setattr(fake_sdk, "ClaudeSDKClient", ClientQuiEchoue)
    return etat


async def test_un_connect_qui_echoue_ne_laisse_pas_de_matiere_ssh(
    manager: SessionManager,
    projet_distant: None,
    connexion_qui_echoue: SimpleNamespace,
    mode_conteneur: Path,
    tmp_path: Path,
) -> None:
    """La copie de clé existe quand le `connect` échoue, et a disparu après.

    Le dossier du projet est comme avant : la matière d'une autre session du
    même projet n'est pas touchée.
    """
    projet = tmp_path / "maisons" / "p1-ssh"
    dossier = projet / "s1"
    voisine = projet / "s2"
    voisine.mkdir(parents=True)
    (voisine / "cle").write_text("copie-de-s2", encoding="utf-8")
    vu_au_connect: list[list[str]] = []
    connexion_qui_echoue.rappels.append(
        lambda: vu_au_connect.append(sorted(f.name for f in dossier.iterdir()))
    )

    with pytest.raises(RuntimeError):
        await manager.start(session_id="s1", project_id="p1", user_id="u1", cwd=str(mode_conteneur))

    # sans cette ligne, le test passerait aussi si la matière n'était jamais écrite
    assert vu_au_connect == [["cle", "config"]]
    assert not dossier.exists()
    assert sorted(f.name for f in projet.iterdir()) == ["s2"]
    assert (voisine / "cle").read_text(encoding="utf-8") == "copie-de-s2"
    assert manager.active_count == 0


async def test_un_calcul_de_conteneur_qui_echoue_apres_la_cle_ne_la_laisse_pas(
    manager: SessionManager,
    fake_sdk: MagicMock,
    projet_distant: None,
    mode_conteneur: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`options_de_conteneur` écrit la clé avant de calculer l'environnement.

    Un cwd hors de `workspaces_root` fait lever ce calcul une fois la clé
    écrite : `options_de_conteneur` ne rend rien, `start` ne peut donc pas se
    fier à son résultat pour savoir s'il y a quelque chose à effacer.
    """
    dossier = tmp_path / "maisons" / "p1-ssh" / "s1"
    vu_au_calcul: list[bool] = []
    env_d_origine = session_container.env_pour_enrobage

    def espion(**kwargs: object) -> dict[str, str]:
        vu_au_calcul.append(dossier.is_dir())
        return env_d_origine(**kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(session_container, "env_pour_enrobage", espion)

    with pytest.raises(ValueError):
        await manager.start(session_id="s1", project_id="p1", user_id="u1", cwd="/tmp")

    assert vu_au_calcul == [True]
    assert not dossier.exists()


async def test_un_connect_qui_depasse_le_delai_ne_laisse_pas_de_matiere_ssh(
    manager: SessionManager,
    fake_sdk: MagicMock,
    projet_distant: None,
    mode_conteneur: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Le vrai délai dépassé reste annoncé comme tel, et nettoie lui aussi."""
    clients: list[object] = []

    class ClientQuiNeRepondPas:
        def __init__(self, *_: object, **__: object) -> None:
            clients.append(self)
            self.disconnect = AsyncMock()

        async def connect(self) -> None:
            await asyncio.sleep(10)

    monkeypatch.setattr(fake_sdk, "ClaudeSDKClient", ClientQuiNeRepondPas)
    monkeypatch.setattr("app.services.session_manager.SESSION_CONNECT_TIMEOUT_S", 0.05)
    publies: list[tuple[str, dict[str, object]]] = []

    async def noter(_session_id: str, type_: str, data: dict[str, object]) -> None:
        publies.append((type_, data))

    manager.register_persist_callback(noter)

    with pytest.raises(SessionStartTimeoutError):
        await manager.start(session_id="s1", project_id="p1", user_id="u1", cwd=str(mode_conteneur))

    clients[0].disconnect.assert_awaited()  # type: ignore[attr-defined]
    assert [d["type"] for t, d in publies if t == "error"] == ["ConnectTimeout"]
    assert not (tmp_path / "maisons" / "p1-ssh" / "s1").exists()
    assert manager.active_count == 0


async def test_une_erreur_de_disque_au_calcul_n_est_pas_annoncee_comme_un_delai(
    manager: SessionManager, fake_sdk: MagicMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`TimeoutError` est aussi un `OSError` `ETIMEDOUT` : seul le `connect` compte.

    Lue comme un CLI qui ne répond pas, une erreur de volume ferait chercher la
    cause au mauvais endroit.
    """

    async def echoue(**_: object) -> dict[str, object]:
        raise OSError(errno.ETIMEDOUT, "volume qui ne répond pas")

    monkeypatch.setattr("app.services.session_manager.options_de_conteneur", echoue)
    publies: list[str] = []

    async def noter(_session_id: str, type_: str, _data: dict[str, object]) -> None:
        publies.append(type_)

    manager.register_persist_callback(noter)

    with pytest.raises(OSError, match="volume qui ne répond pas"):
        await manager.start(session_id="s1", project_id="p1", user_id="u1", cwd="/tmp")

    assert "error" not in publies


async def test_un_demarrage_reussi_garde_sa_matiere_jusqu_a_l_arret(
    manager: SessionManager,
    fake_sdk: MagicMock,
    projet_distant: None,
    mode_conteneur: Path,
    tmp_path: Path,
) -> None:
    """Le chemin réussi est intact : la clé vit autant que la session."""
    dossier = tmp_path / "maisons" / "p1-ssh" / "s1"

    await manager.start(session_id="s1", project_id="p1", user_id="u1", cwd=str(mode_conteneur))

    assert sorted(f.name for f in dossier.iterdir()) == ["cle", "config"]

    await manager.stop("s1")

    assert not dossier.exists()


async def test_pendant_l_effacement_d_un_demarrage_tombe_un_reessai_est_refuse(
    manager: SessionManager,
    projet_distant: None,
    connexion_qui_echoue: SimpleNamespace,
    mode_conteneur: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Le marqueur n'est rendu qu'après l'effacement.

    Rendu avant, un réessai concurrent écrirait sa matière que l'effacement en
    cours détruirait : la session repartirait sans sa clé, sans le dire.
    """
    entre, libere = threading.Event(), threading.Event()

    def efface_lentement(_project_id: str, _session_id: str) -> None:
        entre.set()
        libere.wait(5)

    monkeypatch.setattr(remote_access_service, "supprimer_materiel_de_session", efface_lentement)
    premier = asyncio.create_task(
        manager.start(session_id="s1", project_id="p1", user_id="u1", cwd=str(mode_conteneur))
    )
    assert await asyncio.to_thread(entre.wait, 5), "l'effacement n'a jamais commencé"

    try:
        with pytest.raises(SessionAlreadyStartingError):
            await manager.start(
                session_id="s1", project_id="p1", user_id="u1", cwd=str(mode_conteneur)
            )
    finally:
        libere.set()
    with pytest.raises(RuntimeError):
        await premier

    # et le marqueur est bien rendu ensuite : le même identifiant se réessaie
    with pytest.raises(RuntimeError):
        await manager.start(session_id="s1", project_id="p1", user_id="u1", cwd=str(mode_conteneur))


async def test_un_connect_qui_echoue_n_est_pas_retente_sans_conteneur(
    manager: SessionManager,
    connexion_qui_echoue: SimpleNamespace,
    options_recues: list[dict[str, object]],
    mode_conteneur: Path,
) -> None:
    """Le repli, tel que l'invariant le craint, vérifié sans démon.

    Un `connect` qui échoue ne doit pas déclencher un second client, monté sans
    `cli_path`, donc sans conteneur. Le test d'intégration le tient aussi, mais
    il saute sans Docker, et c'est là que la plupart lancent cette suite.

    Mutation qui le fait tomber (mesurée) : `start` qui retente sans `cli_path`
    quand le `connect` échoue.
    """
    with pytest.raises(RuntimeError):
        await manager.start(session_id="s1", project_id="p1", user_id="u1", cwd=str(mode_conteneur))

    assert len(connexion_qui_echoue.construits) == 1
    # sans cette ligne, `all` passerait sur une liste vide
    assert options_recues
    assert all(o.get("cli_path") == str(CHEMIN_ENROBAGE) for o in options_recues)
    assert manager.active_count == 0


async def test_une_valeur_inattendue_du_mode_tombe_dans_la_branche_isolee(
    mode_conteneur: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Seul `processus` est ouvert ; tout le reste prend le chemin du conteneur.

    Le `Literal` de `Settings` rend une autre valeur inatteignable : on en
    fournit une au code, pour que la comparaison reste écrite du bon côté.
    """
    monkeypatch.setattr(
        "app.services.session_manager.get_settings",
        lambda: SimpleNamespace(session_runtime="inattendu"),
    )

    options = await options_de_conteneur(project_id="p1", session_id="s1", cwd=str(mode_conteneur))

    assert options["cli_path"] == str(CHEMIN_ENROBAGE)


async def test_un_effacement_qui_leve_ne_garde_pas_le_marqueur_de_demarrage(
    manager: SessionManager,
    connexion_qui_echoue: SimpleNamespace,
    mode_conteneur: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Le `discard` est dans un `finally` : un effacement qui lève ne le saute pas.

    Un marqueur qui fuit interdirait toute reprise de la session jusqu'au
    redémarrage. Le second démarrage doit donc échouer pour la même raison que
    le premier, et pas parce qu'il serait « déjà en cours ».

    Mutation qui le fait tomber (mesurée) : `try/finally` remplacé par deux
    instructions à la suite.
    """

    def echoue(_project_id: str, _session_id: str) -> None:
        raise EldirError("effacement impossible")

    monkeypatch.setattr(remote_access_service, "supprimer_materiel_de_session", echoue)

    for _ in range(2):
        with pytest.raises(EldirError, match="effacement impossible"):
            await manager.start(
                session_id="s1", project_id="p1", user_id="u1", cwd=str(mode_conteneur)
            )


async def test_materiel_de_session_ne_fige_pas_la_boucle(
    manager: SessionManager,
    fake_sdk: MagicMock,
    mode_conteneur: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """La copie de clé part dans un thread : tenue, elle ne fige pas la boucle.

    Appelée sur place, elle bloquerait la boucle jusqu'à la fin du `wait`, et le
    démarrage serait terminé quand le test reprend la main.
    """
    entre, libere = threading.Event(), threading.Event()

    def lente(_project_id: str, _session_id: str) -> None:
        entre.set()
        libere.wait(5)

    monkeypatch.setattr(remote_access_service, "materiel_de_session", lente)
    premier = asyncio.create_task(
        manager.start(session_id="s1", project_id="p1", user_id="u1", cwd=str(mode_conteneur))
    )
    assert await asyncio.to_thread(entre.wait, 5), "la copie n'a jamais commencé"
    try:
        assert not premier.done()
    finally:
        libere.set()
    await premier
    assert manager.is_active("s1")


async def test_stop_efface_la_matiere_avant_de_deconnecter(
    manager: SessionManager,
    fake_sdk: MagicMock,
    mode_conteneur: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """L'effacement suit la sortie du pool, il n'attend pas le `disconnect`.

    Le `disconnect` peut durer `SESSION_DISCONNECT_TIMEOUT_S` secondes, pendant
    lesquelles l'identifiant n'est ni dans le pool ni dans le marqueur : une
    reprise y écrirait sa matière, qu'un effacement tardif détruirait.

    L'effacement est tenu dans son thread : tant qu'il l'est, le `disconnect`
    ne doit pas avoir eu lieu. Cela observe aussi le thread : sur place,
    l'effacement figerait la boucle, et l'arrêt serait fini quand le test
    reprend la main.

    Mutation qui le fait tomber : l'effacement déplacé après le `disconnect`.
    """
    evenements: list[str] = []
    entre, libere = threading.Event(), threading.Event()

    def efface_lentement(_project_id: str, _session_id: str) -> None:
        evenements.append("efface")
        entre.set()
        libere.wait(5)

    async def deconnecte() -> None:
        evenements.append("disconnect")

    monkeypatch.setattr(remote_access_service, "supprimer_materiel_de_session", efface_lentement)
    await manager.start(session_id="s1", project_id="p1", user_id="u1", cwd=str(mode_conteneur))
    manager.get("s1").client.disconnect = AsyncMock(side_effect=deconnecte)  # type: ignore[union-attr]

    arret = asyncio.create_task(manager.stop("s1"))
    assert await asyncio.to_thread(entre.wait, 5), "l'effacement n'a jamais commencé"
    try:
        assert evenements == ["efface"]
        assert not arret.done()
        assert not manager.is_active("s1"), "déjà sortie du pool"
    finally:
        libere.set()
    await arret

    assert evenements == ["efface", "disconnect"]


async def test_stop_deconnecte_meme_si_l_effacement_leve(
    manager: SessionManager,
    fake_sdk: MagicMock,
    mode_conteneur: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Un effacement qui lève ne laisse pas un conteneur ouvert.

    La session est déjà sortie du pool : si `disconnect` était sauté, plus rien
    ne reviendrait fermer son CLI.

    Mutation qui le fait tomber : le `try/finally` autour de l'effacement
    remplacé par deux instructions à la suite.
    """

    def echoue(_project_id: str, _session_id: str) -> None:
        raise EldirError("effacement impossible")

    monkeypatch.setattr(remote_access_service, "supprimer_materiel_de_session", echoue)
    await manager.start(session_id="s1", project_id="p1", user_id="u1", cwd=str(mode_conteneur))
    client = manager.get("s1").client

    with pytest.raises(EldirError, match="effacement impossible"):
        await manager.stop("s1")

    client.disconnect.assert_awaited()  # type: ignore[union-attr]


async def test_stop_sans_projet_n_efface_rien(manager: SessionManager, fake_sdk: MagicMock) -> None:
    """La session superviseur n'a pas de projet, donc pas de matière SSH.

    Sans la garde sur `project_id`, `supprimer_materiel_de_session` refuserait
    un identifiant vide et l'arrêt lèverait.
    """
    await manager.start(session_id="s1", project_id=None, user_id="u1", cwd="/tmp")

    await manager.stop("s1")

    assert not manager.is_active("s1")
