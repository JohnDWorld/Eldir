"""La ligne de commande que l'enrobage construit.

C'est la commande qui est la décision : ce qui n'y figure pas n'existe pas
dans le conteneur. On la lit avec un faux `docker` qui imprime ses arguments,
donc sans démon, en quelques millisecondes.

Le faux `docker` a un compagnon, un faux `id` : l'enrobage passe `-u` avec
l'uid de celui qui le lance et refuse tout uid autre que 1000. Sans ce double,
ces tests réussiraient sur un poste en uid 1000 et échoueraient sur tout poste
ou runner d'un autre uid.
"""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

import pytest
from app.core.config import get_settings
from app.services.session_container import env_pour_enrobage

ENROBAGE = Path(__file__).parents[2] / "docker" / "session" / "claude-dans-un-conteneur"

BASE = {
    "ELDIR_IMAGE": "eldir-session:local",
    "ELDIR_NETWORK": "eldir-sessions",
    "ELDIR_WORKSPACES_VOLUME": "vol_ws",
    "ELDIR_WORKTREE_ABS": "/var/eldir/workspaces/u1/depot.s1",
    "ELDIR_WORKTREE_SUBPATH": "u1/depot.s1",
    "ELDIR_CLAUDE_HOME_VOLUME": "vol_maisons",
    "ELDIR_CLAUDE_HOME_SUBPATH": "p1",
}

# Tout ce qu'un projet complet ajoute : le clone, le toolchain, la collecte et
# la matière SSH. Chaque groupe est un montage optionnel de l'enrobage.
OPTIONNELLES = {
    "ELDIR_CLONE_ABS": "/var/eldir/workspaces/u1/depot",
    "ELDIR_CLONE_SUBPATH": "u1/depot",
    "ELDIR_TOOLCHAINS_VOLUME": "vol_tc",
    "ELDIR_TOOLCHAIN_ABS": "/var/eldir/toolchains/p1",
    "ELDIR_TOOLCHAIN_SUBPATH": "p1",
    "ELDIR_COLLECTES_VOLUME": "vol_co",
    "ELDIR_COLLECTE_ABS": "/var/eldir/collectes/p1",
    "ELDIR_COLLECTE_SUBPATH": "p1",
    "ELDIR_SSH_SUBPATH": "p1-ssh/s1",
}


@pytest.fixture
def faux_docker(tmp_path: Path) -> Path:
    """Un dossier de PATH avec un `docker` qui imprime ses arguments, un par ligne,
    et un `id` qui répond 1000 (ou `UID_FAUX`) pour `-u` et 2000 pour `-g`.

    Le gid diffère exprès de l'uid : un `-u` qui coderait `1000:1000` en dur
    se verrait.
    """
    binaire = tmp_path / "bin"
    binaire.mkdir()
    (binaire / "docker").write_text('#!/bin/sh\nprintf "%s\\n" "$@"\n', encoding="utf-8")
    (binaire / "id").write_text(
        '#!/bin/sh\ncase "$1" in -u) echo "${UID_FAUX:-1000}" ;; -g) echo 2000 ;; esac\n',
        encoding="utf-8",
    )
    os.chmod(binaire / "docker", 0o700)
    os.chmod(binaire / "id", 0o700)
    return binaire


def _executer(
    faux_docker: Path, variables: dict[str, str], *args: str, cwd: Path = Path("/")
) -> subprocess.CompletedProcess[str]:
    """Lance l'enrobage comme le SDK le fait : dans le cwd du worktree.

    `sh` pose `PWD` lui-même quand celui qu'on lui passe ne correspond pas à
    son cwd, d'où les deux réglés ensemble sur la même valeur.
    """
    env = {"PATH": f"{faux_docker}:{os.environ['PATH']}", "PWD": str(cwd), **variables}
    return subprocess.run(
        ["sh", str(ENROBAGE), *args],
        capture_output=True,
        text=True,
        check=False,
        env=env,
        cwd=cwd,
        timeout=30,
    )


def lancer(
    faux_docker: Path, variables: dict[str, str], *args: str, cwd: Path = Path("/")
) -> list[str]:
    """Les arguments que l'enrobage passe à `docker`, un par élément."""
    proc = _executer(faux_docker, variables, *args, cwd=cwd)
    assert proc.returncode == 0, proc.stderr
    return proc.stdout.splitlines()


