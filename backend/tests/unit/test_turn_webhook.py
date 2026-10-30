"""Ping de fin de tour vers un abonné externe.

Le ping interne réveille le superviseur en mémoire : un agent dans un autre
processus ne le voit pas, et n'apprendrait la fin du travail qu'à son prochain
réveil. Il avancerait d'un pas par tic de cron au lieu d'enchaîner.

Les tests parlent à un vrai serveur HTTP local (`serveur_abonne`). Un test qui
vérifie seulement « ça n'a pas levé » passerait aussi quand rien n'est parti :
chaque cas d'échec prouve donc deux choses, que la requête est bien arrivée (ou
que la connexion a bien été refusée) et que l'échec n'est pas remonté.
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import logging
import time
from collections.abc import Callable, Iterator
from typing import Any

import pytest
import structlog
from app.core.config import Settings, get_settings
from app.core.logging import configure_logging
from app.services import turn_webhook
from app.services.turn_webhook import prevenir, signer

from tests.unit.serveur_abonne import ServeurAbonne, port_ferme

JETON = "jeton-d-url-42"
CHARGE = {"session_id": "s1", "projet": "Munin", "etat": "fin_de_tour", "cr": "Fait : é à ü"}


class _Journal:
    """Remplace le logger du module : ce que le ping a dit, et sous quel nom."""

    def __init__(self) -> None:
        self.appels: list[tuple[str, dict[str, Any]]] = []

    def warning(self, evenement: str, **champs: Any) -> None:
        self.appels.append((evenement, champs))

    def evenements(self) -> list[str]:
        return [e for e, _ in self.appels]


@pytest.fixture
def journal(monkeypatch: pytest.MonkeyPatch) -> _Journal:
    espion = _Journal()
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


def test_la_signature_depend_du_corps_et_du_secret() -> None:
    a = signer(b'{"session_id":"s1"}', "secret")
    assert a == signer(b'{"session_id":"s1"}', "secret"), "déterministe"
    assert a != signer(b'{"session_id":"s2"}', "secret"), "dépend du corps"
    assert a != signer(b'{"session_id":"s1"}', "autre"), "dépend du secret"
    assert a.startswith("sha256="), "l'abonné doit savoir quel algorithme vérifier"


def test_la_signature_est_un_hmac_sha256_en_hexadecimal() -> None:
    """Ce que n'importe quel abonné recalcule avec sa bibliothèque standard."""
    attendu = hmac.new(b"secret", b"corps", hashlib.sha256).hexdigest()
    assert signer(b"corps", "secret") == f"sha256={attendu}"


def test_par_defaut_aucun_ping_n_est_configure(monkeypatch: pytest.MonkeyPatch) -> None:
    """Un déploiement existant, sans ces variables, ne doit rien envoyer nulle part."""
    for nom in ("TURN_WEBHOOK_URL", "TURN_WEBHOOK_SECRET", "TURN_WEBHOOK_TIMEOUT_SECONDS"):
        monkeypatch.delenv(nom, raising=False)
    reglages = Settings(_env_file=None)  # type: ignore[call-arg]
    assert reglages.turn_webhook_url == ""
    assert reglages.turn_webhook_secret is None
    assert reglages.turn_webhook_timeout_seconds == 10.0


async def test_sans_url_configuree_on_ne_fait_rien(
    reglages: Callable[..., None], journal: _Journal
) -> None:
    reglages(turn_webhook_url="")
    await prevenir(CHARGE)
    # Sans la garde, httpx refuserait l'URL vide et le ping dirait « injoignable » :
    # ne pas lever ne prouve pas qu'on s'est abstenu, le silence du journal si.
    assert journal.appels == []


async def test_le_ping_part_vraiment_avec_le_bon_corps_et_la_bonne_signature(
    reglages: Callable[..., None], journal: _Journal, abonne: ServeurAbonne
) -> None:
    reglages(turn_webhook_url=abonne.url("/ok"), turn_webhook_secret="secret-de-test")

    await prevenir(CHARGE)

    assert len(abonne.requetes) == 1, "le POST doit avoir traversé la socket"
    requete = abonne.requetes[0]
    assert (requete.methode, requete.chemin) == ("POST", "/ok")
    assert requete.entetes["content-type"] == "application/json"
    assert json.loads(requete.corps) == CHARGE, "accents compris, rien d'échappé en perdant du sens"
    attendu = hmac.new(b"secret-de-test", requete.corps, hashlib.sha256).hexdigest()
    assert requete.entetes["x-eldir-signature"] == f"sha256={attendu}", (
        "recalculée par l'abonné sur les octets reçus"
    )
    assert journal.appels == [], "un succès ne journalise rien"


@pytest.mark.parametrize("secret", [None, ""])
async def test_sans_secret_le_ping_part_non_signe(
    reglages: Callable[..., None],
    journal: _Journal,
    abonne: ServeurAbonne,
    secret: str | None,
) -> None:
    """Un secret vide signerait avec une clé que tout le monde connaît : pas de signature."""
    if secret is None:
        reglages(turn_webhook_url=abonne.url("/ok"))
    else:
        reglages(turn_webhook_url=abonne.url("/ok"), turn_webhook_secret=secret)

    await prevenir(CHARGE)

    assert len(abonne.requetes) == 1
    assert "x-eldir-signature" not in abonne.requetes[0].entetes
    assert journal.appels == []


