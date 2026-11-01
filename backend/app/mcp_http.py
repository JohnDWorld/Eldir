"""La surface MCP d'Eldir, servie en HTTP pour un agent extérieur.

Les outils servis sont ceux du superviseur, à l'identique : ce module ne porte
aucune logique métier, seulement l'adaptation d'un transport et la garde du
jeton. Toute règle qui vivrait ici seulement serait une règle que le
superviseur interne n'applique pas, donc deux Eldir qui divergent.

Une seule exception, et elle est un retrait, pas une règle : la surface externe
ne sert pas `allow_publish`. Cf. `HORS_SURFACE_EXTERNE`.
"""

from __future__ import annotations

import copy
from collections.abc import Awaitable, Callable
from contextvars import ContextVar

from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.tools import Tool
from mcp.server.transport_security import TransportSecuritySettings
from pydantic import StrictBool
from starlette.datastructures import Headers
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from app.core.config import get_settings
from app.core.exceptions import AuthenticationError
from app.core.logging import get_logger
from app.core.security import extract_bearer
from app.db.session import async_session_factory
from app.services import agent_token_service
from app.services.singletons import get_supervisor_service
from app.services.supervisor_service import SCHEMAS_OUTILS

logger = get_logger("eldir.mcp")

# Au nom de qui l'appel en cours agit : (user_id, libellé du jeton). Les
# fonctions d'outil de FastMCP ne reçoivent pas la requête, et un contextvar
# traverse la pile sans que chaque outil ait à porter un argument de plus.
# Posé par `GardeJeton`, jamais lu ailleurs que par `agent_courant`.
AGENT_COURANT: ContextVar[tuple[str, str] | None] = ContextVar("agent_courant", default=None)


def agent_courant() -> tuple[str, str]:
    valeur = AGENT_COURANT.get()
    if valeur is None:
        raise AuthenticationError("Appel MCP sans agent authentifié.")
    return valeur


class GardeJeton:
    """Valide le Bearer devant l'app MCP et pose l'identité de l'appel.

    Pourquoi pas le `token_verifier` de FastMCP : il exige des réglages `auth`
    complets de serveur de ressources OAuth (`ValueError: Cannot specify
    auth_server_provider or token_verifier without auth settings`). On sert un
    jeton statique, pas un flux OAuth : une vingtaine de lignes honnêtes valent
    mieux qu'une façade.

    Toute la décision (bonne porte, révocation) est dans
    `agent_token_service.authentifier` : la garde n'en réimplémente rien.
    """

    def __init__(self, app: ASGIApp) -> None:
        self._app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        # L'app MCP ne sert que du HTTP (aucune route WebSocket) : rien à garder
        # d'autre.
        if scope["type"] != "http":
            await self._app(scope, receive, send)
            return
        try:
            identite = await self._identifier(Headers(scope=scope))
        except AuthenticationError as exc:
            # Le motif seulement : jamais le jeton, ni en clair ni tronqué.
            logger.info("mcp.refus", motif=exc.message)
            reponse = JSONResponse(
                {"code": exc.code, "message": exc.message, "details": exc.details},
                status_code=exc.status_code,
                headers={"WWW-Authenticate": "Bearer"},
            )
            await reponse(scope, receive, send)
            return
        contexte = AGENT_COURANT.set(identite)
        try:
            await self._app(scope, receive, send)
        finally:
            AGENT_COURANT.reset(contexte)

    @staticmethod
    async def _identifier(entetes: Headers) -> tuple[str, str]:
        jeton = extract_bearer(entetes.get("authorization"))
        async with async_session_factory() as db:
            identite = await agent_token_service.authentifier(db, jeton=jeton)
            # Sans commit, la date de dernier usage écrite par `authentifier`
            # serait perdue à la fermeture de la session.
            await db.commit()
        return identite


# ── Les cinq outils : le corps est celui du superviseur, rien d'autre ──
# Les annotations servent à valider les arguments reçus ; ce que le modèle lit
# (descriptions, schéma) vient de SCHEMAS_OUTILS, cf. `_outil`. Elles sont
# STRICTES pour les booléens : le serveur MCP in-process valide contre la table,
# où `"true"` n'est pas un booléen, alors que pydantic coerce par défaut. Avec
# `bool`, `{"autoriser": "true"}` ouvrait la publication par HTTP seulement. Un
# `str` pydantic, lui, refuse déjà tout ce qui n'est pas une chaîne JSON.
async def list_projects() -> str:
    user_id, _ = agent_courant()
    return await get_supervisor_service().outil_list_projects(user_id)


async def list_sessions() -> str:
    user_id, _ = agent_courant()
    return await get_supervisor_service().outil_list_sessions(user_id)


async def dispatch(
    project_id: str,
    consigne: str,
    # `""` et non `None` : la table type `session_id` en `string`, elle refuse `null`.
    session_id: str = "",
    nouveau_chantier: StrictBool = False,
) -> str:
    # Le libellé du jeton signe la consigne : l'historique de la session dit lequel
    # des deux Eldir l'a donnée.
    user_id, libelle = agent_courant()
    return await get_supervisor_service().outil_dispatch(
        user_id,
        project_id=project_id,
        consigne=consigne,
        session_id=session_id,
        nouveau_chantier=nouveau_chantier,
        libelle_agent=libelle,
    )


async def remember(fait: str) -> str:
    # Le libellé du jeton signe la préférence : elle entre dans le prompt de John.
    user_id, libelle = agent_courant()
    return await get_supervisor_service().outil_remember(user_id, fait=fait, libelle_agent=libelle)


