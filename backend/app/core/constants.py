"""Constantes globales d'Eldir.

Aucune valeur hardcodée ne doit traîner ailleurs dans le code.
"""

from typing import Final

# ── Sessions ────────────────────────────────────────────────────
# Le plafond de sessions actives dépend de la RAM du serveur (chaque session
# fait vivre un process `claude` Node) : il est réglable via l'env
# MAX_CONCURRENT_SESSIONS, cf. app.core.config.Settings.
# Un `connect()` qui ne rend jamais la main bloque la requête HTTP sans
# aucun signal côté interface : au-delà de ce délai, on remonte une erreur.
# Test d'un credential Claude : une question triviale au CLI suffit, mais il
# faut lui laisser le temps de démarrer Node.
CREDENTIAL_TEST_TIMEOUT_S: Final[float] = 60.0

# Un CLI bloqué ne doit pas empêcher d'arrêter ou de supprimer sa session.
SESSION_DISCONNECT_TIMEOUT_S: Final[float] = 15.0

SESSION_CONNECT_TIMEOUT_S: Final[float] = 90.0

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

# Raison portée par un STOP. Deux producteurs : la fin d'un tour (`turn_complete`,
# Claude a répondu jusqu'au bout) et `SessionManager.stop()`, qui publie un STOP
# sans charge quand la session est arrêtée, supprimée ou qu'Eldir s'éteint. Seul
# le premier dit « le tour est fini » ; le second l'interrompt.
STOP_REASON_TURN_COMPLETE: Final[str] = "turn_complete"

# Qui a écrit un `user_message` : John, ou Eldir lui-même (consigne dispatchée
# par le superviseur, ping de fin de tour). Les events écrits avant l'ajout de
# ce champ n'ont pas d'origine : ils sont traités comme venant de John.
# Un agent extérieur (jeton sur `/api/mcp/`) est un second Eldir possible : son
# origine est ce préfixe suivi du libellé de son jeton, sur une seule ligne,
# pour que l'historique dise lequel des deux a décidé. Le frontend lit la même
# forme (`MESSAGE_ORIGIN_AGENT_PREFIX` dans `lib/constants.ts`).
MESSAGE_ORIGIN_USER: Final[str] = "user"
MESSAGE_ORIGIN_ELDIR: Final[str] = "eldir"
MESSAGE_ORIGIN_AGENT_PREFIX: Final[str] = "agent:"
EVENT_TYPE_USAGE: Final[str] = "usage"

# ── Budget tokens par session (Phase 5) ─────────────────────────
# Seuil d'alerte (jamais bloquant - cf. Principes directeurs #5)
DEFAULT_SESSION_TOKEN_BUDGET: Final[int] = 1_000_000

# ── Git providers supportés (V1) ────────────────────────────────
PROVIDER_GITHUB: Final[str] = "github"
PROVIDER_FORGEJO: Final[str] = "forgejo"
SUPPORTED_PROVIDERS: Final[frozenset[str]] = frozenset({PROVIDER_GITHUB, PROVIDER_FORGEJO})
