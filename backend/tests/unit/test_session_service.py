"""Tests SessionService — flux create / persist / stop avec manager mocké."""

from __future__ import annotations

import os
from typing import Any
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.exceptions import AuthenticationError, NotFoundError
from app.db.models import Project, Session, User
from app.schemas.claude_credential import ClaudeCredentialCreate
from app.services.claude_credential_service import claude_credential_service
from app.services.session_manager import SessionManager
from app.services.session_service import SessionService


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


@pytest.fixture
async def project(db_session: AsyncSession, admin: User, tmp_path) -> Project:
    p = Project(
        user_id=admin.id,
        name="repo",
        slug="repo",
        provider="github",
        repo_full_name="owner/repo",
        default_branch="main",
        workspace_path=str(tmp_path),
    )
    db_session.add(p)
    await db_session.commit()
    await db_session.refresh(p)
    return p


class _FakeManager(SessionManager):
    """SessionManager qui n'instancie pas de vrai SDK client."""

    async def start(self, **kwargs: Any) -> Any:  # type: ignore[override]
        session_id = kwargs["session_id"]
        # On simule juste l'enregistrement.
        self._sessions[session_id] = type("Active", (), {"session_id": session_id})()  # type: ignore[misc]
        return self._sessions[session_id]

    async def send_message(self, session_id: str, content: str) -> None:  # type: ignore[override]
        self.last_message = (session_id, content)

    async def stop(self, session_id: str) -> None:  # type: ignore[override]
        self._sessions.pop(session_id, None)


@pytest.fixture
def service(
    session_factory: async_sessionmaker[AsyncSession],
) -> SessionService:
    bus = AsyncMock()
    bus.publish = AsyncMock()
    manager = _FakeManager(event_bus=bus)
    svc = SessionService(manager=manager)
    svc.attach_session_factory(session_factory)
    return svc


async def test_create_requires_claude_credential(
    db_session: AsyncSession,
    admin: User,
    project: Project,
    service: SessionService,
) -> None:
    with pytest.raises(AuthenticationError):
        await service.create_and_start(
            db_session,
            user_id=admin.id,
            project_id=project.id,
        )


async def test_create_session_happy_path(
    db_session: AsyncSession,
    admin: User,
    project: Project,
    service: SessionService,
) -> None:
    await claude_credential_service.create(
        db_session,
        admin.id,
        ClaudeCredentialCreate(kind="oauth_token", value="sk-ant-oat01-test"),
    )
    await db_session.commit()

    session = await service.create_and_start(
        db_session,
        user_id=admin.id,
        project_id=project.id,
    )
    await db_session.commit()

    assert session.id
    assert session.project_id == project.id
    assert session.branch == "main"
    assert os.environ.get("CLAUDE_CODE_OAUTH_TOKEN") == "sk-ant-oat01-test"


async def test_create_unknown_project_raises(
    db_session: AsyncSession,
    admin: User,
    service: SessionService,
) -> None:
    with pytest.raises(NotFoundError):
        await service.create_and_start(
            db_session,
            user_id=admin.id,
            project_id="missing",
        )


async def test_send_message_starts_if_not_active(
    db_session: AsyncSession,
    admin: User,
    project: Project,
    service: SessionService,
) -> None:
    await claude_credential_service.create(
        db_session,
        admin.id,
        ClaudeCredentialCreate(kind="oauth_token", value="sk-ant-oat01-test"),
    )
    await db_session.commit()

    session = await service.create_and_start(
        db_session, user_id=admin.id, project_id=project.id
    )
    session.sdk_session_id = "sdk-xyz"
    await db_session.commit()

    await service.stop(db_session, user_id=admin.id, session_id=session.id)
    # send_message doit déclencher resume() puis send_message du manager.
    await service.send_message(
        db_session,
        user_id=admin.id,
        session_id=session.id,
        content="hello",
    )
    assert service._manager.is_active(session.id) is True  # noqa: SLF001
