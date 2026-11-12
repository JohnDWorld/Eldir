# Risque nº 3 - plan d'implémentation

> **Pour les agents :** sous-skill requis : superpowers:subagent-driven-development.
> Les étapes se cochent (`- [ ]`).

**Objectif :** le backend ne lit plus de git ce qu'une session écrit : config et
hooks en lecture seule dans le conteneur, chemins git fixés par Eldir, jeton
réservé à l'hôte de la forge.

**Spec :** [`docs/specs/2026-11-12-risque-3-git-du-backend.md`](../specs/2026-11-12-risque-3-git-du-backend.md)

## Contraintes globales

- **Aucun tiret cadratin ni demi-cadratin** (U+2014, U+2013), nulle part,
  commits compris. Trait d'union `-` seulement.
- **Dépôt public** : aucun secret, aucune adresse réelle ; tests en `exemple.lan`.
- Backend, avant chaque commit, depuis `backend/` : `uv run ruff format --check .`,
  `uv run ruff check .`, `uv run pytest -q` (plancher 57 %).
- Français pour le code, les commentaires, les tests ; un commentaire dit
  pourquoi.
- Un commit par tâche, terminé par la ligne Co-Authored-By de l'environnement.
- Branche : `fix/risque-3-git-du-backend` (déjà créée, porte la spec).
- Les tests qui posent une config ou un hook hostile le font dans un dépôt
  jetable, avec un marqueur inoffensif (écrire un fichier témoin), et affirment
  qu'Eldir ne le suit pas. Rien de plus.

---

### Tâche 1 : le git du backend

**Fichiers :**
- Modifier : `backend/app/services/worktree_service.py`,
  `backend/app/services/session_container.py` (import de `chemin_du_clone`),
  `backend/app/services/git_providers/base.py`, `github.py`, `forgejo.py`,
  `backend/app/services/session_service.py` (`commit_push`, `open_pull_request`),
  `backend/app/services/project_service.py` (`create_from_repo`, `sync_with_remote`)
- Test : `backend/tests/unit/test_worktree_git_securite.py` (créé), et les faux
  providers des tests existants (attribut `origine_git`)

**Interfaces produites :**
- `chemin_du_clone(worktree: Path) -> Path | None` déplacé tel quel de
  `session_container.py` vers `worktree_service.py` ; `session_container.py`
  l'importe de là (même nom, même comportement, sa docstring suit).
- `GitProviderInterface.origine_git: str` (propriété abstraite) :
  `GitHubProvider` rend `"https://github.com"`, `ForgejoProvider` rend
  `self._base_url` (déjà sans `/` final).
- `WorktreeService._prefixe_git(token: str | None, origine: str | None) -> tuple[str, ...]`
- `WorktreeService._chemins_forces(cwd: Path) -> dict[str, str]`
- `_run_git(*args, cwd, token=None, origine=None)`, `push(..., token=None, origine=None)`,
  `fetch_remote(..., token=None, origine=None)`, `clone_repo(..., token=None, origine=None)`.

- [ ] **Étape 1 : les tests qui échouent**

`backend/tests/unit/test_worktree_git_securite.py` :

