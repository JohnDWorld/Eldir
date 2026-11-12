"""GitProviderInterface - abstraction multi-providers (GitHub, Forgejo, …).

Cf. ROADMAP §Phase 3 et AGENTS.md §Architecture: tout couplage à GitHub
spécifiquement est INTERDIT en dehors d'une implémentation concrète.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


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
    # `open`, `merged` ou `closed`. Les deux forges disent `closed` pour une PR
    # mergée et ajoutent `merged: true` : c'est `pr_depuis_payload` qui sépare.
    state: str = "open"
    head_sha: str = ""


def pr_depuis_payload(data: dict[str, Any]) -> PullRequestRef:
    """Une PR telle que GitHub et Forgejo la rendent : les deux ont la même forme."""
    if data.get("merged"):
        state = "merged"
    elif data.get("state") == "closed":
        state = "closed"
    else:
        state = "open"
    head = data["head"]
    return PullRequestRef(
        number=int(data["number"]),
        url=str(data["html_url"]),
        head=str(head["ref"]),
        base=str(data["base"]["ref"]),
        title=str(data["title"]),
        state=state,
        head_sha=str(head.get("sha") or ""),
    )


CHECKS_VERT = "vert"
CHECKS_ROUGE = "rouge"
CHECKS_EN_COURS = "en_cours"
CHECKS_AUCUN = "aucun"


@dataclass(slots=True, frozen=True)
class ChecksReport:
    """L'état agrégé des checks d'un commit, et le nom de ceux qui ont échoué."""

    etat: str
    en_echec: tuple[str, ...] = ()


def ajouter_etat_global(
    etats: list[tuple[str, str]], global_brut: object, *, a_des_statuts: bool
) -> None:
    """Le `state` global du statut combiné sert de plancher aux états individuels.

    Un `pending` global sans aucun statut individuel ne dit rien (GitHub le rend
    ainsi, même quand tous ses check runs sont verts) : il ne devient pas « en cours ».
    """
    if global_brut in ("failure", "error") and not any(e == CHECKS_ROUGE for _, e in etats):
        etats.append(("statut combiné", CHECKS_ROUGE))
    elif (
        global_brut == "pending"
        and a_des_statuts
        and not any(e == CHECKS_EN_COURS for _, e in etats)
    ):
        etats.append(("statut combiné", CHECKS_EN_COURS))


def agreger(etats: list[tuple[str, str]]) -> ChecksReport:
    """(nom, état normalisé) vers un état unique. Un seul rouge suffit à tout rougir."""
    if not etats:
        return ChecksReport(CHECKS_AUCUN)
    rouges = tuple(nom for nom, etat in etats if etat == CHECKS_ROUGE)
    if rouges:
        return ChecksReport(CHECKS_ROUGE, rouges)
    if any(etat == CHECKS_EN_COURS for _, etat in etats):
        return ChecksReport(CHECKS_EN_COURS)
    return ChecksReport(CHECKS_VERT)


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

    @abstractmethod
    async def get_pr(self, full_name: str, number: int) -> PullRequestRef: ...

    @abstractmethod
    async def checks(self, full_name: str, sha: str) -> ChecksReport: ...

    @abstractmethod
    async def merge_pr(self, full_name: str, number: int, sha: str) -> None:
        """Merge à condition que la tête de la PR soit encore `sha`, le commit vérifié."""
