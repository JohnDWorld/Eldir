"""Routes /projects/{id}/toolchain - installation des outils du repo.

Le Mission Template déclare les commandes (`setup_commands`), ces routes les
exécutent à la demande et rendent compte de ce que ça a coûté en disque. Rien
ne s'installe sans un clic. Cf. `ToolchainService`.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from fastapi import APIRouter, status
from pydantic import Field

from app.core.deps import CurrentUserId, DbDep
from app.schemas.common import EldirModel
from app.services.mission_template_service import mission_template_service
from app.services.toolchain_service import toolchain_service

router = APIRouter(prefix="/projects/{project_id}", tags=["toolchain"])


class ToolchainStatusResponse(EldirModel):
    status: Literal["absent", "installing", "installed", "error"]
    size_bytes: int | None = None
    installed_at: datetime | None = None
    # Les commandes déclarées ont changé depuis l'installation.
    stale: bool = False
    # Commandes actuellement déclarées dans le Mission Template.
    commands: list[str] = Field(default_factory=list)
    log: str | None = None
    detail: str | None = None


async def _commands(db: DbDep, project_id: str, user_id: str) -> list[str]:
    template = await mission_template_service.get(db, project_id=project_id, user_id=user_id)
    return list(template.setup_commands or []) if template is not None else []


@router.get("/toolchain", response_model=ToolchainStatusResponse)
async def get_toolchain(
    project_id: str, user_id: CurrentUserId, db: DbDep
) -> ToolchainStatusResponse:
    """État du toolchain : absent, en cours d'installation, installé ou en échec."""
    commands = await _commands(db, project_id, user_id)
    state = toolchain_service.status(project_id, commands)
    return ToolchainStatusResponse(
        status=state.status,  # type: ignore[arg-type]
        size_bytes=state.size_bytes,
        installed_at=state.installed_at,
        stale=state.stale,
        commands=commands,
        log=state.log,
        detail=state.detail,
    )


@router.post("/toolchain/install", status_code=status.HTTP_202_ACCEPTED)
async def install_toolchain(project_id: str, user_id: CurrentUserId, db: DbDep) -> dict[str, str]:
    """Lance l'installation en tâche de fond et rend la main tout de suite.

    Un SDK complet peut prendre 10 minutes : le client suit l'avancement via
    `GET /toolchain` (statut + fin du log).
    """
    commands = await _commands(db, project_id, user_id)
    toolchain_service.start_install(project_id, commands)
    return {"status": "installing"}


@router.delete("/toolchain", status_code=status.HTTP_204_NO_CONTENT)
async def delete_toolchain(project_id: str, user_id: CurrentUserId, db: DbDep) -> None:
    """Supprime le toolchain du projet et rend le disque."""
    await _commands(db, project_id, user_id)  # contrôle d'accès au projet
    await toolchain_service.remove(project_id)
