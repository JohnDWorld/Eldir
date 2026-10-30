"""Fixtures partagées par les tests du ping de fin de tour."""

from __future__ import annotations

from collections.abc import Callable, Iterator

import pytest
from app.core.config import get_settings
from app.services import turn_webhook

from tests.unit.serveur_abonne import Journal, ServeurAbonne


@pytest.fixture
def journal(monkeypatch: pytest.MonkeyPatch) -> Journal:
    espion = Journal()
    monkeypatch.setattr(turn_webhook, "logger", espion)
    return espion


@pytest.fixture
def reglages(monkeypatch: pytest.MonkeyPatch) -> Iterator[Callable[..., None]]:
    """Pose des variables d'environnement, puis vide le cache des réglages."""

    def poser(**env: str) -> None:
        for nom, valeur in env.items():
            monkeypatch.setenv(nom.upper(), valeur)
        get_settings.cache_clear()

    yield poser
    get_settings.cache_clear()


@pytest.fixture
def abonne() -> Iterator[ServeurAbonne]:
    with ServeurAbonne() as serveur:
        yield serveur


@pytest.fixture
def sdk_factice(monkeypatch: pytest.MonkeyPatch) -> None:
    """Un `ResultMessage` sans les champs du vrai : `_consume_response` l'importe à chaque tour.

    Le reste du SDK reste réel, le superviseur en a besoin pour monter ses outils.
    """
    import claude_agent_sdk

    monkeypatch.setattr(claude_agent_sdk, "ResultMessage", type("ResultMessage", (), {}))
