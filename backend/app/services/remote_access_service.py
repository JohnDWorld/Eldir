"""RemoteAccessService - brancher un projet sur la machine où il tourne.

Demander à John d'écrire lui-même un `~/.ssh/config` et de le monter en
lecture seule marchait, mais c'est une corvée par projet et ça oblige à
sortir d'Eldir pour faire une chose qu'Eldir peut faire.

Donc un bouton. John donne l'adresse et le nom d'utilisateur ; Eldir génère
une clé dédiée à ce projet, la dépose sur la machine (mot de passe demandé
**une seule fois**, pour cette requête, jamais stocké ni journalisé), écrit
son bloc de configuration et vérifie que la connexion passe en clé seule.

Trois décisions qui structurent le reste :

- **Une clé par projet**, pas une clé Eldir unique : révoquer l'accès d'un
  projet ne casse pas les autres, et la ligne déposée sur la machine porte
  l'id du projet en commentaire, donc on sait exactement quoi retirer.
- **La config SSH est la source de vérité**, pas la base. L'adresse et
  l'utilisateur se relisent dans le bloc du projet. Rien à resynchroniser
  entre un dossier et une table, même raisonnement que pour les toolchains.
- **La suppression révoque.** Retirer un projet d'Eldir retire la clé du
  `authorized_keys` distant. Une clé qu'on sait déposer et pas retirer, c'est
  une clé oubliée sur une machine.

Ce que ça ne change pas : le bouton rend l'accès facile à ouvrir, pas plus sûr.
Ce que la session peut lire de la clé dépend du mode d'exécution des sessions
(`SESSION_RUNTIME`) :

- en mode `processus`, le CLI Claude tourne dans le conteneur du backend, donc
  une session peut lire toutes les clés privées et le `config` entier ;
- en mode `conteneur` (le défaut), il tourne dans un conteneur à part, qui ne
  voit que la copie de la clé de son propre projet, montée en lecture seule, et
  un `config` à un seul bloc (cf. `materiel_de_session`). Les clés et les
  machines des autres projets n'y existent pas. Cette clé-là, la session la
  lit toujours : c'est avec elle qu'elle se connecte.

Dans les deux modes, la protection de la machine reste le compte dédié sans
sudo, côté machine.
"""

from __future__ import annotations

import asyncio
import contextlib
import os
import re
import shlex
import shutil
import signal
from dataclasses import dataclass
from pathlib import Path

from app.core.config import get_settings
from app.core.exceptions import EldirError
from app.core.logging import get_logger

logger = get_logger(__name__)

_CONFIG_FILE = "config"
_KEYS_DIRNAME = "projects"
# Les blocs des autres projets, et tout ce que John aurait écrit à la main,
# ne sont jamais touchés : on ne réécrit que ce qui est entre ces marqueurs.
_DEBUT = "# >>> eldir:{project_id}"
_FIN = "# <<< eldir:{project_id}"

# Où la session voit sa matière SSH, côté conteneur. L'image y branche son
# `Include` (cf. backend/docker/session/Dockerfile) ; l'enrobage y monte le dossier en
# lecture seule. Le dossier (0700) et la clé (0600) appartiennent à l'uid du
# backend : le montage n'est lisible que parce que le conteneur tourne avec ce
# même uid, sans quoi la session aurait une erreur de permission sans
# explication.
CLE_DANS_LE_CONTENEUR = Path("/eldir/ssh/cle")
CONFIG_DANS_LE_CONTENEUR = Path("/eldir/ssh/config")
# Dans la maison, donc en écriture et persistant par projet : `accept-new`
# doit pouvoir figer l'empreinte vue à la première connexion.
KNOWN_HOSTS_DANS_LE_CONTENEUR = Path("/eldir/maison/known_hosts")


@dataclass(slots=True, frozen=True)
class RemoteStatus:
    configured: bool
    alias: str | None = None
    host: str | None = None
    user: str | None = None
    port: int = 22
    # None = pas encore testé dans cet appel.
    connected: bool | None = None
    detail: str | None = None


def _preparer_dossier(dossier: Path) -> None:
    dossier.mkdir(parents=True, exist_ok=True)
    os.chmod(dossier, 0o700)


def _proteger(fichier: Path) -> None:
    os.chmod(fichier, 0o600)


def _alias_for(slug: str) -> str:
    """Alias SSH d'un projet. Préfixé pour ne pas écraser un Host à John."""
    propre = re.sub(r"[^a-z0-9-]+", "-", slug.lower()).strip("-") or "projet"
    return f"eldir-{propre}"


