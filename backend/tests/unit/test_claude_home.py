"""La règle de nommage des transcripts du CLI, relevée sur des dossiers réels.

Le CLI Claude range le transcript d'une conversation dans
`$HOME/.claude/projects/<slug>`, où `<slug>` dérive du chemin absolu du cwd.
Un slug mal reproduit ne casse rien : il perd tous les `resume`, sans bruit.
D'où ces cas : la règle a été relevée sur les dossiers réels d'une installation,
et chacun reproduit un des cinq points qu'elle fixe.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from app.services.claude_home import (
    MAISON_SUPERVISEUR,
    maison_du_projet,
    slug_du_cwd,
    sous_chemin_de_maison,
)

CAS_DE_LA_REGLE = [
    # la racine : le premier `/` donne un tiret de tête
    ("/home/eldir", "-home-eldir"),
    # le bord de fin n'est pas rogné non plus : un `/` final donne un tiret de queue
    ("/home/eldir/", "-home-eldir-"),
    # le point : `/.claude` donne deux tirets, un par caractère
    ("/home/eldir/.claude", "-home-eldir--claude"),
    # l'espace
    ("/srv/depots/Mon Projet/api", "-srv-depots-Mon-Projet-api"),
    # le souligné
    ("/srv/depots/mon_outil", "-srv-depots-mon-outil"),
    # le caractère accentué, et trois tirets consécutifs qui ne fusionnent pas
    ("/srv/depots/Projet à Rendre/api", "-srv-depots-Projet---Rendre-api"),
]


@pytest.mark.parametrize(("chemin", "attendu"), CAS_DE_LA_REGLE)
def test_le_slug_applique_la_regle(chemin: str, attendu: str) -> None:
    assert slug_du_cwd(chemin) == attendu


def test_le_slug_accepte_un_path() -> None:
    assert slug_du_cwd(Path("/home/eldir")) == "-home-eldir"


def test_un_slug_trop_long_est_refuse_bruyamment() -> None:
    """Au-delà de 200 caractères le CLI tronque et suffixe un hash.

    Rendre le slug tronqué sans son hash donnerait un nom qui ne désigne rien :
    le transcript ne serait pas retrouvé, et `resume` repartirait de zéro sans
    que personne ne voie passer d'erreur. On préfère l'erreur.
    """
    with pytest.raises(ValueError, match="trop long"):
        slug_du_cwd("/srv/depots/" + "a" * 200)


def test_un_slug_de_la_longueur_limite_passe() -> None:
    """La borne est inclusive, comme celle du CLI (`<= 200`)."""
    assert len(slug_du_cwd("/" + "a" * 199)) == 200


def test_un_chemin_hors_bmp_est_refuse() -> None:
    """Le CLI substitue par unité UTF-16, ce module par code point.

    Un emoji vaut deux unités chez lui et une seule ici : son slug porterait
    deux tirets où nous en portons un. Le nom ne désignerait rien, et le
    `resume` serait perdu sans bruit. On préfère l'erreur.
    """
    with pytest.raises(ValueError, match="plan multilingue"):
        slug_du_cwd("/srv/depots/\U0001f600/api")


def test_deux_sessions_du_meme_repo_ont_deux_slugs() -> None:
    """Le point qui sépare le repo de l'id de session devient un tiret.

    Layout de `WorktreeService` : `<user>/<repo_slug>.<session_id>`. Deux
    sessions du même projet ont donc deux transcripts distincts, et c'est ce
    qui rend une maison `.claude` par projet suffisante.
    """
    a = slug_du_cwd("/var/eldir/workspaces/u1/eldir.s1")
    b = slug_du_cwd("/var/eldir/workspaces/u1/eldir.s2")
    assert a == "-var-eldir-workspaces-u1-eldir-s1"
    assert a != b


def test_le_superviseur_a_une_maison_nommee() -> None:
    """Le superviseur n'a pas de projet : sa maison porte un nom réservé.

    Sans ça, `volume-subpath` recevrait une chaîne vide et monterait la racine
    du volume, c'est-à-dire les maisons de tous les projets.
    """
    assert sous_chemin_de_maison(None) == MAISON_SUPERVISEUR
    assert sous_chemin_de_maison("p1") == "p1"
    assert sous_chemin_de_maison("") == MAISON_SUPERVISEUR


def test_la_maison_vit_sous_la_racine_configuree(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CLAUDE_HOME_ROOT", "/tmp/maisons")
    from app.core.config import get_settings

    get_settings.cache_clear()
    try:
        assert maison_du_projet("p1") == Path("/tmp/maisons/p1")
    finally:
        get_settings.cache_clear()
