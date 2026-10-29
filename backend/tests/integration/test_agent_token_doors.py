"""Un jeton d'agent n'ouvre ni l'API REST ni le WebSocket.

Il est signé par la même clé qu'un jeton de connexion et porte un `sub` : sans
refus explicite, il vaudrait dix ans de connexion complète, et la table de
révocation, que ces deux portes ne consultent pas, ne protégerait rien.
Un test par porte : chacune est un témoin distinct du contrôle d'accès.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import pytest
import uvicorn
from app.core.security import create_access_token, hash_password
from app.db.models import Session, User
from app.main import create_app
from app.services import agent_token_service
from app.ws import sessions as ws_sessions
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from websockets.asyncio.client import ClientConnection, connect
from websockets.exceptions import ConnectionClosed

_FERMETURE_POLITIQUE = 1008


async def _utilisateur(factory: async_sessionmaker[AsyncSession]) -> str:
    async with factory() as db:
        user = User(
            email="utilisateur@exemple.lan", hashed_password=hash_password("motdepasse-solide")
        )
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
# Testée contre un vrai serveur uvicorn et un vrai client `websockets`, pas
# contre un faux WebSocket : un `close` émis avant `accept` y devient un refus
# HTTP 403 sans corps, et seul le vrai transport le montre. Un faux WebSocket
# affirmerait un code et un motif que le client ne reçoit jamais.
class _BusFactice:
    """Remplace Redis : un événement, puis la connexion reste ouverte."""

    def __init__(self, _redis: object) -> None: ...

    async def subscribe(self, session_id: str) -> AsyncIterator[dict[str, str]]:
        yield {"type": "text", "session_id": session_id}
        await asyncio.Event().wait()


@pytest.fixture(params=["auto", "websockets-sansio"])
def implementation_ws(request: pytest.FixtureRequest) -> str:
    """`auto` est ce que lance la prod ; sansio est le remplaçant annoncé du défaut."""
    return str(request.param)


@pytest.fixture
def ws_de_test(
    monkeypatch: pytest.MonkeyPatch, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    """Base de test et faux Redis : le reste de la porte est le vrai."""
    monkeypatch.setattr(ws_sessions, "async_session_factory", session_factory)
    monkeypatch.setattr(ws_sessions, "get_redis_client", object)
    monkeypatch.setattr(ws_sessions, "EventBus", _BusFactice)


@asynccontextmanager
async def _connexion(
    implementation: str, session_id: str, jeton: str
) -> AsyncIterator[ClientConnection]:
    """Lance l'application sous uvicorn sur un port libre et s'y connecte pour de vrai."""
    config = uvicorn.Config(
        create_app(),
        host="127.0.0.1",
        port=0,
        ws=implementation,
        lifespan="off",
        log_level="warning",
    )
    serveur = uvicorn.Server(config)
    tache = asyncio.create_task(serveur.serve())
    try:
        async with asyncio.timeout(10):
            # uvicorn n'expose que ce drapeau pour dire qu'il écoute.
            while not serveur.started:  # noqa: ASYNC110
                await asyncio.sleep(0.01)
            port = serveur.servers[0].sockets[0].getsockname()[1]
            url = f"ws://127.0.0.1:{port}/ws/sessions/{session_id}?token={jeton}"
            async with connect(url) as client:
                yield client
    finally:
        serveur.should_exit = True
        await tache


@pytest.mark.usefixtures("ws_de_test")
async def test_ws_accepte_un_jeton_de_connexion(
    session_factory: async_sessionmaker[AsyncSession], implementation_ws: str
) -> None:
    """Le jeton passe l'authentification ET l'autorisation (la session est à lui),
    la connexion est acceptée une seule fois et le client reçoit les événements."""
    user_id = await _utilisateur(session_factory)
    session_id = await _session_de(session_factory, user_id)
    async with _connexion(implementation_ws, session_id, create_access_token(user_id)) as client:
        evenement = json.loads(await client.recv())
    assert evenement == {"type": "text", "session_id": session_id}


@pytest.mark.usefixtures("ws_de_test")
async def test_ws_refuse_un_jeton_d_agent_et_le_client_recoit_pourquoi(
    session_factory: async_sessionmaker[AsyncSession], implementation_ws: str
) -> None:
    user_id = await _utilisateur(session_factory)
    # Même propriétaire, session existante : seul le type de jeton est en cause.
    session_id = await _session_de(session_factory, user_id)
    jeton = await _jeton_d_agent(session_factory, user_id)
    async with _connexion(implementation_ws, session_id, jeton) as client:
        with pytest.raises(ConnectionClosed) as exc:
            await client.recv()
    recu = exc.value.rcvd
    assert recu is not None, "le serveur doit fermer proprement, avec un code"
    assert recu.code == _FERMETURE_POLITIQUE
    assert "Jeton d'agent" in recu.reason
    assert "MCP" in recu.reason
