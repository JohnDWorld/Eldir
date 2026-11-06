"""Le mode d'exécution des sessions, et les noms de volumes qu'il exige.

Le défaut du code est `conteneur`, le mode qui isole : un réglage oublié coûte
de la disponibilité, jamais l'isolement. `processus` ne s'obtient que par un
réglage explicite, et il ne protège rien : le CLI tourne dans le conteneur du
backend, qui voit le disque de tous les projets. La suite le demande (cf.
`tests/conftest.py`), parce qu'elle tourne sans démon Docker. Le mode d'une
installation servie se décide dans le compose de prod, où il est écrit en clair.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from app.core.config import Settings

COMPOSE_PROD = Path(__file__).parents[3] / "docker-compose.yml"


def test_le_mode_par_defaut_est_conteneur(monkeypatch: pytest.MonkeyPatch) -> None:
    """Le défaut doit isoler, même quand on a oublié de le régler.

    La suite exporte `SESSION_RUNTIME=processus` (cf. `tests/conftest.py`) et
    un `.env` local peut le fixer aussi : on écarte les deux, pour lire le
    défaut du code et rien d'autre.
    """
    monkeypatch.delenv("SESSION_RUNTIME", raising=False)
    assert Settings(_env_file=None).session_runtime == "conteneur"


def test_le_compose_de_prod_demande_le_mode_conteneur() -> None:
    """Le mode de prod s'écrit dans le compose, là où l'opérateur le lit.

    Le défaut du code porte déjà `conteneur` : la ligne ne change pas le
    comportement, elle rend le choix visible. Le test la garde contre une
    suppression silencieuse. L'ancrage compte : une ligne commentée
    (`# SESSION_RUNTIME: conteneur`) ne doit pas passer pour la vraie.
    """
    texte = COMPOSE_PROD.read_text(encoding="utf-8")
    assert re.search(r"^\s+SESSION_RUNTIME: conteneur$", texte, re.MULTILINE)


def test_les_noms_de_volumes_portent_le_prefixe_du_projet_compose() -> None:
    """Compose préfixe le nom d'un volume par celui du projet.

    Le compose de prod déclare `name: eldir` et un volume `eldir_workspaces` :
    le démon, lui, ne connaît que `eldir_eldir_workspaces`. Un `docker run`
    sur le nom non préfixé créerait un volume vide tout neuf, et la session
    démarrerait sur un worktree inexistant.
    """
    reglages = Settings()
    texte = COMPOSE_PROD.read_text(encoding="utf-8")
    assert re.search(r"^name: eldir$", texte, re.MULTILINE)
    for nom in (
        reglages.workspaces_volume,
        reglages.toolchains_volume,
        reglages.claude_home_volume,
        reglages.collectes_volume,
    ):
        assert nom.startswith("eldir_eldir_"), nom
        # Le volume existe bien sous son nom court dans le compose.
        assert f"\n  {nom.removeprefix('eldir_')}:\n" in texte
