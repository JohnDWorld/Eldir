"""Routes /settings/git-credentials — CRUD PAT GitHub/Forgejo."""

from __future__ import annotations

from fastapi import APIRouter, status

from app.core.deps import CurrentUserId, DbDep
from app.schemas.git_credential import GitCredentialCreate, GitCredentialRead
from app.services.git_credential_service import git_credential_service

router = APIRouter(prefix="/settings/git-credentials", tags=["settings"])


@router.get("", response_model=list[GitCredentialRead])
async def list_credentials(
    user_id: CurrentUserId, db: DbDep
) -> list[GitCredentialRead]:
    creds = await git_credential_service.list_for_user(db, user_id)
    out: list[GitCredentialRead] = []
    for c in creds:
        out.append(
            GitCredentialRead(
                id=c.id,
                provider=c.provider,
                base_url=c.base_url,
                label=c.label,
                masked_token=await git_credential_service.reveal_masked(c),
                created_at=c.created_at,
                updated_at=c.updated_at,
            )
        )
    return out


@router.post(
    "",
    response_model=GitCredentialRead,
    status_code=status.HTTP_201_CREATED,
)
async def upsert_credential(
    payload: GitCredentialCreate,
    user_id: CurrentUserId,
    db: DbDep,
) -> GitCredentialRead:
    cred = await git_credential_service.upsert(db, user_id, payload)
    await db.commit()
    return GitCredentialRead(
        id=cred.id,
        provider=cred.provider,
        base_url=cred.base_url,
        label=cred.label,
        masked_token=await git_credential_service.reveal_masked(cred),
        created_at=cred.created_at,
        updated_at=cred.updated_at,
    )


@router.delete("/{credential_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_credential(
    credential_id: str, user_id: CurrentUserId, db: DbDep
) -> None:
    await git_credential_service.delete(db, credential_id, user_id)
    await db.commit()