```python
"""Le git du backend ne suit pas ce qu'une session écrit (risque nº 3).

Dépôts jetables, marqueurs inoffensifs : on affirme qu'Eldir ne lit pas ce
qu'une session a pu réécrire, rien de plus.
"""

from __future__ import annotations

import subprocess
import uuid
from pathlib import Path

import pytest
from app.services.worktree_service import WorktreeService, _AIDE_CREDENTIEL


def _git(*args: str, cwd: Path) -> str:
    return subprocess.run(
        ["git", *args], cwd=cwd, check=True, capture_output=True, text=True
    ).stdout.strip()


@pytest.fixture
def depot(tmp_path: Path) -> tuple[WorktreeService, Path, Path, Path]:
    """Un dépôt nu, son clone et un worktree au chemin qu'Eldir leur donne."""
    racine = tmp_path / "workspaces"
    utilisateur = racine / "u1"
    utilisateur.mkdir(parents=True)
    nu = tmp_path / "nu"
    _git("init", "-q", "--bare", "-b", "main", str(nu), cwd=tmp_path)
    clone = utilisateur / "depot"
    _git("clone", "-q", str(nu), str(clone), cwd=tmp_path)
    _git("-c", "user.email=a@exemple.lan", "-c", "user.name=a", "commit", "-q",
         "--allow-empty", "-m", "init", cwd=clone)
    _git("push", "-q", "origin", "main", cwd=clone)
    worktree = utilisateur / f"depot.{uuid.uuid4()}"
    _git("worktree", "add", "-q", "-b", "claude/s1", str(worktree), cwd=clone)
    return WorktreeService(root=racine), nu, clone, worktree


def test_le_prefixe_neutralise_toujours_hooks_fsmonitor_et_sous_modules() -> None:
    prefixe = WorktreeService._prefixe_git(None, None)

    for reglage in (
        "core.hooksPath=/dev/null",
        "core.fsmonitor=false",
        "submodule.recurse=false",
        "diff.ignoreSubmodules=all",
    ):
        assert reglage in prefixe


def test_le_jeton_n_est_declare_que_pour_l_origine_de_la_forge() -> None:
    prefixe = WorktreeService._prefixe_git("jeton", "https://forge.exemple.lan")

    assert "credential.helper=" in prefixe
    assert f"credential.https://forge.exemple.lan.helper={_AIDE_CREDENTIEL}" in prefixe
    assert f"credential.helper={_AIDE_CREDENTIEL}" not in prefixe


def test_un_jeton_sans_origine_est_refuse() -> None:
    with pytest.raises(ValueError):
        WorktreeService._prefixe_git("jeton", None)


@pytest.mark.parametrize(("hote", "attendu"), [("forge.exemple.lan", True), ("autre.exemple.lan", False)])
def test_git_ne_donne_le_jeton_qu_a_l_hote_de_la_forge(
    tmp_path: Path, hote: str, attendu: bool
) -> None:
    prefixe = WorktreeService._prefixe_git("SECRET-JETON", "https://forge.exemple.lan")
    sortie = subprocess.run(
        ["git", *prefixe, "credential", "fill"],
        input=f"protocol=https\nhost={hote}\n\n",
        cwd=tmp_path,
        capture_output=True,
        text=True,
        env={"PATH": "/usr/bin:/bin", "HOME": str(tmp_path), "ELDIR_GIT_TOKEN": "SECRET-JETON",
             "GIT_TERMINAL_PROMPT": "0"},
    )

    assert ("SECRET-JETON" in sortie.stdout) is attendu


async def test_un_worktree_reecrit_ne_choisit_pas_la_config_lue(
    depot: tuple[WorktreeService, Path, Path, Path], tmp_path: Path
) -> None:
    service, _, clone, worktree = depot
    _git("config", "eldir.mesure", "vrai", cwd=clone)
    leurre = tmp_path / "leurre.git"
    _git("init", "-q", "--bare", str(leurre), cwd=tmp_path)
    _git("config", "eldir.mesure", "leurre", cwd=leurre)
    (worktree / ".git").write_text(f"gitdir: {leurre}\n")

    assert await service._run_git("config", "eldir.mesure", cwd=worktree) == "vrai"
    assert await service.current_branch(worktree) == "claude/s1"


async def test_un_worktree_au_chemin_d_eldir_commite_et_pousse_toujours(
    depot: tuple[WorktreeService, Path, Path, Path],
) -> None:
    service, nu, _, worktree = depot
    (worktree / "f.txt").write_text("x")

    await service.commit_all(
        worktree, message="m", author_name="a", author_email="a@exemple.lan"
    )
    await service.push(worktree, branch="claude/s1")

    assert _git("rev-parse", "--verify", "refs/heads/claude/s1", cwd=nu)


def test_un_chemin_hors_convention_n_est_pas_force(tmp_path: Path) -> None:
    assert WorktreeService._chemins_forces(tmp_path / "travail") == {}
```