def _montages(sortie: list[str]) -> list[str]:
    """Les valeurs de chaque `--mount`, qu'il vienne des montages fixes ou des
    optionnels (ceux-ci passent par un découpage de mots)."""
    return [sortie[i + 1] for i, arg in enumerate(sortie) if arg == "--mount"]


def test_les_montages_de_base_sont_la(faux_docker: Path, tmp_path: Path) -> None:
    sortie = lancer(faux_docker, BASE, "--version", cwd=tmp_path)

    assert "run" in sortie
    assert "-i" in sortie and "--rm" in sortie and "--init" in sortie
    assert "eldir-sessions" in sortie
    assert (
        "type=volume,src=vol_ws,dst=/var/eldir/workspaces/u1/depot.s1,volume-subpath=u1/depot.s1"
        in sortie
    )
    assert "type=volume,src=vol_maisons,dst=/eldir/maison,volume-subpath=p1" in sortie
    # le cwd que le SDK a posé devient celui du conteneur. Comparé à la place
    # exacte de la valeur : le chemin figure déjà dans les arguments de montage,
    # donc sa seule présence ne prouverait rien. Le cwd diffère ici du
    # `dst` du worktree, pour qu'une valeur lue ailleurs que dans `$PWD` se voie.
    assert sortie[sortie.index("-w") + 1] == str(tmp_path)
    # l'uid et le gid de celui qui lance, tels que `id` les rend
    assert sortie[sortie.index("-u") + 1] == "1000:2000"
    # les arguments du CLI passent tels quels, après le nom de l'image
    assert sortie[-1] == "--version"
    assert sortie[-2] == "claude"
    assert sortie[-3] == "eldir-session:local"


def test_ce_qui_est_en_lecture_seule_l_est(faux_docker: Path) -> None:
    """Le toolchain, la collecte et la matière SSH : la session les lit."""
    sortie = lancer(
        faux_docker,
        {
            **BASE,
            "ELDIR_TOOLCHAINS_VOLUME": "vol_tc",
            "ELDIR_TOOLCHAIN_ABS": "/var/eldir/toolchains/p1",
            "ELDIR_TOOLCHAIN_SUBPATH": "p1",
            "ELDIR_COLLECTES_VOLUME": "vol_co",
            "ELDIR_COLLECTE_ABS": "/var/eldir/collectes/p1",
            "ELDIR_COLLECTE_SUBPATH": "p1",
            "ELDIR_SSH_SUBPATH": "p1-ssh/s1",
        },
    )

    assert (
        "type=volume,src=vol_tc,dst=/var/eldir/toolchains/p1,volume-subpath=p1,readonly" in sortie
    )
    assert "type=volume,src=vol_co,dst=/var/eldir/collectes/p1,volume-subpath=p1,readonly" in sortie
    assert "type=volume,src=vol_maisons,dst=/eldir/ssh,volume-subpath=p1-ssh/s1,readonly" in sortie


def test_le_clone_canonique_est_monte_en_ecriture(faux_docker: Path) -> None:
    """`git commit` depuis un worktree écrit ses objets dans le dépôt partagé."""
    sortie = lancer(
        faux_docker,
        {
            **BASE,
            "ELDIR_CLONE_ABS": "/var/eldir/workspaces/u1/depot",
            "ELDIR_CLONE_SUBPATH": "u1/depot",
        },
    )

    # La chaîne entière, comme pour les autres montages : un `src=` faux
    # monterait un autre volume sans qu'aucun autre test ne le voie. Sans
    # `readonly`, c'est ce que dit « en écriture ».
    clone = "type=volume,src=vol_ws,dst=/var/eldir/workspaces/u1/depot,volume-subpath=u1/depot"
    assert clone in sortie


