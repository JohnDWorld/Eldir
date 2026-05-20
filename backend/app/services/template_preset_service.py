"""TemplatePresetService - charge les presets bundlés et les applique aux projets.

Les fichiers JSON vivent dans `backend/app/data/template_presets/`. Chacun
décrit un template complet (system prompt + model + allowed_tools + skills
+ sub-agents) prêt à être cloné dans un projet.
"""

from __future__ import annotations

import json
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.core.logging import get_logger
from app.db.models import MissionTemplate, TemplateSkill, TemplateSubAgent
from app.schemas.mission_template import (
    TemplatePresetDetail,
    TemplatePresetSkill,
    TemplatePresetSubAgent,
    TemplatePresetSummary,
)
from app.services.mission_template_service import mission_template_service

logger = get_logger(__name__)

_PRESETS_DIR = Path(__file__).parent.parent / "data" / "template_presets"


def _load_preset(path: Path) -> TemplatePresetDetail:
    raw = json.loads(path.read_text(encoding="utf-8"))
    raw.setdefault("skills", [])
    raw.setdefault("sub_agents", [])
    return TemplatePresetDetail.model_validate(raw)


class TemplatePresetService:
    def __init__(self, presets_dir: Path = _PRESETS_DIR) -> None:
        self._dir = presets_dir
        self._cache: dict[str, TemplatePresetDetail] | None = None

    def _load_all(self) -> dict[str, TemplatePresetDetail]:
        if self._cache is not None:
            return self._cache
        cache: dict[str, TemplatePresetDetail] = {}
        if not self._dir.exists():
            self._cache = cache
            return cache
        for path in sorted(self._dir.glob("*.json")):
            try:
                preset = _load_preset(path)
            except Exception:  # noqa: BLE001
                logger.exception("preset.load.failed", path=str(path))
                continue
            cache[preset.slug] = preset
        self._cache = cache
        return cache

    def list_summaries(self) -> list[TemplatePresetSummary]:
        return [
            TemplatePresetSummary(
                slug=p.slug,
                title=p.title,
                description=p.description,
                tags=p.tags,
                model=p.model,
                skill_count=len(p.skills),
                sub_agent_count=len(p.sub_agents),
            )
            for p in self._load_all().values()
        ]

    def get(self, slug: str) -> TemplatePresetDetail:
        presets = self._load_all()
        if slug not in presets:
            raise NotFoundError(f"Preset `{slug}` introuvable.")
        return presets[slug]

    async def apply(
        self,
        db: AsyncSession,
        *,
        project_id: str,
        user_id: str,
        slug: str,
        overwrite: bool,
    ) -> MissionTemplate:
        """Applique un preset au template d'un projet.

        - overwrite=True : remplace entièrement les champs scalaires, les
          skills et les sub-agents existants.
        - overwrite=False : merge - les scalaires existants restent
          inchangés s'ils ne sont pas vides, les skills/sub-agents du
          preset sont ajoutés (collisions de nom skip).
        """
        preset = self.get(slug)
        template = await mission_template_service._get_or_create(  # noqa: SLF001 - intentionnel ici
            db, project_id=project_id, user_id=user_id
        )

        # Champs scalaires
        if overwrite or not template.system_prompt:
            template.system_prompt = preset.system_prompt
        if overwrite or not template.model:
            template.model = preset.model
        if overwrite or not template.allowed_tools:
            template.allowed_tools = preset.allowed_tools
        template.source_preset = preset.slug

        await db.flush()

        # Skills et sub-agents existants
        existing_skill_names = {s.name for s in template.skills}
        existing_agent_names = {a.name for a in template.sub_agents}

        if overwrite:
            for s in list(template.skills):
                await db.delete(s)
            for a in list(template.sub_agents):
                await db.delete(a)
            await db.flush()
            existing_skill_names = set()
            existing_agent_names = set()

        for skill_preset in preset.skills:
            if skill_preset.name in existing_skill_names:
                continue
            _add_skill_from_preset(db, template.id, skill_preset)
        for agent_preset in preset.sub_agents:
            if agent_preset.name in existing_agent_names:
                continue
            _add_sub_agent_from_preset(db, template.id, agent_preset)

        await db.flush()
        return template


def _add_skill_from_preset(
    db: AsyncSession, template_id: str, preset: TemplatePresetSkill
) -> None:
    db.add(
        TemplateSkill(
            template_id=template_id,
            name=preset.name,
            description=preset.description,
            content=preset.content,
        )
    )


def _add_sub_agent_from_preset(
    db: AsyncSession, template_id: str, preset: TemplatePresetSubAgent
) -> None:
    db.add(
        TemplateSubAgent(
            template_id=template_id,
            name=preset.name,
            description=preset.description,
            system_prompt=preset.system_prompt,
            allowed_tools=preset.allowed_tools,
        )
    )


template_preset_service = TemplatePresetService()
