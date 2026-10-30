"""L'échange de jeton OAuth GitHub laisse une trace quand il échoue.

C'est le chemin qui casse le plus souvent chez un nouvel installeur (client_id,
secret ou callback mal recopiés). Les journaux de requêtes d'`httpx` sont muselés
(leur INFO recopiait l'URL complète, jeton compris) et le gestionnaire d'erreurs
global ne journalise pas les erreurs métier : sans ces lignes, un échec ne laisse
plus rien du tout côté serveur.
"""

from __future__ import annotations

from collections.abc import Callable

import httpx
import pytest
from app.core.config import Settings
from app.core.exceptions import GitProviderError
from app.services import github_oauth_service as module

from tests.unit.serveur_abonne import Journal

SECRET = "secret-de-l-app-42"


def _reglages() -> Settings:
    return Settings(
        github_oauth_client_id="Iv1.exemple",
        github_oauth_client_secret=SECRET,  # type: ignore[arg-type]
    )


@pytest.fixture
def journal(monkeypatch: pytest.MonkeyPatch) -> Journal:
    espion = Journal()
    monkeypatch.setattr(module, "logger", espion)
    return espion


@pytest.fixture
def repondre(monkeypatch: pytest.MonkeyPatch) -> Callable[[httpx.Response], None]:
    """Fait répondre ce qu'on veut à l'échange, sans toucher au code appelé."""
    reel = httpx.AsyncClient

    def poser(reponse: httpx.Response) -> None:
        def fabrique(**kwargs: object) -> httpx.AsyncClient:
            return reel(transport=httpx.MockTransport(lambda _: reponse), **kwargs)  # type: ignore[arg-type]

        monkeypatch.setattr(module.httpx, "AsyncClient", fabrique)

    return poser


async def test_un_echange_refuse_en_http_laisse_une_trace(
    journal: Journal, repondre: Callable[[httpx.Response], None]
) -> None:
    repondre(httpx.Response(401, text="Bad credentials"))

    with pytest.raises(GitProviderError):
        await module.exchange_code_for_token(_reglages(), code="le-code")

    assert journal.appels == [
        (
            "github_oauth.refuse",
            {"methode": "POST", "chemin": "/login/oauth/access_token", "status": 401},
        )
    ]


async def test_un_refus_annonce_dans_le_corps_nomme_le_code_d_erreur(
    journal: Journal, repondre: Callable[[httpx.Response], None]
) -> None:
    """GitHub répond 200 avec un `error` dans le corps : c'est ce code qui dit
    quoi corriger, et c'est la seule part du corps qu'on journalise."""
    repondre(
        httpx.Response(
            200,
            json={
                "error": "bad_verification_code",
                "error_description": "The code passed is incorrect or expired.",
            },
        )
    )

    with pytest.raises(GitProviderError):
        await module.exchange_code_for_token(_reglages(), code="le-code")

    assert journal.appels == [
        (
            "github_oauth.refuse",
            {
                "methode": "POST",
                "chemin": "/login/oauth/access_token",
                "status": 200,
                "erreur": "bad_verification_code",
            },
        )
    ]


async def test_une_reponse_sans_jeton_laisse_une_trace(
    journal: Journal, repondre: Callable[[httpx.Response], None]
) -> None:
    repondre(httpx.Response(200, json={"token_type": "bearer"}))

    with pytest.raises(GitProviderError, match="access_token"):
        await module.exchange_code_for_token(_reglages(), code="le-code")

    assert [e for e, _ in journal.appels] == ["github_oauth.refuse"]


async def test_un_echange_reussi_ne_journalise_rien_et_jamais_le_secret(
    journal: Journal, repondre: Callable[[httpx.Response], None]
) -> None:
    """Un appel sortant réussi ne laisse aucune trace : c'est le contrat du
    muselage, et le secret de l'app ne doit apparaître nulle part."""
    repondre(httpx.Response(200, json={"access_token": "gho_secret"}))

    charge = await module.exchange_code_for_token(_reglages(), code="le-code")

    assert charge["access_token"] == "gho_secret"
    assert journal.appels == []
    assert SECRET not in repr(journal.appels)
