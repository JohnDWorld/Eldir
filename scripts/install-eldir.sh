#!/usr/bin/env bash
# Eldir - script d'installation interactif (Phase 1)
#
# Boote la stack via docker compose, attend que l'API soit prête, récupère
# le bootstrap_token émis par le backend, propose à l'utilisateur de générer
# son token Claude Pro/Max + (optionnellement) une clé API Console, puis
# POST /api/v1/setup/bootstrap pour créer l'admin et persister les
# credentials chiffrés en DB.
#
# Usage:
#   ./scripts/install-eldir.sh [--api-url http://localhost:8000]

set -euo pipefail

API_URL="${ELDIR_API_URL:-http://localhost:8000}"
FRONTEND_URL="${ELDIR_FRONTEND_URL:-http://localhost:5173}"
COMPOSE_FILE="${ELDIR_COMPOSE_FILE:-docker-compose.dev.yml}"
BACKEND_CONTAINER="${ELDIR_BACKEND_CONTAINER:-eldir-backend}"

# ── helpers ──────────────────────────────────────────────────────
b()   { printf '\033[1m%s\033[0m' "$1"; }
gr()  { printf '\033[32m%s\033[0m' "$1"; }
yl()  { printf '\033[33m%s\033[0m' "$1"; }
rd()  { printf '\033[31m%s\033[0m' "$1"; }
hr()  { printf '\033[2m%s\033[0m\n' "────────────────────────────────────────────────"; }

step()    { hr; printf '%s %s\n' "$(b "▸")" "$(b "$1")"; }
ok()      { printf '  %s %s\n' "$(gr "✓")" "$1"; }
warn()    { printf '  %s %s\n' "$(yl "!")" "$1" >&2; }
fail()    { printf '  %s %s\n' "$(rd "✗")" "$1" >&2; exit 1; }
ask()     { printf '%s ' "$(b "$1")"; }

require() {
    command -v "$1" >/dev/null 2>&1 \
        || fail "$1 est requis (introuvable dans le PATH)."
}

# ── parse args ───────────────────────────────────────────────────
while [[ $# -gt 0 ]]; do
    case "$1" in
        --api-url)      API_URL="$2"; shift 2 ;;
        --frontend-url) FRONTEND_URL="$2"; shift 2 ;;
        --compose-file) COMPOSE_FILE="$2"; shift 2 ;;
        -h|--help)
            cat <<EOF
Usage: $0 [options]

