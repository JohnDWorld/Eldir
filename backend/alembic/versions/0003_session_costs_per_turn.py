"""session_costs: une ligne par tour de conversation + dimensions.

Avant : 1 ligne / session (agrégat). Après : 1 ligne / ResultMessage SDK,
avec project_id, user_id, model et duration_ms pour permettre des
agrégations par jour / projet / modèle (Phase 5 du ROADMAP).

Revision ID: 0003
Revises: 0002
Create Date: 2026-05-20
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | Sequence[str] | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Les lignes existantes (s'il y en a) étaient des agrégats par session :
    # on les efface plutôt que de tenter une migration data hasardeuse.
    op.execute("DELETE FROM session_costs")

    op.add_column(
        "session_costs",
        sa.Column("project_id", sa.String(length=36), nullable=True),
    )
    op.add_column(
        "session_costs",
        sa.Column("user_id", sa.String(length=36), nullable=True),
    )
    op.add_column(
        "session_costs",
        sa.Column("model", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "session_costs",
        sa.Column(
            "duration_ms", sa.Integer(), nullable=False, server_default="0"
        ),
    )
    op.add_column(
        "session_costs",
        sa.Column("num_turns", sa.Integer(), nullable=False, server_default="1"),
    )

    op.create_foreign_key(
        "fk_session_costs_project_id",
        "session_costs",
        "projects",
        ["project_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_session_costs_user_id",
        "session_costs",
        "users",
        ["user_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_session_costs_project_id", "session_costs", ["project_id"]
    )
    op.create_index("ix_session_costs_user_id", "session_costs", ["user_id"])
    op.create_index("ix_session_costs_model", "session_costs", ["model"])
    op.create_index(
        "ix_session_costs_created_at", "session_costs", ["created_at"]
    )


def downgrade() -> None:
    op.drop_index("ix_session_costs_created_at", table_name="session_costs")
    op.drop_index("ix_session_costs_model", table_name="session_costs")
    op.drop_index("ix_session_costs_user_id", table_name="session_costs")
    op.drop_index("ix_session_costs_project_id", table_name="session_costs")
    op.drop_constraint(
        "fk_session_costs_user_id", "session_costs", type_="foreignkey"
    )
    op.drop_constraint(
        "fk_session_costs_project_id", "session_costs", type_="foreignkey"
    )
    op.drop_column("session_costs", "num_turns")
    op.drop_column("session_costs", "duration_ms")
    op.drop_column("session_costs", "model")
    op.drop_column("session_costs", "user_id")
    op.drop_column("session_costs", "project_id")
