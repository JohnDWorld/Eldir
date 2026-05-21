"""Router v1 - agrège tous les sous-routers de l'API."""

from fastapi import APIRouter

from app.api.v1.auth import router as auth_router
from app.api.v1.auth_github_oauth import router as auth_github_oauth_router
from app.api.v1.costs import router as costs_router
from app.api.v1.health import router as health_router
from app.api.v1.ollama import router as ollama_router
from app.api.v1.mission_templates import (
    presets_router as templates_presets_router,
    router as mission_templates_router,
)
from app.api.v1.projects import router as projects_router
from app.api.v1.providers import router as providers_router
from app.api.v1.sessions import router as sessions_router
from app.api.v1.settings_claude import router as settings_claude_router
from app.api.v1.settings_git import router as settings_git_router
from app.api.v1.setup import router as setup_router
from app.api.v1.system_prompts import router as system_prompts_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(setup_router)
api_router.include_router(auth_router)
api_router.include_router(auth_github_oauth_router)
api_router.include_router(providers_router)
api_router.include_router(projects_router)
api_router.include_router(mission_templates_router)
api_router.include_router(templates_presets_router)
api_router.include_router(sessions_router)
api_router.include_router(costs_router)
api_router.include_router(settings_claude_router)
api_router.include_router(settings_git_router)
api_router.include_router(system_prompts_router)
api_router.include_router(ollama_router)
