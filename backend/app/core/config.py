"""Configuration centralisée d'Eldir.

Toutes les variables d'environnement passent par cette classe Settings.
Aucun `os.getenv()` ne doit exister ailleurs dans le code.
"""

import os
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, PostgresDsn, RedisDsn, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.core.constants import ENV_VAR_CREDENTIEL_PAR_KIND


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
    #
    # Le conteneur par session (Phase 6 bis) ajoute une enveloppe autour de ce
    # process. Mesuré le 2026-11-06 (Docker 29.9.2, cgroup v2, image
    # `eldir-session:local`), sans lancer le CLI : son coût à lui existait déjà,
    # dans le conteneur du backend, et n'a pas été remesuré.
    #   - le conteneur au repos : 0,4 à 0,6 Mo (`docker stats`, 3 mesures sans
    #     `--init`, 4 avec `-i --rm --init` comme l'enrobage) ;
    #   - son shim containerd (`containerd-shim-runc-v2`), côté hôte, donc hors
    #     du cgroup du conteneur : 11 Mo de RSS dont 3,7 Mo anonymes (4 mesures) ;
    #   - le client `docker run -i`, dans le conteneur du backend : 32,5 Mo de
    #     RSS dont 11 Mo anonymes, le reste étant le binaire, partagé entre les
    #     clients (4 mesures). Le client mesuré est celui de l'hôte, en 29.9.2,
    #     pas celui de l'image du backend.
    #   Les chiffres du shim et du client se relisent dans `/proc/<pid>/status`
    #   (champs `VmRSS`, RSS complet, et `RssAnon`, anonyme) ; celui du
    #   conteneur dans `docker stats --no-stream` ou le `memory.current` de son
    #   cgroup.
    # Soit de 15 Mo (anonyme seulement) à 45 Mo (RSS complet) par session, de
    # 3 % à 30 % de ce que coûte le process `claude`. C'est moins que l'écart
    # de 300 Mo qui sépare les deux bornes de son estimation : le plafond ne
    # bouge pas. À 4 sessions l'enveloppe ajoute au plus 180 Mo, et la valeur
    # recommandée pour 4 Go reste 4. Aucune limite mémoire n'est posée aux
    # conteneurs (l'enrobage ne passe pas `--memory`) : ce plafond reste la
    # seule borne.
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
    # worktree, donc incommitable. Dans un volume (`eldir_collectes`) : le
    # démon ne monte dans une session que ce qu'il voit lui-même, et un dossier
    # du conteneur du backend lui est invisible. Une collecte survit donc à un
    # redéploiement, mais elle se refait à chaque création de session : elle
    # n'est jamais plus ancienne que la session qui la lit. Cf. `CollectService`.
    collectes_root: Path = Path("/var/eldir/collectes")
    # Une commande de collecte lit un fichier ou un log, pas plus.
    collect_timeout_s: int = 60
    # Taille max par fichier collecté (`ulimit -f`), en Mo : un `docker logs`
    # sans borne remplirait le disque du serveur.
    collect_max_file_mb: int = 2

    # ── Accès SSH aux machines des projets ──────────────────────
    # Eldir est propriétaire de ce dossier : il y écrit une clé par projet et
    # les blocs de `config` correspondants. Ne monte pas ton `~/.ssh`
    # personnel dedans. Cf. `RemoteAccessService` et `docs/acces-serveur.md`.
    ssh_home: Path = Path("/home/eldir/.ssh")
    # Au-delà, la machine est considérée injoignable : on préfère un échec
    # net à une requête HTTP qui pend.
    ssh_connect_timeout_s: int = 15

    # ── Maisons `.claude` des sessions ──────────────────────────
    # Point de montage, chez le backend, du volume qui porte les transcripts
    # du CLI. Une maison par projet dessous (cf. `claude_home.py`) : sans
    # cette séparation, une session lirait les conversations de tous les
    # autres projets. Le nom DOCKER de ce volume est `claude_home_volume`,
    # plus bas : un point de montage et un nom de volume ne se déduisent pas
    # l'un de l'autre.
    claude_home_root: Path = Path("/home/eldir/.claude")

    # ── Isolement des sessions (Phase 6 bis) ────────────────────
    # `conteneur` : un conteneur par session, monté sur son seul worktree, sa
    #   seule clé et la seule maison `.claude` de son projet.
    # `processus` : le CLI de la session tourne dans le conteneur du backend,
    #   qui voit le disque de tous les projets. C'est le mode qui marche sans
    #   démon Docker joignable, pas le mode sûr.
    # Le défaut est `conteneur` : un réglage oublié doit coûter de la
    # disponibilité (la session échoue au démarrage), jamais l'isolement.
    # Une installation dont le backend n'a pas de démon joignable règle
    # `SESSION_RUNTIME=processus` explicitement. Le font les tests (cf.
    # `backend/tests/conftest.py`) et le compose de dev (`docker-compose.dev.yml`).
    # Le réglage existe parce qu'Eldir doit pouvoir tourner là où le backend
    # n'a pas de Docker.
    session_runtime: Literal["processus", "conteneur"] = "conteneur"
    # Image de la session : le CLI Claude, git et Node, rien d'autre.
    # Construite par `DOCKER_BUILDKIT=1 docker build -t eldir-session:local
    # backend/docker/session` (BuildKit est requis : `COPY --chmod`).
    # Sans elle, une session échoue au démarrage avec le message du démon.
    session_image: str = "eldir-session:local"
    # Réseau dédié, sans route vers les réseaux du compose : celui de Postgres
    # et Redis, et celui du proxy de socket. À créer une fois (cf.
    # docs/deployment.md) : compose ne crée pas un réseau qu'aucun de ses
    # services n'utilise. Sans lui, chaque session échoue au démarrage, le
    # réseau étant introuvable.
    session_network: str = "eldir-sessions"
    # Les noms DOCKER des volumes, à distinguer des `*_root` ci-dessus, qui
    # sont leurs points de montage chez le backend. `docker run` monte un
    # volume par son nom, et compose préfixe ce nom par le nom effectif du
    # projet compose, y compris si `COMPOSE_PROJECT_NAME` le change (ordre :
    # `-p`, puis `COMPOSE_PROJECT_NAME`, puis `name:`). Le volume
    # `eldir_workspaces` du compose de prod (`name: eldir`) s'appelle donc
    # `eldir_eldir_workspaces` pour le démon, et une variable
    # `COMPOSE_PROJECT_NAME` exportée renommerait les quatre volumes d'un coup.
    # Les deux informations ne se déduisent pas l'une de l'autre, donc elles se
    # déclarent toutes les deux. Une installation dont le projet compose porte
    # un autre nom renseigne ces quatre variables (cf. docs/deployment.md).
    workspaces_volume: str = "eldir_eldir_workspaces"
    toolchains_volume: str = "eldir_eldir_toolchains"
    claude_home_volume: str = "eldir_eldir_claude_home"
    collectes_volume: str = "eldir_eldir_collectes"

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

    # ── File d'attente par session ──────────────────────────────
    # On peut écrire à une session qui travaille : le message attend la fin du
    # tour. Ce plafond ne protège pas un budget (la politique maison est
    # l'alerte, jamais le blocage), il protège une file : un agent parti en
    # boucle y empilerait des centaines de consignes que personne ne relira.
    session_queue_max: int = 5

    # ── Surface d'agent externe (MCP sur HTTP) ──────────────────
    # Hôtes autorisés à joindre /api/mcp/, séparés par des virgules, port
    # compris ou en `hote:*` (ex "eldir.exemple.lan,127.0.0.1:8000"). Vide =
    # protection anti-DNS-rebinding désactivée : le jeton d'agent est la garde,
    # et aucun cookie n'est en jeu sur cette surface, donc rien à rejouer
    # depuis un navigateur. À renseigner si l'endpoint est exposé au-delà du
    # VPN : un `Host` hors liste est alors refusé en 421.
    mcp_allowed_hosts: str = ""

    # ── Ping de fin de tour vers un abonné externe ──────────────
    # Un agent branché sur /api/mcp/ vit dans un autre processus : il ne voit
    # pas le réveil en mémoire du superviseur. Un seul abonné pour l'instant,
    # une table viendra quand il y en aura deux. URL vide = pas de ping.
    # L'URL peut porter un jeton : elle n'est jamais journalisée.
    turn_webhook_url: str = ""
    # Sert à signer le corps (HMAC SHA-256). Vide = ping non signé.
    turn_webhook_secret: SecretStr | None = None
    # Délai total d'un ping (connexion, réponse, tout compris).
    turn_webhook_timeout_seconds: float = 10.0

    @property
    def is_dev(self) -> bool:
        return self.app_env == "dev"

    @property
    def is_test(self) -> bool:
        return self.app_env == "test"

    @property
    def mcp_hosts(self) -> list[str]:
        return [h.strip() for h in self.mcp_allowed_hosts.split(",") if h.strip()]

    @property
    def mcp_origins(self) -> list[str]:
        """Les origines autorisées sur /api/mcp/, dérivées des hôtes déclarés.

        Le même drapeau allume les deux contrôles du middleware de transport, et
        sa validation d'`Origin` rend vrai sur un en-tête absent mais faux sur
        toute valeur hors liste. Laisser la liste vide refusait donc en 403 tout
        client qui envoie un `Origin`, c'est-à-dire tout agent hébergé ou piloté
        par un navigateur, et précisément sur le chemin de durcissement que la
        documentation recommande.

        Les deux schémas : derrière un proxy TLS le navigateur envoie `https://`,
        un agent en clair sur le réseau privé `http://`. Le `Host` reste la garde
        du nom, et le jeton celle de l'accès.
        """
        return [f"{schema}://{hote}" for hote in self.mcp_hosts for schema in ("https", "http")]

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


