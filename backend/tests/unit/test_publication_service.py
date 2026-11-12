"""PublicationService : Eldir publie et merge, avec ses refus mécaniques."""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock

import pytest
from app.core.config import get_settings
from app.db.models import MissionTemplate, Project, Session, User
from app.services.event_bus import EventBus
from app.services.git_credential_service import git_credential_service
from app.services.git_providers.base import (
    CHECKS_AUCUN,
    CHECKS_EN_COURS,
    CHECKS_ROUGE,
    CHECKS_VERT,
    ChecksReport,
    PullRequestRef,
)
from app.services.publication_service import PublicationService
from app.services.remote_access_service import RemoteStatus, remote_access_service
from app.services.session_manager import ActiveSession, SessionManager
from app.services.session_service import OpenPRResult, SessionService
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker


class _Forge:
    """Une forge dont les checks défilent : le dernier état se répète."""

    def __init__(
        self, *etats: ChecksReport, state: str = "open", shas: tuple[str, ...] = ("abc123",)
    ) -> None:
        self.etats = list(etats)
        self.shas = list(shas)
        self.state = state
        self.merges: list[int] = []
        self.sha_vises: list[str] = []

    async def get_pr(self, full_name: str, number: int) -> PullRequestRef:
        return PullRequestRef(
            number=number,
            url=f"https://forge.exemple.lan/{full_name}/pulls/{number}",
            head="eldir/s1",
            base="main",
            title="X",
            state=self.state,
            head_sha=self.shas.pop(0) if len(self.shas) > 1 else self.shas[0],
        )

    async def checks(self, full_name: str, sha: str) -> ChecksReport:
        return self.etats.pop(0) if len(self.etats) > 1 else self.etats[0]

    async def merge_pr(self, full_name: str, number: int, sha: str) -> None:
        self.merges.append(number)
        self.sha_vises.append(sha)
        self.state = "merged"


@pytest.fixture
async def monde(session_factory: async_sessionmaker[AsyncSession]) -> dict[str, str]:
    async with session_factory() as db:
        user = User(email="john@exemple.lan", hashed_password="x")
        db.add(user)
        await db.flush()
        project = Project(
            user_id=user.id,
            name="demo",
            slug="demo",
            provider="github",
            repo_full_name="owner/demo",
            default_branch="main",
            autonomous=True,
        )
        db.add(project)
        await db.flush()
        session = Session(
            project_id=project.id,
            user_id=user.id,
            branch="eldir/s1",
            worktree_path="/tmp/inexistant",
            state="idle",
            pr_number=7,
        )
        db.add(session)
        await db.commit()
        return {"user": user.id, "project": project.id, "session": session.id}


@pytest.fixture
def prevenus() -> list[tuple[str, str]]:
    return []


@pytest.fixture
def service(
    session_factory: async_sessionmaker[AsyncSession],
    prevenus: list[tuple[str, str]],
    monkeypatch: pytest.MonkeyPatch,
) -> PublicationService:
    reglages = get_settings()
    monkeypatch.setattr(reglages, "merge_watch_interval_s", 0)
    monkeypatch.setattr(reglages, "merge_no_checks_grace_s", 0)
    monkeypatch.setattr(reglages, "merge_watch_timeout_s", 3600)
    manager = SessionManager(event_bus=EventBus(redis=AsyncMock()))

    async def prevenir(user_id: str, message: str) -> None:
        prevenus.append((user_id, message))

    return PublicationService(
        manager=manager,
        sessions=SessionService(manager=manager),
        session_factory=session_factory,
        prevenir=prevenir,
    )


def _brancher(monkeypatch: pytest.MonkeyPatch, forge: _Forge) -> None:
    monkeypatch.setattr(
        git_credential_service, "get_active_client", AsyncMock(return_value=("jeton", forge))
    )


async def _fin_des_taches(service: PublicationService) -> None:
    await asyncio.gather(*list(service._tasks))


