"""Ranger les transcripts du CLI sous la maison `.claude` de leur projet.

Appelée une fois au boot, idempotente. Avant la Phase 6 bis, tous les
transcripts vivaient à plat dans `<claude_home_root>/projects/`, donc dans un
volume partagé par toutes les sessions de tous les projets. La séparation par
projet n'a d'intérêt que si l'existant la rejoint.

Le rattachement se fait par le slug : le CLI nomme chaque dossier d'après le
chemin absolu du cwd (cf. `claude_home.slug_du_cwd`), et chaque session connue
en base porte son `worktree_path`. Ce qui ne se rattache pas reste où il est
et se retrouve dans les logs par son nom. Rien n'est supprimé, jamais : une
session dont le transcript n'a pas été rattaché perd son `resume` et redémarre
une conversation neuve, ce qui est déjà le comportement de
`SessionService.resume` et de `SupervisorService._ensure_session`.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import select

from app.core.config import get_settings
from app.core.logging import get_logger
from app.db.models.session import Session
from app.db.session import async_session_factory
from app.services.claude_home import slug_du_cwd, sous_chemin_de_maison

logger = get_logger(__name__)

_A_PLAT = "projects"


@dataclass(slots=True, frozen=True)
class Rapport:
    deplacees: int
    laissees: tuple[str, ...]


def ranger_les_dossiers(racine: Path, maison_par_slug: dict[str, str]) -> Rapport:
    """Déplace ce qu'on sait rattacher, laisse le reste, ne supprime rien.

    `racine` est le point de montage du volume chez le backend,
    `maison_par_slug` associe un nom de dossier de transcript au sous-chemin
    de la maison qui doit l'accueillir.
    """
    source = racine / _A_PLAT
    if not source.is_dir():
        return Rapport(deplacees=0, laissees=())

    deplacees = 0
    laissees: list[str] = []
    for dossier in sorted(p for p in source.iterdir() if p.is_dir()):
        maison = maison_par_slug.get(dossier.name)
        if maison is None:
            laissees.append(dossier.name)
            continue
        destination = racine / maison / ".claude" / _A_PLAT / dossier.name
        if destination.exists():
            # Déjà rangé, ou homonyme : on ne sait pas lequel est le bon, donc
            # on ne touche à aucun des deux.
            laissees.append(dossier.name)
            continue
        try:
            destination.parent.mkdir(parents=True, exist_ok=True)
            # `rename` et pas `shutil.move` : move retombe sur une copie suivie
            # d'un `rmtree` dès qu'`os.rename` lève une OSError, et pas
            # seulement entre systèmes de fichiers. Une copie interrompue
            # laisserait un transcript tronqué à destination, que le prochain
            # boot prendrait pour un dossier déjà rangé, et le `rmtree`
            # emporterait au passage ce qui aurait été écrit entre-temps.
            # `rename` réussit ou lève, jamais entre les deux.
            dossier.rename(destination)
        except OSError:
            # Un dossier qui résiste (droits, fichier ordinaire là où devrait
            # être la maison, systèmes de fichiers différents) ne doit pas
            # emporter tous les suivants : l'ordre est déterministe, donc le
            # même échouerait en premier à chaque boot.
            logger.warning(
                "maisons.migration.deplacement_impossible",
                dossier=dossier.name,
                destination=str(destination),
                exc_info=True,
            )
            laissees.append(dossier.name)
            continue
        deplacees += 1

    return Rapport(deplacees=deplacees, laissees=tuple(laissees))


async def migrer_les_maisons() -> Rapport:
    """Construit le rattachement depuis la base, puis range les dossiers."""
    async with async_session_factory() as db:
        lignes = (
            await db.execute(
                select(Session.project_id, Session.worktree_path).where(
                    Session.worktree_path.is_not(None)
                )
            )
        ).all()

    maison_par_slug: dict[str, str] = {}
    en_collision: dict[str, set[str]] = {}
    for project_id, worktree in lignes:
        if not worktree:
            continue
        try:
            slug = slug_du_cwd(worktree)
        except ValueError as exc:
            # Un chemin dont le CLI ne nomme pas le transcript comme nous
            # (trop long, ou hors du plan multilingue de base). On ne sait pas
            # rattacher celui-là, donc il reste où il est et on le dit. Une
            # seule session dans ce cas ne doit pas emporter la migration de
            # toutes les autres.
            logger.warning(
                "maisons.migration.slug_irreproductible",
                project_id=project_id,
                worktree=worktree,
                raison=str(exc),
            )
            continue
        maison = sous_chemin_de_maison(project_id)
        precedente = maison_par_slug.get(slug)
        if precedente is not None and precedente != maison:
            # Deux worktrees de projets différents que le CLI nomme pareil.
            # C'est sa propre règle de nommage qui entre en collision : ces deux
            # sessions partagent déjà un seul dossier de transcript aujourd'hui,
            # et la migration ne sait pas le démêler. Le ranger sous l'une des
            # deux maisons le rendrait lisible par un projet qui n'est pas le
            # sien, et c'est précisément ce que cette phase ferme. On ne choisit
            # pas : il reste où il est. Deux sessions d'un même projet ne sont
            # pas ambiguës (même maison), elles passent.
            en_collision.setdefault(slug, {precedente}).add(maison)
            continue
        maison_par_slug[slug] = maison

    for slug in en_collision:
        maison_par_slug.pop(slug, None)

    if en_collision:
        logger.warning(
            "maisons.migration.slugs_en_collision",
            maisons_par_slug={
                slug: sorted(maisons) for slug, maisons in sorted(en_collision.items())
            },
            consequence="transcripts laissés en place, rattachement ambigu",
        )

    racine = get_settings().claude_home_root
    # Déplacements de dossiers : du bloquant, donc dans un thread. C'est un
    # one-shot de boot, mais le boot sert aussi le premier appel HTTP.
    rapport = await asyncio.to_thread(ranger_les_dossiers, racine, maison_par_slug)

    if rapport.laissees:
        logger.warning(
            "maisons.migration.non_rattachees",
            dossiers=list(rapport.laissees),
            consequence=(
                "transcripts laissés en place : selon le cas, la session "
                "redémarrera une conversation neuve, ou son transcript est "
                "déjà rangé sous sa maison"
            ),
        )
    logger.info(
        "maisons.migration.terminee",
        deplacees=rapport.deplacees,
        laissees=len(rapport.laissees),
    )
    return rapport
