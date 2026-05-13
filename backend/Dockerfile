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
# Le Claude Agent SDK Python lance `claude` en subprocess (Node binary)
# pour communiquer avec l'API Anthropic — il DOIT être dans le PATH.
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      git curl ca-certificates gnupg \
 && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
 && apt-get install -y --no-install-recommends nodejs \
 && rm -rf /var/lib/apt/lists/* \
 && node --version && npm --version

# CLI officiel @anthropic-ai/claude-code — disponible pour debug et override
# du binaire bundlé par le SDK Python (cf. docs/installation.md).
# Note : on évite `claude --version` ici car certaines versions tentent un
# onboarding interactif au premier lancement.
RUN npm install -g @anthropic-ai/claude-code@latest \
 && command -v claude

WORKDIR /app

# Étape 1 : résolution des deps avec cache mount.
COPY pyproject.toml uv.lock* ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --no-install-project --all-groups

# Étape 2 : code applicatif.
COPY . .
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --all-groups

EXPOSE 8000

CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
