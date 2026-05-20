"""Git providers - registry et factory."""

from app.core.constants import PROVIDER_FORGEJO, PROVIDER_GITHUB, SUPPORTED_PROVIDERS
from app.core.exceptions import GitProviderError
from app.services.git_providers.base import (
    GitProviderInterface,
    PullRequestRef,
    RepoRef,
)
from app.services.git_providers.forgejo import ForgejoProvider
from app.services.git_providers.github import GitHubProvider


def make_provider(
    name: str,
    *,
    token: str,
    base_url: str | None = None,
) -> GitProviderInterface:
    if name not in SUPPORTED_PROVIDERS:
        raise GitProviderError(f"Provider non supporté: {name}")
    if name == PROVIDER_GITHUB:
        return GitHubProvider(token=token)
    if name == PROVIDER_FORGEJO:
        if not base_url:
            raise GitProviderError("Forgejo nécessite une base_url.")
        return ForgejoProvider(base_url=base_url, token=token)
    raise GitProviderError(f"Provider inconnu: {name}")  # pragma: no cover


__all__ = [
    "ForgejoProvider",
    "GitHubProvider",
    "GitProviderInterface",
    "PullRequestRef",
    "RepoRef",
    "make_provider",
]
