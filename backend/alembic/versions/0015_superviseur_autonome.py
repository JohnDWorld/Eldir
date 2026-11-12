"""Un projet peut être autonome : le superviseur y merge et y déploie seul.

`projects.autonomous` est le consentement de John, projet par projet : décoché,
le superviseur ouvre les PR et John merge. `projects.deploy_command` est la
seule commande que le superviseur peut lancer sur la machine du projet ; vide,
la forge déploie au merge. `sessions.pr_number` retient la PR qu'Eldir a ouverte
pour une session, celle qu'un second `open_pr` met à jour et que `merge` vise.

Revision ID: 0015
Revises: 0014
Create Date: 2026-11-12
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0015"
down_revision: str | Sequence[str] | None = "0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "projects",
        sa.Column("autonomous", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column("projects", sa.Column("deploy_command", sa.Text(), nullable=True))
    op.add_column("sessions", sa.Column("pr_number", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("sessions", "pr_number")
    op.drop_column("projects", "deploy_command")
    op.drop_column("projects", "autonomous")
