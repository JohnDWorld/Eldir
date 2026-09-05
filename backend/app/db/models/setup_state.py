"""SetupState - singleton qui pilote le bootstrap au premier boot."""

from __future__ import annotations

from sqlalchemy import Boolean, DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKey


class SetupState(UUIDPrimaryKey, TimestampMixin, Base):
    """Row unique (id='singleton') qui matérialise l'état d'installation."""

    __tablename__ = "setup_state"

    bootstrap_token_hash: Mapped[str | None] = mapped_column(Text, nullable=True)
    bootstrap_completed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    bootstrap_completed_at: Mapped[str | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    eldir_version: Mapped[str | None] = mapped_column(String(32), nullable=True)
