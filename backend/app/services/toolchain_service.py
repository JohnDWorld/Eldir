"""ToolchainService - installe les outils dont un repo a besoin, une fois.

Le conteneur backend n'embarque que git, node, python et le CLI Claude. Un
agent qui travaille sur un repo Flutter ne peut donc pas lancer
`flutter analyze`, et il le dit dans son compte rendu (`RESTE: flutter analyze
non exécuté, aucun SDK Flutter`). Tout embarquer dans l'image serait une image
de 15 Go, reconstruite à chaque déploiement, avec Flutter installé même pour
les projets Python.

Donc : chaque projet déclare ses commandes d'installation dans son Mission
Template (`setup_commands`), et elles tournent **à la demande** dans un dossier
qui lui est propre, partagé par toutes ses sessions :

    /var/eldir/toolchains/<project_id>/        ← $ELDIR_TOOLCHAIN
    /var/eldir/toolchains/<project_id>/bin/    ← ajouté au PATH des sessions

Trois garde-fous, parce que le coût doit être visible avant d'être payé :

- rien ne s'installe tout seul : il faut cliquer, et l'UI affiche le poids
  disque obtenu ;
- une seule installation à la fois sur tout le serveur (4 Go de RAM, 4 cœurs) ;
- refus si le disque libre passe sous `toolchain_min_free_gb`.

L'état vit dans le dossier lui-même (`.eldir-state.json` + `install.log`) et
pas en base : si le volume est purgé, l'état disparaît avec lui, ce qui est
exactement ce qu'on veut. Pas de table à resynchroniser avec le disque.
"""

from __future__ import annotations

import asyncio
import json
import os
import shutil
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from app.core.config import get_settings
from app.core.exceptions import EldirError
from app.core.logging import get_logger

logger = get_logger(__name__)

_STATE_FILE = ".eldir-state.json"
_LOG_FILE = "install.log"
_LOG_TAIL_CHARS = 8_000

STATUS_ABSENT = "absent"
STATUS_INSTALLING = "installing"
STATUS_INSTALLED = "installed"
STATUS_ERROR = "error"


@dataclass(slots=True, frozen=True)
class ToolchainStatus:
    status: str  # absent | installing | installed | error
    size_bytes: int | None = None
    installed_at: datetime | None = None
    # True quand les `setup_commands` du template ont changé depuis
    # l'installation : ce qui est sur disque ne correspond plus à ce qui est
    # déclaré.
    stale: bool = False
    log: str | None = None
    detail: str | None = None


