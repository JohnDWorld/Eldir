"""Routes /projects/{id}/template - CRUD MissionTemplate Phase 4."""

from __future__ import annotations

from fastapi import APIRouter, status

from app.core.deps import CurrentUserId, DbDep
from app.core.exceptions import NotFoundError
from app.schemas.common import EldirModel
from app.schemas.mission_template import (
    MissionTemplateRead,
    MissionTemplateWrite,
    TemplatePresetApply,
    TemplatePresetDetail,
    TemplatePresetSummary,
    TemplateSkillRead,
    TemplateSkillWrite,
    TemplateSubAgentRead,
    TemplateSubAgentWrite,
    TemplateVersionRead,
    TemplateVersionRestore,
)
from app.services.mission_template_service import mission_template_service
from app.services.singletons import get_template_generator
from app.services.template_preset_service import template_preset_service

router = APIRouter(prefix="/projects/{project_id}", tags=["templates"])

# Routes presets côté global (pas project-scoped pour la liste).
presets_router = APIRouter(prefix="/templates/presets", tags=["templates"])


@presets_router.get("", response_model=list[TemplatePresetSummary])
async def list_presets() -> list[TemplatePresetSummary]:
    return template_preset_service.list_summaries()


@presets_router.get("/{slug}", response_model=TemplatePresetDetail)
async def get_preset(slug: str) -> TemplatePresetDetail:
    return template_preset_service.get(slug)


def _serialize_template(template) -> MissionTemplateRead:  # type: ignore[no-untyped-def]
    return MissionTemplateRead(
        id=template.id,
        project_id=template.project_id,
        system_prompt=template.system_prompt,
        model=template.model,
        allowed_tools=template.allowed_tools,
        source_preset=template.source_preset,
        created_at=template.created_at,
        updated_at=template.updated_at,
        skills=[TemplateSkillRead.model_validate(s) for s in template.skills],
        sub_agents=[
            TemplateSubAgentRead.model_validate(a) for a in template.sub_agents
        ],
    )


@router.get("/template", response_model=MissionTemplateRead | None)
async def get_template(
    project_id: str, user_id: CurrentUserId, db: DbDep
) -> MissionTemplateRead | None:
    template = await mission_template_service.get(
        db, project_id=project_id, user_id=user_id
    )
    if template is None:
        return None
    return _serialize_template(template)


@router.put("/template", response_model=MissionTemplateRead)
async def upsert_template(
    project_id: str,
    payload: MissionTemplateWrite,
    user_id: CurrentUserId,
    db: DbDep,
) -> MissionTemplateRead:
    # Snapshot avant modification pour permettre rollback (Chantier 6).
    await mission_template_service.snapshot(
        db, project_id=project_id, user_id=user_id, note="avant upsert"
    )
    await mission_template_service.upsert(
        db, project_id=project_id, user_id=user_id, payload=payload
    )
    await db.commit()
    # Recharge avec les skills/sub-agents pour le payload de retour.
    reloaded = await mission_template_service.get(
        db, project_id=project_id, user_id=user_id
    )
    if reloaded is None:
        raise NotFoundError("Template introuvable après upsert.")
    return _serialize_template(reloaded)


@router.delete("/template", status_code=status.HTTP_204_NO_CONTENT)
async def delete_template(
    project_id: str, user_id: CurrentUserId, db: DbDep
) -> None:
    await mission_template_service.delete(
        db, project_id=project_id, user_id=user_id
    )
    await db.commit()


class TemplateGenerateRequest(EldirModel):
    model: str | None = None


class TemplateGenerateResponse(EldirModel):
    preset: TemplatePresetDetail
    session_id: str


@router.post(
    "/template/generate", response_model=TemplateGenerateResponse
)
async def generate_template(
    project_id: str,
    payload: TemplateGenerateRequest,
    user_id: CurrentUserId,
    db: DbDep,
) -> TemplateGenerateResponse:
    """Génère un preset via Claude en lecture seule sur le repo cloné.

    Crée une session système (is_system=True) - les coûts apparaissent
    dans le dashboard comme n'importe quelle autre session.
    """
    result = await get_template_generator().generate(
        db,
        user_id=user_id,
        project_id=project_id,
        model=payload.model,
    )
    return TemplateGenerateResponse(
        preset=result.preset, session_id=result.session_id
    )


class TemplateApplyInlineRequest(EldirModel):
    preset: TemplatePresetDetail
    overwrite: bool = True


@router.post(
    "/template/apply-inline", response_model=MissionTemplateRead
)
async def apply_inline_preset(
    project_id: str,
    payload: TemplateApplyInlineRequest,
    user_id: CurrentUserId,
    db: DbDep,
) -> MissionTemplateRead:
    """Applique un preset construit côté client (issu d'une génération
    Claude, par exemple) sans qu'il soit persisté en fichier.
    """
    await mission_template_service.snapshot(
        db,
        project_id=project_id,
        user_id=user_id,
        note=f"avant apply-inline ({payload.preset.slug})",
    )
    await template_preset_service.apply_detail(
        db,
        project_id=project_id,
        user_id=user_id,
        preset=payload.preset,
        overwrite=payload.overwrite,
    )
    await db.commit()
    reloaded = await mission_template_service.get(
        db, project_id=project_id, user_id=user_id
    )
    if reloaded is None:
        raise NotFoundError("Template introuvable après apply-inline.")
    return _serialize_template(reloaded)


