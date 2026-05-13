"""Exporte le schéma OpenAPI du backend vers un JSON sur disque.

Source unique de vérité des types API. Lancé en CI et en local avant
chaque génération des types TS.

Usage :
    cd backend && uv run python ../scripts/export_openapi.py > ../shared/openapi.json
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path


def _setup_minimal_env() -> None:
    """Pose des valeurs neutres pour pouvoir importer l'app sans .env."""
    os.environ.setdefault("APP_ENV", "test")
    os.environ.setdefault(
        "DATABASE_URL", "postgresql+asyncpg://eldir:eldir@localhost:5432/eldir"
    )
    os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
    os.environ.setdefault("ENCRYPTION_KEY", "x" * 44)
    os.environ.setdefault("JWT_SECRET", "export-only-not-used")


def main() -> int:
    _setup_minimal_env()

    # backend/ doit être sur le sys.path
    backend_dir = Path(__file__).resolve().parent.parent / "backend"
    if str(backend_dir) not in sys.path:
        sys.path.insert(0, str(backend_dir))

    from app.main import create_app  # noqa: E402  (après configuration env)

    app = create_app()
    schema = app.openapi()

    out = json.dumps(schema, indent=2, ensure_ascii=False, sort_keys=True)
    sys.stdout.write(out)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
