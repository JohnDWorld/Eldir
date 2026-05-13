# Eldir — Backend

FastAPI + Claude Agent SDK. Voir [`AGENTS.md`](../AGENTS.md), [`CLAUDE.md`](../CLAUDE.md), [`ROADMAP.md`](../ROADMAP.md) à la racine.

## Démarrage

```bash
cp .env.example .env
# Générer ENCRYPTION_KEY :
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
# Coller dans .env

uv sync
uv run alembic upgrade head
uv run uvicorn app.main:app --reload --port 8000
```

## Qualité (avant tout commit)

```bash
uv run ruff check --fix
uv run ruff format
uv run mypy app
uv run pytest
```

## Structure

```
app/
├── api/v1/        # Routes REST (fines, déléguent aux services)
├── ws/            # WebSocket handlers
├── core/          # config, exceptions, constants, security, deps, logging
├── db/            # SQLAlchemy 2.0 async + modèles
├── services/      # Logique métier (SessionManager, GitProviders, Worktree, EventBus)
├── schemas/       # Pydantic v2 (source de vérité des types API)
└── main.py        # create_app + lifespan + handlers d'exception
```

## Phase actuelle

Phase 0 — Fondations. Les routes business (`create_session`, `send_message`, `create_project`)
sont des squelettes qui lèvent `NotImplementedError`. À implémenter en Phase 1.
