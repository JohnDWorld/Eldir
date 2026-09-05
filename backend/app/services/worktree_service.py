"""WorktreeService - clone des repos et gestion des git worktrees.

Layout disque :
    /var/eldir/workspaces/{user_id}/
        {repo_slug}/              ← clone canonique (bare ou normal)
        {repo_slug}.{session_id}/ ← worktrees par session (Phase 2)
"""

from __future__ import annotations

import asyncio
import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse, urlunparse

from app.core.config import get_settings
from app.core.constants import SESSION_BRANCH_PREFIX, SESSION_WORKTREE_TEMPLATE
from app.core.exceptions import WorkspaceError
from app.core.logging import get_logger

logger = get_logger(__name__)

_SLUG_PATTERN = re.compile(r"[^a-z0-9-]+")
_DUP_DASH = re.compile(r"-+")


def slugify(name: str) -> str:
    """Slugifie un nom pour usage filesystem."""
    s = name.lower().strip().replace("/", "-")
    s = _SLUG_PATTERN.sub("-", s)
    s = _DUP_DASH.sub("-", s)
    s = s.strip("-")
    return s or "repo"


@dataclass(slots=True, frozen=True)
class WorktreeRef:
    path: Path
    branch: str
    base_branch: str


@dataclass(slots=True, frozen=True)
class CloneResult:
    path: Path
    default_branch: str
    repo_slug: str


@dataclass(slots=True, frozen=True)
class FileChange:
    """Un fichier modifié dans un diff (committed ou working tree)."""

    path: str
    status: str  # A | M | D | R | C | U | T (cf. git diff --name-status)
    additions: int
    deletions: int


def _inject_token(clone_url: str, token: str) -> str:
    """Injecte un PAT dans l'URL HTTPS pour le clone."""
    parsed = urlparse(clone_url)
    if parsed.scheme not in {"http", "https"}:
        return clone_url
    # username `x-access-token` est conventionnel chez GitHub.
    netloc = f"x-access-token:{token}@{parsed.hostname}"
    if parsed.port:
        netloc = f"{netloc}:{parsed.port}"
    return urlunparse(parsed._replace(netloc=netloc))


