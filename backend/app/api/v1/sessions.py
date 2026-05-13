"""Routes /sessions — CRUD + messages + stop."""

from __future__ import annotations

from fastapi import APIRouter, status

from app.core.deps import CurrentUserId, DbDep
from app.schemas.session import (
    CommitPushRequest,
    CommitPushResponse,
    GitStatusResponse,
    OpenPullRequestRequest,
    OpenPullRequestResponse,
    SessionCreate,
    SessionEventRead,
    SessionMessageInput,
    SessionRead,
)
from app.services.singletons import get_session_service

router = APIRouter(prefix="/sessions", tags=["sessions"])


@router.get("", response_model=list[SessionRead])
async def list_sessions(
    user_id: CurrentUserId, db: DbDep
) -> list[SessionRead]:
    sessions = await get_session_service().list_for_user(db, user_id)
    return [SessionRead.model_validate(s) for s in sessions]


@router.get("/{session_id}", response_model=SessionRead)
async def get_session(
    session_id: str, user_id: CurrentUserId, db: DbDep
) -> SessionRead:
    session = await get_session_service().get(db, session_id, user_id)
    return SessionRead.model_validate(session)


@router.post(
    "", response_model=SessionRead, status_code=status.HTTP_201_CREATED
)
async def create_session(
    payload: SessionCreate, user_id: CurrentUserId, db: DbDep
) -> SessionRead:
    service = get_session_service()
    session = await service.create_and_start(
        db,
        user_id=user_id,
        project_id=payload.project_id,
        system_prompt=payload.system_prompt,
        model=payload.model,
    )
    await db.commit()
    return SessionRead.model_validate(session)


@router.get(
    "/{session_id}/events", response_model=list[SessionEventRead]
)
async def list_session_events(
    session_id: str, user_id: CurrentUserId, db: DbDep
) -> list[SessionEventRead]:
    events = await get_session_service().list_events(db, session_id, user_id)
    return [SessionEventRead.model_validate(e) for e in events]


@router.post(
    "/{session_id}/messages", status_code=status.HTTP_202_ACCEPTED
)
async def send_message(
    session_id: str,
    payload: SessionMessageInput,
    user_id: CurrentUserId,
    db: DbDep,
) -> dict[str, str]:
    # Long-poll style : on bloque jusqu'à fin du tour (le client peut aussi
    # écouter via WS pour le streaming pendant ce temps).
    await get_session_service().send_message(
        db,
        user_id=user_id,
        session_id=session_id,
        content=payload.content,
    )
    await db.commit()
    return {"status": "accepted"}


@router.post(
    "/{session_id}/resume", response_model=SessionRead
)
async def resume_session(
    session_id: str, user_id: CurrentUserId, db: DbDep
) -> SessionRead:
    session = await get_session_service().resume(
        db, user_id=user_id, session_id=session_id
    )
    await db.commit()
    return SessionRead.model_validate(session)


@router.post(
    "/{session_id}/stop", status_code=status.HTTP_204_NO_CONTENT
)
async def stop_session(
    session_id: str, user_id: CurrentUserId, db: DbDep
) -> None:
    await get_session_service().stop(
        db, user_id=user_id, session_id=session_id
    )
    await db.commit()


# ── Git ops (chantier 5) ────────────────────────────────────────
@router.get("/{session_id}/git-status", response_model=GitStatusResponse)
async def git_status(
    session_id: str, user_id: CurrentUserId, db: DbDep
) -> GitStatusResponse:
    data = await get_session_service().git_status(
        db, user_id=user_id, session_id=session_id
    )
    return GitStatusResponse(**data)


@router.post(
    "/{session_id}/commit-push",
    response_model=CommitPushResponse,
)
async def commit_push(
    session_id: str,
    payload: CommitPushRequest,
    user_id: CurrentUserId,
    db: DbDep,
) -> CommitPushResponse:
    result = await get_session_service().commit_push(
        db,
        user_id=user_id,
        session_id=session_id,
        message=payload.message,
        push=payload.push,
    )
    await db.commit()
    return CommitPushResponse(
        branch=result.branch, sha=result.sha, pushed=result.pushed
    )


@router.post(
    "/{session_id}/pull-request",
    response_model=OpenPullRequestResponse,
)
async def open_pull_request(
    session_id: str,
    payload: OpenPullRequestRequest,
    user_id: CurrentUserId,
    db: DbDep,
) -> OpenPullRequestResponse:
    result = await get_session_service().open_pull_request(
        db,
        user_id=user_id,
        session_id=session_id,
        title=payload.title,
        body=payload.body,
        base=payload.base,
    )
    await db.commit()
    return OpenPullRequestResponse(
        pr_number=result.pr_number,
        pr_url=result.pr_url,
        head=result.head,
        base=result.base,
        title=result.title,
    )
