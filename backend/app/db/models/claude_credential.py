"""ClaudeCredential - token Pro/Max et/ou API key Console, chiffrés en DB."""

from __future__ import annotations

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKey


class ClaudeCredential(UUIDPrimaryKey, TimestampMixin, Base):
    __tablename__ = "claude_credentials"

    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    kind: Mapped[str] = mapped_column(String(20), nullable=False)  # oauth_token | api_key
    label: Mapped[str | None] = mapped_column(String(120), nullable=True)
    encrypted_value: Mapped[str] = mapped_column(Text, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_validated_at: Mapped[str | None] = mapped_column(DateTime(timezone=True), nullable=True)
