"""Tests RepoWatcher - un repo cassé ne doit pas arrêter la surveillance."""

from __future__ import annotations

from typing import Any

import pytest
from app.db.models import Project, User
from app.services import repo_watcher as module
from app.services.repo_watcher import RepoWatcher
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker


@pytest.fixture
async def two_projects(db_session: AsyncSession) -> list[Project]:
    user = User(email="john@example.com", hashed_password="x")
    db_session.add(user)
    await db_session.flush()
    projects = [
        Project(
            user_id=user.id,
            name=name,
            slug=name,
            provider="github",
            repo_full_name=f"john/{name}",
            default_branch="main",
            workspace_path=f"/nonexistent/{name}",
        )
        for name in ("munin", "hugin")
    ]
    db_session.add_all(projects)
    await db_session.commit()
    return projects


async def test_sync_all_continue_apres_un_repo_casse(
    two_projects: list[Project],
    session_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: list[str] = []

    async def fake_sync(_db: Any, *, project_id: str, user_id: str) -> Any:
        seen.append(project_id)
        if project_id == two_projects[0].id:
            raise RuntimeError("token expiré")
        return type("Sync", (), {"fast_forwarded": True, "branch": "main"})()

    monkeypatch.setattr(module.project_service, "sync_with_remote", fake_sync)

    watcher = RepoWatcher(session_factory=session_factory, interval_seconds=60)
    updated = await watcher.sync_all()

    assert len(seen) == 2  # le second projet est traité malgré l'échec du premier
    assert updated == 1


async def test_start_ne_lance_rien_si_desactive(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    watcher = RepoWatcher(session_factory=session_factory, interval_seconds=0)
    watcher.start()
    assert watcher._task is None
    await watcher.stop()
