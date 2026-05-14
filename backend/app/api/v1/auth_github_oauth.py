"""Routes /auth/github/oauth — flow "Connect with GitHub" (web).

- `GET  /auth/github/oauth/config`   : statut de configuration (utile au front).
- `POST /auth/github/oauth/start`    : génère l'URL d'autorisation (authentifié).
- `GET  /auth/github/oauth/callback` : reçoit le code GitHub, échange, persiste,
  redirige vers le frontend.
"""

from __future__ import annotations

from fastapi import APIRouter, Query
from fastapi.responses import RedirectResponse

from app.core.config import get_settings
from app.core.deps import CurrentUserId, DbDep, RedisDep, SettingsDep
from app.core.exceptions import GitProviderError
from app.schemas.common import EldirModel
from app.schemas.git_credential import GitCredentialCreate
from app.services import github_oauth_service
from app.services.git_credential_service import git_credential_service

router = APIRouter(prefix="/auth/github/oauth", tags=["auth"])


class GitHubOAuthConfig(EldirModel):
    enabled: bool
    client_id: str | None = None


class GitHubOAuthStartResponse(EldirModel):
    authorize_url: str


@router.get("/config", response_model=GitHubOAuthConfig)
async def oauth_config(settings: SettingsDep) -> GitHubOAuthConfig:
    return GitHubOAuthConfig(
        enabled=settings.github_oauth_enabled,
        client_id=settings.github_oauth_client_id if settings.github_oauth_enabled else None,
    )


@router.post("/start", response_model=GitHubOAuthStartResponse)
async def oauth_start(
    user_id: CurrentUserId,
    settings: SettingsDep,
    redis: RedisDep,
) -> GitHubOAuthStartResponse:
    url = await github_oauth_service.start_oauth_flow(settings, redis, user_id)
    return GitHubOAuthStartResponse(authorize_url=url)


@router.get("/callback")
async def oauth_callback(
    db: DbDep,
    redis: RedisDep,
    code: str | None = Query(default=None),
    state: str | None = Query(default=None),
    error: str | None = Query(default=None),
    error_description: str | None = Query(default=None),
) -> RedirectResponse:
    settings = get_settings()
    frontend_target = f"{settings.frontend_base_url.rstrip('/')}/settings/git"

    if error:
        return RedirectResponse(
            url=f"{frontend_target}?github=error&reason={error_description or error}",
            status_code=303,
        )
    if not code or not state:
        return RedirectResponse(
            url=f"{frontend_target}?github=error&reason=missing_params",
            status_code=303,
        )

    try:
        user_id = await github_oauth_service.consume_state(redis, state)
        payload = await github_oauth_service.exchange_code_for_token(settings, code)
    except GitProviderError as exc:
        return RedirectResponse(
            url=f"{frontend_target}?github=error&reason={exc.message}",
            status_code=303,
        )

    access_token = payload["access_token"]
    await git_credential_service.upsert(
        db,
        user_id,
        GitCredentialCreate(
            provider="github",
            token=access_token,
            label="OAuth (Connect with GitHub)",
            base_url=None,
        ),
    )
    await db.commit()
    return RedirectResponse(url=f"{frontend_target}?github=connected", status_code=303)
