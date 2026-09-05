"""ollama_settings : singleton des préférences utilisateur pour Ollama.

Pour l'instant juste le flag expose_to_sessions (injection auto du
sub-agent 'mask-data' dans les sessions). Phase 6+ du ROADMAP.

Revision ID: 0006
Revises: 0005
Create Date: 2026-05-24
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006"
down_revision: str | Sequence[str] | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "ollama_settings",
        sa.Column("id", sa.String(length=16), primary_key=True),
        sa.Column(
            "expose_to_sessions",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
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
    )
    # Seed la ligne singleton au défaut (désactivé)
    op.execute("INSERT INTO ollama_settings (id, expose_to_sessions) VALUES ('singleton', false)")


def downgrade() -> None:
    op.drop_table("ollama_settings")
