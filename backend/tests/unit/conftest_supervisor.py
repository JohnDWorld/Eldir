"""Doubles minimaux pour instancier SupervisorService hors runtime SDK.

Le superviseur prend un SessionManager et un SessionService réels, qui
démarrent des processus CLI. Un test unitaire de la résolution de cible n'a
pas besoin de ça : seul `create_and_start` est appelé.
"""

from __future__ import annotations

import asyncio
from typing import Any

from app.db.models import Project, User
from app.db.models import Session as SessionRow
from app.services.supervisor_service import SupervisorService
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker


class ManagerFactice:
    """Ne démarre aucun CLI : le test ne touche pas au SDK."""

    def register_persist_callback(self, _cb: Any) -> None:
        return None

    def is_active(self, _session_id: str) -> bool:
        return False


class ManagerEspion(ManagerFactice):
    """Une session déjà active, qui note ce qu'on lui envoie et sous quelle origine.

    Le test d'une consigne dispatchée traverse le vrai `_run_child` : seule la
    frontière du SDK, `send_message`, est remplacée, et c'est là que `origin` se lit.
    """

    def __init__(self) -> None:
        self.recus: list[tuple[str, str, str]] = []
        self.recu = asyncio.Event()

    def is_active(self, _session_id: str) -> bool:
        return True

    async def send_message(self, session_id: str, content: str, *, origin: str) -> None:
        self.recus.append((session_id, content, origin))
        self.recu.set()


class SessionsFactice:
    """Crée la ligne de session, sans worktree ni client SDK."""

    def __init__(self, factory: async_sessionmaker[AsyncSession]) -> None:
        self._factory = factory

    async def get(self, _db: AsyncSession, _session_id: str, _user_id: str) -> None:
        return None

    async def create_and_start(
        self, db: AsyncSession, *, user_id: str, project_id: str
    ) -> SessionRow:
        row = SessionRow(
            project_id=project_id,
            user_id=user_id,
            branch="claude/deux",
            worktree_path="/tmp/munin-wt2",
            model="claude-sonnet-5",
        )
        db.add(row)
        await db.flush()
        return row


def service_superviseur(
    factory: async_sessionmaker[AsyncSession], manager: ManagerFactice | None = None
) -> SupervisorService:
    return SupervisorService(
        manager=manager or ManagerFactice(),  # type: ignore[arg-type]
        sessions=SessionsFactice(factory),  # type: ignore[arg-type]
        session_factory=factory,
    )


async def pose_projet_et_session(db: AsyncSession) -> tuple[str, str, str]:
    """Pose un utilisateur, un projet et une session déjà démarrée.

    Rend (user_id, project_id, session_id). La session porte un
    `sdk_session_id` : sans lui, `_resolve_target` la considère comme jamais
    démarrée et en ouvre une neuve, ce qui masquerait le cas qu'on teste.
    """
    user = User(email="jarl@exemple.lan", hashed_password="x")
    db.add(user)
    await db.flush()
    projet = Project(
        user_id=user.id,
        name="Munin",
        slug="munin",
        provider="github",
        repo_full_name="exemple/munin",
        default_branch="main",
        workspace_path="/tmp/munin",
    )
    db.add(projet)
    await db.flush()
    session = SessionRow(
        project_id=projet.id,
        user_id=user.id,
        branch="claude/un",
        worktree_path="/tmp/munin-wt1",
        model="claude-sonnet-5",
        sdk_session_id="sdk-1",
    )
    db.add(session)
    await db.commit()
    return user.id, projet.id, session.id
