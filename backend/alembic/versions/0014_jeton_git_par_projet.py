"""Un jeton Git peut être limité à un seul projet.

Jusqu'ici un jeton valait pour (utilisateur, provider) : un seul PAT servait
tous les dépôts, donc sa fuite les exposait tous. Les sessions tournent en
`bypassPermissions` sur des consignes qui peuvent venir de l'extérieur : mieux
vaut qu'un jeton compromis ne porte que sur le dépôt qu'il sert.

`project_id` NULL = jeton global, le comportement d'avant, et le repli quand un
projet n'a pas le sien. Les lignes existantes restent donc globales.

Côté provider, c'est le jeton lui-même qui doit être restreint : PAT
fine-grained GitHub limité à ce dépôt, jeton d'accès Forgejo par dépôt. Eldir
permet d'en avoir un par projet, il ne peut pas en réduire la portée à la
place du provider.

Revision ID: 0014
Revises: 0013
Create Date: 2026-10-30
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0014"
down_revision: str | Sequence[str] | None = "0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "git_credentials",
        sa.Column("project_id", sa.String(36), nullable=True),
    )
    op.create_foreign_key(
        "fk_git_credentials_project_id",
        "git_credentials",
        "projects",
        ["project_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index(
        "ix_git_credentials_project_id",
        "git_credentials",
        ["project_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_git_credentials_project_id", table_name="git_credentials")
    op.drop_constraint("fk_git_credentials_project_id", "git_credentials", type_="foreignkey")
    op.drop_column("git_credentials", "project_id")
