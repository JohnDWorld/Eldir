"""Point d'entrée FastAPI d'Eldir."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1 import api_router
from app.core.bootstrap import emit_bootstrap_token_if_needed
from app.core.config import get_settings
from app.core.exceptions import EldirError
from app.core.logging import configure_logging, get_logger
from app.mcp_http import construire_app_mcp
from app.services.singletons import init_singletons, shutdown_singletons
from app.ws import ws_router


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    configure_logging()
    logger = get_logger("eldir.lifespan")
    logger.info("app.startup", env=get_settings().app_env)
    if not get_settings().is_test:
        try:
            await emit_bootstrap_token_if_needed()
        except Exception:
            logger.exception("bootstrap.hook.error")
        try:
            await init_singletons()
        except Exception:
            logger.exception("singletons.init.error")
    try:
        # L'app MCP montée a son propre lifespan, que FastAPI ne joue pas pour
        # une sous-app : son gestionnaire de sessions doit tourner ici, sinon
        # toute requête vers /api/mcp/ échoue. Imbriqué DANS le try : à l'arrêt
        # il se ferme (et coupe les appels en cours) avant les singletons que
        # ces appels utilisent.
        async with app.state.mcp.session_manager.run():
            yield
    finally:
        if not get_settings().is_test:
            await shutdown_singletons()
        logger.info("app.shutdown")


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        debug=settings.app_debug,
        lifespan=lifespan,
    )
    # Un serveur MCP par application, pas un par module : son gestionnaire de
    # sessions ne tourne qu'une fois, et chaque `create_app()` rejoue le lifespan.
    mcp, mcp_app = construire_app_mcp()
    app.state.mcp = mcp

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(EldirError)
    async def _eldir_error_handler(_: Request, exc: EldirError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "code": exc.code,
                "message": exc.message,
                "details": exc.details,
            },
        )

    app.include_router(api_router, prefix=settings.api_prefix)
    app.include_router(ws_router)
    # Surface d'agent externe. Montée hors du routeur v1 : le transport MCP
    # parle JSON-RPC sur SSE, pas du REST versionné.
    app.mount("/api/mcp", mcp_app)
    return app


app = create_app()
