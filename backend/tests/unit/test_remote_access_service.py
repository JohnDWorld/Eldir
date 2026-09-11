"""Tests du RemoteAccessService : la config SSH qu'Eldir s'écrit à lui-même.

Rien ici n'ouvre de connexion. Ce qui est vérifié, c'est ce qui casserait
silencieusement : un projet qui écrase le bloc d'un autre, une révocation qui
efface la config du voisin, une clé générée sans le commentaire qui permet de
la retrouver dans un `authorized_keys` distant.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from app.core.config import get_settings
from app.services.remote_access_service import RemoteAccessService, _alias_for

UN = "projet-un"
DEUX = "projet-deux"


@pytest.fixture
def ssh_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    home = tmp_path / "ssh"
    monkeypatch.setenv("SSH_HOME", str(home))
    get_settings.cache_clear()
    yield home
    monkeypatch.delenv("SSH_HOME", raising=False)
    get_settings.cache_clear()


def test_sans_configuration_il_n_y_a_pas_de_machine(ssh_home: Path) -> None:
    assert RemoteAccessService().status(UN).configured is False


def test_ecrire_puis_relire(ssh_home: Path) -> None:
    service = RemoteAccessService()
    service._write_block(UN, _alias_for("mon-repo"), "192.0.2.10", "deploy", 2222)

    state = service.status(UN)
    assert state.configured is True
    assert state.alias == "eldir-mon-repo"
    assert state.host == "192.0.2.10"
    assert state.user == "deploy"
    assert state.port == 2222


def test_deux_projets_cohabitent(ssh_home: Path) -> None:
    """Un projet ne doit pas écraser le bloc d'un autre."""
    service = RemoteAccessService()
    service._write_block(UN, "eldir-un", "192.0.2.10", "deploy", 22)
    service._write_block(DEUX, "eldir-deux", "192.0.2.11", "autre", 22)

    assert service.status(UN).host == "192.0.2.10"
    assert service.status(DEUX).host == "192.0.2.11"


def test_reconfigurer_remplace_au_lieu_d_empiler(ssh_home: Path) -> None:
    service = RemoteAccessService()
    service._write_block(UN, "eldir-un", "192.0.2.10", "deploy", 22)
    service._write_block(UN, "eldir-un", "192.0.2.99", "deploy", 22)

    assert service.status(UN).host == "192.0.2.99"
    assert (ssh_home / "config").read_text().count("Host eldir-un") == 1


def test_oublier_n_efface_que_le_bon_projet(ssh_home: Path) -> None:
    service = RemoteAccessService()
    service._write_block(UN, "eldir-un", "192.0.2.10", "deploy", 22)
    service._write_block(DEUX, "eldir-deux", "192.0.2.11", "autre", 22)

    service._forget(UN)

    assert service.status(UN).configured is False
    assert service.status(DEUX).host == "192.0.2.11"


async def test_la_cle_porte_l_id_du_projet(ssh_home: Path) -> None:
    """Le commentaire de la clé est ce qu'on cherchera pour la révoquer."""
    service = RemoteAccessService()
    await service._ensure_key(UN)

    cle = service.key_path(UN)
    assert cle.exists()
    assert oct(cle.stat().st_mode)[-3:] == "600"
    assert f"eldir-{UN}" in cle.with_suffix(".pub").read_text()


async def test_la_cle_n_est_generee_qu_une_fois(ssh_home: Path) -> None:
    service = RemoteAccessService()
    await service._ensure_key(UN)
    empreinte = service.key_path(UN).read_bytes()

    await service._ensure_key(UN)
    assert service.key_path(UN).read_bytes() == empreinte


async def test_oublier_supprime_la_paire_de_cles(ssh_home: Path) -> None:
    service = RemoteAccessService()
    await service._ensure_key(UN)
    service._forget(UN)

    assert not service.key_path(UN).exists()
    assert not service.key_path(UN).with_suffix(".pub").exists()


def test_l_alias_reste_utilisable_meme_avec_un_slug_bizarre() -> None:
    assert _alias_for("Mon Village Viking") == "eldir-mon-village-viking"
    assert _alias_for("--") == "eldir-projet"
