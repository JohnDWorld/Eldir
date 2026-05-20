"""Constantes globales d'Eldir.

Aucune valeur hardcodée ne doit traîner ailleurs dans le code.
"""

from typing import Final

# ── Sessions ────────────────────────────────────────────────────
MAX_CONCURRENT_SESSIONS: Final[int] = 8
SESSION_BRANCH_PREFIX: Final[str] = "claude/"
SESSION_WORKTREE_TEMPLATE: Final[str] = "{repo_slug}.{session_id}"

# ── Redis channels ──────────────────────────────────────────────
REDIS_SESSION_CHANNEL_TEMPLATE: Final[str] = "session:{session_id}"
REDIS_GLOBAL_EVENTS_CHANNEL: Final[str] = "eldir:events"

# ── États possibles d'une session (cf. design system DA D1) ─────
SESSION_STATE_IDLE: Final[str] = "idle"
SESSION_STATE_THINKING: Final[str] = "thinking"
SESSION_STATE_TOOL_USE: Final[str] = "tool_use"
SESSION_STATE_WAITING_INPUT: Final[str] = "waiting_input"
SESSION_STATE_BLOCKED: Final[str] = "blocked"

SESSION_STATES: Final[frozenset[str]] = frozenset(
    {
        SESSION_STATE_IDLE,
        SESSION_STATE_THINKING,
        SESSION_STATE_TOOL_USE,
        SESSION_STATE_WAITING_INPUT,
        SESSION_STATE_BLOCKED,
    }
)

# ── Types d'events streamés vers le frontend ────────────────────
EVENT_TYPE_TEXT: Final[str] = "text"
EVENT_TYPE_TOOL_USE: Final[str] = "tool_use"
EVENT_TYPE_TOOL_RESULT: Final[str] = "tool_result"
EVENT_TYPE_STATE: Final[str] = "state"
EVENT_TYPE_STOP: Final[str] = "stop"
EVENT_TYPE_ERROR: Final[str] = "error"
EVENT_TYPE_USER_MESSAGE: Final[str] = "user_message"

# ── Git providers supportés (V1) ────────────────────────────────
PROVIDER_GITHUB: Final[str] = "github"
PROVIDER_FORGEJO: Final[str] = "forgejo"
SUPPORTED_PROVIDERS: Final[frozenset[str]] = frozenset({PROVIDER_GITHUB, PROVIDER_FORGEJO})
