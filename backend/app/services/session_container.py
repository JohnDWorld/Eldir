"""Ce que l'enrobage a besoin de savoir pour lancer une session en conteneur.

Un seul rôle : calculer. Ce module ne lance rien, n'appelle pas Docker et
n'ouvre aucune connexion. Le lancement reste au SDK, qui exécute l'enrobage ;
l'enrobage lit ce que ce module a calculé et construit son `docker run`.

Pourquoi un module à part : les montages **sont** la décision de sécurité de
cette phase. Ici ils se testent sur un dictionnaire, sans démon, et les tests
d'intégration vérifient ensuite pour de vrai qu'un voisin est introuvable.

Deux règles qui valent pour tout ce fichier :

- **Un montage dont le sous-chemin peut ne pas exister est conditionnel, ou
  garanti par l'appelant.** `volume-subpath` sur un sous-chemin absent fait
  échouer `docker run` avec le code 127 (mesuré). Un projet sans toolchain
  installé n'a pas de dossier dans ce volume. `ELDIR_CLAUDE_HOME_SUBPATH` est
  garanti par `preparer_la_maison`, `ELDIR_SSH_SUBPATH` par la création du
  dossier SSH (cf. `env_pour_enrobage`).
- **Rien de secret ne sort d'ici.** L'enrobage n'a besoin que de noms de
  volumes et de chemins. Le credential Claude, lui, est transmis par
  l'enrobage depuis son propre environnement, sans passer par ce calcul.
"""

from __future__ import annotations

from pathlib import Path

from app.core.config import get_settings
from app.services.claude_home import maison_du_projet, sous_chemin_de_maison
from app.services.collect_service import collect_service
from app.services.toolchain_service import toolchain_service
from app.services.worktree_service import chemin_du_clone


def env_pour_enrobage(
    *,
    project_id: str | None,
    worktree_abs: Path,
    ssh_subpath: str | None,
) -> dict[str, str]:
    """Ce que l'enrobage a besoin de savoir, et rien de plus.

    Les chemins absolus sont ceux de l'hôte, et les montages les reproduisent
    à l'identique dans le conteneur : sans ça, les chemins que la session
    manipule, que les hooks inspectent et que le diff viewer affiche
    désigneraient des fichiers que le backend ne connaît pas.

    L'appelant doit avoir appelé `preparer_la_maison` pour ce projet avant :
    `ELDIR_CLAUDE_HOME_SUBPATH` est monté sans condition, et son sous-chemin
    doit exister avant le `docker run`, sans quoi il échoue en code 127.

    Un `ssh_subpath` non `None` doit déjà exister sur le disque : c'est
    `RemoteAccessService.materiel_de_session`, côté appelant, qui crée ce
    dossier et le garantit. Ce module ne le vérifie pas.
    """
    reglages = get_settings()
    # Les deux `relative_to` ci-dessous supposent worktree et clone sous
    # `workspaces_root`, vrai par construction (noms issus de `slugify` et d'UUID).
    # Un cwd hors de cette racine lève `ValueError` au démarrage, à dessein : il
    # n'y aurait aucun sous-chemin à monter, et échouer bruyamment vaut mieux que
    # deviner. `relative_to` est lexical : un segment `..` passerait, ce qui n'est
    # pas atteignable tant que les noms viennent de `slugify` et d'UUID.
    env = {
        "ELDIR_IMAGE": reglages.session_image,
        "ELDIR_NETWORK": reglages.session_network,
        "ELDIR_WORKSPACES_VOLUME": reglages.workspaces_volume,
        "ELDIR_WORKTREE_ABS": str(worktree_abs),
        "ELDIR_WORKTREE_SUBPATH": str(worktree_abs.relative_to(reglages.workspaces_root)),
        "ELDIR_CLAUDE_HOME_VOLUME": reglages.claude_home_volume,
        "ELDIR_CLAUDE_HOME_SUBPATH": sous_chemin_de_maison(project_id),
    }

    clone = chemin_du_clone(worktree_abs)
    if clone is not None:
        env["ELDIR_CLONE_ABS"] = str(clone)
        env["ELDIR_CLONE_SUBPATH"] = str(clone.relative_to(reglages.workspaces_root))

    # `env_for` rend un dictionnaire vide quand rien n'est installé ou rien
    # n'a été collecté : c'est exactement la condition du montage.
    if project_id and toolchain_service.env_for(project_id):
        env["ELDIR_TOOLCHAINS_VOLUME"] = reglages.toolchains_volume
        env["ELDIR_TOOLCHAIN_ABS"] = str(toolchain_service.root(project_id))
        env["ELDIR_TOOLCHAIN_SUBPATH"] = project_id
    if project_id and collect_service.env_for(project_id):
        env["ELDIR_COLLECTES_VOLUME"] = reglages.collectes_volume
        env["ELDIR_COLLECTE_ABS"] = str(collect_service.root(project_id))
        env["ELDIR_COLLECTE_SUBPATH"] = project_id
    if ssh_subpath is not None:
        env["ELDIR_SSH_SUBPATH"] = ssh_subpath

    return env


def preparer_la_maison(project_id: str | None) -> None:
    """Crée la maison du projet avant le premier `docker run`.

    `volume-subpath` exige que le sous-chemin existe déjà : sans ce mkdir, la
    première session d'un projet échoue au démarrage avec le code 127 du
    démon. Le dossier est créé côté backend, qui voit le même volume. Cet appel
    précède `env_pour_enrobage` pour le même projet (cf. ce dernier).

    `tmp` est créé avec : le CLI s'y calcule son temporaire
    (`CLAUDE_CODE_TMPDIR`), et un dossier créé par Docker comme parent
    implicite de montage appartiendrait à root, ce que le CLI refuse.
    """
    (maison_du_projet(project_id) / "tmp").mkdir(parents=True, exist_ok=True)
