"""Tests ForgejoProvider via httpx MockTransport."""

from __future__ import annotations

import httpx
import pytest
from app.core.exceptions import GitProviderError
from app.services.git_providers import forgejo
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
