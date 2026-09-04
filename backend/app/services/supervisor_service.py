"""SupervisorService - la session Eldir qui pilote les autres sessions.

Le superviseur est une session Claude comme les autres (row `sessions`,
events streamés, coûts comptés), à trois différences près :

- elle n'a pas de projet ni de worktree : `project_id` est NULL ;
- ses seuls outils sont quatre outils MCP in-process (aucun accès disque,
  aucun git, aucun réseau) ;
- elle est notifiée automatiquement quand une session qu'elle a dispatchée
  termine son tour, via le compte rendu `<cr>` recopié dans `sessions.summary`.

Boucle complète : John parle au superviseur → `dispatch` → la session enfant
travaille en tâche de fond → son `<cr>` écrase le précédent → STOP → ping du
superviseur → il traduit le compte rendu à John, qui valide (ou non) la
publication depuis le dashboard.
"""

from __future__ import annotations

import asyncio
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import get_settings
from app.core.constants import EVENT_TYPE_ERROR, EVENT_TYPE_STOP
from app.core.exceptions import NotFoundError
from app.core.logging import get_logger
from app.db.models import Project
from app.db.models import Session as SessionRow
from app.services.claude_credential_service import claude_credential_service
from app.services.session_manager import SessionManager
from app.services.session_service import SessionService
from app.services.system_prompt_service import system_prompt_service

logger = get_logger(__name__)

SUPERVISOR_KIND = "supervisor"
SUPERVISOR_PROMPT_SLUG = "supervisor"
SUPERVISOR_PREFS_SLUG = "supervisor_prefs"

_MCP_SERVER = "eldir"
_TOOL_NAMES = ("list_projects", "list_sessions", "dispatch", "remember")
ALLOWED_TOOLS = [f"mcp__{_MCP_SERVER}__{name}" for name in _TOOL_NAMES]
# Le superviseur ne touche ni au disque ni au réseau : il délègue, point.
# `allowed_tools` seul ne suffit pas à retirer les outils intégrés quand la
# session tourne en bypassPermissions, d'où la liste d'interdits.
DISALLOWED_TOOLS = [
    "Bash",
    "BashOutput",
    "KillShell",
    "Read",
    "Write",
    "Edit",
    "NotebookEdit",
    "Glob",
    "Grep",
    "Task",
    "WebFetch",
    "WebSearch",
]

# Le worktree du superviseur n'est qu'un cwd vide : il ne code pas.
_CWD_DIRNAME = "_supervisor"


def _text(message: str) -> dict[str, Any]:
    """Réponse d'outil MCP au format attendu par le SDK."""
    return {"content": [{"type": "text", "text": message}]}


