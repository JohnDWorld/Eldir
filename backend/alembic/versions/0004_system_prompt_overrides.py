"""system_prompt_overrides : override utilisateur des prompts Eldir.

Cf. Phase 5+ (Mission Template generator) - l'utilisateur peut éditer
les prompts système qu'Eldir envoie à ses propres sessions internes
(génération de template, etc.). Le défaut vit en fichier git.

Revision ID: 0004
Revises: 0003
Create Date: 2026-05-21
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: str | Sequence[str] | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "system_prompt_overrides",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("slug", sa.String(length=64), nullable=False),
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
        sa.UniqueConstraint("slug", name="uq_system_prompt_overrides_slug"),
    )
    op.create_index(
        "ix_system_prompt_overrides_slug",
        "system_prompt_overrides",
        ["slug"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_system_prompt_overrides_slug",
        table_name="system_prompt_overrides",
    )
    op.drop_table("system_prompt_overrides")
