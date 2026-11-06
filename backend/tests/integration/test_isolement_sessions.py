"""L'image des sessions, vérifiée sur un vrai démon Docker.

Ces tests ont besoin d'un vrai démon : ils vérifient l'image elle-même (le CLI,
l'uid, le `ssh`, l'entrée), ce qu'un double ne prouverait pas. Ils sautent sans
démon joignable, ou avant Docker 25. Aucun ne démarre de session : le CLI Claude
n'est lancé que pour afficher sa version, donc ils ne consomment aucun crédit.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from collections.abc import Iterator
from pathlib import Path
from typing import NoReturn

import pytest

pytestmark = pytest.mark.docker

DOSSIER_IMAGE = Path(__file__).parents[2] / "docker" / "session"
IMAGE = "eldir-session:local"
VOLUME = "eldir-test-isolement"
WORKSPACES = "/var/eldir/workspaces"
# Un démon qui accepte la connexion sans répondre ne doit pas figer le fichier.
DELAI_SONDE_S = 30
# Posée (non vide), elle change chaque saut de `demon_docker` en échec.
EXIGE_DOCKER = "ELDIR_EXIGE_DOCKER"


def _docker(*args: str, attendu: int | None = 0) -> subprocess.CompletedProcess[str]:
    proc = subprocess.run(
        ["docker", *args], capture_output=True, text=True, check=False, timeout=300
    )
    if attendu is not None:
        assert proc.returncode == attendu, f"{args}\n{proc.stdout}\n{proc.stderr}"
    return proc


def _sans_demon(raison: str) -> NoReturn:
    if os.environ.get(EXIGE_DOCKER):
        pytest.fail(f"{raison} ({EXIGE_DOCKER} est posé)", pytrace=False)
    pytest.skip(raison)


@pytest.fixture(scope="module", autouse=True)
def demon_docker() -> None:
    """Saute en local sans démon, ce qui est le rôle du marqueur `docker`.

    Échoue au lieu de sauter quand `ELDIR_EXIGE_DOCKER` est posé, comme en CI :
    un saut y serait la perte silencieuse des tests du conteneur de session,
    sous un voyant vert.
    """
    if shutil.which("docker") is None:
        _sans_demon("docker absent")
    try:
        info = subprocess.run(
            ["docker", "info"], capture_output=True, check=False, timeout=DELAI_SONDE_S
        )
        version = subprocess.run(
            ["docker", "version", "--format", "{{.Server.Version}}"],
            capture_output=True,
            text=True,
            check=False,
            timeout=DELAI_SONDE_S,
        ).stdout.strip()
    except subprocess.TimeoutExpired:
        _sans_demon("démon docker sans réponse")
    if info.returncode:
        _sans_demon("démon docker injoignable")
    majeure = int(version.split(".")[0]) if version[:1].isdigit() else 0
    if majeure < 25:
        _sans_demon(f"volume-subpath exige Docker 25+, vu {version!r}")


@pytest.fixture(scope="module")
def image() -> str:
    _docker("build", "-t", IMAGE, str(DOSSIER_IMAGE))
    return IMAGE


@pytest.fixture(scope="module")
def volume(image: str) -> Iterator[str]:
    """Deux projets voisins dans un volume : chacun un clone et un worktree."""
    # Le reste d'un run interrompu ferait échouer le `git commit` de la boucle
    # ci-dessous (rien à valider).
    _docker("volume", "rm", "-f", VOLUME, attendu=None)
    _docker("volume", "create", VOLUME)
    # Ce chemin n'existe pas dans l'image : Docker crée la racine du volume en
    # root, et l'uid 1000 n'y pourrait rien créer.
    _docker(
        "run",
        "--rm",
        "--user",
        "root",
        "-v",
        f"{VOLUME}:{WORKSPACES}",
        "--entrypoint",
        "chown",
        image,
        "1000:1000",
        WORKSPACES,
    )
    _docker(
        "run",
        "--rm",
        "-v",
        f"{VOLUME}:{WORKSPACES}",
        "--entrypoint",
        "sh",
        image,
        "-c",
        f"""set -e
        for p in projet-a projet-b; do
          mkdir -p {WORKSPACES}/$p
          cd {WORKSPACES}/$p
          git init -q depot && cd depot
          git config user.email eldir@exemple.lan && git config user.name eldir
          echo "code de $p" > fichier.txt
          git add -A && git commit -qm premier
          git worktree add -q -b claude/t {WORKSPACES}/$p/depot.s1
          echo "secret de $p" > {WORKSPACES}/$p/depot.s1/secret.txt
        done
        """,
    )
    yield VOLUME
    _docker("volume", "rm", "-f", VOLUME, attendu=None)


def _version_epinglee() -> str:
    """Le numéro que l'`ARG CLAUDE_CLI_VERSION` du Dockerfile épingle."""
    dockerfile = (DOSSIER_IMAGE / "Dockerfile").read_text(encoding="utf-8")
    trouve = re.search(r"^ARG CLAUDE_CLI_VERSION=(\S+)$", dockerfile, re.MULTILINE)
    assert trouve, "ARG CLAUDE_CLI_VERSION introuvable dans le Dockerfile"
    return trouve.group(1)


