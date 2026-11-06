"""Ce qu'une session ne peut pas atteindre, et l'image qui la porte, vérifiés sur un vrai démon.

Les trois tests `test_une_session_ne_lit_pas_...` sont le coeur de la Phase 6 bis.
Ils vérifient ce que le démon fait de `volume-subpath`, sur des chaînes de
montage **recopiées à la main** de celles que l'enrobage construit : ils
échouent si cette sémantique change, ou si l'on modifie ces chaînes ici. Une
régression de l'enrobage lui-même, elle, est attrapée par les chaînes exactes
de `tests/unit/test_enrobage.py`, pas par ces tests. Chacun nomme dans son
docstring la ou les mutations qui doivent le faire tomber, pour que personne
n'ait à deviner ce qu'il protège.

Le critère n'est pas qu'un accès soit refusé mais qu'il soit **impossible** :
une règle qui refuse se négocie par injection de prompt, un fichier qui
n'existe pas dans l'univers de la session ne se négocie pas. Ces tests
cherchent donc le voisin dans tout le conteneur et exigent qu'il n'y soit pas,
au lieu de constater qu'une lecture échoue.

Les autres tests vérifient l'image elle-même (le CLI, l'uid, le `ssh`, l'entrée),
sauf le dernier : un démarrage de conteneur qui échoue ne retombe pas en mode
`processus`. Tous ont besoin d'un vrai démon, ce qu'un double ne prouverait pas.
Ils sautent sans démon joignable, ou avant Docker 26. Aucun ne mène une session
jusqu'au CLI. Le dernier appelle `SessionManager.start` avec une image que le
démon ne peut pas obtenir, donc le démarrage échoue avant qu'aucun CLI ne
tourne ; les autres ne lancent le CLI Claude que pour afficher sa version. Aucun
ne consomme de crédit.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from collections.abc import Iterator
from pathlib import Path
from typing import NoReturn
from unittest.mock import AsyncMock

import pytest
from app.core.config import get_settings
from app.services.event_bus import EventBus
from app.services.session_manager import SessionManager
from claude_agent_sdk import ProcessError

pytestmark = pytest.mark.docker

DOSSIER_IMAGE = Path(__file__).parents[2] / "docker" / "session"
IMAGE = "eldir-session:local"
VOLUME = "eldir-test-isolement"
MAISONS = "eldir-test-maisons"
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
    """Saute en local sans démon : c'est cette fixture qui saute, pas le marqueur `docker`.

    Échoue au lieu de sauter quand `ELDIR_EXIGE_DOCKER` est posé, comme en CI :
    un saut y serait la perte silencieuse des tests du conteneur de session,
    sous un voyant vert.

    Le seuil est 26, minimum documenté par Docker (`volume-subpath` est apparu
    avec la 26.0, API 1.45), pas une mesure : seule la 29.9.2 a été essayée. Ce
    qu'un démon plus ancien ferait d'un `Subpath` qu'il ne connaît pas est
    inconnu, et le pire cas est qu'il l'ignore et monte le volume entier. C'est
    exactement ce que les trois tests `test_une_session_ne_lit_pas_...`
    attrapent, parce qu'ils exigent l'absence du voisin et non une erreur. Mais
    ils ne protègent que le démon sur lequel ils tournent, une machine de dev ou
    le runner de la CI, pas un hôte de production, et au seuil 26 ils sautent
    justement sur les démons à risque. Pour savoir ce que fait un démon plus
    ancien, baisse ce seuil et lance ces trois tests : ils échouent s'il monte
    tout. Pour une installation passée par le script, le garde-fou est le contrôle
    de version de `scripts/install-eldir.sh` ; le backend ne vérifie pas lui-même
    la version du démon.
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
    if majeure < 26:
        _sans_demon(f"volume-subpath exige Docker 26+, vu {version!r}")


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


