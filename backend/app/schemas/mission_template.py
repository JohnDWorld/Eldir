"""Schemas MissionTemplate - Phase 4.

Le pipeline `gen-types.sh` exposera ces modèles côté frontend.
"""

from __future__ import annotations

import re
from datetime import datetime

from pydantic import Field, field_validator

from app.schemas.common import EldirModel, TimestampedModel

# Slug filesystem-safe : lettres, chiffres, tirets, underscores.
_NAME_PATTERN = re.compile(r"^[a-zA-Z0-9_-]+$")


def _validate_name(value: str) -> str:
    if not _NAME_PATTERN.match(value):
        raise ValueError(
            "Le nom doit contenir uniquement des lettres, chiffres, tirets et underscores."
        )
    return value


# ── Skills ─────────────────────────────────────────────────────
class TemplateSkillWrite(EldirModel):
    name: str = Field(min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=255)
    content: str = Field(min_length=1, max_length=64_000)

    @field_validator("name")
    @classmethod
    def _check_name(cls, v: str) -> str:
        return _validate_name(v)


class TemplateSkillRead(TimestampedModel):
    id: str
    template_id: str
    name: str
    description: str | None
    content: str


# ── Sub-agents ────────────────────────────────────────────────
class TemplateSubAgentWrite(EldirModel):
    name: str = Field(min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=255)
    system_prompt: str = Field(min_length=1, max_length=32_000)
    allowed_tools: list[str] | None = Field(default=None)

    @field_validator("name")
    @classmethod
    def _check_name(cls, v: str) -> str:
        return _validate_name(v)


class TemplateSubAgentRead(TimestampedModel):
    id: str
    template_id: str
    name: str
    description: str | None
    system_prompt: str
    allowed_tools: list[str] | None


# ── Template ──────────────────────────────────────────────────
class MissionTemplateWrite(EldirModel):
    """Payload pour `PUT /projects/{id}/template` - upsert.

    `allowed_tools=None` ou liste vide ⇒ tous les outils built-in autorisés
    (cf. décision Phase 4).
    """

    system_prompt: str | None = Field(default=None, max_length=32_000)
    model: str | None = Field(default=None, max_length=64)
    allowed_tools: list[str] | None = Field(default=None)


class MissionTemplateRead(TimestampedModel):
    id: str
    project_id: str
    system_prompt: str | None
    model: str | None
    allowed_tools: list[str] | None
    source_preset: str | None
    skills: list[TemplateSkillRead] = []
    sub_agents: list[TemplateSubAgentRead] = []


# ── Versions (Chantier 6) ─────────────────────────────────────
class TemplateVersionRead(TimestampedModel):
    id: str
    template_id: str
    version_index: int
    note: str | None
    snapshot: dict


class TemplateVersionRestore(EldirModel):
    note: str | None = Field(default=None, max_length=255)


# ── Presets bundlés (Chantier 5) ──────────────────────────────
class TemplatePresetSummary(EldirModel):
    """Vue compacte pour la liste des presets."""

    slug: str
    title: str
    description: str
    tags: list[str] = []
    model: str | None = None
    skill_count: int = 0
    sub_agent_count: int = 0


class TemplatePresetSkill(EldirModel):
    name: str
    description: str | None = None
    content: str


class TemplatePresetSubAgent(EldirModel):
    name: str
    description: str | None = None
    system_prompt: str
    allowed_tools: list[str] | None = None


class TemplatePresetDetail(EldirModel):
    """Preset rendu - utilisé pour preview ET pour application."""

    slug: str
    title: str
    description: str
    tags: list[str] = []
    system_prompt: str
    model: str | None = None
    allowed_tools: list[str] | None = None
    skills: list[TemplatePresetSkill] = []
    sub_agents: list[TemplatePresetSubAgent] = []


class TemplatePresetApply(EldirModel):
    """Payload pour `POST /projects/{id}/template/apply-preset`."""

    slug: str = Field(min_length=1, max_length=64)
    # Si True : écrase tout ce qui existait. Sinon : merge (skills/sub-agents
    # ajoutés sans toucher aux existants, champs scalaires écrasés).
    overwrite: bool = True


# Avoid unused import warning for datetime (reserved for downstream additions)
_ = datetime
