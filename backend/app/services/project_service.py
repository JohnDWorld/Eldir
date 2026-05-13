"""ProjectService — création de projets à partir de repos Git distants."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import SUPPORTED_PROVIDERS
from app.core.exceptions import (
    AuthenticationError,
    ConflictError,
    GitProviderError,
    NotFoundError,
)
from app.core.logging import get_logger
from app.db.models import Project
from app.services.git_credential_service import git_credential_service
from app.services.git_providers import make_provider
from app.services.worktree_service import worktree_service

logger = get_logger(__name__)


class ProjectService:
    async def list_for_user(
        self, db: AsyncSession, user_id: str
    ) -> list[Project]:
        result = await db.execute(
            select(Project)
            .where(Project.user_id == user_id)
            .order_by(Project.created_at.desc())
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
        project = await self.get(db, project_id, user_id)
        if project.workspace_path:
            await worktree_service.remove_repo(user_id, project.slug)
        await db.delete(project)


project_service = ProjectService()
