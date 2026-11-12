"""Tests ProjectService - mocks GitHub + clone."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from app.core.exceptions import AuthenticationError, ConflictError
from app.db.models import User
from app.schemas.git_credential import GitCredentialCreate
from app.services import git_credential_service as cred_module
from app.services import project_service as project_service_module
from app.services.git_credential_service import git_credential_service
from app.services.git_providers.base import RepoRef
from app.services.git_providers.forgejo import ForgejoProvider
from app.services.project_service import project_service
from app.services.worktree_service import CloneResult
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.fixture
async def admin(db_session: AsyncSession) -> User:
    user = User(
        email="admin@example.com",
        hashed_password="x",
        is_active=True,
        is_admin=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


class _FakeGitHubProvider:
    """Stub minimal qui répond à get_repo."""

    origine_git = "https://forge.exemple.lan"

    name = "github"

    def __init__(self, *_: Any, **__: Any) -> None:
        pass

    async def get_repo(self, full_name: str) -> RepoRef:
        return RepoRef(
            full_name=full_name,
            default_branch="main",
            clone_url=f"https://github.com/{full_name}.git",
            description="stub",
            is_private=False,
        )


@pytest.fixture
def patch_clone(monkeypatch, tmp_path: Path):  # type: ignore[no-untyped-def]
    """Un clone qui ne touche pas au reseau, sans toucher au reste."""

    async def _fake_clone(*, user_id: str, repo_full_name: str, **_: Any) -> CloneResult:
        slug = repo_full_name.rsplit("/", maxsplit=1)[-1].lower()
        path = tmp_path / user_id / slug
        path.mkdir(parents=True, exist_ok=True)
        return CloneResult(path=path, default_branch="main", repo_slug=slug)

    monkeypatch.setattr(project_service_module.worktree_service, "clone_repo", _fake_clone)


@pytest.fixture
def patch_provider_and_clone(monkeypatch, patch_clone: None):  # type: ignore[no-untyped-def]
    """Patch la fabrique de clients et le clone pour les tests GitHub."""
    monkeypatch.setattr(
        cred_module,
        "make_provider",
        lambda *args, **kwargs: _FakeGitHubProvider(),
    )


async def test_create_from_repo_requires_credential(
    db_session: AsyncSession, admin: User, patch_provider_and_clone: None
) -> None:
    with pytest.raises(AuthenticationError):
        await project_service.create_from_repo(
            db_session,
            user_id=admin.id,
            provider="github",
            repo_full_name="owner/repo",
        )


async def test_create_from_repo_happy_path(
    db_session: AsyncSession, admin: User, patch_provider_and_clone: None
) -> None:
    await git_credential_service.upsert(
        db_session,
        admin.id,
        GitCredentialCreate(provider="github", token="ghp_clone_token_aaa"),
    )
    await db_session.commit()

    project = await project_service.create_from_repo(
        db_session,
        user_id=admin.id,
        provider="github",
        repo_full_name="owner/my-repo",
    )
    await db_session.commit()

    assert project.id
    assert project.slug == "my-repo"
    assert project.provider == "github"
    assert project.repo_full_name == "owner/my-repo"
    assert project.workspace_path is not None


async def test_create_from_repo_rejects_duplicate(
    db_session: AsyncSession, admin: User, patch_provider_and_clone: None
) -> None:
    await git_credential_service.upsert(
        db_session,
        admin.id,
        GitCredentialCreate(provider="github", token="ghp_dup_token_aaa"),
    )
    await db_session.commit()

    await project_service.create_from_repo(
        db_session,
        user_id=admin.id,
        provider="github",
        repo_full_name="owner/repo",
    )
    await db_session.commit()

    with pytest.raises(ConflictError):
        await project_service.create_from_repo(
            db_session,
            user_id=admin.id,
            provider="github",
            repo_full_name="owner/repo",
        )


async def test_sync_compte_les_commits_recuperes(
    db_session: AsyncSession,
    admin: User,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """`pulled` doit valoir le retard d'avant le fast-forward, pas celui d'après.

    `behind` est recalculé une fois le pull fait, donc il vaut 0 : l'UI
    affichait « mis à jour · 0 commit récupéré », ce qui ne veut rien dire.
    """
    from app.db.models import Project

    project = Project(
        user_id=admin.id,
        provider="github",
        repo_full_name="JohnDWorld/demo",
        name="demo",
        slug="demo",
        default_branch="main",
        workspace_path=str(tmp_path),
    )
    db_session.add(project)
    await db_session.commit()

    await git_credential_service.upsert(
        db_session,
        admin.id,
        GitCredentialCreate(provider="github", token="ghp_test"),
    )
    await db_session.commit()

    worktree = project_service_module.worktree_service
    appels: list[int] = []

    async def _fetch(*_: Any, **__: Any) -> None:
        return None

    async def _branch(*_: Any, **__: Any) -> str:
        return "main"

    async def _changes(*_: Any, **__: Any) -> bool:
        return False

    async def _ahead_behind(*_: Any, **__: Any) -> tuple[int, int]:
        # 3 commits de retard au premier appel, plus rien après le pull.
        appels.append(1)
        return (0, 3) if len(appels) == 1 else (0, 0)

    async def _ff(*_: Any, **__: Any) -> None:
        return None

    monkeypatch.setattr(worktree, "fetch_remote", _fetch)
    monkeypatch.setattr(worktree, "current_branch", _branch)
    monkeypatch.setattr(worktree, "has_changes", _changes)
    monkeypatch.setattr(worktree, "branch_ahead_behind", _ahead_behind)
    monkeypatch.setattr(worktree, "fast_forward_merge", _ff)

    result = await project_service.sync_with_remote(
        db_session, project_id=project.id, user_id=admin.id
    )

    assert result.fast_forwarded is True
    assert result.pulled == 3
    assert result.behind == 0


async def test_supprimer_un_projet_nettoie_tout_le_serveur(
    db_session: AsyncSession,
    admin: User,
    patch_provider_and_clone: None,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Le disque et la machine distante ne se nettoient pas tout seuls.

    Ce qui traîne sinon : un SDK de plusieurs Go dans le volume des
    toolchains, des fichiers de prod dans la collecte, et surtout une clé
    Eldir encore autorisée sur une machine dont le projet n'existe plus.
    """
    await git_credential_service.upsert(
        db_session,
        admin.id,
        GitCredentialCreate(provider="github", token="ghp_clone_token_aaa"),
    )
    await db_session.commit()
    project = await project_service.create_from_repo(
        db_session,
        user_id=admin.id,
        provider="github",
        repo_full_name="owner/my-repo",
    )
    await db_session.commit()

    nettoyes: list[str] = []

    async def _revoke(project_id: str) -> bool:
        nettoyes.append(f"cle:{project_id}")
        return True

    async def _remove_repo(user_id: str, slug: str) -> None:
        nettoyes.append(f"repo:{slug}")

    async def _remove_toolchain(project_id: str) -> None:
        nettoyes.append(f"toolchain:{project_id}")

    async def _remove_collecte(project_id: str) -> None:
        nettoyes.append(f"collecte:{project_id}")

    monkeypatch.setattr(project_service_module.remote_access_service, "revoke", _revoke)
    monkeypatch.setattr(project_service_module.worktree_service, "remove_repo", _remove_repo)
    monkeypatch.setattr(project_service_module.toolchain_service, "remove", _remove_toolchain)
    monkeypatch.setattr(project_service_module.collect_service, "remove", _remove_collecte)
    maison = tmp_path / "maisons" / project.id
    (maison / "projects").mkdir(parents=True)
    (maison / "projects" / "transcript.jsonl").write_text("{}")
    monkeypatch.setattr(
        project_service_module, "maison_du_projet", lambda pid: tmp_path / "maisons" / pid
    )

    await project_service.delete(db_session, project.id, admin.id)
    await db_session.commit()

    assert not maison.exists()
    assert nettoyes == [
        f"cle:{project.id}",
        "repo:my-repo",
        f"toolchain:{project.id}",
        f"collecte:{project.id}",
    ]


