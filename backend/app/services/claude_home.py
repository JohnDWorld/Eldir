"""Où vit la maison `.claude` d'un projet, et comment le CLI nomme ses transcripts.

Une maison par **projet**, pas par session : deux sessions d'un même projet
partagent déjà leur worktree de base, leur clé et leur code, elles sont le
même domaine de confiance. Deux projets différents, en revanche, ne se voient
plus. Cf. la spec, section « La maison `.claude`, une par projet ».

Le slug est la seule chose ici qui ne soit pas un choix d'Eldir : c'est le CLI
Claude qui nomme ses dossiers de transcripts, et la règle est relevée sur les
dossiers réels d'une installation (cf. `tests/unit/test_claude_home.py`), pas devinée. Elle est
déterministe, et comme le worktree est monté au même chemin absolu dans le
conteneur que sur l'hôte, le slug reste identique après la bascule : un
transcript rattaché continue de se résoudre.
"""

from __future__ import annotations

import re
from pathlib import Path

from app.core.config import get_settings

# Tout ce qui n'est ni lettre ASCII, ni chiffre, ni tiret devient un tiret.
# Un tiret par caractère : les tirets consécutifs ne fusionnent pas, et les
# bords ne sont pas rognés.
# Le CLI substitue par unité UTF-16 (regex JS sans `u`), ce module par point de code.
# Les deux coïncident dans le BMP : hors BMP, `slug_du_cwd` refuse au lieu de deviner.
# Dans le BMP, un caractère vaut une unité : la borne LONGUEUR_MAX_SLUG est celle du CLI.
_HORS_SLUG = re.compile(r"[^A-Za-z0-9-]")

# Le CLI tronque un slug de plus de 200 caractères et lui colle un hash de son
# cru (relevé dans le bundle 2.1.316 : `n.length <= 200 ? n : n.slice(0, 200)
# + "-" + hash(e)`). On ne reproduit pas ce hash : on ne l'a pas vérifié, et la
# spec interdit de deviner le nommage. On refuse donc bruyamment.
LONGUEUR_MAX_SLUG = 200

# Le superviseur n'a pas de projet. Sans ce nom, son sous-chemin de maison
# serait vide et monterait la racine du volume, donc les maisons de tous les
# projets.
MAISON_SUPERVISEUR = "_superviseur"


def slug_du_cwd(cwd: str | Path) -> str:
    """Le nom du dossier de transcript du CLI.

    Lève ValueError hors du plan multilingue de base, et au-delà de 200 caractères.
    """
    texte = str(cwd)
    if any(ord(caractere) > 0xFFFF for caractere in texte):
        raise ValueError(
            "Chemin hors du plan multilingue de base, nommage du CLI non "
            f"reproductible : {cwd}. Le CLI substitue par unité UTF-16, donc il "
            "produirait deux tirets là où ce module en produit un, et son slug "
            "ne serait pas le nôtre."
        )
    slug = _HORS_SLUG.sub("-", texte)
    if len(slug) > LONGUEUR_MAX_SLUG:
        raise ValueError(
            f"Chemin trop long pour reproduire le nommage du CLI : {len(slug)} "
            f"caractères pour un maximum de {LONGUEUR_MAX_SLUG} ({cwd}). Au-delà, "
            "le CLI tronque et suffixe un hash que ce module ne reproduit pas, "
            "et le `resume` serait perdu sans bruit."
        )
    return slug


def sous_chemin_de_maison(project_id: str | None) -> str:
    """Le sous-chemin de la maison dans le volume, pour un projet ou le superviseur."""
    return project_id or MAISON_SUPERVISEUR


def maison_du_projet(project_id: str | None) -> Path:
    """La maison du projet telle que le **backend** la voit.

    Le conteneur de session la voit à `/eldir/maison`, par un montage de
    sous-chemin. Les deux chemins désignent le même dossier du même volume.
    """
    return get_settings().claude_home_root / sous_chemin_de_maison(project_id)
