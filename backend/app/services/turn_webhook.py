"""Prévient un abonné externe qu'une session dispatchée a fini son tour."""

from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import json
import uuid
from datetime import UTC, datetime
from typing import Any

import httpx

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger("eldir.turn_webhook")


def signer(corps: bytes, secret: str) -> str:
    """Signature du corps, pour que l'abonné sache que le ping vient d'Eldir.

    Le préfixe nomme l'algorithme : sans lui, un abonné devinerait, et le jour
    où l'algorithme change, il vérifierait encore l'ancien en silence.
    """
    empreinte = hmac.new(secret.encode(), corps, hashlib.sha256).hexdigest()
    return f"sha256={empreinte}"


def signer_standard(identifiant: str, instant: int, corps: bytes, secret: str) -> str:
    """La même preuve au format Standard Webhooks (standardwebhooks.com).

    C'est le format que des abonnés tout faits savent déjà vérifier (Hermes, Svix) :
    sans lui, chacun devrait apprendre `X-Eldir-Signature`. L'identifiant et l'instant
    sont signés avec le corps, ce qui laisse l'abonné refuser un rejeu ou un doublon
    sans lire la charge. Le secret sert tel quel de clé : une bibliothèque qui attend
    un `whsec_` reçoit `whsec_` suivi du secret encodé en base64.
    """
    contenu = f"{identifiant}.{instant}.".encode() + corps
    empreinte = hmac.new(secret.encode(), contenu, hashlib.sha256).digest()
    return "v1," + base64.b64encode(empreinte).decode()


async def prevenir(charge: dict[str, Any]) -> None:
    """Poste la charge si un abonné est configuré. N'échoue jamais.

    La session enfant a terminé son travail : un abonné injoignable, lent ou en
    erreur ne doit pas transformer ce succès en échec. L'échec est journalisé,
    et c'est tout.

    Le journal ne dit jamais l'URL (elle peut porter un jeton) ni le message de
    l'exception (httpx y recopie parfois l'URL) : le nom de l'exception et le
    statut suffisent à diagnostiquer. Une redirection n'est pas suivie, donc le
    corps signé ne part jamais ailleurs que vers l'URL configurée, et elle
    compte comme un refus : un abonné déménagé doit s'entendre dire que son
    adresse ne reçoit plus rien.
    """
    try:
        settings = get_settings()
        url = settings.turn_webhook_url.strip()
        if not url:
            return
        # L'horodatage est dans le corps signé : sans lui, une charge vue passer se rejoue
        # indéfiniment, et l'abonné ne peut pas refuser ce qui est trop vieux.
        maintenant = datetime.now(UTC).replace(microsecond=0)
        horodatage = maintenant.isoformat()
        # ASCII pur (les accents partent échappés) : aucun abonné n'a à deviner l'encodage.
        # Chaque ping a son identifiant : deux pings d'une même session dans la même seconde
        # seraient sinon identiques octet pour octet, et l'abonné ne pourrait ni dédoublonner
        # ni distinguer un doublon de livraison d'un rejeu dans la fenêtre de fraîcheur.
        envoi = {**charge, "ping_id": str(uuid.uuid4()), "horodatage": horodatage}
        corps = json.dumps(envoi).encode()
        entetes = {"Content-Type": "application/json"}
        # Un secret vide signerait avec une clé que tout le monde connaît.
        secret = settings.turn_webhook_secret
        cle = secret.get_secret_value() if secret else ""
        if cle:
            entetes["X-Eldir-Signature"] = signer(corps, cle)
            instant = int(maintenant.timestamp())
            entetes["webhook-id"] = envoi["ping_id"]
            entetes["webhook-timestamp"] = str(instant)
            entetes["webhook-signature"] = signer_standard(envoi["ping_id"], instant, corps, cle)
        delai = settings.turn_webhook_timeout_seconds
        # Un seul délai, sur le ping entier. Celui de httpx court par phase : un abonné qui
        # répond au compte-gouttes le remet à zéro sans cesse, et il doublonnerait celui-ci.
        # `timeout=None` le désactive (sans l'argument, httpx impose 5 s par phase, et un
        # abonné lent mais dans le délai configuré serait coupé avant).
        async with (
            asyncio.timeout(delai),
            httpx.AsyncClient(timeout=None) as client,  # noqa: S113 (asyncio.timeout borne le ping)
        ):
            reponse = await client.post(url, content=corps, headers=entetes)
        if not reponse.is_success:
            logger.warning("turn_webhook.refuse", status=reponse.status_code)
    except Exception as exc:
        logger.warning("turn_webhook.injoignable", erreur=type(exc).__name__)
