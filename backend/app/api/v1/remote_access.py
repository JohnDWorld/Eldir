"""Routes /projects/{id}/remote - la machine où tourne le projet.

Un bouton, trois issues possibles : ça passe déjà en clé, il faut le mot de
passe une fois, ou la machine refuse. Le mot de passe ne traverse que cette
requête : il n'est ni stocké, ni journalisé, ni renvoyé.
"""

from __future__ import annotations

from fastapi import APIRouter, status
from pydantic import Field, SecretStr

from app.core.deps import CurrentUserId, DbDep
from app.schemas.common import EldirModel
from app.services.mission_template_service import mission_template_service
from app.services.project_service import project_service
from app.services.remote_access_service import RemoteStatus, remote_access_service

router = APIRouter(prefix="/projects/{project_id}/remote", tags=["remote"])


class RemoteConnectInput(EldirModel):
    host: str = Field(min_length=1, max_length=255)
    user: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9._-]+$")
    port: int = Field(default=22, ge=1, le=65_535)
    # `SecretStr` : ne peut pas fuiter dans un log ou une trace par un repr
    # accidentel. Utilisé une fois pour déposer la clé, puis oublié.
    password: SecretStr | None = Field(default=None, max_length=256)


class RemoteStatusRead(EldirModel):
    configured: bool
    alias: str | None = None
    host: str | None = None
    user: str | None = None
    port: int = 22
    connected: bool | None = None
    detail: str | None = None


def _serialize(state: RemoteStatus) -> RemoteStatusRead:
    return RemoteStatusRead(
        configured=state.configured,
        alias=state.alias,
        host=state.host,
        user=state.user,
        port=state.port,
        connected=state.connected,
        detail=state.detail,
    )


@router.get("", response_model=RemoteStatusRead)
async def remote_status(project_id: str, user_id: CurrentUserId, db: DbDep) -> RemoteStatusRead:
    """Ce que dit la configuration, sans ouvrir de connexion."""
    await project_service.get(db, project_id, user_id)
    return _serialize(remote_access_service.status(project_id))


@router.post("", response_model=RemoteStatusRead)
async def remote_connect(
    project_id: str, payload: RemoteConnectInput, user_id: CurrentUserId, db: DbDep
) -> RemoteStatusRead:
    """Génère la clé si besoin, la dépose, et vérifie la connexion.

    Sans mot de passe, on tente d'abord la clé : si elle passe déjà, rien
    d'autre n'est nécessaire et on n'a jamais eu à demander de secret.
    """
    project = await project_service.get(db, project_id, user_id)
    state = await remote_access_service.connect(
        project_id=project_id,
        slug=project.slug,
        host=payload.host,
        user=payload.user,
        port=payload.port,
        password=payload.password.get_secret_value() if payload.password else None,
    )
    if state.connected and state.alias:
        # L'alias devient celui du Mission Template : c'est lui que les
        # sessions du projet auront le droit d'atteindre.
        await mission_template_service.set_remote_host(
            db, project_id=project_id, user_id=user_id, remote_host=state.alias
        )
        await db.commit()
    return _serialize(state)


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
async def remote_disconnect(project_id: str, user_id: CurrentUserId, db: DbDep) -> None:
    """Retire la clé de la machine distante, puis la configuration locale."""
    await project_service.get(db, project_id, user_id)
    await remote_access_service.revoke(project_id)
    await mission_template_service.set_remote_host(
        db, project_id=project_id, user_id=user_id, remote_host=None
    )
    await db.commit()