(Adapter le nom et la signature exacts de `commit_all` et `current_branch` à
ceux du fichier s'ils diffèrent ; garder ce que chaque test affirme.)

- [ ] **Étape 2 : les lancer, ils échouent**

Run : `cd backend && uv run pytest -q --no-cov tests/unit/test_worktree_git_securite.py`
Attendu : `_prefixe_git` et `_chemins_forces` absents ; le test du worktree
réécrit lit « leurre ».

- [ ] **Étape 3 : `chemin_du_clone` déménage**

Couper la fonction `chemin_du_clone` (et sa docstring) de
`session_container.py`, la coller dans `worktree_service.py` après `slugify`,
et importer `chemin_du_clone` depuis `app.services.worktree_service` dans
`session_container.py`. Si un test l'importe depuis `session_container`, il
continue de marcher par cet import.

- [ ] **Étape 4 : le préfixe et les chemins**

Dans `WorktreeService` :

```python
    @staticmethod
    def _prefixe_git(token: str | None, origine: str | None) -> tuple[str, ...]:
        """Les `-c` de chaque appel : rien de ce qu'une session écrit n'est exécuté.

        Le backend lance git dans des dossiers que la session écrit (risque nº 3
        de docs/securite-sessions.md). En mode conteneur, la config et les hooks
        y sont en lecture seule ; ces options sont la défense en profondeur, et
        la seule en mode processus.

        Le jeton n'est confié qu'à l'origine de la forge : la valeur vide vide
        la liste des helpers, puis le nôtre n'est déclaré que pour cette
        origine. Une URL de remote réécrite vers un autre hôte ne le reçoit pas.
        """
        prefixe: tuple[str, ...] = (
            "-c", "core.hooksPath=/dev/null",
            "-c", "core.fsmonitor=false",
            "-c", "submodule.recurse=false",
            "-c", "diff.ignoreSubmodules=all",
        )
        if token:
            if not origine:
                raise ValueError("Un jeton git exige l'origine de la forge.")
            prefixe += (
                "-c", "credential.helper=",
                "-c", f"credential.{origine}.helper={_AIDE_CREDENTIEL}",
            )
        return prefixe

    @staticmethod
    def _chemins_forces(cwd: Path) -> dict[str, str]:
        """Les chemins git d'un worktree de session, calculés par Eldir.

        Reconnu à son chemin (`<user>/<slug>.<session>`), jamais à son contenu :
        le fichier `.git` du worktree et le `commondir` de son dossier
        d'administration sont écrits par la session. Mesuré : chemins fixés,
        la config lue est celle du vrai clone, quoi que disent ces fichiers.
        """
        clone = chemin_du_clone(cwd)
        if clone is None:
            return {}
        return {
            "GIT_DIR": str(clone / ".git" / "worktrees" / cwd.name),
            "GIT_COMMON_DIR": str(clone / ".git"),
            "GIT_WORK_TREE": str(cwd),
        }
```

`_run_git(self, *args, cwd, token=None, origine=None)` : `prefixe =
self._prefixe_git(token, origine)` ; `env = {**os.environ, **self._chemins_forces(cwd)}`,
plus `ELDIR_GIT_TOKEN` et `GIT_TERMINAL_PROMPT=0` quand il y a un jeton ; le reste
inchangé. Supprimer l'ancien bloc de préfixe et son commentaire, dont le contenu
passe dans la docstring de `_prefixe_git`.

`push`, `fetch_remote` et `clone_repo` prennent `origine: str | None = None` et
le transmettent à `_run_git`.

- [ ] **Étape 5 : l'origine vient du provider**

`base.py`, dans `GitProviderInterface` :

```python
    @property
    @abstractmethod
    def origine_git(self) -> str:
        """L'origine HTTPS de la forge, la seule à recevoir le jeton git."""
```

`github.py` : `origine_git` rend `"https://github.com"`. `forgejo.py` : rend
`self._base_url`. Tests de forge : un test par forge sur cette valeur.

Appelants (tous ont, ou prennent, le client par
`git_credential_service.get_active_client`) :
- `ProjectService.create_from_repo` : `clone_repo(..., token=token, origine=provider_client.origine_git)`.
- `ProjectService.sync_with_remote` : `get_active_token` devient
  `get_active_client` ; `fetch_remote(repo_path, token=token, origine=client.origine_git)`.
  Garder le comportement actuel quand il n'y a pas de credential (lire le code :
  si l'absence de jeton y est tolérée, attraper `AuthenticationError` et
  continuer sans jeton ni origine).
