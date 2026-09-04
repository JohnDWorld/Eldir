"""sessions.project_id nullable : la session superviseur n'a pas de repo.

Le superviseur (system_kind='supervisor') est une session Claude comme les
autres - visible, facturée, streamée - mais elle ne travaille sur aucun
worktree : elle pilote les sessions projet via ses outils Eldir.

Revision ID: 0007
Revises: 0006
Create Date: 2026-09-04
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0007"
down_revision: str | Sequence[str] | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column(
        "sessions",
        "project_id",
        existing_type=sa.String(length=36),
        nullable=True,
    )


def downgrade() -> None:
    # Les sessions sans projet (superviseur) n'ont pas d'équivalent dans
    # l'ancien schéma : on les supprime, leurs events/coûts partent en cascade.
    op.execute("DELETE FROM sessions WHERE project_id IS NULL")
    op.alter_column(
        "sessions",
        "project_id",
        existing_type=sa.String(length=36),
        nullable=False,
    )
