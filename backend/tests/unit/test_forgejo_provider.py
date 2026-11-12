"""Tests ForgejoProvider via httpx MockTransport."""

from __future__ import annotations

import json
from typing import Any

import httpx
import pytest
from app.core.exceptions import GitProviderError
from app.services.git_providers import forgejo
from app.services.git_providers.base import (
    CHECKS_EN_COURS,
    CHECKS_ROUGE,
    ChecksReport,
)
from app.services.git_providers.forgejo import ForgejoProvider

from tests.unit.serveur_abonne import Journal


def _mount(provider: ForgejoProvider, transport: httpx.MockTransport) -> None:
    """Force le provider à utiliser un client httpx mocké."""

    async def _client() -> httpx.AsyncClient:
        return httpx.AsyncClient(
            base_url="https://forgejo.exemple.lan/api/v1",
            headers=provider._headers,
            transport=transport,
        )

    provider._client = _client  # type: ignore[assignment]


async def test_un_refus_de_l_api_laisse_une_trace_sans_l_url_complete(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """httpx n'écrit plus ses requêtes : sans cette ligne, un 401 ne laisse rien côté serveur."""
    journal = Journal()
    monkeypatch.setattr(forgejo, "logger", journal)
    provider = ForgejoProvider(base_url="https://forgejo.exemple.lan", token="pat_test")
    _mount(
        provider,
        httpx.MockTransport(lambda request: httpx.Response(401, json={"message": "bad token"})),
    )

    with pytest.raises(GitProviderError):
        await provider.list_repos()

    # Le chemin seul : ni l'hôte, ni les paramètres de pagination, ni le jeton.
    assert journal.appels == [
        (
            "git_provider.refuse",
            {"provider": "forgejo", "methode": "GET", "chemin": "/repos/search", "status": 401},
        )
    ]


async def test_un_succes_ne_laisse_pas_de_trace(monkeypatch: pytest.MonkeyPatch) -> None:
    journal = Journal()
    monkeypatch.setattr(forgejo, "logger", journal)
    provider = ForgejoProvider(base_url="https://forgejo.exemple.lan", token="pat_test")
    _mount(provider, httpx.MockTransport(lambda request: httpx.Response(200, json={"data": []})))

    assert await provider.list_repos() == []
    assert journal.appels == []


def _pr_forgejo(*, state: str = "open", merged: bool = False) -> dict[str, Any]:
    return {
        "number": 7,
        "html_url": "https://forgejo.exemple.lan/owner/demo/pulls/7",
        "head": {"ref": "eldir/s1", "sha": "abc123"},
        "base": {"ref": "main"},
        "title": "Ajoute x",
        "state": state,
        "merged": merged,
    }


async def test_get_pr_forgejo_lit_l_etat_et_le_sha() -> None:
    provider = ForgejoProvider(base_url="https://forgejo.exemple.lan", token="t")
    _mount(provider, httpx.MockTransport(lambda r: httpx.Response(200, json=_pr_forgejo())))

    pr = await provider.get_pr("owner/demo", 7)

    assert (pr.state, pr.head_sha) == ("open", "abc123")


async def test_les_checks_forgejo_viennent_du_statut_combine() -> None:
    vus: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        vus.append(request.url.path)
        return httpx.Response(
            200,
            json={
                "state": "failure",
                "statuses": [
                    {"context": "ci / tests", "status": "success"},
                    {"context": "ci / lint", "status": "failure"},
                    {"context": "ci / docs", "status": "warning"},
                ],
            },
        )

    provider = ForgejoProvider(base_url="https://forgejo.exemple.lan", token="t")
    _mount(provider, httpx.MockTransport(handler))

    rapport = await provider.checks("owner/demo", "abc123")

    assert vus == ["/api/v1/repos/owner/demo/commits/abc123/status"]
    assert rapport == ChecksReport(CHECKS_ROUGE, ("ci / lint",))


async def test_un_statut_forgejo_en_attente_rend_la_ci_en_cours() -> None:
    provider = ForgejoProvider(base_url="https://forgejo.exemple.lan", token="t")
    _mount(
        provider,
        httpx.MockTransport(
            lambda r: httpx.Response(
                200, json={"statuses": [{"context": "ci / tests", "status": "pending"}]}
            )
        ),
    )

    assert (await provider.checks("owner/demo", "abc123")).etat == CHECKS_EN_COURS


async def test_merge_pr_forgejo_fait_un_commit_de_merge() -> None:
    vus: list[tuple[str, str, bytes]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        vus.append((request.method, request.url.path, request.content))
        return httpx.Response(200)

    provider = ForgejoProvider(base_url="https://forgejo.exemple.lan", token="t")
    _mount(provider, httpx.MockTransport(handler))

    await provider.merge_pr("owner/demo", 7)

    methode, chemin, corps = vus[0]
    assert (methode, chemin) == ("POST", "/api/v1/repos/owner/demo/pulls/7/merge")
    assert json.loads(corps) == {"Do": "merge"}
