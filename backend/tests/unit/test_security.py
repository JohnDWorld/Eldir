"""Tests unitaires de app.core.security."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest
from app.core.exceptions import AuthenticationError
from app.core.security import (
    create_access_token,
    decode_agent_token,
    decode_session_token,
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
    payload = decode_session_token(token)
    assert payload["sub"] == "user-123"


def test_jwt_invalid_raises() -> None:
    with pytest.raises(AuthenticationError, match="Jeton invalide"):
        decode_session_token("not-a-token")


def test_decode_session_token_refuse_un_jeton_d_agent_et_dit_pourquoi() -> None:
    jeton = create_access_token("user-123", extra_claims={"kind": "agent", "jti": "j"})
    with pytest.raises(AuthenticationError, match="Jeton d'agent") as exc:
        decode_session_token(jeton)
    # Le message sert de motif de fermeture WebSocket : 123 octets au plus.
    assert len(exc.value.message.encode()) <= 123


@pytest.mark.parametrize("kind", ["refresh", "session", ""])
def test_decode_session_token_refuse_tout_kind(kind: str) -> None:
    """Liste blanche : un jeton de connexion n'a pas de `kind`, un futur type de
    jeton ne doit pas passer les portes sans que quelqu'un l'y autorise."""
    jeton = create_access_token("user-123", extra_claims={"kind": kind})
    with pytest.raises(AuthenticationError, match="pas un jeton de connexion") as exc:
        decode_session_token(jeton)
    assert len(exc.value.message.encode()) <= 123


def test_decode_agent_token_accepte_un_jeton_d_agent() -> None:
    jeton = create_access_token("user-123", extra_claims={"kind": "agent", "jti": "j"})
    assert decode_agent_token(jeton)["jti"] == "j"


@pytest.mark.parametrize("extra", [{}, {"kind": "refresh"}])
def test_decode_agent_token_refuse_ce_qui_n_est_pas_un_jeton_d_agent(
    extra: dict[str, str],
) -> None:
    with pytest.raises(AuthenticationError, match="pas un jeton d'agent"):
        decode_agent_token(create_access_token("user-123", extra_claims=extra))


@pytest.mark.parametrize(
    ("decoder", "extra"),
    [(decode_session_token, {}), (decode_agent_token, {"kind": "agent"})],
)
def test_les_deux_decodeurs_verifient_signature_et_expiration(
    decoder: Callable[[str], dict[str, Any]], extra: dict[str, str]
) -> None:
    """Les deux portes reposent sur le même décodeur privé : si celui-ci cessait
    de vérifier, aucune des deux ne protégerait plus rien."""
    valide = create_access_token("user-123", extra_claims=extra)
    assert decoder(valide)["sub"] == "user-123"
    falsifie = valide[:-4] + ("AAAA" if not valide.endswith("AAAA") else "BBBB")
    with pytest.raises(AuthenticationError, match="Jeton invalide"):
        decoder(falsifie)
    # Deux causes distinctes, deux messages : John doit savoir s'il faut en
    # réémettre un (expiré) ou chercher une erreur de copie (invalide).
    with pytest.raises(AuthenticationError, match="Jeton expiré"):
        decoder(create_access_token("user-123", expires_minutes=-1, extra_claims=extra))


def test_fernet_roundtrip() -> None:
    encrypted = encrypt_secret("ghp_secret_token")
    assert encrypted != "ghp_secret_token"
    assert decrypt_secret(encrypted) == "ghp_secret_token"