async def test_un_abonne_qui_refuse_ne_fait_pas_echouer_le_tour(
    reglages: Callable[..., None], journal: _Journal, abonne: ServeurAbonne
) -> None:
    """La session enfant a fini son travail : un abonné en erreur n'y change rien."""
    reglages(turn_webhook_url=abonne.url("/erreur") + f"?jeton={JETON}")

    await prevenir(CHARGE)  # ne lève pas

    assert len(abonne.requetes) == 1, "il a bien été joint, c'est lui qui a répondu 500"
    assert journal.appels == [("turn_webhook.refuse", {"status": 500})]
    assert JETON not in repr(journal.appels), "l'URL peut porter un jeton"


async def test_une_redirection_n_est_pas_suivie_et_compte_comme_un_refus(
    reglages: Callable[..., None], journal: _Journal, abonne: ServeurAbonne
) -> None:
    """Suivre la redirection enverrait le corps signé là où John ne l'a pas configuré,
    et l'ignorer en silence laisserait un abonné déménagé sans ping, sans le savoir."""
    reglages(turn_webhook_url=abonne.url("/ancien"))

    await prevenir(CHARGE)

    assert [r.chemin for r in abonne.requetes] == ["/ancien"], "/nouveau ne doit pas être joint"
    assert journal.appels == [("turn_webhook.refuse", {"status": 302})]


async def test_un_abonne_injoignable_ne_fait_pas_echouer_le_tour(
    reglages: Callable[..., None], journal: _Journal
) -> None:
    """Connexion refusée pour de bon, sans remplacer httpx : si le ping n'était pas
    parti, il n'y aurait pas d'avertissement du tout."""
    reglages(turn_webhook_url=f"http://127.0.0.1:{port_ferme()}/ping?jeton={JETON}")

    await prevenir(CHARGE)  # ne lève pas

    assert journal.appels == [("turn_webhook.injoignable", {"erreur": "ConnectError"})]
    assert JETON not in repr(journal.appels), "ni l'URL ni le message de l'exception"


async def test_un_abonne_qui_ne_repond_pas_est_lache_au_bout_du_delai(
    reglages: Callable[..., None], journal: _Journal, abonne: ServeurAbonne
) -> None:
    reglages(turn_webhook_url=abonne.url("/silence"), turn_webhook_timeout_seconds="0.3")

    debut = time.monotonic()
    await asyncio.wait_for(prevenir(CHARGE), timeout=5)
    ecoule = time.monotonic() - debut

    assert len(abonne.requetes) == 1, "la requête est partie, l'abonné s'est tu"
    assert ecoule < 3
    assert journal.evenements() == ["turn_webhook.injoignable"]


async def test_un_abonne_qui_repond_au_compte_gouttes_ne_garde_pas_le_ping_indefiniment(
    reglages: Callable[..., None], journal: _Journal, abonne: ServeurAbonne
) -> None:
    """Le délai de httpx court par phase : un octet toutes les 50 ms le remet à zéro
    sans cesse. Seul un délai sur le ping entier le borne."""
    reglages(turn_webhook_url=abonne.url("/goutte"), turn_webhook_timeout_seconds="0.3")

    debut = time.monotonic()
    await asyncio.wait_for(prevenir(CHARGE), timeout=5)
    ecoule = time.monotonic() - debut

    assert len(abonne.requetes) == 1
    assert ecoule < 3
    assert journal.appels == [("turn_webhook.injoignable", {"erreur": "TimeoutError"})]


async def test_une_charge_qui_ne_se_serialise_pas_ne_fait_pas_echouer_le_tour(
    reglages: Callable[..., None], journal: _Journal, abonne: ServeurAbonne
) -> None:
    reglages(turn_webhook_url=abonne.url("/ok"))

    await prevenir({"session_id": "s1", "cr": object()})  # ne lève pas

    assert abonne.requetes == [], "rien à envoyer"
    assert journal.appels == [("turn_webhook.injoignable", {"erreur": "TypeError"})]


async def test_httpx_ne_journalise_pas_l_url_d_un_abonne(
    reglages: Callable[..., None],
    abonne: ServeurAbonne,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """httpx écrit chaque requête en INFO, URL complète comprise, jeton compris.

    Le témoin d'abord : sans la configuration d'Eldir, la fuite existe. Sinon le
    second constat ne prouverait rien (httpx pourrait ne pas journaliser du tout).
    """
    reglages(turn_webhook_url=abonne.url("/ok") + f"?jeton={JETON}")
    httpx_logger = logging.getLogger("httpx")
    niveau_initial = httpx_logger.level
    try:
        httpx_logger.setLevel(logging.NOTSET)
        with caplog.at_level(logging.INFO):
            await prevenir(CHARGE)
        assert JETON in caplog.text, "témoin : sans réglage, httpx recopie l'URL"

        caplog.clear()
        configure_logging()
        with caplog.at_level(logging.INFO):
            await prevenir(CHARGE)
        assert len(abonne.requetes) == 2, "le ping est bien reparti"
        assert JETON not in caplog.text
    finally:
        httpx_logger.setLevel(niveau_initial)
        structlog.reset_defaults()
