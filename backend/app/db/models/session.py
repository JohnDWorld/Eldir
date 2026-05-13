"""Modèles Session et SessionEvent — coeur du domaine Eldir."""

from __future__ import annotations

from sqlalchemy import JSON, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.constants import SESSION_STATE_IDLE
from app.db.base import Base, TimestampMixin, UUIDPrimaryKey


class Session(UUIDPrimaryKey, TimestampMixin, Base):
    """Une session = un ClaudeSDKClient (cf. AGENTS.md §Sessions Claude)."""

    __tablename__ = "sessions"

    project_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("projects.id", ondelete="CASCADE"), index=True, nullable=False
    )
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )

    # session_id côté SDK Claude (capturé au premier message, peut être null avant)
    sdk_session_id: Mapped[str | None] = mapped_column(
        String(64), unique=True, index=True, nullable=True
    )

    branch: Mapped[str] = mapped_column(String(255), nullable=False)
    worktree_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    state: Mapped[str] = mapped_column(String(32), default=SESSION_STATE_IDLE, nullable=False)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    model: Mapped[str | None] = mapped_column(String(64), nullable=True)
    system_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)


class SessionEvent(UUIDPrimaryKey, TimestampMixin, Base):
    """Event SDK persisté (text / tool_use / tool_result / state / stop / error)."""

    __tablename__ = "session_events"

    session_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("sessions.id", ondelete="CASCADE"), index=True, nullable=False
    )
    type: Mapped[str] = mapped_column(String(32), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)


class SessionCost(UUIDPrimaryKey, TimestampMixin, Base):
    """Tracking de coût agrégé par session (alimenté par OTel SDK)."""

    __tablename__ = "session_costs"

    session_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("sessions.id", ondelete="CASCADE"), index=True, nullable=False
    )
    input_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    cache_read_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    cache_write_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    cost_usd: Mapped[float] = mapped_column(Numeric(10, 6), default=0, nullable=False)
