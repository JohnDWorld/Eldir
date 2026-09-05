"""Tests SessionService - flux create / persist / stop avec manager mocké."""

from __future__ import annotations

import asyncio
import os
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock

import pytest
from app.core.exceptions import AuthenticationError, NotFoundError
from app.db.models import Project, Session, User
from app.schemas.claude_credential import ClaudeCredentialCreate
from app.services.claude_credential_service import claude_credential_service
from app.services.session_manager import SessionManager
from app.services.session_service import SessionService
from app.services.worktree_service import worktree_service
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker


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


async def _git(args: list[str], cwd: Path) -> None:
    process = await asyncio.create_subprocess_exec(
        "git",
        *args,
        cwd=str(cwd),
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await process.communicate()
    if process.returncode != 0:
        raise RuntimeError(stderr.decode())


@pytest.fixture(autouse=True)
def workspaces_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Les worktrees de session sont créés sous la racine du WorktreeService.

    Le service est un singleton instancié à l'import : on patche son attribut
    plutôt que l'env, qui a déjà été lu.
    """
    root = tmp_path / "workspaces"
    monkeypatch.setattr(worktree_service, "_root", root)
    return root


@pytest.fixture
async def repo(tmp_path: Path) -> Path:
    """Un vrai repo git : `create_and_start` crée un worktree dessus."""
    work = tmp_path / "repo"
    work.mkdir()
    await _git(["init", "--initial-branch=main"], cwd=work)
    await _git(["config", "user.email", "x@y"], cwd=work)
    await _git(["config", "user.name", "x"], cwd=work)
    (work / "README.md").write_text("hello")
    await _git(["add", "-A"], cwd=work)
    await _git(["commit", "-m", "init"], cwd=work)
    return work


@pytest.fixture
async def project(db_session: AsyncSession, admin: User, repo: Path) -> Project:
    p = Project(
        user_id=admin.id,
        name="repo",
        slug="repo",
        provider="github",
        repo_full_name="owner/repo",
        default_branch="main",
        workspace_path=str(repo),
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
    # Une session vit sur son propre worktree / sa propre branche.
    assert session.branch == f"claude/{session.id}"
    assert session.worktree_path is not None
    assert session.worktree_path != project.workspace_path
    # Le protocole enfant est collé au system prompt et persisté sur la row.
    assert session.system_prompt is not None
    assert "<cr>" in session.system_prompt
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

    session = await service.create_and_start(db_session, user_id=admin.id, project_id=project.id)
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
    assert service._manager.is_active(session.id) is True


async def test_resume_repart_de_zero_si_le_transcript_a_disparu(
    db_session: AsyncSession,
    admin: User,
    project: Project,
    service: SessionService,
) -> None:
    """Une image reconstruite efface les transcripts du CLI.

    Sans filet, `resume` échoue et la session devient inutilisable. On
    accepte de perdre le contexte côté SDK (l'historique reste en base)
    plutôt que de rendre la session morte.
    """
    session = Session(
        project_id=project.id,
        user_id=admin.id,
        branch="claude/x",
        worktree_path=str(project.workspace_path),
        sdk_session_id="transcript-disparu",
    )
    db_session.add(session)
    await claude_credential_service.create(
        db_session,
        admin.id,
        ClaudeCredentialCreate(kind="oauth_token", value="sk-ant-oat01-test"),
    )
    await db_session.commit()

    calls: list[str | None] = []
    manager = service._manager
    original_start = manager.start

    async def flaky_start(**kwargs: Any) -> Any:
        calls.append(kwargs.get("resume_sdk_id"))
        if kwargs.get("resume_sdk_id") is not None:
            raise RuntimeError("No conversation found with session ID")
        return await original_start(**kwargs)

    manager.start = flaky_start  # type: ignore[method-assign]
    try:
        await service.resume(db_session, user_id=admin.id, session_id=session.id)
    finally:
        manager.start = original_start  # type: ignore[method-assign]

    assert calls == ["transcript-disparu", None]
    assert session.sdk_session_id is None
