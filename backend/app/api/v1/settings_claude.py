"""Routes /settings/claude-credentials — CRUD post-bootstrap."""

from __future__ import annotations

from fastapi import APIRouter, status

from app.core.deps import CurrentUserId, DbDep
from app.schemas.claude_credential import (
    ClaudeCredentialCreate,
    ClaudeCredentialRead,
)
from app.services.claude_credential_service import claude_credential_service

router = APIRouter(prefix="/settings/claude-credentials", tags=["settings"])


def _to_read(cred, masked: str) -> ClaudeCredentialRead:  # type: ignore[no-untyped-def]
    return ClaudeCredentialRead(
        id=cred.id,
        kind=cred.kind,
        label=cred.label,
        is_active=cred.is_active,
        last_validated_at=cred.last_validated_at,
        masked_value=masked,
        created_at=cred.created_at,
        updated_at=cred.updated_at,
    )


@router.get("", response_model=list[ClaudeCredentialRead])
async def list_credentials(
    user_id: CurrentUserId, db: DbDep
) -> list[ClaudeCredentialRead]:
    creds = await claude_credential_service.list_for_user(db, user_id)
    items: list[ClaudeCredentialRead] = []
    for cred in creds:
        masked = await claude_credential_service.reveal_masked(cred)
        items.append(_to_read(cred, masked))
    return items


@router.post(
    "",
    response_model=ClaudeCredentialRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_credential(
    payload: ClaudeCredentialCreate,
    user_id: CurrentUserId,
    db: DbDep,
) -> ClaudeCredentialRead:
    cred = await claude_credential_service.create(db, user_id, payload)
    await db.commit()
    masked = await claude_credential_service.reveal_masked(cred)
    return _to_read(cred, masked)


@router.delete(
    "/{credential_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_credential(
    credential_id: str,
    user_id: CurrentUserId,
    db: DbDep,
) -> None:
    await claude_credential_service.delete(db, credential_id, user_id)
    await db.commit()
