"""GitHubProvider — implémentation httpx contre l'API REST v3 GitHub.

Authentification V1 : Personal Access Token (PAT).
- L'utilisateur crée son PAT sur https://github.com/settings/tokens?type=beta
- Scopes minimum : `repo`, `read:user`.
- Le PAT est chiffré (Fernet) avant persistance en DB.

V2 (à venir) : OAuth device flow avec client_id Eldir.
"""

from __future__ import annotations

from typing import Any

import httpx

from app.core.exceptions import GitProviderError
from app.services.git_providers.base import (
    GitProviderInterface,
    PullRequestRef,
    RepoRef,
)

GITHUB_API = "https://api.github.com"
DEFAULT_TIMEOUT = 15.0
DEFAULT_PAGE_SIZE = 100


def _repo_from_payload(p: dict[str, Any]) -> RepoRef:
    return RepoRef(
        full_name=p["full_name"],
        default_branch=p.get("default_branch") or "main",
        clone_url=p["clone_url"],
        description=p.get("description"),
        is_private=bool(p.get("private", False)),
    )


class GitHubProvider(GitProviderInterface):
    name = "github"

    def __init__(self, token: str) -> None:
        if not token:
            raise GitProviderError("Token GitHub manquant.")
        self._token = token
        self._headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "eldir/0.1",
        }

    async def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            base_url=GITHUB_API,
            headers=self._headers,
            timeout=DEFAULT_TIMEOUT,
        )

    async def _request(
        self, method: str, path: str, *, params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
    ) -> httpx.Response:
        async with await self._client() as client:
            response = await client.request(method, path, params=params, json=json)
        if response.is_success:
            return response
        try:
            body = response.json()
        except ValueError:
            body = {"message": response.text}
        raise GitProviderError(
            f"GitHub API {response.status_code}: {body.get('message', '?')}",
            details={"status": response.status_code, "body": body},
        )

    async def list_repos(self) -> list[RepoRef]:
        """Liste tous les repos accessibles (paginé)."""
        repos: list[RepoRef] = []
        page = 1
        while True:
            response = await self._request(
                "GET",
                "/user/repos",
                params={
                    "per_page": DEFAULT_PAGE_SIZE,
                    "page": page,
                    "sort": "updated",
                    "affiliation": "owner,collaborator,organization_member",
                },
            )
            payload = response.json()
            if not isinstance(payload, list):
                raise GitProviderError("Réponse inattendue de l'API GitHub.")
            repos.extend(_repo_from_payload(p) for p in payload)
            if len(payload) < DEFAULT_PAGE_SIZE:
                break
            page += 1
            if page > 20:  # garde-fou
                break
        return repos

    async def get_repo(self, full_name: str) -> RepoRef:
        response = await self._request("GET", f"/repos/{full_name}")
        return _repo_from_payload(response.json())

    async def create_repo(
        self,
        name: str,
        *,
        private: bool = True,
        description: str | None = None,
    ) -> RepoRef:
        body: dict[str, Any] = {"name": name, "private": private}
        if description:
            body["description"] = description
        response = await self._request("POST", "/user/repos", json=body)
        return _repo_from_payload(response.json())

    async def get_branches(self, full_name: str) -> list[str]:
        branches: list[str] = []
        page = 1
        while True:
            response = await self._request(
                "GET",
                f"/repos/{full_name}/branches",
                params={"per_page": DEFAULT_PAGE_SIZE, "page": page},
            )
            payload = response.json()
            if not isinstance(payload, list):
                raise GitProviderError("Réponse inattendue de l'API GitHub.")
            branches.extend(b["name"] for b in payload if isinstance(b.get("name"), str))
            if len(payload) < DEFAULT_PAGE_SIZE:
                break
            page += 1
            if page > 20:
                break
        return branches

    async def get_default_branch(self, full_name: str) -> str:
        ref = await self.get_repo(full_name)
        return ref.default_branch

    async def create_pr(
        self,
        full_name: str,
        *,
        head: str,
        base: str,
        title: str,
        body: str | None = None,
    ) -> PullRequestRef:
        payload: dict[str, Any] = {"title": title, "head": head, "base": base}
        if body:
            payload["body"] = body
        response = await self._request(
            "POST", f"/repos/{full_name}/pulls", json=payload
        )
        data = response.json()
        return PullRequestRef(
            number=int(data["number"]),
            url=str(data["html_url"]),
            head=str(data["head"]["ref"]),
            base=str(data["base"]["ref"]),
            title=str(data["title"]),
        )

    async def validate_token(self) -> dict[str, Any]:
        """Vérifie que le PAT est valide en appelant /user."""
        response = await self._request("GET", "/user")
        return dict(response.json())
