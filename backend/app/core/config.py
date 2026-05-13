"""Configuration centralisée d'Eldir.

Toutes les variables d'environnement passent par cette classe Settings.
Aucun `os.getenv()` ne doit exister ailleurs dans le code.
"""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, PostgresDsn, RedisDsn, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Settings globales chargées depuis l'environnement ou un .env."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── App ─────────────────────────────────────────────────────
    app_name: str = "Eldir"
    app_env: Literal["dev", "test", "prod"] = "dev"
    app_debug: bool = False
    app_version: str = "0.1.0"
    api_prefix: str = "/api/v1"

    # ── Server ──────────────────────────────────────────────────
    host: str = "0.0.0.0"  # noqa: S104 (bind public, géré au niveau réseau)
    port: int = 8000
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:5173"])

    # ── Database ────────────────────────────────────────────────
    database_url: PostgresDsn | str = (
        "postgresql+asyncpg://eldir:eldir@localhost:5432/eldir"
    )

    # ── Redis ───────────────────────────────────────────────────
    redis_url: RedisDsn | str = "redis://localhost:6379/0"

    # ── Sécurité ────────────────────────────────────────────────
    jwt_secret: SecretStr = SecretStr("change-me-in-production-please")
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60 * 24 * 7  # 7 jours
    encryption_key: SecretStr = SecretStr("")  # Fernet key, généré au setup

    # ── Workspaces ──────────────────────────────────────────────
    workspaces_root: Path = Path("/var/eldir/workspaces")

    # ── Claude ──────────────────────────────────────────────────
    anthropic_api_key: SecretStr | None = None
    claude_default_model: str = "claude-sonnet-4-6"

    # ── Budgets (alerte uniquement, jamais blocage) ─────────────
    daily_token_budget: int = 1_000_000
    daily_cost_cap_usd: float = 8.0

    @property
    def is_dev(self) -> bool:
        return self.app_env == "dev"

    @property
    def is_test(self) -> bool:
        return self.app_env == "test"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Retourne l'instance Settings singleton (cache LRU)."""
    return Settings()
