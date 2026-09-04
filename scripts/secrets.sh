#!/usr/bin/env bash
# Chiffrement des fichiers d'environnement d'Eldir (SOPS + age).
#
#   ./scripts/secrets.sh encrypt          <nom>.env     -> <nom>.enc.env
#   ./scripts/secrets.sh decrypt          <nom>.enc.env -> <nom>.env
#   ./scripts/secrets.sh deploy [hôte]    déchiffre en mémoire et pousse en SSH
#
# Les fichiers vivent dans un dépôt SÉPARÉ, privé : même chiffré, un secret
# poussé sur un dépôt public y reste pour toujours (forks, caches, archives).
# Par défaut `../eldir-secrets`, sinon ELDIR_SECRETS_DIR.
#
# Ce dépôt-là contient le `.sops.yaml` qui liste les clés age destinataires,
# les `<nom>.enc.env` chiffrés (versionnés) et les `<nom>.env` en clair
# (gitignorés).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SECRETS_DIR="${ELDIR_SECRETS_DIR:-$ROOT/../eldir-secrets}"
SSH_HOST="${ELDIR_SSH_HOST:-eldir}"
REMOTE_DIR="${ELDIR_REMOTE_DIR:-eldir}"

# Nom du fichier -> chemin de destination dans le repo déployé.
declare -A DESTINATIONS=(
  ["root"]=".env"
  ["backend"]="backend/.env"
)

die() { echo "✗ $*" >&2; exit 1; }
command -v sops >/dev/null || die "sops absent (https://github.com/getsops/sops/releases)"
[[ -d "$SECRETS_DIR" ]] || die "dépôt de secrets introuvable : $SECRETS_DIR (cf. ELDIR_SECRETS_DIR)"
cd "$SECRETS_DIR"
shopt -s nullglob

encrypt() {
  local found=0
  for clear in *.env; do
    [[ "$clear" == *.enc.env ]] && continue
    sops -e "$clear" > "${clear%.env}.enc.env"
    echo "✓ $SECRETS_DIR/${clear%.env}.enc.env"
    found=1
  done
  ((found)) || die "aucun *.env à chiffrer dans $SECRETS_DIR"
}

decrypt() {
  local found=0
  for enc in *.enc.env; do
    sops -d "$enc" > "${enc%.enc.env}.env"
    chmod 600 "${enc%.enc.env}.env"
    echo "✓ $SECRETS_DIR/${enc%.enc.env}.env"
    found=1
  done
  ((found)) || die "aucun *.enc.env à déchiffrer dans $SECRETS_DIR"
}

deploy() {
  local host="${1:-$SSH_HOST}"
  for enc in *.enc.env; do
    local name="${enc%.enc.env}"
    local dest="${DESTINATIONS[$name]:-}"
    [[ -n "$dest" ]] || die "pas de destination connue pour $name (cf. DESTINATIONS)"
    # Le clair ne touche jamais le disque local : sops écrit dans le pipe SSH.
    sops -d "$enc" | ssh "$host" "umask 077 && cat > '$REMOTE_DIR/$dest'"
    echo "✓ $host:$REMOTE_DIR/$dest"
  done
}

usage() {
  cat <<USAGE
Chiffrement des environnements d'Eldir (SOPS + age).

  ./scripts/secrets.sh encrypt          <nom>.env     -> <nom>.enc.env
  ./scripts/secrets.sh decrypt          <nom>.enc.env -> <nom>.env
  ./scripts/secrets.sh deploy [hôte]    déchiffre en mémoire et pousse en SSH

Dépôt de secrets : $SECRETS_DIR
Serveur par défaut : $SSH_HOST:$REMOTE_DIR
USAGE
}

case "${1:-}" in
  encrypt) encrypt ;;
  decrypt) decrypt ;;
  deploy)  shift; deploy "$@" ;;
  *) usage; exit 1 ;;
esac