- `SessionService.commit_push` : `get_active_token` + garde deviennent
  `get_active_client` ; `push(..., token=token, origine=provider.origine_git)`.
- `SessionService.open_pull_request` : `push(..., origine=provider.origine_git)`.

Faux providers des tests existants : leur ajouter `origine_git =
"https://forge.exemple.lan"`.

- [ ] **Étape 6 : tout passe**

Run : `cd backend && uv run pytest -q`, ruff format et check. Toute la suite
verte.

- [ ] **Étape 7 : commit**

`fix(git): le backend ne suit plus les chemins ni l'hôte qu'une session écrit`

---

### Tâche 2 : le conteneur de la session

**Fichiers :**
- Modifier : `backend/docker/session/claude-dans-un-conteneur`,
  `backend/app/services/session_container.py`
- Test : `backend/tests/unit/test_enrobage.py`, `backend/tests/unit/test_session_container.py`

- [ ] **Étape 1 : les tests qui échouent**

`test_enrobage.py`, à côté de `test_le_clone_canonique_est_monte_en_ecriture` :

```python
def test_ce_que_git_lit_comme_des_ordres_est_en_lecture_seule(faux_docker: Path) -> None:
    """Risque nº 3 : le backend lance git dans ce clone.

    `.git` monté à part ne se renomme pas ; sa config, ses hooks et le dossier
    des sous-modules sont en lecture seule.
    """
    sortie = lancer(
        faux_docker,
        {
            **BASE,
            "ELDIR_CLONE_ABS": "/var/eldir/workspaces/u1/depot",
            "ELDIR_CLONE_SUBPATH": "u1/depot",
        },
    )

    base = "type=volume,src=vol_ws,dst=/var/eldir/workspaces/u1/depot/.git"
    assert f"{base},volume-subpath=u1/depot/.git" in sortie
    assert f"{base},volume-subpath=u1/depot/.git,readonly" not in sortie
    for nom in ("config", "hooks", "modules"):
        assert (
            f"type=volume,src=vol_ws,dst=/var/eldir/workspaces/u1/depot/.git/{nom},"
            f"volume-subpath=u1/depot/.git/{nom},readonly"
        ) in sortie


def test_sans_clone_aucun_montage_de_git(faux_docker: Path) -> None:
    sortie = lancer(faux_docker, BASE)

    assert "/.git" not in sortie
```

(Reprendre `lancer`, `BASE` et `faux_docker` du fichier ; si
`test_ce_qui_n_est_pas_nomme_n_est_pas_monte` compte les montages, mettre son
compte à jour.)

`test_session_container.py` : un test qui construit l'environnement du
conteneur pour un worktree dont le clone existe sans `.git/hooks` ni
`.git/modules`, et affirme que les deux dossiers existent ensuite. Reprendre la
fixture du fichier qui crée clone et worktree sous `workspaces_root`.

- [ ] **Étape 2 : l'enrobage**

Dans le bloc `if [ -n "${ELDIR_CLONE_SUBPATH:-}" ]`, après le montage du
clone :

