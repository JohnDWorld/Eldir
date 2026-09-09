"""Routes /batch - actions groupées sur tous les projets.

Deux boutons du dashboard, deux besoins différents :

- `sync-repos` : court (un fetch par repo), donc synchrone, on renvoie le
  détail par projet ;
- `generate-templates` : long (un tour Claude par repo), donc en tâche de fond
  avec un état à interroger.

Prefix `/batch` plutôt qu'une route sous `/projects` : `/projects/sync-all`
entrerait en collision avec `/projects/{project_id}`, où `project_id` vaudrait
« sync-all ».
"""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, status
from pydantic import Field

from app.core.deps import CurrentUserId, DbDep
from app.schemas.common import EldirModel
from app.services.project_service import project_service
from app.services.singletons import get_template_generator
from app.services.template_generator_service import BatchState

router = APIRouter(prefix="/batch", tags=["batch"])


class RepoSyncItem(EldirModel):
    project_id: str
    project_name: str
    fast_forwarded: bool = False
    ahead: int = 0
    behind: int = 0
    error: str | None = None


class RepoSyncResponse(EldirModel):
    items: list[RepoSyncItem] = Field(default_factory=list)


class BatchItemRead(EldirModel):
    project_id: str
    project_name: str
    state: Literal["pending", "running", "done", "error"]
    session_id: str | None = None
    detail: str | None = None


class BatchStateRead(EldirModel):
    running: bool
    items: list[BatchItemRead] = Field(default_factory=list)


@router.post("/sync-repos", response_model=RepoSyncResponse)
async def sync_all_repos(user_id: CurrentUserId, db: DbDep) -> RepoSyncResponse:
    """Fetch + fast-forward de tous les repos clonés, un par un.

    Un repo cassé ou un token expiré n'arrête pas les autres : son erreur est
    renvoyée dans sa ligne.
    """
    items: list[RepoSyncItem] = []
    for project in await project_service.list_for_user(db, user_id):
        try:
            result = await project_service.sync_with_remote(
                db, project_id=project.id, user_id=user_id
            )
        except Exception as exc:  # remonté par projet, jamais fatal
            items.append(
                RepoSyncItem(
                    project_id=project.id,
                    project_name=project.name,
                    error=str(exc) or type(exc).__name__,
                )
            )
            continue
        items.append(
            RepoSyncItem(
                project_id=project.id,
                project_name=project.name,
                fast_forwarded=result.fast_forwarded,
                ahead=result.ahead,
                behind=result.behind,
            )
        )
    await db.commit()
    return RepoSyncResponse(items=items)


def _serialize_batch(state: BatchState | None) -> BatchStateRead:
    if state is None:
        return BatchStateRead(running=False, items=[])
    return BatchStateRead(
        running=state.running,
        items=[
            BatchItemRead(
                project_id=i.project_id,
                project_name=i.project_name,
                state=i.state,  # type: ignore[arg-type]
                session_id=i.session_id,
                detail=i.detail,
            )
            for i in state.items
        ],
    )


@router.post(
    "/generate-templates",
    response_model=BatchStateRead,
    status_code=status.HTTP_202_ACCEPTED,
)
async def generate_missing_templates(user_id: CurrentUserId, db: DbDep) -> BatchStateRead:
    """Génère et applique le template des projets qui n'en ont pas encore.

    Un tour Claude par projet, enchaînés un par un, comptés dans les coûts
    comme n'importe quelle session. Les projets déjà pourvus sont sautés.
    """
    state = await get_template_generator().start_batch(db, user_id=user_id)
    await db.commit()
    return _serialize_batch(state)


@router.get("/generate-templates", response_model=BatchStateRead)
async def generation_batch_state(user_id: CurrentUserId) -> BatchStateRead:
    """Avancement du lot en cours, ou du dernier terminé.

    `user_id` n'est pas utilisé mais reste exigé : l'état d'un lot ne se lit
    pas sans être authentifié.
    """
    del user_id
    return _serialize_batch(get_template_generator().batch_state())
