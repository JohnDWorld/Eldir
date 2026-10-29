"""Sécurité : hash de mots de passe, JWT, chiffrement Fernet pour secrets en DB."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from cryptography.fernet import Fernet, InvalidToken
from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import get_settings
from app.core.exceptions import AuthenticationError

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return _pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return _pwd_context.verify(plain, hashed)


# ── JWT ─────────────────────────────────────────────────────────
def create_access_token(
    subject: str,
    *,
    expires_minutes: int | None = None,
    extra_claims: dict[str, Any] | None = None,
) -> str:
    settings = get_settings()
    expire = datetime.now(UTC) + timedelta(minutes=expires_minutes or settings.jwt_expire_minutes)
    payload: dict[str, Any] = {"sub": subject, "exp": expire, **(extra_claims or {})}
    return jwt.encode(
        payload,
        settings.jwt_secret.get_secret_value(),
        algorithm=settings.jwt_algorithm,
    )


def decode_access_token(token: str) -> dict[str, Any]:
    settings = get_settings()
    try:
        return jwt.decode(
            token,
            settings.jwt_secret.get_secret_value(),
            algorithms=[settings.jwt_algorithm],
        )
    except JWTError as exc:
        raise AuthenticationError("Token invalide ou expiré.") from exc


# Valeur du claim `kind` d'un jeton d'agent externe. Un jeton de connexion n'a
# pas de `kind`. Ces trois définitions sont le seul endroit qui décide de ce
# qu'est un jeton d'agent : toute porte d'entrée passe par l'une d'elles.
KIND_AGENT = "agent"


def is_agent_payload(payload: dict[str, Any]) -> bool:
    """Vrai si la charge d'un JWT décodé est celle d'un jeton d'agent."""
    return payload.get("kind") == KIND_AGENT


def decode_session_token(token: str) -> dict[str, Any]:
    """Décode un jeton de connexion (API REST, WebSocket) et refuse un jeton d'agent.

    Le jeton d'agent est signé par la même clé et porte un `sub` : sans ce refus,
    il vaudrait dix ans de connexion complète, et la table de révocation, que ce
    chemin ne consulte pas, ne protégerait rien. Il n'ouvre que la surface MCP,
    qui passe par `agent_token_service.authentifier`.

    Le message part tel quel en motif de fermeture WebSocket, limité à 123 octets.
    """
    payload = decode_access_token(token)
    if is_agent_payload(payload):
        raise AuthenticationError(
            "Jeton d'agent : réservé à la surface MCP, il n'ouvre ni l'API ni le WebSocket."
        )
    return payload


# ── Chiffrement symétrique (Fernet) pour credentials Git en DB ──
def _fernet() -> Fernet:
    settings = get_settings()
    key = settings.encryption_key.get_secret_value()
    if not key:
        raise RuntimeError("ENCRYPTION_KEY non configurée - générer via Fernet.generate_key()")
    return Fernet(key.encode() if isinstance(key, str) else key)


def encrypt_secret(plain: str) -> str:
    return _fernet().encrypt(plain.encode()).decode()


def decrypt_secret(token: str) -> str:
    try:
        return _fernet().decrypt(token.encode()).decode()
    except InvalidToken as exc:
        raise AuthenticationError("Secret chiffré invalide.") from exc
