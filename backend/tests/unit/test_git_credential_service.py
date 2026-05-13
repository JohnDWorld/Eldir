"""Tests GitCredentialService."""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import GitProviderError, NotFoundError
from app.db.models import User
from app.schemas.git_credential import GitCredentialCreate
from app.services.git_credential_service import git_credential_service


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


async def test_upsert_creates_then_replaces(
    db_session: AsyncSession, admin: User
) -> None:
    first = await git_credential_service.upsert(
        db_session,
        admin.id,
        GitCredentialCreate(provider="github", token="ghp_first_token_aaaaa"),
    )
    await db_session.commit()
    assert first.id

    second = await git_credential_service.upsert(
        db_session,
        admin.id,
        GitCredentialCreate(provider="github", token="ghp_second_token_bbbbb"),
    )
    await db_session.commit()

    creds = await git_credential_service.list_for_user(db_session, admin.id)
    assert len(creds) == 1
    assert creds[0].id == second.id

    plain = await git_credential_service.get_active_token(
        db_session, admin.id, "github"
    )
    assert plain == "ghp_second_token_bbbbb"


async def test_forgejo_requires_base_url(
    db_session: AsyncSession, admin: User
) -> None:
    with pytest.raises(GitProviderError):
        await git_credential_service.upsert(
            db_session,
            admin.id,
            GitCredentialCreate(provider="forgejo", token="fj_token_xxxxx"),
        )


async def test_delete_removes(db_session: AsyncSession, admin: User) -> None:
    cred = await git_credential_service.upsert(
        db_session,
        admin.id,
        GitCredentialCreate(provider="github", token="ghp_to_delete_token"),
    )
    await db_session.commit()
    await git_credential_service.delete(db_session, cred.id, admin.id)
    await db_session.commit()

    with pytest.raises(NotFoundError):
        await git_credential_service.get(db_session, cred.id, admin.id)
