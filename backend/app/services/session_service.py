"""SessionService — couche métier au-dessus du SessionManager.

- Crée le Session en DB
- Démarre la session SDK via SessionManager
- Persiste les events SDK (text / tool_use / tool_result / state / stop / error)
- Stoppe + persiste le state final
- Reprend une session via resume=sdk_session_id
- Opérations git : status, commit & push, open PR
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import get_settings
from app.core.constants import (
    EVENT_TYPE_STATE,
    EVENT_TYPE_TEXT,
    SESSION_STATES,
)
from app.core.exceptions import (
    AuthenticationError,
    GitProviderError,
    NotFoundError,
    SessionNotFoundError,
    WorkspaceError,
)
from app.core.logging import get_logger
from app.db.models import Project, Session, SessionEvent, User
from app.services.claude_credential_service import claude_credential_service
from app.services.git_credential_service import git_credential_service
from app.services.git_providers import make_provider
from app.services.session_manager import SessionManager
from app.services.worktree_service import worktree_service


@dataclass(slots=True, frozen=True)
class CommitPushResult:
    branch: str
    sha: str
    pushed: bool


@dataclass(slots=True, frozen=True)
class OpenPRResult:
    pr_number: int
    pr_url: str
    head: str
    base: str
    title: str

logger = get_logger(__name__)


class SessionService:
    def __init__(self, manager: SessionManager) -> None:
        self._manager = manager
        self._session_factory: async_sessionmaker[AsyncSession] | None = None

    def attach_session_factory(
        self, factory: async_sessionmaker[AsyncSession]
    ) -> None:
        """Le manager a besoin du factory pour persister depuis les callbacks hors-requête."""
        self._session_factory = factory
        self._manager.register_persist_callback(self._persist_event)

    async def list_for_user(
        self, db: AsyncSession, user_id: str
    ) -> list[Session]:
        result = await db.execute(
            select(Session)
            .where(Session.user_id == user_id)
            .order_by(Session.created_at.desc())
        )
        return list(result.scalars().all())

    async def get(self, db: AsyncSession, session_id: str, user_id: str) -> Session:
        result = await db.execute(
            select(Session).where(
                Session.id == session_id, Session.user_id == user_id
            )
        )
        session = result.scalar_one_or_none()
        if session is None:
            raise SessionNotFoundError(f"Session {session_id} introuvable.")
        return session

    async def list_events(
        self, db: AsyncSession, session_id: str, user_id: str
    ) -> list[SessionEvent]:
        await self.get(db, session_id, user_id)
        result = await db.execute(
            select(SessionEvent)
            .where(SessionEvent.session_id == session_id)
            .order_by(SessionEvent.created_at.asc())
        )
        return list(result.scalars().all())

    async def create_and_start(
        self,
        db: AsyncSession,
        *,
        user_id: str,
        project_id: str,
        system_prompt: str | None = None,
        model: str | None = None,
    ) -> Session:
        # 1. Récupère le projet pour avoir cwd / branche
        result = await db.execute(
            select(Project).where(
                Project.id == project_id, Project.user_id == user_id
            )
        )
        project = result.scalar_one_or_none()
        if project is None:
            raise NotFoundError(f"Projet {project_id} introuvable.")
        if not project.workspace_path:
            raise NotFoundError(
                f"Projet {project_id} n'a pas de workspace cloné."
            )

        # 2. Injecte les credentials Claude dans os.environ (V1 mono-user)
        await self._inject_claude_env(db, user_id)

        # 3. Crée la row Session
        session = Session(
            project_id=project_id,
            user_id=user_id,
            branch=project.default_branch,
            worktree_path=project.workspace_path,
            model=model or get_settings().claude_default_model,
            system_prompt=system_prompt,
        )
        db.add(session)
        await db.flush()

        # 4. Démarre le ClaudeSDKClient (via le manager)
        await self._manager.start(
            session_id=session.id,
            project_id=project.id,
            user_id=user_id,
            cwd=project.workspace_path,
            system_prompt=system_prompt,
            model=session.model,
        )
        return session

    async def resume(
        self,
        db: AsyncSession,
        *,
        user_id: str,
        session_id: str,
    ) -> Session:
        session = await self.get(db, session_id, user_id)
        if not session.sdk_session_id:
            raise NotFoundError(
                "Cette session n'a pas de sdk_session_id capturé — impossible de reprendre."
            )
        if self._manager.is_active(session_id):
            return session

        await self._inject_claude_env(db, user_id)

        await self._manager.start(
            session_id=session.id,
            project_id=session.project_id,
            user_id=user_id,
            cwd=session.worktree_path or "",
            system_prompt=session.system_prompt,
            model=session.model,
            resume_sdk_id=session.sdk_session_id,
        )
        return session

    async def send_message(
        self,
        db: AsyncSession,
        *,
        user_id: str,
        session_id: str,
        content: str,
    ) -> None:
        await self.get(db, session_id, user_id)
        if not self._manager.is_active(session_id):
            await self.resume(db, user_id=user_id, session_id=session_id)
        await self._manager.send_message(session_id, content)

    async def stop(
        self, db: AsyncSession, *, user_id: str, session_id: str
    ) -> None:
        await self.get(db, session_id, user_id)
        if self._manager.is_active(session_id):
            await self._manager.stop(session_id)

    # ── git ops (chantier 5) ─────────────────────────────────────
    async def git_status(
        self, db: AsyncSession, *, user_id: str, session_id: str
    ) -> dict[str, Any]:
        session = await self.get(db, session_id, user_id)
        repo_path = self._require_workspace(session)
        summary = await worktree_service.status_summary(repo_path)
        branch = await worktree_service.current_branch(repo_path)
        return {
            "branch": branch,
            "has_changes": sum(summary.values()) > 0,
            **summary,
        }

    async def commit_push(
        self,
        db: AsyncSession,
        *,
        user_id: str,
        session_id: str,
        message: str,
        push: bool = True,
    ) -> CommitPushResult:
        session = await self.get(db, session_id, user_id)
        project = await self._require_project(db, session)
        repo_path = self._require_workspace(session)

        # User identity pour le commit (author)
        user = await db.get(User, user_id)
        author_name = (user.display_name if user else None) or "Eldir"
        author_email = user.email if user else "eldir@local"

        sha = await worktree_service.commit_all(
            repo_path,
            message=message,
            author_name=author_name,
            author_email=author_email,
        )

        if not push:
            return CommitPushResult(
                branch=await worktree_service.current_branch(repo_path),
                sha=sha,
                pushed=False,
            )

        token = await git_credential_service.get_active_token(
            db, user_id, project.provider
        )
        if not token:
            raise AuthenticationError(
                f"Aucun credential {project.provider} configuré. Settings > Git."
            )

        branch = await worktree_service.current_branch(repo_path)
        await worktree_service.push(repo_path, branch=branch, token=token)
        logger.info(
            "session.commit_push", session_id=session_id, branch=branch, sha=sha
        )
        return CommitPushResult(branch=branch, sha=sha, pushed=True)

    async def open_pull_request(
        self,
        db: AsyncSession,
        *,
        user_id: str,
        session_id: str,
        title: str,
        body: str | None = None,
        base: str | None = None,
    ) -> OpenPRResult:
        session = await self.get(db, session_id, user_id)
        project = await self._require_project(db, session)
        repo_path = self._require_workspace(session)

        # 1. Commit s'il reste des changements, sinon on saute.
        if await worktree_service.has_changes(repo_path):
            user = await db.get(User, user_id)
            author_name = (user.display_name if user else None) or "Eldir"
            author_email = user.email if user else "eldir@local"
            await worktree_service.commit_all(
                repo_path,
                message=title,
                author_name=author_name,
                author_email=author_email,
            )

        # 2. Récupère le token et push la branche.
        token = await git_credential_service.get_active_token(
            db, user_id, project.provider
        )
        if not token:
            raise AuthenticationError(
                f"Aucun credential {project.provider} configuré. Settings > Git."
            )

        head_branch = await worktree_service.current_branch(repo_path)
        base_branch = base or project.default_branch
        if head_branch == base_branch:
            raise WorkspaceError(
                "Impossible d'ouvrir une PR : la branche courante == base."
            )
        await worktree_service.push(repo_path, branch=head_branch, token=token)

        # 3. Crée la PR via le provider.
        provider = make_provider(project.provider, token=token)
        try:
            pr = await provider.create_pr(
                project.repo_full_name,
                head=head_branch,
                base=base_branch,
                title=title,
                body=body,
            )
        except GitProviderError:
            raise

        logger.info(
            "session.pr.opened",
            session_id=session_id,
            pr_number=pr.number,
            url=pr.url,
        )
        return OpenPRResult(
            pr_number=pr.number,
            pr_url=pr.url,
            head=pr.head,
            base=pr.base,
            title=pr.title,
        )

    # ── helpers ──────────────────────────────────────────────────
    def _require_workspace(self, session: Session) -> Path:
        if not session.worktree_path:
            raise WorkspaceError(
                "La session n'a pas de worktree_path — état inconsistant."
            )
        return Path(session.worktree_path)

    async def _require_project(
        self, db: AsyncSession, session: Session
    ) -> Project:
        result = await db.execute(
            select(Project).where(Project.id == session.project_id)
        )
        project = result.scalar_one_or_none()
        if project is None:
            raise NotFoundError(
                f"Projet {session.project_id} introuvable pour cette session."
            )
        return project

    # ── internals ───────────────────────────────────────────────
    async def _inject_claude_env(self, db: AsyncSession, user_id: str) -> None:
        resolved = await claude_credential_service.resolve_active(db, user_id)
        if resolved is None:
            raise AuthenticationError(
                "Aucun credential Claude configuré. Settings > Claude."
            )
        # Set seulement la variable correspondante, pas les deux à la fois.
        # On nettoie les autres pour éviter qu'un ancien ANTHROPIC_API_KEY traîne.
        os.environ.pop("CLAUDE_CODE_OAUTH_TOKEN", None)
        os.environ.pop("ANTHROPIC_API_KEY", None)
        os.environ[resolved.env_var_name] = resolved.value
        logger.info(
            "session.claude.env.injected",
            user_id=user_id,
            kind=resolved.kind,
        )

    async def _persist_event(
        self, session_id: str, event_type: str, data: dict[str, Any]
    ) -> None:
        """Callback branché sur SessionManager → persiste l'event en DB."""
        if self._session_factory is None:
            return
        async with self._session_factory() as db:
            try:
                # Update state si applicable
                if event_type == EVENT_TYPE_STATE and isinstance(
                    data.get("state"), str
                ) and data["state"] in SESSION_STATES:
                    await db.execute(
                        update(Session)
                        .where(Session.id == session_id)
                        .values(state=data["state"])
                    )

                if event_type == EVENT_TYPE_STATE and "sdk_session_id" in data:
                    await db.execute(
                        update(Session)
                        .where(Session.id == session_id)
                        .values(sdk_session_id=data["sdk_session_id"])
                    )

                # Mise à jour du summary depuis le premier text
                if event_type == EVENT_TYPE_TEXT and isinstance(
                    data.get("text"), str
                ):
                    summary = data["text"][:280]
                    await db.execute(
                        update(Session)
                        .where(
                            Session.id == session_id, Session.summary.is_(None)
                        )
                        .values(summary=summary)
                    )

                event = SessionEvent(
                    session_id=session_id,
                    type=event_type,
                    payload=data,
                )
                db.add(event)
                await db.commit()
            except Exception:  # noqa: BLE001
                await db.rollback()
                logger.exception("session.event.persist.error")
