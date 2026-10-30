"""Un vrai serveur HTTP local, pour les tests du ping de fin de tour.

Un substitut de `httpx` ferait passer un test qui vérifie « ça n'a pas levé »
alors que rien n'est parti. Ici le POST traverse une vraie socket, et le
serveur garde ce qu'il a reçu : le test lit l'octet, pas l'intention.

Chaque chemin joue un abonné différent (seul le premier segment compte) :
    /ok       répond 204
    /json     répond 200 avec un petit JSON (modèles Ollama, réponse de génération)
    /erreur   répond 500
    /ancien   redirige vers /nouveau (302)
    /nouveau  répond 200 (ne doit jamais être joint)
    /silence  ne répond jamais
    /goutte   répond au compte-gouttes, un en-tête toutes les 50 ms
"""

from __future__ import annotations

import asyncio
import socket
import threading
import time
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from types import TracebackType
from typing import Any


@dataclass(frozen=True)
class RequeteRecue:
    methode: str
    chemin: str
    entetes: dict[str, str]
    corps: bytes


class ServeurAbonne:
    def __init__(self) -> None:
        self.requetes: list[RequeteRecue] = []
        self._arret = threading.Event()
        serveur = self

        class _Gestionnaire(BaseHTTPRequestHandler):
            def _traiter(self) -> None:
                taille = int(self.headers.get("Content-Length") or 0)
                serveur.requetes.append(
                    RequeteRecue(
                        methode=self.command,
                        chemin=self.path,
                        entetes={k.lower(): v for k, v in self.headers.items()},
                        corps=self.rfile.read(taille),
                    )
                )
                # Le premier segment choisit le rôle : un client qui ajoute son propre chemin
                # à l'URL de base (Ollama : `/api/tags`) joue le même abonné.
                chemin = "/" + self.path.split("?")[0].lstrip("/").split("/")[0]
                if chemin == "/silence":
                    serveur._arret.wait(30)
                elif chemin == "/goutte":
                    self.wfile.write(b"HTTP/1.1 200 OK\r\n")
                    while not serveur._arret.wait(0.05):
                        self.wfile.write(b"X-Goutte: 1\r\n")
                        self.wfile.flush()
                elif chemin == "/erreur":
                    self.send_response(500)
                    self.send_header("Content-Length", "0")
                    self.end_headers()
                elif chemin == "/json":
                    corps = b'{"models": [], "response": "ok"}'
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(corps)))
                    self.end_headers()
                    self.wfile.write(corps)
                elif chemin == "/ancien":
                    self.send_response(302)
                    self.send_header("Location", "/nouveau")
                    self.send_header("Content-Length", "0")
                    self.end_headers()
                else:
                    self.send_response(204 if chemin == "/ok" else 200)
                    self.send_header("Content-Length", "0")
                    self.end_headers()

            # Les noms sont imposés par BaseHTTPRequestHandler.
            def do_POST(self) -> None:
                self._traiter()

            def do_GET(self) -> None:
                self._traiter()

            def log_message(self, *_: object) -> None:
                return None

        self._http = ThreadingHTTPServer(("127.0.0.1", 0), _Gestionnaire)
        self._http.daemon_threads = True
        self._fil = threading.Thread(
            target=self._http.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True
        )

    @property
    def port(self) -> int:
        return int(self._http.server_address[1])

    def url(self, chemin: str) -> str:
        return f"http://127.0.0.1:{self.port}{chemin}"

    def __enter__(self) -> ServeurAbonne:
        self._fil.start()
        return self

    def __exit__(
        self,
        _type: type[BaseException] | None,
        _exc: BaseException | None,
        _tb: TracebackType | None,
    ) -> None:
        self.liberer()
        self._http.shutdown()
        self._http.server_close()
        self._fil.join(timeout=5)

    def liberer(self) -> None:
        """Laisse repartir les requêtes que le serveur retenait (/silence, /goutte)."""
        self._arret.set()

    async def attendre(self, nombre: int, delai: float = 5.0) -> None:
        """Bloque jusqu'à avoir reçu `nombre` requêtes (ou échoue au bout de `delai`)."""
        fin = time.monotonic() + delai
        while len(self.requetes) < nombre:
            if time.monotonic() > fin:
                raise AssertionError(f"{len(self.requetes)} requête(s) reçue(s) sur {nombre}")
            await asyncio.sleep(0.01)


class Journal:
    """Remplace un logger : ce qu'il a dit, et sous quel nom.

    Le journal réel écrit sur la sortie standard, que rien ne relit ; l'espion
    permet de prouver qu'un échec a bien été vu, donc que le ping est bien parti.
    """

    def __init__(self) -> None:
        self.appels: list[tuple[str, dict[str, Any]]] = []

    def warning(self, evenement: str, **champs: Any) -> None:
        self.appels.append((evenement, champs))

    info = exception = warning

    def evenements(self) -> list[str]:
        return [e for e, _ in self.appels]


def port_ferme() -> int:
    """Un port sur lequel plus rien n'écoute : la connexion y est refusée pour de bon."""
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])
