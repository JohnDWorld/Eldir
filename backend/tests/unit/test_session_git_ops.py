"""Tests des opérations Git du SessionService (chantier 5).

On instancie un VRAI repo git local (tmp_path) pour valider commit/push.
Le push se fait sur un faux remote local (file:// bare repo).
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock

import pytest
from app.core.exceptions import AuthenticationError, WorkspaceError
from app.db.models import Project, Session, User
from app.schemas.git_credential import GitCredentialCreate
from app.services import git_credential_service as cred_module
from app.services.git_credential_service import git_credential_service
from app.services.git_providers.base import PullRequestRef
from app.services.git_providers.forgejo import ForgejoProvider
from app.services.session_manager import SessionManager
from app.services.session_service import SessionService
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker


async def _run(cmd: list[str], cwd: Path) -> str:
    process = await asyncio.create_subprocess_exec(
        *cmd,
        cwd=str(cwd),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await process.communicate()
    if process.returncode != 0:
        raise RuntimeError(stderr.decode())
    return stdout.decode().strip()


@pytest.fixture
async def admin(db_session: AsyncSession) -> User:
    user = User(
        email="admin@example.com",
        hashed_password="x",
        display_name="Admin",
        is_active=True,
        is_admin=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.fixture
async def repo_pair(tmp_path: Path) -> tuple[Path, Path]:
    """Crée un bare repo `remote.git` + un clone local avec branche `feat/x`."""
    remote = tmp_path / "remote.git"
    remote.mkdir()
    await _run(["git", "init", "--bare", "--initial-branch=main"], cwd=remote)

    work = tmp_path / "work"
    await _run(["git", "clone", str(remote), str(work)], cwd=tmp_path)
    await _run(["git", "config", "user.email", "x@y"], cwd=work)
    await _run(["git", "config", "user.name", "x"], cwd=work)
    # Premier commit pour avoir un HEAD sur main.
    (work / "README.md").write_text("hello")
    await _run(["git", "add", "-A"], cwd=work)
    await _run(["git", "commit", "-m", "init"], cwd=work)
    await _run(["git", "push", "-u", "origin", "main"], cwd=work)
    # Crée une branche de session
    await _run(["git", "checkout", "-b", "feat/eldir"], cwd=work)
    return remote, work


@pytest.fixture
async def project_session(
    db_session: AsyncSession, admin: User, repo_pair: tuple[Path, Path]
) -> tuple[Project, Session]:
    _, work = repo_pair
    project = Project(
        user_id=admin.id,
        name="repo",
        slug="repo",
        provider="github",
        repo_full_name="owner/repo",
        default_branch="main",
        workspace_path=str(work),
    )
    db_session.add(project)
    await db_session.flush()
    session = Session(
        project_id=project.id,
        user_id=admin.id,
        branch="feat/eldir",
        worktree_path=str(work),
        state="idle",
    )
    db_session.add(session)
    await db_session.commit()
    await db_session.refresh(session)
    return project, session


@pytest.fixture
def service(
    session_factory: async_sessionmaker[AsyncSession],
) -> SessionService:
    bus = AsyncMock()
    manager = SessionManager(event_bus=bus)
    svc = SessionService(manager=manager)
    svc.attach_session_factory(session_factory)
    return svc


# ── tests ────────────────────────────────────────────────────────


async def test_git_status_clean(
    db_session: AsyncSession,
    admin: User,
    project_session: tuple[Project, Session],
    service: SessionService,
) -> None:
    _, session = project_session
    status = await service.git_status(db_session, user_id=admin.id, session_id=session.id)
    assert status["has_changes"] is False
    assert status["branch"] == "feat/eldir"


async def test_git_status_with_changes(
    db_session: AsyncSession,
    admin: User,
    project_session: tuple[Project, Session],
    service: SessionService,
) -> None:
    _, session = project_session
    Path(session.worktree_path).joinpath("new.txt").write_text("hi")  # type: ignore[arg-type]
    status = await service.git_status(db_session, user_id=admin.id, session_id=session.id)
    assert status["has_changes"] is True
    assert status["untracked"] == 1


async def test_commit_without_push(
    db_session: AsyncSession,
    admin: User,
    project_session: tuple[Project, Session],
    service: SessionService,
) -> None:
    _, session = project_session
    Path(session.worktree_path).joinpath("foo.py").write_text("x = 1")  # type: ignore[arg-type]

    result = await service.commit_push(
        db_session,
        user_id=admin.id,
        session_id=session.id,
        message="add foo",
        push=False,
    )
    assert result.pushed is False
    assert len(result.sha) >= 7
    assert result.branch == "feat/eldir"


async def test_commit_push_requires_credential(
    db_session: AsyncSession,
    admin: User,
    project_session: tuple[Project, Session],
    service: SessionService,
) -> None:
    _, session = project_session
    Path(session.worktree_path).joinpath("bar.py").write_text("y = 2")  # type: ignore[arg-type]

    with pytest.raises(AuthenticationError):
        await service.commit_push(
            db_session,
            user_id=admin.id,
            session_id=session.id,
            message="add bar",
            push=True,
        )


async def test_commit_push_happy_path(
    db_session: AsyncSession,
    admin: User,
    project_session: tuple[Project, Session],
    service: SessionService,
    repo_pair: tuple[Path, Path],
) -> None:
    _, session = project_session
    # PAT (le push local n'en a pas besoin mais le code l'exige).
    await git_credential_service.upsert(
        db_session,
        admin.id,
        GitCredentialCreate(provider="github", token="ghp_local_test"),
    )
    await db_session.commit()

    Path(session.worktree_path).joinpath("baz.py").write_text("z = 3")  # type: ignore[arg-type]

    result = await service.commit_push(
        db_session,
        user_id=admin.id,
        session_id=session.id,
        message="add baz",
        push=True,
    )
    assert result.pushed is True
    # Vérifie que le commit est bien dans le remote (bare).
    remote = repo_pair[0]
    branches = await _run(["git", "branch"], cwd=remote)
    assert "feat/eldir" in branches


async def test_commit_nothing_to_commit_raises(
    db_session: AsyncSession,
    admin: User,
    project_session: tuple[Project, Session],
    service: SessionService,
) -> None:
    _, session = project_session
    with pytest.raises(WorkspaceError):
        await service.commit_push(
            db_session,
            user_id=admin.id,
            session_id=session.id,
            message="empty",
            push=False,
        )


async def test_open_pr_calls_provider(
    db_session: AsyncSession,
    admin: User,
    project_session: tuple[Project, Session],
    service: SessionService,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, session = project_session
    await git_credential_service.upsert(
        db_session,
        admin.id,
        GitCredentialCreate(provider="github", token="ghp_local_test"),
    )
    await db_session.commit()
    Path(session.worktree_path).joinpath("pr.py").write_text("a = 1")  # type: ignore[arg-type]

    captured: dict[str, Any] = {}

    class _FakeProvider:
        origine_git = "https://forge.exemple.lan"
        name = "github"

        async def create_pr(
            self,
            full_name: str,
            *,
            head: str,
            base: str,
            title: str,
            body: str | None = None,
        ) -> PullRequestRef:
            captured.update(full_name=full_name, head=head, base=base, title=title, body=body)
            return PullRequestRef(
                number=42,
                url="https://github.com/owner/repo/pull/42",
                head=head,
                base=base,
                title=title,
            )

    monkeypatch.setattr(cred_module, "make_provider", lambda *a, **kw: _FakeProvider())

    pr = await service.open_pull_request(
        db_session,
        user_id=admin.id,
        session_id=session.id,
        title="Add pr",
        body="body",
    )
    assert pr.pr_number == 42
    assert captured["head"] == "feat/eldir"
    assert captured["base"] == "main"
    assert captured["title"] == "Add pr"


async def test_open_pr_same_branch_as_base_fails(
    db_session: AsyncSession,
    admin: User,
    project_session: tuple[Project, Session],
    service: SessionService,
    repo_pair: tuple[Path, Path],
) -> None:
    _, session = project_session
    # On revient sur main pour que head==base.
    await _run(["git", "checkout", "main"], cwd=Path(session.worktree_path))  # type: ignore[arg-type]

    await git_credential_service.upsert(
        db_session,
        admin.id,
        GitCredentialCreate(provider="github", token="ghp_local_test"),
    )
    await db_session.commit()

    with pytest.raises(WorkspaceError):
        await service.open_pull_request(
            db_session,
            user_id=admin.id,
            session_id=session.id,
            title="oops",
        )


async def test_ouvrir_une_pr_forgejo_garde_la_base_url_du_credential(
    db_session: AsyncSession,
    admin: User,
    project_session: tuple[Project, Session],
    service: SessionService,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Meme oubli que pour le clone, decouvert plus tard : la PR part sur une
    instance Forgejo dont l'URL vit sur le credential. Sans elle, la session
    travaille, commit, pousse, et echoue a la derniere etape."""
    project, session = project_session
    project.provider = "forgejo"
    await git_credential_service.upsert(
        db_session,
        admin.id,
        GitCredentialCreate(
            provider="forgejo",
            token="jeton-forgejo-de-test",
            base_url="https://forgejo.exemple.lan",
        ),
    )
    await db_session.commit()
    Path(session.worktree_path).joinpath("pr.py").write_text("a = 1")  # type: ignore[arg-type]

    vues: list[str] = []

    async def _create_pr(
        self: ForgejoProvider,
        full_name: str,
        *,
        head: str,
        base: str,
        title: str,
        body: str | None = None,
    ) -> PullRequestRef:
        vues.append(self._base_url)
        return PullRequestRef(
            number=7,
            url=f"https://forgejo.exemple.lan/{full_name}/pulls/7",
            head=head,
            base=base,
            title=title,
        )

    monkeypatch.setattr(ForgejoProvider, "create_pr", _create_pr)

    pr = await service.open_pull_request(
        db_session,
        user_id=admin.id,
        session_id=session.id,
        title="Ajoute pr",
    )

    assert vues == ["https://forgejo.exemple.lan"]
    assert pr.pr_number == 7


