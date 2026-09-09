"""Génération de template en lot : périmètre et séquencement.

Deux garanties valent un test, parce qu'un lot qui se trompe coûte des tokens
et peut écraser du travail :

1. les projets qui ont déjà un Mission Template sont **sautés** ;
2. les générations s'enchaînent **une par une** (une génération = un process
   `claude` résident, les lancer en parallèle mettrait le serveur à genoux).
"""

from __future__ import annotations

import asyncio

import pytest
from app.db.models import MissionTemplate, Project, User
from app.services.event_bus import EventBus
from app.services.session_manager import SessionManager
from app.services.template_generator_service import BatchItem, TemplateGeneratorService
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker


@pytest.fixture
async def user(db_session: AsyncSession) -> User:
    row = User(email="john@example.com", hashed_password="x", is_admin=True)
    db_session.add(row)
    await db_session.commit()
    await db_session.refresh(row)
    return row


async def _project(db: AsyncSession, user_id: str, name: str, *, with_template: bool) -> Project:
    project = Project(
        user_id=user_id,
        provider="github",
        repo_full_name=f"JohnDWorld/{name}",
        name=name,
        slug=name.lower(),
        default_branch="main",
        workspace_path=f"/tmp/{name}",
    )
    db.add(project)
    await db.flush()
    if with_template:
        db.add(MissionTemplate(project_id=project.id, system_prompt="déjà configuré"))
    await db.commit()
    return project


@pytest.fixture
def generator(
    session_factory: async_sessionmaker[AsyncSession],
) -> TemplateGeneratorService:
    service = TemplateGeneratorService(
        manager=SessionManager(event_bus=EventBus(redis=None)),  # type: ignore[arg-type]
        event_bus=EventBus(redis=None),  # type: ignore[arg-type]
    )
    service.attach_session_factory(session_factory)
    return service


async def test_le_lot_saute_les_projets_deja_pourvus(
    db_session: AsyncSession, user: User, generator: TemplateGeneratorService
) -> None:
    await _project(db_session, user.id, "avec-template", with_template=True)
    await _project(db_session, user.id, "sans-template", with_template=False)

    traites: list[str] = []

    async def _fake(user_id: str, item: BatchItem) -> None:
        traites.append(item.project_name)
        item.state = "done"

    generator._generate_and_apply = _fake  # type: ignore[method-assign]

    state = await generator.start_batch(db_session, user_id=user.id)
    assert [i.project_name for i in state.items] == ["sans-template"]

    for _ in range(50):
        await asyncio.sleep(0.02)
        if not state.running:
            break
    assert traites == ["sans-template"]
    assert state.done_count == 1


async def test_les_generations_ne_se_chevauchent_pas(
    db_session: AsyncSession, user: User, generator: TemplateGeneratorService
) -> None:
    for name in ("un", "deux", "trois"):
        await _project(db_session, user.id, name, with_template=False)

    en_cours = 0
    max_simultane = 0

    async def _fake(user_id: str, item: BatchItem) -> None:
        nonlocal en_cours, max_simultane
        en_cours += 1
        max_simultane = max(max_simultane, en_cours)
        await asyncio.sleep(0.01)
        en_cours -= 1
        item.state = "done"

    generator._generate_and_apply = _fake  # type: ignore[method-assign]

    state = await generator.start_batch(db_session, user_id=user.id)
    for _ in range(100):
        await asyncio.sleep(0.02)
        if not state.running:
            break

    assert max_simultane == 1
    assert state.done_count == 3
    assert state.running is False


async def test_un_projet_en_echec_n_arrete_pas_le_lot(
    db_session: AsyncSession, user: User, generator: TemplateGeneratorService
) -> None:
    for name in ("un", "deux"):
        await _project(db_session, user.id, name, with_template=False)

    async def _fake(user_id: str, item: BatchItem) -> None:
        if item.project_name == "un":
            raise RuntimeError("repo cassé")
        item.state = "done"

    generator._generate_and_apply = _fake  # type: ignore[method-assign]

    state = await generator.start_batch(db_session, user_id=user.id)
    for _ in range(50):
        await asyncio.sleep(0.02)
        if not state.running:
            break

    par_nom = {i.project_name: i for i in state.items}
    assert par_nom["un"].state == "error"
    assert par_nom["un"].detail == "repo cassé"
    assert par_nom["deux"].state == "done"
