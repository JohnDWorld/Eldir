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

Ce que ça ne change pas : le CLI Claude tourne dans ce conteneur, donc une
session peut lire la clé privée. Le bouton rend l'accès facile à ouvrir, pas
plus sûr. La protection reste le compte dédié sans sudo, côté machine.
"""

from __future__ import annotations

import asyncio
import os
import re
import shlex
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
        conteneur la verrait, et une session tourne dans ce conteneur).
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
        bloc = (
            f"{_DEBUT.format(project_id=project_id)}\n"
            f"Host {alias}\n"
            f"    HostName {host}\n"
            f"    User {user}\n"
            f"    Port {port}\n"
            f"    IdentityFile {self.key_path(project_id)}\n"
            f"    IdentitiesOnly yes\n"
            # Première connexion : on fait confiance à l'empreinte vue, puis on
            # la fige. Si elle change ensuite, la connexion échoue au lieu de
            # passer en silence.
            f"    StrictHostKeyChecking accept-new\n"
            f"    UserKnownHostsFile {self._home() / 'known_hosts'}\n"
            f"{_FIN.format(project_id=project_id)}\n"
        )
        self._replace_block(project_id, bloc)

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
