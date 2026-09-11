"""CollectService - ramener ce que la session doit lire mais qui n'est pas dans le repo.

Le cas qui a motivé ça : une passerelle dont le code vit dans une image
Docker sur un autre serveur, pas dans le repo. La session a fait l'audit,
conclu qu'elle ne pouvait pas coder à l'aveugle, et s'est arrêtée. Elle avait
raison.

La réponse évidente serait de donner un accès SSH à l'agent. Elle est
mauvaise : les sessions tournent en `bypassPermissions`, un agent qui peut
ouvrir un shell distant peut tout faire sur la machine de prod, et le
garde-fou « pas de publication sans accord humain » ne vaut plus rien.

Donc le projet **déclare** ce qu'il faut ramener, une commande par fichier,
dans son Mission Template. Eldir les lance à la création de session et dépose
le résultat ici :

    /var/eldir/collectes/<project_id>/            ← $ELDIR_COLLECTE
    /var/eldir/collectes/<project_id>/collecte.log

Trois propriétés qui comptent :

- **hors du worktree** : un fichier de prod rapatrié ne peut pas partir dans
  un commit, même si l'agent le voulait ;
- **déclaré** : ce qui sort d'un serveur se lit dans le template, se relit et
  se versionne, au lieu de dépendre de ce qu'un agent a improvisé ;
- **jamais fatal** : une collecte qui échoue n'empêche pas la session de
  démarrer, elle laisse une trace dans `collecte.log` que l'agent lit et
  remonte dans son compte rendu.

La clé SSH, elle, reste lisible par l'agent (le CLI Claude tourne dans ce
conteneur). C'est côté machine distante que ça se verrouille : compte dédié,
`command=` forcé dans `authorized_keys`. Cf. `docs/acces-serveur.md`.
"""

from __future__ import annotations

import asyncio
import shutil
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.core.config import Settings, get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)

_LOG_FILE = "collecte.log"


def _ouvrir(cible: Path):  # type: ignore[no-untyped-def]
    return cible.open("wb")


def _reinitialiser(root: Path) -> None:
    # Repartir propre : un fichier laissé par une collecte précédente, que la
    # commande ne produit plus, serait lu comme s'il était à jour.
    shutil.rmtree(root, ignore_errors=True)
    root.mkdir(parents=True, exist_ok=True)


def _ecrire_log(root: Path, lignes: list[str]) -> None:
    (root / _LOG_FILE).write_text("\n".join(lignes) + "\n", encoding="utf-8")


def _supprimer(cible: Path) -> None:
    cible.unlink(missing_ok=True)


def _taille(cible: Path) -> int:
    return cible.stat().st_size


class CollectService:
    def root(self, project_id: str) -> Path:
        return get_settings().collectes_root / project_id

    def env_for(self, project_id: str | None) -> dict[str, str]:
        """Variable à passer aux sessions du projet, vide si rien n'a été collecté.

        Pas de variable plutôt qu'un dossier vide : un `$ELDIR_COLLECTE` qui
        pointe vers rien ferait croire à l'agent que la collecte a eu lieu et
        n'a rien donné.
        """
        if not project_id:
            return {}
        root = self.root(project_id)
        if not (root / _LOG_FILE).exists():
            return {}
        return {"ELDIR_COLLECTE": str(root)}

    async def run(self, project_id: str, entries: list[dict[str, Any]] | None) -> None:
        """Lance les commandes déclarées, une par une, et écrit les fichiers.

        Ne lève jamais : la collecte est un confort pour la session, pas une
        condition de son démarrage.
        """
        if not entries:
            return
        settings = get_settings()
        root = self.root(project_id)
        await asyncio.to_thread(_reinitialiser, root)

        lignes = [f"# collecte du {datetime.now(UTC).isoformat(timespec='seconds')}"]
        for entry in entries:
            fichier = str(entry.get("fichier") or "").strip()
            commande = str(entry.get("commande") or "").strip()
            # Validé côté schema à l'écriture du template ; revérifié ici
            # parce que la valeur vient de la base et finit en chemin.
            if not fichier or not commande or "/" in fichier or fichier.startswith("."):
                lignes.append(f"! entrée ignorée (nom de fichier invalide) : {fichier!r}")
                continue
            lignes.append(await self._one(root / fichier, commande, settings))

        await asyncio.to_thread(_ecrire_log, root, lignes)

    async def _one(self, cible: Path, commande: str, settings: Settings) -> str:
        """Une commande, un fichier. Renvoie la ligne de log correspondante."""
        # `ulimit -f` en blocs de 512 octets : la commande est tuée si elle
        # dépasse, plutôt que de remplir le disque du serveur.
        blocs = settings.collect_max_file_mb * 1024 * 1024 // 512
        prelude = f"set -o pipefail\nulimit -f {blocs}\n"
        try:
            sortie = await asyncio.to_thread(_ouvrir, cible)
        except OSError as exc:  # pragma: no cover - disque plein, chemin illisible
            logger.warning("collecte.io.error", fichier=cible.name, exc_info=True)
            return f"! {cible.name} : {exc}"

        try:
            proc = await asyncio.create_subprocess_shell(
                prelude + commande,
                stdout=sortie,
                stderr=asyncio.subprocess.PIPE,
                executable="/bin/bash",
            )
            try:
                _, stderr = await asyncio.wait_for(
                    proc.communicate(), timeout=settings.collect_timeout_s
                )
            except TimeoutError:
                proc.kill()
                await asyncio.to_thread(_supprimer, cible)
                return f"! {cible.name} : délai de {settings.collect_timeout_s}s dépassé"
        finally:
            sortie.close()

        if proc.returncode != 0:
            # Un fichier à moitié écrit qui ressemble à du code source est
            # pire qu'un fichier absent : l'agent le lirait pour argent
            # comptant.
            await asyncio.to_thread(_supprimer, cible)
            erreur = (stderr or b"").decode("utf-8", "replace").strip()[:500]
            logger.info("collecte.echec", fichier=cible.name, code=proc.returncode)
            return f"! {cible.name} : code {proc.returncode} · {erreur or 'aucun détail'}"

        taille = await asyncio.to_thread(_taille, cible)
        if taille == 0:
            await asyncio.to_thread(_supprimer, cible)
            return f"! {cible.name} : la commande n'a rien produit"
        return f"✓ {cible.name} · {taille} octets"


collect_service = CollectService()