async def test_une_machine_eteinte_n_empeche_pas_la_suppression(
    db_session: AsyncSession,
    admin: User,
    patch_provider_and_clone: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """La révocation peut échouer (machine éteinte) : le projet part quand même."""
    await git_credential_service.upsert(
        db_session,
        admin.id,
        GitCredentialCreate(provider="github", token="ghp_clone_token_aaa"),
    )
    await db_session.commit()
    project = await project_service.create_from_repo(
        db_session,
        user_id=admin.id,
        provider="github",
        repo_full_name="owner/my-repo",
    )
    await db_session.commit()

    async def _revoke_casse(project_id: str) -> bool:
        raise RuntimeError("machine injoignable")

    async def _rien(*_: Any, **__: Any) -> None:
        return None

    monkeypatch.setattr(project_service_module.remote_access_service, "revoke", _revoke_casse)
    monkeypatch.setattr(project_service_module.worktree_service, "remove_repo", _rien)
    monkeypatch.setattr(project_service_module.toolchain_service, "remove", _rien)
    monkeypatch.setattr(project_service_module.collect_service, "remove", _rien)

    await project_service.delete(db_session, project.id, admin.id)
    await db_session.commit()

    assert await project_service.list_for_user(db_session, admin.id) == []


async def test_cloner_un_depot_forgejo_garde_la_base_url_du_credential(
    db_session: AsyncSession,
    admin: User,
    patch_clone: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """La base_url d'une instance Forgejo vit sur le credential, pas sur le projet.

    Le chemin qui liste les depots la relisait, celui qui en clone un ne la
    relisait pas : la liste s'affichait et cocher un depot repondait
    « Forgejo necessite une base_url ». Le test construit un VRAI
    ForgejoProvider, donc il echoue tant que l'appel perd l'argument.
    """
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

    vues: list[str] = []

    async def _get_repo(self: ForgejoProvider, full_name: str) -> RepoRef:
        vues.append(self._base_url)
        return RepoRef(
            full_name=full_name,
            default_branch="main",
            clone_url=f"https://forgejo.exemple.lan/{full_name}.git",
            description=None,
            is_private=True,
        )

    monkeypatch.setattr(ForgejoProvider, "get_repo", _get_repo)

    project = await project_service.create_from_repo(
        db_session,
        user_id=admin.id,
        provider="forgejo",
        repo_full_name="john/Skali",
    )
    await db_session.commit()

    assert vues == ["https://forgejo.exemple.lan"]
    assert project.provider == "forgejo"
    assert project.workspace_path is not None
