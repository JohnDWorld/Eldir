"""Ranger les transcripts sous la maison de leur projet, sans rien perdre.

Un transcript qu'on ne sait pas rattacher n'est pas supprimé : il reste où il
est, il est journalisé par son nom, et la session concernée redémarrera une
conversation neuve au lieu d'échouer. C'est le comportement voulu par la spec,
et c'est pour ça qu'il est testé.
"""

from __future__ import annotations

import errno
import os
from pathlib import Path
from types import SimpleNamespace

import pytest
from app.db.models.session import Session
from app.services import claude_home_migration
from app.services.claude_home import LONGUEUR_MAX_SLUG, slug_du_cwd
from app.services.claude_home_migration import (
    Rapport,
    migrer_les_maisons,
    ranger_les_dossiers,
)
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker


def _transcript(racine: Path, nom: str) -> Path:
    dossier = racine / "projects" / nom
    dossier.mkdir(parents=True)
    (dossier / "2026-01-01T00-00-00-000Z.jsonl").write_text("{}\n", encoding="utf-8")
    return dossier


def test_un_transcript_connu_part_sous_la_maison_de_son_projet(tmp_path: Path) -> None:
    _transcript(tmp_path, "-var-eldir-workspaces-u1-eldir-s1")

    rapport = ranger_les_dossiers(tmp_path, {"-var-eldir-workspaces-u1-eldir-s1": "projet-a"})

    assert rapport.deplacees == 1
    assert rapport.laissees == ()
    cible = tmp_path / "projet-a" / ".claude" / "projects" / "-var-eldir-workspaces-u1-eldir-s1"
    assert (cible / "2026-01-01T00-00-00-000Z.jsonl").exists()
    assert not (tmp_path / "projects" / "-var-eldir-workspaces-u1-eldir-s1").exists()


def test_un_transcript_inconnu_reste_en_place(tmp_path: Path) -> None:
    _transcript(tmp_path, "-un-chemin-que-plus-aucune-session-ne-porte")

    rapport = ranger_les_dossiers(tmp_path, {})

    assert rapport.deplacees == 0
    assert rapport.laissees == ("-un-chemin-que-plus-aucune-session-ne-porte",)
    assert (tmp_path / "projects" / "-un-chemin-que-plus-aucune-session-ne-porte").is_dir()


def test_la_migration_est_idempotente(tmp_path: Path) -> None:
    """Deux boots de suite, et le second ne fait rien.

    Le script est appelé à chaque démarrage : s'il n'était pas idempotent, il
    déplacerait des dossiers déjà rangés, ou écraserait un transcript en cours.
    """
    _transcript(tmp_path, "-var-eldir-workspaces-u1-eldir-s1")
    maison_par_slug = {"-var-eldir-workspaces-u1-eldir-s1": "projet-a"}

    premier = ranger_les_dossiers(tmp_path, maison_par_slug)
    second = ranger_les_dossiers(tmp_path, maison_par_slug)

    assert premier.deplacees == 1
    assert second.deplacees == 0
    assert second.laissees == ()


def test_une_collision_ne_detruit_rien(tmp_path: Path) -> None:
    """Un transcript déjà rangé sous la maison, et un homonyme resté à plat.

    On ne sait pas lequel est le bon, donc on ne touche ni l'un ni l'autre, et
    on le dit.
    """
    _transcript(tmp_path, "-var-eldir-workspaces-u1-eldir-s1")
    deja = tmp_path / "projet-a" / ".claude" / "projects" / "-var-eldir-workspaces-u1-eldir-s1"
    deja.mkdir(parents=True)
    (deja / "ancien.jsonl").write_text("{}\n", encoding="utf-8")

    rapport = ranger_les_dossiers(tmp_path, {"-var-eldir-workspaces-u1-eldir-s1": "projet-a"})

    assert rapport.deplacees == 0
    assert rapport.laissees == ("-var-eldir-workspaces-u1-eldir-s1",)
    assert (deja / "ancien.jsonl").exists()
    assert (tmp_path / "projects" / "-var-eldir-workspaces-u1-eldir-s1").is_dir()


def test_sans_dossier_projects_la_migration_ne_fait_rien(tmp_path: Path) -> None:
    """Installation neuve : rien à plat, rien à ranger, aucun échec."""
    rapport = ranger_les_dossiers(tmp_path, {"peu-importe": "projet-a"})

    assert rapport == Rapport(deplacees=0, laissees=())


