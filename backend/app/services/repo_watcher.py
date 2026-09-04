"""RepoWatcher - surveillance périodique des repos clonés.

Boucle unique en tâche de fond : toutes les `repo_sync_interval_minutes`,
chaque projet est fetché et fast-forwardé quand c'est sans risque. Toute la
prudence vit déjà dans `ProjectService.sync_with_remote` (pas de pull si le
working tree est sale ou si on n'est pas sur la branche par défaut), on ne
fait qu'appeler à intervalle régulier ce que le bouton "sync" fait à la main.

Les worktrees de session ne sont jamais touchés : seul le clone canonique du
projet est mis à jour, et les nouvelles sessions partent de `origin/<branche>`.
"""

from __future__ import annotations

import asyncio
from contextlib import suppress

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.logging import get_logger
from app.db.models import Project
from app.services.project_service import project_service

logger = get_logger(__name__)


class RepoWatcher:
    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        interval_seconds: float,
    ) -> None:
        self._factory = session_factory
        self._interval = interval_seconds
        self._task: asyncio.Task[None] | None = None

    def start(self) -> None:
        if self._interval <= 0:
            logger.info("repo_watcher.disabled")
            return
        if self._task is not None:
            return
        self._task = asyncio.create_task(self._loop())
        logger.info("repo_watcher.started", interval_seconds=self._interval)

    async def stop(self) -> None:
        if self._task is None:
            return
        self._task.cancel()
        with suppress(asyncio.CancelledError):
            await self._task
        self._task = None

    async def _loop(self) -> None:
        while True:
            await asyncio.sleep(self._interval)
            try:
                await self.sync_all()
            except Exception:  # noqa: BLE001
                logger.exception("repo_watcher.cycle.failed")

    async def sync_all(self) -> int:
        """Un cycle de synchro. Renvoie le nombre de projets fast-forwardés."""
        async with self._factory() as db:
            result = await db.execute(select(Project))
            projects = list(result.scalars().all())

            updated = 0
            for project in projects:
                try:
                    sync = await project_service.sync_with_remote(
                        db, project_id=project.id, user_id=project.user_id
                    )
                except Exception:  # noqa: BLE001
                    # Un repo cassé ou un token expiré ne doit pas arrêter
                    # la surveillance des autres.
                    logger.exception(
                        "repo_watcher.project.failed", project_id=project.id
                    )
                    continue
                if sync.fast_forwarded:
                    updated += 1
                    logger.info(
                        "repo_watcher.project.updated",
                        project_id=project.id,
                        branch=sync.branch,
                    )
            await db.commit()
        return updated
