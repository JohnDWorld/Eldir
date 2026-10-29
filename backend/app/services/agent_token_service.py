"""Émission, révocation et authentification des jetons d'agent."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AuthenticationError, NotFoundError, ValidationError
from app.core.security import create_access_token, decode_access_token
from app.db.models import AgentToken

# Dix ans : un agent ne se reconnecte pas derrière un formulaire. La borne
# n'est pas l'expiration, c'est la révocation.
_DUREE_MINUTES = 10 * 365 * 24 * 60
_KIND = "agent"
_LABEL_MAX = 80  # taille de la colonne `agent_tokens.label`


async def emettre(db: AsyncSession, *, user_id: str, label: str) -> tuple[AgentToken, str]:
    """Crée un jeton et rend (la ligne, le jeton en clair).

    Le clair n'est rendu qu'ici : on ne le stocke pas, donc on ne peut pas le
    réafficher. L'interface doit le dire avant de le montrer.
    """
    label = label.strip()
    if not label or len(label) > _LABEL_MAX:
        raise ValidationError(
            f"Un jeton d'agent doit porter un libellé de 1 à {_LABEL_MAX} caractères."
        )
    jti = str(uuid.uuid4())
    ligne = AgentToken(user_id=user_id, label=label, jti=jti)
    db.add(ligne)
    await db.flush()
    clair = create_access_token(
        user_id,
        expires_minutes=_DUREE_MINUTES,
        extra_claims={"kind": _KIND, "jti": jti},
    )
    return ligne, clair


async def lister(db: AsyncSession, *, user_id: str) -> list[AgentToken]:
    result = await db.execute(
        select(AgentToken)
        .where(AgentToken.user_id == user_id)
        .order_by(AgentToken.created_at.desc())
    )
    return list(result.scalars().all())


async def revoquer(db: AsyncSession, *, user_id: str, token_id: str) -> None:
    ligne = await db.get(AgentToken, token_id)
    if ligne is None or ligne.user_id != user_id:
        raise NotFoundError(f"Jeton {token_id} introuvable.")
    if ligne.revoked_at is None:
        ligne.revoked_at = datetime.now(UTC)


async def authentifier(db: AsyncSession, *, jeton: str) -> tuple[str, str]:
    """Rend (user_id, libellé) ou lève. Met à jour la date de dernier usage."""
    charge = decode_access_token(jeton)
    if charge.get("kind") != _KIND:
        raise AuthenticationError("Ce jeton n'est pas un jeton d'agent.")
    jti = charge.get("jti")
    sujet = charge.get("sub")
    if not isinstance(jti, str) or not isinstance(sujet, str):
        raise AuthenticationError("Jeton d'agent incomplet.")
    result = await db.execute(select(AgentToken).where(AgentToken.jti == jti))
    ligne = result.scalar_one_or_none()
    if ligne is None or ligne.revoked_at is not None or ligne.user_id != sujet:
        raise AuthenticationError("Jeton d'agent invalide ou révoqué.")
    ligne.last_used_at = datetime.now(UTC)
    return ligne.user_id, ligne.label