Options:
  --api-url URL         URL du backend Eldir (par défaut: http://localhost:8000)
  --frontend-url URL    URL du frontend (par défaut: http://localhost:5173)
  --compose-file PATH   Fichier compose à utiliser (par défaut: docker-compose.dev.yml)
EOF
            exit 0
            ;;
        *) fail "Option inconnue: $1" ;;
    esac
done

# ── 0. prérequis ─────────────────────────────────────────────────
step "Prérequis"
require docker
require curl
require sed
require awk
require python3
if ! docker compose version >/dev/null 2>&1; then
    fail "docker compose (v2) n'est pas disponible."
fi
ok "docker, docker compose, curl, python3 OK"

CLAUDE_BIN=""
if command -v claude >/dev/null 2>&1; then
    CLAUDE_BIN="claude"
    ok "claude CLI déjà installé ($(claude --version 2>/dev/null | head -n1))"
elif command -v npx >/dev/null 2>&1; then
    ok "npx disponible - claude sera lancé via 'npx -y @anthropic-ai/claude-code'"
    CLAUDE_BIN="npx -y @anthropic-ai/claude-code"
else
    warn "Ni 'claude' ni 'npx' trouvés dans le PATH."
    warn "Pour générer automatiquement le token Pro/Max, installe Node.js ≥ 18"
    warn "(https://nodejs.org). Sinon, tu pourras coller un token déjà généré."
fi

HAS_CLAUDE_HELPER="0"
if [[ -n "$CLAUDE_BIN" ]]; then
    HAS_CLAUDE_HELPER="1"
fi

# ── 1. démarrer la stack ─────────────────────────────────────────
step "Démarrage de la stack Eldir"
docker compose -f "$COMPOSE_FILE" up -d postgres redis backend frontend
ok "Containers lancés"

# ── 2. attendre que /setup/status réponde ────────────────────────
step "Attente du backend (peut prendre 30s au 1er boot)"
for _ in $(seq 1 60); do
    if curl -fsS "$API_URL/api/v1/setup/status" >/dev/null 2>&1; then
        break
    fi
    sleep 1
done
if ! curl -fsS "$API_URL/api/v1/setup/status" >/dev/null 2>&1; then
    fail "Le backend ne répond pas sur $API_URL - voir 'docker compose -f $COMPOSE_FILE logs backend'."
fi
ok "Backend en ligne"

STATUS_JSON="$(curl -fsS "$API_URL/api/v1/setup/status")"
NEEDS_BOOTSTRAP="$(printf '%s' "$STATUS_JSON" | python3 -c 'import sys, json; print(json.load(sys.stdin)["needs_bootstrap"])')"

if [[ "$NEEDS_BOOTSTRAP" != "True" ]]; then
    warn "Eldir est déjà installé sur cette instance - abandon."
    warn "Pour modifier les credentials, va dans Settings > Claude depuis l'UI."
    exit 0
fi

# ── 3. récupérer le bootstrap_token depuis les logs ──────────────
step "Récupération du bootstrap token"
BOOTSTRAP_TOKEN="$(docker logs "$BACKEND_CONTAINER" 2>&1 \
    | grep -oE 'ELDIR_BOOTSTRAP_TOKEN=[A-Za-z0-9_-]+' \
    | tail -n1 \
    | sed 's/^ELDIR_BOOTSTRAP_TOKEN=//' || true)"

if [[ -z "$BOOTSTRAP_TOKEN" ]]; then
    fail "Bootstrap token introuvable dans les logs du container '$BACKEND_CONTAINER'.
Astuce : 'docker logs $BACKEND_CONTAINER 2>&1 | grep ELDIR_BOOTSTRAP_TOKEN'"
fi
ok "Token capturé"

# ── 4. compte admin ──────────────────────────────────────────────
step "Création du compte administrateur"
while true; do
    ask "Email admin :"; read -r ADMIN_EMAIL
    [[ "$ADMIN_EMAIL" == *"@"*.* ]] && break
    warn "Email invalide, réessaie."
done
while true; do
    ask "Mot de passe (≥ 8 caractères) :"; read -rs ADMIN_PW; echo
    ask "Confirmation :"; read -rs ADMIN_PW2; echo
    if [[ "$ADMIN_PW" == "$ADMIN_PW2" && ${#ADMIN_PW} -ge 8 ]]; then break; fi
    warn "Les mots de passe ne correspondent pas ou trop court."
done
ask "Nom affiché (optionnel) :"; read -r ADMIN_DISPLAY

# ── 5. token Claude Pro/Max ──────────────────────────────────────
step "Connexion Claude Pro/Max"
echo "Eldir va te connecter à ton compte Claude Pro/Max (recommandé)."
echo "Une fenêtre navigateur va s'ouvrir pour autoriser Eldir."
echo

CLAUDE_OAUTH_TOKEN=""
if [[ "$HAS_CLAUDE_HELPER" == "1" ]]; then
    ask "Lancer 'claude setup-token' maintenant ? [Y/n] :"; read -r REPLY
    REPLY="${REPLY:-Y}"
    if [[ "$REPLY" =~ ^[Yy]$ ]]; then
        echo
        echo "Quand le CLI t'invite à coller le code de vérification :"
        echo "  1. ouvre le lien dans ton navigateur"
        echo "  2. connecte-toi avec ton compte Claude Pro/Max"
        echo "  3. colle le code retourné dans le terminal"
        echo
        # On capture stdout pour parser le token, tout en laissant le CLI
        # interactif sur le terminal de l'utilisateur via /dev/tty.
        TMP_OUT="$(mktemp)"
        if $CLAUDE_BIN setup-token 2>&1 \
            | tee "$TMP_OUT" \
            ; then
            CLAUDE_OAUTH_TOKEN="$(grep -oE 'sk-ant-oat[A-Za-z0-9_-]+' "$TMP_OUT" \
                | tail -n1 || true)"
            rm -f "$TMP_OUT"
            if [[ -n "$CLAUDE_OAUTH_TOKEN" ]]; then
                ok "Token Pro/Max récupéré"
            else
                warn "Token Pro/Max non détecté dans la sortie - colle-le manuellement ci-dessous."
            fi
        else
            rm -f "$TMP_OUT"
            warn "'claude setup-token' a échoué - on continue sans token Pro/Max."
        fi
    fi
fi

if [[ -z "$CLAUDE_OAUTH_TOKEN" ]]; then
    ask "Coller un token Pro/Max existant (laisser vide pour passer) :"
    read -r CLAUDE_OAUTH_TOKEN
fi

# ── 6. API key Console (fallback optionnel) ──────────────────────
step "Clé API Anthropic Console (optionnelle, fallback)"
echo "Si tu as une clé API Anthropic Console (sk-ant-api...), tu peux la"
echo "configurer comme fallback. À récupérer sur https://platform.claude.com"
ask "Coller une clé API Console (laisser vide pour passer) :"
read -r CLAUDE_API_KEY

if [[ -z "$CLAUDE_OAUTH_TOKEN" && -z "$CLAUDE_API_KEY" ]]; then
    warn "Aucun credential Claude configuré - tu pourras les ajouter via Settings > Claude."
fi

# ── 7. POST /setup/bootstrap ─────────────────────────────────────
step "Création de l'administrateur et persistance des credentials"

PAYLOAD="$(python3 - "$BOOTSTRAP_TOKEN" "$ADMIN_EMAIL" "$ADMIN_PW" "$ADMIN_DISPLAY" "$CLAUDE_OAUTH_TOKEN" "$CLAUDE_API_KEY" <<'PY'
import json, sys
token, email, pw, display, oauth, api_key = sys.argv[1:7]
creds = []
if oauth.strip():
    creds.append({"kind": "oauth_token", "value": oauth.strip(), "label": "Pro/Max"})
if api_key.strip():
    creds.append({"kind": "api_key", "value": api_key.strip(), "label": "Console"})
body = {
    "bootstrap_token": token,
    "admin_email": email,
    "admin_password": pw,
    "claude_credentials": creds,
}
if display.strip():
    body["admin_display_name"] = display.strip()
sys.stdout.write(json.dumps(body))
PY
)"

HTTP_CODE="$(curl -sS -o /tmp/eldir-bootstrap.out -w '%{http_code}' \
    -X POST "$API_URL/api/v1/setup/bootstrap" \
    -H 'Content-Type: application/json' \
    -d "$PAYLOAD")"

if [[ "$HTTP_CODE" != "201" ]]; then
    echo
    fail "Bootstrap échoué (HTTP $HTTP_CODE) - réponse:
$(cat /tmp/eldir-bootstrap.out)"
fi
rm -f /tmp/eldir-bootstrap.out
ok "Admin créé, credentials chiffrés et stockés"

# ── 8. récap ─────────────────────────────────────────────────────
hr
printf '%s\n' "$(b "🔥 Eldir est prêt.")"
printf '\n'
printf '  Frontend : %s\n' "$FRONTEND_URL"
printf '  Backend  : %s/api/v1\n' "$API_URL"
printf '  Login    : %s\n' "$ADMIN_EMAIL"
printf '\n'
echo "Connecte-toi sur le frontend pour démarrer ta première session."
