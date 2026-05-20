"""GitProviderInterface - abstraction multi-providers (GitHub, Forgejo, …).

Cf. ROADMAP §Phase 3 et AGENTS.md §Architecture: tout couplage à GitHub
spécifiquement est INTERDIT en dehors d'une implémentation concrète.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(slots=True, frozen=True)
class RepoRef:
    """Référence minimale d'un dépôt distant."""

    full_name: str  # owner/repo
    default_branch: str
    clone_url: str
    description: str | None = None
    is_private: bool = False


@dataclass(slots=True, frozen=True)
class PullRequestRef:
    number: int
    url: str
    head: str
    base: str
    title: str


class GitProviderInterface(ABC):
    """Contrat que toute implémentation provider doit respecter."""

    name: str

    @abstractmethod
    async def list_repos(self) -> list[RepoRef]: ...

    @abstractmethod
    async def get_repo(self, full_name: str) -> RepoRef: ...

    @abstractmethod
    async def create_repo(
        self,
        name: str,
        *,
        private: bool = True,
        description: str | None = None,
    ) -> RepoRef: ...

    @abstractmethod
    async def get_branches(self, full_name: str) -> list[str]: ...

    @abstractmethod
    async def get_default_branch(self, full_name: str) -> str: ...

    @abstractmethod
    async def create_pr(
        self,
        full_name: str,
        *,
        head: str,
        base: str,
        title: str,
        body: str | None = None,
    ) -> PullRequestRef: ...
