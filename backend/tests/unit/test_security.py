"""Tests unitaires de app.core.security."""

from __future__ import annotations

import pytest
from app.core.exceptions import AuthenticationError
from app.core.security import (
    create_access_token,
    decode_access_token,
    decrypt_secret,
    encrypt_secret,
    hash_password,
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


def test_fernet_roundtrip() -> None:
    encrypted = encrypt_secret("ghp_secret_token")
    assert encrypted != "ghp_secret_token"
    assert decrypt_secret(encrypted) == "ghp_secret_token"
