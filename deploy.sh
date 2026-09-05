#!/usr/bin/env bash
# Eldir - déploiement sur le serveur.
#
#   ./deploy.sh          pull, puis reconstruit uniquement ce qui a changé
#   ./deploy.sh --force  reconstruit tout, même sans nouveau commit
#
# À lancer sur le serveur, depuis le clone (`~/eldir`). Les migrations
# Alembic sont jouées au démarrage du backend, il n'y a rien à faire de plus.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"

FORCE=0
[[ "${1:-}" == "--force" || "${1:-}" == "-f" ]] && FORCE=1

bold() { printf '\033[1m%s\033[0m\n' "$*"; }
info() { printf '  %s\n' "$*"; }
warn() { printf '\033[33m  ! %s\033[0m\n' "$*"; }

# ── 1. état de départ ────────────────────────────────────────────
if [[ -n "$(git status --porcelain --untracked-files=no)" ]]; then
    warn "des modifications locales non commitées existent, elles seront conservées"
fi

BEFORE="$(git rev-parse HEAD)"
bold "→ git pull"
git pull --ff-only
AFTER="$(git rev-parse HEAD)"

if [[ "$BEFORE" == "$AFTER" && "$FORCE" -eq 0 ]]; then
    info "déjà à jour sur $(git log --oneline -1)"
    info "rien à reconstruire (--force pour forcer)"
    exit 0
fi

# ── 2. qui doit être reconstruit ? ───────────────────────────────
CHANGED="$(git diff --name-only "$BEFORE" "$AFTER")"
SERVICES=()
RECREATE_ALL=0

if [[ "$FORCE" -eq 1 ]]; then
    SERVICES=(backend frontend caddy)
    RECREATE_ALL=1
else
    grep -q '^backend/'                 <<<"$CHANGED" && SERVICES+=(backend)
    grep -q '^frontend/'                <<<"$CHANGED" && SERVICES+=(frontend)
    grep -qE '^docker/'                 <<<"$CHANGED" && SERVICES+=(caddy)
    # Le compose décrit tous les services : un changement peut toucher
    # n'importe lequel (ports, volumes, variables).
    grep -q '^docker-compose.yml$'      <<<"$CHANGED" && RECREATE_ALL=1
fi

# Une variable d'environnement ajoutée en amont ne se voit pas : le `.env`
# du serveur, lui, n'est pas versionné.
if grep -qE '(^|/)\.env\.example$' <<<"$CHANGED"; then
    warn "un .env.example a changé : compare-le à ton .env, il manque peut-être une variable"
fi

bold "→ $(git log --oneline "$BEFORE".."$AFTER" | wc -l) commit(s) déployé(s)"
git log --oneline "$BEFORE".."$AFTER" | sed 's/^/  /'

# ── 3. build + redémarrage ───────────────────────────────────────
if [[ "$RECREATE_ALL" -eq 1 ]]; then
    bold "→ docker compose up -d --build (toute la stack)"
    docker compose up -d --build
elif [[ ${#SERVICES[@]} -eq 0 ]]; then
    info "aucun service concerné (doc, CI, scripts) : rien à reconstruire"
    exit 0
else
    bold "→ docker compose up -d --build ${SERVICES[*]}"
    docker compose up -d --build "${SERVICES[@]}"
fi

# ── 4. contrôle ──────────────────────────────────────────────────
bold "→ vérification"
for _ in $(seq 1 30); do
    if docker compose exec -T backend python -c "
import sys, urllib.request
try:
    urllib.request.urlopen('http://localhost:8000/api/v1/health', timeout=2)
except Exception:
    sys.exit(1)
" 2>/dev/null; then
        info "backend en ligne"
        break
    fi
    sleep 2
done

docker compose ps --format '  {{.Name}}  {{.Status}}'
bold "✓ déployé sur $(git log --oneline -1)"
