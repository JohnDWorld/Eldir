"""OllamaService : un refus de l'API laisse une trace côté serveur.

httpx n'écrit plus ses requêtes (son INFO recopiait l'URL, jeton compris), et un refus
d'Ollama lève une exception que rien ne journalise. Le serveur HTTP est réel.
"""

from __future__ import annotations

from collections.abc import Callable

import pytest
from app.core.exceptions import EldirError
from app.services import ollama_service as module
from app.services.ollama_service import OllamaService

from tests.unit.serveur_abonne import Journal, ServeurAbonne

JETON = "jeton-d-url-42"


@pytest.fixture
def journal_ollama(monkeypatch: pytest.MonkeyPatch) -> Journal:
    espion = Journal()
    monkeypatch.setattr(module, "logger", espion)
    return espion


async def test_un_refus_de_list_models_laisse_une_trace_sans_l_url(
    reglages: Callable[..., None], journal_ollama: Journal, abonne: ServeurAbonne
) -> None:
    reglages(ollama_base_url=abonne.url(f"/erreur/{JETON}"))

    with pytest.raises(EldirError, match="500"):
        await OllamaService().list_models()

    assert [r.chemin for r in abonne.requetes] == [f"/erreur/{JETON}/api/tags"], "il a été joint"
    assert journal_ollama.appels == [
        ("ollama.refuse", {"methode": "GET", "chemin": "/api/tags", "status": 500})
    ]
    assert JETON not in repr(journal_ollama.appels)


async def test_un_refus_de_generate_laisse_une_trace_sans_l_url(
    reglages: Callable[..., None], journal_ollama: Journal, abonne: ServeurAbonne
) -> None:
    reglages(ollama_base_url=abonne.url(f"/erreur/{JETON}"))

    with pytest.raises(EldirError, match="500"):
        await OllamaService().generate("Bonjour")

    assert [(r.methode, r.chemin) for r in abonne.requetes] == [
        ("POST", f"/erreur/{JETON}/api/generate")
    ]
    assert journal_ollama.appels == [
        ("ollama.refuse", {"methode": "POST", "chemin": "/api/generate", "status": 500})
    ]
    assert JETON not in repr(journal_ollama.appels)


async def test_un_succes_ne_laisse_pas_de_trace(
    reglages: Callable[..., None], journal_ollama: Journal, abonne: ServeurAbonne
) -> None:
    reglages(ollama_base_url=abonne.url("/json"))
    service = OllamaService()

    assert await service.list_models() == []
    assert await service.generate("Bonjour") == "ok"

    assert len(abonne.requetes) == 2, "les deux appels sont bien partis"
    assert journal_ollama.appels == []