def test_ce_que_git_lit_comme_des_ordres_est_en_lecture_seule(faux_docker: Path) -> None:
    """Risque nº 3 : le backend lance git dans ce clone.

    `.git` monté à part ne se renomme pas ; sa config, ses hooks et le dossier
    des sous-modules sont en lecture seule.
    """
    sortie = lancer(
        faux_docker,
        {
            **BASE,
            "ELDIR_CLONE_ABS": "/var/eldir/workspaces/u1/depot",
            "ELDIR_CLONE_SUBPATH": "u1/depot",
        },
    )

    base = "type=volume,src=vol_ws,dst=/var/eldir/workspaces/u1/depot/.git"
    assert f"{base},volume-subpath=u1/depot/.git" in sortie
    assert f"{base},volume-subpath=u1/depot/.git,readonly" not in sortie
    for nom in ("config", "hooks", "modules"):
        assert (
            f"type=volume,src=vol_ws,dst=/var/eldir/workspaces/u1/depot/.git/{nom},"
            f"volume-subpath=u1/depot/.git/{nom},readonly"
        ) in sortie


def test_sans_clone_aucun_montage_de_git(faux_docker: Path) -> None:
    sortie = lancer(faux_docker, BASE)

    assert "/.git" not in sortie


def test_ce_qui_n_est_pas_nomme_n_est_pas_monte(faux_docker: Path) -> None:
    """Un sous-chemin absent ferait échouer `docker run` en code 127.

    Un projet sans toolchain, sans collecte et sans accès distant ne porte
    aucun de ces trois montages.
    """
    sortie = lancer(faux_docker, BASE)

    # Exactement les deux montages fixes. Chercher un nom de volume dans la
    # sortie ne verrait rien d'un montage dont les variables sont vides : il
    # s'écrirait `src=,dst=,volume-subpath=` sans aucun de ces mots.
    assert _montages(sortie) == [
        "type=volume,src=vol_ws,dst=/var/eldir/workspaces/u1/depot.s1,volume-subpath=u1/depot.s1",
        "type=volume,src=vol_maisons,dst=/eldir/maison,volume-subpath=p1",
    ]


def test_la_maison_et_le_temporaire_sont_poses(faux_docker: Path) -> None:
    """`CLAUDE_CODE_TMPDIR` est explicite, et ce n'est pas un détail.

    Le CLI se calcule sinon un temporaire `/tmp/claude-<uid>` et refuse de
    démarrer s'il le trouve possédé par un autre utilisateur : « Temp
    directory /tmp/claude-1000 is owned by uid 0, expected 1000. Refusing to
    use it ». Docker crée les parents de montage en root, donc un montage dont
    le chemin passe par `/tmp` suffit à déclencher ça.
    """
    sortie = lancer(faux_docker, BASE)

    assert "HOME=/eldir/maison" in sortie
    assert "CLAUDE_CODE_TMPDIR=/eldir/maison/tmp" in sortie


def test_seules_les_variables_nommees_sont_transmises(faux_docker: Path) -> None:
    """La liste exacte des `-e` : ce qui entre dans le conteneur est ce qu'on y nomme.

    `HOME` et `CLAUDE_CODE_TMPDIR` ont aussi leur test. Les six transmis
    (`ANTHROPIC_API_KEY`, `CLAUDE_CODE_OAUTH_TOKEN`, `CLAUDE_CODE_ENTRYPOINT`,
    `ELDIR_TOOLCHAIN`, `ELDIR_COLLECTE`, `ELDIR_REMOTE_HOST`) n'en ont aucun
    autre : mesuré, en retirer un à la fois ne fait échouer que celui-ci. Un
    credential perdu se verrait quand même, la session échouant à
    l'authentification ; `ELDIR_REMOTE_HOST` ou `ELDIR_COLLECTE` perdus feraient
    disparaître « Connecter au serveur » ou la collecte sans autre signe. Un
    `-e` ajouté passerait aussi : le test des secrets ne cherche que
    `DATABASE_URL` et `JWT_SECRET`.
    """
    sortie = lancer(faux_docker, BASE)

    transmises = [sortie[i + 1] for i, arg in enumerate(sortie) if arg == "-e"]
    assert sorted(transmises) == sorted(
        [
            "HOME=/eldir/maison",
            "CLAUDE_CODE_TMPDIR=/eldir/maison/tmp",
            "ANTHROPIC_API_KEY",
            "CLAUDE_CODE_OAUTH_TOKEN",
            "CLAUDE_CODE_ENTRYPOINT",
            "ELDIR_TOOLCHAIN",
            "ELDIR_COLLECTE",
            "ELDIR_REMOTE_HOST",
        ]
    )


