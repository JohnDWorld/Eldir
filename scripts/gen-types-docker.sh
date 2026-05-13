#!/usr/bin/env bash
# Variante 100% Docker — aucun outil requis sur la machine hôte.
#
# Étape 1 : exporte OpenAPI via le container backend (uv).
# Étape 2 : génère les types TS via une image node:20-alpine éphémère.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SHARED="$ROOT/shared"
mkdir -p "$SHARED"

echo "→ Export OpenAPI via container backend..."
docker compose -f "$ROOT/docker-compose.dev.yml" run --rm --no-deps \
  -v "$ROOT/scripts:/scripts:ro" \
  -v "$SHARED:/shared" \
  backend \
  sh -c "uv run python /scripts/export_openapi.py > /shared/openapi.json"
echo "  ✓ shared/openapi.json"

echo "→ Génération des types TS via container node éphémère..."
docker run --rm \
  -v "$ROOT/frontend:/frontend" \
  -v "$SHARED:/shared:ro" \
  -w /frontend \
  node:20-alpine \
  sh -c "corepack enable >/dev/null 2>&1 && \
         corepack prepare pnpm@9.12.0 --activate >/dev/null 2>&1 && \
         pnpm dlx openapi-typescript@7 /shared/openapi.json \
           --output /frontend/src/lib/types/api-generated.ts \
           --root-types true --enum true"
echo "  ✓ frontend/src/lib/types/api-generated.ts"

echo "Terminé."
