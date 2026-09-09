"""Tests du ToolchainService : installation, état, PATH des sessions."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
from app.core.config import get_settings
from app.core.exceptions import EldirError
from app.services.toolchain_service import ToolchainService

PROJECT = "proj-1"


@pytest.fixture
def toolchains_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_path / "toolchains"
    monkeypatch.setenv("TOOLCHAINS_ROOT", str(root))
    get_settings.cache_clear()
    yield root
    monkeypatch.delenv("TOOLCHAINS_ROOT", raising=False)
    get_settings.cache_clear()


async def _wait_done(service: ToolchainService, project_id: str) -> None:
    for _ in range(100):
        await asyncio.sleep(0.05)
        if project_id not in service._running:
            return
    raise AssertionError("installation jamais terminée")


async def test_absent_puis_installe(toolchains_root: Path) -> None:
    service = ToolchainService()
    assert service.status(PROJECT, []).status == "absent"
    # Rien d'installé : aucune variable, l'agent ne trouvera pas l'outil et le
    # signalera, ce qui est le comportement voulu.
    assert service.env_for(PROJECT) == {}

    service.start_install(PROJECT, ["mkdir -p bin", "printf '#!/bin/sh\\n' > bin/faux-outil"])
    await _wait_done(service, PROJECT)

    state = service.status(PROJECT, ["mkdir -p bin", "printf '#!/bin/sh\\n' > bin/faux-outil"])
    assert state.status == "installed"
    assert state.size_bytes is not None and state.size_bytes > 0
    assert state.installed_at is not None
    assert state.stale is False

    env = service.env_for(PROJECT)
    assert env["ELDIR_TOOLCHAIN"] == str(toolchains_root / PROJECT)
    assert env["PATH"].startswith(str(toolchains_root / PROJECT / "bin"))


async def test_commande_en_echec_remonte_dans_l_etat(toolchains_root: Path) -> None:
    service = ToolchainService()
    service.start_install(PROJECT, ["exit 3"])
    await _wait_done(service, PROJECT)

    state = service.status(PROJECT, ["exit 3"])
    assert state.status == "error"
    assert state.detail is not None and "exit 3" in state.detail
    assert state.log is not None and "$ exit 3" in state.log


async def test_commandes_modifiees_marquent_le_toolchain_perime(
    toolchains_root: Path,
) -> None:
    service = ToolchainService()
    service.start_install(PROJECT, ["true"])
    await _wait_done(service, PROJECT)

    assert service.status(PROJECT, ["true"]).stale is False
    assert service.status(PROJECT, ["true", "echo nouveau"]).stale is True


async def test_sans_commandes_declarees_on_refuse(toolchains_root: Path) -> None:
    service = ToolchainService()
    with pytest.raises(EldirError):
        service.start_install(PROJECT, [])


async def test_remove_rend_le_disque(toolchains_root: Path) -> None:
    service = ToolchainService()
    service.start_install(PROJECT, ["true"])
    await _wait_done(service, PROJECT)
    assert (toolchains_root / PROJECT).exists()

    await service.remove(PROJECT)
    assert not (toolchains_root / PROJECT).exists()
    assert service.status(PROJECT, ["true"]).status == "absent"


async def test_pipeline_casse_fait_echouer_l_installation(toolchains_root: Path) -> None:
    """`curl … | bash` sur une URL morte ne doit pas passer pour un succès.

    Sans `pipefail`, le code de sortie d'un pipeline est celui du dernier
    maillon : l'installation continuait sur un dossier vide et n'échouait
    qu'à la commande de vérification, quand il y en avait une.
    """
    service = ToolchainService()
    service.start_install(PROJECT, ["false | cat"])
    await _wait_done(service, PROJECT)

    assert service.status(PROJECT, ["false | cat"]).status == "error"
