"""Tests GitCredentialService."""

from __future__ import annotations

import pytest
from app.core.exceptions import GitProviderError, NotFoundError
from app.db.models import Project, User
from app.schemas.git_credential import GitCredentialCreate
from app.services.git_credential_service import git_credential_service
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


async def test_upsert_creates_then_replaces(db_session: AsyncSession, admin: User) -> None:
    first = await git_credential_service.upsert(
        db_session,
        admin.id,
        GitCredentialCreate(provider="github", token="ghp_first_token_aaaaa"),
    )
    await db_session.commit()
    assert first.id

    second = await git_credential_service.upsert(
        db_session,
        admin.id,
        GitCredentialCreate(provider="github", token="ghp_second_token_bbbbb"),
    )
    await db_session.commit()

    creds = await git_credential_service.list_for_user(db_session, admin.id)
    assert len(creds) == 1
    assert creds[0].id == second.id

    plain = await git_credential_service.get_active_token(db_session, admin.id, "github")
    assert plain == "ghp_second_token_bbbbb"


async def test_forgejo_requires_base_url(db_session: AsyncSession, admin: User) -> None:
    with pytest.raises(GitProviderError):
        await git_credential_service.upsert(
            db_session,
            admin.id,
            GitCredentialCreate(provider="forgejo", token="fj_token_xxxxx"),
        )


async def test_delete_removes(db_session: AsyncSession, admin: User) -> None:
    cred = await git_credential_service.upsert(
        db_session,
        admin.id,
        GitCredentialCreate(provider="github", token="ghp_to_delete_token"),
    )
    await db_session.commit()
    await git_credential_service.delete(db_session, cred.id, admin.id)
    await db_session.commit()

    with pytest.raises(NotFoundError):
        await git_credential_service.get(db_session, cred.id, admin.id)


async def test_token_colle_avec_un_saut_de_ligne_est_nettoye() -> None:
    """Un token collé depuis un navigateur arrive souvent avec un \\n.

    Stocké tel quel, il part dans l'en-tête Authorization et le provider
    répond "401 Bad credentials" sans indice sur la cause.
    """
    payload = GitCredentialCreate(provider="github", token="  ghp_abcd1234efgh\n")
    assert payload.token == "ghp_abcd1234efgh"


# ── Un jeton par projet (migration 0014) ────────────────────────────────
# Un seul PAT pour tous les dépôts, c'est une fuite qui les expose tous. Les
# sessions tournent en `bypassPermissions` sur des consignes qui peuvent venir
# de l'extérieur : mieux vaut qu'un jeton compromis ne porte que son dépôt.


async def _projet_pour_jeton(db: AsyncSession, user_id: str, nom: str) -> Project:
    row = Project(
        user_id=user_id,
        provider="github",
        repo_full_name=f"JohnDWorld/{nom}",
        name=nom,
        slug=nom,
        default_branch="main",
        workspace_path=f"/tmp/{nom}",
    )
    db.add(row)
    await db.flush()
    return row


async def test_le_jeton_du_projet_passe_avant_le_global(
    db_session: AsyncSession, admin: User
) -> None:
    projet = await _projet_pour_jeton(db_session, admin.id, "vitrine")
    await git_credential_service.upsert(
        db_session, admin.id, GitCredentialCreate(provider="github", token="jeton-global-aaaa")
    )
    await git_credential_service.upsert(
        db_session,
        admin.id,
        GitCredentialCreate(
            provider="github", token="jeton-du-projet-bbbb", project_id=projet.id
        ),
    )
    await db_session.commit()

    assert (
        await git_credential_service.get_active_token(db_session, admin.id, "github", projet.id)
        == "jeton-du-projet-bbbb"
    )
    # Un autre projet, sans jeton propre, retombe sur le global.
    autre = await _projet_pour_jeton(db_session, admin.id, "boutique")
    assert (
        await git_credential_service.get_active_token(db_session, admin.id, "github", autre.id)
        == "jeton-global-aaaa"
    )
    # Et sans projet du tout (création de projet, liste des dépôts distants).
    assert (
        await git_credential_service.get_active_token(db_session, admin.id, "github")
        == "jeton-global-aaaa"
    )


async def test_poser_le_jeton_d_un_projet_ne_chasse_pas_le_global(
    db_session: AsyncSession, admin: User
) -> None:
    """Le remplacement ne vaut qu'à portée égale.

    `upsert` remplace l'existant du même provider : sans condition de portée,
    poser le jeton d'un projet supprimait celui qui sert tous les autres, et la
    synchronisation de tout le reste s'arrêtait.
    """
    projet = await _projet_pour_jeton(db_session, admin.id, "vitrine")
    await git_credential_service.upsert(
        db_session, admin.id, GitCredentialCreate(provider="github", token="jeton-global-aaaa")
    )
    await git_credential_service.upsert(
        db_session,
        admin.id,
        GitCredentialCreate(
            provider="github", token="jeton-du-projet-bbbb", project_id=projet.id
        ),
    )
    await db_session.commit()

    tous = await git_credential_service.list_for_user(db_session, admin.id)
    portees = {(c.project_id or "global") for c in tous}
    assert portees == {"global", projet.id}


async def test_remplacer_le_jeton_d_un_projet_ne_touche_que_le_sien(
    db_session: AsyncSession, admin: User
) -> None:
    projet = await _projet_pour_jeton(db_session, admin.id, "vitrine")
    autre = await _projet_pour_jeton(db_session, admin.id, "boutique")
    for cible, valeur in ((projet.id, "jeton-un-aaaa"), (autre.id, "jeton-deux-bbbb")):
        await git_credential_service.upsert(
            db_session,
            admin.id,
            GitCredentialCreate(provider="github", token=valeur, project_id=cible),
        )
    await git_credential_service.upsert(
        db_session,
        admin.id,
        GitCredentialCreate(
            provider="github", token="jeton-un-remplace", project_id=projet.id
        ),
    )
    await db_session.commit()

    assert (
        await git_credential_service.get_active_token(db_session, admin.id, "github", projet.id)
        == "jeton-un-remplace"
    )
    assert (
        await git_credential_service.get_active_token(db_session, admin.id, "github", autre.id)
        == "jeton-deux-bbbb"
    )