@pytest.fixture(scope="module")
def maisons(image: str) -> Iterator[str]:
    """Le volume des maisons tel que le backend le remplit, pour deux projets.

    La maison `.claude` de chaque projet est à la racine (`<projet>`), la
    matière SSH de chaque session à côté d'elle (`<projet>-ssh/<session>`) : le
    projet A a deux sessions, pour qu'un dossier trop large montre aussi la
    session voisine du même projet.
    """
    _docker("volume", "rm", "-f", MAISONS, attendu=None)
    _docker("volume", "create", MAISONS)
    # Monté sur `/eldir/maison` et pas sur un chemin absent de l'image : un
    # volume neuf prend le propriétaire du dossier qu'il recouvre, ici l'uid
    # 1000 de l'image. Sur un chemin inexistant sa racine serait à root, et
    # rien ne pourrait y créer les dossiers ci-dessous.
    _docker(
        "run",
        "--rm",
        "-v",
        f"{MAISONS}:/eldir/maison",
        "--entrypoint",
        "sh",
        image,
        "-c",
        """set -e
        cd /eldir/maison
        mkdir -p projet-a/.claude/projects projet-b/.claude/projects
        echo "conversation de projet-b" > projet-b/.claude/projects/t.jsonl
        mkdir -p projet-a-ssh/s1 projet-a-ssh/s2 projet-b-ssh/s9
        echo "cle de projet-a, session s1" > projet-a-ssh/s1/cle
        echo "cle de projet-a, session s2" > projet-a-ssh/s2/cle
        echo "cle de projet-b, session s9" > projet-b-ssh/s9/cle
        """,
    )
    yield MAISONS
    _docker("volume", "rm", "-f", MAISONS, attendu=None)


def _version_epinglee() -> str:
    """Le numéro que l'`ARG CLAUDE_CLI_VERSION` du Dockerfile épingle."""
    dockerfile = (DOSSIER_IMAGE / "Dockerfile").read_text(encoding="utf-8")
    trouve = re.search(r"^ARG CLAUDE_CLI_VERSION=(\S+)$", dockerfile, re.MULTILINE)
    assert trouve, "ARG CLAUDE_CLI_VERSION introuvable dans le Dockerfile"
    return trouve.group(1)


