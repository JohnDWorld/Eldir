"""GitHubOAuthService - flow "Connect with GitHub" (OAuth App, web flow).

Le user clique "Connect with GitHub" → backend génère un `state`, le stocke dans
Redis avec le `user_id` (TTL court), et renvoie l'URL d'autorisation. GitHub
redirige ensuite sur `/auth/github/oauth/callback`, le backend résout le state
→ échange `code` contre `access_token` → persiste comme `GitCredential`.

Pré-requis côté GitHub :
- Créer une OAuth App sur https://github.com/settings/applications/new
- Authorization callback URL = `{github_oauth_redirect_url}` (cf. Settings)
- Récupérer client_id + client_secret, les mettre en variables d'env.
"""

from __future__ import annotations

import secrets
from typing import Any
from urllib.parse import urlencode

import httpx
from redis.asyncio import Redis

from app.core.config import Settings
from app.core.exceptions import GitProviderError, ValidationError

GITHUB_AUTHORIZE_URL = "https://github.com/login/oauth/authorize"
GITHUB_ACCESS_TOKEN_URL = "https://github.com/login/oauth/access_token"

STATE_REDIS_PREFIX = "eldir:gh-oauth:state:"
STATE_TTL_SECONDS = 600  # 10 minutes


def _ensure_configured(settings: Settings) -> None:
    if not settings.github_oauth_enabled:
        raise ValidationError(
            "OAuth GitHub non configuré. Définis GITHUB_OAUTH_CLIENT_ID et "
            "GITHUB_OAUTH_CLIENT_SECRET dans l'env du backend."
        )


def _state_key(state: str) -> str:
    return f"{STATE_REDIS_PREFIX}{state}"


async def start_oauth_flow(
    settings: Settings, redis: Redis, user_id: str
) -> str:
    """Génère un state, le persiste, retourne l'URL d'autorisation GitHub."""
    _ensure_configured(settings)
    state = secrets.token_urlsafe(32)
    await redis.set(_state_key(state), user_id, ex=STATE_TTL_SECONDS)
    params = {
        "client_id": settings.github_oauth_client_id,
        "redirect_uri": settings.github_oauth_redirect_url,
        "scope": settings.github_oauth_scopes,
        "state": state,
        "allow_signup": "false",
    }
    return f"{GITHUB_AUTHORIZE_URL}?{urlencode(params)}"


async def consume_state(redis: Redis, state: str) -> str:
    """Récupère et invalide le state ; retourne l'user_id associé."""
    key = _state_key(state)
    user_id = await redis.get(key)
    if not user_id:
        raise ValidationError("État OAuth invalide ou expiré. Relance la connexion.")
    await redis.delete(key)
    return user_id if isinstance(user_id, str) else user_id.decode("utf-8")


async def exchange_code_for_token(settings: Settings, code: str) -> dict[str, Any]:
    """Échange le code OAuth contre un access_token. Renvoie le payload GitHub."""
    _ensure_configured(settings)
    assert settings.github_oauth_client_secret is not None  # garanti par _ensure_configured
    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.post(
            GITHUB_ACCESS_TOKEN_URL,
            data={
                "client_id": settings.github_oauth_client_id,
                "client_secret": settings.github_oauth_client_secret.get_secret_value(),
                "code": code,
                "redirect_uri": settings.github_oauth_redirect_url,
            },
            headers={"Accept": "application/json"},
        )
    if response.status_code != 200:
        raise GitProviderError(
            f"GitHub OAuth token exchange a échoué (HTTP {response.status_code}).",
            details={"body": response.text[:500]},
        )
    payload = response.json()
    if "error" in payload:
        raise GitProviderError(
            f"GitHub OAuth : {payload.get('error_description') or payload['error']}",
            details=payload,
        )
    access_token = payload.get("access_token")
    if not access_token:
        raise GitProviderError("Réponse OAuth GitHub sans access_token.")
    return payload
