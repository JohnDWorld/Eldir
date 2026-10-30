"""WorktreeService - clone des repos et gestion des git worktrees.

Layout disque :
    /var/eldir/workspaces/{user_id}/
        {repo_slug}/              ← clone canonique (bare ou normal)
        {repo_slug}.{session_id}/ ← worktrees par session (Phase 2)
"""

from __future__ import annotations

import asyncio
import os
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


# Comment git obtient le jeton, sans qu'il touche le disque ni la ligne de
# commande : il le demande à ce helper, qui le lit dans l'environnement du seul
# sous-processus git concerné.
#
# Avant, le jeton était injecté dans l'URL. Celle du clone atterrissait dans
# `.git/config`, donc sous les yeux de la session qui travaille dans ce dépôt :
# un `git remote -v` suffisait. Et `push -u <url>` écrivait en plus l'URL
# complète dans `branch.<branche>.remote`, donc dans le même fichier.
#
# Le hook `PreToolUse` refuse bien `git push` comme commande, mais il filtre
# des commandes, pas des destinations : un `curl` vers l'API du provider avec
# ce jeton ne ressemble pas à un push. Le risque n'était donc pas la
# publication, c'était l'exfiltration, et avec un PAT classique elle portait
# sur tous les dépôts du porteur.
#
# `test "$1" = get` : git appelle aussi le helper pour `store` et `erase`, où
# il ne doit rien répondre. Le jeton ne doit être ni stocké ni effacé, il ne
# vit que le temps de l'appel.
_AIDE_CREDENTIEL = (
    '!f() { test "$1" = get && '
    'printf "username=x-access-token\\npassword=%s\\n" "$ELDIR_GIT_TOKEN"; }; f'
)


def _sans_identifiants(url: str) -> str:
    """Retire le `utilisateur:motdepasse@` d'une URL HTTP(S).

    Sert à assainir les dépôts déjà clonés par une version d'Eldir qui mettait
    le jeton dans l'URL du remote : ils portent le jeton sur le disque jusqu'à
    ce qu'on le retire, et un reclone n'est pas une option raisonnable.
    """
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or "@" not in parsed.netloc:
        return url
    netloc = parsed.hostname or ""
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
            await self._nettoyer_identifiants(dest)
            branch = default_branch or await self._detect_default_branch(dest)
            return CloneResult(path=dest, default_branch=branch, repo_slug=repo_slug)

        dest.parent.mkdir(parents=True, exist_ok=True)
        logger.info("clone.start", repo=repo_full_name, dest=str(dest))
        # L'URL clonée est celle du dépôt, sans identifiant : c'est elle que
        # git écrit dans `.git/config`, et la session la lit.
        await self._run_git("clone", clone_url, str(dest), cwd=dest.parent, token=token)

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
        """Push la branche, le jeton passant par le credential helper.

        On pousse vers le *nom* du remote, jamais vers une URL : `push -u` écrit
        sa cible dans `branch.<branche>.remote`, et une URL avec jeton y restait
        sur le disque.
        """
        args = ["push"]
        if set_upstream:
            args.append("-u")
        args += [remote, branch]
        await self._run_git(*args, cwd=repo_path, token=token)

    async def fetch_remote(
        self,
        repo_path: Path,
        *,
        remote: str = "origin",
        token: str | None = None,
    ) -> None:
        """Fetch un remote, le jeton passant par le credential helper.

        Cette méthode écrivait le jeton courant dans l'URL du remote avant de
        fetch, pour qu'une rotation de PAT n'invalide pas la sync. Le helper
        rend ça inutile : il lit le jeton frais à chaque appel. Surtout, comme
        `RepoWatcher` appelle cette méthode périodiquement, elle repoisonnait
        `.git/config` à intervalle régulier, et nettoyer après le clone n'aurait
        servi à rien.

        C'est maintenant l'inverse : chaque sync assainit le dépôt.
        """
        await self._nettoyer_identifiants(repo_path)
        await self._run_git("fetch", remote, "--prune", cwd=repo_path, token=token)

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

    async def _nettoyer_identifiants(self, repo_path: Path) -> None:
        """Retire du `.git/config` local tout identifiant laissé dans une URL.

        Les dépôts clonés par une version d'Eldir qui injectait le jeton dans
        l'URL le portent sur le disque, lisible par la session qui travaille
        dedans. On balaie la configuration locale entière plutôt que la seule
        `remote.origin.url` : `push -u` en écrivait une copie dans
        `branch.<branche>.remote`, et deviner où elles sont toutes est moins
        sûr que de les chercher.

        Un worktree partage le `config` de son dépôt principal, donc nettoyer
        ici couvre aussi les sessions en cours. Idempotent : sur un dépôt sain,
        aucune écriture.
        """
        sortie = await self._run_git("config", "--local", "--list", cwd=repo_path)
        for ligne in sortie.splitlines():
            cle, separateur, valeur = ligne.partition("=")
            if not separateur:
                continue
            propre = _sans_identifiants(valeur)
            if propre == valeur:
                continue
            await self._run_git("config", "--local", "--replace-all", cle, propre, cwd=repo_path)
            logger.info("remote.identifiant.retire", repo=str(repo_path), cle=cle)

    async def _run_git(self, *args: str, cwd: Path, token: str | None = None) -> str:
        prefixe: tuple[str, ...] = ()
        env: dict[str, str] | None = None
        if token:
            # La valeur vide réinitialise la liste des helpers : git n'utilise
            # que le nôtre, et jamais un helper système qui, lui, stockerait le
            # jeton dans un fichier.
            prefixe = (
                "-c",
                "credential.helper=",
                "-c",
                f"credential.helper={_AIDE_CREDENTIEL}",
            )
            # Le jeton passe par l'environnement de ce seul sous-processus : ni
            # dans la ligne de commande (lisible dans /proc), ni sur le disque.
            # `GIT_TERMINAL_PROMPT=0` pour qu'un refus d'authentification sorte
            # en erreur au lieu d'attendre une saisie qui ne viendra jamais.
            env = {**os.environ, "ELDIR_GIT_TOKEN": token, "GIT_TERMINAL_PROMPT": "0"}
        process = await asyncio.create_subprocess_exec(
            "git",
            *prefixe,
            *args,
            cwd=str(cwd),
            env=env,
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
