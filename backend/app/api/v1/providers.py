"""Routes /providers/{provider} - interactions avec les Git providers distants."""

from __future__ import annotations

from fastapi import APIRouter, status

from app.core.constants import SUPPORTED_PROVIDERS
from app.core.deps import CurrentUserId, DbDep
from app.core.exceptions import AuthenticationError, GitProviderError
from app.schemas.project import (
    ProjectRead,
    RemoteRepoCreate,
    RemoteRepoRead,
)
from app.services.git_credential_service import git_credential_service
from app.services.git_providers import make_provider
from app.services.project_service import project_service

router = APIRouter(prefix="/providers", tags=["providers"])


def _check_provider(name: str) -> None:
    if name not in SUPPORTED_PROVIDERS:
        raise GitProviderError(f"Provider non supporté : {name}")


async def _client_for(db, user_id: str, provider: str):  # type: ignore[no-untyped-def]
    _check_provider(provider)
    token = await git_credential_service.get_active_token(db, user_id, provider)
    if not token:
        raise AuthenticationError(f"Aucun credential {provider} configuré. Va dans Settings > Git.")
    # base_url uniquement pour Forgejo
    cred = await git_credential_service.get_active(db, user_id, provider)
    base_url = cred.base_url if cred and cred.base_url else None
    return make_provider(provider, token=token, base_url=base_url)


@router.get(
    "/{provider}/repos",
    response_model=list[RemoteRepoRead],
)
async def list_remote_repos(
    provider: str,
    user_id: CurrentUserId,
    db: DbDep,
) -> list[RemoteRepoRead]:
    client = await _client_for(db, user_id, provider)
    repos = await client.list_repos()
    return [
        RemoteRepoRead(
            full_name=r.full_name,
            default_branch=r.default_branch,
            clone_url=r.clone_url,
            description=r.description,
            is_private=r.is_private,
        )
        for r in repos
    ]


@router.post(
    "/{provider}/repos",
    response_model=ProjectRead | RemoteRepoRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_remote_repo(
    provider: str,
    payload: RemoteRepoCreate,
    user_id: CurrentUserId,
    db: DbDep,
) -> ProjectRead | RemoteRepoRead:
    """Crée un nouveau repo côté provider et, optionnellement, le clone en projet."""
    client = await _client_for(db, user_id, provider)
    repo = await client.create_repo(
        payload.name,
        private=payload.private,
        description=payload.description,
    )

    if not payload.create_project:
        return RemoteRepoRead(
            full_name=repo.full_name,
            default_branch=repo.default_branch,
            clone_url=repo.clone_url,
            description=repo.description,
            is_private=repo.is_private,
        )

    project = await project_service.create_from_repo(
        db,
        user_id=user_id,
        provider=provider,
        repo_full_name=repo.full_name,
    )
    await db.commit()
    return ProjectRead.model_validate(project)
