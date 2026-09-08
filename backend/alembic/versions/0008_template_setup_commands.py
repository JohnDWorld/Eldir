"""mission_templates.setup_commands : le toolchain déclaré du projet.

Un repo Flutter a besoin du SDK Flutter pour que l'agent puisse lancer
`flutter analyze`, un repo Go a besoin de Go, etc. Le conteneur ne peut pas
tout embarquer (15 Go d'images, et Flutter installé pour un projet Python),
donc chaque projet déclare les commandes qui installent ce qu'il lui faut,
une fois, dans un volume partagé par ses sessions.

Revision ID: 0008
Revises: 0007
Create Date: 2026-09-08
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0008"
down_revision: str | Sequence[str] | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "mission_templates",
        sa.Column("setup_commands", sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("mission_templates", "setup_commands")