def test_l_enrobage_est_executable() -> None:
    """Les autres tests lancent `sh <fichier>`, mais le SDK exécute `cli_path`
    directement : sans le bit exécutable, une session ne démarrerait pas, et
    rien ici ne le dirait."""
    assert os.access(ENROBAGE, os.X_OK)


def test_aucun_secret_du_backend_ne_passe(faux_docker: Path) -> None:
    """Le filet devient un choix : on nomme ce qui entre, pas ce qu'on retire.

    `env_a_masquer_pour_cli` est une liste de refus dérivée de `Settings` :
    correcte, mais elle protège ce qu'Eldir connaît. Ici `DATABASE_URL` et
    `JWT_SECRET` n'existent pas dans le conteneur, qu'Eldir y ait pensé ou non.
    """
    sortie = lancer(
        faux_docker,
        {**BASE, "DATABASE_URL": "postgres://x", "JWT_SECRET": "s3cr3t"},
    )

    rendu = "\n".join(sortie)
    assert "DATABASE_URL" not in rendu
    assert "JWT_SECRET" not in rendu
    assert "s3cr3t" not in rendu


def test_une_variable_obligatoire_absente_fait_echouer_tot(faux_docker: Path) -> None:
    """Mieux vaut un refus nommé qu'un `docker run` sur un montage vide."""
    partiel = {c: v for c, v in BASE.items() if c != "ELDIR_WORKTREE_SUBPATH"}
    proc = _executer(faux_docker, partiel, "-v")

    assert proc.returncode != 0
    assert "ELDIR_WORKTREE_SUBPATH" in proc.stderr
    assert proc.stdout == ""


# Les variables que l'enrobage lit dans des montages développés sans guillemets :
# les neuf optionnelles, et les deux noms de volume qui les alimentent.
SANS_GUILLEMETS = [*OPTIONNELLES, "ELDIR_WORKSPACES_VOLUME", "ELDIR_CLAUDE_HOME_VOLUME"]


@pytest.mark.parametrize("variable", SANS_GUILLEMETS)
def test_un_blanc_dans_un_montage_optionnel_est_refuse(faux_docker: Path, variable: str) -> None:
    """`sh` n'a pas de tableaux : les montages optionnels s'accumulent dans une
    chaîne développée sans guillemets, donc découpée aux blancs.

    Une valeur qui en contient couperait un montage en deux, et le morceau
    suivant serait lu par `docker` comme un autre argument (jusqu'au nom de
    l'image). Les `*_ABS` viennent de `WORKSPACES_ROOT`, `TOOLCHAINS_ROOT` et
    `COLLECTES_ROOT`, que l'opérateur règle : le cas est atteignable par un
    choix de déploiement. Chaque variable est essayée seule, avec tous les
    montages présents, pour que le refus nomme la bonne.
    """
    complet = {**BASE, **OPTIONNELLES}
    # sans blanc, cette configuration passe : le refus vient bien du blanc
    lancer(faux_docker, complet)

    proc = _executer(faux_docker, {**complet, variable: "mon dossier"}, "-v")

    assert proc.returncode != 0
    assert variable in proc.stderr
    assert proc.stdout == ""


