#!/usr/bin/env bash
# Génère shared/openapi.json puis frontend/src/lib/types/api-generated.ts
# Pipeline DRY: la source de vérité est Pydantic. Aucun type ne doit
# être défini côté frontend pour ce qui existe côté backend.
#
# Usage local :
#   ./scripts/gen-types.sh
#
# CI : voir .github/workflows/types.yml

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND="$ROOT/backend"
SHARED="$ROOT/shared"
FRONTEND="$ROOT/frontend"

mkdir -p "$SHARED"

echo "→ Export OpenAPI depuis le backend FastAPI..."
(
  cd "$BACKEND"
  uv run python "$ROOT/scripts/export_openapi.py" > "$SHARED/openapi.json"
)
echo "  ✓ shared/openapi.json"

echo "→ Génération des types TS (openapi-typescript)..."
(
  cd "$FRONTEND"
  pnpm dlx openapi-typescript@7 \
    "$SHARED/openapi.json" \
    --output "src/lib/types/api-generated.ts" \
    --root-types true \
    --enum true
)
echo "  ✓ frontend/src/lib/types/api-generated.ts"

echo "Terminé."