class WorktreeService:
    def __init__(self, root: Path | None = None) -> None:
        self._root = root or get_settings().workspaces_root

    # ── paths ───────────────────────────────────────────────────
    def user_root(self, user_id: str) -> Path:
        return self._root / user_id

    def repo_path(self, user_id: str, repo_slug: str) -> Path:
        return self.user_root(user_id) / repo_slug

    def session_worktree_path(self, user_id: str, repo_slug: str, session_id: str) -> Path:
        return self.user_root(user_id) / SESSION_WORKTREE_TEMPLATE.format(
            repo_slug=repo_slug, session_id=session_id
        )

    def session_branch(self, session_id: str, slug: str | None = None) -> str:
        suffix = f"-{slug}" if slug else ""
        return f"{SESSION_BRANCH_PREFIX}{session_id}{suffix}"

    # ── clone ───────────────────────────────────────────────────
    async def clone_repo(
        self,
        *,
        user_id: str,
        repo_full_name: str,
        clone_url: str,
        token: str | None = None,
        default_branch: str | None = None,
    ) -> CloneResult:
        """Clone un repo dans /var/eldir/workspaces/{user_id}/{repo_slug}/.

        Idempotent : si le dossier existe déjà avec un .git valide, on n'écrase pas.
        """
        repo_slug = slugify(repo_full_name)
        dest = self.repo_path(user_id, repo_slug)

        if (dest / ".git").is_dir():
            logger.info("clone.skip.exists", repo=repo_full_name, dest=str(dest))
            branch = default_branch or await self._detect_default_branch(dest)
            return CloneResult(path=dest, default_branch=branch, repo_slug=repo_slug)

        dest.parent.mkdir(parents=True, exist_ok=True)
        url = _inject_token(clone_url, token) if token else clone_url
        logger.info("clone.start", repo=repo_full_name, dest=str(dest))
        await self._run_git("clone", url, str(dest), cwd=dest.parent)

        branch = default_branch or await self._detect_default_branch(dest)
        logger.info("clone.done", repo=repo_full_name, branch=branch)
        return CloneResult(path=dest, default_branch=branch, repo_slug=repo_slug)

    async def remove_repo(self, user_id: str, repo_slug: str) -> None:
        dest = self.repo_path(user_id, repo_slug)
        if dest.exists():
            shutil.rmtree(dest, ignore_errors=False)
            logger.info("repo.removed", path=str(dest))

    # ── worktrees (Phase 2 - squelette) ─────────────────────────
    async def create_worktree(
        self,
        *,
        repo_path: Path,
        user_id: str,
        repo_slug: str,
        session_id: str,
        base_branch: str,
        slug: str | None = None,
    ) -> WorktreeRef:
        branch = self.session_branch(session_id, slug)
        wt_path = self.session_worktree_path(user_id, repo_slug, session_id)
        wt_path.parent.mkdir(parents=True, exist_ok=True)
        await self._run_git(
            "worktree", "add", "-b", branch, str(wt_path), base_branch, cwd=repo_path
        )
        return WorktreeRef(path=wt_path, branch=branch, base_branch=base_branch)

    async def remove_worktree(self, repo_path: Path, worktree_path: Path) -> None:
        await self._run_git("worktree", "remove", "--force", str(worktree_path), cwd=repo_path)

    # ── git status / commit / push ──────────────────────────────
    async def current_branch(self, repo_path: Path) -> str:
        out = await self._run_git("symbolic-ref", "--short", "HEAD", cwd=repo_path)
        return out or "main"

    async def has_changes(self, repo_path: Path) -> bool:
        out = await self._run_git("status", "--porcelain", cwd=repo_path)
        return bool(out.strip())

    async def status_summary(self, repo_path: Path) -> dict[str, int]:
        out = await self._run_git("status", "--porcelain", cwd=repo_path)
        summary = {"modified": 0, "added": 0, "deleted": 0, "untracked": 0}
        for line in out.splitlines():
            if len(line) < 2:
                continue
            code = line[:2]
            if "?" in code:
                summary["untracked"] += 1
            elif "A" in code:
                summary["added"] += 1
            elif "D" in code:
                summary["deleted"] += 1
            else:
                summary["modified"] += 1
        return summary

    async def commit_all(
        self,
        repo_path: Path,
        *,
        message: str,
        author_name: str | None = None,
        author_email: str | None = None,
    ) -> str:
        if not await self.has_changes(repo_path):
            raise WorkspaceError("Rien à commiter.", details={"path": str(repo_path)})

        await self._run_git("config", "user.name", author_name or "Eldir", cwd=repo_path)
        await self._run_git("config", "user.email", author_email or "eldir@local", cwd=repo_path)
        await self._run_git("add", "-A", cwd=repo_path)
        await self._run_git("commit", "-m", message, cwd=repo_path)
        return await self._run_git("rev-parse", "HEAD", cwd=repo_path)

    async def push(
        self,
        repo_path: Path,
        *,
        branch: str,
        token: str | None = None,
        remote: str = "origin",
        set_upstream: bool = True,
    ) -> None:
        """Push la branche. Si token, injecte temporairement le PAT dans l'URL."""
        if token:
            remote_url = await self._run_git("remote", "get-url", remote, cwd=repo_path)
            push_url = _inject_token(remote_url, token)
            args = ["push"]
            if set_upstream:
                args.append("-u")
            args += [push_url, branch]
        else:
            args = ["push"]
            if set_upstream:
                args.append("-u")
            args += [remote, branch]
        await self._run_git(*args, cwd=repo_path)

    async def fetch_remote(
        self,
        repo_path: Path,
        *,
        remote: str = "origin",
        token: str | None = None,
    ) -> None:
        """Fetch un remote, en réécrivant son URL si un token plus frais est dispo.

        Ainsi un rotation de PAT n'invalide pas la sync : on remet le token
        courant dans l'URL de l'origine avant de fetch.
        """
        if token:
            remote_url = await self._run_git("remote", "get-url", remote, cwd=repo_path)
            new_url = _inject_token(remote_url, token)
            if new_url != remote_url:
                await self._run_git("remote", "set-url", remote, new_url, cwd=repo_path)
        await self._run_git("fetch", remote, "--prune", cwd=repo_path)

    async def branch_ahead_behind(
        self,
        repo_path: Path,
        *,
        local: str,
        remote: str,
    ) -> tuple[int, int]:
        """Retourne (ahead, behind) entre `local` et `remote` (refs git)."""
        try:
            out = await self._run_git(
                "rev-list",
                "--left-right",
                "--count",
                f"{local}...{remote}",
                cwd=repo_path,
            )
        except WorkspaceError:
            return (0, 0)
        parts = out.split()
        if len(parts) != 2:
            return (0, 0)
        try:
            return (int(parts[0]), int(parts[1]))
        except ValueError:
            return (0, 0)

    async def fast_forward_merge(
        self,
        repo_path: Path,
        *,
        upstream_ref: str,
    ) -> None:
        """Fast-forward la branche courante sur `upstream_ref`. Échoue sinon."""
        await self._run_git("merge", "--ff-only", upstream_ref, cwd=repo_path)

    async def merge_base(self, repo_path: Path, *, a: str, b: str) -> str | None:
        """Retourne le SHA du merge-base entre `a` et `b`, ou None si absent."""
        try:
            return await self._run_git("merge-base", a, b, cwd=repo_path)
        except WorkspaceError:
            return None

    async def diff_summary(self, repo_path: Path, *, base_ref: str) -> list[FileChange]:
        """Liste les fichiers modifiés depuis `base_ref` (committed + working tree).

        Combine `git diff --name-status` et `git diff --numstat` pour avoir
        à la fois le statut (A/M/D/R/C) et les stats de lignes.
        """
        try:
            name_status = await self._run_git("diff", "--name-status", base_ref, cwd=repo_path)
            numstat = await self._run_git("diff", "--numstat", base_ref, cwd=repo_path)
        except WorkspaceError:
            return []

        stats: dict[str, tuple[int, int]] = {}
        for line in numstat.splitlines():
            parts = line.split("\t")
            if len(parts) < 3:
                continue
            adds_raw, dels_raw, path = parts[0], parts[1], parts[-1]
            # Pour binaires, git met `-` au lieu de chiffres.
            adds = int(adds_raw) if adds_raw.isdigit() else 0
            dels = int(dels_raw) if dels_raw.isdigit() else 0
            stats[path] = (adds, dels)

        changes: list[FileChange] = []
        for line in name_status.splitlines():
            parts = line.split("\t")
            if len(parts) < 2:
                continue
            status_code = parts[0][:1]
            path = parts[-1]
            adds, dels = stats.get(path, (0, 0))
            changes.append(
                FileChange(path=path, status=status_code, additions=adds, deletions=dels)
            )
        return changes

    async def diff_file(self, repo_path: Path, *, base_ref: str, path: str) -> str:
        """Diff unifié d'un fichier vs `base_ref`. Retourne '' si pas de changement."""
        try:
            return await self._run_git("diff", base_ref, "--", path, cwd=repo_path)
        except WorkspaceError:
            return ""

    async def checkout_new_branch(
        self,
        repo_path: Path,
        *,
        branch: str,
        base: str | None = None,
    ) -> None:
        cmd = ["checkout", "-b", branch]
        if base:
            cmd.append(base)
        await self._run_git(*cmd, cwd=repo_path)

    # ── helpers ─────────────────────────────────────────────────
    async def _detect_default_branch(self, repo_path: Path) -> str:
        try:
            out = await self._run_git("symbolic-ref", "--short", "HEAD", cwd=repo_path)
            return out or "main"
        except WorkspaceError:
            return "main"

    async def _run_git(self, *args: str, cwd: Path) -> str:
        process = await asyncio.create_subprocess_exec(
            "git",
            *args,
            cwd=str(cwd),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await process.communicate()
        if process.returncode != 0:
            err = stderr.decode().strip()
            # Masque le token éventuel dans le message d'erreur.
            err = re.sub(r"x-access-token:[^@]+@", "x-access-token:***@", err)
            raise WorkspaceError(
                f"git {' '.join(args)} failed",
                details={"stderr": err},
            )
        return stdout.decode().strip()


worktree_service = WorktreeService()
