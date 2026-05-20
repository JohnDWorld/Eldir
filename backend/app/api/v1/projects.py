"""Routes /projects - list, get, create (from existing repo), delete."""

from __future__ import annotations

from fastapi import APIRouter, status

from app.core.deps import CurrentUserId, DbDep
from app.schemas.project import (
    ProjectCreateFromRepo,
    ProjectRead,
    ProjectSyncRead,
)
from app.services.project_service import project_service

router = APIRouter(prefix="/projects", tags=["projects"])


@router.get("", response_model=list[ProjectRead])
async def list_projects(
    user_id: CurrentUserId, db: DbDep
) -> list[ProjectRead]:
    items = await project_service.list_for_user(db, user_id)
    return [ProjectRead.model_validate(p) for p in items]


@router.get("/{project_id}", response_model=ProjectRead)
async def get_project(
    project_id: str, user_id: CurrentUserId, db: DbDep
) -> ProjectRead:
    project = await project_service.get(db, project_id, user_id)
    return ProjectRead.model_validate(project)


@router.post(
    "",
    response_model=ProjectRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_project(
    payload: ProjectCreateFromRepo,
    user_id: CurrentUserId,
    db: DbDep,
) -> ProjectRead:
    project = await project_service.create_from_repo(
        db,
        user_id=user_id,
        provider=payload.provider,
        repo_full_name=payload.repo_full_name,
        display_name=payload.display_name,
    )
    await db.commit()
    return ProjectRead.model_validate(project)


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(
    project_id: str, user_id: CurrentUserId, db: DbDep
) -> None:
    await project_service.delete(db, project_id, user_id)
    await db.commit()


@router.post("/{project_id}/sync", response_model=ProjectSyncRead)
async def sync_project(
    project_id: str, user_id: CurrentUserId, db: DbDep
) -> ProjectSyncRead:
    result = await project_service.sync_with_remote(
        db, project_id=project_id, user_id=user_id
    )
    return ProjectSyncRead(
        fetched=result.fetched,
        fast_forwarded=result.fast_forwarded,
        ahead=result.ahead,
        behind=result.behind,
        branch=result.branch,
        has_local_changes=result.has_local_changes,
        message=result.message,
    )
