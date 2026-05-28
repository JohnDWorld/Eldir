"""SessionService - couche métier au-dessus du SessionManager.

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
    EVENT_TYPE_USAGE,
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
from app.services.cost_service import cost_service
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

        repo_path = Path(project.workspace_path)

        # 2. Injecte les credentials Claude dans os.environ (V1 mono-user)
        await self._inject_claude_env(db, user_id)

        # 2bis. Best-effort : fetch + fast-forward pour partir d'une base à jour.
        # On ne bloque jamais une session si la sync échoue (pas de réseau,
        # token rotaté, etc.). Le résultat est loggé pour debug.
        try:
            from app.services.project_service import project_service

            sync_result = await project_service.sync_with_remote(
                db, project_id=project_id, user_id=user_id
            )
            if sync_result.message:
                logger.info(
                    "session.create.sync.note",
                    project_id=project_id,
                    message=sync_result.message,
                )
        except Exception:  # noqa: BLE001
            logger.exception(
                "session.create.sync.failed", project_id=project_id
            )

        # 2ter. Charge le MissionTemplate du projet (Phase 4) pour ses
        # défauts : system_prompt, model, allowed_tools. Les valeurs
        # explicites passées en argument restent prioritaires.
        from app.services.mission_template_service import (
            mission_template_service,
        )

        template = await mission_template_service.get(
            db, project_id=project_id, user_id=user_id
        )
        effective_system_prompt = system_prompt or (
            template.system_prompt if template else None
        )
        effective_model = (
            model
            or (template.model if template else None)
            or get_settings().claude_default_model
        )
        effective_allowed_tools = (
            template.allowed_tools if template and template.allowed_tools else None
        )

        # 3. Crée la row Session (avec worktree_path provisoire - on le mettra
        # à jour après création du worktree git).
        session = Session(
            project_id=project_id,
            user_id=user_id,
            branch=project.default_branch,
            worktree_path=project.workspace_path,
            model=effective_model,
            system_prompt=effective_system_prompt,
        )
        db.add(session)
        await db.flush()  # capture session.id pour nommer le worktree

        # 4. Crée un worktree git isolé pour cette session, partant de
        # `origin/{default_branch}` pour bénéficier du fetch fait en 2bis
        # même si le default branch local était sale.
        try:
            worktree_ref = await worktree_service.create_worktree(
                repo_path=repo_path,
                user_id=user_id,
                repo_slug=project.slug,
                session_id=session.id,
                base_branch=f"origin/{project.default_branch}",
            )
        except WorkspaceError:
            # Pas de remote origin/<branch> (repo fraîchement cloné sans push),
            # fallback sur le default_branch local.
            worktree_ref = await worktree_service.create_worktree(
                repo_path=repo_path,
                user_id=user_id,
                repo_slug=project.slug,
                session_id=session.id,
                base_branch=project.default_branch,
            )
        session.worktree_path = str(worktree_ref.path)
        session.branch = worktree_ref.branch
        await db.flush()

        # 4bis. Matérialise les skills et sub-agents du template dans le
        # worktree (`.claude/skills/` et `.claude/agents/`). Best-effort -
        # un I/O failure ne doit pas bloquer la session.
        # Si Ollama est configuré + joignable + toggle activé, on injecte
        # aussi le sub-agent système 'mask-data' (cf. Phase 6).
        extra_sub_agents = await self._build_extra_sub_agents(db)
        try:
            await mission_template_service.materialize_to_worktree(
                db,
                project_id=project_id,
                user_id=user_id,
                worktree_path=worktree_ref.path,
                extra_sub_agents=extra_sub_agents,
            )
        except Exception:  # noqa: BLE001
            logger.exception(
                "session.create.template.materialize.failed",
                session_id=session.id,
            )

        # 5. Démarre le ClaudeSDKClient sur le worktree. Si ça échoue, on
        # nettoie le worktree pour ne pas laisser de squelette orphelin sur
        # disque (la row DB sera rollbackée par get_db).
        try:
            await self._manager.start(
                session_id=session.id,
                project_id=project.id,
                user_id=user_id,
                cwd=str(worktree_ref.path),
                system_prompt=effective_system_prompt,
                model=session.model,
                allowed_tools=effective_allowed_tools,
            )
        except Exception:
            try:
                await worktree_service.remove_worktree(
                    repo_path, worktree_ref.path
                )
            except Exception:  # noqa: BLE001
                logger.exception(
                    "session.create.worktree.cleanup.failed",
                    session_id=session.id,
                )
            raise
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
                "Cette session n'a pas de sdk_session_id capturé - impossible de reprendre."
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

    async def delete(
        self, db: AsyncSession, *, user_id: str, session_id: str
    ) -> None:
        """Stoppe la session si active, supprime son worktree, puis la row DB.

        Les SessionEvent et SessionCost partent en cascade via la FK
        `ondelete=CASCADE`. Le worktree git n'est retiré que s'il diffère du
        clone canonique du projet (sécurité pour les sessions anciennes créées
        avant l'introduction des worktrees, qui pointaient sur le clone).
        """
        session = await self.get(db, session_id, user_id)
        if self._manager.is_active(session_id):
            try:
                await self._manager.stop(session_id)
            except Exception:  # noqa: BLE001
                logger.exception(
                    "session.delete.stop.failed", session_id=session_id
                )

        project = await db.get(Project, session.project_id)
        if (
            project is not None
            and project.workspace_path
            and session.worktree_path
            and session.worktree_path != project.workspace_path
        ):
            try:
                await worktree_service.remove_worktree(
                    Path(project.workspace_path), Path(session.worktree_path)
                )
            except Exception:  # noqa: BLE001
                logger.exception(
                    "session.delete.worktree.cleanup.failed",
                    session_id=session_id,
                    worktree=session.worktree_path,
                )

        await db.delete(session)

    # ── diff (chantier 5) ───────────────────────────────────────
    async def diff_summary(
        self, db: AsyncSession, *, user_id: str, session_id: str
    ) -> dict[str, Any]:
        session = await self.get(db, session_id, user_id)
        project = await self._require_project(db, session)
        repo_path = self._require_workspace(session)
        base_ref = await self._diff_base_ref(project, repo_path)
        files = await worktree_service.diff_summary(repo_path, base_ref=base_ref)
        head_branch = await worktree_service.current_branch(repo_path)
        return {
            "base_ref": base_ref,
            "head_branch": head_branch,
            "files": [
                {
                    "path": f.path,
                    "status": f.status,
                    "additions": f.additions,
                    "deletions": f.deletions,
                }
                for f in files
            ],
        }

    async def diff_file(
        self,
        db: AsyncSession,
        *,
        user_id: str,
        session_id: str,
        path: str,
    ) -> dict[str, Any]:
        session = await self.get(db, session_id, user_id)
        project = await self._require_project(db, session)
        repo_path = self._require_workspace(session)
        base_ref = await self._diff_base_ref(project, repo_path)
        patch = await worktree_service.diff_file(
            repo_path, base_ref=base_ref, path=path
        )
        return {"path": path, "base_ref": base_ref, "patch": patch}

    async def _diff_base_ref(self, project: Project, repo_path: Path) -> str:
        """Référence de base pour calculer le diff d'une session.

        Préfère le merge-base avec `origin/<default_branch>` pour montrer
        exactement ce que la session a ajouté (et ignorer les commits qui
        ont atterri sur main depuis). Fallback sur la branche locale puis
        sur HEAD~0 (= zéro diff) si rien d'autre.
        """
        upstream = f"origin/{project.default_branch}"
        mb = await worktree_service.merge_base(
            repo_path, a="HEAD", b=upstream
        )
        if mb:
            return mb
        mb_local = await worktree_service.merge_base(
            repo_path, a="HEAD", b=project.default_branch
        )
        if mb_local:
            return mb_local
        return project.default_branch

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
                "La session n'a pas de worktree_path - état inconsistant."
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
    async def _build_extra_sub_agents(
        self, db: AsyncSession
    ) -> list[Any]:
        """Calcule les sub-agents 'système' à injecter dans le worktree.

        Pour l'instant un seul cas : `mask-data` quand
            ollama_enabled AND ollama_reachable AND expose_to_sessions.
        Si l'une des trois conditions n'est pas remplie, renvoie [].
        Best-effort : si on n'arrive pas à pinger Ollama, on n'injecte pas.
        """
        from app.services.mission_template_service import InlineSubAgent
        from app.services.ollama_service import ollama_service
        from app.services.ollama_settings_service import (
            ollama_settings_service,
        )
        from app.services.system_prompt_service import system_prompt_service

        settings = get_settings()
        if not settings.ollama_enabled:
            return []

        user_settings = await ollama_settings_service.get(db)
        if not user_settings.expose_to_sessions:
            return []

        # Health check rapide - si Ollama est down, on n'injecte pas.
        try:
            status = await ollama_service.status()
        except Exception:
            logger.warning("session.ollama.status.failed", exc_info=True)
            return []
        if not status.reachable:
            return []

        try:
            system_prompt = await system_prompt_service.resolve(
                db, "mask_data_subagent"
            )
        except Exception:
            logger.warning(
                "session.ollama.subagent_prompt.missing", exc_info=True
            )
            return []

        return [
            InlineSubAgent(
                name="mask-data",
                description=(
                    "Pré-traitement local via Ollama : masque secrets, "
                    "anonymise PII ou résume avant d'envoyer du texte "
                    "sensible à Claude. Invoque-moi dès qu'un fichier "
                    "contient des données qui ne doivent pas quitter le "
                    "réseau local."
                ),
                system_prompt=system_prompt,
                allowed_tools=["Bash"],
            )
        ]

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

                # Persistance du coût d'un tour SDK (Phase 5)
                if event_type == EVENT_TYPE_USAGE:
                    await cost_service.record_turn(
                        db, session_id=session_id, data=data
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
