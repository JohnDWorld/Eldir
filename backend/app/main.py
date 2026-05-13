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
from app.services.singletons import init_singletons, shutdown_singletons
from app.ws import ws_router


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    configure_logging()
    logger = get_logger("eldir.lifespan")
    logger.info("app.startup", env=get_settings().app_env)
    if not get_settings().is_test:
        try:
            await emit_bootstrap_token_if_needed()
        except Exception:  # noqa: BLE001
            logger.exception("bootstrap.hook.error")
        try:
            await init_singletons()
        except Exception:  # noqa: BLE001
            logger.exception("singletons.init.error")
    try:
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
    return app


app = create_app()