class ToolchainService:
    def __init__(self) -> None:
        self._running: set[str] = set()
        # Une installation à la fois : deux `git clone` d'un SDK en parallèle
        # sur 4 cœurs et 4 Go de RAM, c'est le serveur à genoux.
        self._lock = asyncio.Lock()
        self._tasks: set[asyncio.Task[None]] = set()

    # ── chemins et environnement ────────────────────────────────
    def root(self, project_id: str) -> Path:
        return get_settings().toolchains_root / project_id

    def env_for(self, project_id: str | None) -> dict[str, str]:
        """Variables à passer aux sessions du projet.

        Vide si rien n'est installé : l'agent ne trouve pas l'outil, le signale
        dans son compte rendu, et c'est ce signal qui dit quel toolchain
        déclarer. Mieux qu'un PATH qui pointe vers du vide.
        """
        if not project_id:
            return {}
        root = self.root(project_id)
        if not (root / _STATE_FILE).exists():
            return {}
        bin_dir = root / "bin"
        return {
            "ELDIR_TOOLCHAIN": str(root),
            "PATH": f"{bin_dir}:{os.environ.get('PATH', '')}",
        }

    # ── état ────────────────────────────────────────────────────
    def status(self, project_id: str, commands: list[str] | None) -> ToolchainStatus:
        root = self.root(project_id)
        log = self._read_log(root)
        if project_id in self._running:
            return ToolchainStatus(status=STATUS_INSTALLING, log=log)

        state = self._read_state(root)
        if state is None:
            return ToolchainStatus(status=STATUS_ABSENT, log=log)

        installed_at: datetime | None = None
        raw_date = state.get("installed_at")
        if isinstance(raw_date, str):
            try:
                installed_at = datetime.fromisoformat(raw_date)
            except ValueError:
                installed_at = None

        size = state.get("size_bytes")
        stale = list(state.get("commands") or []) != list(commands or [])
        if state.get("ok") is False:
            return ToolchainStatus(
                status=STATUS_ERROR,
                size_bytes=size if isinstance(size, int) else None,
                installed_at=installed_at,
                stale=stale,
                log=log,
                detail=str(state.get("error") or "Installation en échec."),
            )
        return ToolchainStatus(
            status=STATUS_INSTALLED,
            size_bytes=size if isinstance(size, int) else None,
            installed_at=installed_at,
            stale=stale,
            log=log,
        )

    # ── installation ────────────────────────────────────────────
    def start_install(self, project_id: str, commands: list[str]) -> None:
        """Lance l'installation en tâche de fond (idempotent si déjà en cours)."""
        if not commands:
            raise EldirError("Aucune commande d'installation déclarée dans le Mission Template.")
        if project_id in self._running:
            return

        settings = get_settings()
        settings.toolchains_root.mkdir(parents=True, exist_ok=True)
        free_gb = shutil.disk_usage(settings.toolchains_root).free / 1024**3
        if free_gb < settings.toolchain_min_free_gb:
            raise EldirError(
                f"Disque presque plein : {free_gb:.1f} Go libres, seuil à "
                f"{settings.toolchain_min_free_gb} Go. Libère de la place avant "
                "d'installer un toolchain."
            )

        self._running.add(project_id)
        task = asyncio.create_task(self._run(project_id, list(commands)))
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    async def remove(self, project_id: str) -> None:
        """Supprime le toolchain du projet pour rendre le disque."""
        if project_id in self._running:
            raise EldirError("Installation en cours : réessaye quand elle est finie.")
        root = self.root(project_id)
        if root.exists():
            await asyncio.to_thread(shutil.rmtree, root, True)
        logger.info("toolchain.removed", project_id=project_id)

    async def _run(self, project_id: str, commands: list[str]) -> None:
        root = self.root(project_id)
        error: str | None = None
        try:
            async with self._lock:
                (root / "bin").mkdir(parents=True, exist_ok=True)
                await asyncio.to_thread(self._write_state, root, None)
                await self._execute(root, commands)
        except Exception as exc:  # remonté dans l'état sur disque, pas perdu
            error = str(exc) or type(exc).__name__
            logger.exception("toolchain.install.failed", project_id=project_id)
        finally:
            size = await self._measure(root)
            await asyncio.to_thread(
                self._write_state,
                root,
                {
                    "ok": error is None,
                    "error": error,
                    "commands": commands,
                    "size_bytes": size,
                    "installed_at": datetime.now(UTC).isoformat(),
                },
            )
            self._running.discard(project_id)
            logger.info(
                "toolchain.install.done",
                project_id=project_id,
                ok=error is None,
                size_bytes=size,
            )

    async def _execute(self, root: Path, commands: list[str]) -> None:
        settings = get_settings()
        env = {
            **os.environ,
            "ELDIR_TOOLCHAIN": str(root),
            "PATH": f"{root / 'bin'}:{os.environ.get('PATH', '')}",
            # Pas d'invite interactive pendant une install de fond.
            "DEBIAN_FRONTEND": "noninteractive",
            "CI": "true",
        }
        deadline = asyncio.get_running_loop().time() + settings.toolchain_install_timeout_s
        with (root / _LOG_FILE).open("w", encoding="utf-8") as fh:
            for command in commands:
                fh.write(f"$ {command}\n")
                fh.flush()
                proc = await asyncio.create_subprocess_shell(
                    # `set -o pipefail` : sans ça, `curl … | bash` renvoie le
                    # code de bash, donc 0 même quand curl s'est pris un 404,
                    # et l'installation continue sur du vide. Vu en vrai sur
                    # une install Flutter. D'où bash explicite : `sh` (dash)
                    # ne connaît pas pipefail.
                    f"set -o pipefail\n{command}",
                    cwd=str(root),
                    env=env,
                    stdout=fh,
                    stderr=asyncio.subprocess.STDOUT,
                    executable="/bin/bash",
                )
                remaining = deadline - asyncio.get_running_loop().time()
                if remaining <= 0:
                    proc.kill()
                    raise EldirError(
                        f"Installation interrompue après {settings.toolchain_install_timeout_s}s."
                    )
                try:
                    code = await asyncio.wait_for(proc.wait(), timeout=remaining)
                except TimeoutError as exc:
                    proc.kill()
                    raise EldirError(
                        f"Installation interrompue après "
                        f"{settings.toolchain_install_timeout_s}s "
                        f"(commande en cours : {command})."
                    ) from exc
                fh.write(f"\n[exit {code}]\n")
                fh.flush()
                if code != 0:
                    raise EldirError(f"La commande a échoué (exit {code}) : {command}")

    # ── disque ──────────────────────────────────────────────────
    async def _measure(self, root: Path) -> int | None:
        """Poids du toolchain sur disque, via `du` (plus rapide qu'un walk)."""
        if not await asyncio.to_thread(root.exists):
            return None
        try:
            proc = await asyncio.create_subprocess_exec(
                "du",
                "-sb",
                str(root),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL,
            )
            out, _ = await asyncio.wait_for(proc.communicate(), timeout=120)
            return int(out.split()[0])
        except Exception:  # une taille manquante n'est pas un échec d'install
            return None

    # ── état sur disque ─────────────────────────────────────────
    def _read_state(self, root: Path) -> dict | None:
        path = root / _STATE_FILE
        try:
            raw = path.read_text(encoding="utf-8")
        except OSError:
            return None
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return None
        return data if isinstance(data, dict) else None

    def _write_state(self, root: Path, state: dict | None) -> None:
        path = root / _STATE_FILE
        try:
            if state is None:
                path.unlink(missing_ok=True)
            else:
                path.write_text(json.dumps(state, indent=2), encoding="utf-8")
        except OSError:
            logger.warning("toolchain.state.write.failed", path=str(path))

    def _read_log(self, root: Path) -> str | None:
        try:
            text = (root / _LOG_FILE).read_text(encoding="utf-8", errors="replace")
        except OSError:
            return None
        return text[-_LOG_TAIL_CHARS:] if text else None


toolchain_service = ToolchainService()