@router.post("/template/apply-preset", response_model=MissionTemplateRead)
async def apply_preset(
    project_id: str,
    payload: TemplatePresetApply,
    user_id: CurrentUserId,
    db: DbDep,
) -> MissionTemplateRead:
    # Snapshot avant écrasement par le preset (Chantier 6).
    await mission_template_service.snapshot(
        db,
        project_id=project_id,
        user_id=user_id,
        note=f"avant apply-preset {payload.slug}",
    )
    await template_preset_service.apply(
        db,
        project_id=project_id,
        user_id=user_id,
        slug=payload.slug,
        overwrite=payload.overwrite,
    )
    await db.commit()
    reloaded = await mission_template_service.get(
        db, project_id=project_id, user_id=user_id
    )
    if reloaded is None:
        raise NotFoundError("Template introuvable après apply-preset.")
    return _serialize_template(reloaded)


# ── Versions ──────────────────────────────────────────────────
@router.get("/template/versions", response_model=list[TemplateVersionRead])
async def list_template_versions(
    project_id: str, user_id: CurrentUserId, db: DbDep
) -> list[TemplateVersionRead]:
    versions = await mission_template_service.list_versions(
        db, project_id=project_id, user_id=user_id
    )
    return [TemplateVersionRead.model_validate(v) for v in versions]


@router.post(
    "/template/versions/{version_id}/restore", response_model=MissionTemplateRead
)
async def restore_template_version(
    project_id: str,
    version_id: str,
    payload: TemplateVersionRestore,
    user_id: CurrentUserId,
    db: DbDep,
) -> MissionTemplateRead:
    await mission_template_service.restore_version(
        db,
        project_id=project_id,
        user_id=user_id,
        version_id=version_id,
        note=payload.note,
    )
    await db.commit()
    reloaded = await mission_template_service.get(
        db, project_id=project_id, user_id=user_id
    )
    if reloaded is None:
        raise NotFoundError("Template introuvable après restauration.")
    return _serialize_template(reloaded)


# ── Skills ────────────────────────────────────────────────────
@router.get("/template/skills", response_model=list[TemplateSkillRead])
async def list_skills(
    project_id: str, user_id: CurrentUserId, db: DbDep
) -> list[TemplateSkillRead]:
    skills = await mission_template_service.list_skills(
        db, project_id=project_id, user_id=user_id
    )
    return [TemplateSkillRead.model_validate(s) for s in skills]


@router.post(
    "/template/skills",
    response_model=TemplateSkillRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_skill(
    project_id: str,
    payload: TemplateSkillWrite,
    user_id: CurrentUserId,
    db: DbDep,
) -> TemplateSkillRead:
    skill = await mission_template_service.create_skill(
        db, project_id=project_id, user_id=user_id, payload=payload
    )
    await db.commit()
    return TemplateSkillRead.model_validate(skill)


@router.put("/template/skills/{skill_id}", response_model=TemplateSkillRead)
async def update_skill(
    project_id: str,
    skill_id: str,
    payload: TemplateSkillWrite,
    user_id: CurrentUserId,
    db: DbDep,
) -> TemplateSkillRead:
    skill = await mission_template_service.update_skill(
        db,
        project_id=project_id,
        user_id=user_id,
        skill_id=skill_id,
        payload=payload,
    )
    await db.commit()
    return TemplateSkillRead.model_validate(skill)


@router.delete(
    "/template/skills/{skill_id}", status_code=status.HTTP_204_NO_CONTENT
)
async def delete_skill(
    project_id: str,
    skill_id: str,
    user_id: CurrentUserId,
    db: DbDep,
) -> None:
    await mission_template_service.delete_skill(
        db, project_id=project_id, user_id=user_id, skill_id=skill_id
    )
    await db.commit()


# ── Sub-agents ────────────────────────────────────────────────
@router.get(
    "/template/sub-agents", response_model=list[TemplateSubAgentRead]
)
async def list_sub_agents(
    project_id: str, user_id: CurrentUserId, db: DbDep
) -> list[TemplateSubAgentRead]:
    agents = await mission_template_service.list_sub_agents(
        db, project_id=project_id, user_id=user_id
    )
    return [TemplateSubAgentRead.model_validate(a) for a in agents]


@router.post(
    "/template/sub-agents",
    response_model=TemplateSubAgentRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_sub_agent(
    project_id: str,
    payload: TemplateSubAgentWrite,
    user_id: CurrentUserId,
    db: DbDep,
) -> TemplateSubAgentRead:
    agent = await mission_template_service.create_sub_agent(
        db, project_id=project_id, user_id=user_id, payload=payload
    )
    await db.commit()
    return TemplateSubAgentRead.model_validate(agent)


@router.put(
    "/template/sub-agents/{agent_id}", response_model=TemplateSubAgentRead
)
async def update_sub_agent(
    project_id: str,
    agent_id: str,
    payload: TemplateSubAgentWrite,
    user_id: CurrentUserId,
    db: DbDep,
) -> TemplateSubAgentRead:
    agent = await mission_template_service.update_sub_agent(
        db,
        project_id=project_id,
        user_id=user_id,
        agent_id=agent_id,
        payload=payload,
    )
    await db.commit()
    return TemplateSubAgentRead.model_validate(agent)


@router.delete(
    "/template/sub-agents/{agent_id}", status_code=status.HTTP_204_NO_CONTENT
)
async def delete_sub_agent(
    project_id: str,
    agent_id: str,
    user_id: CurrentUserId,
    db: DbDep,
) -> None:
    await mission_template_service.delete_sub_agent(
        db, project_id=project_id, user_id=user_id, agent_id=agent_id
    )
    await db.commit()
