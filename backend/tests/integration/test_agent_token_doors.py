"""Un jeton d'agent n'ouvre ni l'API REST ni le WebSocket.

Il est signé par la même clé qu'un jeton de connexion et porte un `sub` : sans
refus explicite, il vaudrait dix ans de connexion complète, et la table de
révocation, que ces deux portes ne consultent pas, ne protégerait rien.
Un test par porte : chacune est un témoin distinct du contrôle d'accès.
"""

from __future__ import annotations

from typing import cast

import pytest
from app.core.security import create_access_token, hash_password
from app.db.models import Session, User
from app.services import agent_token_service
from app.ws import sessions as ws_sessions
from fastapi import WebSocket
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

_FERMETURE_POLITIQUE = 1008
_FERMETURE_INTERNE = 1011


async def _utilisateur(factory: async_sessionmaker[AsyncSession]) -> str:
    async with factory() as db:
        user = User(email="john@example.com", hashed_password=hash_password("motdepasse-solide"))
        db.add(user)
        await db.commit()
        return user.id


async def _session_de(factory: async_sessionmaker[AsyncSession], user_id: str) -> str:
    async with factory() as db:
        session = Session(user_id=user_id, branch="main")
        db.add(session)
        await db.commit()
        return session.id


async def _jeton_d_agent(factory: async_sessionmaker[AsyncSession], user_id: str) -> str:
    """Un jeton d'agent valide, non révoqué : celui qui passerait si rien ne le refusait."""
    async with factory() as db:
        _, clair = await agent_token_service.emettre(db, user_id=user_id, label="eldir du village")
        await db.commit()
    return clair


# ── Porte REST : app.core.deps.get_current_user_id ──────────────────────
async def test_rest_accepte_un_jeton_de_connexion(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    user_id = await _utilisateur(session_factory)
    reponse = await client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {create_access_token(user_id)}"}
    )
    assert reponse.status_code == 200
    assert reponse.json()["id"] == user_id


async def test_rest_refuse_un_jeton_d_agent_et_dit_pourquoi(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    user_id = await _utilisateur(session_factory)
    jeton = await _jeton_d_agent(session_factory, user_id)
    reponse = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {jeton}"})
    assert reponse.status_code == 401
    assert "Jeton d'agent" in reponse.json()["message"]
    assert "MCP" in reponse.json()["message"]


# ── Porte WebSocket : app.ws.sessions.session_stream ────────────────────
class _FauxWebSocket:
    """Enregistre la fermeture : tout ce que la porte fait avant d'accepter."""

    def __init__(self) -> None:
        self.fermetures: list[tuple[int, str | None]] = []

    async def close(self, code: int = 1000, reason: str | None = None) -> None:
        self.fermetures.append((code, reason))


async def _ouvrir(session_id: str, jeton: str) -> list[tuple[int, str | None]]:
    ws = _FauxWebSocket()
    await ws_sessions.session_stream(cast(WebSocket, ws), session_id, token=jeton)
    return ws.fermetures


@pytest.fixture
def ws_de_test(
    monkeypatch: pytest.MonkeyPatch, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    """Base de test, et pas de Redis : la porte s'arrête après l'authentification
    et l'autorisation, juste avant le pubsub (fermeture 1011)."""

    def _absent() -> None:
        raise RuntimeError("Redis client non initialisé.")

    monkeypatch.setattr(ws_sessions, "async_session_factory", session_factory)
    monkeypatch.setattr(ws_sessions, "get_redis_client", _absent)


@pytest.mark.usefixtures("ws_de_test")
async def test_ws_accepte_un_jeton_de_connexion(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Le jeton passe l'authentification ET l'autorisation (la session est à lui) :
    la porte va jusqu'au pubsub, que `ws_de_test` coupe en 1011."""
    user_id = await _utilisateur(session_factory)
    session_id = await _session_de(session_factory, user_id)
    fermetures = await _ouvrir(session_id, create_access_token(user_id))
    assert fermetures == [(_FERMETURE_INTERNE, None)]


@pytest.mark.usefixtures("ws_de_test")
async def test_ws_refuse_un_jeton_d_agent_et_dit_pourquoi(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    user_id = await _utilisateur(session_factory)
    session_id = await _session_de(session_factory, user_id)
    jeton = await _jeton_d_agent(session_factory, user_id)
    # Même propriétaire, session existante : seul le type de jeton est en cause.
    fermetures = await _ouvrir(session_id, jeton)
    assert len(fermetures) == 1
    code, motif = fermetures[0]
    assert code == _FERMETURE_POLITIQUE
    assert motif is not None
    assert "Jeton d'agent" in motif
    assert "MCP" in motif
