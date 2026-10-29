"""Tests unitaires de app.core.security."""

from __future__ import annotations

import pytest
from app.core.exceptions import AuthenticationError
from app.core.security import (
    create_access_token,
    decode_access_token,
    decode_session_token,
    decrypt_secret,
    encrypt_secret,
    hash_password,
    is_agent_payload,
    verify_password,
)


def test_password_hash_roundtrip() -> None:
    hashed = hash_password("super-secret-pw")
    assert hashed != "super-secret-pw"
    assert verify_password("super-secret-pw", hashed)
    assert not verify_password("wrong", hashed)


def test_jwt_roundtrip() -> None:
    token = create_access_token("user-123")
    payload = decode_access_token(token)
    assert payload["sub"] == "user-123"


def test_jwt_invalid_raises() -> None:
    with pytest.raises(AuthenticationError):
        decode_access_token("not-a-token")


def test_decode_session_token_accepte_un_jeton_de_connexion() -> None:
    payload = decode_session_token(create_access_token("user-123"))
    assert payload["sub"] == "user-123"
    assert not is_agent_payload(payload)


def test_decode_session_token_refuse_un_jeton_d_agent_et_dit_pourquoi() -> None:
    jeton = create_access_token("user-123", extra_claims={"kind": "agent", "jti": "j"})
    with pytest.raises(AuthenticationError, match="Jeton d'agent") as exc:
        decode_session_token(jeton)
    # Le message sert de motif de fermeture WebSocket : 123 octets au plus.
    assert len(exc.value.message.encode()) <= 123


def test_decode_session_token_refuse_toujours_un_jeton_invalide() -> None:
    with pytest.raises(AuthenticationError):
        decode_session_token("not-a-token")


def test_fernet_roundtrip() -> None:
    encrypted = encrypt_secret("ghp_secret_token")
    assert encrypted != "ghp_secret_token"
    assert decrypt_secret(encrypted) == "ghp_secret_token"
