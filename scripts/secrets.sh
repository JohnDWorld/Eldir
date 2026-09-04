#!/usr/bin/env bash
# Chiffrement des fichiers d'environnement d'Eldir (SOPS + age).
#
#   ./scripts/secrets.sh encrypt          secrets/*.env     -> secrets/*.enc.env
#   ./scripts/secrets.sh decrypt          secrets/*.enc.env -> secrets/*.env
#   ./scripts/secrets.sh deploy [hôte]    déchiffre en mémoire et pousse en SSH
#
# Les fichiers en clair restent dans `secrets/` (gitignoré). Seuls les
# `.enc.env` partent sur GitHub. Cf. .sops.yaml pour les destinataires.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

SSH_HOST="${ELDIR_SSH_HOST:-eldir}"
REMOTE_DIR="${ELDIR_REMOTE_DIR:-eldir}"

# Fichier en clair -> chemin de destination dans le repo déployé.
declare -A DESTINATIONS=(
  ["secrets/root.env"]=".env"
  ["secrets/backend.env"]="backend/.env"
)

die() { echo "✗ $*" >&2; exit 1; }
command -v sops >/dev/null || die "sops absent (https://github.com/getsops/sops/releases)"

encrypt() {
  shopt -s nullglob
  local found=0
  for clear in secrets/*.env; do
    [[ "$clear" == *.enc.env ]] && continue
    sops -e "$clear" > "${clear%.env}.enc.env"
    echo "✓ ${clear%.env}.enc.env"
    found=1
  done
  ((found)) || die "aucun secrets/*.env à chiffrer"
}

decrypt() {
  shopt -s nullglob
  local found=0
  for enc in secrets/*.enc.env; do
    local clear="${enc%.enc.env}.env"
    sops -d "$enc" > "$clear"
    chmod 600 "$clear"
    echo "✓ $clear"
    found=1
  done
  ((found)) || die "aucun secrets/*.enc.env à déchiffrer"
}

deploy() {
  local host="${1:-$SSH_HOST}"
  for enc in secrets/*.enc.env; do
    local clear="${enc%.enc.env}.env"
    local dest="${DESTINATIONS[$clear]:-}"
    [[ -n "$dest" ]] || die "pas de destination connue pour $clear (cf. DESTINATIONS)"
    # Le clair ne touche jamais le disque local : sops écrit dans le pipe SSH.
    sops -d "$enc" | ssh "$host" "umask 077 && cat > '$REMOTE_DIR/$dest'"
    echo "✓ $host:$REMOTE_DIR/$dest"
  done
}

case "${1:-}" in
  encrypt) encrypt ;;
  decrypt) decrypt ;;
  deploy)  shift; deploy "$@" ;;
  *) sed -n '2,9p' "$0" | sed 's/^# \{0,1\}//'; exit 1 ;;
esac