def test_un_dossier_qui_resiste_n_emporte_pas_les_suivants(tmp_path: Path) -> None:
    """Un déplacement impossible est laissé en place, les autres continuent.

    L'ordre est trié donc déterministe : sans ça, le même dossier échouerait en
    premier à chaque boot, et tout ce qui le suit ne migrerait jamais.
    """
    _transcript(tmp_path, "-a-premier")
    _transcript(tmp_path, "-b-second")
    # Un fichier ordinaire là où devrait être la maison de `projet-a` : le
    # `mkdir` de sa destination ne peut pas aboutir.
    (tmp_path / "projet-a").write_text("pas un dossier\n", encoding="utf-8")

    rapport = ranger_les_dossiers(tmp_path, {"-a-premier": "projet-a", "-b-second": "projet-b"})

    assert rapport.deplacees == 1
    assert rapport.laissees == ("-a-premier",)
    assert (tmp_path / "projects" / "-a-premier" / "2026-01-01T00-00-00-000Z.jsonl").exists()
    assert (tmp_path / "projet-a").read_text(encoding="utf-8") == "pas un dossier\n"
    cible = tmp_path / "projet-b" / ".claude" / "projects" / "-b-second"
    assert (cible / "2026-01-01T00-00-00-000Z.jsonl").exists()


