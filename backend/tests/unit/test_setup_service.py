"""Tests unitaires de SetupService."""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AuthenticationError, ConflictError
from app.schemas.setup import BootstrapClaudeCredentialIn, BootstrapRequest
from app.services.setup_service import setup_service


async def test_needs_bootstrap_when_empty(db_session: AsyncSession) -> None:
    assert await setup_service.needs_bootstrap(db_session) is True


async def test_ensure_bootstrap_token_returns_clear_token(
    db_session: AsyncSession,
) -> None:
    token = await setup_service.ensure_bootstrap_token(db_session)
    await db_session.commit()
    assert token is not None
    assert len(token) >= 32

    # Hashé en DB, jamais le clair.
    state = await setup_service.get_or_create_state(db_session)
    assert state.bootstrap_token_hash is not None
    assert state.bootstrap_token_hash != token


async def test_perform_bootstrap_creates_admin_and_completes(
    db_session: AsyncSession,
) -> None:
    token = await setup_service.ensure_bootstrap_token(db_session)
    await db_session.commit()
    assert token is not None

    payload = BootstrapRequest(
        bootstrap_token=token,
        admin_email="admin@example.com",
        admin_password="superpassword123",
        admin_display_name="Admin",
        claude_credentials=[
            BootstrapClaudeCredentialIn(
                kind="oauth_token", value="sk-ant-oat01-test", label="pro"
            )
        ],
    )
    user = await setup_service.perform_bootstrap(db_session, payload)
    await db_session.commit()

    assert user.email == "admin@example.com"
    assert user.is_admin is True
    assert await setup_service.needs_bootstrap(db_session) is False

    state = await setup_service.get_or_create_state(db_session)
    assert state.bootstrap_completed is True
    assert state.bootstrap_token_hash is None


async def test_bootstrap_rejects_invalid_token(db_session: AsyncSession) -> None:
    await setup_service.ensure_bootstrap_token(db_session)
    await db_session.commit()

    payload = BootstrapRequest(
        bootstrap_token="wrong-token-wrong-token-wrong",
        admin_email="other@example.com",
        admin_password="passwordlong",
    )
    with pytest.raises(AuthenticationError):
        await setup_service.perform_bootstrap(db_session, payload)


async def test_bootstrap_twice_fails(db_session: AsyncSession) -> None:
    token = await setup_service.ensure_bootstrap_token(db_session)
    await db_session.commit()
    assert token is not None

    payload = BootstrapRequest(
        bootstrap_token=token,
        admin_email="admin@example.com",
        admin_password="superpassword123",
    )
    await setup_service.perform_bootstrap(db_session, payload)
    await db_session.commit()

    with pytest.raises(ConflictError):
        await setup_service.perform_bootstrap(db_session, payload)
