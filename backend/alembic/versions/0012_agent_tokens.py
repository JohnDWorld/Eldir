"""Jetons d'agent externe, révocables.

Les cinq outils du superviseur s'ouvrent à un agent extérieur par MCP sur
HTTP. Un agent tourne en continu : son jeton vit des mois, là où le JWT de
connexion vit une heure. Cette table est la liste blanche des `jti` valides,
donc le seul moyen de couper un accès sans faire tourner la clé de l'instance.

Revision ID: 0012
Revises: 0011
Create Date: 2026-10-29
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0012"
down_revision: str | Sequence[str] | None = "0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "agent_tokens",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), nullable=False),
        sa.Column("label", sa.String(80), nullable=False),
        sa.Column("jti", sa.String(36), nullable=False),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        # L'unicité crée l'index de recherche par `jti` : pas d'index en double.
        sa.UniqueConstraint("jti", name="uq_agent_tokens_jti"),
    )
    op.create_index("ix_agent_tokens_user_id", "agent_tokens", ["user_id"])
    # Deux jetons vivants au même libellé seraient indiscernables : la
    # documentation présente `demandeur` comme le champ qui dit qui a décidé, et
    # le fil comme la liste n'affichent que ce libellé. La révocation étant par
    # jeton, John ne saurait pas lequel couper. Partielle sur les jetons non
    # révoqués : réémettre après révocation est le geste de secours documenté
    # quand un jeton a fuité, et il reprend le même libellé.
    op.create_index(
        "uq_agent_tokens_user_label_vivant",
        "agent_tokens",
        ["user_id", "label"],
        unique=True,
        sqlite_where=sa.text("revoked_at IS NULL"),
        postgresql_where=sa.text("revoked_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_agent_tokens_user_label_vivant", table_name="agent_tokens")
    op.drop_index("ix_agent_tokens_user_id", table_name="agent_tokens")
    op.drop_table("agent_tokens")
