"""Un projet peut être alimenté par une source externe, donc non fiable.

La surface d'agent externe (0012) sert à transmettre à Eldir des suggestions
et des tickets écrits par des utilisateurs de La Boutique. Ce texte arrive
jusqu'à des sessions qui tournent en `bypassPermissions` : une injection de
prompt y est un scénario normal, pas un cas limite.

Le drapeau marque les projets concernés. Il annule l'accès SSH « Machine du
projet » (`remote_host`, 0011) sans effacer l'alias, et les consignes reçues
sont présentées à la session comme des données, pas comme des instructions de
son propriétaire.

`false` par défaut : un projet n'est pas alimenté de l'extérieur sans que
quelqu'un le dise.

Revision ID: 0013
Revises: 0012
Create Date: 2026-10-30
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0013"
down_revision: str | Sequence[str] | None = "0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "mission_templates",
        sa.Column(
            "source_externe",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )


def downgrade() -> None:
    op.drop_column("mission_templates", "source_externe")
