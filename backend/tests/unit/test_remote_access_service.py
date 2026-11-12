"""Tests du RemoteAccessService : la config SSH qu'Eldir s'écrit à lui-même.

Rien ici n'ouvre de connexion. Ce qui est vérifié, c'est ce qui casserait
silencieusement : un projet qui écrase le bloc d'un autre, une révocation qui
efface la config du voisin, une clé générée sans le commentaire qui permet de
la retrouver dans un `authorized_keys` distant.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from app.core.config import get_settings
from app.core.exceptions import EldirError
from app.services.remote_access_service import RemoteAccessService, _alias_for, bloc_ssh
from structlog.testing import capture_logs

UN = "projet-un"
DEUX = "projet-deux"


@pytest.fixture
def ssh_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    home = tmp_path / "ssh"
    monkeypatch.setenv("SSH_HOME", str(home))
    get_settings.cache_clear()
    yield home
    monkeypatch.delenv("SSH_HOME", raising=False)
    get_settings.cache_clear()


@pytest.fixture
def maisons(ssh_home: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """La racine des maisons `.claude`, où vit la matière SSH des sessions."""
    racine = tmp_path / "maisons"
    monkeypatch.setenv("CLAUDE_HOME_ROOT", str(racine))
    get_settings.cache_clear()
    return racine


@pytest.fixture
def sans_umask():
    """Le umask ambiant ne doit pas faire passer un test de droits à tort.

    Sous un umask serré, un fichier créé sans `chmod` sort quand même en 600 :
    sans ce témoin, retirer le chmod laisserait le test au vert.
    """
    ancien = os.umask(0)
    yield
    os.umask(ancien)


def _ecrire_cle_factice(service: RemoteAccessService, project_id: str) -> None:
    """Une clé privée factice au bon endroit, pour ne pas appeler `ssh-keygen`."""
    cle = service.key_path(project_id)
    cle.parent.mkdir(parents=True, exist_ok=True)
    cle.write_text(f"cle-factice-{project_id}", encoding="utf-8")
    os.chmod(cle, 0o600)


def test_sans_configuration_il_n_y_a_pas_de_machine(ssh_home: Path) -> None:
    assert RemoteAccessService().status(UN).configured is False


def test_ecrire_puis_relire(ssh_home: Path) -> None:
    service = RemoteAccessService()
    service._write_block(UN, _alias_for("mon-repo"), "192.0.2.10", "deploy", 2222)

    state = service.status(UN)
    assert state.configured is True
    assert state.alias == "eldir-mon-repo"
    assert state.host == "192.0.2.10"
    assert state.user == "deploy"
    assert state.port == 2222


def test_deux_projets_cohabitent(ssh_home: Path) -> None:
    """Un projet ne doit pas écraser le bloc d'un autre."""
    service = RemoteAccessService()
    service._write_block(UN, "eldir-un", "192.0.2.10", "deploy", 22)
    service._write_block(DEUX, "eldir-deux", "192.0.2.11", "autre", 22)

    assert service.status(UN).host == "192.0.2.10"
    assert service.status(DEUX).host == "192.0.2.11"


def test_reconfigurer_remplace_au_lieu_d_empiler(ssh_home: Path) -> None:
    service = RemoteAccessService()
    service._write_block(UN, "eldir-un", "192.0.2.10", "deploy", 22)
    service._write_block(UN, "eldir-un", "192.0.2.99", "deploy", 22)

    assert service.status(UN).host == "192.0.2.99"
    assert (ssh_home / "config").read_text().count("Host eldir-un") == 1


def test_oublier_n_efface_que_le_bon_projet(ssh_home: Path) -> None:
    service = RemoteAccessService()
    service._write_block(UN, "eldir-un", "192.0.2.10", "deploy", 22)
    service._write_block(DEUX, "eldir-deux", "192.0.2.11", "autre", 22)

    service._forget(UN)

    assert service.status(UN).configured is False
    assert service.status(DEUX).host == "192.0.2.11"


async def test_la_cle_porte_l_id_du_projet(ssh_home: Path) -> None:
    """Le commentaire de la clé est ce qu'on cherchera pour la révoquer."""
    service = RemoteAccessService()
    await service._ensure_key(UN)

    cle = service.key_path(UN)
    assert cle.exists()
    assert oct(cle.stat().st_mode)[-3:] == "600"
    assert f"eldir-{UN}" in cle.with_suffix(".pub").read_text()


async def test_la_cle_n_est_generee_qu_une_fois(ssh_home: Path) -> None:
    service = RemoteAccessService()
    await service._ensure_key(UN)
    empreinte = service.key_path(UN).read_bytes()

    await service._ensure_key(UN)
    assert service.key_path(UN).read_bytes() == empreinte


