"""Le mode d'exécution des sessions, et les noms de volumes qu'il exige.

Le défaut du code est `conteneur`, le mode qui isole : un réglage oublié coûte
de la disponibilité, jamais l'isolement. `processus` ne s'obtient que par un
réglage explicite, et il ne protège rien : le CLI tourne dans le conteneur du
backend, qui voit le disque de tous les projets. La suite le demande (cf.
`tests/conftest.py`), parce qu'elle tourne sans démon Docker. Le mode d'une
installation servie se décide dans le compose de prod, où il est écrit en clair.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from pathlib import Path

import pytest
from app.core.config import Settings, get_settings
from app.services.session_container import (
    chemin_du_clone,
    env_pour_enrobage,
    preparer_la_maison,
)

COMPOSE_PROD = Path(__file__).parents[3] / "docker-compose.yml"


def test_le_mode_par_defaut_est_conteneur(monkeypatch: pytest.MonkeyPatch) -> None:
    """Le défaut doit isoler, même quand on a oublié de le régler.

    La suite exporte `SESSION_RUNTIME=processus` (cf. `tests/conftest.py`) et
    un `.env` local peut le fixer aussi : on écarte les deux, pour lire le
    défaut du code et rien d'autre.
    """
    monkeypatch.delenv("SESSION_RUNTIME", raising=False)
    assert Settings(_env_file=None).session_runtime == "conteneur"


def test_le_compose_de_prod_demande_le_mode_conteneur() -> None:
    """Le mode de prod s'écrit dans le compose, là où l'opérateur le lit.

    Le défaut du code porte déjà `conteneur` : la ligne ne change pas le
    comportement, elle rend le choix visible. Le test la garde contre une
    suppression silencieuse. L'ancrage compte : une ligne commentée
    (`# SESSION_RUNTIME: conteneur`) ne doit pas passer pour la vraie.
    """
    texte = COMPOSE_PROD.read_text(encoding="utf-8")
    assert re.search(r"^\s+SESSION_RUNTIME: conteneur$", texte, re.MULTILINE)


def test_les_noms_de_volumes_portent_le_prefixe_du_projet_compose() -> None:
    """Compose préfixe le nom d'un volume par celui du projet.

    Le compose de prod déclare `name: eldir` et un volume `eldir_workspaces` :
    le démon, lui, ne connaît que `eldir_eldir_workspaces`. Un `docker run`
    sur le nom non préfixé créerait un volume vide tout neuf, et la session
    démarrerait sur un worktree inexistant.
    """
    reglages = Settings()
    texte = COMPOSE_PROD.read_text(encoding="utf-8")
    assert re.search(r"^name: eldir$", texte, re.MULTILINE)
    for nom in (
        reglages.workspaces_volume,
        reglages.toolchains_volume,
        reglages.claude_home_volume,
        reglages.collectes_volume,
    ):
        assert nom.startswith("eldir_eldir_"), nom
        # Le volume existe bien sous son nom court dans le compose.
        assert f"\n  {nom.removeprefix('eldir_')}:\n" in texte


@pytest.fixture
def workspaces(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    """Un faux disque Eldir : un clone, son worktree, et un projet voisin."""
    racine = tmp_path / "workspaces"
    (racine / "u1" / "eldir").mkdir(parents=True)
    (racine / "u1" / "eldir.s1").mkdir()
    (racine / "u2" / "voisin").mkdir(parents=True)
    monkeypatch.setenv("WORKSPACES_ROOT", str(racine))
    monkeypatch.setenv("CLAUDE_HOME_ROOT", str(tmp_path / "maisons"))
    monkeypatch.setenv("TOOLCHAINS_ROOT", str(tmp_path / "toolchains"))
    monkeypatch.setenv("COLLECTES_ROOT", str(tmp_path / "collectes"))
    get_settings.cache_clear()
    yield racine
    get_settings.cache_clear()


def test_le_clone_canonique_se_deduit_du_worktree(workspaces: Path) -> None:
    """Sans ce montage, git ne fonctionne pas du tout dans la session.

    Le `.git` d'un worktree est un fichier qui pointe vers
    `<clone>/.git/worktrees/<nom>`. Mesuré : worktree monté seul, `git status`
    répond `fatal: not a git repository`.
    """
    assert chemin_du_clone(workspaces / "u1" / "eldir.s1") == workspaces / "u1" / "eldir"


def test_un_cwd_sans_point_n_a_pas_de_clone(workspaces: Path) -> None:
    """Le cwd du superviseur, qui n'est le worktree de rien."""
    (workspaces / "_supervisor").mkdir()
    assert chemin_du_clone(workspaces / "_supervisor") is None


