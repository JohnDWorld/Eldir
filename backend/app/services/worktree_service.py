"""WorktreeService — clone des repos et gestion des git worktrees.

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

    def session_worktree_path(
        self, user_id: str, repo_slug: str, session_id: str
    ) -> Path:
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

    # ── worktrees (Phase 2 — squelette) ─────────────────────────
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
        await self._run_git(
            "worktree", "remove", "--force", str(worktree_path), cwd=repo_path
        )

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

        await self._run_git(
            "config", "user.name", author_name or "Eldir", cwd=repo_path
        )
        await self._run_git(
            "config", "user.email", author_email or "eldir@local", cwd=repo_path
        )
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
            remote_url = await self._run_git(
                "remote", "get-url", remote, cwd=repo_path
            )
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
            out = await self._run_git(
                "symbolic-ref", "--short", "HEAD", cwd=repo_path
            )
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
