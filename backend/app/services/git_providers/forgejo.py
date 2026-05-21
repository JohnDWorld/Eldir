"""ForgejoProvider - implémentation httpx contre l'API REST Forgejo/Gitea.

Authentification : Personal Access Token (PAT) Forgejo.
- L'utilisateur crée son PAT sur {base_url}/user/settings/applications
- Scopes minimum : `read:user`, `read:repository`, `write:repository`,
  `read:issue`, `write:issue`.
- Le PAT est chiffré (Fernet) avant persistance en DB.

L'API Forgejo (/api/v1/...) est compatible Gitea : si tu pointes Eldir
vers une instance Gitea, ça marche aussi.
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

DEFAULT_TIMEOUT = 15.0
DEFAULT_PAGE_SIZE = 50
MAX_PAGES = 20


def _repo_from_payload(p: dict[str, Any]) -> RepoRef:
    return RepoRef(
        full_name=p["full_name"],
        default_branch=p.get("default_branch") or "main",
        clone_url=p["clone_url"],
        description=p.get("description"),
        is_private=bool(p.get("private", False)),
    )


class ForgejoProvider(GitProviderInterface):
    name = "forgejo"

    def __init__(self, base_url: str, token: str) -> None:
        if not base_url:
            raise GitProviderError("base_url Forgejo manquante.")
        if not token:
            raise GitProviderError("Token Forgejo manquant.")
        self._base_url = base_url.rstrip("/")
        self._token = token
        self._headers = {
            "Authorization": f"token {token}",
            "Accept": "application/json",
            "User-Agent": "eldir/0.1",
        }

    async def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            base_url=f"{self._base_url}/api/v1",
            headers=self._headers,
            timeout=DEFAULT_TIMEOUT,
        )

    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
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
            f"Forgejo API {response.status_code}: "
            f"{body.get('message', body.get('errors', '?'))}",
            details={"status": response.status_code, "body": body},
        )

    async def list_repos(self) -> list[RepoRef]:
        """Liste tous les repos accessibles à l'utilisateur courant (paginé)."""
        repos: list[RepoRef] = []
        page = 1
        while True:
            response = await self._request(
                "GET",
                "/repos/search",
                params={
                    "limit": DEFAULT_PAGE_SIZE,
                    "page": page,
                    "sort": "updated",
                    "order": "desc",
                },
            )
            payload = response.json()
            data = payload.get("data") if isinstance(payload, dict) else None
            if not isinstance(data, list):
                raise GitProviderError("Réponse inattendue de l'API Forgejo.")
            repos.extend(_repo_from_payload(p) for p in data)
            if len(data) < DEFAULT_PAGE_SIZE:
                break
            page += 1
            if page > MAX_PAGES:  # garde-fou
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
        body: dict[str, Any] = {
            "name": name,
            "private": private,
            "auto_init": True,
            "default_branch": "main",
        }
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
                params={"limit": DEFAULT_PAGE_SIZE, "page": page},
            )
            payload = response.json()
            if not isinstance(payload, list):
                raise GitProviderError("Réponse inattendue de l'API Forgejo.")
            branches.extend(b["name"] for b in payload if isinstance(b.get("name"), str))
            if len(payload) < DEFAULT_PAGE_SIZE:
                break
            page += 1
            if page > MAX_PAGES:
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