class SupervisorService:
    def __init__(
        self,
        *,
        manager: SessionManager,
        sessions: SessionService,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        self._manager = manager
        self._sessions = sessions
        self._factory = session_factory
        # Sessions dispatchées dont on attend la fin de tour pour pinger.
        self._pending: set[str] = set()
        self._tasks: set[asyncio.Task[None]] = set()
        manager.register_persist_callback(self._on_event)

    # ── cycle de vie ────────────────────────────────────────────
    async def ensure_session(
        self, db: AsyncSession, user_id: str
    ) -> SessionRow:
        """Renvoie la session superviseur, démarrée si besoin (idempotent)."""
        row = await self._find_row(db, user_id)
        if row is not None and self._manager.is_active(row.id):
            return row

        await claude_credential_service.inject_active_into_env(
            db, user_id=user_id
        )
        prompt = await self._build_prompt(db)
        cwd = get_settings().workspaces_root / _CWD_DIRNAME
        cwd.mkdir(parents=True, exist_ok=True)

        if row is None:
            row = SessionRow(
                project_id=None,
                user_id=user_id,
                branch="-",
                worktree_path=str(cwd),
                model=get_settings().claude_default_model,
                system_prompt=prompt,
                is_system=True,
                system_kind=SUPERVISOR_KIND,
                summary="Superviseur Eldir",
            )
            db.add(row)
            await db.flush()
        else:
            # Le prompt est reconstruit à chaque démarrage pour embarquer
            # les préférences apprises depuis la dernière fois.
            row.system_prompt = prompt
            row.worktree_path = str(cwd)
            await db.flush()

        try:
            await self._start_sdk(row, user_id, prompt)
        except Exception:  # noqa: BLE001
            # Transcript SDK disparu (redémarrage du conteneur, purge…) :
            # on repart d'une conversation neuve plutôt que de rester bloqué.
            if not row.sdk_session_id:
                raise
            logger.warning(
                "supervisor.resume.failed", session_id=row.id, exc_info=True
            )
            row.sdk_session_id = None
            await db.flush()
            await self._start_sdk(row, user_id, prompt)
        logger.info("supervisor.started", session_id=row.id)
        return row

    async def _start_sdk(
        self, row: SessionRow, user_id: str, prompt: str
    ) -> None:
        await self._manager.start(
            session_id=row.id,
            project_id=None,
            user_id=user_id,
            cwd=row.worktree_path or "",
            system_prompt=prompt,
            model=row.model,
            resume_sdk_id=row.sdk_session_id,
            allowed_tools=ALLOWED_TOOLS,
            disallowed_tools=DISALLOWED_TOOLS,
            mcp_servers={_MCP_SERVER: self._build_mcp_server(user_id)},
        )

    async def _find_row(
        self, db: AsyncSession, user_id: str
    ) -> SessionRow | None:
        result = await db.execute(
            select(SessionRow)
            .where(
                SessionRow.user_id == user_id,
                SessionRow.is_system.is_(True),
                SessionRow.system_kind == SUPERVISOR_KIND,
            )
            .order_by(SessionRow.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def _build_prompt(self, db: AsyncSession) -> str:
        base = await system_prompt_service.resolve(db, SUPERVISOR_PROMPT_SLUG)
        prefs = await system_prompt_service.resolve(db, SUPERVISOR_PREFS_SLUG)
        return f"{base.rstrip()}\n\n## Préférences de John\n\n{prefs.strip()}"

    # ── outils exposés à Claude ─────────────────────────────────
    def _build_mcp_server(self, user_id: str) -> Any:
        from claude_agent_sdk import create_sdk_mcp_server, tool

        @tool(
            "list_projects",
            "Liste les repos branchés sur Eldir. Sert à identifier de quel "
            "projet John parle avant de dispatcher.",
            {"type": "object", "properties": {}},
        )
        async def list_projects(_args: dict[str, Any]) -> dict[str, Any]:
            async with self._factory() as db:
                result = await db.execute(
                    select(Project)
                    .where(Project.user_id == user_id)
                    .order_by(Project.name.asc())
                )
                projects = list(result.scalars().all())
            if not projects:
                return _text("Aucun projet branché sur Eldir.")
            lines = [
                f"- {p.name} (id={p.id}) · {p.provider}:{p.repo_full_name} "
                f"· branche {p.default_branch}"
                for p in projects
            ]
            return _text("\n".join(lines))

        @tool(
            "list_sessions",
            "Liste les sessions Claude existantes avec leur état et le compte "
            "rendu de leur dernier passage. À consulter avant de dispatcher.",
            {"type": "object", "properties": {}},
        )
        async def list_sessions(_args: dict[str, Any]) -> dict[str, Any]:
            async with self._factory() as db:
                result = await db.execute(
                    select(SessionRow, Project.name)
                    .join(Project, Project.id == SessionRow.project_id)
                    .where(
                        SessionRow.user_id == user_id,
                        SessionRow.is_system.is_(False),
                    )
                    .order_by(SessionRow.updated_at.desc())
                    .limit(20)
                )
                rows = list(result.all())
            if not rows:
                return _text("Aucune session projet ouverte.")
            blocks: list[str] = []
            for session, project_name in rows:
                live = "active" if self._manager.is_active(session.id) else "dormante"
                cr = (session.summary or "pas encore de compte rendu").strip()
                blocks.append(
                    f"### {project_name} · session {session.id}\n"
                    f"état: {session.state} ({live}) · branche: {session.branch}\n"
                    f"dernier passage:\n{cr}"
                )
            return _text("\n\n".join(blocks))

        @tool(
            "dispatch",
            "Transmet une consigne à une session projet et rend la main "
            "immédiatement. Reprend la session indiquée, sinon la session "
            "ouverte la plus récente du projet, sinon en démarre une. Tu "
            "recevras un message automatique avec son compte rendu quand elle "
            "aura terminé.",
            {
                "type": "object",
                "properties": {
                    "project_id": {
                        "type": "string",
                        "description": "id du projet cible (cf. list_projects)",
                    },
                    "consigne": {
                        "type": "string",
                        "description": (
                            "Consigne complète et auto-suffisante : la session "
                            "enfant ne voit pas ta conversation avec John."
                        ),
                    },
                    "session_id": {
                        "type": "string",
                        "description": (
                            "Optionnel : session précise à reprendre. Laisser "
                            "vide pour laisser Eldir choisir."
                        ),
                    },
                },
                "required": ["project_id", "consigne"],
            },
        )
        async def dispatch(args: dict[str, Any]) -> dict[str, Any]:
            project_id = str(args.get("project_id") or "").strip()
            consigne = str(args.get("consigne") or "").strip()
            session_id = str(args.get("session_id") or "").strip() or None
            if not project_id or not consigne:
                return _text("Erreur : project_id et consigne sont obligatoires.")
            try:
                target, project_name, created = await self._resolve_target(
                    user_id=user_id,
                    project_id=project_id,
                    session_id=session_id,
                )
            except NotFoundError as exc:
                return _text(f"Erreur : {exc.message}")

            self._pending.add(target)
            self._spawn(self._run_child(user_id, target, consigne))
            origine = "nouvelle session" if created else "session reprise"
            return _text(
                f"Consigne transmise à {project_name} ({origine} {target}). "
                "Elle travaille en tâche de fond, tu seras notifié à la fin de "
                "son tour."
            )

        @tool(
            "remember",
            "Enregistre une préférence de travail durable de John (elle sera "
            "dans ton prompt aux prochains démarrages). Uniquement pour ce qui "
            "vaut pour les fois suivantes, jamais pour une demande ponctuelle.",
            {
                "type": "object",
                "properties": {
                    "fait": {
                        "type": "string",
                        "description": (
                            "Une phrase courte et impérative, ex : 'Sur Munin, "
                            "toujours ouvrir une PR plutôt que commiter sur main.'"
                        ),
                    }
                },
                "required": ["fait"],
            },
        )
        async def remember(args: dict[str, Any]) -> dict[str, Any]:
            return _text(await self.remember_preference(str(args.get("fait") or "")))

        return create_sdk_mcp_server(
            name=_MCP_SERVER,
            tools=[list_projects, list_sessions, dispatch, remember],
        )

    async def remember_preference(self, fait: str) -> str:
        """Ajoute une préférence durable au prompt du superviseur."""
        fait = fait.strip()
        if not fait:
            return "Erreur : 'fait' est vide."
        line = f"- {fait}"
        async with self._factory() as db:
            current = await system_prompt_service.get(db, SUPERVISOR_PREFS_SLUG)
            # Le défaut versionné n'est qu'un placeholder : la première
            # préférence part d'une page blanche.
            body = current.content.strip() if current.is_overridden else ""
            if line in body:
                return "Préférence déjà enregistrée."
            await system_prompt_service.upsert(
                db, SUPERVISOR_PREFS_SLUG, f"{body}\n{line}".strip()
            )
            await db.commit()
        logger.info("supervisor.remember", fait=fait)
        return f"Noté : {fait}"

    # ── dispatch ────────────────────────────────────────────────
    async def _resolve_target(
        self, *, user_id: str, project_id: str, session_id: str | None
    ) -> tuple[str, str, bool]:
        """Renvoie (session_id, nom du projet, session_créée)."""
        async with self._factory() as db:
            project = await db.get(Project, project_id)
            if project is None or project.user_id != user_id:
                raise NotFoundError(f"Projet {project_id} introuvable.")

            if session_id is not None:
                existing = await db.get(SessionRow, session_id)
                if existing is None or existing.user_id != user_id:
                    raise NotFoundError(f"Session {session_id} introuvable.")
                return existing.id, project.name, False

            result = await db.execute(
                select(SessionRow)
                .where(
                    SessionRow.user_id == user_id,
                    SessionRow.project_id == project_id,
                    SessionRow.is_system.is_(False),
                )
                .order_by(SessionRow.updated_at.desc())
                .limit(1)
            )
            existing = result.scalar_one_or_none()
            if existing is not None and existing.sdk_session_id:
                return existing.id, project.name, False

            created = await self._sessions.create_and_start(
                db, user_id=user_id, project_id=project_id
            )
            await db.commit()
            return created.id, project.name, True

    async def _run_child(
        self, user_id: str, session_id: str, consigne: str
    ) -> None:
        """Fait tourner le tour de la session enfant hors de la requête."""
        try:
            # La DB n'est utilisée que pour le contrôle d'accès et le resume :
            # on rend la connexion avant le tour, qui peut durer des minutes.
            async with self._factory() as db:
                await self._sessions.get(db, session_id, user_id)
                if not self._manager.is_active(session_id):
                    await self._sessions.resume(
                        db, user_id=user_id, session_id=session_id
                    )
                await db.commit()
            await self._manager.send_message(session_id, consigne)
        except Exception as exc:  # noqa: BLE001
            logger.exception("supervisor.dispatch.failed", session_id=session_id)
            self._pending.discard(session_id)
            self._spawn(
                self._tell_supervisor(
                    user_id,
                    f"[Eldir] La session {session_id} n'a pas pu traiter la "
                    f"consigne : {exc}. Explique le problème à John.",
                )
            )

    # ── ping de fin de tour ─────────────────────────────────────
    async def _on_event(
        self, session_id: str, event_type: str, data: dict[str, Any]
    ) -> None:
        """Callback branché sur le SessionManager (tous les events)."""
        if event_type not in (EVENT_TYPE_STOP, EVENT_TYPE_ERROR):
            return
        if session_id not in self._pending:
            return
        self._pending.discard(session_id)
        self._spawn(self._notify_turn_done(session_id, event_type, data))

    async def _notify_turn_done(
        self, session_id: str, event_type: str, data: dict[str, Any]
    ) -> None:
        async with self._factory() as db:
            child = await db.get(SessionRow, session_id)
            if child is None:
                return
            user_id = child.user_id
            project_name = "projet inconnu"
            if child.project_id:
                project = await db.get(Project, child.project_id)
                if project is not None:
                    project_name = project.name
            cr = (child.summary or "").strip()

        if event_type == EVENT_TYPE_ERROR:
            body = f"Elle a échoué : {data.get('message', 'erreur inconnue')}"
        else:
            body = (
                f"Compte rendu :\n{cr}"
                if cr
                else "Elle n'a pas produit de compte rendu <cr>."
            )
        await self._tell_supervisor(
            user_id,
            f"[Eldir] La session {session_id} ({project_name}, branche "
            f"{child.branch}) a terminé son tour.\n{body}\n\n"
            "Résume à John ce qui a été fait et dis-lui si c'est prêt à être "
            "relu et publié.",
        )

    async def _tell_supervisor(self, user_id: str, content: str) -> None:
        """Envoie un message système au superviseur (comme si John parlait)."""
        try:
            async with self._factory() as db:
                supervisor = await self.ensure_session(db, user_id)
                await db.commit()
            await self._manager.send_message(supervisor.id, content)
        except Exception:  # noqa: BLE001
            logger.exception("supervisor.notify.failed")

    def _spawn(self, coro: Any) -> None:
        """Tâche de fond dont on garde une référence (sinon GC prématuré)."""
        task = asyncio.create_task(coro)
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)
