FROM python:3.12-slim AS base

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV PIP_DISABLE_PIP_VERSION_CHECK=1
ENV UV_LINK_MODE=copy
ENV UV_PROJECT_ENVIRONMENT=/app/.venv
ENV PATH="/app/.venv/bin:$PATH"
ENV CI=true
ENV npm_config_fund=false
ENV npm_config_audit=false
ENV npm_config_update_notifier=false
ENV npm_config_progress=false
# DEBIAN_FRONTEND est défini en ARG (build-time uniquement) pour éviter
# qu'il fuite dans le container final et déclenche des comportements
# inattendus sur les apt-get exécutés à l'exécution.
ARG DEBIAN_FRONTEND=noninteractive

# uv (package manager imposé par AGENTS.md)
COPY --from=ghcr.io/astral-sh/uv:0.5 /uv /usr/local/bin/uv

# Node 20 (LTS) + outils système requis par git et le SDK Claude.
# `unzip` et `xz-utils` servent aux toolchains par projet : un SDK se
# distribue en archive (Flutter en .tar.xz, le SDK Dart en .zip), sans eux
# l'installation échoue à l'extraction.
# `openssh-client` sert à la collecte distante : rapatrier un fichier qui vit
# sur un autre serveur et pas dans le repo. Inutile tant qu'aucune clé n'est
# montée dans le conteneur, cf. docs/collecte-distante.md.
# Le Claude Agent SDK Python lance `claude` en subprocess (Node binary)
# pour communiquer avec l'API Anthropic - il DOIT être dans le PATH.
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      git curl ca-certificates gnupg \
      unzip xz-utils \
      openssh-client \
 && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
 && apt-get install -y --no-install-recommends nodejs \
 && rm -rf /var/lib/apt/lists/* \
 && node --version && npm --version

# CLI officiel @anthropic-ai/claude-code - disponible pour debug et override
# du binaire bundlé par le SDK Python (cf. docs/installation.md).
# Note : on évite `claude --version` ici car certaines versions tentent un
# onboarding interactif au premier lancement.
RUN npm install -g @anthropic-ai/claude-code@latest \
 && command -v claude

# Utilisateur non-root : le Claude CLI refuse `bypassPermissions` en root
# ("--dangerously-skip-permissions cannot be used with root/sudo privileges").
# UID/GID alignés sur l'utilisateur hôte pour que les bind-mounts (`./backend`)
# restent lisibles/écrivables sans `sudo`.
ARG UID=1000
ARG GID=1000
# `/var/eldir/workspaces` et `/home/eldir/.claude` reçoivent tous deux un
# volume nommé. Docker initialise un volume vide en recopiant le contenu ET
# le propriétaire du répertoire présent dans l'image : si le répertoire
# n'existe pas ici, le volume appartient à root et le CLI, qui tourne en
# `eldir`, ne peut plus rien y écrire (les transcripts du SDK finissent en
# "Permission denied", et une session ne démarre plus).
RUN groupadd -g $GID eldir \
 && useradd -u $UID -g eldir -m -s /bin/bash eldir \
 && mkdir -p /var/eldir/workspaces /var/eldir/toolchains /var/eldir/collectes /home/eldir/.claude \
 && chown -R eldir:eldir /var/eldir /home/eldir

WORKDIR /app

# Étape 1 : résolution des deps avec cache mount.
COPY pyproject.toml uv.lock* ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --no-install-project --all-groups

# Étape 2 : code applicatif.
COPY . .
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --all-groups \
 && chown -R eldir:eldir /app

USER eldir

EXPOSE 8000

CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
