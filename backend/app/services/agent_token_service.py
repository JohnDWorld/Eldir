"""Émission, révocation et authentification des jetons d'agent."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    AuthenticationError,
    ConflictError,
    NotFoundError,
    ValidationError,
)
from app.core.security import KIND_AGENT, create_access_token, decode_agent_token
from app.db.models import AgentToken

# Dix ans : un agent ne se reconnecte pas derrière un formulaire. La borne
# n'est pas l'expiration, c'est la révocation.
_DUREE_MINUTES = 10 * 365 * 24 * 60
_LABEL_MAX = 80  # taille de la colonne `agent_tokens.label`


async def emettre(db: AsyncSession, *, user_id: str, label: str) -> tuple[AgentToken, str]:
    """Crée un jeton et rend (la ligne, le jeton en clair).

    Le clair n'est rendu qu'ici : on ne le stocke pas, donc on ne peut pas le
    réafficher. L'interface doit le dire avant de le montrer.

    Raises:
        ValidationError: libellé vide ou trop long.
        ConflictError: un jeton non révoqué porte déjà ce libellé. Un libellé
            révoqué se réutilise : c'est le geste de secours après une fuite.
    """
    label = label.strip()
    if not label or len(label) > _LABEL_MAX:
        raise ValidationError(
            f"Un jeton d'agent doit porter un libellé de 1 à {_LABEL_MAX} caractères."
        )
    deja = await db.execute(
        select(AgentToken.id).where(
            AgentToken.user_id == user_id,
            AgentToken.label == label,
            AgentToken.revoked_at.is_(None),
        )
    )
    if deja.first() is not None:
        raise ConflictError(
            f"Un jeton actif porte déjà le libellé « {label} ». C'est ce libellé "
            "qui dit quel agent a décidé, dans les pings comme dans le fil, et "
            "la révocation est par jeton : avec deux homonymes, tu ne saurais "
            "pas lequel couper. Donne-lui un autre nom, ou révoque le premier."
        )
    jti = str(uuid.uuid4())
    ligne = AgentToken(user_id=user_id, label=label, jti=jti)
    db.add(ligne)
    await db.flush()
    clair = create_access_token(
        user_id,
        expires_minutes=_DUREE_MINUTES,
        extra_claims={"kind": KIND_AGENT, "jti": jti},
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
    """Révoque un jeton. Ne commit pas : c'est à l'appelant, et sans commit rien
    n'est coupé, même si l'objet en mémoire porte déjà `revoked_at`."""
    ligne = await db.get(AgentToken, token_id)
    if ligne is None or ligne.user_id != user_id:
        raise NotFoundError(f"Jeton {token_id} introuvable.")
    if ligne.revoked_at is None:
        ligne.revoked_at = datetime.now(UTC)


async def authentifier(db: AsyncSession, *, jeton: str) -> tuple[str, str]:
    """Rend (user_id, libellé) ou lève. Met à jour la date de dernier usage."""
    charge = decode_agent_token(jeton)
    jti = charge.get("jti")
    sujet = charge.get("sub")
    if not isinstance(jti, str) or not isinstance(sujet, str):
        raise AuthenticationError("Jeton d'agent incomplet.")
    result = await db.execute(select(AgentToken).where(AgentToken.jti == jti))
    ligne = result.scalar_one_or_none()
    if ligne is None or ligne.user_id != sujet:
        raise AuthenticationError("Jeton d'agent inconnu.")
    # Distinct d'« inconnu » : le `jti` ne circule que dans un jeton signé par la
    # clé de l'instance, donc la différence ne renseigne personne, et c'est elle
    # dont John a besoin pour comprendre pourquoi un agent est refusé.
    if ligne.revoked_at is not None:
        raise AuthenticationError("Jeton d'agent révoqué.")
    ligne.last_used_at = datetime.now(UTC)
    return ligne.user_id, ligne.label
