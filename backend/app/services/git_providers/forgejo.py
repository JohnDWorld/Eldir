"""Forgejo provider - squelette. Implémentation réelle en Phase 3."""

from __future__ import annotations

from app.core.exceptions import GitProviderError
from app.services.git_providers.base import (
    GitProviderInterface,
    PullRequestRef,
    RepoRef,
)


class ForgejoProvider(GitProviderInterface):
    name = "forgejo"

    def __init__(self, base_url: str, token: str) -> None:
        self._base_url = base_url.rstrip("/")
        self._token = token

    async def list_repos(self) -> list[RepoRef]:
        raise GitProviderError("ForgejoProvider.list_repos non implémenté (Phase 3).")

    async def get_repo(self, full_name: str) -> RepoRef:
        raise GitProviderError("ForgejoProvider.get_repo non implémenté (Phase 3).")

    async def create_repo(
        self,
        name: str,
        *,
        private: bool = True,
        description: str | None = None,
    ) -> RepoRef:
        raise GitProviderError("ForgejoProvider.create_repo non implémenté (Phase 3).")

    async def get_branches(self, full_name: str) -> list[str]:
        raise GitProviderError("ForgejoProvider.get_branches non implémenté (Phase 3).")

    async def get_default_branch(self, full_name: str) -> str:
        raise GitProviderError(
            "ForgejoProvider.get_default_branch non implémenté (Phase 3)."
        )

    async def create_pr(
        self,
        full_name: str,
        *,
        head: str,
        base: str,
        title: str,
        body: str | None = None,
    ) -> PullRequestRef:
        raise GitProviderError("ForgejoProvider.create_pr non implémenté (Phase 3).")
