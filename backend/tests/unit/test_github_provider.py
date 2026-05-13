"""Tests GitHubProvider via httpx MockTransport."""

from __future__ import annotations

import json

import httpx
import pytest

from app.core.exceptions import GitProviderError
from app.services.git_providers.github import GitHubProvider


def _make_transport(handler):  # type: ignore[no-untyped-def]
    return httpx.MockTransport(handler)


def _mount(provider: GitHubProvider, transport: httpx.MockTransport) -> None:
    """Force le provider à utiliser un client httpx mocké."""

    async def _client() -> httpx.AsyncClient:
        return httpx.AsyncClient(
            base_url="https://api.github.com",
            headers=provider._headers,  # noqa: SLF001
            transport=transport,
        )

    provider._client = _client  # type: ignore[assignment]


async def test_list_repos_single_page() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/user/repos"
        body = [
            {
                "full_name": "owner/repo-a",
                "default_branch": "main",
                "clone_url": "https://github.com/owner/repo-a.git",
                "description": "first",
                "private": False,
            },
            {
                "full_name": "owner/repo-b",
                "default_branch": "develop",
                "clone_url": "https://github.com/owner/repo-b.git",
                "description": None,
                "private": True,
            },
        ]
        return httpx.Response(200, json=body)

    provider = GitHubProvider(token="ghp_test")
    _mount(provider, _make_transport(handler))
    repos = await provider.list_repos()
    assert len(repos) == 2
    assert repos[0].full_name == "owner/repo-a"
    assert repos[1].is_private is True


async def test_get_repo_404_raises() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"message": "Not Found"})

    provider = GitHubProvider(token="ghp_test")
    _mount(provider, _make_transport(handler))
    with pytest.raises(GitProviderError) as exc:
        await provider.get_repo("missing/repo")
    assert exc.value.details["status"] == 404


async def test_create_repo_sends_payload() -> None:
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content)
        return httpx.Response(
            201,
            json={
                "full_name": "owner/new-repo",
                "default_branch": "main",
                "clone_url": "https://github.com/owner/new-repo.git",
                "description": "ok",
                "private": True,
            },
        )

    provider = GitHubProvider(token="ghp_test")
    _mount(provider, _make_transport(handler))
    repo = await provider.create_repo("new-repo", private=True, description="ok")
    assert repo.full_name == "owner/new-repo"
    assert captured["body"] == {
        "name": "new-repo",
        "private": True,
        "description": "ok",
    }


async def test_validate_token_returns_user() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"login": "john", "id": 1})

    provider = GitHubProvider(token="ghp_test")
    _mount(provider, _make_transport(handler))
    data = await provider.validate_token()
    assert data["login"] == "john"
