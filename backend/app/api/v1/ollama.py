"""Routes /ollama - Phase 6 (mode données sensibles).

Permet à l'utilisateur d'effectuer des transformations LOCALES sur du
texte (masquage de secrets, anonymisation, résumé) avant de l'envoyer
à Claude. Ollama tourne en local, rien ne traverse le réseau.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from app.core.config import get_settings
from app.core.deps import CurrentUserId, DbDep
from app.schemas.ollama import (
    OllamaModelInfo,
    OllamaSettingsRead,
    OllamaSettingsWrite,
    OllamaStatus,
    OllamaTransformRequest,
    OllamaTransformResponse,
)
from app.services.ollama_service import ollama_service
from app.services.ollama_settings_service import ollama_settings_service

router = APIRouter(prefix="/ollama", tags=["ollama"])


@router.get("/status", response_model=OllamaStatus)
async def get_status(user_id: CurrentUserId) -> OllamaStatus:
    s = await ollama_service.status()
    return OllamaStatus(
        enabled=s.enabled,
        base_url=s.base_url,
        reachable=s.reachable,
        error=s.error,
        default_model=s.default_model,
        available_models=[
            OllamaModelInfo(
                name=m.name,
                size_bytes=m.size_bytes,
                modified_at=m.modified_at,
            )
            for m in s.available_models
        ],
    )


@router.post("/transform", response_model=OllamaTransformResponse)
async def transform(
    payload: OllamaTransformRequest, user_id: CurrentUserId
) -> OllamaTransformResponse:
    settings = get_settings()
    if not settings.ollama_enabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Ollama n'est pas configuré sur ce serveur Eldir.",
        )
    used_model = payload.model or settings.ollama_default_model
    result = await ollama_service.transform(
        text=payload.text, mode=payload.mode, model=payload.model
    )
    return OllamaTransformResponse(text=result, mode=payload.mode, model_used=used_model)


@router.get("/settings", response_model=OllamaSettingsRead)
async def get_ollama_settings(user_id: CurrentUserId, db: DbDep) -> OllamaSettingsRead:
    row = await ollama_settings_service.get(db)
    return OllamaSettingsRead(expose_to_sessions=row.expose_to_sessions)


@router.put("/settings", response_model=OllamaSettingsRead)
async def set_ollama_settings(
    payload: OllamaSettingsWrite, user_id: CurrentUserId, db: DbDep
) -> OllamaSettingsRead:
    row = await ollama_settings_service.set_expose(db, value=payload.expose_to_sessions)
    await db.commit()
    return OllamaSettingsRead(expose_to_sessions=row.expose_to_sessions)