def test_un_deplacement_refuse_ne_retombe_pas_sur_une_copie(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Quand `rename` échoue, rien n'est copié et rien n'est supprimé.

    `shutil.move` retombe sur une copie suivie d'un `rmtree` dès qu'`os.rename`
    lève une `OSError` : un transcript tronqué à destination, ou un source
    effacé. Ici le rename échoue comme entre deux systèmes de fichiers, et le
    dossier doit rester entier là où il est.
    """
    dossier = _transcript(tmp_path, "-var-eldir-workspaces-u1-eldir-s1")

    def _refuse(*_args: object, **_kwargs: object) -> None:
        raise OSError(errno.EXDEV, "Invalid cross-device link")

    monkeypatch.setattr(os, "rename", _refuse)

    rapport = ranger_les_dossiers(tmp_path, {"-var-eldir-workspaces-u1-eldir-s1": "projet-a"})

    assert rapport.deplacees == 0
    assert rapport.laissees == ("-var-eldir-workspaces-u1-eldir-s1",)
    assert (dossier / "2026-01-01T00-00-00-000Z.jsonl").exists()
    destination = tmp_path / "projet-a" / ".claude" / "projects" / dossier.name
    assert not destination.exists()


async def test_un_chemin_irreproductible_n_emporte_pas_les_autres_sessions(
    tmp_path: Path,
    session_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Une session dont le CLI ne nomme pas le transcript comme nous reste en place.

    `slug_du_cwd` refuse un chemin trop long (le CLI y colle un hash que nous ne
    reproduisons pas). Si ce refus remontait de la construction du rattachement,
    la migration s'arrêterait là et le `try/except` du boot l'avalerait : les
    transcripts de toutes les autres sessions resteraient à plat, sans bruit.
    """
    ok_a = "/var/eldir/workspaces/u1/eldir-s1"
    ok_b = "/var/eldir/workspaces/u1/autre-s2"
    trop_long = "/var/eldir/workspaces/u1/" + "x" * LONGUEUR_MAX_SLUG
    with pytest.raises(ValueError):
        slug_du_cwd(trop_long)

    async with session_factory() as db:
        for projet, chemin in (("projet-a", ok_a), ("projet-b", ok_b), ("projet-c", trop_long)):
            db.add(
                Session(project_id=projet, user_id="u1", branch="claude/x", worktree_path=chemin)
            )
        await db.commit()

    _transcript(tmp_path, slug_du_cwd(ok_a))
    _transcript(tmp_path, slug_du_cwd(ok_b))
    # Le dossier que le CLI aurait créé pour la session trop longue : tronqué et
    # suffixé d'un hash. Son nom exact importe peu, il ne se rattache à rien.
    orphelin = "-var-eldir-workspaces-u1-" + "x" * 175 + "-hash"
    _transcript(tmp_path, orphelin)

    monkeypatch.setattr(claude_home_migration, "async_session_factory", session_factory)
    monkeypatch.setattr(
        claude_home_migration,
        "get_settings",
        lambda: SimpleNamespace(claude_home_root=tmp_path, session_runtime="conteneur"),
    )

    rapport = await migrer_les_maisons()

    assert rapport.deplacees == 2
    assert rapport.laissees == (orphelin,)
    for projet, chemin in (("projet-a", ok_a), ("projet-b", ok_b)):
        cible = tmp_path / projet / ".claude" / "projects" / slug_du_cwd(chemin)
        assert (cible / "2026-01-01T00-00-00-000Z.jsonl").exists()
    assert (tmp_path / "projects" / orphelin).is_dir()


async def test_deux_projets_qui_se_nomment_pareil_ne_sont_rattaches_a_aucun(
    tmp_path: Path,
    session_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Un slug que deux projets se partagent reste à plat, il ne choisit pas de camp.

    Ces deux chemins sont distincts et le CLI les nomme pareil. Ranger le
    transcript sous l'une des deux maisons le rendrait lisible par un projet qui
    n'est pas le sien : c'est la fuite que cette phase ferme, et la migration ne
    doit pas la recréer. Deux sessions d'un MÊME projet sur un même worktree ne
    sont en revanche pas ambiguës, et se rangent normalement.
    """
    chemin_a = "/srv/a/depot-b.s1"
    chemin_b = "/srv/a/depot/b.s1"
    voisin = "/srv/c/voisin.s1"
    assert slug_du_cwd(chemin_a) == slug_du_cwd(chemin_b)

    async with session_factory() as db:
        for projet, chemin in (
            ("projet-a", chemin_a),
            ("projet-b", chemin_b),
            ("projet-c", voisin),
            ("projet-c", voisin),
        ):
            db.add(
                Session(project_id=projet, user_id="u1", branch="claude/x", worktree_path=chemin)
            )
        await db.commit()

    en_collision = slug_du_cwd(chemin_a)
    _transcript(tmp_path, en_collision)
    _transcript(tmp_path, slug_du_cwd(voisin))

    monkeypatch.setattr(claude_home_migration, "async_session_factory", session_factory)
    monkeypatch.setattr(
        claude_home_migration,
        "get_settings",
        lambda: SimpleNamespace(claude_home_root=tmp_path, session_runtime="conteneur"),
    )

    rapport = await migrer_les_maisons()

    assert rapport.deplacees == 1
    assert rapport.laissees == (en_collision,)
    assert (tmp_path / "projects" / en_collision / "2026-01-01T00-00-00-000Z.jsonl").exists()
    for projet in ("projet-a", "projet-b"):
        assert not (tmp_path / projet).exists()
    cible = tmp_path / "projet-c" / ".claude" / "projects" / slug_du_cwd(voisin)
    assert (cible / "2026-01-01T00-00-00-000Z.jsonl").exists()


async def test_en_mode_processus_la_migration_ne_touche_a_rien(
    tmp_path: Path,
    session_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """En `processus`, le CLI lit `<claude_home_root>/projects` : on n'y touche pas.

    Le transcript ci-dessous SERAIT rattaché (la session est en base, son slug
    est celui du dossier) : c'est ce qui rend le test juste. Sans la garde, le
    boot le rangerait sous la maison de son projet, hors de portée du CLI qui
    le relit, et le `resume` de la session ne trouverait plus rien.

    Mutation qui le fait tomber (mesurée) : retirer le retour anticipé de
    `migrer_les_maisons`.
    """
    chemin = "/var/eldir/workspaces/u1/eldir.s1"
    async with session_factory() as db:
        db.add(
            Session(project_id="projet-a", user_id="u1", branch="claude/x", worktree_path=chemin)
        )
        await db.commit()
    transcript = _transcript(tmp_path, slug_du_cwd(chemin))

    monkeypatch.setattr(claude_home_migration, "async_session_factory", session_factory)
    monkeypatch.setattr(
        claude_home_migration,
        "get_settings",
        lambda: SimpleNamespace(claude_home_root=tmp_path, session_runtime="processus"),
    )

    rapport = await migrer_les_maisons()

    assert rapport == Rapport(deplacees=0, laissees=())
    assert (transcript / "2026-01-01T00-00-00-000Z.jsonl").exists()
    assert not (tmp_path / "projet-a").exists()
