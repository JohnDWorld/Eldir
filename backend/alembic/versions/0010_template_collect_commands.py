"""mission_templates.collect_commands : la collecte distante déclarée.

Le code d'un projet ne tient pas toujours dans son repo : une passerelle qui
vit dans une image Docker, une config générée sur l'hôte, un log de prod. La
session, elle, ne voit que son worktree.

Plutôt que d'ouvrir un shell distant à l'agent, le projet déclare quoi
ramener : une commande par fichier. Eldir les lance à la création de session,
dépose le résultat en dehors du worktree (`$ELDIR_COLLECTE`) pour qu'il ne
puisse pas partir dans un commit, et l'agent lit des fichiers.

Revision ID: 0010
Revises: 0009
Create Date: 2026-09-10
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0010"
down_revision: str | Sequence[str] | None = "0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "mission_templates",
        sa.Column("collect_commands", sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("mission_templates", "collect_commands")
