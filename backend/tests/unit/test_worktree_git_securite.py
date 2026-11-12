"""Le git du backend ne suit pas ce qu'une session écrit (risque nº 3).

Dépôts jetables, marqueurs inoffensifs : on affirme qu'Eldir ne lit pas ce
qu'une session a pu réécrire, rien de plus.
"""

from __future__ import annotations

import subprocess
import uuid
from pathlib import Path

import pytest
from app.services.worktree_service import _AIDE_CREDENTIEL, WorktreeService


def _git(*args: str, cwd: Path) -> str:
    return subprocess.run(
        ["git", *args], cwd=cwd, check=True, capture_output=True, text=True
    ).stdout.strip()


@pytest.fixture
def depot(tmp_path: Path) -> tuple[WorktreeService, Path, Path, Path]:
    """Un dépôt nu, son clone et un worktree au chemin qu'Eldir leur donne."""
    racine = tmp_path / "workspaces"
    utilisateur = racine / "u1"
    utilisateur.mkdir(parents=True)
    nu = tmp_path / "nu"
    _git("init", "-q", "--bare", "-b", "main", str(nu), cwd=tmp_path)
    clone = utilisateur / "depot"
    _git("clone", "-q", str(nu), str(clone), cwd=tmp_path)
    _git(
        "-c",
        "user.email=a@exemple.lan",
        "-c",
        "user.name=a",
        "commit",
        "-q",
        "--allow-empty",
        "-m",
        "init",
        cwd=clone,
    )
    _git("push", "-q", "origin", "main", cwd=clone)
    worktree = utilisateur / f"depot.{uuid.uuid4()}"
    _git("worktree", "add", "-q", "-b", "claude/s1", str(worktree), cwd=clone)
    return WorktreeService(root=racine), nu, clone, worktree


def test_le_prefixe_neutralise_toujours_hooks_fsmonitor_et_sous_modules() -> None:
    prefixe = WorktreeService._prefixe_git(None, None)

    for reglage in (
        "core.hooksPath=/dev/null",
        "core.fsmonitor=false",
        "submodule.recurse=false",
        "diff.ignoreSubmodules=all",
    ):
        assert reglage in prefixe


def test_le_jeton_n_est_declare_que_pour_l_origine_de_la_forge() -> None:
    prefixe = WorktreeService._prefixe_git("jeton", "https://forge.exemple.lan")

    assert "credential.helper=" in prefixe
    assert f"credential.https://forge.exemple.lan.helper={_AIDE_CREDENTIEL}" in prefixe
    assert f"credential.helper={_AIDE_CREDENTIEL}" not in prefixe


def test_un_jeton_sans_origine_est_refuse() -> None:
    with pytest.raises(ValueError):
        WorktreeService._prefixe_git("jeton", None)


@pytest.mark.parametrize(
    ("hote", "attendu"), [("forge.exemple.lan", True), ("autre.exemple.lan", False)]
)
def test_git_ne_donne_le_jeton_qu_a_l_hote_de_la_forge(
    tmp_path: Path, hote: str, attendu: bool
) -> None:
    prefixe = WorktreeService._prefixe_git("SECRET-JETON", "https://forge.exemple.lan")
    sortie = subprocess.run(
        ["git", *prefixe, "credential", "fill"],
        input=f"protocol=https\nhost={hote}\n\n",
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
        env={
            "PATH": "/usr/bin:/bin",
            "HOME": str(tmp_path),
            "ELDIR_GIT_TOKEN": "SECRET-JETON",
            "GIT_TERMINAL_PROMPT": "0",
        },
    )

    assert ("SECRET-JETON" in sortie.stdout) is attendu


async def test_un_worktree_reecrit_ne_choisit_pas_la_config_lue(
    depot: tuple[WorktreeService, Path, Path, Path], tmp_path: Path
) -> None:
    service, _, clone, worktree = depot
    _git("config", "eldir.mesure", "vrai", cwd=clone)
    leurre = tmp_path / "leurre.git"
    _git("init", "-q", "--bare", str(leurre), cwd=tmp_path)
    _git("config", "eldir.mesure", "leurre", cwd=leurre)
    (worktree / ".git").write_text(f"gitdir: {leurre}\n")

    assert await service._run_git("config", "eldir.mesure", cwd=worktree) == "vrai"
    assert await service.current_branch(worktree) == "claude/s1"


async def test_un_worktree_au_chemin_d_eldir_commite_et_pousse_toujours(
    depot: tuple[WorktreeService, Path, Path, Path],
) -> None:
    service, nu, _, worktree = depot
    (worktree / "f.txt").write_text("x")

    await service.commit_all(worktree, message="m", author_name="a", author_email="a@exemple.lan")
    await service.push(worktree, branch="claude/s1")

    assert _git("rev-parse", "--verify", "refs/heads/claude/s1", cwd=nu)


def test_un_chemin_hors_convention_n_est_pas_force(tmp_path: Path) -> None:
    service = WorktreeService(root=tmp_path / "workspaces")

    assert service._chemins_forces(tmp_path / "travail") == {}
    assert service._chemins_forces(tmp_path / "ailleurs" / "u1" / "depot") == {}


async def test_un_clone_dont_commondir_est_pose_ne_choisit_pas_la_config_lue(
    depot: tuple[WorktreeService, Path, Path, Path], tmp_path: Path
) -> None:
    service, _, clone, _ = depot
    _git("config", "eldir.mesure", "vrai", cwd=clone)
    leurre = tmp_path / "leurre.git"
    _git("init", "-q", "--bare", str(leurre), cwd=tmp_path)
    _git("config", "eldir.mesure", "leurre", cwd=leurre)
    (clone / ".git" / "commondir").write_text(f"{leurre}\n")

    assert await service._run_git("config", "eldir.mesure", cwd=clone) == "vrai"


async def test_les_worktrees_se_creent_et_se_retirent_depuis_un_clone_aux_chemins_fixes(
    depot: tuple[WorktreeService, Path, Path, Path],
) -> None:
    service, _, clone, _ = depot
    neuf = clone.parent / f"depot.{uuid.uuid4()}"

    await service._run_git("worktree", "add", "-q", "-b", "claude/s2", str(neuf), cwd=clone)
    assert (neuf / ".git").exists()
    await service._run_git("worktree", "remove", "--force", str(neuf), cwd=clone)
    assert not neuf.exists()
