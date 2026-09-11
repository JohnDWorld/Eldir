"""Accès serveur déclaré par projet, figé à la création de session.

Déclarer fichier par fichier ce qu'une session doit lire (collecte, 0010) ne
passe pas à l'échelle : sur un projet déployé, l'agent a besoin de parcourir
la machine, pas de recevoir trois fichiers choisis d'avance.

Le projet déclare donc un alias SSH, et ses sessions peuvent s'y connecter.
La colonne est dupliquée sur `sessions` pour que l'accès d'une session soit
fixé au moment où elle est créée : changer l'alias du projet ne change pas ce
qu'une session déjà lancée peut atteindre, et un `resume` repart avec
exactement le même périmètre.

Revision ID: 0011
Revises: 0010
Create Date: 2026-09-11
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0011"
down_revision: str | Sequence[str] | None = "0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("mission_templates", sa.Column("remote_host", sa.String(120), nullable=True))
    op.add_column("sessions", sa.Column("remote_host", sa.String(120), nullable=True))


def downgrade() -> None:
    op.drop_column("sessions", "remote_host")
    op.drop_column("mission_templates", "remote_host")
