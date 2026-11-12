"""PublicationService - la fin du chemin : publier, merger, déployer.

L'agent d'une session code ; c'est Eldir qui publie, avec son propre code. Les
gardes sont donc mécaniques, pas des consignes de prompt :

- `open_pr` ne pousse que la branche de la session, jamais la base
  (`SessionService.open_pull_request` le refuse), et jamais en force ;
- `merge` refuse un projet que John n'a pas déclaré autonome, et une CI qui
  n'est pas verte ;
- `deploy` ne lance que la commande que John a déclarée pour le projet.

Une injection lue dans un dépôt peut donc, par le superviseur, ouvrir une PR
(John merge), et sur un projet autonome merger une CI verte et lancer la
commande déclarée. C'est ce que John accepte en cochant la case.
Cf. `docs/specs/2026-11-12-superviseur-autonome.md`.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Coroutine
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import get_settings
from app.core.exceptions import EldirError
from app.core.logging import get_logger
from app.db.models import MissionTemplate, Project
from app.db.models import Session as SessionRow
from app.services.git_credential_service import git_credential_service
from app.services.git_providers.base import (
    CHECKS_AUCUN,
    CHECKS_ROUGE,
    CHECKS_VERT,
    GitProviderInterface,
    PullRequestRef,
)
from app.services.project_service import project_service
from app.services.remote_access_service import remote_access_service
from app.services.session_manager import SessionManager
from app.services.session_service import SessionService

logger = get_logger(__name__)

# (user_id, message) : le chemin qui réveille le superviseur, celui des comptes rendus.
Prevenir = Callable[[str, str], Awaitable[None]]


# Une ligne peut peser des Mo (barre de progression) : les lignes ne suffisent pas à borner.
_SORTIE_MAX_CARS = 4000


@dataclass(slots=True)
class _Cible:
    """La PR qu'un merge vise, et la forge qui la porte."""

    session_id: str
    repo: str
    numero: int
    forge: GitProviderInterface
    # Le commit dont la CI a été lue au moment du merge ; vide tant que la PR n'est pas lue.
    head_sha: str = ""


