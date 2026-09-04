"""Tests SupervisorService - session sans projet, préférences, ping de fin de tour."""

from __future__ import annotations

import asyncio
from typing import Any

import pytest
from app.core.config import get_settings
from app.db.models import Project, Session, User
from app.schemas.claude_credential import ClaudeCredentialCreate
from app.services.claude_credential_service import claude_credential_service
from app.services.event_bus import EventBus
from app.services.session_manager import SessionManager
from app.services.session_service import SessionService
from app.services.supervisor_service import SUPERVISOR_KIND, SupervisorService
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker


@pytest.fixture(autouse=True)
def workspaces_root(tmp_path, monkeypatch) -> Any:
    """Le superviseur crée son cwd : on le sort de /var/eldir pour les tests."""
    monkeypatch.setenv("WORKSPACES_ROOT", str(tmp_path))
    get_settings.cache_clear()
    yield tmp_path
    get_settings.cache_clear()


@pytest.fixture
async def admin(db_session: AsyncSession) -> User:
    user = User(email="john@example.com", hashed_password="x", is_admin=True)
    db_session.add(user)
    await db_session.commit()
    await claude_credential_service.create(
        db_session,
        user.id,
        ClaudeCredentialCreate(kind="oauth_token", value="sk-ant-oat01-test"),
    )
    await db_session.commit()
    await db_session.refresh(user)
    return user


class _FakeManager(SessionManager):
    """Manager sans SDK : mémorise les démarrages et les messages envoyés."""

    def __init__(self) -> None:
        super().__init__(event_bus=EventBus(redis=None))  # type: ignore[arg-type]
        self.started: list[dict[str, Any]] = []
        self.sent: list[tuple[str, str]] = []

    async def start(self, **kwargs: Any) -> Any:  # type: ignore[override]
        self.started.append(kwargs)
        session_id = kwargs["session_id"]
        self._sessions[session_id] = type("Active", (), {"session_id": session_id})()  # type: ignore[misc]
        return self._sessions[session_id]

    async def send_message(self, session_id: str, content: str) -> None:  # type: ignore[override]
        self.sent.append((session_id, content))


@pytest.fixture
def supervisor(
    session_factory: async_sessionmaker[AsyncSession],
) -> SupervisorService:
    manager = _FakeManager()
    return SupervisorService(
        manager=manager,
        sessions=SessionService(manager=manager),
        session_factory=session_factory,
    )


async def test_ensure_session_cree_une_session_sans_projet(
    db_session: AsyncSession, admin: User, supervisor: SupervisorService
) -> None:
    row = await supervisor.ensure_session(db_session, admin.id)
    await db_session.commit()

    assert row.project_id is None
    assert row.is_system is True
    assert row.system_kind == SUPERVISOR_KIND
    # Les 4 outils Eldir et rien d'autre : pas de Bash, pas de Read.
    started = supervisor._manager.started[0]  # type: ignore[attr-defined]
    assert started["allowed_tools"] == [
        "mcp__eldir__list_projects",
        "mcp__eldir__list_sessions",
        "mcp__eldir__dispatch",
        "mcp__eldir__remember",
    ]
    assert "eldir" in started["mcp_servers"]
    assert "Bash" in started["disallowed_tools"]


async def test_ensure_session_est_idempotente(
    db_session: AsyncSession, admin: User, supervisor: SupervisorService
) -> None:
    first = await supervisor.ensure_session(db_session, admin.id)
    await db_session.commit()
    second = await supervisor.ensure_session(db_session, admin.id)
    assert first.id == second.id
    assert len(supervisor._manager.started) == 1  # type: ignore[attr-defined]


async def test_remember_preference_ecrit_et_dedoublonne(
    supervisor: SupervisorService,
) -> None:
    assert "Noté" in await supervisor.remember_preference("Toujours une PR.")
    again = await supervisor.remember_preference("Toujours une PR.")
    assert again == "Préférence déjà enregistrée."
    assert await supervisor.remember_preference("  ") == "Erreur : 'fait' est vide."

    async with supervisor._factory() as db:  # type: ignore[attr-defined]
        prompt = await supervisor._build_prompt(db)  # type: ignore[attr-defined]
    assert "- Toujours une PR." in prompt


async def test_ping_uniquement_pour_les_sessions_dispatchees(
    db_session: AsyncSession, admin: User, supervisor: SupervisorService
) -> None:
    project = Project(
        user_id=admin.id,
        name="munin",
        slug="munin",
        provider="github",
        repo_full_name="john/munin",
        default_branch="main",
        workspace_path="/nonexistent/munin",
    )
    db_session.add(project)
    await db_session.flush()
    child = Session(
        project_id=project.id,
        user_id=admin.id,
        branch="claude/x",
        summary="FAIT: ajout de la compétence\nPRET: oui",
    )
    db_session.add(child)
    await db_session.commit()

    manager = supervisor._manager  # type: ignore[attr-defined]

    # Une session que le superviseur n'a pas dispatchée ne le réveille pas.
    await supervisor._on_event(child.id, "stop", {})  # type: ignore[attr-defined]
    await asyncio.sleep(0.05)
    assert manager.sent == []

    # Dispatchée : le superviseur est démarré et reçoit le compte rendu.
    supervisor._pending.add(child.id)  # type: ignore[attr-defined]
    await supervisor._on_event(child.id, "stop", {})  # type: ignore[attr-defined]
    for _ in range(40):
        await asyncio.sleep(0.05)
        if manager.sent:
            break
    assert len(manager.sent) == 1
    _, content = manager.sent[0]
    assert "munin" in content
    assert "FAIT: ajout de la compétence" in content