def test_la_garde_couvre_toutes_les_variables_des_montages_optionnels() -> None:
    """La liste du garde-fou des blancs suit les montages écrits `montages="$montages ..."`.

    Elle nomme les variables que les montages optionnels développent sans
    guillemets. Un montage ajouté un jour avec une variable de plus, sans
    l'ajouter à cette liste, repasserait sur le défaut que la garde existe pour
    fermer, et aucun test paramétré ne le verrait (il ne connaît que les noms
    qu'on lui a donnés). On lit donc le script : chaque `$ELDIR_*` des lignes
    `montages="$montages ..."` doit être dans la liste du `for nom in`.

    Limite : un montage ajouté par un autre accumulateur que `montages` serait
    invisible à ce test.
    """
    texte = ENROBAGE.read_text(encoding="utf-8")
    lignes = re.findall(r'^\s*montages="\$montages .*$', texte, re.MULTILINE)
    developpees = set(re.findall(r"\$\{?(ELDIR_[A-Z_]+)", "\n".join(lignes)))
    garde = re.search(r"^for nom in (.*?); do$", texte, re.MULTILINE | re.DOTALL)

    # Un script réécrit autrement ferait tout trouver vide : mieux vaut échouer.
    assert lignes, "aucun montage optionnel trouvé : le script a changé de forme"
    assert garde is not None, "boucle `for nom in ...; do` introuvable"
    # Sans variable développée, l'inclusion ci-dessous serait vraie à vide.
    assert developpees, "aucune variable ELDIR_ dans les montages optionnels"
    gardees = set(re.findall(r"ELDIR_[A-Z_]+", garde.group(1)))
    assert developpees <= gardees, f"développées sans garde : {sorted(developpees - gardees)}"


@pytest.mark.parametrize("blanc", ["\t", "\n"])
def test_une_tabulation_ou_un_retour_a_la_ligne_coupent_aussi(
    faux_docker: Path, blanc: str
) -> None:
    """Le découpage de mots se fait sur tous les blancs, pas seulement l'espace."""
    complet = {**BASE, **OPTIONNELLES, "ELDIR_TOOLCHAIN_ABS": f"/var/mon{blanc}dossier/p1"}
    proc = _executer(faux_docker, complet, "-v")

    assert proc.returncode != 0
    assert "ELDIR_TOOLCHAIN_ABS" in proc.stderr
    assert proc.stdout == ""


def test_un_joker_dans_un_montage_optionnel_n_est_pas_developpe(
    faux_docker: Path, tmp_path: Path
) -> None:
    """La même chaîne développée sans guillemets fait aussi du globbing : un `*`
    dans une racine mal saisie serait remplacé par ce qu'il trouve dans le
    système de fichiers, avant que `docker` ne voie quoi que ce soit.

    Le piège est posé pour que l'expansion réussisse : le dossier du cwd dont le
    chemin est exactement le montage attendu (avec `p1` à la place de `p*`).
    Sans `set -f`, l'argument deviendrait ce chemin et non la valeur saisie.
    """
    (
        tmp_path / "type=volume,src=vol_tc,dst=/var/eldir/toolchains/p1,volume-subpath=p1,readonly"
    ).mkdir(parents=True)
    sortie = lancer(
        faux_docker,
        {
            **BASE,
            "ELDIR_TOOLCHAINS_VOLUME": "vol_tc",
            "ELDIR_TOOLCHAIN_ABS": "/var/eldir/toolchains/p*",
            "ELDIR_TOOLCHAIN_SUBPATH": "p1",
        },
        cwd=tmp_path,
    )

    assert (
        "type=volume,src=vol_tc,dst=/var/eldir/toolchains/p*,volume-subpath=p1,readonly" in sortie
    )


def test_les_montages_fixes_tolerent_un_blanc(faux_docker: Path) -> None:
    """Les deux montages fixes sont entre guillemets : un blanc y reste dans un
    seul argument, et `docker` l'accepte, dans le `dst` comme dans le
    `volume-subpath` (mesuré sur un vrai démon, avec plusieurs niveaux de
    sous-chemin à blancs). Les refuser interdirait un déploiement qui
    fonctionne."""
    sortie = lancer(
        faux_docker,
        {
            **BASE,
            "ELDIR_WORKTREE_ABS": "/var/eldir/mon dossier/depot.s1",
            "ELDIR_WORKTREE_SUBPATH": "u1/mon dossier/depot.s1",
            "ELDIR_CLAUDE_HOME_SUBPATH": "mon projet",
        },
    )

    assert _montages(sortie) == [
        "type=volume,src=vol_ws,dst=/var/eldir/mon dossier/depot.s1,"
        "volume-subpath=u1/mon dossier/depot.s1",
        "type=volume,src=vol_maisons,dst=/eldir/maison,volume-subpath=mon projet",
    ]


