"""sessions.is_system + sessions.system_kind : flag pour les sessions
internes lancées par Eldir lui-même (génération de template, etc.).

Cf. principe directeur : aucune session "cachée" - tout ce qui consomme
des tokens reste visible dans le dashboard. Le flag permet juste de
filtrer/distinguer dans l'UI.

Revision ID: 0005
Revises: 0004
Create Date: 2026-05-21
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: str | Sequence[str] | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "sessions",
        sa.Column(
            "is_system",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.add_column(
        "sessions",
        sa.Column("system_kind", sa.String(length=64), nullable=True),
    )
    op.create_index("ix_sessions_is_system", "sessions", ["is_system"])


def downgrade() -> None:
    op.drop_index("ix_sessions_is_system", table_name="sessions")
    op.drop_column("sessions", "system_kind")
    op.drop_column("sessions", "is_system")