def test_l_image_porte_le_cli_claude(image: str) -> None:
    """Le binaire est là, il répond, et c'est la version que le Dockerfile épingle.

    Le SDK lance bien `claude -v` avant de démarrer, mais il en avale l'échec
    (`_check_claude_version` : `except Exception: pass`, sans le moindre log ;
    seul un contrôle réussi peut avertir, d'une version trop ancienne). Ce qui
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


def _run_session(image: str, *montages: str, commande: str) -> subprocess.CompletedProcess[str]:
    """Un conteneur de session monté comme l'enrobage le monterait.

    Les chaînes de montage ont la forme de celles que l'enrobage construit et
    que `tests/unit/test_enrobage.py` vérifie ; elles sont recopiées ici à la
    main, ce qui est le seul lien entre les deux. Sans réseau : une session
    n'a pas besoin du réseau pour lire ses fichiers.

    Le code de sortie est contrôlé (0, la valeur par défaut de `_docker`).
    C'est celui de la dernière commande de chaque test, un `sed`, donc il vaut 0
    quoi qu'ait fait un `cat` en route : un code non nul ne peut venir que de
    `docker` (montage refusé, image absente) et remonte avec son stderr, au lieu
    de se deviner à un stdout vide.
    """
    return _docker(
        "run",
        "--rm",
        "--network",
        "none",
        *[arg for montage in montages for arg in ("--mount", montage)],
        "--entrypoint",
        "sh",
        image,
        "-c",
        commande,
    )


def _chercher_partout(nom: str) -> str:
    """Le shell qui liste, partout dans le conteneur, les fichiers de ce nom.

    Lire le voisin là où l'on croit qu'il serait ne prouve rien : un chemin
    deviné de travers est introuvable avec ou sans isolement. Chercher par le
    nom, dans tout l'arbre (montages compris, hors `/proc`, `/sys` et `/dev`),
    répond à la vraie question : existe-t-il quelque part ?

    C'est `find` et pas `grep -r` : `grep -s` taira un fichier qui existe mais
    que la session n'a pas le droit de lire, et un refus passerait pour une
    absence. `find` le liste. Limite connue : un fichier dans un dossier fermé
    à la session resterait caché, ce que ces fixtures (tout est à l'uid 1000)
    ne produisent pas.

    Revers voulu : si l'image livre un jour un fichier de ce nom (le CLI et un
    `*.jsonl`, par exemple), la comparaison échoue bruyamment au lieu de passer
    à vide ; on met alors la liste attendue à jour.
    """
    return (
        "find / \\( -path /proc -o -path /sys -o -path /dev \\) -prune "
        f"-o -name '{nom}' -print | sed 's/^/trouve : /'"
    )


def _trouves(proc: subprocess.CompletedProcess[str]) -> list[str]:
    """Les chemins que `_chercher_partout` a imprimés, triés."""
    return sorted(
        ligne.removeprefix("trouve : ")
        for ligne in proc.stdout.splitlines()
        if ligne.startswith("trouve : ")
    )


def test_une_session_ne_lit_pas_le_worktree_voisin(image: str, volume: str) -> None:
    """Le test central de la Phase 6 bis.

    Mutations qui doivent le faire tomber :

    - monter la racine du volume `workspaces` (sans `volume-subpath`) au lieu du
      sous-chemin du worktree ;
    - celle qui laisse intact le travail de la session, donc qui ne peut tomber
      que sur l'assertion d'absence : garder les deux montages et monter en plus
      le volume entier ailleurs (`dst=/mnt/tout`).
    """
    proc = _run_session(
        image,
        f"type=volume,src={volume},dst={WORKSPACES}/projet-a/depot.s1,volume-subpath=projet-a/depot.s1",
        f"type=volume,src={volume},dst={WORKSPACES}/projet-a/depot,volume-subpath=projet-a/depot",
        commande=f"""
        cd {WORKSPACES}/projet-a/depot.s1
        echo "git chez moi : $(git rev-parse --abbrev-ref HEAD)"
        echo "mon secret   : $(cat secret.txt)"
        cat {WORKSPACES}/projet-b/depot.s1/secret.txt 2>&1
        {_chercher_partout("secret.txt")}
        """,
    )

    # son propre travail marche, git compris
    assert "git chez moi : claude/t" in proc.stdout
    assert "mon secret   : secret de projet-a" in proc.stdout
    # et le voisin n'existe pas, sans refus de permission à négocier
    assert "No such file or directory" in proc.stdout
    assert "secret de projet-b" not in proc.stdout
    # ni là où on l'attendait, ni nulle part ailleurs
    assert _trouves(proc) == [f"{WORKSPACES}/projet-a/depot.s1/secret.txt"]


def test_une_session_ne_lit_pas_la_cle_ssh_d_un_autre_projet(image: str, maisons: str) -> None:
    """Mutations qui doivent le faire tomber :

    - monter le volume des maisons entier, ou le dossier `projet-a-ssh` de toutes
      les sessions du projet, au lieu du seul dossier de la session ;
    - celle qui laisse intacte la clé de la session, donc qui ne peut tomber que
      sur l'assertion d'absence : garder le montage et monter en plus le volume
      entier ailleurs (`dst=/mnt/tout`).
    """
    proc = _run_session(
        image,
        f"type=volume,src={maisons},dst=/eldir/ssh,volume-subpath=projet-a-ssh/s1,readonly",
        commande=f"""
        echo "ma cle : $(cat /eldir/ssh/cle)"
        {_chercher_partout("cle")}
        """,
    )

    assert "ma cle : cle de projet-a, session s1" in proc.stdout
    # la seule clé de tout le conteneur est la sienne : ni celle de l'autre
    # projet, ni celle d'une autre session du même projet
    assert _trouves(proc) == ["/eldir/ssh/cle"]


def test_une_session_ne_lit_pas_la_maison_claude_d_un_autre_projet(
    image: str, maisons: str
) -> None:
    """Les transcripts sont des conversations entières : les partager, c'est
    partager tout ce qui a été dit dans les autres projets.

    Mutation qui doit le faire tomber : monter le volume sans `volume-subpath`.
    """
    proc = _run_session(
        image,
        f"type=volume,src={maisons},dst=/eldir/maison,volume-subpath=projet-a",
        commande=f"""
        mkdir -p /eldir/maison/.claude/projects
        echo ok > /eldir/maison/.claude/projects/moi.jsonl
        echo "j'ecris chez moi : $(cat /eldir/maison/.claude/projects/moi.jsonl)"
        {_chercher_partout("*.jsonl")}
        """,
    )

    # sa maison marche : elle y écrit son propre transcript
    assert "j'ecris chez moi : ok" in proc.stdout
    # et le seul transcript du conteneur est le sien
    assert _trouves(proc) == ["/eldir/maison/.claude/projects/moi.jsonl"]


@pytest.fixture
def uid_1000(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Un `id` qui répond 1000, pour que l'enrobage arrive jusqu'au `docker run`.

    L'enrobage refuse un backend qui n'est pas en uid 1000 (code 2) avant de
    contacter le démon, et un runner de CI n'est pas forcément en uid 1000. Sans
    ce double, le test ci-dessous échouerait là où il ne prétend pas échouer.
    """
    binaire = tmp_path / "bin"
    binaire.mkdir()
    (binaire / "id").write_text("#!/bin/sh\necho 1000\n", encoding="utf-8")
    os.chmod(binaire / "id", 0o700)
    monkeypatch.setenv("PATH", f"{binaire}:{os.environ['PATH']}")


