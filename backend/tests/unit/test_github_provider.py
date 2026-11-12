"""Tests GitHubProvider via httpx MockTransport."""

from __future__ import annotations

import json
from typing import Any

import httpx
import pytest
from app.core.exceptions import GitProviderError
from app.services.git_providers import github
from app.services.git_providers.base import (
    CHECKS_AUCUN,
    CHECKS_EN_COURS,
    CHECKS_ROUGE,
    CHECKS_VERT,
    ChecksReport,
)
from app.services.git_providers.github import GitHubProvider

from tests.unit.serveur_abonne import Journal


def _make_transport(handler):  # type: ignore[no-untyped-def]
    return httpx.MockTransport(handler)


def _mount(provider: GitHubProvider, transport: httpx.MockTransport) -> None:
    """Force le provider à utiliser un client httpx mocké."""

    async def _client() -> httpx.AsyncClient:
        return httpx.AsyncClient(
            base_url="https://api.github.com",
            headers=provider._headers,
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


async def test_un_refus_de_l_api_laisse_une_trace_sans_l_url_complete(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """httpx n'écrit plus ses requêtes : sans cette ligne, un 403 ne laisse rien côté serveur."""
    journal = Journal()
    monkeypatch.setattr(github, "logger", journal)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(403, json={"message": "Forbidden"})

    provider = GitHubProvider(token="ghp_test")
    _mount(provider, _make_transport(handler))
    with pytest.raises(GitProviderError):
        await provider.list_repos()

    # Le chemin seul : ni l'hôte, ni les paramètres de pagination, ni le jeton.
    assert journal.appels == [
        (
            "git_provider.refuse",
            {"provider": "github", "methode": "GET", "chemin": "/user/repos", "status": 403},
        )
    ]


async def test_un_succes_ne_laisse_pas_de_trace(monkeypatch: pytest.MonkeyPatch) -> None:
    journal = Journal()
    monkeypatch.setattr(github, "logger", journal)
    provider = GitHubProvider(token="ghp_test")
    _mount(provider, _make_transport(lambda request: httpx.Response(200, json=[])))

    assert await provider.list_repos() == []
    assert journal.appels == []


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


def _pr(number: int = 7, *, state: str = "open", merged: bool = False) -> dict[str, Any]:
    return {
        "number": number,
        "html_url": f"https://github.com/owner/demo/pull/{number}",
        "head": {"ref": "eldir/s1", "sha": "abc123"},
        "base": {"ref": "main"},
        "title": "Ajoute x",
        "state": state,
        "merged": merged,
    }


async def test_get_pr_lit_l_etat_et_le_sha_de_la_tete() -> None:
    provider = GitHubProvider(token="ghp_test")
    _mount(
        provider,
        httpx.MockTransport(lambda r: httpx.Response(200, json=_pr(state="closed", merged=True))),
    )

    pr = await provider.get_pr("owner/demo", 7)

    assert (pr.number, pr.state, pr.head_sha) == (7, "merged", "abc123")


async def test_find_open_pr_cherche_par_branche_source() -> None:
    vus: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        vus.append(str(request.url.params))
        return httpx.Response(200, json=[_pr()])

    provider = GitHubProvider(token="ghp_test")
    _mount(provider, httpx.MockTransport(handler))

    pr = await provider.find_open_pr("owner/demo", "eldir/s1")
    assert pr is not None and pr.number == 7
    assert "head=owner%3Aeldir%2Fs1" in vus[0] and "state=open" in vus[0]
    assert await provider.find_open_pr("owner/demo", "autre") is None


async def test_les_checks_reunissent_check_runs_et_statuts() -> None:
    """GitHub Actions écrit des check runs, d'autres CI des statuts : il faut les deux."""

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/check-runs"):
            return httpx.Response(
                200,
                json={
                    "check_runs": [
                        {"name": "tests", "status": "completed", "conclusion": "success"},
                        {"name": "lint", "status": "completed", "conclusion": "skipped"},
                    ]
                },
            )
        return httpx.Response(
            200, json={"statuses": [{"context": "ci/externe", "state": "failure"}]}
        )

    provider = GitHubProvider(token="ghp_test")
    _mount(provider, httpx.MockTransport(handler))

    rapport = await provider.checks("owner/demo", "abc123")

    assert rapport == ChecksReport(CHECKS_ROUGE, ("ci/externe",))


async def test_un_check_qui_tourne_rend_la_ci_en_cours() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/check-runs"):
            return httpx.Response(
                200,
                json={
                    "check_runs": [{"name": "tests", "status": "in_progress", "conclusion": None}]
                },
            )
        return httpx.Response(200, json={"statuses": []})

    provider = GitHubProvider(token="ghp_test")
    _mount(provider, httpx.MockTransport(handler))

    assert (await provider.checks("owner/demo", "abc123")).etat == CHECKS_EN_COURS


async def test_sans_check_ni_statut_la_ci_est_absente() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/check-runs"):
            return httpx.Response(200, json={"check_runs": []})
        return httpx.Response(200, json={"statuses": []})

    provider = GitHubProvider(token="ghp_test")
    _mount(provider, httpx.MockTransport(handler))

    assert (await provider.checks("owner/demo", "abc123")).etat == CHECKS_AUCUN


async def test_merge_pr_fait_un_commit_de_merge() -> None:
    vus: list[tuple[str, str, bytes]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        vus.append((request.method, request.url.path, request.content))
        return httpx.Response(200, json={"merged": True})

    provider = GitHubProvider(token="ghp_test")
    _mount(provider, httpx.MockTransport(handler))

    await provider.merge_pr("owner/demo", 7, "abc123")

    methode, chemin, corps = vus[0]
    assert (methode, chemin) == ("PUT", "/repos/owner/demo/pulls/7/merge")
    assert json.loads(corps) == {"merge_method": "merge", "sha": "abc123"}


async def test_un_merge_refuse_remonte_le_message_de_github() -> None:
    provider = GitHubProvider(token="ghp_test")
    _mount(
        provider,
        httpx.MockTransport(
            lambda r: httpx.Response(405, json={"message": "Pull Request is not mergeable"})
        ),
    )

    with pytest.raises(GitProviderError, match="not mergeable"):
        await provider.merge_pr("owner/demo", 7, "abc123")


def _fournir_github(runs: list[dict[str, Any]], combine: dict[str, Any]) -> GitHubProvider:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/check-runs"):
            return httpx.Response(200, json={"check_runs": runs})
        return httpx.Response(200, json=combine)

    provider = GitHubProvider(token="ghp_test")
    _mount(provider, httpx.MockTransport(handler))
    return provider


async def test_github_l_etat_global_en_echec_sert_de_plancher() -> None:
    provider = _fournir_github(
        [{"name": "tests", "status": "completed", "conclusion": "success"}],
        {"state": "failure", "statuses": [{"context": "ci/x", "state": "success"}]},
    )

    rapport = await provider.checks("owner/demo", "abc123")

    assert rapport == ChecksReport(CHECKS_ROUGE, ("statut combiné",))


async def test_github_l_etat_global_en_attente_sert_de_plancher_mais_pas_sans_statut() -> None:
    en_attente = _fournir_github(
        [{"name": "tests", "status": "completed", "conclusion": "success"}],
        {"state": "pending", "statuses": [{"context": "ci/x", "state": "success"}]},
    )
    runs_verts = _fournir_github(
        [{"name": "tests", "status": "completed", "conclusion": "success"}],
        {"state": "pending", "statuses": []},
    )
    vide = _fournir_github([], {"state": "pending", "statuses": []})

    assert (await en_attente.checks("owner/demo", "abc123")).etat == CHECKS_EN_COURS
    assert (await runs_verts.checks("owner/demo", "abc123")).etat == CHECKS_VERT
    assert (await vide.checks("owner/demo", "abc123")).etat == CHECKS_AUCUN


def test_l_origine_git_de_github_est_son_site() -> None:
    assert GitHubProvider(token="ghp_test").origine_git == "https://github.com"
