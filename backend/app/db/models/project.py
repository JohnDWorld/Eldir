"""Modèle Project - un repo Git lié à un provider (GitHub/Forgejo)."""

from __future__ import annotations

from sqlalchemy import Boolean, ForeignKey, String, Text, false
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKey


class Project(UUIDPrimaryKey, TimestampMixin, Base):
    __tablename__ = "projects"

    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    slug: Mapped[str] = mapped_column(String(120), index=True, nullable=False)
    provider: Mapped[str] = mapped_column(String(20), nullable=False)  # github | forgejo
    repo_full_name: Mapped[str] = mapped_column(String(255), nullable=False)  # owner/repo
    default_branch: Mapped[str] = mapped_column(String(120), default="main", nullable=False)
    workspace_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    # Le consentement de John : le superviseur merge et déploie seul ici.
    autonomous: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=false(), nullable=False
    )
    # La seule commande que le superviseur peut lancer sur la machine du projet.
    # Vide : la forge déploie au merge.
    deploy_command: Mapped[str | None] = mapped_column(Text, nullable=True)
