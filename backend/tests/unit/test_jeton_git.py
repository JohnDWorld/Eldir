"""Le jeton Git n'est pas à portée d'une session.

Une session travaille dans un worktree du dépôt cloné et tourne en
`bypassPermissions`. Le hook `PreToolUse` lui refuse `git push`, mais il filtre
des commandes, pas des destinations : un jeton trouvé dans `.git/config` part
par `curl` vers l'API du provider sans ressembler à un push. La garde utile
n'est donc pas « refuser la commande », c'est « que le jeton ne soit pas là ».
"""

from __future__ import annotations

import asyncio
import os
import subprocess
from pathlib import Path
from typing import Any

import pytest
from app.core.exceptions import WorkspaceError
from app.services.worktree_service import (
    _AIDE_CREDENTIEL,
    WorktreeService,
    _sans_identifiants,
)

# La sentinelle ne doit PAS ressembler à un vrai jeton. `ghp_` suivi
# d'alphanumériques est le format d'un PAT GitHub : GitGuardian l'a signalée
# comme un secret en clair sur la PR, un rapport qui n'était pas faux dans sa
# forme et qui coûte cher sur un dépôt public, puisqu'un contrôle qui crie au
# loup est un contrôle qu'on arrête de lire. Le test n'y perd rien : cette
# valeur ne sert qu'à être cherchée dans les fichiers, dans `argv`, dans
# l'environnement et dans la sortie de git.
#
# Les jetons à métacaractères plus bas gardent, eux, le préfixe `ghp_` : leur
# corps contient `$`, des accents graves, des espaces ou `%`, donc aucun
# détecteur ne les prend pour un vrai jeton, et le préfixe dit ce qu'ils
# imitent.
JETON = "sentinelle-de-jeton-a-ne-jamais-retrouver"