class PublicationService:
    def __init__(
        self,
        *,
        manager: SessionManager,
        sessions: SessionService,
        session_factory: async_sessionmaker[AsyncSession],
        prevenir: Prevenir,
    ) -> None:
        self._manager = manager
        self._sessions = sessions
        self._factory = session_factory
        self._prevenir = prevenir
        # Une surveillance de CI par session, un déploiement par projet.
        # ponytail: en mémoire, perdus au redémarrage du backend (rien n'est
        # mergé, personne n'est prévenu) ; une file persistée si ça gêne.
        self._surveillances: set[str] = set()
        self._deploiements: set[str] = set()
        self._tasks: set[asyncio.Task[None]] = set()

    # ── open_pr ──────────────────────────────────────────────────
    async def open_pr(self, user_id: str, *, session_id: str, titre: str, description: str) -> str:
        session_id = session_id.strip()
        titre = titre.strip()
        if not session_id or not titre:
            return "Erreur : session_id et titre sont obligatoires."
        if self._manager.tour_en_cours(session_id):
            return (
                "Refusé : cette session a un tour en cours. Attends son compte rendu, "
                "puis publie : on ne publie pas un travail à moitié écrit."
            )
        try:
            async with self._factory() as db:
                pr = await self._sessions.open_pull_request(
                    db,
                    user_id=user_id,
                    session_id=session_id,
                    title=titre,
                    body=description.strip() or None,
                )
                await db.commit()
        except EldirError as exc:
            return f"Erreur : {exc.message}"
        logger.info("publication.open_pr", session_id=session_id, pr_number=pr.pr_number)
        return f"PR nº {pr.pr_number} à jour : {pr.pr_url} ({pr.head} vers {pr.base})."

    # ── merge ────────────────────────────────────────────────────
    async def merge(self, user_id: str, *, session_id: str) -> str:  # noqa: PLR0911
        session_id = session_id.strip()
        if not session_id:
            return "Erreur : session_id est obligatoire."
        if session_id in self._surveillances:
            return (
                "Une surveillance de CI est déjà en cours pour cette session : "
                "je merge dès qu'elle passe."
            )
        try:
            cible = await self._cible(user_id, session_id)
            if isinstance(cible, str):
                return cible
            pr = await cible.forge.get_pr(cible.repo, cible.numero)
            if pr.state != "open":
                return f"Refusé : la PR nº {cible.numero} est {_etat_lisible(pr)}."
            cible.head_sha = pr.head_sha
            rapport = await cible.forge.checks(cible.repo, pr.head_sha)
            if rapport.etat == CHECKS_VERT:
                return await self._merger(cible)
        except EldirError as exc:
            return f"Erreur : {exc.message}"
        if rapport.etat == CHECKS_ROUGE:
            return (
                f"Refusé : la CI est rouge ({', '.join(rapport.en_echec)}). Fais corriger la "
                "session, publie avec open_pr, puis redemande le merge."
            )
        self._surveillances.add(session_id)
        self._spawn(self._surveiller(user_id, cible))
        if rapport.etat == CHECKS_AUCUN:
            delai = get_settings().merge_no_checks_grace_s
            return (
                "Aucun check sur cette PR pour l'instant : la CI démarre peut-être. "
                f"Je relis pendant {delai} s : je merge dès qu'elle passe au vert, ou si "
                "elle n'a toujours aucun check. Je te préviens."
            )
        return "CI en cours : je merge dès qu'elle passe au vert, et je te préviens."

    async def _cible(self, user_id: str, session_id: str) -> _Cible | str:
        """La PR de la session, ou la raison du refus. Les refus passent avant la forge."""
        async with self._factory() as db:
            session = await self._sessions.get(db, session_id, user_id)
            if session.project_id is None:
                return "Refusé : cette session n'a pas de projet."
            project = await project_service.get(db, session.project_id, user_id)
            if not project.autonomous:
                return (
                    f"Refusé : {project.name} n'est pas autonome. John merge lui-même "
                    "ses PR : donne-lui le lien."
                )
            if await _source_externe(db, project.id):
                return _refus_source_externe(project.name, "merge")
            if session.pr_number is None:
                return "Refusé : cette session n'a pas de PR. Publie d'abord avec open_pr."
            _, forge = await git_credential_service.get_active_client(
                db, user_id, project.provider, project.id
            )
            return _Cible(
                session_id=session_id,
                repo=project.repo_full_name,
                numero=session.pr_number,
                forge=forge,
            )

    async def _merger(self, cible: _Cible) -> str:
        await cible.forge.merge_pr(cible.repo, cible.numero)
        logger.info("publication.merge", session_id=cible.session_id, pr_number=cible.numero)
        return f"PR nº {cible.numero} mergée. Déploie si le changement le demande."

    async def _surveiller(self, user_id: str, cible: _Cible) -> None:
        """Relit la CI jusqu'au vert, au rouge ou au délai, puis prévient le superviseur."""
        reglages = get_settings()
        horloge = asyncio.get_running_loop()
        debut = horloge.time()
        try:
            message = await self._attendre_la_ci(cible, reglages, horloge, debut)
        except Exception as exc:
            # Réseau, base : sans ce filet le superviseur ne saurait jamais que le merge a cessé.
            logger.exception("publication.surveillance.failed", session_id=cible.session_id)
            message = (
                f"Merge de la PR nº {cible.numero} abandonné : erreur inattendue "
                f"({type(exc).__name__}). Redemande le merge."
            )
        finally:
            self._surveillances.discard(cible.session_id)
        await self._prevenir(user_id, f"[merge de la session {cible.session_id}] {message}")

    async def _attendre_la_ci(  # noqa: PLR0911
        self, cible: _Cible, reglages: Any, horloge: asyncio.AbstractEventLoop, debut: float
    ) -> str:
        numero = cible.numero
        while True:
            await asyncio.sleep(reglages.merge_watch_interval_s)
            ecoule = horloge.time() - debut
            try:
                async with self._factory() as db:
                    ligne = await db.get(SessionRow, cible.session_id)
                    if ligne is None:
                        return f"PR nº {numero} non mergée : la session a été supprimée."
                    # John a pu décocher la case pendant l'attente : la case
                    # vaut au moment du merge, pas à celui de la demande.
                    projet = await db.get(Project, ligne.project_id)
                    if projet is None or not projet.autonomous:
                        return f"PR nº {numero} non mergée : le projet n'est plus autonome."
                pr = await cible.forge.get_pr(cible.repo, numero)
                if pr.state != "open":
                    return f"PR nº {numero} non mergée : elle est {_etat_lisible(pr)}."
                if pr.head_sha != cible.head_sha:
                    return (
                        f"PR nº {numero} non mergée : un nouveau commit a été poussé pendant "
                        "l'attente. Redemande le merge pour qu'Eldir surveille sa CI."
                    )
                rapport = await cible.forge.checks(cible.repo, pr.head_sha)
                if rapport.etat == CHECKS_VERT:
                    return await self._merger(cible)
                if rapport.etat == CHECKS_ROUGE:
                    return (
                        f"PR nº {numero} non mergée : la CI est rouge "
                        f"({', '.join(rapport.en_echec)})."
                    )
                if rapport.etat == CHECKS_AUCUN and ecoule >= reglages.merge_no_checks_grace_s:
                    fait = await self._merger(cible)
                    return (
                        f"Aucun check après {reglages.merge_no_checks_grace_s} s : "
                        f"pas de CI sur ce projet. {fait}"
                    )
            except EldirError as exc:
                return f"Merge de la PR nº {numero} abandonné : {exc.message}"
            if ecoule >= reglages.merge_watch_timeout_s:
                return (
                    f"PR nº {numero} non mergée : la CI n'a pas fini en "
                    f"{reglages.merge_watch_timeout_s // 60} min. Redemande le merge plus tard."
                )

    # ── deploy ───────────────────────────────────────────────────
    async def deploy(self, user_id: str, *, project_id: str) -> str:  # noqa: PLR0911
        project_id = project_id.strip()
        if not project_id:
            return "Erreur : project_id est obligatoire."
        try:
            async with self._factory() as db:
                project = await project_service.get(db, project_id, user_id)
                externe = await _source_externe(db, project.id)
        except EldirError as exc:
            return f"Erreur : {exc.message}"
        nom, commande = project.name, project.deploy_command
        if not project.autonomous:
            return f"Refusé : {nom} n'est pas autonome. Le déploiement reste à John."
        if externe:
            return _refus_source_externe(nom, "déploie")
        if not commande:
            return (
                f"{nom} n'a pas de commande de déploiement : "
                "la forge déploie au merge, rien à lancer."
            )
        alias = remote_access_service.status(project_id).alias
        if alias is None:
            return (
                f"Refusé : {nom} a une commande de déploiement mais pas d'accès distant. "
                "John le configure dans la page du projet, section « Machine du projet »."
            )
        if project_id in self._deploiements:
            return f"Un déploiement de {nom} est déjà en cours."
        self._deploiements.add(project_id)
        self._spawn(self._deployer(user_id, project_id, nom, alias, commande))
        return f"Déploiement de {nom} lancé. Le résultat t'arrive par message quand il a fini."

    async def _deployer(
        self, user_id: str, project_id: str, nom: str, alias: str, commande: str
    ) -> None:
        reglages = get_settings()
        try:
            code, sortie = await remote_access_service.executer(
                alias, commande, timeout_s=reglages.deploy_timeout_s
            )
        except Exception as exc:
            # Même filet que la surveillance : le superviseur doit savoir qu'il a cessé.
            logger.exception("publication.deploy.failed", project_id=project_id)
            await self._prevenir(
                user_id,
                f"[déploiement de {nom}] abandonné : erreur inattendue ({type(exc).__name__}).",
            )
            return
        finally:
            self._deploiements.discard(project_id)
        fin = "\n".join(sortie.strip().splitlines()[-reglages.deploy_output_lines :])[
            -_SORTIE_MAX_CARS:
        ]
        logger.info("publication.deploy", project_id=project_id, code=code)
        if code is None:
            etat = (
                f"ssh coupé après {reglages.deploy_timeout_s // 60} min : la commande peut "
                "encore tourner sur la machine, vérifie avant de relancer"
            )
        elif code == 0:
            etat = "réussi"
        else:
            etat = f"en échec (code {code})"
        await self._prevenir(
            user_id,
            f"[déploiement de {nom}] {etat}. Fin de la sortie :\n{fin or '(aucune sortie)'}",
        )

    def _spawn(self, coro: Coroutine[Any, Any, None]) -> None:
        tache = asyncio.create_task(self._sans_lever(coro), name=coro.__qualname__)
        self._tasks.add(tache)
        tache.add_done_callback(self._tasks.discard)
        # Annulée avant son premier tour, la coroutine n'est jamais attendue : on la ferme.
        tache.add_done_callback(lambda _: coro.close())

    async def _sans_lever(self, coro: Coroutine[Any, Any, None]) -> None:
        try:
            await coro
        except Exception:
            logger.exception("publication.tache.failed", tache=coro.__qualname__)


async def _source_externe(db: AsyncSession, project_id: str) -> bool:
    """Un projet alimenté par des tickets non fiables : John seul merge et déploie."""
    return bool(
        await db.scalar(
            select(MissionTemplate.source_externe).where(MissionTemplate.project_id == project_id)
        )
    )


def _refus_source_externe(nom: str, verbe: str) -> str:
    return f"Refusé : {nom} est alimenté par une source externe, John {verbe} lui-même."


def _etat_lisible(pr: PullRequestRef) -> str:
    return "déjà mergée" if pr.state == "merged" else "fermée"