async def test_un_echec_de_demarrage_ne_retombe_pas_en_mode_processus(
    uid_1000: None, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Le repli silencieux est exactement ce qu'un attaquant veut provoquer.

    Le conteneur ne démarre pas : on attend une erreur, et surtout **pas** une
    session vivante dans le pool, qui tournerait alors sans isolement.

    L'image vient d'un registre qui refuse la connexion (`localhost:1`), donc
    le `docker run` de l'enrobage échoue vite, sans réseau, et avant qu'aucun
    CLI ne tourne : le test ne coûte aucun crédit. `ProcessError` est l'erreur
    du SDK quand le processus du CLI meurt, et le code de sortie 125 est celui
    de `docker run` lui-même. Les deux ancrent l'échec là où le test dit qu'il
    est : un `ValueError` levé en amont n'est pas un `ProcessError`, et un
    refus de l'enrobage (uid, code 2) est un `ProcessError` sans rapport avec
    le démon.

    Mutations qui le font tomber (mesurées) : que `start` retente sans
    `cli_path` quand le `connect` échoue, ou qu'il ne pose jamais `cli_path`.
    Dans les deux cas `start` rend une session et il n'y a plus d'exception.
    Ne le fait pas tomber : que `options_de_conteneur` rende `{}` quand son
    calcul échoue. Ici le calcul réussit, l'échec vient du `docker run`. Cette
    moitié est tenue, dans `tests/unit/test_session_manager.py`, par :
    `test_une_decision_de_conteneur_qui_echoue_ne_retombe_pas_en_mode_processus`.
    """
    worktree = tmp_path / "workspaces" / "u1" / "depot.s1"
    (tmp_path / "workspaces" / "u1" / "depot").mkdir(parents=True)
    worktree.mkdir()
    monkeypatch.setenv("SESSION_RUNTIME", "conteneur")
    monkeypatch.setenv("SESSION_IMAGE", "localhost:1/eldir-session:absente")
    monkeypatch.setenv("WORKSPACES_ROOT", str(tmp_path / "workspaces"))
    monkeypatch.setenv("CLAUDE_HOME_ROOT", str(tmp_path / "maisons"))
    monkeypatch.setenv("SSH_HOME", str(tmp_path / "ssh"))
    get_settings.cache_clear()
    manager = SessionManager(EventBus(redis=AsyncMock()))
    try:
        with pytest.raises(ProcessError) as erreur:
            await manager.start(session_id="s1", project_id="p1", user_id="u1", cwd=str(worktree))

        assert erreur.value.exit_code == 125
        assert manager.active_count == 0
        assert not manager.is_active("s1")
    finally:
        # Si l'invariant tombe, `start` a rendu une session : ne pas laisser
        # son CLI tourner derrière le test rouge.
        for session in manager.list_active():
            await manager.stop(session.session_id)
        get_settings.cache_clear()
