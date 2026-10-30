"""Sécurité : hash de mots de passe, JWT, chiffrement Fernet pour secrets en DB."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from cryptography.fernet import Fernet, InvalidToken
from jose import ExpiredSignatureError, JWTError, jwt
from passlib.context import CryptContext

from app.core.config import get_settings
from app.core.exceptions import AuthenticationError

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return _pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return _pwd_context.verify(plain, hashed)


# ── JWT ─────────────────────────────────────────────────────────
def extract_bearer(authorization: str | None) -> str:
    """Rend le jeton d'un en-tête `Authorization: Bearer <jeton>`, ou lève.

    Le seul endroit qui décide de la forme de l'en-tête : l'API REST et la garde
    MCP passent ici, pour qu'aucune forme ne soit acceptée par l'une et refusée
    par l'autre. Le schéma se compare sans tenir compte de la casse (RFC 7235).
    Ne dit rien du jeton lui-même, que le décodeur de chaque porte examine.
    """
    schema, _, jeton = (authorization or "").partition(" ")
    if schema.lower() != "bearer" or not jeton:
        raise AuthenticationError("Header Authorization manquant ou mal formé.")
    return jeton


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


def _decode_jwt(token: str) -> dict[str, Any]:
    """Décodeur nu : vérifie la signature et l'expiration, rien d'autre.

    Privé exprès. Il ne dit pas à quelle porte le jeton est destiné, donc le
    brancher directement sur un transport ouvre cette porte à tous les types de
    jeton (c'était le trou des jetons d'agent). Passer par `decode_session_token`
    ou `decode_agent_token`, qui nomment la porte.
    """
    settings = get_settings()
    try:
        return jwt.decode(
            token,
            settings.jwt_secret.get_secret_value(),
            algorithms=[settings.jwt_algorithm],
        )
    except ExpiredSignatureError as exc:
        raise AuthenticationError("Jeton expiré.") from exc
    except JWTError as exc:
        raise AuthenticationError("Jeton invalide.") from exc


# Valeur du claim `kind` d'un jeton d'agent externe. Un jeton de connexion n'en
# porte aucun. Les deux fonctions ci-dessous sont, avec `_decode_jwt`, le seul
# endroit qui décide à quelle porte un jeton est destiné.
KIND_AGENT = "agent"


def decode_session_token(token: str) -> dict[str, Any]:
    """Décode un jeton de connexion (API REST, WebSocket) et refuse tout autre.

    Liste blanche : un jeton de connexion ne porte aucun `kind`, et tout jeton
    qui en porte un est refusé, y compris un type futur. Le jeton d'agent est
    signé par la même clé et porte un `sub` : sans ce refus, il vaudrait dix ans
    de connexion complète, et la table de révocation, que ce chemin ne consulte
    pas, ne protégerait rien. Il n'ouvre que la surface MCP.

    Les messages partent tels quels en motif de fermeture WebSocket : 123 octets
    au plus.
    """
    payload = _decode_jwt(token)
    kind = payload.get("kind")
    if kind == KIND_AGENT:
        raise AuthenticationError(
            "Jeton d'agent : réservé à la surface MCP, il n'ouvre ni l'API ni le WebSocket."
        )
    if kind is not None:
        raise AuthenticationError("Ce jeton n'est pas un jeton de connexion.")
    return payload


def decode_agent_token(token: str) -> dict[str, Any]:
    """Décode un jeton d'agent (surface MCP) et refuse tout autre.

    La signature ne suffit pas : l'appelant doit encore vérifier le `jti` dans la
    table, qui est la liste blanche de révocation (`agent_token_service`).
    """
    payload = _decode_jwt(token)
    if payload.get("kind") != KIND_AGENT:
        raise AuthenticationError("Ce jeton n'est pas un jeton d'agent.")
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