def test_l_image_porte_le_cli_claude(image: str) -> None:
    """Le binaire est là, il répond, et c'est la version que le Dockerfile épingle.

    Le SDK lance bien `claude -v` avant de démarrer, mais il en avale l'échec
    (`_check_claude_version` : `except Exception: pass`), au pire un log. Ce qui
    arrête une session, c'est un `claude` introuvable ou qui ne démarre pas : en
    mode `conteneur`, le `docker run` de l'enrobage échoue (en mode `processus`,
    c'est `_find_cli`). Ce test attrape le cas de l'image. Un `latest`, ou une
    installation qui ignore l'`ARG`, rendrait la version du jour et échouerait
    ici.
    """
    proc = _docker("run", "--rm", "--entrypoint", "claude", image, "-v")
    assert proc.stdout.split()[0] == _version_epinglee()


def test_l_image_tourne_en_uid_1000(image: str) -> None:
    """Le CLI refuse `bypassPermissions` en root, et `ssh` refuse un `config` d'un
    autre propriétaire que l'uid du conteneur, qui est celui du backend (1000)."""
    proc = _docker("run", "--rm", "--entrypoint", "id", image, "-u")
    assert proc.stdout.strip() == "1000"


def test_ssh_lit_le_config_monte(image: str) -> None:
    """Le `config` d'une session n'est ni `~/.ssh/config` ni un chemin système.

    Sans le `Include` de l'image, `ssh` ne trouverait pas l'alias, et « Connecter
    au serveur » échouerait (nom d'hôte inconnu).

    Le `config` vit dans un volume et non dans un `tmp_path` : `ssh` refuse un
    fichier qui n'est ni à son uid ni à root (« Bad owner or permissions »), et
    le `tmp_path` d'un poste dont l'uid n'est pas 1000 serait refusé (mesuré
    avec un propriétaire d'uid 1001). Un volume neuf prend le propriétaire du
    dossier de l'image, donc l'uid 1000.
    """
    nom = "eldir-test-ssh"
    _docker("volume", "rm", "-f", nom, attendu=None)
    _docker("volume", "create", nom)
    try:
        _docker(
            "run",
            "--rm",
            "-v",
            f"{nom}:/eldir/ssh",
            "--entrypoint",
            "sh",
            image,
            "-c",
            "printf 'Host eldir-essai\\n"
            "    HostName machine.exemple.lan\\n"
            "    IdentityFile /eldir/ssh/cle\\n' > /eldir/ssh/config",
        )
        proc = _docker(
            "run",
            "--rm",
            "--mount",
            f"type=volume,src={nom},dst=/eldir/ssh,readonly",
            "--entrypoint",
            "ssh",
            image,
            "-G",
            "eldir-essai",
        )
    finally:
        _docker("volume", "rm", "-f", nom, attendu=None)
    assert "hostname machine.exemple.lan" in proc.stdout
    assert "identityfile /eldir/ssh/cle" in proc.stdout


