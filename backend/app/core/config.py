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
    database_url: PostgresDsn | str = "postgresql+asyncpg://eldir:eldir@localhost:5432/eldir"

    # ── Redis ───────────────────────────────────────────────────
    redis_url: RedisDsn | str = "redis://localhost:6379/0"

    # ── Sécurité ────────────────────────────────────────────────
    jwt_secret: SecretStr = SecretStr("change-me-in-production-please")
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60 * 24 * 7  # 7 jours
    encryption_key: SecretStr = SecretStr("")  # Fernet key, généré au setup

    # ── Sessions ───────────────────────────────────────────────
    # Chaque session active = un process `claude` (Node) résident, soit
    # 150 à 450 Mo selon la taille de la conversation. Le superviseur compte
    # comme une session. Sur un serveur à 4 Go : 4.
    max_concurrent_sessions: int = 8

    # ── Workspaces ──────────────────────────────────────────────
    workspaces_root: Path = Path("/var/eldir/workspaces")
    # Surveillance des repos : fetch + fast-forward périodique des clones
    # (jamais quand le working tree est sale). 0 = désactivé.
    repo_sync_interval_minutes: int = 15

    # ── Toolchains par projet ───────────────────────────────────
    # Un dossier par projet, monté en volume : installé une fois, réutilisé
    # par toutes ses sessions. Cf. `ToolchainService`.
    toolchains_root: Path = Path("/var/eldir/toolchains")
    # Un SDK complet peut être long à télécharger (Flutter : ~3 Go).
    toolchain_install_timeout_s: int = 1_800
    # On refuse d'installer si le disque descend sous ce seuil : mieux vaut un
    # refus explicite qu'un serveur à 100% avec Postgres qui ne peut plus
    # écrire.
    toolchain_min_free_gb: int = 5

    # ── Collecte distante par projet ────────────────────────────
    # Ce que la session doit lire mais qui ne vit pas dans le repo. Hors
    # worktree, donc incommitable, et volontairement hors volume : la
    # collecte se refait à chaque création de session, une donnée de prod
    # rapatriée n'a pas à survivre à un redéploiement. Cf. `CollectService`.
    collectes_root: Path = Path("/var/eldir/collectes")
    # Une commande de collecte lit un fichier ou un log, pas plus.
    collect_timeout_s: int = 60
    # Taille max par fichier collecté (`ulimit -f`), en Mo : un `docker logs`
    # sans borne remplirait le disque du serveur.
    collect_max_file_mb: int = 2

    # ── Frontend (pour redirections OAuth) ──────────────────────
    frontend_base_url: str = "http://localhost:5173"

    # ── GitHub OAuth App (optionnel - flow "Connect with GitHub") ──
    github_oauth_client_id: str | None = None
    github_oauth_client_secret: SecretStr | None = None
    # Doit matcher l'Authorization callback URL configurée sur l'OAuth App GitHub.
    github_oauth_redirect_url: str = "http://localhost:8000/api/v1/auth/github/oauth/callback"
    # Scopes : `repo` pour les repos privés, `read:user` pour le username.
    github_oauth_scopes: str = "repo read:user"

    # ── Claude ──────────────────────────────────────────────────
    anthropic_api_key: SecretStr | None = None
    claude_default_model: str = "claude-sonnet-5"

    # ── Ollama (Phase 6 - mode "données sensibles") ────────────
    # URL du serveur Ollama. Laisser vide = Ollama désactivé.
    # Exemple : http://host.docker.internal:11434 si Ollama tourne
    # sur l'host Docker, http://ollama:11434 si c'est un service compose.
    ollama_base_url: str = ""
    ollama_default_model: str = "llama3.2"
    ollama_timeout_seconds: float = 60.0

    # ── Budgets (alerte uniquement, jamais blocage) ─────────────
    daily_token_budget: int = 1_000_000
    daily_cost_cap_usd: float = 8.0

    @property
    def is_dev(self) -> bool:
        return self.app_env == "dev"

    @property
    def is_test(self) -> bool:
        return self.app_env == "test"

    @property
    def ollama_enabled(self) -> bool:
        return bool(self.ollama_base_url.strip())

    @property
    def github_oauth_enabled(self) -> bool:
        return bool(
            self.github_oauth_client_id
            and self.github_oauth_client_secret
            and self.github_oauth_client_secret.get_secret_value()
        )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Retourne l'instance Settings singleton (cache LRU)."""
    return Settings()
