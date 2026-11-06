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
from typing import Any

import pytest
import yaml
from app.core.config import Settings, get_settings
from app.services.session_container import (
    chemin_du_clone,
    env_pour_enrobage,
    preparer_la_maison,
)

COMPOSE_PROD = Path(__file__).parents[3] / "docker-compose.yml"
BACKEND_DOCKERFILE = Path(__file__).parents[2] / "Dockerfile"
SESSION_DOCKERFILE = Path(__file__).parents[2] / "docker" / "session" / "Dockerfile"


def _compose() -> dict[str, Any]:
    """Le compose de prod, lu par un parseur YAML.

    Les tests du compose ne lisent pas son texte : une expression régulière
    reste vraie sur un style que le fichier utilise lui-même (`networks:
    [docker-api]`, en ligne), sur `network_mode: service:docker-proxy`, sur un
    service au nom que l'expression ne prévoit pas, sur une valeur suivie d'un
    commentaire. Le parseur résout tout cela, et les commentaires n'existent
    plus pour lui. Les expressions régulières ne restent que pour le texte d'un
    Dockerfile, qui n'a pas de parseur.
    """
    return dict(yaml.safe_load(COMPOSE_PROD.read_text(encoding="utf-8")))


def _services() -> dict[str, dict[str, Any]]:
    return dict(_compose()["services"])


def _environnement(service: dict[str, Any]) -> dict[str, str]:
    """L'environnement d'un service, en table (`CLE: v`) ou en liste (`- CLE=v`)."""
    brut = service.get("environment") or {}
    if isinstance(brut, list):
        brut = dict(ligne.partition("=")[::2] for ligne in brut)
    return {cle: str(valeur) for cle, valeur in brut.items()}


