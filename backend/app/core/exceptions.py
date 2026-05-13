"""Hiérarchie d'exceptions métier d'Eldir.

Toute exception applicative DOIT hériter de `EldirError`. Les handlers FastAPI
mappent ces exceptions vers les bons codes HTTP de manière centralisée.
"""

from __future__ import annotations


class EldirError(Exception):
    """Exception racine pour toute erreur métier d'Eldir."""

    status_code: int = 500
    code: str = "eldir_error"

    def __init__(self, message: str, *, details: dict[str, object] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}


# ── 4xx ─────────────────────────────────────────────────────────
class NotFoundError(EldirError):
    status_code = 404
    code = "not_found"


class ConflictError(EldirError):
    status_code = 409
    code = "conflict"


class ValidationError(EldirError):
    status_code = 422
    code = "validation_error"


class AuthenticationError(EldirError):
    status_code = 401
    code = "unauthenticated"


class AuthorizationError(EldirError):
    status_code = 403
    code = "forbidden"


# ── Domain ──────────────────────────────────────────────────────
class SessionError(EldirError):
    """Erreur générique liée à une session Claude."""

    code = "session_error"


class SessionNotFoundError(NotFoundError):
    code = "session_not_found"


class SessionLimitError(EldirError):
    """Levée quand on tente de dépasser la limite de sessions actives."""

    status_code = 429
    code = "session_limit_reached"


class GitProviderError(EldirError):
    """Erreur lors d'une interaction avec un provider Git."""

    code = "git_provider_error"


class WorkspaceError(EldirError):
    """Erreur lors d'opérations sur les workspaces / worktrees."""

    code = "workspace_error"


class BudgetExceededWarning(EldirError):
    """Levé pour signaler un dépassement — JAMAIS pour bloquer (cf. roadmap)."""

    status_code = 200  # avertissement uniquement
    code = "budget_warning"