def bloc_ssh(
    *,
    project_id: str,
    alias: str,
    host: str,
    user: str,
    port: int,
    identity_file: Path,
    known_hosts: Path,
) -> str:
    """Un bloc `Host` de config SSH, délimité par les marqueurs du projet.

    Pure, et partagée par les deux usages : le `config` unique du backend, qui
    porte un bloc par projet, et le `config` à un seul bloc monté dans le
    conteneur d'une session. Les chemins diffèrent entre les deux (la clé est
    à `/eldir/ssh/cle` dans le conteneur), donc ils sont des paramètres et pas
    des dérivations.
    """
    return (
        f"{_DEBUT.format(project_id=project_id)}\n"
        f"Host {alias}\n"
        f"    HostName {host}\n"
        f"    User {user}\n"
        f"    Port {port}\n"
        f"    IdentityFile {identity_file}\n"
        f"    IdentitiesOnly yes\n"
        # Première connexion : on fait confiance à l'empreinte vue, puis on
        # la fige. Si elle change ensuite, la connexion échoue au lieu de
        # passer en silence.
        f"    StrictHostKeyChecking accept-new\n"
        f"    UserKnownHostsFile {known_hosts}\n"
        f"{_FIN.format(project_id=project_id)}\n"
    )


class RemoteAccessService:
    # ── chemins ─────────────────────────────────────────────────
    def _home(self) -> Path:
        return get_settings().ssh_home

    def _config_path(self) -> Path:
        return self._home() / _CONFIG_FILE

    def key_path(self, project_id: str) -> Path:
        return self._home() / _KEYS_DIRNAME / project_id

    # ── lecture ─────────────────────────────────────────────────
    def status(self, project_id: str) -> RemoteStatus:
        """Ce que dit la config SSH, sans ouvrir de connexion."""
        bloc = self._read_block(project_id)
        if bloc is None:
            return RemoteStatus(configured=False)
        return RemoteStatus(
            configured=True,
            alias=_champ(bloc, "Host"),
            host=_champ(bloc, "HostName"),
            user=_champ(bloc, "User"),
            port=int(_champ(bloc, "Port") or 22),
        )

    def _read_block(self, project_id: str) -> str | None:
        path = self._config_path()
        if not path.exists():
            return None
        contenu = path.read_text(encoding="utf-8")
        debut, fin = _DEBUT.format(project_id=project_id), _FIN.format(project_id=project_id)
        if debut not in contenu or fin not in contenu:
            return None
        return contenu.split(debut, 1)[1].split(fin, 1)[0]

    # ── écriture ────────────────────────────────────────────────
    async def connect(
        self,
        *,
        project_id: str,
        slug: str,
        host: str,
        user: str,
        port: int,
        password: str | None,
    ) -> RemoteStatus:
        """Génère la clé au besoin, l'installe, et vérifie la connexion.

        Le mot de passe ne sert qu'ici, transmis par variable d'environnement
        pour ne pas apparaître dans la ligne de commande (un `ps` dans le
        conteneur la verrait, et en mode `processus` une session tourne dans
        ce conteneur).
        """
        alias = _alias_for(slug)
        await self._ensure_key(project_id)
        await asyncio.to_thread(self._write_block, project_id, alias, host, user, port)

        ok, detail = await self._test(alias)
        if ok:
            return RemoteStatus(
                configured=True, alias=alias, host=host, user=user, port=port, connected=True
            )

        if not password:
            return RemoteStatus(
                configured=True,
                alias=alias,
                host=host,
                user=user,
                port=port,
                connected=False,
                detail=(
                    "La connexion par clé ne passe pas encore. Donne le mot de "
                    "passe du compte pour cette première connexion : il servira "
                    "à déposer la clé, et ne sera ni stocké ni journalisé."
                ),
            )

        await self._install_key(project_id, host=host, user=user, port=port, password=password)
        ok, detail = await self._test(alias)
        return RemoteStatus(
            configured=True,
            alias=alias,
            host=host,
            user=user,
            port=port,
            connected=ok,
            detail=None if ok else detail,
        )

    async def _ensure_key(self, project_id: str) -> None:
        cle = self.key_path(project_id)
        if await asyncio.to_thread(cle.exists):
            return
        await asyncio.to_thread(_preparer_dossier, cle.parent)
        # Le commentaire porte l'id du projet : c'est lui qu'on cherchera dans
        # le `authorized_keys` distant au moment de révoquer.
        proc = await asyncio.create_subprocess_exec(
            "ssh-keygen",
            "-q",
            "-t",
            "ed25519",
            "-N",
            "",
            "-C",
            f"eldir-{project_id}",
            "-f",
            str(cle),
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.PIPE,
        )
        _, erreur = await proc.communicate()
        if proc.returncode != 0:
            detail = (erreur or b"").decode("utf-8", "replace").strip()[:200]
            raise EldirError(f"Génération de la clé SSH impossible : {detail or 'sans détail'}")
        await asyncio.to_thread(_proteger, cle)

    def _write_block(self, project_id: str, alias: str, host: str, user: str, port: int) -> None:
        self._replace_block(
            project_id,
            bloc_ssh(
                project_id=project_id,
                alias=alias,
                host=host,
                user=user,
                port=port,
                identity_file=self.key_path(project_id),
                known_hosts=self._home() / "known_hosts",
            ),
        )

    # ── matière SSH d'une session en conteneur ───────────────────
    def _dossier_de_session(self, project_id: str, session_id: str) -> Path:
        """Frère de la maison du projet, et pas dedans.

        La maison est montée en écriture (le CLI y écrit son transcript) :
        tout ce qui est dedans est réécrivable par la session, et un `config`
        réécrivable n'est plus une garde. Le sous-chemin est donc voisin.
        """
        # `supprimer_materiel_de_session` fait un `rmtree` sur ce chemin. Un
        # composant vide le ferait remonter d'un niveau et emporterait la
        # matière de toutes les sessions du projet. Les deux composants
        # viennent d'UUID générés par le serveur, donc le cas n'arrive pas :
        # la garde est ici précisément parce que la seule chose qui l'empêche
        # aujourd'hui est une convention, et qu'une convention ne survit pas à
        # un appelant distrait.
        for composant in (project_id, session_id):
            if not composant or "/" in composant or composant in (".", ".."):
                raise EldirError(
                    f"Identifiant inutilisable dans un chemin de session : {composant!r}"
                )
        return get_settings().claude_home_root / f"{project_id}-ssh" / session_id

    def materiel_de_session(self, project_id: str, session_id: str) -> str | None:
        """Écrit la clé et le `config` à un seul bloc, rend le sous-chemin à monter.

        Rend `None` quand le projet n'a pas d'accès distant : la session n'a
        alors aucune clé, pas même la sienne.

        La clé est recopiée, pas montée depuis `ssh_home` : le `src` d'un bind
        mount est résolu par le démon sur l'hôte, où le chemin du conteneur
        backend n'existe pas, et `volume-subpath` ne monte pas un fichier
        seul. La copie est refaite à chaque démarrage, donc jamais périmée.
        """
        etat = self.status(project_id)
        if not etat.configured or not etat.alias:
            return None
        source = self.key_path(project_id)
        if not source.exists():
            # Le projet a un accès configuré mais sa clé a disparu : la session
            # démarrera sans SSH, et « Connecter au serveur » cessera de marcher
            # sans autre signe. Ce module est le seul à le savoir, donc il le dit.
            logger.warning("remote.materiel.cle_absente", project_id=project_id, chemin=str(source))
            return None

        dossier = self._dossier_de_session(project_id, session_id)
        _preparer_dossier(dossier)
        cible = dossier / CLE_DANS_LE_CONTENEUR.name
        # Pas de `shutil.copyfile` : il ne copie pas les droits, donc le mode de
        # la copie dépendrait du umask ambiant. On demande 0600 à la création :
        # l'umask ne peut que retirer des bits, jamais en ajouter.
        donnees = source.read_bytes()
        descripteur = os.open(cible, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        # Le mode passé à `os.open` est masqué par l'umask, et `O_CREAT` sans
        # `O_EXCL` garde celui d'un fichier qui existe déjà : on le fixe donc
        # sur le descripteur, où il vaut exactement 600 quel que soit l'umask
        # et l'état précédent du fichier, sans chemin à courir derrière. Une
        # copie préexistante plus large le reste entre `O_TRUNC` et `fchmod`,
        # mais elle est alors vide : aucun octet de clé n'est écrit avant le
        # `fchmod`. Il est dans le `with` pour que le descripteur soit fermé même
        # s'il lève. Pas de garde autour de `os.fdopen` : s'il échoue, le
        # processus manque de descripteurs ou de mémoire, et un démarrage de
        # session qui échoue bruyamment est alors le bon résultat.
        with os.fdopen(descripteur, "wb") as fichier:
            os.fchmod(fichier.fileno(), 0o600)
            fichier.write(donnees)
        (dossier / CONFIG_DANS_LE_CONTENEUR.name).write_text(
            bloc_ssh(
                project_id=project_id,
                alias=etat.alias,
                host=etat.host or "",
                user=etat.user or "",
                port=etat.port or 22,
                identity_file=CLE_DANS_LE_CONTENEUR,
                known_hosts=KNOWN_HOSTS_DANS_LE_CONTENEUR,
            ),
            encoding="utf-8",
        )
        racine = get_settings().claude_home_root
        return str(dossier.relative_to(racine))

    def supprimer_materiel_de_session(self, project_id: str, session_id: str) -> None:
        """Efface la copie de clé et le `config` d'une session arrêtée.

        Idempotent : un arrêt qui suit un crash ne doit pas lever.
        """
        dossier = self._dossier_de_session(project_id, session_id)
        try:
            shutil.rmtree(dossier)
        except FileNotFoundError:
            # Un arrêt qui suit un crash : il n'y a rien à supprimer, et ce
            # n'est pas une anomalie.
            pass
        except OSError:
            # Une copie de clé privée qu'on n'a pas pu effacer ne doit pas
            # faire échouer l'arrêt de la session, mais elle ne doit pas
            # disparaître des logs non plus.
            logger.warning(
                "remote.materiel.suppression_impossible",
                project_id=project_id,
                dossier=str(dossier),
                exc_info=True,
            )

    def _replace_block(self, project_id: str, bloc: str) -> None:
        path = self._config_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        os.chmod(path.parent, 0o700)
        contenu = path.read_text(encoding="utf-8") if path.exists() else ""
        debut, fin = _DEBUT.format(project_id=project_id), _FIN.format(project_id=project_id)
        if debut in contenu and fin in contenu:
            avant = contenu.split(debut, 1)[0]
            apres = contenu.split(fin, 1)[1].lstrip("\n")
            contenu = avant + apres
        contenu = contenu.rstrip("\n")
        contenu = f"{contenu}\n\n{bloc}" if contenu else bloc
        path.write_text(contenu, encoding="utf-8")
        os.chmod(path, 0o600)

    async def _install_key(
        self, project_id: str, *, host: str, user: str, port: int, password: str
    ) -> None:
        pub = self.key_path(project_id).with_suffix(".pub")
        commande = (
            f"sshpass -e ssh-copy-id -i {shlex.quote(str(pub))} "
            f"-o StrictHostKeyChecking=accept-new "
            f"-o UserKnownHostsFile={shlex.quote(str(self._home() / 'known_hosts'))} "
            f"-o PreferredAuthentications=password -o PubkeyAuthentication=no "
            f"-p {port} {shlex.quote(f'{user}@{host}')}"
        )
        # `sshpass -e` lit SSHPASS dans l'environnement : le mot de passe
        # n'apparaît pas dans la ligne de commande, donc pas dans un `ps`.
        proc = await asyncio.create_subprocess_shell(
            commande,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            env={**os.environ, "SSHPASS": password},
        )
        sortie, _ = await proc.communicate()
        if proc.returncode != 0:
            # Le message de ssh-copy-id ne contient pas le mot de passe, mais
            # on le tronque quand même plutôt que de tout recopier à l'écran.
            detail = (sortie or b"").decode("utf-8", "replace").strip()[:300]
            logger.info("remote.copyid.echec", project_id=project_id, code=proc.returncode)
            raise EldirError(f"Dépôt de la clé refusé par la machine : {detail or 'sans détail'}")
        logger.info("remote.copyid.ok", project_id=project_id)

    async def _test(self, alias: str) -> tuple[bool, str | None]:
        timeout = get_settings().ssh_connect_timeout_s
        commande = (
            f"ssh -o BatchMode=yes -o ConnectTimeout={timeout} "
            f"-F {shlex.quote(str(self._config_path()))} {shlex.quote(alias)} true"
        )
        proc = await asyncio.create_subprocess_shell(
            commande, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT
        )
        try:
            sortie, _ = await asyncio.wait_for(proc.communicate(), timeout=timeout + 5)
        except TimeoutError:
            proc.kill()
            return False, f"Pas de réponse en {timeout}s."
        if proc.returncode == 0:
            return True, None
        return False, (sortie or b"").decode("utf-8", "replace").strip()[:300] or None

    async def executer(
        self, alias: str, commande: str, *, timeout_s: float
    ) -> tuple[int | None, str]:
        """Lance une commande déclarée sur la machine d'un projet, par son alias.

        Rend (code de retour, sortie et erreurs fusionnées). `None` : la commande
        a dépassé `timeout_s` et a été tuée. La commande est passée à ssh en un
        seul argument, sans shell local : c'est le shell distant qui l'interprète.
        ssh tourne dans son propre groupe de processus, tué en entier à l'échéance.
        """
        connexion = get_settings().ssh_connect_timeout_s
        proc = await asyncio.create_subprocess_exec(
            "ssh",
            "-o",
            "BatchMode=yes",
            "-o",
            f"ConnectTimeout={connexion}",
            "-F",
            str(self._config_path()),
            alias,
            commande,
            stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            start_new_session=True,
        )
        try:
            sortie, _ = await asyncio.wait_for(proc.communicate(), timeout=timeout_s)
        except TimeoutError:
            with contextlib.suppress(ProcessLookupError):
                os.killpg(proc.pid, signal.SIGKILL)
            await proc.wait()
            return None, ""
        return proc.returncode, (sortie or b"").decode("utf-8", "replace")

    # ── suppression ─────────────────────────────────────────────
    async def revoke(self, project_id: str) -> bool:
        """Retire la clé de la machine distante, puis localement.

        Renvoie True si la ligne a pu être retirée à distance. Un échec n'est
        pas bloquant (machine éteinte, accès déjà coupé) mais il est tracé :
        c'est une clé qui reste sur une machine, John doit pouvoir le savoir.
        """
        bloc = self._read_block(project_id)
        retiree = False
        if bloc is not None:
            alias = _champ(bloc, "Host")
            if alias:
                retiree = await self._revoke_remote(project_id, alias)
        await asyncio.to_thread(self._forget, project_id)
        return retiree

    async def _revoke_remote(self, project_id: str, alias: str) -> bool:
        marqueur = f"eldir-{project_id}"
        # `grep -v` sort en 1 quand il ne reste plus rien : le `|| true` évite
        # de prendre un fichier vidé légitimement pour un échec.
        distant = (
            "f=$HOME/.ssh/authorized_keys; [ -f $f ] || exit 0; "
            f"{{ grep -v {shlex.quote(marqueur)} $f || true; }} > $f.eldir-tmp "
            "&& cat $f.eldir-tmp > $f && rm -f $f.eldir-tmp"
        )
        timeout = get_settings().ssh_connect_timeout_s
        commande = (
            f"ssh -o BatchMode=yes -o ConnectTimeout={timeout} "
            f"-F {shlex.quote(str(self._config_path()))} {shlex.quote(alias)} "
            f"{shlex.quote(distant)}"
        )
        proc = await asyncio.create_subprocess_shell(
            commande, stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL
        )
        try:
            await asyncio.wait_for(proc.wait(), timeout=timeout + 5)
        except TimeoutError:
            proc.kill()
            logger.warning("remote.revoke.timeout", project_id=project_id)
            return False
        if proc.returncode != 0:
            logger.warning("remote.revoke.echec", project_id=project_id, code=proc.returncode)
            return False
        logger.info("remote.revoke.ok", project_id=project_id)
        return True

    def _forget(self, project_id: str) -> None:
        """Efface le bloc de config et la paire de clés du projet."""
        path = self._config_path()
        if path.exists():
            contenu = path.read_text(encoding="utf-8")
            debut, fin = _DEBUT.format(project_id=project_id), _FIN.format(project_id=project_id)
            if debut in contenu and fin in contenu:
                avant = contenu.split(debut, 1)[0]
                apres = contenu.split(fin, 1)[1].lstrip("\n")
                path.write_text((avant + apres).lstrip("\n"), encoding="utf-8")
        cle = self.key_path(project_id)
        cle.unlink(missing_ok=True)
        cle.with_suffix(".pub").unlink(missing_ok=True)


def _champ(bloc: str, nom: str) -> str | None:
    for ligne in bloc.splitlines():
        depouillee = ligne.strip()
        if depouillee.lower().startswith(f"{nom.lower()} "):
            return depouillee.split(None, 1)[1].strip()
    return None


remote_access_service = RemoteAccessService()