def test_les_montages_de_base_sont_calcules(workspaces: Path) -> None:
    env = env_pour_enrobage(
        project_id="p1", worktree_abs=workspaces / "u1" / "eldir.s1", ssh_subpath=None
    )

    assert env["ELDIR_WORKTREE_ABS"] == str(workspaces / "u1" / "eldir.s1")
    assert env["ELDIR_WORKTREE_SUBPATH"] == "u1/eldir.s1"
    assert env["ELDIR_CLONE_SUBPATH"] == "u1/eldir"
    assert env["ELDIR_CLAUDE_HOME_SUBPATH"] == "p1"
    assert env["ELDIR_IMAGE"] == get_settings().session_image
    assert env["ELDIR_NETWORK"] == get_settings().session_network


def test_sans_toolchain_installe_aucun_montage_de_toolchain(workspaces: Path) -> None:
    """Un sous-chemin absent ferait échouer `docker run` en code 127.

    Un projet dont le toolchain n'est pas installé n'a pas de dossier dans ce
    volume : le montage doit disparaître, pas pointer vers rien.
    """
    env = env_pour_enrobage(
        project_id="p1", worktree_abs=workspaces / "u1" / "eldir.s1", ssh_subpath=None
    )
    assert "ELDIR_TOOLCHAIN_SUBPATH" not in env
    assert "ELDIR_COLLECTE_SUBPATH" not in env


