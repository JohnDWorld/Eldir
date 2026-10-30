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
from datetime import UTC, datetime, timedelta

import pytest
import uvicorn
from app.core.config import get_settings
from app.core.security import create_access_token, hash_password
from app.db.models import Session, User
from app.main import create_app
from app.services import agent_token_service
from app.ws import sessions as ws_sessions
from httpx import AsyncClient
from jose import jwt
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from websockets.asyncio.client import ClientConnection, connect
from websockets.exceptions import ConnectionClosed

_FERMETURE_POLITIQUE = 1008
_FERMETURE_INTERNE = 1011


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


def _jeton_sans_sujet() -> str:
    """Signé par la bonne clé et valide, mais sans `sub` : personne à qui l'attribuer."""
    settings = get_settings()
    return jwt.encode(
        {"exp": datetime.now(UTC) + timedelta(minutes=5)},
        settings.jwt_secret.get_secret_value(),
        algorithm=settings.jwt_algorithm,
    )


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


async def test_rest_dit_qu_un_jeton_n_a_pas_de_sujet(client: AsyncClient) -> None:
    reponse = await client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {_jeton_sans_sujet()}"}
    )
    assert reponse.status_code == 401
    assert reponse.json()["message"] == "Jeton sans sujet valide."


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


async def _fermeture(implementation: str, session_id: str, jeton: str) -> tuple[int, str]:
    """Se connecte pour de vrai et rend (code, motif) de la fermeture reçue."""
    async with _connexion(implementation, session_id, jeton) as client:
        with pytest.raises(ConnectionClosed) as exc:
            await client.recv()
    recu = exc.value.rcvd
    assert recu is not None, "le serveur doit fermer proprement, avec un code"
    return recu.code, recu.reason


@pytest.mark.usefixtures("ws_de_test")
async def test_ws_refuse_un_jeton_d_agent_et_le_client_recoit_pourquoi(
    session_factory: async_sessionmaker[AsyncSession], implementation_ws: str
) -> None:
    user_id = await _utilisateur(session_factory)
    # Même propriétaire, session existante : seul le type de jeton est en cause.
    session_id = await _session_de(session_factory, user_id)
    jeton = await _jeton_d_agent(session_factory, user_id)
    code, motif = await _fermeture(implementation_ws, session_id, jeton)
    assert code == _FERMETURE_POLITIQUE
    assert "Jeton d'agent" in motif
    assert "MCP" in motif


# Chaque refus ferme avec un motif lisible : un refus muet ne dit pas à celui
# qui s'est trompé ce qu'il doit corriger.
@pytest.mark.usefixtures("ws_de_test")
async def test_ws_dit_qu_un_jeton_est_invalide(implementation_ws: str) -> None:
    code, motif = await _fermeture(implementation_ws, "peu-importe", "pas-un-jeton")
    assert (code, motif) == (_FERMETURE_POLITIQUE, "Jeton invalide.")


@pytest.mark.usefixtures("ws_de_test")
async def test_ws_dit_qu_un_jeton_est_expire(
    session_factory: async_sessionmaker[AsyncSession], implementation_ws: str
) -> None:
    user_id = await _utilisateur(session_factory)
    expire = create_access_token(user_id, expires_minutes=-1)
    code, motif = await _fermeture(implementation_ws, "peu-importe", expire)
    assert (code, motif) == (_FERMETURE_POLITIQUE, "Jeton expiré.")


@pytest.mark.usefixtures("ws_de_test")
async def test_ws_dit_qu_un_jeton_n_a_pas_de_sujet(implementation_ws: str) -> None:
    sans_sujet = _jeton_sans_sujet()
    code, motif = await _fermeture(implementation_ws, "peu-importe", sans_sujet)
    assert (code, motif) == (_FERMETURE_POLITIQUE, "Jeton sans sujet valide.")


@pytest.mark.usefixtures("ws_de_test")
async def test_ws_dit_qu_une_session_est_introuvable_pour_son_porteur(
    session_factory: async_sessionmaker[AsyncSession], implementation_ws: str
) -> None:
    """La session existe mais n'est pas à ce porteur : même motif que si elle
    n'existait pas, pour ne pas renseigner sur ce qu'on ne possède pas."""
    proprietaire = await _utilisateur(session_factory)
    session_id = await _session_de(session_factory, proprietaire)
    autre = create_access_token("quelqu-un-d-autre")
    code, motif = await _fermeture(implementation_ws, session_id, autre)
    assert (code, motif) == (_FERMETURE_POLITIQUE, "Session introuvable.")


async def test_ws_dit_que_le_bus_est_indisponible(
    session_factory: async_sessionmaker[AsyncSession],
    implementation_ws: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _redis_absent() -> None:
        raise RuntimeError("Redis client non initialisé.")

    monkeypatch.setattr(ws_sessions, "async_session_factory", session_factory)
    monkeypatch.setattr(ws_sessions, "get_redis_client", _redis_absent)
    user_id = await _utilisateur(session_factory)
    session_id = await _session_de(session_factory, user_id)
    code, motif = await _fermeture(implementation_ws, session_id, create_access_token(user_id))
    assert (code, motif) == (_FERMETURE_INTERNE, "Le bus d'événements est indisponible.")
