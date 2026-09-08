"""sessions.publish_allowed : autorisation de publier, donnée par John.

La publication (commit, push, PR) est refusée par défaut au niveau du hook
`PreToolUse` : c'est la porte de validation humaine. Mais John doit pouvoir
dire « fais la PR » et que ça marche, sans aller cliquer dans le dashboard.
D'où un drapeau par session, qu'il donne (depuis l'UI ou en le demandant au
superviseur) et qu'il retire quand il veut.

Revision ID: 0009
Revises: 0008
Create Date: 2026-09-08
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0009"
down_revision: str | Sequence[str] | None = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "sessions",
        sa.Column(
            "publish_allowed",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )


def downgrade() -> None:
    op.drop_column("sessions", "publish_allowed")