async def _rendre(
    factory: async_sessionmaker[AsyncSession], project_id: str, **champs: Any
) -> None:
    async with factory() as db:
        project = await db.get(Project, project_id)
        assert project is not None
        for nom, valeur in champs.items():
            setattr(project, nom, valeur)
        await db.commit()


# ── open_pr ──────────────────────────────────────────────────────
async def test_open_pr_est_refuse_pendant_un_tour(
    service: PublicationService, monde: dict[str, str]
) -> None:
    active = ActiveSession(
        session_id=monde["session"], project_id=monde["project"], user_id=monde["user"], cwd="/tmp"
    )
    service._manager._sessions[monde["session"]] = active

    async with active.message_lock:
        reponse = await service.open_pr(
            monde["user"], session_id=monde["session"], titre="X", description="d"
        )

    assert reponse.startswith("Refusé : cette session a un tour en cours")


async def test_open_pr_rend_le_lien_de_la_pr(
    service: PublicationService, monde: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    appel = AsyncMock(
        return_value=OpenPRResult(
            pr_number=7,
            pr_url="https://forge.exemple.lan/pr/7",
            head="eldir/s1",
            base="main",
            title="X",
        )
    )
    monkeypatch.setattr(service._sessions, "open_pull_request", appel)

    reponse = await service.open_pr(
        monde["user"], session_id=monde["session"], titre=" X ", description="d"
    )

    assert "https://forge.exemple.lan/pr/7" in reponse
    assert appel.await_args.kwargs["title"] == "X"


# ── merge : les refus ────────────────────────────────────────────
async def test_merge_refuse_un_projet_non_autonome(
    service: PublicationService,
    monde: dict[str, str],
    session_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await _rendre(session_factory, monde["project"], autonomous=False)
    forge = _Forge(ChecksReport(CHECKS_VERT))
    _brancher(monkeypatch, forge)

    reponse = await service.merge(monde["user"], session_id=monde["session"])

    assert reponse.startswith("Refusé : demo n'est pas autonome")
    assert forge.merges == []


async def _source_externe(factory: async_sessionmaker[AsyncSession], project_id: str) -> None:
    async with factory() as db:
        db.add(MissionTemplate(project_id=project_id, source_externe=True))
        await db.commit()


async def test_merge_refuse_un_projet_alimente_par_une_source_externe(
    service: PublicationService,
    monde: dict[str, str],
    session_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await _source_externe(session_factory, monde["project"])
    forge = _Forge(ChecksReport(CHECKS_VERT))
    _brancher(monkeypatch, forge)

    reponse = await service.merge(monde["user"], session_id=monde["session"])

    assert reponse == ("Refusé : demo est alimenté par une source externe, John merge lui-même.")
    assert forge.merges == []


async def test_deploy_refuse_un_projet_alimente_par_une_source_externe(
    service: PublicationService,
    monde: dict[str, str],
    session_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await _rendre(session_factory, monde["project"], deploy_command="./d.sh")
    await _source_externe(session_factory, monde["project"])
    executer = _machine(monkeypatch)

    reponse = await service.deploy(monde["user"], project_id=monde["project"])

    assert reponse == ("Refusé : demo est alimenté par une source externe, John déploie lui-même.")
    executer.assert_not_awaited()


async def test_merge_refuse_une_session_sans_pr(
    service: PublicationService,
    monde: dict[str, str],
    session_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async with session_factory() as db:
        session = await db.get(Session, monde["session"])
        assert session is not None
        session.pr_number = None
        await db.commit()
    _brancher(monkeypatch, _Forge(ChecksReport(CHECKS_VERT)))

    reponse = await service.merge(monde["user"], session_id=monde["session"])

    assert "n'a pas de PR" in reponse


async def test_merge_refuse_une_pr_deja_mergee(
    service: PublicationService, monde: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    _brancher(monkeypatch, _Forge(ChecksReport(CHECKS_VERT), state="merged"))

    reponse = await service.merge(monde["user"], session_id=monde["session"])

    assert "déjà mergée" in reponse


async def test_merge_refuse_la_session_d_un_autre(
    service: PublicationService, monde: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    _brancher(monkeypatch, _Forge(ChecksReport(CHECKS_VERT)))

    reponse = await service.merge("u-autre", session_id=monde["session"])

    assert reponse.startswith("Erreur :")


# ── merge : selon la CI ──────────────────────────────────────────
async def test_une_ci_verte_merge_tout_de_suite(
    service: PublicationService, monde: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    forge = _Forge(ChecksReport(CHECKS_VERT))
    _brancher(monkeypatch, forge)

    reponse = await service.merge(monde["user"], session_id=monde["session"])

    assert forge.merges == [7]
    assert "mergée" in reponse


async def test_une_ci_rouge_refuse_et_nomme_les_checks(
    service: PublicationService, monde: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    forge = _Forge(ChecksReport(CHECKS_ROUGE, ("tests", "lint")))
    _brancher(monkeypatch, forge)

    reponse = await service.merge(monde["user"], session_id=monde["session"])

    assert forge.merges == []
    assert "tests, lint" in reponse


async def test_une_ci_en_cours_merge_des_qu_elle_passe_et_previent(
    service: PublicationService,
    monde: dict[str, str],
    prevenus: list[tuple[str, str]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    forge = _Forge(
        ChecksReport(CHECKS_EN_COURS), ChecksReport(CHECKS_EN_COURS), ChecksReport(CHECKS_VERT)
    )
    _brancher(monkeypatch, forge)

    reponse = await service.merge(monde["user"], session_id=monde["session"])
    assert reponse.startswith("CI en cours")
    await _fin_des_taches(service)

    assert forge.merges == [7]
    assert forge.sha_vises == ["abc123"]
    assert prevenus[0][0] == monde["user"]
    assert "mergée" in prevenus[0][1]


async def test_une_ci_en_cours_puis_rouge_ne_merge_pas(
    service: PublicationService,
    monde: dict[str, str],
    prevenus: list[tuple[str, str]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    forge = _Forge(ChecksReport(CHECKS_EN_COURS), ChecksReport(CHECKS_ROUGE, ("tests",)))
    _brancher(monkeypatch, forge)

    await service.merge(monde["user"], session_id=monde["session"])
    await _fin_des_taches(service)

    assert forge.merges == []
    assert "rouge" in prevenus[0][1]


async def test_une_ci_trop_longue_ne_merge_pas(
    service: PublicationService,
    monde: dict[str, str],
    prevenus: list[tuple[str, str]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(get_settings(), "merge_watch_timeout_s", 0)
    forge = _Forge(ChecksReport(CHECKS_EN_COURS))
    _brancher(monkeypatch, forge)

    await service.merge(monde["user"], session_id=monde["session"])
    await _fin_des_taches(service)

    assert forge.merges == []
    assert "n'a pas fini" in prevenus[0][1]


async def test_sans_check_apres_le_delai_de_grace_le_projet_n_a_pas_de_ci(
    service: PublicationService,
    monde: dict[str, str],
    prevenus: list[tuple[str, str]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    forge = _Forge(ChecksReport(CHECKS_AUCUN))
    _brancher(monkeypatch, forge)

    reponse = await service.merge(monde["user"], session_id=monde["session"])
    assert reponse.startswith("Aucun check")
    await _fin_des_taches(service)

    assert forge.merges == [7]
    assert "pas de CI" in prevenus[0][1]


async def test_une_seule_surveillance_par_session(
    service: PublicationService, monde: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(get_settings(), "merge_watch_interval_s", 3600)
    _brancher(monkeypatch, _Forge(ChecksReport(CHECKS_EN_COURS)))

    await service.merge(monde["user"], session_id=monde["session"])
    seconde = await service.merge(monde["user"], session_id=monde["session"])

    assert "déjà en cours" in seconde
    taches = list(service._tasks)
    for tache in taches:
        tache.cancel()
    await asyncio.gather(*taches, return_exceptions=True)


async def test_une_erreur_reseau_pendant_la_surveillance_previent_le_superviseur(
    service: PublicationService,
    monde: dict[str, str],
    prevenus: list[tuple[str, str]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    forge = _Forge(ChecksReport(CHECKS_EN_COURS))
    appels = 0

    async def checks(full_name: str, sha: str) -> ChecksReport:
        nonlocal appels
        appels += 1
        if appels > 1:
            raise RuntimeError("réseau coupé")
        return ChecksReport(CHECKS_EN_COURS)

    forge.checks = checks  # type: ignore[method-assign]
    _brancher(monkeypatch, forge)

    await service.merge(monde["user"], session_id=monde["session"])
    await _fin_des_taches(service)

    assert forge.merges == []
    assert "abandonné" in prevenus[0][1]


async def test_un_nouveau_commit_pendant_l_attente_ne_merge_pas(
    service: PublicationService,
    monde: dict[str, str],
    prevenus: list[tuple[str, str]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    forge = _Forge(
        ChecksReport(CHECKS_EN_COURS), ChecksReport(CHECKS_AUCUN), shas=("abc123", "def456")
    )
    _brancher(monkeypatch, forge)

    await service.merge(monde["user"], session_id=monde["session"])
    await _fin_des_taches(service)

    assert forge.merges == []
    assert "nouveau commit" in prevenus[0][1]


async def test_decocher_autonome_pendant_l_attente_ne_merge_pas(
    service: PublicationService,
    monde: dict[str, str],
    session_factory: async_sessionmaker[AsyncSession],
    prevenus: list[tuple[str, str]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    forge = _Forge(ChecksReport(CHECKS_EN_COURS), ChecksReport(CHECKS_VERT))
    _brancher(monkeypatch, forge)
    lire = forge.checks

    async def checks_puis_decoche(full_name: str, sha: str) -> ChecksReport:
        rapport = await lire(full_name, sha)
        await _rendre(session_factory, monde["project"], autonomous=False)
        return rapport

    monkeypatch.setattr(forge, "checks", checks_puis_decoche)

    await service.merge(monde["user"], session_id=monde["session"])
    await _fin_des_taches(service)

    assert forge.merges == []
    assert "n'est plus autonome" in prevenus[0][1]


async def test_une_session_supprimee_pendant_la_surveillance_ne_merge_pas(
    service: PublicationService,
    monde: dict[str, str],
    session_factory: async_sessionmaker[AsyncSession],
    prevenus: list[tuple[str, str]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    forge = _Forge(ChecksReport(CHECKS_EN_COURS), ChecksReport(CHECKS_VERT))
    _brancher(monkeypatch, forge)
    lire = forge.checks

    async def checks_puis_supprime(full_name: str, sha: str) -> ChecksReport:
        rapport = await lire(full_name, sha)
        async with session_factory() as db:
            ligne = await db.get(Session, monde["session"])
            await db.delete(ligne)
            await db.commit()
        return rapport

    monkeypatch.setattr(forge, "checks", checks_puis_supprime)

    await service.merge(monde["user"], session_id=monde["session"])
    await _fin_des_taches(service)

    assert forge.merges == []
    assert "supprimée" in prevenus[0][1]


# ── deploy ───────────────────────────────────────────────────────
def _machine(monkeypatch: pytest.MonkeyPatch, *, alias: str | None = "eldir-demo") -> AsyncMock:
    monkeypatch.setattr(
        remote_access_service,
        "status",
        lambda project_id: RemoteStatus(configured=alias is not None, alias=alias),
    )
    executer = AsyncMock(return_value=(0, "\n".join(f"ligne {i}" for i in range(60))))
    monkeypatch.setattr(remote_access_service, "executer", executer)
    return executer


async def test_deploy_refuse_un_projet_non_autonome(
    service: PublicationService,
    monde: dict[str, str],
    session_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await _rendre(session_factory, monde["project"], autonomous=False, deploy_command="./d.sh")
    executer = _machine(monkeypatch)

    reponse = await service.deploy(monde["user"], project_id=monde["project"])

    assert reponse.startswith("Refusé : demo n'est pas autonome")
    executer.assert_not_awaited()


async def test_sans_commande_la_forge_deploie_au_merge(
    service: PublicationService, monde: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    executer = _machine(monkeypatch)

    reponse = await service.deploy(monde["user"], project_id=monde["project"])

    assert "la forge déploie au merge" in reponse
    executer.assert_not_awaited()


async def test_une_commande_sans_acces_distant_est_refusee(
    service: PublicationService,
    monde: dict[str, str],
    session_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await _rendre(session_factory, monde["project"], deploy_command="./d.sh")
    executer = _machine(monkeypatch, alias=None)

    reponse = await service.deploy(monde["user"], project_id=monde["project"])

    assert "pas d'accès distant" in reponse
    executer.assert_not_awaited()


async def test_deploy_lance_la_commande_declaree_et_previent_avec_la_fin_de_la_sortie(
    service: PublicationService,
    monde: dict[str, str],
    session_factory: async_sessionmaker[AsyncSession],
    prevenus: list[tuple[str, str]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await _rendre(session_factory, monde["project"], deploy_command="./d.sh")
    executer = _machine(monkeypatch)

    reponse = await service.deploy(monde["user"], project_id=monde["project"])
    assert reponse.startswith("Déploiement de demo lancé")
    await _fin_des_taches(service)

    assert executer.await_args.args == ("eldir-demo", "./d.sh")
    message = prevenus[0][1]
    assert "réussi" in message
    assert "ligne 59" in message
    assert "ligne 9\n" not in message  # seules les 50 dernières lignes


async def test_un_deploiement_trop_long_est_signale(
    service: PublicationService,
    monde: dict[str, str],
    session_factory: async_sessionmaker[AsyncSession],
    prevenus: list[tuple[str, str]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await _rendre(session_factory, monde["project"], deploy_command="./d.sh")
    executer = _machine(monkeypatch)
    executer.return_value = (None, "")

    await service.deploy(monde["user"], project_id=monde["project"])
    await _fin_des_taches(service)

    assert "ssh coupé après" in prevenus[0][1]
    assert "la commande peut encore tourner sur la machine" in prevenus[0][1]


async def test_la_sortie_du_deploiement_est_bornee_en_caracteres(
    service: PublicationService,
    monde: dict[str, str],
    session_factory: async_sessionmaker[AsyncSession],
    prevenus: list[tuple[str, str]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await _rendre(session_factory, monde["project"], deploy_command="./d.sh")
    executer = _machine(monkeypatch)
    executer.return_value = (0, "début\n" + "x" * 10_000 + "FIN")

    await service.deploy(monde["user"], project_id=monde["project"])
    await _fin_des_taches(service)

    message = prevenus[0][1]
    assert message.endswith("xFIN")
    assert "début" not in message
    assert len(message) < 4200


async def test_un_seul_deploiement_a_la_fois_par_projet(
    service: PublicationService,
    monde: dict[str, str],
    session_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await _rendre(session_factory, monde["project"], deploy_command="./d.sh")
    executer = _machine(monkeypatch)
    libere = asyncio.Event()

    async def lent(*_: Any, **__: Any) -> tuple[int, str]:
        await libere.wait()
        return 0, "ok"

    executer.side_effect = lent

    await service.deploy(monde["user"], project_id=monde["project"])
    seconde = await service.deploy(monde["user"], project_id=monde["project"])
    libere.set()
    await _fin_des_taches(service)

    assert "déjà en cours" in seconde


async def test_une_erreur_inattendue_previent_et_libere_le_projet(
    service: PublicationService,
    monde: dict[str, str],
    session_factory: async_sessionmaker[AsyncSession],
    prevenus: list[tuple[str, str]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await _rendre(session_factory, monde["project"], deploy_command="./d.sh")
    executer = _machine(monkeypatch)
    executer.side_effect = RuntimeError("boom")

    await service.deploy(monde["user"], project_id=monde["project"])
    await _fin_des_taches(service)
    seconde = await service.deploy(monde["user"], project_id=monde["project"])
    await _fin_des_taches(service)

    assert "erreur inattendue" in prevenus[0][1]
    assert "déjà en cours" not in seconde