async def test_oublier_supprime_la_paire_de_cles(ssh_home: Path) -> None:
    service = RemoteAccessService()
    await service._ensure_key(UN)
    service._forget(UN)

    assert not service.key_path(UN).exists()
    assert not service.key_path(UN).with_suffix(".pub").exists()


def test_l_alias_reste_utilisable_meme_avec_un_slug_bizarre() -> None:
    assert _alias_for("Mon Village Viking") == "eldir-mon-village-viking"
    assert _alias_for("--") == "eldir-projet"


def test_le_bloc_ssh_est_une_fonction_pure() -> None:
    """Le même générateur sert le `config` partagé et celui d'une session.

    Dupliquer la génération, c'est accepter qu'un durcissement n'arrive que
    dans une des deux copies.
    """
    bloc = bloc_ssh(
        project_id="p1",
        alias="eldir-projet",
        host="machine.exemple.lan",
        user="deploy",
        port=2222,
        identity_file=Path("/eldir/ssh/cle"),
        known_hosts=Path("/eldir/maison/known_hosts"),
    )

    assert "Host eldir-projet" in bloc
    assert "HostName machine.exemple.lan" in bloc
    assert "Port 2222" in bloc
    assert "IdentityFile /eldir/ssh/cle" in bloc
    assert "UserKnownHostsFile /eldir/maison/known_hosts" in bloc
    assert "IdentitiesOnly yes" in bloc
    assert "StrictHostKeyChecking accept-new" in bloc


def test_le_config_d_une_session_ne_porte_que_son_projet(
    ssh_home: Path, maisons: Path, sans_umask: None
) -> None:
    """Un seul bloc, et pas l'inventaire des machines des autres projets.

    C'est le vrai trou de l'accès distant : la clé était déjà par projet, le
    `config` ne l'était pas.
    """
    service = RemoteAccessService()
    # deux projets configurés dans le `config` partagé
    _ecrire_cle_factice(service, "p1")
    _ecrire_cle_factice(service, "p2")
    service._write_block("p1", "eldir-un", "un.exemple.lan", "deploy", 22)
    service._write_block("p2", "eldir-deux", "deux.exemple.lan", "root", 2222)

    sous_chemin = service.materiel_de_session("p1", "s1")

    assert sous_chemin == "p1-ssh/s1"
    dossier = maisons / sous_chemin
    config = (dossier / "config").read_text(encoding="utf-8")
    assert "un.exemple.lan" in config
    assert "deux.exemple.lan" not in config
    assert "eldir-deux" not in config
    # les chemins sont ceux du conteneur, pas ceux du backend
    assert "IdentityFile /eldir/ssh/cle" in config
    assert str(ssh_home) not in config
    # la clé est copiée, et seule son propriétaire peut la lire ou entrer
    assert (dossier / "cle").read_text(encoding="utf-8") == "cle-factice-p1"
    assert oct((dossier / "cle").stat().st_mode)[-3:] == "600"
    assert oct(dossier.stat().st_mode)[-3:] == "700"


def test_une_copie_deja_la_est_resserree_en_600(maisons: Path, sans_umask: None) -> None:
    """`O_CREAT` garde le mode d'un fichier existant : le code doit le refixer."""
    service = RemoteAccessService()
    _ecrire_cle_factice(service, "p1")
    service._write_block("p1", "eldir-un", "un.exemple.lan", "deploy", 22)
    ancienne = maisons / "p1-ssh" / "s1" / "cle"
    ancienne.parent.mkdir(parents=True)
    ancienne.write_text("copie-perimee", encoding="utf-8")
    os.chmod(ancienne, 0o666)  # noqa: S103 (c'est le cas à resserrer)

    service.materiel_de_session("p1", "s1")

    assert ancienne.read_text(encoding="utf-8") == "cle-factice-p1"
    assert oct(ancienne.stat().st_mode)[-3:] == "600"


def test_sans_acces_distant_il_n_y_a_pas_de_materiel(maisons: Path) -> None:
    """Le projet n'a pas de clé du tout dans son conteneur."""
    assert RemoteAccessService().materiel_de_session("p1", "s1") is None
    assert not maisons.exists()


def test_le_materiel_disparait_a_l_arret(maisons: Path) -> None:
    service = RemoteAccessService()
    _ecrire_cle_factice(service, "p1")
    service._write_block("p1", "eldir-un", "un.exemple.lan", "deploy", 22)
    sous_chemin = service.materiel_de_session("p1", "s1")
    autre = service.materiel_de_session("p1", "s2")
    assert sous_chemin is not None
    assert autre is not None

    service.supprimer_materiel_de_session("p1", "s1")

    assert not (maisons / sous_chemin).exists()
    # la session voisine du même projet garde la sienne
    assert (maisons / autre / "cle").exists()
    # idempotent : un arrêt après un crash ne doit ni lever ni crier à l'anomalie,
    # il n'y avait simplement rien à supprimer
    with capture_logs() as journal:
        service.supprimer_materiel_de_session("p1", "s1")
    assert journal == []


