"""Modèles MissionTemplate - Phase 4 du ROADMAP.

Un projet possède 0..1 MissionTemplate qui décrit son system prompt, son
modèle préféré, les outils autorisés, et 0..N skills + sub-agents
matérialisés sur disque (`.claude/skills/` / `.claude/agents/`) à la
création d'une session.
"""

from __future__ import annotations

from sqlalchemy import JSON, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKey


class MissionTemplate(UUIDPrimaryKey, TimestampMixin, Base):
    """Configuration applicative d'un projet (one-to-one avec `projects`)."""

    __tablename__ = "mission_templates"
    __table_args__ = (
        UniqueConstraint("project_id", name="uq_mission_templates_project_id"),
    )

    project_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("projects.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    # NULL → on retombe sur le default du serveur côté session_service.
    system_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    model: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # NULL ou liste vide → tous les outils built-in sont autorisés.
    allowed_tools: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    # Référence informative quand on a appliqué un preset (slug du preset).
    source_preset: Mapped[str | None] = mapped_column(String(64), nullable=True)

    skills: Mapped[list["TemplateSkill"]] = relationship(
        "TemplateSkill",
        cascade="all, delete-orphan",
        back_populates="template",
        order_by="TemplateSkill.name",
    )
    sub_agents: Mapped[list["TemplateSubAgent"]] = relationship(
        "TemplateSubAgent",
        cascade="all, delete-orphan",
        back_populates="template",
        order_by="TemplateSubAgent.name",
    )


class TemplateSkill(UUIDPrimaryKey, TimestampMixin, Base):
    """Un skill markdown - matérialisé en `.claude/skills/{name}.md`."""

    __tablename__ = "template_skills"
    __table_args__ = (
        UniqueConstraint(
            "template_id", "name", name="uq_template_skills_template_name"
        ),
    )

    template_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("mission_templates.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    # Slug filesystem-safe (validé côté schema).
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)

    template: Mapped["MissionTemplate"] = relationship(
        "MissionTemplate", back_populates="skills"
    )


class TemplateSubAgent(UUIDPrimaryKey, TimestampMixin, Base):
    """Un sub-agent - matérialisé en `.claude/agents/{name}.md`."""

    __tablename__ = "template_sub_agents"
    __table_args__ = (
        UniqueConstraint(
            "template_id", "name", name="uq_template_sub_agents_template_name"
        ),
    )

    template_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("mission_templates.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)
    system_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    allowed_tools: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)

    template: Mapped["MissionTemplate"] = relationship(
        "MissionTemplate", back_populates="sub_agents"
    )


class TemplateVersion(UUIDPrimaryKey, TimestampMixin, Base):
    """Snapshot complet d'un template à un instant donné (Chantier 6).

    Stocké en JSON pour pouvoir restaurer template + skills + sub-agents
    en bloc sans gérer des FK temporelles.
    """

    __tablename__ = "template_versions"

    template_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("mission_templates.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    version_index: Mapped[int] = mapped_column(Integer, nullable=False)
    snapshot: Mapped[dict] = mapped_column(JSON, nullable=False)
    note: Mapped[str | None] = mapped_column(String(255), nullable=True)
