"""Ce que `deploy.sh` fait quand c'est lui-même qui change.

Bash lit le script en entier avant de l'exécuter : un `git pull` qui remplace
`deploy.sh` en cours de route laisse donc tourner l'ancienne version, et les
étapes que le commit déployé vient d'ajouter sont sautées en silence. C'est
arrivé en production le 2026-11-09 : l'image des sessions et leur réseau n'ont
jamais été créés, et le script a affiché « ✓ déployé » avec un code 0.

Le faux `git` de ces tests remplace réellement `deploy.sh` au moment du `pull`,
comme le vrai. Si la reprise par la nouvelle version disparaît du script, la
sentinelle écrite par ce `pull` ne s'exécute pas et les tests échouent.

Ce fichier vit dans les tests du backend parce que c'est le seul harnais du
dépôt ; `deploy.sh`, lui, est à la racine.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

DEPLOY = Path(__file__).parents[3] / "deploy.sh"

AVANT = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
APRES = "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"

SENTINELLE = "NOUVELLE-VERSION"


@pytest.fixture
def chantier(tmp_path: Path) -> Path:
    """Une copie de `deploy.sh` que le faux `git pull` peut écraser, et des faux
    `git` et `docker` sur le PATH.

    Le faux `git` garde son état dans des fichiers : `sha` donne ce que
    `rev-parse HEAD` répond (le `pull` le fait passer de AVANT à APRES),
    `changed` donne la liste que `diff --name-only` imprime, et `git.log`
    reçoit chaque appel pour qu'un test puisse affirmer qu'il n'y a pas eu de
    `pull`.

    Le `pull` n'écrit par-dessus `deploy.sh` que si `changed` le nomme, comme
    le vrai : un pull qui laisse le fichier intact ne perturbe pas la lecture
    du script en cours. Ce qu'il écrit alors est une sentinelle qui imprime son
    nom et la variable de reprise, seule façon de savoir si la nouvelle version
    a bien repris la main.
    """
    (tmp_path / "deploy.sh").write_text(DEPLOY.read_text(encoding="utf-8"), encoding="utf-8")
    os.chmod(tmp_path / "deploy.sh", 0o700)

    (tmp_path / "sha").write_text(AVANT, encoding="utf-8")
    (tmp_path / "changed").write_text("backend/app/main.py\n", encoding="utf-8")

    binaire = tmp_path / "bin"
    binaire.mkdir()
    (binaire / "git").write_text(
        f"""#!/bin/sh
printf '%s\\n' "$*" >> "$CHANTIER/git.log"
case "$1 $2" in
"rev-parse HEAD") cat "$CHANTIER/sha" ;;
"pull --ff-only")
    printf '%s' '{APRES}' > "$CHANTIER/sha"
    if grep -qx 'deploy.sh' "$CHANTIER/changed"; then
        cat > "$CHANTIER/deploy.sh" <<'SENT'
#!/usr/bin/env bash
echo "{SENTINELLE} ELDIR_DEPLOY_BEFORE=${{ELDIR_DEPLOY_BEFORE:-VIDE}}"
SENT
        chmod 700 "$CHANTIER/deploy.sh"
    fi
    ;;
"status --porcelain") ;;
"diff --name-only") cat "$CHANTIER/changed" ;;
"log --oneline") echo "ccccccc un commit" ;;
*) ;;
esac
""",
        encoding="utf-8",
    )
    # `network inspect` échoue exprès : sans cela le script sauterait la
    # création du réseau, et un test ne pourrait pas la constater.
    (binaire / "docker").write_text(
        """#!/bin/sh
printf '%s\\n' "$*" >> "$CHANTIER/docker.log"
case "$*" in
"network inspect eldir-sessions") exit 1 ;;
esac
exit 0
""",
        encoding="utf-8",
    )
    os.chmod(binaire / "git", 0o700)
    os.chmod(binaire / "docker", 0o700)
    return tmp_path


def lancer(chantier: Path, **variables: str) -> subprocess.CompletedProcess[str]:
    env = {
        "PATH": f"{chantier / 'bin'}:{os.environ['PATH']}",
        "CHANTIER": str(chantier),
        **variables,
    }
    return subprocess.run(
        ["bash", str(chantier / "deploy.sh")],
        capture_output=True,
        text=True,
        check=False,
        env=env,
        cwd=chantier,
        timeout=60,
    )


def journal(chantier: Path, nom: str) -> str:
    fichier = chantier / nom
    return fichier.read_text(encoding="utf-8") if fichier.exists() else ""


def test_un_deploy_qui_se_modifie_repasse_la_main_a_sa_nouvelle_version(
    chantier: Path,
) -> None:
    (chantier / "changed").write_text("deploy.sh\nbackend/app/main.py\n", encoding="utf-8")

    proc = lancer(chantier)

    assert proc.returncode == 0, proc.stderr
    assert SENTINELLE in proc.stdout, (
        "l'ancienne version a terminé le déploiement toute seule : les étapes "
        f"ajoutées par le commit déployé ont été sautées.\n{proc.stdout}"
    )


def test_la_nouvelle_version_recoit_le_point_de_depart(chantier: Path) -> None:
    """Sans le commit de départ, la reprise verrait « déjà à jour » et sortirait
    sans rien reconstruire : le déploiement serait silencieusement vide."""
    (chantier / "changed").write_text("deploy.sh\n", encoding="utf-8")

    proc = lancer(chantier)

    assert f"{SENTINELLE} ELDIR_DEPLOY_BEFORE={AVANT}" in proc.stdout, proc.stdout


def test_sans_changement_de_deploy_le_script_va_au_bout_lui_meme(chantier: Path) -> None:
    """L'anti-vacuité des deux tests du dessus : quand `deploy.sh` ne change
    pas, personne ne reprend la main, et le déploiement a bien lieu."""
    proc = lancer(chantier)

    assert proc.returncode == 0, proc.stderr
    assert SENTINELLE not in proc.stdout
    assert "network create eldir-sessions" in journal(chantier, "docker.log")
    assert "compose up -d --build" in journal(chantier, "docker.log")


def test_la_reprise_ne_tire_pas_une_seconde_fois_et_ne_boucle_pas(chantier: Path) -> None:
    """Le deuxième passage ne doit ni refaire le `pull` (il est déjà fait) ni se
    relancer encore : une boucle de `exec` ne s'arrêterait jamais.

    Le changement backend n'est pas décoratif : `deploy.sh` seul ne donne aucun
    service à reconstruire, et le script sortirait avant le `compose up`.
    """
    (chantier / "changed").write_text("deploy.sh\nbackend/app/main.py\n", encoding="utf-8")
    (chantier / "sha").write_text(APRES, encoding="utf-8")

    proc = lancer(chantier, ELDIR_DEPLOY_BEFORE=AVANT)

    assert proc.returncode == 0, proc.stderr
    assert SENTINELLE not in proc.stdout, "le pull a été refait, donc le script a rebouclé"
    assert "pull" not in journal(chantier, "git.log")
    assert "compose up -d --build" in journal(chantier, "docker.log")
