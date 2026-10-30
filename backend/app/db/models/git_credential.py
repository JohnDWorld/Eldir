"""Credentials Git provider (chiffrés en DB via Fernet)."""

from __future__ import annotations

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKey


class GitCredential(UUIDPrimaryKey, TimestampMixin, Base):
    __tablename__ = "git_credentials"

    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    # NULL = jeton global de l'utilisateur, le défaut. Renseigné, le jeton ne
    # sert qu'à ce projet : sa fuite n'expose que le dépôt qu'il sert, à
    # condition qu'il soit lui-même restreint côté provider (PAT fine-grained
    # GitHub, jeton par dépôt Forgejo). Cf. `docs/securite-sessions.md`.
    project_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("projects.id", ondelete="CASCADE"), index=True, nullable=True
    )
    provider: Mapped[str] = mapped_column(String(20), nullable=False)
    base_url: Mapped[str | None] = mapped_column(String(255), nullable=True)
    label: Mapped[str | None] = mapped_column(String(120), nullable=True)
    # Toujours stocker chiffré (utiliser security.encrypt_secret avant insertion)
    encrypted_token: Mapped[str] = mapped_column(Text, nullable=False)