def test_aucun_secret_ne_sort_dans_l_environnement_de_l_enrobage(
    workspaces: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """L'enrobage n'a pas besoin d'un seul secret, donc il n'en reçoit aucun.

    Chaque champ de `Settings` typé `SecretStr` reçoit sa sentinelle dans
    l'environnement. Deux volets : aucune sentinelle ne sort, quel que soit le
    nom de la clé qui la porte, et aucune clé ne porte le nom exact d'un champ
    secret, même vide.

    Non couvert : `database_url` et `redis_url` ne sont pas typés secret. Un mot
    de passe dans une DSN échappe aux deux volets, faute de champ à lister.
    """
    noms_secrets = [
        nom for nom, champ in Settings.model_fields.items() if "Secret" in str(champ.annotation)
    ]
    for nom in noms_secrets:
        monkeypatch.setenv(nom.upper(), f"sentinelle-{nom}")
    get_settings.cache_clear()

    env = env_pour_enrobage(
        project_id="p1", worktree_abs=workspaces / "u1" / "eldir.s1", ssh_subpath=None
    )

    rendu = "\n".join(f"{c}={v}" for c, v in env.items())
    fuites = [nom for nom in noms_secrets if f"sentinelle-{nom}" in rendu]
    assert fuites == []
    assert {nom.upper() for nom in noms_secrets}.isdisjoint(env)


def test_la_maison_est_creee_avant_le_lancement(workspaces: Path) -> None:
    """`volume-subpath` exige que le sous-chemin existe déjà.

    Sans ce mkdir, la première session d'un projet échoue au démarrage avec le
    code 127 du démon.
    """
    preparer_la_maison("p1")
    maison = get_settings().claude_home_root / "p1"
    assert (maison / "tmp").is_dir()
    preparer_la_maison("p1")  # idempotent


def test_le_superviseur_a_une_maison_et_pas_de_clone(workspaces: Path) -> None:
    (workspaces / "_supervisor").mkdir()
    env = env_pour_enrobage(
        project_id=None, worktree_abs=workspaces / "_supervisor", ssh_subpath=None
    )
    assert env["ELDIR_CLAUDE_HOME_SUBPATH"] == "_superviseur"
    assert "ELDIR_CLONE_SUBPATH" not in env


def test_avec_toolchain_et_collecte_installes_les_montages_apparaissent(
    workspaces: Path, tmp_path: Path
) -> None:
    """La branche positive : sans elle, le conditionnel n'est vu que dans un sens.

    Les marqueurs sont ceux que lisent les services (`.eldir-state.json` pour
    le toolchain, `collecte.log` pour la collecte). Un projet installé doit
    voir ses volumes, avec son sous-chemin.
    """
    (tmp_path / "toolchains" / "p1").mkdir(parents=True)
    (tmp_path / "toolchains" / "p1" / ".eldir-state.json").write_text("{}")
    (tmp_path / "collectes" / "p1").mkdir(parents=True)
    (tmp_path / "collectes" / "p1" / "collecte.log").write_text("")

    env = env_pour_enrobage(
        project_id="p1", worktree_abs=workspaces / "u1" / "eldir.s1", ssh_subpath=None
    )

    assert env["ELDIR_TOOLCHAINS_VOLUME"] == get_settings().toolchains_volume
    assert env["ELDIR_TOOLCHAIN_SUBPATH"] == "p1"
    assert env["ELDIR_TOOLCHAIN_ABS"] == str(tmp_path / "toolchains" / "p1")
    assert env["ELDIR_COLLECTES_VOLUME"] == get_settings().collectes_volume
    assert env["ELDIR_COLLECTE_SUBPATH"] == "p1"
    assert env["ELDIR_COLLECTE_ABS"] == str(tmp_path / "collectes" / "p1")


def test_la_matiere_ssh_est_montee_quand_le_projet_en_a_une(workspaces: Path) -> None:
    """La clé et le `config` à un seul bloc, nommés pour l'enrobage.

    Un renommage de cette clé ne casserait rien bruyamment : l'enrobage
    conclurait simplement qu'il n'y a pas de montage SSH, et « Connecter au
    serveur » cesserait de marcher sans que rien ne le dise.
    """
    env = env_pour_enrobage(
        project_id="p1",
        worktree_abs=workspaces / "u1" / "eldir.s1",
        ssh_subpath="p1-ssh/s1",
    )
    assert env["ELDIR_SSH_SUBPATH"] == "p1-ssh/s1"


def test_un_worktree_sans_clone_n_a_pas_de_clone(workspaces: Path) -> None:
    """Le nom finit en `.s1` mais le clone n'existe pas : pas de montage fantôme.

    Sans ce garde, `ELDIR_CLONE_SUBPATH` désignerait un dossier absent, et le
    `docker run` échouerait en code 127.
    """
    (workspaces / "u2" / "x.s1").mkdir()
    assert chemin_du_clone(workspaces / "u2" / "x.s1") is None


def test_sans_ssh_aucune_cle_ssh(workspaces: Path) -> None:
    env = env_pour_enrobage(
        project_id="p1", worktree_abs=workspaces / "u1" / "eldir.s1", ssh_subpath=None
    )
    assert "ELDIR_SSH_SUBPATH" not in env


def test_une_toolchain_sans_collecte_ne_monte_que_le_toolchain(
    workspaces: Path, tmp_path: Path
) -> None:
    """Les deux blocs conditionnels se testent séparément : un copier-coller qui
    lierait la collecte au toolchain passerait sinon.
    """
    (tmp_path / "toolchains" / "p1").mkdir(parents=True)
    (tmp_path / "toolchains" / "p1" / ".eldir-state.json").write_text("{}")

    env = env_pour_enrobage(
        project_id="p1", worktree_abs=workspaces / "u1" / "eldir.s1", ssh_subpath=None
    )

    assert env["ELDIR_TOOLCHAIN_SUBPATH"] == "p1"
    assert "ELDIR_COLLECTE_SUBPATH" not in env
    assert "ELDIR_COLLECTES_VOLUME" not in env


def test_une_collecte_sans_toolchain_ne_monte_que_la_collecte(
    workspaces: Path, tmp_path: Path
) -> None:
    """Le symétrique du précédent : la collecte seule, sans toolchain."""
    (tmp_path / "collectes" / "p1").mkdir(parents=True)
    (tmp_path / "collectes" / "p1" / "collecte.log").write_text("")

    env = env_pour_enrobage(
        project_id="p1", worktree_abs=workspaces / "u1" / "eldir.s1", ssh_subpath=None
    )

    assert env["ELDIR_COLLECTE_SUBPATH"] == "p1"
    assert "ELDIR_TOOLCHAIN_SUBPATH" not in env
    assert "ELDIR_TOOLCHAINS_VOLUME" not in env
