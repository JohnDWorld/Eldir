"""Tests unitaires de ClaudeCredentialService."""

from __future__ import annotations

import pytest
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import User
from app.schemas.claude_credential import ClaudeCredentialCreate
from app.services.claude_credential_service import (
    claude_credential_service,
    mask_value,
)


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


def test_mask_short_value() -> None:
    assert mask_value("abcd") == "…"
    assert mask_value("abc") == "…"


def test_mask_long_value() -> None:
    assert mask_value("sk-ant-oat01-supersecret-XYZ9") == "…XYZ9"
    assert mask_value("0123456789") == "…6789"


async def test_create_and_resolve_oauth_priority(
    db_session: AsyncSession, admin: User
) -> None:
    await claude_credential_service.create(
        db_session,
        admin.id,
        ClaudeCredentialCreate(kind="api_key", value="sk-api-aaaaaaaa", label="console"),
    )
    await claude_credential_service.create(
        db_session,
        admin.id,
        ClaudeCredentialCreate(
            kind="oauth_token", value="sk-ant-oat01-bbbbbbbb", label="pro"
        ),
    )
    await db_session.commit()

    resolved = await claude_credential_service.resolve_active(db_session, admin.id)
    assert resolved is not None
    assert resolved.kind == "oauth_token"
    assert resolved.env_var_name == "CLAUDE_CODE_OAUTH_TOKEN"
    assert resolved.value == "sk-ant-oat01-bbbbbbbb"


async def test_resolve_falls_back_to_api_key(
    db_session: AsyncSession, admin: User
) -> None:
    await claude_credential_service.create(
        db_session,
        admin.id,
        ClaudeCredentialCreate(kind="api_key", value="sk-api-fallback"),
    )
    await db_session.commit()

    resolved = await claude_credential_service.resolve_active(db_session, admin.id)
    assert resolved is not None
    assert resolved.kind == "api_key"
    assert resolved.env_var_name == "ANTHROPIC_API_KEY"
    assert resolved.value == "sk-api-fallback"


async def test_create_replaces_existing_same_kind(
    db_session: AsyncSession, admin: User
) -> None:
    first = await claude_credential_service.create(
        db_session,
        admin.id,
        ClaudeCredentialCreate(kind="oauth_token", value="sk-ant-oat01-OLD"),
    )
    second = await claude_credential_service.create(
        db_session,
        admin.id,
        ClaudeCredentialCreate(kind="oauth_token", value="sk-ant-oat01-NEW"),
    )
    await db_session.commit()

    creds = await claude_credential_service.list_for_user(db_session, admin.id)
    actives = [c for c in creds if c.is_active]
    assert len(actives) == 1
    assert actives[0].id == second.id
    assert first.id != second.id
    # L'ancien doit avoir été désactivé.
    inactives = [c for c in creds if not c.is_active]
    assert len(inactives) == 1
    assert inactives[0].id == first.id


async def test_resolve_returns_none_when_no_credentials(
    db_session: AsyncSession, admin: User
) -> None:
    resolved = await claude_credential_service.resolve_active(db_session, admin.id)
    assert resolved is None


def test_refuse_une_cle_api_rangee_en_token_oauth() -> None:
    """Se tromper de mode ne se voyait qu'au 401, en pleine session."""
    with pytest.raises(ValidationError):
        ClaudeCredentialCreate(kind="oauth_token", value="sk-ant-api03-abcdefgh")
    with pytest.raises(ValidationError):
        ClaudeCredentialCreate(kind="api_key", value="sk-ant-oat01-abcdefgh")


def test_accepte_un_prefixe_inconnu() -> None:
    """Le jour où Anthropic change de format, Eldir ne doit pas bloquer."""
    cred = ClaudeCredentialCreate(kind="oauth_token", value="sk-ant-futur-xyz  ")
    assert cred.value == "sk-ant-futur-xyz"
