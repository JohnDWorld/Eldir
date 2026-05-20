"""Tests ProjectService - mocks GitHub + clone."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AuthenticationError, ConflictError
from app.db.models import User
from app.schemas.git_credential import GitCredentialCreate
from app.services import project_service as project_service_module
from app.services.git_credential_service import git_credential_service
from app.services.git_providers.base import RepoRef
from app.services.project_service import project_service
from app.services.worktree_service import CloneResult


@pytest.fixture
async def admin(db_session: AsyncSession) -> User:
    user = User(
        email="admin@example.com",
        hashed_password="x",
        is_active=True,
        is_admin=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


class _FakeGitHubProvider:
    """Stub minimal qui répond à get_repo."""

    name = "github"

    def __init__(self, *_: Any, **__: Any) -> None:
        pass

    async def get_repo(self, full_name: str) -> RepoRef:
        return RepoRef(
            full_name=full_name,
            default_branch="main",
            clone_url=f"https://github.com/{full_name}.git",
            description="stub",
            is_private=False,
        )


@pytest.fixture
def patch_provider_and_clone(monkeypatch, tmp_path: Path):  # type: ignore[no-untyped-def]
    """Patch make_provider et worktree_service.clone_repo pour les tests."""
    monkeypatch.setattr(
        project_service_module,
        "make_provider",
        lambda *args, **kwargs: _FakeGitHubProvider(),
    )

    async def _fake_clone(*, user_id: str, repo_full_name: str, **_: Any) -> CloneResult:
        slug = repo_full_name.split("/")[-1].lower()
        path = tmp_path / user_id / slug
        path.mkdir(parents=True, exist_ok=True)
        return CloneResult(path=path, default_branch="main", repo_slug=slug)

    monkeypatch.setattr(
        project_service_module.worktree_service, "clone_repo", _fake_clone
    )


async def test_create_from_repo_requires_credential(
    db_session: AsyncSession, admin: User, patch_provider_and_clone: None
) -> None:
    with pytest.raises(AuthenticationError):
        await project_service.create_from_repo(
            db_session,
            user_id=admin.id,
            provider="github",
            repo_full_name="owner/repo",
        )


async def test_create_from_repo_happy_path(
    db_session: AsyncSession, admin: User, patch_provider_and_clone: None
) -> None:
    await git_credential_service.upsert(
        db_session,
        admin.id,
        GitCredentialCreate(provider="github", token="ghp_clone_token_aaa"),
    )
    await db_session.commit()

    project = await project_service.create_from_repo(
        db_session,
        user_id=admin.id,
        provider="github",
        repo_full_name="owner/my-repo",
    )
    await db_session.commit()

    assert project.id
    assert project.slug == "my-repo"
    assert project.provider == "github"
    assert project.repo_full_name == "owner/my-repo"
    assert project.workspace_path is not None


async def test_create_from_repo_rejects_duplicate(
    db_session: AsyncSession, admin: User, patch_provider_and_clone: None
) -> None:
    await git_credential_service.upsert(
        db_session,
        admin.id,
        GitCredentialCreate(provider="github", token="ghp_dup_token_aaa"),
    )
    await db_session.commit()

    await project_service.create_from_repo(
        db_session,
        user_id=admin.id,
        provider="github",
        repo_full_name="owner/repo",
    )
    await db_session.commit()

    with pytest.raises(ConflictError):
        await project_service.create_from_repo(
            db_session,
            user_id=admin.id,
            provider="github",
            repo_full_name="owner/repo",
        )