def test_ssh_demarre_sans_config_monte(image: str) -> None:
    """Un projet sans accès distant n'a aucun montage SSH.

    `/eldir/ssh/config` n'existe pas, et `ssh` doit démarrer quand même. C'est
    le cas que le motif `config*` de l'`Include` rend sûr par construction : la
    config système de Debian fait la même chose avec `ssh_config.d/*.conf`, vide
    dans cette image. Ce test ne distingue pas le motif d'un chemin littéral
    (celui de bookworm ignore aussi un chemin littéral absent, et rien
    n'épingle OpenSSH) : il tombe si une version d'OpenSSH rendait l'absence
    d'un fichier inclus fatale.
    """
    proc = _docker("run", "--rm", "--entrypoint", "ssh", image, "-G", "une-machine")
    assert "hostname une-machine" in proc.stdout


def test_l_entree_pose_le_path_du_toolchain(image: str) -> None:
    """Le seul endroit qui met le toolchain du projet sur le PATH.

    S'il cesse de le faire, l'agent ne trouve plus les outils installés et le
    signale comme une absence d'outil, un symptôme très loin de sa cause.

    Pas de `--entrypoint` ici : c'est l'entrée de l'image qu'on fait tourner. Le
    PATH de référence est lu en la contournant, pour comparer à l'égalité et
    non à un préfixe : une entrée qui ajouterait un dossier sans toolchain, ou
    le mettrait à la fin, serait vue.
    """
    echo = ("sh", "-c", "echo $PATH")
    base = _docker("run", "--rm", "--entrypoint", "sh", image, "-c", "echo $PATH")
    sans = _docker("run", "--rm", image, *echo)
    vide = _docker("run", "--rm", "-e", "ELDIR_TOOLCHAIN=", image, *echo)
    avec = _docker("run", "--rm", "-e", "ELDIR_TOOLCHAIN=/var/eldir/toolchains/p1", image, *echo)
    assert sans.stdout == base.stdout
    assert vide.stdout == base.stdout
    assert avec.stdout == f"/var/eldir/toolchains/p1/bin:{base.stdout}"


def test_l_entree_cede_la_place_a_la_commande(image: str) -> None:
    """`exec "$@"` et pas un appel : la commande remplace le shell de l'entrée.

    Sans `--init`, elle est alors le PID 1 du conteneur, et c'est elle qui reçoit
    les signaux, pas un shell intermédiaire. `--init=false` est explicite pour ne
    pas dépendre du réglage `init` du démon.

    L'enrobage des sessions (plan, tâche 8) lance en revanche `docker run
    --init` : en production, la commande est l'enfant de tini et non le PID 1.
    Ce test tourne volontairement sans, ce qui donne une valeur simple à vérifier.

    Le code de sortie attendu (42) ne garde PAS l'`exec` : un script `sh` sort
    avec le statut de sa dernière commande, `exec` ou non (mesuré sur la
    mutation). Seul le PID le voit.
    """
    proc = _docker("run", "--rm", "--init=false", image, "sh", "-c", "echo $$; exit 42", attendu=42)
    assert proc.stdout.strip() == "1"


def test_les_dossiers_de_l_image_sont_a_l_uid_1000(image: str) -> None:
    """`/eldir/maison` est le home de la session : le CLI y écrit son transcript,
    `ssh` son `known_hosts`. Un volume neuf monté sur ces dossiers en hérite le
    propriétaire (c'est ce qui rend `/eldir/ssh` inscriptible dans le test du
    `config`), et un dossier laissé à root ne serait inscriptible par aucun uid
    qui fait tourner le CLI.
    """
    proc = _docker(
        "run",
        "--rm",
        "--entrypoint",
        "sh",
        image,
        "-c",
        "touch /eldir/maison/essai && stat -c %u /eldir /eldir/maison /eldir/ssh",
    )
    assert proc.stdout.split() == ["1000", "1000", "1000"]


def test_l_image_ne_garde_pas_les_variables_de_build(image: str) -> None:
    """Les `ARG` du Dockerfile (`CI`, `DEBIAN_FRONTEND`, les réglages de `npm`)
    ne servent qu'au build. En `ENV` ils resteraient dans l'environnement de
    chaque session.

    Insensible à la casse : `npm` lit `npm_config_*` comme `NPM_CONFIG_*`.
    """
    proc = _docker("run", "--rm", "--entrypoint", "env", image)
    noms = {ligne.split("=")[0].lower() for ligne in proc.stdout.splitlines()}
    assert not noms & {"ci", "debian_frontend"}
    assert not [nom for nom in noms if nom.startswith("npm_config_")]
