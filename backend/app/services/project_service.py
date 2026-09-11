"""ProjectService - création de projets à partir de repos Git distants."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import SUPPORTED_PROVIDERS
from app.core.exceptions import (
    AuthenticationError,
    ConflictError,
    GitProviderError,
    NotFoundError,
    WorkspaceError,
)
from app.core.logging import get_logger
from app.db.models import MissionTemplate, Project
from app.services.collect_service import collect_service
from app.services.git_credential_service import git_credential_service
from app.services.git_providers import make_provider
from app.services.remote_access_service import remote_access_service
from app.services.toolchain_service import toolchain_service
from app.services.worktree_service import worktree_service

logger = get_logger(__name__)


@dataclass(slots=True, frozen=True)
class SyncResult:
    fetched: bool
    fast_forwarded: bool
    ahead: int
    behind: int
    branch: str
    has_local_changes: bool
    message: str | None = None
    # Commits effectivement récupérés par le fast-forward. `behind` est
    # recalculé après coup, donc il vaut 0 quand le pull a réussi : sans ce
    # champ, l'UI affichait « mis à jour · 0 commit récupéré ».
    pulled: int = 0


class ProjectService:
    async def project_ids_with_template(self, db: AsyncSession, user_id: str) -> set[str]:
        """Projets de l'utilisateur qui ont déjà un Mission Template."""
        result = await db.execute(
            select(MissionTemplate.project_id)
            .join(Project, Project.id == MissionTemplate.project_id)
            .where(Project.user_id == user_id)
        )
        return set(result.scalars().all())

    async def list_for_user(self, db: AsyncSession, user_id: str) -> list[Project]:
        result = await db.execute(
            select(Project).where(Project.user_id == user_id).order_by(Project.created_at.desc())
        )
        return list(result.scalars().all())

    async def get(self, db: AsyncSession, project_id: str, user_id: str) -> Project:
        result = await db.execute(
            select(Project).where(
                Project.id == project_id,
                Project.user_id == user_id,
            )
        )
        project = result.scalar_one_or_none()
        if project is None:
            raise NotFoundError(f"Projet {project_id} introuvable.")
        return project

    async def create_from_repo(
        self,
        db: AsyncSession,
        *,
        user_id: str,
        provider: str,
        repo_full_name: str,
        display_name: str | None = None,
    ) -> Project:
        """Crée un projet en clonant un repo distant.

        Étapes :
        1. Lit le PAT du provider depuis git_credentials.
        2. Récupère les métadonnées du repo via l'API du provider.
        3. Clone le repo dans /var/eldir/workspaces/{user_id}/{slug}.
        4. Persiste le projet en DB.
        """
        if provider not in SUPPORTED_PROVIDERS:
            raise GitProviderError(f"Provider non supporté : {provider}")

        token = await git_credential_service.get_active_token(db, user_id, provider)
        if not token:
            raise AuthenticationError(
                f"Aucun credential {provider} configuré. Va dans Settings > Git."
            )

        provider_client = make_provider(provider, token=token)
        try:
            repo_ref = await provider_client.get_repo(repo_full_name)
        except GitProviderError:
            raise

        # Empêche les doublons côté DB.
        result = await db.execute(
            select(Project).where(
                Project.user_id == user_id,
                Project.provider == provider,
                Project.repo_full_name == repo_full_name,
            )
        )
        if result.scalar_one_or_none() is not None:
            raise ConflictError(
                f"Le projet {provider}:{repo_full_name} existe déjà.",
            )

        clone = await worktree_service.clone_repo(
            user_id=user_id,
            repo_full_name=repo_full_name,
            clone_url=repo_ref.clone_url,
            token=token,
            default_branch=repo_ref.default_branch,
        )

        project = Project(
            user_id=user_id,
            name=display_name or repo_ref.full_name.split("/")[-1],
            slug=clone.repo_slug,
            provider=provider,
            repo_full_name=repo_ref.full_name,
            default_branch=clone.default_branch,
            workspace_path=str(clone.path),
        )
        db.add(project)
        await db.flush()
        logger.info(
            "project.created",
            project_id=project.id,
            provider=provider,
            repo=repo_full_name,
        )
        return project

    async def delete(self, db: AsyncSession, project_id: str, user_id: str) -> None:
        """Retire le projet et tout ce qu'il a laissé sur le serveur.

        La row part en cascade (sessions, events, coûts, template), mais le
        disque et la machine distante ne se nettoient pas tout seuls. Ce qui
        traîne sinon : un SDK Flutter de 2,4 Go dans le volume des toolchains,
        des fichiers de prod dans la collecte, et surtout une clé Eldir encore
        autorisée sur une machine dont le projet n'existe plus.

        Chaque étape est isolée : une machine éteinte au moment de la
        suppression ne doit pas empêcher de supprimer le projet. Ce qui n'a pas
        pu être nettoyé est journalisé plutôt que perdu en silence.
        """
        project = await self.get(db, project_id, user_id)

        # La clé d'abord, tant que la config SSH du projet existe encore.
        try:
            retiree = await remote_access_service.revoke(project_id)
            if not retiree and remote_access_service.status(project_id).configured:
                logger.warning("project.delete.cle_non_revoquee", project_id=project_id)
        except Exception:
            logger.exception("project.delete.remote.failed", project_id=project_id)

        if project.workspace_path:
            try:
                await worktree_service.remove_repo(user_id, project.slug)
            except Exception:
                logger.exception("project.delete.repo.failed", project_id=project_id)

        try:
            await toolchain_service.remove(project_id)
        except Exception:
            logger.exception("project.delete.toolchain.failed", project_id=project_id)

        try:
            await collect_service.remove(project_id)
        except Exception:
            logger.exception("project.delete.collecte.failed", project_id=project_id)

        await db.delete(project)

    async def sync_with_remote(
        self,
        db: AsyncSession,
        *,
        project_id: str,
        user_id: str,
    ) -> SyncResult:
        """Fetch le remote du projet et fast-forward si possible (no-op safe).

        Stratégie :
        - fetch toujours (impact zéro sur le working tree).
        - fast-forward la branche par défaut uniquement si :
            * la branche courante est la branche par défaut,
            * il n'y a pas de modifications locales non commitées,
            * la branche locale est en retard.

        Sinon on remonte un `message` explicatif et on ne touche pas au working tree.
        """
        project = await self.get(db, project_id, user_id)
        if not project.workspace_path:
            raise WorkspaceError(
                f"Projet {project_id} n'a pas de workspace cloné.",
            )

        repo_path = Path(project.workspace_path)
        token = await git_credential_service.get_active_token(db, user_id, project.provider)
        default_branch = project.default_branch
        upstream_ref = f"origin/{default_branch}"

        try:
            await worktree_service.fetch_remote(repo_path, token=token)
        except WorkspaceError as exc:
            logger.warning(
                "project.sync.fetch_failed",
                project_id=project_id,
                error=exc.message,
            )
            current = await worktree_service.current_branch(repo_path)
            return SyncResult(
                fetched=False,
                fast_forwarded=False,
                ahead=0,
                behind=0,
                branch=current,
                has_local_changes=False,
                message=f"fetch impossible : {exc.message}",
            )

        current = await worktree_service.current_branch(repo_path)
        has_changes = await worktree_service.has_changes(repo_path)
        ahead, behind = await worktree_service.branch_ahead_behind(
            repo_path, local=default_branch, remote=upstream_ref
        )

        fast_forwarded = False
        pulled = 0
        message: str | None = None
        if behind > 0:
            if has_changes:
                message = (
                    f"{behind} commit(s) en retard mais working tree sale "
                    "- pull skippé pour préserver le travail en cours."
                )
            elif current != default_branch:
                message = (
                    f"{behind} commit(s) en retard mais branche courante = "
                    f"`{current}` (≠ `{default_branch}`) - pull skippé."
                )
            else:
                try:
                    await worktree_service.fast_forward_merge(repo_path, upstream_ref=upstream_ref)
                    fast_forwarded = True
                    pulled = behind
                    ahead, behind = await worktree_service.branch_ahead_behind(
                        repo_path, local=default_branch, remote=upstream_ref
                    )
                except WorkspaceError as exc:
                    message = f"fast-forward impossible : {exc.message}"

        logger.info(
            "project.sync.done",
            project_id=project_id,
            fast_forwarded=fast_forwarded,
            pulled=pulled,
            ahead=ahead,
            behind=behind,
        )
        return SyncResult(
            fetched=True,
            fast_forwarded=fast_forwarded,
            pulled=pulled,
            ahead=ahead,
            behind=behind,
            branch=current,
            has_local_changes=has_changes,
            message=message,
        )


project_service = ProjectService()