def test_une_cle_disparue_est_signalee_et_non_avalee(maisons: Path) -> None:
    """Configuré mais sans clé : pas de SSH dans la session, et on le dit."""
    service = RemoteAccessService()
    service._write_block("p1", "eldir-un", "un.exemple.lan", "deploy", 22)

    # `capture_logs` ne voit ce logger que s'il n'a jamais été mis en cache.
    # `configure_logging()` est le seul endroit qui pose
    # `cache_logger_on_first_use=True`, et il ne tourne que dans un test qui
    # remet ensuite `structlog.reset_defaults()`. Un futur test qui lance le
    # lifespan, ou appelle `configure_logging()` sans réinitialiser, laisserait
    # un logger en cache avec d'anciens processeurs : `journal` resterait vide.
    with capture_logs() as journal:
        assert service.materiel_de_session("p1", "s1") is None

    assert [(e["event"], e["log_level"], e["project_id"]) for e in journal] == [
        ("remote.materiel.cle_absente", "warning", "p1")
    ]
    assert not maisons.exists()


def test_un_identifiant_vide_ne_peut_pas_viser_le_dossier_du_projet(maisons: Path) -> None:
    """`rmtree` sur un chemin qui remonterait d'un niveau efface les autres sessions."""
    service = RemoteAccessService()
    _ecrire_cle_factice(service, "p1")
    service._write_block("p1", "eldir-un", "un.exemple.lan", "deploy", 22)
    sous_chemin = service.materiel_de_session("p1", "s1")
    assert sous_chemin is not None

    for mauvais in ("", ".", "..", "a/b"):
        with pytest.raises(EldirError):
            service.supprimer_materiel_de_session("p1", mauvais)
    with pytest.raises(EldirError):
        service.supprimer_materiel_de_session("", "s1")
    # `status("")` rend le bloc du premier projet venu (le marqueur vide les
    # préfixe tous). Sans la garde, `read_bytes` échouerait sur le dossier des
    # clés avant qu'un `config` soit écrit, mais après avoir créé un dossier
    # parasite et par une erreur qui n'a rien de claire : la garde est ce qui
    # lève une `EldirError` nette et ne laisse rien derrière.
    with pytest.raises(EldirError):
        service.materiel_de_session("", "s1")

    assert (maisons / sous_chemin / "cle").exists()
    assert [d.name for d in maisons.iterdir()] == ["p1-ssh"]
    assert [d.name for d in (maisons / "p1-ssh").iterdir()] == ["s1"]


def test_une_suppression_impossible_n_arrete_pas_la_session_mais_se_voit(
    maisons: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Une copie de clé privée non effacée ne doit pas passer sous silence."""
    service = RemoteAccessService()
    _ecrire_cle_factice(service, "p1")
    service._write_block("p1", "eldir-un", "un.exemple.lan", "deploy", 22)
    assert service.materiel_de_session("p1", "s1") is not None

    def refuse(_chemin: Path) -> None:
        raise PermissionError("refuse")

    monkeypatch.setattr("app.services.remote_access_service.shutil.rmtree", refuse)
    with capture_logs() as journal:
        service.supprimer_materiel_de_session("p1", "s1")

    assert [(e["event"], e["log_level"]) for e in journal] == [
        ("remote.materiel.suppression_impossible", "warning")
    ]


async def test_executer_lance_la_commande_par_l_alias_et_rend_code_et_sortie(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Un faux `ssh` en tête du PATH : il rend ses arguments et sort en 3."""
    faux = tmp_path / "bin"
    faux.mkdir()
    ssh = faux / "ssh"
    ssh.write_text('#!/bin/sh\necho "$@"\nexit 3\n')
    ssh.chmod(0o755)
    monkeypatch.setenv("PATH", f"{faux}:{os.environ['PATH']}")
    monkeypatch.setattr(get_settings(), "ssh_home", tmp_path / "ssh")

    code, sortie = await RemoteAccessService().executer(
        "eldir-demo", "cd /srv/demo && ./deploy.sh", timeout_s=10
    )

    assert code == 3
    assert "BatchMode=yes" in sortie
    assert "eldir-demo" in sortie
    assert "cd /srv/demo && ./deploy.sh" in sortie


async def test_executer_tue_une_commande_trop_longue(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    faux = tmp_path / "bin"
    faux.mkdir()
    ssh = faux / "ssh"
    ssh.write_text("#!/bin/sh\nsleep 5\n")
    ssh.chmod(0o755)
    monkeypatch.setenv("PATH", f"{faux}:{os.environ['PATH']}")
    monkeypatch.setattr(get_settings(), "ssh_home", tmp_path / "ssh")

    code, _ = await RemoteAccessService().executer("eldir-demo", "./deploy.sh", timeout_s=0.2)

    assert code is None
