"""MissionTemplateService - orchestration CRUD du template d'un projet.

Le template (system prompt + model + outils + skills + sub-agents) est
appliqué à chaque nouvelle session du projet par `session_service`. Voir
Phase 4 du ROADMAP.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import ConflictError, NotFoundError
from app.core.logging import get_logger
from app.db.models import (
    MissionTemplate,
    Project,
    TemplateSkill,
    TemplateSubAgent,
    TemplateVersion,
)
from app.schemas.mission_template import (
    MissionTemplateWrite,
    TemplateSkillWrite,
    TemplateSubAgentWrite,
)

logger = get_logger(__name__)


def _yaml_escape(value: str) -> str:
    """Quote pour YAML inline si nécessaire (caractères spéciaux)."""
    if any(c in value for c in ":#'\"\n[]{},"):
        escaped = value.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'
    return value


def _frontmatter_block(fields: dict[str, object]) -> str:
    lines = ["---"]
    for k, v in fields.items():
        if v is None:
            continue
        if isinstance(v, list):
            if not v:
                continue
            joined = ", ".join(_yaml_escape(str(x)) for x in v)
            lines.append(f"{k}: [{joined}]")
        else:
            lines.append(f"{k}: {_yaml_escape(str(v))}")
    lines.append("---\n")
    return "\n".join(lines)


def _materialize_skill(skills_root: Path, skill: TemplateSkill) -> None:
    """Écrit le skill dans `.claude/skills/{name}/SKILL.md` (convention Claude).

    Un fichier .md par skill (décision Phase 4), mais placé dans son propre
    dossier pour matcher la convention SDK.
    """
    target = skills_root / skill.name / "SKILL.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    frontmatter = _frontmatter_block(
        {"name": skill.name, "description": skill.description}
    )
    target.write_text(frontmatter + "\n" + skill.content + "\n", encoding="utf-8")


@dataclass(slots=True, frozen=True)
class InlineSubAgent:
    """Sub-agent à matérialiser sans entrée DB - utilisé pour les sub-agents
    'système' injectés dynamiquement (ex. mask-data quand Ollama est exposé).
    """

    name: str
    description: str
    system_prompt: str
    allowed_tools: list[str] | None = None


def _materialize_sub_agent(
    agents_root: Path,
    agent: TemplateSubAgent | InlineSubAgent,
) -> None:
    """Écrit le sub-agent dans `.claude/agents/{name}.md`."""
    target = agents_root / f"{agent.name}.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    frontmatter = _frontmatter_block(
        {
            "name": agent.name,
            "description": agent.description,
            "tools": agent.allowed_tools,
        }
    )
    target.write_text(
        frontmatter + "\n" + agent.system_prompt + "\n", encoding="utf-8"
    )


class MissionTemplateService:
    # ── Project ↔ template ──────────────────────────────────────
    async def _require_project(
        self, db: AsyncSession, *, project_id: str, user_id: str
    ) -> Project:
        result = await db.execute(
            select(Project).where(
                Project.id == project_id, Project.user_id == user_id
            )
        )
        project = result.scalar_one_or_none()
        if project is None:
            raise NotFoundError(f"Projet {project_id} introuvable.")
        return project

    async def get(
        self, db: AsyncSession, *, project_id: str, user_id: str
    ) -> MissionTemplate | None:
        await self._require_project(db, project_id=project_id, user_id=user_id)
        result = await db.execute(
            select(MissionTemplate)
            .where(MissionTemplate.project_id == project_id)
            .options(
                selectinload(MissionTemplate.skills),  # type: ignore[attr-defined]
                selectinload(MissionTemplate.sub_agents),  # type: ignore[attr-defined]
            )
        )
        return result.scalar_one_or_none()

    async def _get_or_create(
        self, db: AsyncSession, *, project_id: str, user_id: str
    ) -> MissionTemplate:
        existing = await self.get(db, project_id=project_id, user_id=user_id)
        if existing is not None:
            return existing
        template = MissionTemplate(project_id=project_id)
        db.add(template)
        await db.flush()
        # Recharge avec selectinload pour que `template.skills` /
        # `template.sub_agents` ne déclenchent pas un lazy-load synchrone
        # plus tard (le contexte async ne le supporte pas — MissingGreenlet).
        reloaded = await self.get(db, project_id=project_id, user_id=user_id)
        assert reloaded is not None  # noqa: S101 — invariant après flush
        return reloaded

    async def upsert(
        self,
        db: AsyncSession,
        *,
        project_id: str,
        user_id: str,
        payload: MissionTemplateWrite,
    ) -> MissionTemplate:
        template = await self._get_or_create(
            db, project_id=project_id, user_id=user_id
        )
        template.system_prompt = payload.system_prompt
        template.model = payload.model
        template.allowed_tools = payload.allowed_tools
        # source_preset reste tel quel (modifié par apply_preset uniquement)
        await db.flush()
        return template

    async def delete(
        self, db: AsyncSession, *, project_id: str, user_id: str
    ) -> None:
        template = await self.get(db, project_id=project_id, user_id=user_id)
        if template is None:
            return
        await db.delete(template)

    # ── Skills ──────────────────────────────────────────────────
    async def list_skills(
        self, db: AsyncSession, *, project_id: str, user_id: str
    ) -> list[TemplateSkill]:
        template = await self._get_or_create(
            db, project_id=project_id, user_id=user_id
        )
        result = await db.execute(
            select(TemplateSkill)
            .where(TemplateSkill.template_id == template.id)
            .order_by(TemplateSkill.name.asc())
        )
        return list(result.scalars().all())

    async def create_skill(
        self,
        db: AsyncSession,
        *,
        project_id: str,
        user_id: str,
        payload: TemplateSkillWrite,
    ) -> TemplateSkill:
        template = await self._get_or_create(
            db, project_id=project_id, user_id=user_id
        )
        # Unique constraint sur (template_id, name) → check explicite pour
        # une erreur 409 lisible.
        existing = await db.execute(
            select(TemplateSkill).where(
                TemplateSkill.template_id == template.id,
                TemplateSkill.name == payload.name,
            )
        )
        if existing.scalar_one_or_none() is not None:
            raise ConflictError(
                f"Un skill `{payload.name}` existe déjà pour ce projet."
            )
        skill = TemplateSkill(
            template_id=template.id,
            name=payload.name,
            description=payload.description,
            content=payload.content,
        )
        db.add(skill)
        await db.flush()
        return skill

    async def update_skill(
        self,
        db: AsyncSession,
        *,
        project_id: str,
        user_id: str,
        skill_id: str,
        payload: TemplateSkillWrite,
    ) -> TemplateSkill:
        skill = await self._require_skill(
            db, project_id=project_id, user_id=user_id, skill_id=skill_id
        )
        if skill.name != payload.name:
            # conflict si le nouveau name est déjà pris dans le même template
            existing = await db.execute(
                select(TemplateSkill).where(
                    TemplateSkill.template_id == skill.template_id,
                    TemplateSkill.name == payload.name,
                    TemplateSkill.id != skill_id,
                )
            )
            if existing.scalar_one_or_none() is not None:
                raise ConflictError(
                    f"Un skill `{payload.name}` existe déjà pour ce projet."
                )
        skill.name = payload.name
        skill.description = payload.description
        skill.content = payload.content
        await db.flush()
        return skill

    async def delete_skill(
        self,
        db: AsyncSession,
        *,
        project_id: str,
        user_id: str,
        skill_id: str,
    ) -> None:
        skill = await self._require_skill(
            db, project_id=project_id, user_id=user_id, skill_id=skill_id
        )
        await db.delete(skill)

    async def _require_skill(
        self,
        db: AsyncSession,
        *,
        project_id: str,
        user_id: str,
        skill_id: str,
    ) -> TemplateSkill:
        template = await self._get_or_create(
            db, project_id=project_id, user_id=user_id
        )
        result = await db.execute(
            select(TemplateSkill).where(
                TemplateSkill.id == skill_id,
                TemplateSkill.template_id == template.id,
            )
        )
        skill = result.scalar_one_or_none()
        if skill is None:
            raise NotFoundError(f"Skill {skill_id} introuvable.")
        return skill

    # ── Sub-agents ──────────────────────────────────────────────
    async def list_sub_agents(
        self, db: AsyncSession, *, project_id: str, user_id: str
    ) -> list[TemplateSubAgent]:
        template = await self._get_or_create(
            db, project_id=project_id, user_id=user_id
        )
        result = await db.execute(
            select(TemplateSubAgent)
            .where(TemplateSubAgent.template_id == template.id)
            .order_by(TemplateSubAgent.name.asc())
        )
        return list(result.scalars().all())

    async def create_sub_agent(
        self,
        db: AsyncSession,
        *,
        project_id: str,
        user_id: str,
        payload: TemplateSubAgentWrite,
    ) -> TemplateSubAgent:
        template = await self._get_or_create(
            db, project_id=project_id, user_id=user_id
        )
        existing = await db.execute(
            select(TemplateSubAgent).where(
                TemplateSubAgent.template_id == template.id,
                TemplateSubAgent.name == payload.name,
            )
        )
        if existing.scalar_one_or_none() is not None:
            raise ConflictError(
                f"Un sub-agent `{payload.name}` existe déjà pour ce projet."
            )
        agent = TemplateSubAgent(
            template_id=template.id,
            name=payload.name,
            description=payload.description,
            system_prompt=payload.system_prompt,
            allowed_tools=payload.allowed_tools,
        )
        db.add(agent)
        await db.flush()
        return agent

    async def update_sub_agent(
        self,
        db: AsyncSession,
        *,
        project_id: str,
        user_id: str,
        agent_id: str,
        payload: TemplateSubAgentWrite,
    ) -> TemplateSubAgent:
        agent = await self._require_sub_agent(
            db, project_id=project_id, user_id=user_id, agent_id=agent_id
        )
        if agent.name != payload.name:
            existing = await db.execute(
                select(TemplateSubAgent).where(
                    TemplateSubAgent.template_id == agent.template_id,
                    TemplateSubAgent.name == payload.name,
                    TemplateSubAgent.id != agent_id,
                )
            )
            if existing.scalar_one_or_none() is not None:
                raise ConflictError(
                    f"Un sub-agent `{payload.name}` existe déjà pour ce projet."
                )
        agent.name = payload.name
        agent.description = payload.description
        agent.system_prompt = payload.system_prompt
        agent.allowed_tools = payload.allowed_tools
        await db.flush()
        return agent

    async def delete_sub_agent(
        self,
        db: AsyncSession,
        *,
        project_id: str,
        user_id: str,
        agent_id: str,
    ) -> None:
        agent = await self._require_sub_agent(
            db, project_id=project_id, user_id=user_id, agent_id=agent_id
        )
        await db.delete(agent)

    async def _require_sub_agent(
        self,
        db: AsyncSession,
        *,
        project_id: str,
        user_id: str,
        agent_id: str,
    ) -> TemplateSubAgent:
        template = await self._get_or_create(
            db, project_id=project_id, user_id=user_id
        )
        result = await db.execute(
            select(TemplateSubAgent).where(
                TemplateSubAgent.id == agent_id,
                TemplateSubAgent.template_id == template.id,
            )
        )
        agent = result.scalar_one_or_none()
        if agent is None:
            raise NotFoundError(f"Sub-agent {agent_id} introuvable.")
        return agent


    # ── Versionnage (Chantier 6) ────────────────────────────────
    def _snapshot(self, template: MissionTemplate) -> dict:
        """Sérialise template + skills + sub-agents en JSON pour stockage."""
        return {
            "system_prompt": template.system_prompt,
            "model": template.model,
            "allowed_tools": template.allowed_tools,
            "source_preset": template.source_preset,
            "skills": [
                {
                    "name": s.name,
                    "description": s.description,
                    "content": s.content,
                }
                for s in template.skills
            ],
            "sub_agents": [
                {
                    "name": a.name,
                    "description": a.description,
                    "system_prompt": a.system_prompt,
                    "allowed_tools": a.allowed_tools,
                }
                for a in template.sub_agents
            ],
        }

    async def snapshot(
        self,
        db: AsyncSession,
        *,
        project_id: str,
        user_id: str,
        note: str | None = None,
    ) -> TemplateVersion | None:
        """Crée une nouvelle entrée TemplateVersion. No-op si pas de template."""
        template = await self.get(db, project_id=project_id, user_id=user_id)
        if template is None:
            return None
        # version_index = max + 1
        result = await db.execute(
            select(TemplateVersion)
            .where(TemplateVersion.template_id == template.id)
            .order_by(TemplateVersion.version_index.desc())
        )
        latest = result.scalars().first()
        next_index = (latest.version_index + 1) if latest else 1
        version = TemplateVersion(
            template_id=template.id,
            version_index=next_index,
            snapshot=self._snapshot(template),
            note=note,
        )
        db.add(version)
        await db.flush()
        return version

    async def list_versions(
        self, db: AsyncSession, *, project_id: str, user_id: str
    ) -> list[TemplateVersion]:
        template = await self.get(db, project_id=project_id, user_id=user_id)
        if template is None:
            return []
        result = await db.execute(
            select(TemplateVersion)
            .where(TemplateVersion.template_id == template.id)
            .order_by(TemplateVersion.version_index.desc())
        )
        return list(result.scalars().all())

    async def restore_version(
        self,
        db: AsyncSession,
        *,
        project_id: str,
        user_id: str,
        version_id: str,
        note: str | None = None,
    ) -> MissionTemplate:
        """Restaure une version : snapshot l'état courant, puis applique l'ancien.

        On crée toujours un snapshot AVANT la restauration pour pouvoir
        défaire en cas d'erreur.
        """
        template = await self._get_or_create(
            db, project_id=project_id, user_id=user_id
        )
        result = await db.execute(
            select(TemplateVersion).where(
                TemplateVersion.id == version_id,
                TemplateVersion.template_id == template.id,
            )
        )
        version = result.scalar_one_or_none()
        if version is None:
            raise NotFoundError(f"Version {version_id} introuvable.")

        # Snapshot de l'état courant avant écrasement
        await self.snapshot(
            db,
            project_id=project_id,
            user_id=user_id,
            note=note or f"avant restauration v{version.version_index}",
        )

        snap = version.snapshot
        template.system_prompt = snap.get("system_prompt")
        template.model = snap.get("model")
        template.allowed_tools = snap.get("allowed_tools")
        template.source_preset = snap.get("source_preset")

        # Skills et sub-agents : on remplace tout
        for s in list(template.skills):
            await db.delete(s)
        for a in list(template.sub_agents):
            await db.delete(a)
        await db.flush()

        for s in snap.get("skills", []):
            db.add(
                TemplateSkill(
                    template_id=template.id,
                    name=s["name"],
                    description=s.get("description"),
                    content=s["content"],
                )
            )
        for a in snap.get("sub_agents", []):
            db.add(
                TemplateSubAgent(
                    template_id=template.id,
                    name=a["name"],
                    description=a.get("description"),
                    system_prompt=a["system_prompt"],
                    allowed_tools=a.get("allowed_tools"),
                )
            )
        await db.flush()
        return template

    # ── Matérialisation sur disque (Chantier 3) ─────────────────
    async def materialize_to_worktree(
        self,
        db: AsyncSession,
        *,
        project_id: str,
        user_id: str,
        worktree_path: Path,
        extra_sub_agents: list[InlineSubAgent] | None = None,
    ) -> MissionTemplate | None:
        """Écrit les skills et sub-agents du template dans le worktree.

        - `.claude/skills/{name}/SKILL.md` par skill
        - `.claude/agents/{name}.md` par sub-agent

        `extra_sub_agents` permet au caller d'ajouter des sub-agents
        "système" matérialisés à la volée (ex. mask-data quand Ollama
        est exposé). Les noms en collision avec un sub-agent du template
        ne sont PAS écrasés - le template utilisateur prime.

        Le worktree est isolé (Phase 2) → pas de risque de pollution entre
        sessions. Retourne le template chargé pour que le caller puisse
        aussi récupérer system_prompt/model/allowed_tools.
        """
        template = await self.get(db, project_id=project_id, user_id=user_id)
        if template is None:
            return None
        skills_root = worktree_path / ".claude" / "skills"
        agents_root = worktree_path / ".claude" / "agents"
        for skill in template.skills:
            try:
                _materialize_skill(skills_root, skill)
            except OSError:
                logger.exception(
                    "template.skill.materialize.failed",
                    skill=skill.name,
                    worktree=str(worktree_path),
                )
        existing_agent_names = {a.name for a in template.sub_agents}
        for agent in template.sub_agents:
            try:
                _materialize_sub_agent(agents_root, agent)
            except OSError:
                logger.exception(
                    "template.sub_agent.materialize.failed",
                    agent=agent.name,
                    worktree=str(worktree_path),
                )
        for extra in extra_sub_agents or []:
            if extra.name in existing_agent_names:
                logger.info(
                    "template.extra_sub_agent.skipped_collision",
                    agent=extra.name,
                )
                continue
            try:
                _materialize_sub_agent(agents_root, extra)
            except OSError:
                logger.exception(
                    "template.extra_sub_agent.materialize.failed",
                    agent=extra.name,
                    worktree=str(worktree_path),
                )
        return template


mission_template_service = MissionTemplateService()
