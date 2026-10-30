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
