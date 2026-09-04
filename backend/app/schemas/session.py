"""Schemas Session + events streamés vers le frontend."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import Field

from app.schemas.common import EldirModel, TimestampedModel

SessionState = Literal["idle", "thinking", "tool_use", "waiting_input", "blocked"]
SessionEventType = Literal[
    "text",
    "tool_use",
    "tool_result",
    "state",
    "stop",
    "error",
    "user_message",
    "usage",
]


class SessionCreate(EldirModel):
    project_id: str
    system_prompt: str | None = None
    model: str | None = None


class SessionEventRead(TimestampedModel):
    id: str
    session_id: str
    type: SessionEventType
    payload: dict[str, Any]


class SessionRead(TimestampedModel):
    id: str
    # None pour la session superviseur (pas de repo rattaché).
    project_id: str | None
    user_id: str
    sdk_session_id: str | None
    branch: str
    worktree_path: str | None
    state: SessionState
    summary: str | None
    model: str | None
    is_system: bool = False
    system_kind: str | None = None


class SessionSummary(EldirModel):
    """Vue compacte pour la liste sessions (D1 Mission Control)."""

    id: str
    project_slug: str
    state: SessionState
    summary: str | None
    duration_seconds: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0


class SessionMessageInput(EldirModel):
    """Message envoyé par l'utilisateur à une session."""

    content: str = Field(min_length=1, max_length=64_000)


# ── Git ops (chantier 5) ───────────────────────────────────────
class GitStatusResponse(EldirModel):
    branch: str
    has_changes: bool
    modified: int = 0
    added: int = 0
    deleted: int = 0
    untracked: int = 0


class CommitPushRequest(EldirModel):
    message: str = Field(min_length=1, max_length=1000)
    push: bool = True


class CommitPushResponse(EldirModel):
    branch: str
    sha: str
    pushed: bool


class OpenPullRequestRequest(EldirModel):
    title: str = Field(min_length=1, max_length=255)
    body: str | None = Field(default=None, max_length=8000)
    base: str | None = Field(default=None, max_length=120)


class OpenPullRequestResponse(EldirModel):
    pr_number: int
    pr_url: str
    head: str
    base: str
    title: str


# ── Diff ──────────────────────────────────────────────────────
class SessionDiffFile(EldirModel):
    path: str
    status: str  # A | M | D | R | C | U | T
    additions: int
    deletions: int


class SessionDiffSummary(EldirModel):
    base_ref: str
    head_branch: str
    files: list[SessionDiffFile]


class SessionDiffFilePatch(EldirModel):
    path: str
    base_ref: str
    patch: str


# ── WS events ───────────────────────────────────────────────────
class SessionEventOut(EldirModel):
    """Event diffusé sur le channel `session:{id}` (Redis pubsub → WS)."""

    type: SessionEventType
    session_id: str
    timestamp: datetime
    data: dict[str, Any]
