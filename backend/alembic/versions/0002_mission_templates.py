"""mission templates - system prompt / model / outils / skills / sub-agents par projet.

Phase 4 du ROADMAP : MissionTemplate (1↔1 projet), TemplateSkill,
TemplateSubAgent, TemplateVersion (historique snapshots).

Revision ID: 0002
Revises: 0001
Create Date: 2026-05-14
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | Sequence[str] | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "mission_templates",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("project_id", sa.String(length=36), nullable=False),
        sa.Column("system_prompt", sa.Text(), nullable=True),
        sa.Column("model", sa.String(length=64), nullable=True),
        sa.Column("allowed_tools", sa.JSON(), nullable=True),
        sa.Column("source_preset", sa.String(length=64), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("project_id", name="uq_mission_templates_project_id"),
    )
    op.create_index(
        "ix_mission_templates_project_id", "mission_templates", ["project_id"]
    )

    op.create_table(
        "template_skills",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("template_id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("description", sa.String(length=255), nullable=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["template_id"], ["mission_templates.id"], ondelete="CASCADE"
        ),
        sa.UniqueConstraint(
            "template_id", "name", name="uq_template_skills_template_name"
        ),
    )
    op.create_index(
        "ix_template_skills_template_id", "template_skills", ["template_id"]
    )

    op.create_table(
        "template_sub_agents",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("template_id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("description", sa.String(length=255), nullable=True),
        sa.Column("system_prompt", sa.Text(), nullable=False),
        sa.Column("allowed_tools", sa.JSON(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["template_id"], ["mission_templates.id"], ondelete="CASCADE"
        ),
        sa.UniqueConstraint(
            "template_id", "name", name="uq_template_sub_agents_template_name"
        ),
    )
    op.create_index(
        "ix_template_sub_agents_template_id",
        "template_sub_agents",
        ["template_id"],
    )

    op.create_table(
        "template_versions",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("template_id", sa.String(length=36), nullable=False),
        sa.Column("version_index", sa.Integer(), nullable=False),
        sa.Column("snapshot", sa.JSON(), nullable=False),
        sa.Column("note", sa.String(length=255), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["template_id"], ["mission_templates.id"], ondelete="CASCADE"
        ),
    )
    op.create_index(
        "ix_template_versions_template_id",
        "template_versions",
        ["template_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_template_versions_template_id", table_name="template_versions"
    )
    op.drop_table("template_versions")
    op.drop_index(
        "ix_template_sub_agents_template_id", table_name="template_sub_agents"
    )
    op.drop_table("template_sub_agents")
    op.drop_index(
        "ix_template_skills_template_id", table_name="template_skills"
    )
    op.drop_table("template_skills")
    op.drop_index(
        "ix_mission_templates_project_id", table_name="mission_templates"
    )
    op.drop_table("mission_templates")