# Ce que le superviseur sait faire et que la surface externe ne sert pas.
#
# `allow_publish` ouvre la seule action irréversible d'une session. Un agent
# extérieur transmet des suggestions et des tickets écrits par des utilisateurs
# de La Boutique : du texte non fiable, envoyé à des sessions qui tournent en
# `bypassPermissions`. Lui laisser cet outil rendait la porte de publication
# ouvrable par injection de prompt, et un jeton d'agent vit dix ans : la garde
# tenait face à la dérive, pas face à une consigne hostile.
#
# Depuis l'extérieur, la publication ne s'ouvre donc que par un geste humain
# dans le dashboard. Le superviseur interne garde l'outil (décision de John du
# 2026-10-30). Ce qui le protège n'est pas qu'il ignore le texte extérieur : la
# table ci-dessous sert `remember`, qui dépose une ligne d'agent dans son prompt
# durable, relue à chaque démarrage. C'est `_NOTE_AGENTS`
# (`supervisor_service.py`) qui lui interdit de lire une telle ligne comme une
# autorisation de publier. Une garde de prompt, là où les autres sont des
# mécanismes : à rouvrir si le superviseur se met à encaisser plus de texte
# extérieur qu'une préférence bornée et marquée.
# Aucune fonction d'adaptation n'existe ici pour cet outil, et c'est voulu :
# un nom retiré d'une table se remet, une fonction absente ne s'appelle pas.
HORS_SURFACE_EXTERNE: frozenset[str] = frozenset({"allow_publish"})

OUTILS: dict[str, Callable[..., Awaitable[str]]] = {
    "list_projects": list_projects,
    "list_sessions": list_sessions,
    "dispatch": dispatch,
    "remember": remember,
}


def _outil(nom: str, fonction: Callable[..., Awaitable[str]]) -> Tool:
    """Un outil FastMCP dont description ET schéma viennent de la table.

    `add_tool` ne prend pas de schéma : FastMCP déduirait le sien des
    annotations, et les descriptions de chaque paramètre (« la session enfant
    ne voit pas ta conversation avec John ») disparaîtraient, alors que c'est
    ce que le modèle lit. D'où `Tool` construit à la main, schéma remplacé.
    """
    description, schema = SCHEMAS_OUTILS[nom]
    # `structured_output=False` : le superviseur interne rend du texte seul, la
    # surface HTTP ne doit pas y ajouter un `structuredContent` que l'autre n'a pas.
    outil = Tool.from_function(fonction, name=nom, description=description, structured_output=False)
    # Une copie : l'objet de la table sert aussi au serveur in-process, et FastMCP
    # tient `parameters` pour le sien.
    outil.parameters = copy.deepcopy(schema)
    return outil


def construire_app_mcp() -> tuple[FastMCP, ASGIApp]:
    """Rend le serveur FastMCP (pour son gestionnaire de sessions) et l'app à monter.

    Un appel par application : `session_manager.run()` ne peut tourner qu'une
    fois par instance, donc deux applications ne partagent jamais un serveur.
    """
    reglages = get_settings()
    hotes = reglages.mcp_hosts
    mcp = FastMCP(
        "eldir",
        tools=[_outil(nom, fonction) for nom, fonction in OUTILS.items()],
        # Sans état : aucune affinité de session, donc un redémarrage du
        # backend ne casse pas l'agent, et n'importe quel proxy convient.
        stateless_http=True,
        # Réponse en JSON plutôt qu'en flux SSE sur les POST. Pas un réglage
        # de confort : la correction d'un blocage.
        #
        # Le chemin SSE écrit le flux depuis une seconde tâche, et sous charge
        # elle sortait AVANT d'avoir reçu la réponse. Le serveur le disait
        # lui-même : « Closing SSE writer », puis « Request stream 0 not found
        # for message ». La réponse revenait du serveur bas niveau, son flux
        # n'existait plus, elle tombait par terre. Le client recevait les
        # en-têtes 200 `text/event-stream`, puis une connexion coupée sans
        # corps, et attendait jusqu'à expiration une réponse que plus personne
        # ne produisait. Cf. modelcontextprotocol/python-sdk#1764.
        #
        # Le chemin JSON attend la réponse dans la MÊME tâche, et si le flux
        # meurt sans réponse il rend un 500 : le client échoue tout de suite au
        # lieu d'attendre. Mesuré sous contention (coverage + CPU saturé) :
        # 3 échecs sur 6 en SSE, 0 sur 12 en JSON. Écarté avant lui :
        # `stateless_http=False`, qui ne change rien (4 sur 12), parce que le
        # défaut est dans le chemin POST commun aux deux modes.
        #
        # Ce que ça retire : les notifications du serveur pendant un appel. Les
        # quatre outils servis rendent une chaîne et n'en émettent aucune.
        json_response=True,
        # Le chemin par défaut est /mcp : monté sous /api/mcp il donnerait
        # /api/mcp/mcp, et /api/mcp/ rendrait 404.
        streamable_http_path="/",
        # `allowed_hosts` veut une liste, jamais None (ValidationError) : vide
        # avec la protection coupée, c'est le réglage par défaut. Et
        # `allowed_origins` avec, parce que le même drapeau allume les deux
        # contrôles : sans origines déclarées, tout client qui envoie un
        # `Origin` repartait en 403.
        transport_security=TransportSecuritySettings(
            enable_dns_rebinding_protection=bool(hotes),
            allowed_hosts=hotes,
            allowed_origins=reglages.mcp_origins,
        ),
    )
    return mcp, GardeJeton(mcp.streamable_http_app())