def env_a_masquer_pour_cli() -> dict[str, str]:
    """Ce qu'un sous-processus Claude ne doit pas voir de l'environnement du backend.

    Une session tourne en `bypassPermissions` et le SDK lui transmet
    l'environnement du backend en entier (`inherited_env` dans
    `subprocess_cli.py`), `options.env` étant fusionné par-dessus et non à la
    place. On ne choisit donc pas ce qu'on donne : on écrase nommément ce
    qu'on retire, en rendant la valeur vide.

    Sans ce masque, une session lit `JWT_SECRET`, forge un jeton de connexion
    (sans claim `kind`, donc accepté par `decode_session_token`) et appelle
    l'API en tant que son propriétaire : elle s'autorise la publication
    elle-même, sans qu'aucune commande git ne passe devant le hook. Avec
    `ENCRYPTION_KEY` et `DATABASE_URL` elle déchiffre en plus les credentials
    Git de tous les projets.

    La liste se dérive des champs de `Settings`, seul endroit où Eldir lit
    l'environnement : un secret ajouté à la configuration est masqué sans
    qu'on ait à y penser. On compare aux clés réellement présentes plutôt
    qu'aux noms attendus, parce que `Settings` est insensible à la casse et
    lirait aussi bien `jwt_secret` que `JWT_SECRET`.

    Seule exception, le credential Claude : le CLI de la session s'authentifie
    avec. Il reste un risque connu, documenté dans `docs/securite-sessions.md`.
    """
    champs = set(Settings.model_fields)
    gardes = set(ENV_VAR_CREDENTIEL_PAR_KIND.values())
    return {cle: "" for cle in os.environ if cle.lower() in champs and cle not in gardes}
