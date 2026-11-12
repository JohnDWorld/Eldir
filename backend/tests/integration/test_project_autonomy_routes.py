"""PATCH /projects/{id} : John règle l'autonomie d'un projet, et lui seul."""

from __future__ import annotations

from app.db.models import Project, User
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker


async def _projet(factory: async_sessionmaker[AsyncSession], user_id: str = "u-test") -> str:
    async with factory() as db:
        if await db.get(User, user_id) is None:
            db.add(User(id=user_id, email=f"{user_id}@exemple.lan", hashed_password="x"))
        project = Project(
            user_id=user_id,
            name="demo",
            slug="demo",
            provider="github",
            repo_full_name="owner/demo",
            default_branch="main",
        )
        db.add(project)
        await db.commit()
        return project.id


async def test_un_projet_neuf_n_est_pas_autonome(
    client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
    entetes_john: dict[str, str],
) -> None:
    project_id = await _projet(session_factory)

    reponse = await client.get(f"/api/v1/projects/{project_id}", headers=entetes_john)

    assert reponse.status_code == 200
    assert reponse.json()["autonomous"] is False
    assert reponse.json()["deploy_command"] is None


async def test_john_rend_un_projet_autonome_et_declare_sa_commande(
    client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
    entetes_john: dict[str, str],
) -> None:
    project_id = await _projet(session_factory)

    reponse = await client.patch(
        f"/api/v1/projects/{project_id}",
        json={"autonomous": True, "deploy_command": "  cd /srv/demo && ./deploy.sh  "},
        headers=entetes_john,
    )

    assert reponse.status_code == 200
    assert reponse.json()["autonomous"] is True
    assert reponse.json()["deploy_command"] == "cd /srv/demo && ./deploy.sh"


async def test_une_commande_vide_efface_la_commande_sans_toucher_au_reste(
    client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
    entetes_john: dict[str, str],
) -> None:
    project_id = await _projet(session_factory)
    url = f"/api/v1/projects/{project_id}"
    await client.patch(
        url, json={"autonomous": True, "deploy_command": "./deploy.sh"}, headers=entetes_john
    )

    reponse = await client.patch(url, json={"deploy_command": ""}, headers=entetes_john)

    assert reponse.json()["deploy_command"] is None
    assert reponse.json()["autonomous"] is True


async def test_une_commande_sur_plusieurs_lignes_est_refusee(
    client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
    entetes_john: dict[str, str],
) -> None:
    project_id = await _projet(session_factory)

    reponse = await client.patch(
        f"/api/v1/projects/{project_id}",
        json={"deploy_command": "./deploy.sh\nrm -rf /"},
        headers=entetes_john,
    )

    assert reponse.status_code == 422


async def test_le_projet_d_un_autre_est_introuvable(
    client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
    entetes_john: dict[str, str],
) -> None:
    project_id = await _projet(session_factory, user_id="u-autre")

    reponse = await client.patch(
        f"/api/v1/projects/{project_id}", json={"autonomous": True}, headers=entetes_john
    )

    assert reponse.status_code == 404


async def test_un_jeton_d_agent_ne_rend_pas_un_projet_autonome(
    client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
    jeton_agent: str,
) -> None:
    """La case est le consentement de John : un agent ne se la donne pas."""
    project_id = await _projet(session_factory)

    reponse = await client.patch(
        f"/api/v1/projects/{project_id}",
        json={"autonomous": True},
        headers={"Authorization": f"Bearer {jeton_agent}"},
    )

    assert reponse.status_code == 401
