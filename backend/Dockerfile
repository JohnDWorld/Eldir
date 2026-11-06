FROM python:3.12-slim AS base

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV PIP_DISABLE_PIP_VERSION_CHECK=1
ENV UV_LINK_MODE=copy
ENV UV_PROJECT_ENVIRONMENT=/app/.venv
ENV PATH="/app/.venv/bin:$PATH"
# DEBIAN_FRONTEND est défini en ARG (build-time uniquement) pour éviter
# qu'il fuite dans le container final et déclenche des comportements
# inattendus sur les apt-get exécutés à l'exécution.
ARG DEBIAN_FRONTEND=noninteractive
# Pour le build seulement, d'où des ARG et pas des ENV : elles servent à faire
# taire `npm install -g`. En ENV, elles passeraient dans l'environnement de tout
# ce que ce conteneur lance, donc dans celui d'une session du mode `processus`,
# où `CI=true` changerait le comportement des outils que l'agent lance.
# L'image des sessions (backend/docker/session/Dockerfile) porte la même
# correction : sur ce point, les deux modes voient le même environnement.
ARG CI=true
ARG npm_config_fund=false
ARG npm_config_audit=false
ARG npm_config_update_notifier=false
ARG npm_config_progress=false

# uv (package manager imposé par AGENTS.md)
COPY --from=ghcr.io/astral-sh/uv:0.5 /uv /usr/local/bin/uv

# Node 20 (LTS) + outils système requis par git et le SDK Claude.
# `unzip` et `xz-utils` servent aux toolchains par projet : un SDK se
# distribue en archive (Flutter en .tar.xz, le SDK Dart en .zip), sans eux
# l'installation échoue à l'extraction.
# `openssh-client` sert à l'accès aux machines des projets. `sshpass` ne sert
# qu'une fois par machine : déposer la clé publique à la première connexion,
# avec un mot de passe que John saisit et qui n'est jamais stocké. Ensuite
# tout passe par la clé. Cf. docs/acces-serveur.md.
# Le Claude Agent SDK Python lance `claude` en subprocess (Node binary)
# pour communiquer avec l'API Anthropic - il DOIT être dans le PATH.
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      git curl ca-certificates gnupg \
      unzip xz-utils \
      openssh-client sshpass \
 && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
 && apt-get install -y --no-install-recommends nodejs \
 && rm -rf /var/lib/apt/lists/* \
 && node --version && npm --version

# `docker-ce-cli` sert à l'enrobage des sessions : le backend lance le CLI
# Claude dans un conteneur par session (cf. backend/docker/session/). Le client
# seulement, pas le démon : il parle au proxy de socket par `DOCKER_HOST`.
RUN install -m 0755 -d /etc/apt/keyrings \
 && curl -fsSL https://download.docker.com/linux/debian/gpg \
      -o /etc/apt/keyrings/docker.asc \
 && chmod a+r /etc/apt/keyrings/docker.asc \
 && echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/debian $(. /etc/os-release && echo "$VERSION_CODENAME") stable" \
      > /etc/apt/sources.list.d/docker.list \
 && apt-get update \
 && apt-get install -y --no-install-recommends docker-ce-cli \
 && rm -rf /var/lib/apt/lists/* \
 && docker --version

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
 && mkdir -p /var/eldir/workspaces /var/eldir/toolchains /var/eldir/collectes \
          /home/eldir/.claude /home/eldir/.ssh \
 && chmod 700 /home/eldir/.ssh \
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