class _ForgeQuiRetient:
    """Une forge qui rend la PR `existante` à `get_pr` et numérote les nouvelles."""

    origine_git = "https://forge.exemple.lan"

    name = "github"

    def __init__(self, existante: PullRequestRef | None = None) -> None:
        self.existante = existante
        self.creees: list[str] = []

    async def get_pr(self, full_name: str, number: int) -> PullRequestRef:
        assert self.existante is not None
        return self.existante

    async def create_pr(
        self, full_name: str, *, head: str, base: str, title: str, body: str | None = None
    ) -> PullRequestRef:
        self.creees.append(title)
        return PullRequestRef(
            number=43,
            url="https://github.com/owner/repo/pull/43",
            head=head,
            base=base,
            title=title,
        )


async def _avec_un_credential(db: AsyncSession, admin: User) -> None:
    await git_credential_service.upsert(
        db, admin.id, GitCredentialCreate(provider="github", token="ghp_local_test")
    )
    await db.commit()


async def test_ouvrir_une_pr_retient_son_numero(
    db_session: AsyncSession,
    admin: User,
    project_session: tuple[Project, Session],
    service: SessionService,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, session = project_session
    await _avec_un_credential(db_session, admin)
    Path(session.worktree_path).joinpath("x.py").write_text("x = 1")  # type: ignore[arg-type]
    monkeypatch.setattr(cred_module, "make_provider", lambda *a, **kw: _ForgeQuiRetient())

    await service.open_pull_request(db_session, user_id=admin.id, session_id=session.id, title="X")

    await db_session.refresh(session)
    assert session.pr_number == 43


async def test_une_seconde_publication_pousse_dans_la_pr_ouverte(
    db_session: AsyncSession,
    admin: User,
    project_session: tuple[Project, Session],
    service: SessionService,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Le chemin d'une correction après une CI rouge : pas de seconde PR."""
    _, session = project_session
    session.pr_number = 42
    await _avec_un_credential(db_session, admin)
    Path(session.worktree_path).joinpath("fix.py").write_text("y = 2")  # type: ignore[arg-type]
    ouverte = PullRequestRef(
        number=42,
        url="https://github.com/owner/repo/pull/42",
        head="feat/eldir",
        base="main",
        title="X",
        state="open",
    )
    forge = _ForgeQuiRetient(existante=ouverte)
    monkeypatch.setattr(cred_module, "make_provider", lambda *a, **kw: forge)

    pr = await service.open_pull_request(
        db_session, user_id=admin.id, session_id=session.id, title="Corrige"
    )

    assert pr.pr_number == 42
    assert forge.creees == []


async def test_une_pr_mergee_est_remplacee_par_une_nouvelle(
    db_session: AsyncSession,
    admin: User,
    project_session: tuple[Project, Session],
    service: SessionService,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, session = project_session
    session.pr_number = 42
    await _avec_un_credential(db_session, admin)
    Path(session.worktree_path).joinpath("suite.py").write_text("z = 3")  # type: ignore[arg-type]
    mergee = PullRequestRef(
        number=42, url="u", head="feat/eldir", base="main", title="X", state="merged"
    )
    forge = _ForgeQuiRetient(existante=mergee)
    monkeypatch.setattr(cred_module, "make_provider", lambda *a, **kw: forge)

    pr = await service.open_pull_request(
        db_session, user_id=admin.id, session_id=session.id, title="Suite"
    )

    assert pr.pr_number == 43
    assert forge.creees == ["Suite"]


async def test_sans_modification_ni_commit_il_n_y_a_rien_a_publier(
    db_session: AsyncSession,
    admin: User,
    project_session: tuple[Project, Session],
    service: SessionService,
) -> None:
    _, session = project_session

    with pytest.raises(WorkspaceError, match="Rien à publier"):
        await service.open_pull_request(
            db_session, user_id=admin.id, session_id=session.id, title="Vide"
        )


class _PrBidon:
    origine_git = "https://forge.exemple.lan"
    name = "github"

    async def create_pr(self, full_name: str, *, head: str, base: str, title: str, body=None):  # type: ignore[no-untyped-def]
        return PullRequestRef(number=1, url="https://x/1", head=head, base=base, title=title)


async def _jeton(db_session: AsyncSession, admin: User) -> None:
    await git_credential_service.upsert(
        db_session, admin.id, GitCredentialCreate(provider="github", token="ghp_local_test")
    )
    await db_session.commit()


async def test_la_publication_ne_suit_ni_la_config_ni_les_hooks_de_la_session(
    db_session: AsyncSession,
    admin: User,
    project_session: tuple[Project, Session],
    service: SessionService,
    repo_pair: tuple[Path, Path],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """La session écrit la config du clone : un refspec `+...:refs/heads/main` et
    un hook pre-push ne doivent ni écraser main ni s'exécuter."""
    remote, work = repo_pair
    _, session = project_session
    await _jeton(db_session, admin)
    temoin = tmp_path / "temoin-pre-push"
    hook = work / ".git" / "hooks" / "pre-push"
    hook.write_text(f"#!/bin/sh\ntouch {temoin}\n")
    hook.chmod(0o755)
    await _run(
        ["git", "config", "remote.origin.push", "+refs/heads/feat/eldir:refs/heads/main"], work
    )
    main_avant = await _run(["git", "rev-parse", "main"], cwd=remote)
    (work / "pr.py").write_text("a = 1")
    monkeypatch.setattr(cred_module, "make_provider", lambda *a, **kw: _PrBidon())

    await service.open_pull_request(
        db_session, user_id=admin.id, session_id=session.id, title="Add pr"
    )

    assert await _run(["git", "rev-parse", "main"], cwd=remote) == main_avant
    assert "feat/eldir" in await _run(["git", "branch"], cwd=remote)
    assert not temoin.exists()


async def test_open_pr_refuse_une_session_hors_de_sa_branche(
    db_session: AsyncSession,
    admin: User,
    project_session: tuple[Project, Session],
    service: SessionService,
    repo_pair: tuple[Path, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    remote, work = repo_pair
    _, session = project_session
    await _jeton(db_session, admin)
    await _run(["git", "checkout", "-b", "autre"], cwd=work)
    (work / "pr.py").write_text("a = 1")
    monkeypatch.setattr(cred_module, "make_provider", lambda *a, **kw: _PrBidon())

    with pytest.raises(WorkspaceError, match="n'est plus sur sa branche"):
        await service.open_pull_request(
            db_session, user_id=admin.id, session_id=session.id, title="x"
        )
    assert "autre" not in await _run(["git", "branch"], cwd=remote)
    assert "pr.py" in await _run(["git", "status", "--porcelain"], cwd=work)


async def test_un_hook_pre_commit_de_la_session_ne_s_execute_pas(
    repo_pair: tuple[Path, Path], tmp_path: Path
) -> None:
    from app.services.worktree_service import worktree_service

    _, work = repo_pair
    temoin = tmp_path / "temoin-pre-commit"
    hook = work / ".git" / "hooks" / "pre-commit"
    hook.write_text(f"#!/bin/sh\ntouch {temoin}\n")
    hook.chmod(0o755)
    (work / "n.py").write_text("n = 1")

    await worktree_service.commit_all(work, message="m")

    assert not temoin.exists()