```sh
    # Ce que git lit comme des ordres, hors de portée de la session (risque
    # nº 3) : le backend lance git dans ce clone. `.git` monté à part ne se
    # renomme ni ne se remplace (mesuré : refusé) ; sa config, ses hooks et le
    # dossier des dépôts de sous-modules sont en lecture seule. Le reste de
    # `.git` (objets, refs, index du worktree) reste inscriptible : un commit
    # dans le worktree passe toujours (mesuré).
    montages="$montages --mount type=volume,src=$ELDIR_WORKSPACES_VOLUME,dst=$ELDIR_CLONE_ABS/.git,volume-subpath=$ELDIR_CLONE_SUBPATH/.git"
    for ordres in config hooks modules; do
        montages="$montages --mount type=volume,src=$ELDIR_WORKSPACES_VOLUME,dst=$ELDIR_CLONE_ABS/.git/$ordres,volume-subpath=$ELDIR_CLONE_SUBPATH/.git/$ordres,readonly"
    done
```

- [ ] **Étape 3 : les dossiers existent avant `docker run`**

`session_container.py`, là où `clone = chemin_du_clone(worktree_abs)` est non
nul, avant de poser `ELDIR_CLONE_ABS` :

```python
        # Un `volume-subpath` absent fait échouer `docker run` : les dossiers
        # montés en lecture seule doivent exister, même vides.
        for dossier in ("hooks", "modules"):
            (clone / ".git" / dossier).mkdir(exist_ok=True)
```

- [ ] **Étape 4 : tout passe, commit**

Run : `cd backend && uv run pytest -q`, ruff. Commit :
`fix(conteneur): la config et les hooks git du clone en lecture seule pour la session`

---

### Tâche 3 : la documentation

**Fichiers :** `docs/securite-sessions.md`, `docs/specs/2026-11-12-superviseur-autonome.md`,
`docs/supervisor.md`, `docs/agent-externe.md`, `ROADMAP.md`,
`docs/specs/2026-11-12-risque-3-git-du-backend.md` (statut)

- [ ] **Étape 1 : `securite-sessions.md`**

La section « Risque connu nº 3 » garde son historique (ce qui a été mesuré le
2026-11-06) et gagne, en tête, un paragraphe **« Fermé en mode conteneur le
2026-11-12 »** qui résume la spec : ce qui est en lecture seule et pourquoi,
les chemins fixés, le jeton réservé à la forge, ce qui a été mesuré ce jour-là
(les quatre mesures de la spec), et ce qui reste ouvert (mode `processus`, bac
à sable). Le paragraphe « Ce qu'il faudrait » dit que ce lot a pris la première
voie pour la config et les hooks, et garde le bac à sable comme suite. Les
renvois au risque nº 3 ailleurs dans le fichier restent vrais ; corriger ceux
qui disent « ouvert » sans nuance.

- [ ] **Étape 2 : les limites nommées par la PR #56**

Dans la spec du superviseur autonome (section Sécurité), `docs/supervisor.md`
et `docs/agent-externe.md`, la phrase qui nomme la limite du risque nº 3
(« l'aide de credential répond à tout hôte », « l'URL du remote vit dans une
configuration que la session écrit ») devient : fermé en mode conteneur, ouvert
en mode `processus`, avec un renvoi à `securite-sessions.md`.

- [ ] **Étape 3 : ROADMAP et statut**

`ROADMAP.md`, section « Phase 6 bis » : une puce `[x]` « Le git du backend ne
lit plus ce qu'une session écrit (mode conteneur) » avec le lien vers la spec.
Statut de la spec : « implémenté (2026-11-12) ».

- [ ] **Étape 4 : tirets, commit**

Run : `grep -nP '[\x{2014}\x{2013}]' <chaque fichier modifié>`, rien attendu.
Commit : `docs(securite): le risque nº 3 fermé en mode conteneur`
