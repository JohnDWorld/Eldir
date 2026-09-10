"""Tests du CollectService : ce qu'on ramène, et surtout ce qu'on refuse.

Trois garanties valent un test, parce que la collecte lit des machines de
prod et écrit des fichiers que l'agent prendra pour argent comptant :

1. une commande qui échoue ne laisse **pas** de fichier derrière elle ;
2. un nom de fichier ne peut pas sortir du dossier de collecte ;
3. une collecte ne peut pas remplir le disque du serveur.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from app.core.config import get_settings
from app.services.collect_service import CollectService

PROJECT = "proj-1"


@pytest.fixture
def collectes_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    root = tmp_path / "collectes"
    monkeypatch.setenv("COLLECTES_ROOT", str(root))
    get_settings.cache_clear()
    yield root
    monkeypatch.delenv("COLLECTES_ROOT", raising=False)
    get_settings.cache_clear()


async def test_la_sortie_devient_un_fichier(collectes_root: Path) -> None:
    service = CollectService()
    assert service.env_for(PROJECT) == {}

    await service.run(PROJECT, [{"fichier": "config.yaml", "commande": "echo 'cle: valeur'"}])

    root = collectes_root / PROJECT
    assert (root / "config.yaml").read_text().strip() == "cle: valeur"
    assert "✓ config.yaml" in (root / "collecte.log").read_text()
    assert service.env_for(PROJECT) == {"ELDIR_COLLECTE": str(root)}


async def test_une_commande_en_echec_ne_laisse_pas_de_fichier(collectes_root: Path) -> None:
    """Un fichier tronqué qui ressemble à du code est pire qu'un fichier absent."""
    service = CollectService()
    await service.run(
        PROJECT,
        [{"fichier": "adapter.py", "commande": "echo 'def moitie():'; exit 7"}],
    )

    root = collectes_root / PROJECT
    assert not (root / "adapter.py").exists()
    log = (root / "collecte.log").read_text()
    assert "! adapter.py" in log and "code 7" in log


async def test_une_sortie_vide_ne_laisse_pas_de_fichier(collectes_root: Path) -> None:
    service = CollectService()
    await service.run(PROJECT, [{"fichier": "vide.txt", "commande": "true"}])

    root = collectes_root / PROJECT
    assert not (root / "vide.txt").exists()
    assert "n'a rien produit" in (root / "collecte.log").read_text()


async def test_un_nom_de_fichier_ne_peut_pas_sortir_du_dossier(collectes_root: Path) -> None:
    service = CollectService()
    await service.run(
        PROJECT,
        [{"fichier": "../evade.txt", "commande": "echo coucou"}],
    )

    assert not (collectes_root / "evade.txt").exists()
    assert "ignorée" in (collectes_root / PROJECT / "collecte.log").read_text()


async def test_une_collecte_geante_est_coupee(collectes_root: Path) -> None:
    """`ulimit -f` : un `docker logs` sans borne ne remplit pas le disque."""
    service = CollectService()
    get_settings.cache_clear()

    await service.run(
        PROJECT,
        [{"fichier": "gros.log", "commande": "head -c 20000000 /dev/zero"}],
    )

    root = collectes_root / PROJECT
    # Tué par la limite : pas de fichier, et l'échec est tracé.
    assert not (root / "gros.log").exists()
    assert "! gros.log" in (root / "collecte.log").read_text()


async def test_la_collecte_repart_propre(collectes_root: Path) -> None:
    """Un fichier que la commande ne produit plus ne doit pas rester à traîner.

    Sinon l'agent le lit comme s'il était à jour.
    """
    service = CollectService()
    await service.run(PROJECT, [{"fichier": "ancien.txt", "commande": "echo v1"}])
    await service.run(PROJECT, [{"fichier": "nouveau.txt", "commande": "echo v2"}])

    root = collectes_root / PROJECT
    assert not (root / "ancien.txt").exists()
    assert (root / "nouveau.txt").exists()


async def test_sans_declaration_on_ne_touche_a_rien(collectes_root: Path) -> None:
    service = CollectService()
    await service.run(PROJECT, None)
    assert not (collectes_root / PROJECT).exists()
    assert service.env_for(PROJECT) == {}
    assert service.env_for(None) == {}