def git(*args: str, cwd: Path) -> str:
    """Un git direct, sans passer par le service : c'est le témoin."""
    resultat = subprocess.run(
        ["git", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=True,
        env={**os.environ, "GIT_TERMINAL_PROMPT": "0"},
    )
    return resultat.stdout.strip()


@pytest.fixture
def depot_source(tmp_path: Path) -> Path:
    """Un dépôt d'origine, local, pour cloner sans réseau."""
    source = tmp_path / "origine"
    source.mkdir()
    git("init", "--initial-branch=main", cwd=source)
    git("config", "user.email", "eldir@local", cwd=source)
    git("config", "user.name", "Eldir", cwd=source)
    (source / "README.md").write_text("origine\n")
    git("add", "-A", cwd=source)
    git("commit", "-m", "premier", cwd=source)
    return source


def tout_ce_que_la_session_peut_lire(depot: Path) -> str:
    """Le contenu de chaque fichier de `.git`, concaténé.

    `git remote -v` est le geste évident, mais ce n'est pas le seul : un
    `grep -r` dans `.git` trouve aussi bien. Le test lit donc tout, plutôt que
    la seule clé qu'on a pensé à nettoyer.
    """
    morceaux = []
    for chemin in (depot / ".git").rglob("*"):
        if chemin.is_file():
            morceaux.append(chemin.read_bytes().decode("utf-8", errors="replace"))
    return "\n".join(morceaux)


async def test_le_jeton_n_atterrit_nulle_part_dans_le_depot_clone(
    tmp_path: Path, depot_source: Path
) -> None:
    """Le test que John demande : une session ne peut pas pousser en lisant .git/config.

    Avant, l'URL du clone portait le jeton et git l'écrivait dans
    `remote.origin.url` : la session n'avait qu'à le lire pour pousser où elle
    voulait, ou pour s'en servir ailleurs.
    """
    service = WorktreeService(root=tmp_path / "workspaces")
    resultat = await service.clone_repo(
        user_id="u1",
        repo_full_name="owner/repo",
        clone_url=str(depot_source),
        token=JETON,
    )

    assert JETON not in tout_ce_que_la_session_peut_lire(resultat.path)
    assert JETON not in git("remote", "-v", cwd=resultat.path)
    # Témoin : le clone a bien eu lieu, sinon « rien ne contient le jeton »
    # serait vrai d'un dossier vide.
    assert (resultat.path / "README.md").exists()


async def test_l_url_du_clone_ne_porte_jamais_le_jeton(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """La garde sur une vraie URL https, celle qui déclenchait l'injection.

    Le test voisin clone depuis un chemin local, où l'ancien code n'injectait
    rien : il prouve que le dépôt obtenu est propre, pas que l'injection a
    disparu. Ici l'URL est en https, donc sur le chemin exact du défaut. Le
    port 1 de la boucle locale refuse tout de suite : aucun réseau, aucune
    attente, et le clone échoue après que la commande a été construite.
    """
    service = WorktreeService(root=tmp_path / "workspaces")
    appels: list[tuple[str, ...]] = []
    vrai = asyncio.create_subprocess_exec

    async def espion(*args: str, **kwargs: Any) -> Any:
        appels.append(args)
        return await vrai(*args, **kwargs)

    monkeypatch.setattr(asyncio, "create_subprocess_exec", espion)

    with pytest.raises(WorkspaceError):
        await service.clone_repo(
            user_id="u1",
            repo_full_name="owner/repo",
            clone_url="https://127.0.0.1:1/owner/repo.git",
            token=JETON,
        )

    clones = [args for args in appels if "clone" in args]
    assert clones, "aucun clone observé"
    for args in clones:
        assert not any(JETON in a for a in args), f"jeton dans la commande : {args}"


def test_le_helper_rend_le_jeton_a_git() -> None:
    """Le contrat du helper, vérifié par git lui-même.

    Sans ça, « le jeton n'est pas dans le dépôt » pourrait simplement
    vouloir dire qu'aucune authentification ne fonctionne plus.
    """
    resultat = subprocess.run(
        [
            "git",
            "-c",
            "credential.helper=",
            "-c",
            f"credential.helper={_AIDE_CREDENTIEL}",
            "credential",
            "fill",
        ],
        input="protocol=https\nhost=github.com\n\n",
        capture_output=True,
        text=True,
        check=True,
        env={**os.environ, "ELDIR_GIT_TOKEN": JETON},
    )

    assert "username=x-access-token" in resultat.stdout
    assert f"password={JETON}" in resultat.stdout


@pytest.mark.parametrize(
    "jeton",
    [
        "ghp_$(whoami)",
        "ghp_`id`",
        "ghp_guillemets\"et'apostrophes",
        "ghp_avec espace;rm -rf /tmp/x",
        # `%s` et `%n` : le jeton est l'argument du printf du helper, pas son
        # format. S'il devenait le format, `%n` écrirait en mémoire.
        "ghp_%s%n",
    ],
)
def test_un_jeton_a_metacaracteres_ressort_intact(jeton: str) -> None:
    """Le helper est une commande shell : un jeton hostile ne doit pas s'y exécuter.

    C'est l'autre raison de passer par l'environnement plutôt que par l'URL ou
    la ligne de commande : la valeur n'est jamais interpolée dans du texte que
    le shell relit.
    """
    resultat = subprocess.run(
        [
            "git",
            "-c",
            "credential.helper=",
            "-c",
            f"credential.helper={_AIDE_CREDENTIEL}",
            "credential",
            "fill",
        ],
        input="protocol=https\nhost=github.com\n\n",
        capture_output=True,
        text=True,
        check=True,
        env={**os.environ, "ELDIR_GIT_TOKEN": jeton},
    )

    rendus = [
        ligne.removeprefix("password=")
        for ligne in resultat.stdout.splitlines()
        if ligne.startswith("password=")
    ]
    assert rendus == [jeton]


async def test_le_jeton_passe_par_l_environnement_et_pas_par_la_ligne_de_commande(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, depot_source: Path
) -> None:
    """La ligne de commande d'un process est lisible par ses voisins (/proc).

    Le jeton ne doit donc pas y être, même le temps d'un push. Et le push doit
    viser le *nom* du remote : `push -u <url>` écrit sa cible dans
    `branch.<branche>.remote`, ce qui remettait l'URL complète sur le disque.
    """
    service = WorktreeService(root=tmp_path / "workspaces")
    appels: list[tuple[tuple[str, ...], dict[str, Any]]] = []
    vrai = asyncio.create_subprocess_exec

    async def espion(*args: str, **kwargs: Any) -> Any:
        appels.append((args, kwargs))
        return await vrai(*args, **kwargs)

    monkeypatch.setattr(asyncio, "create_subprocess_exec", espion)

    # On pousse vers un dépôt nu : un vrai push, pas un « déjà à jour » qui ne
    # prouverait pas que `-u` a écrit son upstream.
    nu = tmp_path / "nu.git"
    # Nu et non vide : cloner un dépôt vide laisse une branche non née, et le
    # push échouerait pour cette raison plutôt que pour ce qu'on teste.
    git("clone", "--bare", str(depot_source), str(nu), cwd=tmp_path)
    clone = await service.clone_repo(
        user_id="u1", repo_full_name="owner/repo", clone_url=str(nu), token=JETON
    )
    git("config", "user.email", "eldir@local", cwd=clone.path)
    git("config", "user.name", "Eldir", cwd=clone.path)
    (clone.path / "travail.txt").write_text("fait\n")
    git("add", "-A", cwd=clone.path)
    git("commit", "-m", "travail", cwd=clone.path)

    await service.push(clone.path, branch="main", token=JETON)

    pousses = [(args, kw) for args, kw in appels if "push" in args]
    assert pousses, "aucun push observé"
    for args, kwargs in pousses:
        assert not any(JETON in a for a in args), f"jeton dans la ligne de commande : {args}"
        assert "origin" in args, "le push doit viser le nom du remote, pas une URL"
        assert kwargs["env"]["ELDIR_GIT_TOKEN"] == JETON
        assert kwargs["env"]["GIT_TERMINAL_PROMPT"] == "0"

    # Ce que `-u` a écrit : un nom de remote, pas une URL avec jeton.
    assert git("config", "--local", "branch.main.remote", cwd=clone.path) == "origin"
    assert JETON not in tout_ce_que_la_session_peut_lire(clone.path)


async def test_un_depot_deja_empoisonne_est_assaini(tmp_path: Path, depot_source: Path) -> None:
    """Les clones déjà sur le disque portent le jeton : il faut les nettoyer.

    Deux endroits, parce que les deux existaient : l'URL du remote, écrite par
    le clone, et `branch.<branche>.remote`, écrite par `push -u <url>`.
    """
    service = WorktreeService(root=tmp_path / "workspaces")
    clone = await service.clone_repo(
        user_id="u1", repo_full_name="owner/repo", clone_url=str(depot_source), token=None
    )
    empoisonnee = f"https://x-access-token:{JETON}@github.com/owner/repo.git"
    git("remote", "set-url", "origin", empoisonnee, cwd=clone.path)
    git("config", "--local", "branch.main.remote", empoisonnee, cwd=clone.path)
    assert JETON in tout_ce_que_la_session_peut_lire(clone.path)

    await service._nettoyer_identifiants(clone.path)

    assert JETON not in tout_ce_que_la_session_peut_lire(clone.path)
    # L'URL reste utilisable, seul l'identifiant part.
    assert git("remote", "get-url", "origin", cwd=clone.path) == (
        "https://github.com/owner/repo.git"
    )


async def test_chaque_sync_assainit_le_depot(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, depot_source: Path
) -> None:
    """`fetch_remote` nettoie avant de fetch, et c'est l'ordre qui compte.

    Cette méthode faisait l'inverse : elle réécrivait le jeton courant dans
    l'URL du remote à chaque appel. Comme `RepoWatcher` l'appelle
    périodiquement, nettoyer après le clone n'aurait servi à rien, le dépôt
    était repoisonné à intervalle régulier.
    """
    service = WorktreeService(root=tmp_path / "workspaces")
    clone = await service.clone_repo(
        user_id="u1", repo_full_name="owner/repo", clone_url=str(depot_source), token=None
    )
    ordre: list[str] = []
    vrai_nettoyage = service._nettoyer_identifiants
    vrai_git = service._run_git

    async def nettoyage_observe(chemin: Path) -> None:
        ordre.append("nettoyage")
        await vrai_nettoyage(chemin)

    async def git_observe(*args: str, **kwargs: Any) -> str:
        if "fetch" in args:
            ordre.append("fetch")
        return await vrai_git(*args, **kwargs)

    monkeypatch.setattr(service, "_nettoyer_identifiants", nettoyage_observe)
    monkeypatch.setattr(service, "_run_git", git_observe)

    await service.fetch_remote(clone.path, token=JETON)

    assert ordre == ["nettoyage", "fetch"]
    assert JETON not in tout_ce_que_la_session_peut_lire(clone.path)


def test_sans_identifiants_ne_touche_que_les_url_authentifiees() -> None:
    assert (
        _sans_identifiants(f"https://x-access-token:{JETON}@github.com/o/r.git")
        == "https://github.com/o/r.git"
    )
    assert (
        _sans_identifiants("https://forge.exemple.lan:3000/o/r.git")
        == "https://forge.exemple.lan:3000/o/r.git"
    )
    # Le port survit au nettoyage : une forge auto-hébergée n'écoute pas en 443.
    assert (
        _sans_identifiants(f"https://x-access-token:{JETON}@forge.exemple.lan:3000/o/r.git")
        == "https://forge.exemple.lan:3000/o/r.git"
    )
    # On ne touche pas aux URL SSH.
    assert _sans_identifiants("git@github.com:o/r.git") == "git@github.com:o/r.git"