def _reseaux(service: dict[str, Any]) -> set[str]:
    """Les réseaux d'un service, en liste ou en table. Sans `networks`, le défaut."""
    brut = service.get("networks")
    return set(brut) if brut else {"default"}


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
    suppression silencieuse. Elle est lue dans le service du backend : une ligne
    commentée, ou posée dans un autre service, ne compte pas.
    """
    assert _environnement(_services()["backend"]).get("SESSION_RUNTIME") == "conteneur"


def test_les_noms_de_volumes_portent_le_prefixe_du_projet_compose() -> None:
    """Compose préfixe le nom d'un volume par celui du projet.

    Le compose de prod déclare `name: eldir` et un volume `eldir_workspaces` :
    le démon, lui, ne connaît que `eldir_eldir_workspaces`. Un `docker run`
    sur le nom non préfixé créerait un volume vide tout neuf, et la session
    démarrerait sur un worktree inexistant.
    """
    reglages = Settings(_env_file=None)
    compose = _compose()
    assert compose["name"] == "eldir"
    for nom in (
        reglages.workspaces_volume,
        reglages.toolchains_volume,
        reglages.claude_home_volume,
        reglages.collectes_volume,
    ):
        assert nom.startswith("eldir_eldir_"), nom
        # Le volume existe bien sous son nom court dans le compose.
        assert nom.removeprefix("eldir_") in compose["volumes"], nom


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

    Non couvert : `database_url`, `redis_url` et `turn_webhook_url` ne sont pas
    typés secret. Un mot de passe dans une DSN, ou le jeton que peut porter l'URL
    du ping de fin de tour (cf. `config.py`), échappe aux deux volets, faute de
    champ à lister.
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


def test_le_proxy_de_socket_n_autorise_que_ce_qu_il_faut() -> None:
    """L'ensemble des variables du proxy est épinglé, pas une liste d'interdits.

    Une liste de noms interdits laisserait passer `BUILD`, `PLUGINS`, `SYSTEM` et
    tous ceux auxquels on n'a pas pensé. Ajouter une permission au proxy est une
    ligne, et la ligne ne dit pas ce qu'elle ouvre : ce test oblige à le décider
    en relisant le commentaire du compose, qui nomme ce que chacune ouvre.

    Le socket du démon n'est monté nulle part ailleurs que dans le proxy, et le
    proxy ne publie aucun port : il n'a pas d'authentification, et seul le
    backend le joint (cf. le test des réseaux). Aucun autre service ne cite
    `docker.sock`, ni en montage, ni en variable, ni en commande. Le proxy n'a pas
    d'`env_file` : il cacherait des variables à l'assertion sur l'environnement.
    """
    services = _services()
    proxy = services["docker-proxy"]

    assert "env_file" not in proxy
    assert _environnement(proxy) == {"CONTAINERS": "1", "POST": "1", "IMAGES": "1"}
    assert proxy["volumes"] == ["/var/run/docker.sock:/var/run/docker.sock:ro"]
    assert "ports" not in proxy
    citent_le_socket = [nom for nom, s in services.items() if "docker.sock" in yaml.safe_dump(s)]
    assert citent_le_socket == ["docker-proxy"]


def test_seul_le_backend_joint_le_proxy_de_socket() -> None:
    """Créer un conteneur par le proxy équivaut à être root : qui le joint est la garde.

    Le proxy n'a pas d'authentification, et le compose ne peut pas lui en donner.
    Sur le réseau par défaut, Caddy, le frontend, Postgres et Redis le joindraient
    tous : un seul compromis suffirait. Le proxy vit donc sur un réseau à part, et
    le backend est le seul autre service à le rejoindre. Le backend garde le réseau
    par défaut, sans quoi il ne joindrait plus Postgres ni Redis.

    Un service sans `networks` est sur le réseau par défaut. Aucun service ne pose
    `network_mode` : `service:docker-proxy` ou `host` contourneraient les réseaux.

    Le test lit le fichier, pas le modèle que compose en tire (qui exigerait un
    démon Docker, absent de la machine où tourne la suite). Trois écritures lui
    échapperaient donc, et sont fermées une à une : un second réseau qui porte
    `name: eldir_docker-api`, un `default` renommé, `extends` ou `include` qui
    importent la configuration d'un autre fichier.
    """
    compose = _compose()
    services = _services()

    assert compose["networks"] == {"docker-api": None}
    assert "include" not in compose
    assert all("extends" not in service for service in services.values())
    assert _reseaux(services["docker-proxy"]) == {"docker-api"}
    assert _reseaux(services["backend"]) == {"default", "docker-api"}
    autres = {nom: s for nom, s in services.items() if nom not in ("docker-proxy", "backend")}
    assert [nom for nom, s in autres.items() if "docker-api" in _reseaux(s)] == []
    assert [nom for nom, s in services.items() if "network_mode" in s] == []


def test_le_backend_parle_au_proxy_et_pas_au_socket() -> None:
    """Le backend joint le proxy par `DOCKER_HOST`, avec les noms que le démon connaît.

    Tout est lu dans le service du backend : une ligne commentée, ou posée dans un
    autre service, ne compte pas. La collecte est un volume parce que le démon ne
    peut monter dans une session que ce qu'il voit lui-même.
    """
    backend = _services()["backend"]
    environnement = _environnement(backend)
    reglages = Settings(_env_file=None)

    assert environnement.get("DOCKER_HOST") == "tcp://docker-proxy:2375"
    assert environnement.get("WORKSPACES_VOLUME") == reglages.workspaces_volume
    assert environnement.get("TOOLCHAINS_VOLUME") == reglages.toolchains_volume
    assert environnement.get("CLAUDE_HOME_VOLUME") == reglages.claude_home_volume
    assert environnement.get("COLLECTES_VOLUME") == reglages.collectes_volume
    assert f"eldir_collectes:{reglages.collectes_root}" in backend["volumes"]
    assert backend["depends_on"]["docker-proxy"] == {"condition": "service_started"}


def test_les_variables_de_build_ne_fuient_dans_aucune_image() -> None:
    """`CI` et les `npm_config_*` servent au build, ils ne doivent pas rester.

    Posées en `ENV`, elles seraient dans l'environnement de tout ce que l'image
    lance. `CI=true` change le comportement des outils que l'agent exécute : une
    session du mode `processus` (dans l'image du backend) le verrait, une session
    du mode `conteneur` (dans l'image des sessions) non. Les deux Dockerfiles les
    déclarent donc en `ARG`, et ce test les garde alignés.
    """
    for dockerfile in (BACKEND_DOCKERFILE, SESSION_DOCKERFILE):
        texte = dockerfile.read_text(encoding="utf-8")
        for nom in (
            "CI",
            "npm_config_fund",
            "npm_config_audit",
            "npm_config_update_notifier",
            "npm_config_progress",
        ):
            assert re.search(rf"^ARG {nom}=", texte, re.MULTILINE), f"{dockerfile}: ARG {nom}"
            assert not re.search(rf"^ENV {nom}\b", texte, re.MULTILINE), f"{dockerfile}: ENV {nom}"
