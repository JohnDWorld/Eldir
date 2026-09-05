"""Tests des opérations Git du SessionService (chantier 5).

On instancie un VRAI repo git local (tmp_path) pour valider commit/push.
Le push se fait sur un faux remote local (file:// bare repo).
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock

import pytest
from app.core.exceptions import AuthenticationError, WorkspaceError
from app.db.models import Project, Session, User
from app.schemas.git_credential import GitCredentialCreate
from app.services import session_service as svc_module
from app.services.git_credential_service import git_credential_service
from app.services.git_providers.base import PullRequestRef
from app.services.session_manager import SessionManager
from app.services.session_service import SessionService
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker


async def _run(cmd: list[str], cwd: Path) -> str:
    process = await asyncio.create_subprocess_exec(
        *cmd,
        cwd=str(cwd),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await process.communicate()
    if process.returncode != 0:
        raise RuntimeError(stderr.decode())
    return stdout.decode().strip()


@pytest.fixture
async def admin(db_session: AsyncSession) -> User:
    user = User(
        email="admin@example.com",
        hashed_password="x",
        display_name="Admin",
        is_active=True,
        is_admin=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.fixture
async def repo_pair(tmp_path: Path) -> tuple[Path, Path]:
    """Crée un bare repo `remote.git` + un clone local avec branche `feat/x`."""
    remote = tmp_path / "remote.git"
    remote.mkdir()
    await _run(["git", "init", "--bare", "--initial-branch=main"], cwd=remote)

    work = tmp_path / "work"
    await _run(["git", "clone", str(remote), str(work)], cwd=tmp_path)
    await _run(["git", "config", "user.email", "x@y"], cwd=work)
    await _run(["git", "config", "user.name", "x"], cwd=work)
    # Premier commit pour avoir un HEAD sur main.
    (work / "README.md").write_text("hello")
    await _run(["git", "add", "-A"], cwd=work)
    await _run(["git", "commit", "-m", "init"], cwd=work)
    await _run(["git", "push", "-u", "origin", "main"], cwd=work)
    # Crée une branche de session
    await _run(["git", "checkout", "-b", "feat/eldir"], cwd=work)
    return remote, work


@pytest.fixture
async def project_session(
    db_session: AsyncSession, admin: User, repo_pair: tuple[Path, Path]
) -> tuple[Project, Session]:
    _, work = repo_pair
    project = Project(
        user_id=admin.id,
        name="repo",
        slug="repo",
        provider="github",
        repo_full_name="owner/repo",
        default_branch="main",
        workspace_path=str(work),
    )
    db_session.add(project)
    await db_session.flush()
    session = Session(
        project_id=project.id,
        user_id=admin.id,
        branch="feat/eldir",
        worktree_path=str(work),
        state="idle",
    )
    db_session.add(session)
    await db_session.commit()
    await db_session.refresh(session)
    return project, session


@pytest.fixture
def service(
    session_factory: async_sessionmaker[AsyncSession],
) -> SessionService:
    bus = AsyncMock()
    manager = SessionManager(event_bus=bus)
    svc = SessionService(manager=manager)
    svc.attach_session_factory(session_factory)
    return svc


# ── tests ────────────────────────────────────────────────────────


async def test_git_status_clean(
    db_session: AsyncSession,
    admin: User,
    project_session: tuple[Project, Session],
    service: SessionService,
) -> None:
    _, session = project_session
    status = await service.git_status(db_session, user_id=admin.id, session_id=session.id)
    assert status["has_changes"] is False
    assert status["branch"] == "feat/eldir"


async def test_git_status_with_changes(
    db_session: AsyncSession,
    admin: User,
    project_session: tuple[Project, Session],
    service: SessionService,
) -> None:
    _, session = project_session
    Path(session.worktree_path).joinpath("new.txt").write_text("hi")  # type: ignore[arg-type]
    status = await service.git_status(db_session, user_id=admin.id, session_id=session.id)
    assert status["has_changes"] is True
    assert status["untracked"] == 1


async def test_commit_without_push(
    db_session: AsyncSession,
    admin: User,
    project_session: tuple[Project, Session],
    service: SessionService,
) -> None:
    _, session = project_session
    Path(session.worktree_path).joinpath("foo.py").write_text("x = 1")  # type: ignore[arg-type]

    result = await service.commit_push(
        db_session,
        user_id=admin.id,
        session_id=session.id,
        message="add foo",
        push=False,
    )
    assert result.pushed is False
    assert len(result.sha) >= 7
    assert result.branch == "feat/eldir"


async def test_commit_push_requires_credential(
    db_session: AsyncSession,
    admin: User,
    project_session: tuple[Project, Session],
    service: SessionService,
) -> None:
    _, session = project_session
    Path(session.worktree_path).joinpath("bar.py").write_text("y = 2")  # type: ignore[arg-type]

    with pytest.raises(AuthenticationError):
        await service.commit_push(
            db_session,
            user_id=admin.id,
            session_id=session.id,
            message="add bar",
            push=True,
        )


async def test_commit_push_happy_path(
    db_session: AsyncSession,
    admin: User,
    project_session: tuple[Project, Session],
    service: SessionService,
    repo_pair: tuple[Path, Path],
) -> None:
    _, session = project_session
    # PAT (le push local n'en a pas besoin mais le code l'exige).
    await git_credential_service.upsert(
        db_session,
        admin.id,
        GitCredentialCreate(provider="github", token="ghp_local_test"),
    )
    await db_session.commit()

    Path(session.worktree_path).joinpath("baz.py").write_text("z = 3")  # type: ignore[arg-type]

    result = await service.commit_push(
        db_session,
        user_id=admin.id,
        session_id=session.id,
        message="add baz",
        push=True,
    )
    assert result.pushed is True
    # Vérifie que le commit est bien dans le remote (bare).
    remote = repo_pair[0]
    branches = await _run(["git", "branch"], cwd=remote)
    assert "feat/eldir" in branches


async def test_commit_nothing_to_commit_raises(
    db_session: AsyncSession,
    admin: User,
    project_session: tuple[Project, Session],
    service: SessionService,
) -> None:
    _, session = project_session
    with pytest.raises(WorkspaceError):
        await service.commit_push(
            db_session,
            user_id=admin.id,
            session_id=session.id,
            message="empty",
            push=False,
        )


async def test_open_pr_calls_provider(
    db_session: AsyncSession,
    admin: User,
    project_session: tuple[Project, Session],
    service: SessionService,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, session = project_session
    await git_credential_service.upsert(
        db_session,
        admin.id,
        GitCredentialCreate(provider="github", token="ghp_local_test"),
    )
    await db_session.commit()
    Path(session.worktree_path).joinpath("pr.py").write_text("a = 1")  # type: ignore[arg-type]

    captured: dict[str, Any] = {}

    class _FakeProvider:
        name = "github"

        async def create_pr(
            self,
            full_name: str,
            *,
            head: str,
            base: str,
            title: str,
            body: str | None = None,
        ) -> PullRequestRef:
            captured.update(full_name=full_name, head=head, base=base, title=title, body=body)
            return PullRequestRef(
                number=42,
                url="https://github.com/owner/repo/pull/42",
                head=head,
                base=base,
                title=title,
            )

    monkeypatch.setattr(svc_module, "make_provider", lambda *a, **kw: _FakeProvider())

    pr = await service.open_pull_request(
        db_session,
        user_id=admin.id,
        session_id=session.id,
        title="Add pr",
        body="body",
    )
    assert pr.pr_number == 42
    assert captured["head"] == "feat/eldir"
    assert captured["base"] == "main"
    assert captured["title"] == "Add pr"


async def test_open_pr_same_branch_as_base_fails(
    db_session: AsyncSession,
    admin: User,
    project_session: tuple[Project, Session],
    service: SessionService,
    repo_pair: tuple[Path, Path],
) -> None:
    _, session = project_session
    # On revient sur main pour que head==base.
    await _run(["git", "checkout", "main"], cwd=Path(session.worktree_path))  # type: ignore[arg-type]

    await git_credential_service.upsert(
        db_session,
        admin.id,
        GitCredentialCreate(provider="github", token="ghp_local_test"),
    )
    await db_session.commit()

    with pytest.raises(WorkspaceError):
        await service.open_pull_request(
            db_session,
            user_id=admin.id,
            session_id=session.id,
            title="oops",
        )
