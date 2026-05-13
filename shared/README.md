# shared/

Artefacts partagés entre backend et frontend, **générés** à partir du backend.

## Pipeline DRY

Source de vérité : les schémas Pydantic et les `response_model` FastAPI.

```
backend (Pydantic + FastAPI)
       │
       ├─ scripts/export_openapi.py
       ▼
shared/openapi.json
       │
       ├─ openapi-typescript@7
       ▼
frontend/src/lib/types/api-generated.ts
```

Aucun type TS dupliqué à la main. Cf. AGENTS.md §Anti-patterns.

## Régénérer

```bash
# Si tu as uv + pnpm installés localement :
./scripts/gen-types.sh

# Sinon (100% Docker) :
./scripts/gen-types-docker.sh
```

CI : `.github/workflows/types.yml` rejoue ces scripts et fait échouer le build
si `api-generated.ts` est désynchronisé (drift).