@pytest.mark.parametrize(
    "absente",
    [
        "ELDIR_CLONE_ABS",
        "ELDIR_TOOLCHAINS_VOLUME",
        "ELDIR_TOOLCHAIN_ABS",
        "ELDIR_COLLECTES_VOLUME",
        "ELDIR_COLLECTE_ABS",
    ],
)
def test_un_montage_optionnel_incomplet_fait_echouer_tot(faux_docker: Path, absente: str) -> None:
    """Un sous-chemin posé sans son volume ou son chemin donnerait à `docker`
    `src=,dst=` : il échouerait plus loin, ou monterait autre chose. Mieux vaut
    le même refus nommé que pour les variables obligatoires."""
    incomplet = {c: v for c, v in {**BASE, **OPTIONNELLES}.items() if c != absente}
    proc = _executer(faux_docker, incomplet, "-v")

    assert proc.returncode != 0
    assert absente in proc.stderr
    assert proc.stdout == ""


def test_un_autre_uid_que_1000_est_refuse_avant_de_demarrer(faux_docker: Path) -> None:
    """L'image n'a qu'un utilisateur, d'uid 1000.

    Mesuré : un uid sans entrée dans le `passwd` de l'image fait mourir `ssh`
    sur « No user exists for uid 1001 » (code 255), et rien dans cette phrase
    ne dit que le vrai problème est l'uid du backend. Le refus nomme ce qu'il
    faut corriger, et `docker` n'est pas lancé (le faux imprimerait ses
    arguments sur la sortie standard).
    """
    proc = _executer(faux_docker, {**BASE, "UID_FAUX": "1001"}, "-v")

    assert proc.returncode != 0
    assert "1001" in proc.stderr
    assert "UID=1000" in proc.stderr
    assert proc.stdout == ""


def test_les_noms_que_l_enrobage_lit_sont_ceux_que_le_backend_produit(
    faux_docker: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Le contrat entre `env_pour_enrobage` et l'enrobage, bout à bout.

    Les autres tests écrivent les variables à la main : un nom renommé d'un
    seul côté les laisserait verts. Ici l'entrée est la sortie réelle de
    `env_pour_enrobage`, avec tout ce qui est optionnel présent. Un nom
    optionnel que l'enrobage ne lirait plus ne ferait rien échouer : le
    montage disparaîtrait, et la fonctionnalité avec.
    """
    racine = tmp_path / "workspaces"
    worktree = racine / "u1" / "depot.s1"
    worktree.mkdir(parents=True)
    (racine / "u1" / "depot" / ".git").mkdir(parents=True)
    (tmp_path / "toolchains" / "p1").mkdir(parents=True)
    (tmp_path / "toolchains" / "p1" / ".eldir-state.json").write_text("{}", encoding="utf-8")
    (tmp_path / "collectes" / "p1").mkdir(parents=True)
    (tmp_path / "collectes" / "p1" / "collecte.log").write_text("", encoding="utf-8")
    for nom, chemin in (
        ("WORKSPACES_ROOT", racine),
        ("CLAUDE_HOME_ROOT", tmp_path / "maisons"),
        ("TOOLCHAINS_ROOT", tmp_path / "toolchains"),
        ("COLLECTES_ROOT", tmp_path / "collectes"),
    ):
        monkeypatch.setenv(nom, str(chemin))
    get_settings.cache_clear()
    try:
        env = env_pour_enrobage(project_id="p1", worktree_abs=worktree, ssh_subpath="p1-ssh/s1")
    finally:
        get_settings.cache_clear()

    texte = ENROBAGE.read_text(encoding="utf-8")
    inconnus = [cle for cle in env if not re.search(rf"\b{cle}\b", texte)]
    assert inconnus == [], "produites par le backend, jamais lues par l'enrobage"

    destinations = {
        montage.split("dst=")[1].split(",")[0]
        for montage in _montages(lancer(faux_docker, env, cwd=worktree))
    }
    assert destinations == {
        str(worktree),
        str(racine / "u1" / "depot"),
        *(
            str(racine / "u1" / "depot" / ".git" / nom)
            for nom in ("", "config", "hooks", "modules")
        ),
        str(tmp_path / "toolchains" / "p1"),
        str(tmp_path / "collectes" / "p1"),
        "/eldir/maison",
        "/eldir/ssh",
    }
