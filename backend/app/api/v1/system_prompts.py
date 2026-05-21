"""Routes /system-prompts - prompts Eldir éditables (Settings > Prompts).

Cf. AGENTS.md §"L'utilisateur reste maître" : chaque prompt qu'Eldir
envoie pour ses propres opérations (génération de template, etc.) doit
être visible et modifiable depuis l'UI.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.core.deps import CurrentUserId, DbDep
from app.schemas.system_prompt import SystemPromptRead, SystemPromptWrite
from app.services.system_prompt_service import (
    SystemPromptRead as ServiceSystemPromptRead,
)
from app.services.system_prompt_service import (
    system_prompt_service,
)

router = APIRouter(prefix="/system-prompts", tags=["system-prompts"])


def _to_schema(item: ServiceSystemPromptRead) -> SystemPromptRead:
    return SystemPromptRead(
        slug=item.slug,
        title=item.title,
        description=item.description,
        content=item.content,
        is_overridden=item.is_overridden,
        default_content=item.default_content,
    )


@router.get("", response_model=list[SystemPromptRead])
async def list_prompts(
    user_id: CurrentUserId, db: DbDep
) -> list[SystemPromptRead]:
    items = await system_prompt_service.list_all(db)
    return [_to_schema(i) for i in items]


@router.get("/{slug}", response_model=SystemPromptRead)
async def get_prompt(
    slug: str, user_id: CurrentUserId, db: DbDep
) -> SystemPromptRead:
    item = await system_prompt_service.get(db, slug)
    return _to_schema(item)


@router.put("/{slug}", response_model=SystemPromptRead)
async def upsert_prompt(
    slug: str,
    payload: SystemPromptWrite,
    user_id: CurrentUserId,
    db: DbDep,
) -> SystemPromptRead:
    item = await system_prompt_service.upsert(db, slug, payload.content)
    await db.commit()
    return _to_schema(item)


@router.post("/{slug}/reset", response_model=SystemPromptRead)
async def reset_prompt(
    slug: str, user_id: CurrentUserId, db: DbDep
) -> SystemPromptRead:
    item = await system_prompt_service.reset(db, slug)
    await db.commit()
    return _to_schema(item)
