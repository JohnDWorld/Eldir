# Un conteneur par session - plan d'implémentation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** sortir le processus `claude` du conteneur du backend et le mettre dans un conteneur par session, monté sur son seul worktree, sa seule clé SSH et la seule maison `.claude` de son projet, pour qu'une session compromise ne puisse plus lire le disque des autres projets.

**Architecture:** le SDK Claude reste dans le processus du backend. On lui passe `ClaudeAgentOptions(cli_path=<enrobage>)`, un script shell qui se remplace par `docker run -i` : le protocole de contrôle traverse le tube stdio sans adaptation, et les hooks `PreToolUse`/`PostToolUse` continuent de s'exécuter côté backend, donc la porte de publication et la garde d'accès distant restent hors du périmètre qu'elles contraignent. Un service Python calcule les montages, l'enrobage les applique, et rien d'autre n'entre dans le conteneur que ce que l'enrobage nomme.

**Tech Stack:** Python 3.12, FastAPI, `claude-agent-sdk`, Docker 25+ (`--mount volume-subpath`), `tecnativa/docker-socket-proxy`, pytest, shell POSIX.

**Spec:** [`docs/specs/2026-11-03-conteneur-par-session.md`](../specs/2026-11-03-conteneur-par-session.md)

## Global Constraints

- **Aucun tiret long, nulle part.** Ni cadratin (U+2014) ni demi-cadratin (U+2013) : ni dans le code, ni dans les commentaires, ni dans les messages de commit, ni dans la doc, ni dans l'interface. Toujours le trait d'union `-`, ou reformuler. Règle absolue du mainteneur, vérifiée avant chaque commit, et tenue par le job CI `aucun tiret cadratin`.
- **Tout en français** : commentaires, docstrings, messages d'erreur, libellés.
- **Un seul lot, une seule branche, une seule PR** : `feat/conteneur-par-session`, ouverte quand les onze tâches sont finies. Un commit par tâche, annulable seul. Avant chaque commit : `gh pr list --head feat/conteneur-par-session --state all` dans un appel séparé, et lire le résultat avant de décider.
- **Le dépôt est public.** Aucun secret, aucune adresse de machine, aucun nom d'hôte personnel, aucune adresse e-mail dans un fichier commité. Les exemples utilisent `eldir.exemple.lan` ou `127.0.0.1`.
- **Portes de qualité avant chaque commit** : `cd backend && uv run ruff check . && uv run ruff format --check . && uv run mypy app && uv run pytest -q`.
- **Jamais de repli silencieux.** Un échec de démarrage en mode `conteneur` ne retombe pas en mode `processus`. Le mode `processus` ne s'obtient que par le réglage `SESSION_RUNTIME`.
- **Les hooks restent côté backend.** Aucune tâche ne déplace `_publish_denial` ni `_remote_denial` dans le conteneur, ni ne les contourne. C'est la raison d'être de l'approche par enrobage.
- **`volume-subpath` exige un sous-chemin existant.** Un sous-chemin absent fait échouer `docker run` avec le code 127. Tout montage dont le sous-chemin peut ne pas exister est conditionnel, et le backend crée ce qu'il doit créer avant de lancer.
- **Les chemins des montages n'ont pas d'espace.** `sh` n'a pas de tableaux, les montages optionnels de l'enrobage passent par un découpage de mots. `slugify` et les UUID n'en produisent jamais ; l'enrobage refuse explicitement un chemin qui en contiendrait.
- **Docker 25 minimum** sur l'hôte, pour `--mount ...,volume-subpath=...`. Mesuré sur 29.9.2.
- **Les tests marqués `docker` ne lancent jamais le CLI Claude.** Ils ne consomment aucun credit.

---

## Ce que ce plan corrige dans la spec

La spec a été écrite sur une sonde jetable qui utilisait des dossiers ordinaires, un bind mount de l'hôte et `--network host`. Cinq points ne tiennent pas tels quels, et tous ont été **mesurés** avant d'être écrits ici. Chacun est traité par une tâche nommée.

| Point de la spec | Ce qui a été mesuré | Tâche |
|---|---|---|
| « Ce que le conteneur monte » : le worktree seul | Un worktree Eldir est un **worktree git** : son `.git` est un fichier qui pointe vers `<clone>/.git/worktrees/<nom>`. Monté seul, `git status` répond `fatal: not a git repository`. Avec le clone canonique monté en plus : branche, log et commit fonctionnent, et le voisin reste introuvable. | 5, 8 |
| `workspaces_volume = "eldir_workspaces"` | Compose préfixe le nom du volume par celui du projet : le volume s'appelle `eldir_eldir_workspaces` en prod (`name: eldir`) et `eldir-dev_eldir_workspaces` en dev. Un `docker run` sur `eldir_workspaces` monterait un volume vide tout neuf. | 4 |
| `--mount type=bind,src=$ELDIR_SSH_KEY` | La clé vit dans le volume `eldir_ssh`, et le `src` d'un bind est résolu **par le démon, sur l'hôte**. Le chemin que voit le backend n'existe pas là-bas. Et `volume-subpath` ne sait pas monter un fichier seul. | 6, 8 |
| Les variables du projet (`ELDIR_TOOLCHAIN`, `PATH`, `ELDIR_COLLECTE`) | L'enrobage ne transmet que ce qu'il nomme : telles quelles, le toolchain et la collecte disparaissent de la session. La collecte vit de plus hors volume, donc le démon ne peut pas la monter du tout. | 5, 7, 10 |
| `--network eldir-sessions` | Compose ne crée **pas** un réseau déclaré qu'aucun service n'utilise (mesuré : seul `<projet>_default` apparaît). Le réseau doit être créé explicitement, sinon chaque session échoue au démarrage. | 10 |

Et un défaut vivant sur `main`, trouvé en lisant l'assemblage des options du SDK, dans la zone exacte que cette spec durcit :

> `options_kwargs["env"] = env_a_masquer_pour_cli()` est **écrasé** par `options_kwargs.update(_optional_options(...))` dès que le projet apporte une variable (un toolchain installé, une collecte, un hôte distant). Vérifié : avec `remote_host`, l'environnement passé au SDK est `{'ELDIR_REMOTE_HOST': ...}` seul, et `JWT_SECRET` n'est plus masqué. C'est la tâche 1, et elle passe en premier parce qu'elle protège les installations en mode `processus`, c'est-à-dire tout le monde jusqu'à la bascule.

Le reste de la spec est appliqué tel quel : granularité de la maison `.claude` par projet, proxy de socket, pas de repli, sortant complet, et le réseau sortant restreint laissé au second lot.

---

## Structure des fichiers

**Créés**

| Fichier | Responsabilité |
|---|---|
| `backend/app/services/claude_home.py` | Où vit la maison `.claude` d'un projet, et comment le CLI nomme ses transcripts |
| `backend/app/services/claude_home_migration.py` | Ranger les transcripts à plat sous la maison de leur projet, une fois, au boot |
| `backend/app/services/session_container.py` | Calculer les montages d'une session. Ne lance rien |
| `backend/docker/session/Dockerfile` | L'image des sessions : Node, git, le CLI Claude, rien d'autre |
| `backend/docker/session/entree-session` | Pose le PATH du toolchain, puis `exec` |
| `backend/docker/session/claude-dans-un-conteneur` | L'enrobage passé à `cli_path` |
| `backend/tests/unit/test_claude_home.py` | Le slug du CLI, relevé sur des dossiers réels |
| `backend/tests/unit/test_claude_home_migration.py` | Déplacement, idempotence, non-rattachement |
| `backend/tests/unit/test_session_container.py` | Les montages calculés, et l'absence de secret dedans |
| `backend/tests/unit/test_enrobage.py` | La ligne de commande construite, avec un faux `docker` |
| `backend/tests/integration/test_isolement_sessions.py` | Les trois tests d'isolement, avec un vrai démon |

**Modifiés**

| Fichier | Changement |
|---|---|
| `backend/app/services/session_manager.py` | Le masque d'environnement fusionné et plus écrasé ; `cli_path` et l'environnement de l'enrobage en mode `conteneur` ; nettoyage de la matière SSH à l'arrêt |
| `backend/app/core/config.py` | `claude_home_root`, `session_runtime`, `session_image`, `session_network`, les quatre noms de volumes |
| `backend/app/services/remote_access_service.py` | `bloc_ssh` extrait en fonction pure ; matière SSH par session, écrite et supprimée |
| `backend/app/main.py` | La migration des maisons appelée au boot |
| `backend/pyproject.toml` | Le marqueur `docker` déclaré (`--strict-markers` le refuse sinon) |
| `backend/tests/unit/test_env_sessions.py` | Le test de régression du masque fusionné |
| `backend/Dockerfile` | Le CLI `docker` (pas le démon) |
| `docker-compose.yml` | Le proxy de socket, `DOCKER_HOST`, `SESSION_RUNTIME`, les noms de volumes, le volume des collectes |
| `scripts/install-eldir.sh` | Crée le réseau des sessions et construit l'image de session |
| `docs/securite-sessions.md` | Le risque nº 2 passe de structurel à fermé, avec ce qui reste |
| `docs/sessions.md` | Ce qu'une session voit de son disque |
| `docs/deployment.md` | Le réseau, l'image, le proxy, la bascule et le repli |
| `ROADMAP.md` | Phase 6 bis, points 1, 2, 4 cochés, le 5 renseigné par la mesure |

---

## Task 1: Le masque d'environnement, fusionné et plus écrasé

Défaut vivant sur `main`, et le point de départ logique : la spec affirme que le masque « reste en place » pour le mode `processus`. Aujourd'hui il ne reste pas.

**Files:**
- Modify: `backend/app/services/session_manager.py:183-235` (`_optional_options`), `:441-472` (l'assemblage)
- Test: `backend/tests/unit/test_env_sessions.py`

**Interfaces:**
- Consumes: `env_a_masquer_pour_cli()` de `app.core.config`, inchangée.
- Produces: `env_pour_la_session(*, project_id: str | None, remote_host: str | None) -> dict[str, str]` dans `app/services/session_manager.py`. Rend le masque du backend fusionné avec les variables du projet, les variables du projet gagnant sur les clés en conflit. C'est la seule fonction qui construit l'environnement d'une session, et la tâche 9 ajoute ses clés par-dessus.

- [ ] **Step 1: Écrire le test qui échoue**

Dans `backend/tests/unit/test_env_sessions.py`, à la fin du fichier :

```python
def test_le_masque_survit_aux_variables_du_projet(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Le masque et les apports du projet se fusionnent, ils ne se remplacent pas.

    Le défaut qui a motivé ce test : l'assemblage posait le masque dans
    `options_kwargs["env"]`, puis `update()` y écrasait la clé `env` entière
    dès que le projet apportait une variable. Un projet avec un toolchain
    installé, une collecte ou un hôte distant - donc tout projet un peu
    équipé - rendait le masque inopérant, et une session lisait `JWT_SECRET`.

    Le test passe par la fonction d'assemblage et pas par les deux morceaux
    pris séparément : c'est la fusion qui était fausse, pas les morceaux.
    """
    from app.services.session_manager import env_pour_la_session

    monkeypatch.setenv("JWT_SECRET", "valeur-sensible-du-backend")
    env = env_pour_la_session(project_id="p1", remote_host="eldir-machine")

    assert env["ELDIR_REMOTE_HOST"] == "eldir-machine"
    assert env["JWT_SECRET"] == ""
```

- [ ] **Step 2: Lancer le test pour le voir échouer**

Run: `cd backend && uv run pytest tests/unit/test_env_sessions.py::test_le_masque_survit_aux_variables_du_projet -v`
Expected: FAIL avec `ImportError: cannot import name 'env_pour_la_session'`

- [ ] **Step 3: Extraire la fusion dans sa fonction**

Dans `backend/app/services/session_manager.py`, juste avant `_optional_options`, ajouter :

```python
def env_pour_la_session(*, project_id: str | None, remote_host: str | None) -> dict[str, str]:
    """L'environnement d'une session : le masque du backend, puis les apports du projet.

    Deux apports du projet, groupés ici plutôt que chez chaque appelant pour
    que création, resume et sessions système en héritent pareil :

    - `$ELDIR_TOOLCHAIN` et `$ELDIR_TOOLCHAIN/bin` en tête du PATH, pour que
      l'agent trouve les outils installés (SDK Flutter, JDK, Go…) ;
    - `$ELDIR_COLLECTE`, où atterrit ce qui a été ramené d'un serveur avant le
      démarrage (cf. `CollectService`) ;
    - `$ELDIR_REMOTE_HOST`, l'alias SSH de la machine où tourne le projet,
      seule destination que le hook laisse atteindre.

    L'ordre n'est pas décoratif : le masque d'abord, les apports du projet
    ensuite. Le masque vide nommément les secrets d'Eldir que le SDK
    transmettrait sinon (il passe l'environnement du backend en entier, cf.
    `env_a_masquer_pour_cli`), et aucun apport du projet ne porte le nom d'un
    champ de `Settings`, donc rien ne se démasque par cette fusion.
    """
    env = dict(env_a_masquer_pour_cli())
    env.update(toolchain_service.env_for(project_id))
    env.update(collect_service.env_for(project_id))
    if remote_host:
        env["ELDIR_REMOTE_HOST"] = remote_host
    return env
```

L'import de `env_a_masquer_pour_cli` est déjà présent en tête de fichier (il servait à l'assemblage) ; vérifier qu'il y est, l'ajouter sinon :

```python
from app.core.config import env_a_masquer_pour_cli, get_settings
```

- [ ] **Step 4: Retirer la construction d'environnement de `_optional_options`**

Dans `_optional_options`, supprimer les lignes qui construisent `env` et le posent dans `kwargs` (le bloc de commentaire « Deux apports du projet… » et les cinq lignes qui suivent, jusqu'à `kwargs["env"] = env` inclus), ainsi que les paramètres devenus inutiles `project_id` et `remote_host` de sa signature. La fonction ne garde que les options SDK facultatives, et ne rend plus jamais la clé `env`.

Le corps se termine donc par :

```python
    if mcp_servers:
        # Outils in-process (superviseur). `strict_mcp_config` évite de
        # charger en plus les serveurs MCP éventuels de la machine hôte.
        kwargs["mcp_servers"] = mcp_servers
        kwargs["strict_mcp_config"] = True
    return kwargs
```

- [ ] **Step 5: Brancher la fusion dans l'assemblage**

Dans `SessionManager.start`, remplacer la valeur de la clé `env` de `options_kwargs` et l'appel à `_optional_options` :

```python
        options_kwargs: dict[str, Any] = {
            "cwd": cwd,
            "stderr": _on_cli_stderr,
            # Le SDK transmet l'environnement du backend en entier : ce masque
            # retire les secrets d'Eldir de ce que la session peut lire, et
            # `env_pour_la_session` garantit qu'il survit aux variables du
            # projet. Cf. `env_a_masquer_pour_cli` - sans lui, `JWT_SECRET`
            # suffit à une session pour se forger un jeton de connexion et
            # s'autoriser la publication sans passer par le hook.
            "env": env_pour_la_session(project_id=project_id, remote_host=remote_host),
            ...
        }
        options_kwargs.update(
            _optional_options(
                system_prompt=system_prompt,
                model=model,
                resume_sdk_id=resume_sdk_id,
                allowed_tools=allowed_tools,
                disallowed_tools=disallowed_tools,
                mcp_servers=mcp_servers,
            )
        )
```

- [ ] **Step 6: Lancer la suite entière**

Run: `cd backend && uv run pytest -q`
Expected: PASS, nouveau test compris. `_optional_options` est appelée ailleurs dans les tests (`test_session_manager.py`) : si sa signature cassait un appel, le corriger en retirant les deux arguments.

- [ ] **Step 7: Portes de qualité et commit**

```bash
cd backend && uv run ruff check . && uv run ruff format --check . && uv run mypy app && uv run pytest -q
cd .. && git add -A && git commit -m "fix(sessions): le masque d'environnement n'est plus ecrase par les variables du projet

Poser le masque dans options_kwargs puis appeler update() avec un dict qui
porte aussi la cle env remplacait le masque entier. Tout projet avec un
toolchain installe, une collecte ou un hote distant rendait donc le masque
inoperant, et sa session lisait JWT_SECRET, ENCRYPTION_KEY et DATABASE_URL.

La fusion devient une fonction nommee, testee par ce qu'elle rend.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Task 2: Le slug du CLI, et la maison `.claude` par projet

La spec le dit : « Le slugifieur est à dériver de l'observation, pas à deviner. Un slug mal reproduit ne casse rien mais perd tous les `resume`, silencieusement. »

Les cas ci-dessous sont **relevés** sur les dossiers réels de `~/.claude/projects` d'une installation, et chacun fixe un point de la règle : la racine, le point, l'espace, le souligné, le caractère accentué. La règle qui les explique tous : tout caractère hors `[A-Za-z0-9-]` devient un tiret, un tiret par caractère, sans fusion des tirets consécutifs ni rognage des bords.

**Files:**
- Create: `backend/app/services/claude_home.py`
- Modify: `backend/app/core/config.py` (après `ssh_home`)
- Test: `backend/tests/unit/test_claude_home.py`

**Interfaces:**
- Consumes: `get_settings()`.
- Produces :
  - `slug_du_cwd(cwd: str | Path) -> str`
  - `sous_chemin_de_maison(project_id: str | None) -> str` (rend `project_id`, ou `MAISON_SUPERVISEUR` quand il est `None`)
  - `maison_du_projet(project_id: str | None) -> Path` (le chemin **côté backend**, sous `claude_home_root`)
  - `MAISON_SUPERVISEUR: str = "_superviseur"`
  - `Settings.claude_home_root: Path`

- [ ] **Step 1: Écrire le test qui échoue**

Créer `backend/tests/unit/test_claude_home.py` :

```python
"""La règle de nommage des transcripts du CLI, relevée sur des dossiers réels.

Le CLI Claude range le transcript d'une conversation dans
`$HOME/.claude/projects/<slug>`, où `<slug>` dérive du chemin absolu du cwd.
Un slug mal reproduit ne casse rien : il perd tous les `resume`, sans bruit.
D'où ces cas, qui ne sont pas inventés mais copiés depuis un
`~/.claude/projects` réel, et qui fixent chacun un point de la règle.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from app.services.claude_home import (
    MAISON_SUPERVISEUR,
    maison_du_projet,
    slug_du_cwd,
    sous_chemin_de_maison,
)

CAS_RELEVES = [
    # la racine : le premier `/` donne un tiret de tête
    ("/home/john", "-home-john"),
    # le point : `/.claude` donne deux tirets, un par caractère
    ("/home/john/.claude", "-home-john--claude"),
    # l'espace
    (
        "/home/john/Documents/Projet Perso/Eldir",
        "-home-john-Documents-Projet-Perso-Eldir",
    ),
    # le souligné
    (
        "/home/john/Documents/Projet Perso/CrossOps_App",
        "-home-john-Documents-Projet-Perso-CrossOps-App",
    ),
    # le caractère accentué, et trois tirets consécutifs qui ne fusionnent pas
    (
        "/home/john/Documents/Projet Pro/La Boutique à Automatisations/n8n-prod",
        "-home-john-Documents-Projet-Pro-La-Boutique---Automatisations-n8n-prod",
    ),
]


@pytest.mark.parametrize(("chemin", "attendu"), CAS_RELEVES)
def test_le_slug_reproduit_les_dossiers_releves(chemin: str, attendu: str) -> None:
    assert slug_du_cwd(chemin) == attendu


def test_le_slug_accepte_un_path() -> None:
    assert slug_du_cwd(Path("/home/john")) == "-home-john"


def test_deux_sessions_du_meme_repo_ont_deux_slugs() -> None:
    """Le point qui sépare le repo de l'id de session devient un tiret.

    Layout de `WorktreeService` : `<user>/<repo_slug>.<session_id>`. Deux
    sessions du même projet ont donc deux transcripts distincts, et c'est ce
    qui rend une maison `.claude` par projet suffisante.
    """
    a = slug_du_cwd("/var/eldir/workspaces/u1/eldir.s1")
    b = slug_du_cwd("/var/eldir/workspaces/u1/eldir.s2")
    assert a == "-var-eldir-workspaces-u1-eldir-s1"
    assert a != b


def test_le_superviseur_a_une_maison_nommee() -> None:
    """Le superviseur n'a pas de projet : sa maison porte un nom réservé.

    Sans ça, `volume-subpath` recevrait une chaîne vide et monterait la racine
    du volume, c'est-à-dire les maisons de tous les projets.
    """
    assert sous_chemin_de_maison(None) == MAISON_SUPERVISEUR
    assert sous_chemin_de_maison("p1") == "p1"
    assert MAISON_SUPERVISEUR.strip() != ""


def test_la_maison_vit_sous_la_racine_configuree(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CLAUDE_HOME_ROOT", "/tmp/maisons")
    from app.core.config import get_settings

    get_settings.cache_clear()
    try:
        assert maison_du_projet("p1") == Path("/tmp/maisons/p1")
    finally:
        get_settings.cache_clear()
```

- [ ] **Step 2: Lancer le test pour le voir échouer**

Run: `cd backend && uv run pytest tests/unit/test_claude_home.py -v`
Expected: FAIL avec `ModuleNotFoundError: No module named 'app.services.claude_home'`

- [ ] **Step 3: Écrire le module**

Créer `backend/app/services/claude_home.py` :

```python
"""Où vit la maison `.claude` d'un projet, et comment le CLI nomme ses transcripts.

Une maison par **projet**, pas par session : deux sessions d'un même projet
partagent déjà leur worktree de base, leur clé et leur code, elles sont le
même domaine de confiance. Deux projets différents, en revanche, ne se voient
plus. Cf. la spec, section « La maison `.claude`, une par projet ».

Le slug est la seule chose ici qui ne soit pas un choix d'Eldir : c'est le CLI
Claude qui nomme ses dossiers de transcripts, et la règle est relevée sur des
dossiers réels (cf. `tests/unit/test_claude_home.py`), pas devinée. Elle est
déterministe, et comme le worktree est monté au même chemin absolu dans le
conteneur que sur l'hôte, le slug reste identique après la bascule : un
transcript rattaché continue de se résoudre.
"""

from __future__ import annotations

import re
from pathlib import Path

from app.core.config import get_settings

# Tout ce qui n'est ni lettre ASCII, ni chiffre, ni tiret devient un tiret.
# Un tiret par caractère : les tirets consécutifs ne fusionnent pas, et les
# bords ne sont pas rognés.
_HORS_SLUG = re.compile(r"[^A-Za-z0-9-]")

# Le superviseur n'a pas de projet. Sans ce nom, son sous-chemin de maison
# serait vide et monterait la racine du volume, donc les maisons de tous les
# projets.
MAISON_SUPERVISEUR = "_superviseur"


def slug_du_cwd(cwd: str | Path) -> str:
    """Le nom du dossier de transcript que le CLI dérive d'un cwd absolu."""
    return _HORS_SLUG.sub("-", str(cwd))


def sous_chemin_de_maison(project_id: str | None) -> str:
    """Le sous-chemin de la maison dans le volume, pour un projet ou le superviseur."""
    return project_id or MAISON_SUPERVISEUR


def maison_du_projet(project_id: str | None) -> Path:
    """La maison du projet telle que le **backend** la voit.

    Le conteneur de session la voit à `/eldir/maison`, par un montage de
    sous-chemin. Les deux chemins désignent le même dossier du même volume.
    """
    return get_settings().claude_home_root / sous_chemin_de_maison(project_id)
```

- [ ] **Step 4: Déclarer `claude_home_root` dans `Settings`**

Dans `backend/app/core/config.py`, juste après le bloc `ssh_home` / `ssh_connect_timeout_s` :

```python
    # ── Maisons `.claude` des sessions ──────────────────────────
    # Point de montage, chez le backend, du volume qui porte les transcripts
    # du CLI. Une maison par projet dessous (cf. `claude_home.py`) : sans
    # cette séparation, une session lirait les conversations de tous les
    # autres projets. Le nom DOCKER de ce volume est `claude_home_volume`,
    # plus bas : un point de montage et un nom de volume ne se déduisent pas
    # l'un de l'autre.
    claude_home_root: Path = Path("/home/eldir/.claude")
```

- [ ] **Step 5: Lancer le test pour le voir passer**

Run: `cd backend && uv run pytest tests/unit/test_claude_home.py -v`
Expected: PASS, 9 tests

- [ ] **Step 6: Portes de qualité et commit**

```bash
cd backend && uv run ruff check . && uv run ruff format --check . && uv run mypy app && uv run pytest -q
cd .. && git add -A && git commit -m "feat(sessions): la maison .claude par projet, et le slug du CLI releve sur du reel

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Task 3: La migration des maisons `.claude`

Les transcripts existants vivent à plat dans `<claude_home_root>/projects/`. Il faut les ranger sous la maison de leur projet, une fois, sans rien perdre. C'est le seul endroit de cette conception où quelque chose peut disparaître en silence : ce qui n'est pas rattaché perd son `resume`, donc ce qui n'est pas rattaché est **journalisé nommément** et laissé en place.

**Files:**
- Create: `backend/app/services/claude_home_migration.py`
- Modify: `backend/app/main.py:27-35`
- Test: `backend/tests/unit/test_claude_home_migration.py`

**Interfaces:**
- Consumes: `slug_du_cwd`, `sous_chemin_de_maison` (tâche 2), `async_session_factory`, `Session` (modèle).
- Produces :
  - `@dataclass(slots=True, frozen=True) Rapport(deplacees: int, laissees: tuple[str, ...])`
  - `ranger_les_dossiers(racine: Path, maison_par_slug: dict[str, str]) -> Rapport` (synchrone, pure hors système de fichiers, testable sans base)
  - `async def migrer_les_maisons() -> Rapport` (lit la base, appelle la précédente dans un thread)

- [ ] **Step 1: Écrire les tests qui échouent**

Créer `backend/tests/unit/test_claude_home_migration.py` :

```python
"""Ranger les transcripts sous la maison de leur projet, sans rien perdre.

Un transcript qu'on ne sait pas rattacher n'est pas supprimé : il reste où il
est, il est journalisé par son nom, et la session concernée redémarrera une
conversation neuve au lieu d'échouer. C'est le comportement voulu par la spec,
et c'est pour ça qu'il est testé.
"""

from __future__ import annotations

from pathlib import Path

from app.services.claude_home_migration import Rapport, ranger_les_dossiers


def _transcript(racine: Path, nom: str) -> Path:
    dossier = racine / "projects" / nom
    dossier.mkdir(parents=True)
    (dossier / "2026-01-01T00-00-00-000Z.jsonl").write_text("{}\n", encoding="utf-8")
    return dossier


def test_un_transcript_connu_part_sous_la_maison_de_son_projet(tmp_path: Path) -> None:
    _transcript(tmp_path, "-var-eldir-workspaces-u1-eldir-s1")

    rapport = ranger_les_dossiers(
        tmp_path, {"-var-eldir-workspaces-u1-eldir-s1": "projet-a"}
    )

    assert rapport.deplacees == 1
    assert rapport.laissees == ()
    cible = tmp_path / "projet-a" / ".claude" / "projects" / "-var-eldir-workspaces-u1-eldir-s1"
    assert (cible / "2026-01-01T00-00-00-000Z.jsonl").exists()
    assert not (tmp_path / "projects" / "-var-eldir-workspaces-u1-eldir-s1").exists()


def test_un_transcript_inconnu_reste_en_place(tmp_path: Path) -> None:
    _transcript(tmp_path, "-un-chemin-que-plus-aucune-session-ne-porte")

    rapport = ranger_les_dossiers(tmp_path, {})

    assert rapport.deplacees == 0
    assert rapport.laissees == ("-un-chemin-que-plus-aucune-session-ne-porte",)
    assert (tmp_path / "projects" / "-un-chemin-que-plus-aucune-session-ne-porte").is_dir()


def test_la_migration_est_idempotente(tmp_path: Path) -> None:
    """Deux boots de suite, et le second ne fait rien.

    Le script est appelé à chaque démarrage : s'il n'était pas idempotent, il
    déplacerait des dossiers déjà rangés, ou écraserait un transcript en cours.
    """
    _transcript(tmp_path, "-var-eldir-workspaces-u1-eldir-s1")
    maison_par_slug = {"-var-eldir-workspaces-u1-eldir-s1": "projet-a"}

    premier = ranger_les_dossiers(tmp_path, maison_par_slug)
    second = ranger_les_dossiers(tmp_path, maison_par_slug)

    assert premier.deplacees == 1
    assert second.deplacees == 0
    assert second.laissees == ()


def test_une_collision_ne_detruit_rien(tmp_path: Path) -> None:
    """Un transcript déjà rangé sous la maison, et un homonyme resté à plat.

    On ne sait pas lequel est le bon, donc on ne touche ni l'un ni l'autre, et
    on le dit.
    """
    _transcript(tmp_path, "-var-eldir-workspaces-u1-eldir-s1")
    deja = tmp_path / "projet-a" / ".claude" / "projects" / "-var-eldir-workspaces-u1-eldir-s1"
    deja.mkdir(parents=True)
    (deja / "ancien.jsonl").write_text("{}\n", encoding="utf-8")

    rapport = ranger_les_dossiers(
        tmp_path, {"-var-eldir-workspaces-u1-eldir-s1": "projet-a"}
    )

    assert rapport.deplacees == 0
    assert rapport.laissees == ("-var-eldir-workspaces-u1-eldir-s1",)
    assert (deja / "ancien.jsonl").exists()
    assert (tmp_path / "projects" / "-var-eldir-workspaces-u1-eldir-s1").is_dir()


def test_sans_dossier_projects_la_migration_ne_fait_rien(tmp_path: Path) -> None:
    """Installation neuve : rien à plat, rien à ranger, aucun échec."""
    rapport = ranger_les_dossiers(tmp_path, {"peu-importe": "projet-a"})

    assert rapport == Rapport(deplacees=0, laissees=())
```

- [ ] **Step 2: Lancer les tests pour les voir échouer**

Run: `cd backend && uv run pytest tests/unit/test_claude_home_migration.py -v`
Expected: FAIL avec `ModuleNotFoundError: No module named 'app.services.claude_home_migration'`

- [ ] **Step 3: Écrire le module**

Créer `backend/app/services/claude_home_migration.py` :

```python
"""Ranger les transcripts du CLI sous la maison `.claude` de leur projet.

Appelée une fois au boot, idempotente. Avant la Phase 6 bis, tous les
transcripts vivaient à plat dans `<claude_home_root>/projects/`, donc dans un
volume partagé par toutes les sessions de tous les projets. La séparation par
projet n'a d'intérêt que si l'existant la rejoint.

Le rattachement se fait par le slug : le CLI nomme chaque dossier d'après le
chemin absolu du cwd (cf. `claude_home.slug_du_cwd`), et chaque session connue
en base porte son `worktree_path`. Ce qui ne se rattache pas reste où il est
et se retrouve dans les logs par son nom. Rien n'est supprimé, jamais : une
session dont le transcript n'a pas été rattaché perd son `resume` et redémarre
une conversation neuve, ce qui est déjà le comportement de
`SessionService.resume` et de `SupervisorService._ensure_session`.
"""

from __future__ import annotations

import asyncio
import shutil
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import select

from app.core.config import get_settings
from app.core.logging import get_logger
from app.db.models.session import Session
from app.db.session import async_session_factory
from app.services.claude_home import slug_du_cwd, sous_chemin_de_maison

logger = get_logger(__name__)

_A_PLAT = "projects"


@dataclass(slots=True, frozen=True)
class Rapport:
    deplacees: int
    laissees: tuple[str, ...]


def ranger_les_dossiers(racine: Path, maison_par_slug: dict[str, str]) -> Rapport:
    """Déplace ce qu'on sait rattacher, laisse le reste, ne supprime rien.

    `racine` est le point de montage du volume chez le backend,
    `maison_par_slug` associe un nom de dossier de transcript au sous-chemin
    de la maison qui doit l'accueillir.
    """
    source = racine / _A_PLAT
    if not source.is_dir():
        return Rapport(deplacees=0, laissees=())

    deplacees = 0
    laissees: list[str] = []
    for dossier in sorted(p for p in source.iterdir() if p.is_dir()):
        maison = maison_par_slug.get(dossier.name)
        if maison is None:
            laissees.append(dossier.name)
            continue
        destination = racine / maison / ".claude" / _A_PLAT / dossier.name
        if destination.exists():
            # Déjà rangé, ou homonyme : on ne sait pas lequel est le bon, donc
            # on ne touche à aucun des deux.
            laissees.append(dossier.name)
            continue
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(dossier), str(destination))
        deplacees += 1

    return Rapport(deplacees=deplacees, laissees=tuple(laissees))


async def migrer_les_maisons() -> Rapport:
    """Construit le rattachement depuis la base, puis range les dossiers."""
    async with async_session_factory() as db:
        lignes = (
            await db.execute(
                select(Session.project_id, Session.worktree_path).where(
                    Session.worktree_path.is_not(None)
                )
            )
        ).all()

    maison_par_slug = {
        slug_du_cwd(worktree): sous_chemin_de_maison(project_id)
        for project_id, worktree in lignes
        if worktree
    }
    racine = get_settings().claude_home_root
    # Déplacements de dossiers : du bloquant, donc dans un thread. C'est un
    # one-shot de boot, mais le boot sert aussi le premier appel HTTP.
    rapport = await asyncio.to_thread(ranger_les_dossiers, racine, maison_par_slug)

    if rapport.laissees:
        logger.warning(
            "maisons.migration.non_rattachees",
            dossiers=list(rapport.laissees),
            consequence="ces sessions redemarreront une conversation neuve",
        )
    logger.info(
        "maisons.migration.terminee",
        deplacees=rapport.deplacees,
        laissees=len(rapport.laissees),
    )
    return rapport
```

- [ ] **Step 4: Lancer les tests pour les voir passer**

Run: `cd backend && uv run pytest tests/unit/test_claude_home_migration.py -v`
Expected: PASS, 5 tests

- [ ] **Step 5: Appeler la migration au boot**

Dans `backend/app/main.py`, ajouter l'import en tête :

```python
from app.services.claude_home_migration import migrer_les_maisons
```

et, dans `lifespan`, à l'intérieur du `if not get_settings().is_test:`, après le bloc `init_singletons` :

```python
        try:
            # Idempotente, et jamais fatale : une migration qui échoue coûte
            # des `resume`, pas le démarrage du backend.
            await migrer_les_maisons()
        except Exception:
            logger.exception("maisons.migration.error")
```

- [ ] **Step 6: Lancer la suite entière**

Run: `cd backend && uv run pytest -q`
Expected: PASS

- [ ] **Step 7: Portes de qualité et commit**

```bash
cd backend && uv run ruff check . && uv run ruff format --check . && uv run mypy app && uv run pytest -q
cd .. && git add -A && git commit -m "feat(sessions): les transcripts existants rejoignent la maison de leur projet

Idempotente, appelee au boot, jamais fatale. Ce qui ne se rattache pas reste
en place et se retrouve dans les logs par son nom : rien n'est supprime.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Task 4: Le mode d'exécution et les noms de volumes

Six réglages, dont quatre noms de volumes Docker. Ces noms sont nécessaires parce que `docker run` monte un volume **par son nom**, alors que le backend ne connaît que le chemin où ce volume est monté chez lui : les deux informations ne se déduisent pas l'une de l'autre. Et le nom réel n'est pas celui du compose : compose le préfixe par le nom du projet.

**Files:**
- Modify: `backend/app/core/config.py` (après `claude_home_root`)
- Test: `backend/tests/unit/test_session_container.py` (créé ici, complété en tâche 5)

**Interfaces:**
- Produces: `Settings.session_runtime`, `.session_image`, `.session_network`, `.workspaces_volume`, `.toolchains_volume`, `.claude_home_volume`, `.collectes_volume`.

- [ ] **Step 1: Écrire le test qui échoue**

Créer `backend/tests/unit/test_session_container.py` :

```python
"""Le mode d'exécution des sessions, et les noms de volumes qu'il exige.

Le défaut est `processus` et pas `conteneur` : la valeur sûre est celle qui
marche sans démon Docker joignable, c'est-à-dire en test, en dev local, et sur
une installation dont le backend n'a pas accès au socket. Le mode d'une
installation servie se décide dans le compose de prod, à un seul endroit.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

from app.core.config import Settings

COMPOSE_PROD = Path(__file__).parents[3] / "docker-compose.yml"


def test_le_mode_par_defaut_est_processus() -> None:
    assert Settings().session_runtime == "processus"


def test_le_compose_de_prod_demande_le_mode_conteneur() -> None:
    """Le seul endroit où une installation servie bascule.

    Si cette ligne disparaît, les sessions de prod repassent dans le conteneur
    du backend sans que rien n'échoue, et le trou de la Phase 6 bis se
    rouvre en silence. D'où ce test, qui lit le compose.
    """
    texte = COMPOSE_PROD.read_text(encoding="utf-8")
    assert "SESSION_RUNTIME: conteneur" in texte


def test_les_noms_de_volumes_portent_le_prefixe_du_projet_compose() -> None:
    """Compose préfixe le nom d'un volume par celui du projet.

    Le compose de prod déclare `name: eldir` et un volume `eldir_workspaces` :
    le démon, lui, ne connaît que `eldir_eldir_workspaces`. Un `docker run`
    sur le nom non préfixé créerait un volume vide tout neuf, et la session
    démarrerait sur un worktree inexistant.
    """
    reglages = Settings()
    texte = COMPOSE_PROD.read_text(encoding="utf-8")
    assert "name: eldir\n" in texte
    for nom in (
        reglages.workspaces_volume,
        reglages.toolchains_volume,
        reglages.claude_home_volume,
        reglages.collectes_volume,
    ):
        assert nom.startswith("eldir_eldir_"), nom
        # Le volume existe bien sous son nom court dans le compose.
        assert f"\n  {nom.removeprefix('eldir_')}:\n" in texte
```

- [ ] **Step 2: Lancer le test pour le voir échouer**

Run: `cd backend && uv run pytest tests/unit/test_session_container.py -v`
Expected: FAIL avec `AttributeError: 'Settings' object has no attribute 'session_runtime'`

- [ ] **Step 3: Déclarer les réglages**

Dans `backend/app/core/config.py`, après `claude_home_root` :

```python
    # ── Isolement des sessions (Phase 6 bis) ────────────────────
    # `processus` : le CLI de la session tourne dans le conteneur du backend,
    #   comme avant cette phase. Elle y voit le disque de tous les projets.
    # `conteneur` : un conteneur par session, monté sur son seul worktree, sa
    #   seule clé et la seule maison `.claude` de son projet.
    # Le défaut est `processus` parce que c'est la valeur qui marche sans démon
    # Docker joignable (tests, dev local, installation sans socket). Une
    # installation servie bascule dans le compose de prod, et nulle part
    # ailleurs. Ce réglage n'est pas un drapeau à retirer plus tard : il reste,
    # parce qu'Eldir doit pouvoir tourner là où le backend n'a pas de Docker.
    session_runtime: Literal["processus", "conteneur"] = "processus"
    # Construite par `docker build -t eldir-session:local backend/docker/session`.
    session_image: str = "eldir-session:local"
    # Réseau dédié, sans route vers le réseau interne qui porte Postgres,
    # Redis et le proxy de socket. À créer une fois (cf. docs/deployment.md) :
    # compose ne crée pas un réseau qu'aucun de ses services n'utilise.
    session_network: str = "eldir-sessions"
    # Les noms DOCKER des volumes, à distinguer des `*_root` ci-dessus, qui
    # sont leurs points de montage chez le backend. `docker run` monte un
    # volume par son nom, et compose préfixe ce nom par celui du projet : le
    # volume `eldir_workspaces` du compose de prod (`name: eldir`) s'appelle
    # `eldir_eldir_workspaces` pour le démon. Les deux informations ne se
    # déduisent pas l'une de l'autre, donc elles se déclarent toutes les deux.
    # Une installation dont le projet compose porte un autre nom renseigne ces
    # quatre variables (cf. docs/deployment.md).
    workspaces_volume: str = "eldir_eldir_workspaces"
    toolchains_volume: str = "eldir_eldir_toolchains"
    claude_home_volume: str = "eldir_eldir_claude_home"
    collectes_volume: str = "eldir_eldir_collectes"
```

- [ ] **Step 4: Faire exister ce que le test lit dans le compose**

Dans `docker-compose.yml`, service `backend`, bloc `environment`, ajouter :

```yaml
      # Un conteneur par session (Phase 6 bis). Seul endroit où une
      # installation servie bascule : le défaut du code est `processus`.
      SESSION_RUNTIME: conteneur
```

et, dans la section `volumes:` de fin de fichier, ajouter le volume des collectes (la tâche 10 le monte dans le backend) :

```yaml
  eldir_collectes:
```

- [ ] **Step 5: Lancer le test pour le voir passer**

Run: `cd backend && uv run pytest tests/unit/test_session_container.py -v`
Expected: PASS, 3 tests

- [ ] **Step 6: Portes de qualité et commit**

```bash
cd backend && uv run ruff check . && uv run ruff format --check . && uv run mypy app && uv run pytest -q
cd .. && git add -A && git commit -m "feat(sessions): le mode d'execution et les noms de volumes Docker

Un nom de volume n'est pas un point de montage, et compose prefixe le nom par
celui du projet : les deux informations se declarent toutes les deux.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Task 5: `session_container`, le calcul des montages

Un seul rôle : calculer ce que l'enrobage lit. Pas de lancement, pas d'appel à Docker. C'est ici que se décide la sécurité de la phase, et c'est pour ça que ça se teste sur un dictionnaire, sans démon.

Deux points que la sonde n'avait pas vus, et qui sont mesurés :

1. **Le clone canonique doit être monté.** Un worktree Eldir est un worktree git : son `.git` est un fichier qui pointe vers `<clone>/.git/worktrees/<nom>`. Monté seul, `git status` répond `fatal: not a git repository`. Avec le clone, tout fonctionne et le voisin reste introuvable.
2. **Le toolchain et la collecte sont conditionnels.** `volume-subpath` sur un sous-chemin absent fait échouer `docker run` (code 127) : un projet sans toolchain installé n'a pas de dossier dans ce volume.

**Files:**
- Create: `backend/app/services/session_container.py`
- Test: `backend/tests/unit/test_session_container.py` (complété)

**Interfaces:**
- Consumes: `maison_du_projet`, `sous_chemin_de_maison` (tâche 2), les réglages de la tâche 4, `toolchain_service.root/env_for`, `collect_service.root/env_for`.
- Produces :
  - `chemin_du_clone(worktree: Path) -> Path | None`
  - `env_pour_enrobage(*, project_id: str | None, worktree_abs: Path, ssh_subpath: str | None) -> dict[str, str]`
  - `preparer_la_maison(project_id: str | None) -> None`

- [ ] **Step 1: Écrire les tests qui échouent**

Ajouter à `backend/tests/unit/test_session_container.py` :

```python
import pytest
from app.core.config import get_settings
from app.services.session_container import (
    chemin_du_clone,
    env_pour_enrobage,
    preparer_la_maison,
)


@pytest.fixture
def workspaces(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    """Un faux disque Eldir : un clone, son worktree, et un projet voisin."""
    racine = tmp_path / "workspaces"
    (racine / "u1" / "eldir").mkdir(parents=True)
    (racine / "u1" / "eldir.s1").mkdir()
    (racine / "u2" / "voisin").mkdir(parents=True)
    monkeypatch.setenv("WORKSPACES_ROOT", str(racine))
    monkeypatch.setenv("CLAUDE_HOME_ROOT", str(tmp_path / "maisons"))
    monkeypatch.setenv("TOOLCHAINS_ROOT", str(tmp_path / "toolchains"))
    monkeypatch.setenv("COLLECTES_ROOT", str(tmp_path / "collectes"))
    get_settings.cache_clear()
    yield racine
    get_settings.cache_clear()


def test_le_clone_canonique_se_deduit_du_worktree(workspaces: Path) -> None:
    """Sans ce montage, git ne fonctionne pas du tout dans la session.

    Le `.git` d'un worktree est un fichier qui pointe vers
    `<clone>/.git/worktrees/<nom>`. Mesuré : worktree monté seul, `git status`
    répond `fatal: not a git repository`.
    """
    assert chemin_du_clone(workspaces / "u1" / "eldir.s1") == workspaces / "u1" / "eldir"


def test_un_cwd_sans_point_n_a_pas_de_clone(workspaces: Path) -> None:
    """Le cwd du superviseur, qui n'est le worktree de rien."""
    (workspaces / "_supervisor").mkdir()
    assert chemin_du_clone(workspaces / "_supervisor") is None


def test_les_montages_de_base_sont_calcules(workspaces: Path) -> None:
    env = env_pour_enrobage(
        project_id="p1", worktree_abs=workspaces / "u1" / "eldir.s1", ssh_subpath=None
    )

    assert env["ELDIR_WORKTREE_ABS"] == str(workspaces / "u1" / "eldir.s1")
    assert env["ELDIR_WORKTREE_SUBPATH"] == "u1/eldir.s1"
    assert env["ELDIR_CLONE_SUBPATH"] == "u1/eldir"
    assert env["ELDIR_CLAUDE_HOME_SUBPATH"] == "p1"
    assert env["ELDIR_IMAGE"] == get_settings().session_image
    assert env["ELDIR_NETWORK"] == get_settings().session_network


def test_sans_toolchain_installe_aucun_montage_de_toolchain(workspaces: Path) -> None:
    """Un sous-chemin absent ferait échouer `docker run` en code 127.

    Un projet dont le toolchain n'est pas installé n'a pas de dossier dans ce
    volume : le montage doit disparaître, pas pointer vers rien.
    """
    env = env_pour_enrobage(
        project_id="p1", worktree_abs=workspaces / "u1" / "eldir.s1", ssh_subpath=None
    )
    assert "ELDIR_TOOLCHAIN_SUBPATH" not in env
    assert "ELDIR_COLLECTE_SUBPATH" not in env


def test_aucun_secret_ne_sort_dans_l_environnement_de_l_enrobage(
    workspaces: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """L'enrobage n'a pas besoin d'un seul secret, donc il n'en reçoit aucun.

    Le test ne vérifie pas une liste de noms interdits mais l'absence des
    valeurs : un secret qui arriverait là par un champ renommé serait quand
    même attrapé.
    """
    from app.core.config import Settings

    monkeypatch.setenv("JWT_SECRET", "valeur-sensible-jwt")
    monkeypatch.setenv("ENCRYPTION_KEY", "valeur-sensible-fernet")
    get_settings.cache_clear()

    env = env_pour_enrobage(
        project_id="p1", worktree_abs=workspaces / "u1" / "eldir.s1", ssh_subpath=None
    )

    rendu = "\n".join(f"{c}={v}" for c, v in env.items())
    assert "valeur-sensible-jwt" not in rendu
    assert "valeur-sensible-fernet" not in rendu
    # Et aucune clé de `Settings` marquée secrète ne figure dans les noms.
    noms_secrets = {
        nom.upper()
        for nom, champ in Settings.model_fields.items()
        if "Secret" in str(champ.annotation)
    }
    assert noms_secrets.isdisjoint(env)


def test_la_maison_est_creee_avant_le_lancement(workspaces: Path) -> None:
    """`volume-subpath` exige que le sous-chemin existe déjà.

    Sans ce mkdir, la première session d'un projet échoue au démarrage avec le
    code 127 du démon.
    """
    preparer_la_maison("p1")
    maison = get_settings().claude_home_root / "p1"
    assert (maison / "tmp").is_dir()
    preparer_la_maison("p1")  # idempotent


def test_le_superviseur_a_une_maison_et_pas_de_clone(workspaces: Path) -> None:
    (workspaces / "_supervisor").mkdir()
    env = env_pour_enrobage(
        project_id=None, worktree_abs=workspaces / "_supervisor", ssh_subpath=None
    )
    assert env["ELDIR_CLAUDE_HOME_SUBPATH"] == "_superviseur"
    assert "ELDIR_CLONE_SUBPATH" not in env
```

- [ ] **Step 2: Lancer les tests pour les voir échouer**

Run: `cd backend && uv run pytest tests/unit/test_session_container.py -v`
Expected: FAIL avec `ModuleNotFoundError: No module named 'app.services.session_container'`

- [ ] **Step 3: Écrire le module**

Créer `backend/app/services/session_container.py` :

```python
"""Ce que l'enrobage a besoin de savoir pour lancer une session en conteneur.

Un seul rôle : calculer. Ce module ne lance rien, n'appelle pas Docker et
n'ouvre aucune connexion. Le lancement reste au SDK, qui exécute l'enrobage ;
l'enrobage lit ce que ce module a calculé et construit son `docker run`.

Pourquoi un module à part : les montages **sont** la décision de sécurité de
cette phase. Ici ils se testent sur un dictionnaire, sans démon, et les tests
d'intégration vérifient ensuite pour de vrai qu'un voisin est introuvable.

Deux règles qui valent pour tout ce fichier :

- **Un montage dont le sous-chemin peut ne pas exister est conditionnel.**
  `volume-subpath` sur un sous-chemin absent fait échouer `docker run` avec le
  code 127 (mesuré). Un projet sans toolchain installé n'a pas de dossier dans
  ce volume.
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


def chemin_du_clone(worktree: Path) -> Path | None:
    """Le clone canonique dont ce worktree est un worktree, s'il y en a un.

    Layout de `WorktreeService` : le clone est `<user>/<repo_slug>`, ses
    worktrees `<user>/<repo_slug>.<session_id>` (`SESSION_WORKTREE_TEMPLATE`).
    `slugify` ne laisse passer ni point ni souligné dans `repo_slug`, donc le
    dernier point du nom est forcément le séparateur, et la dérivation est
    exacte.

    Ce montage n'est pas un confort. Le `.git` d'un worktree est un fichier
    qui pointe vers `<clone>/.git/worktrees/<nom>`, et `git commit` depuis un
    worktree écrit ses objets dans le dépôt partagé. Mesuré : worktree monté
    seul, `git status` répond « fatal: not a git repository » ; worktree plus
    clone, branche, log et commit fonctionnent, et le projet voisin reste
    introuvable.

    Rend `None` pour un cwd qui n'est le worktree de rien, comme celui du
    superviseur.
    """
    if "." not in worktree.name:
        return None
    candidat = worktree.parent / worktree.name.rsplit(".", 1)[0]
    return candidat if candidat.is_dir() else None


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
    """
    reglages = get_settings()
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
    démon. Le dossier est créé côté backend, qui voit le même volume.

    `tmp` est créé avec : le CLI s'y calcule son temporaire
    (`CLAUDE_CODE_TMPDIR`), et un dossier créé par Docker comme parent
    implicite de montage appartiendrait à root, ce que le CLI refuse.
    """
    (maison_du_projet(project_id) / "tmp").mkdir(parents=True, exist_ok=True)
```

- [ ] **Step 4: Lancer les tests pour les voir passer**

Run: `cd backend && uv run pytest tests/unit/test_session_container.py -v`
Expected: PASS, 10 tests

- [ ] **Step 5: Portes de qualité et commit**

```bash
cd backend && uv run ruff check . && uv run ruff format --check . && uv run mypy app && uv run pytest -q
cd .. && git add -A && git commit -m "feat(sessions): le calcul des montages d'une session, et le clone qu'il fallait monter

Un worktree Eldir est un worktree git : son .git pointe vers le clone
canonique. Monte seul, git repond 'not a git repository'. Mesure.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Task 6: La matière SSH d'une session

Les clés sont déjà une par projet. Le trou à fermer : le `config` SSH est un fichier unique qui porte les blocs de **tous** les projets, avec leurs noms de machines, utilisateurs et ports. Le monter entier ferait fuiter l'inventaire des machines des autres projets.

Deux contraintes mesurées changent la mise en oeuvre par rapport à la spec :

1. **Un bind mount ne marche pas.** Le `src` d'un bind est résolu par le démon, **sur l'hôte** : `/home/eldir/.ssh/keys/<project_id>` n'existe pas là-bas, c'est un chemin du conteneur backend. Et `volume-subpath` ne monte qu'un dossier, pas un fichier.
2. Donc la matière SSH d'une session est **écrite dans un dossier à elle**, sous le volume des maisons, et montée par sous-chemin, en lecture seule : `<claude_home_root>/<project_id>-ssh/<session_id>/{cle,config}`. Sous-chemin **à côté** de la maison et pas dedans : la maison est montée en écriture, donc tout ce qui est dedans est réécrivable par la session, et un `config` réécrivable n'est plus une garde.

La clé est donc recopiée. La source de vérité reste `ssh_home`, la copie est refaite à chaque démarrage (donc jamais périmée) et supprimée à l'arrêt.

**Files:**
- Modify: `backend/app/services/remote_access_service.py:194-210` (`_write_block`)
- Test: `backend/tests/unit/test_remote_access_service.py`

**Interfaces:**
- Consumes: `maison_du_projet` n'est pas utilisée ici (le dossier est un frère de la maison) ; `get_settings().claude_home_root`.
- Produces :
  - `bloc_ssh(*, project_id: str, alias: str, host: str, user: str, port: int, identity_file: Path, known_hosts: Path) -> str` (fonction pure, au niveau module)
  - `RemoteAccessService.materiel_de_session(project_id: str, session_id: str) -> str | None` : écrit `cle` et `config`, rend le sous-chemin à monter, ou `None` si le projet n'a pas d'accès distant
  - `RemoteAccessService.supprimer_materiel_de_session(project_id: str, session_id: str) -> None`
  - Chemins dans le conteneur, fixés ici et lus par l'image en tâche 7 : clé `/eldir/ssh/cle`, config `/eldir/ssh/config`, `known_hosts` `/eldir/maison/known_hosts`.

- [ ] **Step 1: Écrire les tests qui échouent**

Ajouter à `backend/tests/unit/test_remote_access_service.py` :

```python
def test_le_bloc_ssh_est_une_fonction_pure() -> None:
    """Le même générateur sert le `config` partagé et celui d'une session.

    Dupliquer la génération, c'est accepter qu'un durcissement n'arrive que
    dans une des deux copies.
    """
    from app.services.remote_access_service import bloc_ssh

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
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Un seul bloc, et pas l'inventaire des machines des autres projets.

    C'est le vrai trou de l'accès distant : la clé était déjà par projet, le
    `config` ne l'était pas.
    """
    from app.core.config import get_settings
    from app.services.remote_access_service import RemoteAccessService

    monkeypatch.setenv("SSH_HOME", str(tmp_path / "ssh"))
    monkeypatch.setenv("CLAUDE_HOME_ROOT", str(tmp_path / "maisons"))
    get_settings.cache_clear()
    service = RemoteAccessService()
    try:
        # deux projets configurés dans le `config` partagé
        service._ecrire_cle_factice("p1")
        service._ecrire_cle_factice("p2")
        service._write_block("p1", "eldir-un", "un.exemple.lan", "deploy", 22)
        service._write_block("p2", "eldir-deux", "deux.exemple.lan", "root", 2222)

        sous_chemin = service.materiel_de_session("p1", "s1")

        assert sous_chemin == "p1-ssh/s1"
        dossier = get_settings().claude_home_root / sous_chemin
        config = (dossier / "config").read_text(encoding="utf-8")
        assert "un.exemple.lan" in config
        assert "deux.exemple.lan" not in config
        assert "eldir-deux" not in config
        # la clé est copiée, et seule son propriétaire peut la lire
        assert (dossier / "cle").read_text(encoding="utf-8") == "cle-factice-p1"
        assert oct((dossier / "cle").stat().st_mode)[-3:] == "600"
    finally:
        get_settings.cache_clear()


def test_sans_acces_distant_il_n_y_a_pas_de_materiel(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Le projet n'a pas de clé du tout dans son conteneur."""
    from app.core.config import get_settings
    from app.services.remote_access_service import RemoteAccessService

    monkeypatch.setenv("SSH_HOME", str(tmp_path / "ssh"))
    monkeypatch.setenv("CLAUDE_HOME_ROOT", str(tmp_path / "maisons"))
    get_settings.cache_clear()
    try:
        assert RemoteAccessService().materiel_de_session("p1", "s1") is None
    finally:
        get_settings.cache_clear()


def test_le_materiel_disparait_a_l_arret(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.core.config import get_settings
    from app.services.remote_access_service import RemoteAccessService

    monkeypatch.setenv("SSH_HOME", str(tmp_path / "ssh"))
    monkeypatch.setenv("CLAUDE_HOME_ROOT", str(tmp_path / "maisons"))
    get_settings.cache_clear()
    service = RemoteAccessService()
    try:
        service._ecrire_cle_factice("p1")
        service._write_block("p1", "eldir-un", "un.exemple.lan", "deploy", 22)
        sous_chemin = service.materiel_de_session("p1", "s1")
        assert sous_chemin is not None

        service.supprimer_materiel_de_session("p1", "s1")

        assert not (get_settings().claude_home_root / sous_chemin).exists()
        # idempotent : un arrêt après un crash ne doit pas lever
        service.supprimer_materiel_de_session("p1", "s1")
    finally:
        get_settings.cache_clear()
```

Le helper de test `_ecrire_cle_factice` n'existe pas : l'ajouter comme méthode privée du service, utile aux tests comme à rien d'autre serait de la triche. On l'écrit donc **dans le test**, en fonction locale du module de test :

```python
def _ecrire_cle_factice(service, project_id: str) -> None:
    """Une clé privée factice au bon endroit, pour ne pas appeler `ssh-keygen`."""
    cle = service.key_path(project_id)
    cle.parent.mkdir(parents=True, exist_ok=True)
    cle.write_text(f"cle-factice-{project_id}", encoding="utf-8")
    os.chmod(cle, 0o600)
```

et remplacer les appels `service._ecrire_cle_factice("pX")` par `_ecrire_cle_factice(service, "pX")` dans les trois tests ci-dessus.

- [ ] **Step 2: Lancer les tests pour les voir échouer**

Run: `cd backend && uv run pytest tests/unit/test_remote_access_service.py -v`
Expected: FAIL avec `ImportError: cannot import name 'bloc_ssh'`

- [ ] **Step 3: Extraire `bloc_ssh` en fonction pure**

Dans `backend/app/services/remote_access_service.py`, au niveau module (après `_alias_for`) :

```python
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
```

et remplacer le corps de `_write_block` par un appel :

```python
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
```

- [ ] **Step 4: Écrire la matière SSH par session**

Toujours dans `RemoteAccessService`, après `_write_block`, et les deux constantes en tête de module :

```python
# Où la session voit sa matière SSH, côté conteneur. L'image y branche son
# `Include` (cf. backend/docker/session/Dockerfile) ; l'enrobage y monte le dossier en
# lecture seule.
CLE_DANS_LE_CONTENEUR = Path("/eldir/ssh/cle")
CONFIG_DANS_LE_CONTENEUR = Path("/eldir/ssh/config")
# Dans la maison, donc en écriture et persistant par projet : `accept-new`
# doit pouvoir figer l'empreinte vue à la première connexion.
KNOWN_HOSTS_DANS_LE_CONTENEUR = Path("/eldir/maison/known_hosts")
```

```python
    # ── matière SSH d'une session en conteneur ───────────────────
    def _dossier_de_session(self, project_id: str, session_id: str) -> Path:
        """Frère de la maison du projet, et pas dedans.

        La maison est montée en écriture (le CLI y écrit son transcript) :
        tout ce qui est dedans est réécrivable par la session, et un `config`
        réécrivable n'est plus une garde. Le sous-chemin est donc voisin.
        """
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
        source = self.key_path(project_id)
        if not etat.configured or not etat.alias or not source.exists():
            return None

        dossier = self._dossier_de_session(project_id, session_id)
        _preparer_dossier(dossier)
        cible = dossier / CLE_DANS_LE_CONTENEUR.name
        shutil.copyfile(source, cible)
        _proteger(cible)
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
        shutil.rmtree(self._dossier_de_session(project_id, session_id), ignore_errors=True)
```

Ajouter `import shutil` en tête de fichier s'il n'y est pas, et vérifier que `Path` et `get_settings` y sont déjà.

- [ ] **Step 5: Lancer les tests pour les voir passer**

Run: `cd backend && uv run pytest tests/unit/test_remote_access_service.py -v`
Expected: PASS, les tests existants compris (le `config` partagé garde exactement le même contenu : seule la façon de le fabriquer a changé)

- [ ] **Step 6: Portes de qualité et commit**

```bash
cd backend && uv run ruff check . && uv run ruff format --check . && uv run mypy app && uv run pytest -q
cd .. && git add -A && git commit -m "feat(ssh): un config a un seul bloc par session, et sa cle en lecture seule

Le config partage porte les machines de tous les projets : le monter entier
ferait fuiter leur inventaire. Un bind mount ne marche pas (le src est resolu
par le demon, sur l'hote), donc la matiere SSH d'une session est ecrite dans
un dossier voisin de la maison et montee par sous-chemin.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Task 7: L'image de session

Une seule image pour toutes les sessions : Node 20, `git`, `openssh-client`, et `@anthropic-ai/claude-code` épinglé. Le toolchain du projet n'est **pas** dedans : il est monté en lecture seule depuis le volume existant, au même chemin absolu que chez le backend. Une image par projet serait une image à reconstruire à chaque ajout d'outil, pour un gain nul.

**Files:**
- Create: `backend/docker/session/Dockerfile`, `backend/docker/session/entree-session`
- Test: `backend/tests/integration/test_isolement_sessions.py` (créé ici avec les deux tests d'image, complété en tâche 8)
- Modify: `backend/pyproject.toml` (marqueur `docker`)

**Interfaces:**
- Consumes: les chemins fixés en tâche 6 (`/eldir/ssh/config`, `/eldir/ssh/cle`).
- Produces: l'image `eldir-session:local`, avec `claude` dans le PATH, l'uid 1000, `/eldir/maison` et `/eldir/ssh` existants, et `Include /eldir/ssh/config*` dans la config SSH système.

- [ ] **Step 1: Déclarer le marqueur `docker`**

`addopts` contient `--strict-markers` : un marqueur non déclaré fait échouer la collecte. Dans `backend/pyproject.toml`, section `[tool.pytest.ini_options]` :

```toml
markers = [
    # Tests qui ont besoin d'un démon Docker joignable et de
    # `--mount volume-subpath` (Docker 25+). Sautés sinon. Ils ne lancent
    # jamais le CLI Claude, donc ils ne consomment aucun credit.
    "docker: a besoin d'un demon Docker (Docker 25+)",
]
```

- [ ] **Step 2: Écrire les tests qui échouent**

Créer `backend/tests/integration/test_isolement_sessions.py` :

```python
"""Ce qu'une session ne peut pas atteindre, vérifié sur un vrai démon.

Ces tests sont le coeur de la Phase 6 bis : ils échouent si l'isolement se
défait. Chacun porte la mutation qui doit le faire tomber, pour que personne
n'ait à deviner ce qu'il protège.

Le critère n'est pas qu'un accès soit refusé mais qu'il soit **impossible** :
une règle qui refuse se négocie par injection de prompt, un fichier qui
n'existe pas dans l'univers de la session ne se négocie pas.

Aucun de ces tests ne lance le CLI Claude : ils ne consomment aucun credit.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

pytestmark = pytest.mark.docker

DOSSIER_IMAGE = Path(__file__).parents[2] / "docker" / "session"
IMAGE = "eldir-session:local"
VOLUME = "eldir-test-isolement"
WORKSPACES = "/var/eldir/workspaces"


def _docker(*args: str, attendu: int | None = 0) -> subprocess.CompletedProcess[str]:
    proc = subprocess.run(
        ["docker", *args], capture_output=True, text=True, check=False, timeout=300
    )
    if attendu is not None:
        assert proc.returncode == attendu, f"{args}\n{proc.stdout}\n{proc.stderr}"
    return proc


@pytest.fixture(scope="module", autouse=True)
def demon_docker() -> None:
    if shutil.which("docker") is None:
        pytest.skip("docker absent")
    if subprocess.run(["docker", "info"], capture_output=True, check=False).returncode:
        pytest.skip("demon docker injoignable")
    version = subprocess.run(
        ["docker", "version", "--format", "{{.Server.Version}}"],
        capture_output=True,
        text=True,
        check=False,
    ).stdout.strip()
    majeure = int(version.split(".")[0]) if version[:1].isdigit() else 0
    if majeure < 25:
        pytest.skip(f"volume-subpath exige Docker 25+, vu {version!r}")


@pytest.fixture(scope="module")
def image() -> str:
    _docker("build", "-t", IMAGE, str(DOSSIER_IMAGE))
    return IMAGE


@pytest.fixture(scope="module")
def volume(image: str) -> str:
    """Deux projets voisins dans un volume : chacun un clone et un worktree."""
    _docker("volume", "create", VOLUME)
    _docker(
        "run",
        "--rm",
        "-v",
        f"{VOLUME}:{WORKSPACES}",
        "--entrypoint",
        "sh",
        image,
        "-c",
        f"""set -e
        for p in projet-a projet-b; do
          mkdir -p {WORKSPACES}/$p
          cd {WORKSPACES}/$p
          git init -q depot && cd depot
          git config user.email eldir@exemple.lan && git config user.name eldir
          echo "code de $p" > fichier.txt
          git add -A && git commit -qm premier
          git worktree add -q -b claude/t {WORKSPACES}/$p/depot.s1
          echo "secret de $p" > {WORKSPACES}/$p/depot.s1/secret.txt
        done
        """,
    )
    yield VOLUME
    _docker("volume", "rm", "-f", VOLUME, attendu=None)


def test_l_image_porte_le_cli_claude(image: str) -> None:
    """Le SDK appelle `claude -v` avant tout : si ça rate, rien ne démarre."""
    proc = _docker("run", "--rm", "--entrypoint", "claude", image, "-v")
    assert proc.stdout.strip()


def test_l_image_tourne_en_uid_1000(image: str) -> None:
    """Le CLI refuse `bypassPermissions` en root, et les volumes sont à 1000."""
    proc = _docker("run", "--rm", "--entrypoint", "id", image, "-u")
    assert proc.stdout.strip() == "1000"


def test_ssh_lit_le_config_monte(image: str, tmp_path: Path) -> None:
    """Le `config` d'une session n'est ni `~/.ssh/config` ni un chemin système.

    Sans le `Include` de l'image, `ssh` ne le trouverait pas, et « Connecter au
    serveur » cesserait de marcher sans que rien ne le dise.
    """
    (tmp_path / "config").write_text(
        "Host eldir-essai\n"
        "    HostName machine.exemple.lan\n"
        "    IdentityFile /eldir/ssh/cle\n",
        encoding="utf-8",
    )
    proc = _docker(
        "run",
        "--rm",
        "--mount",
        f"type=bind,src={tmp_path},dst=/eldir/ssh,readonly",
        "--entrypoint",
        "ssh",
        image,
        "-G",
        "eldir-essai",
    )
    assert "hostname machine.exemple.lan" in proc.stdout
    assert "identityfile /eldir/ssh/cle" in proc.stdout


def test_ssh_demarre_sans_config_monte(image: str) -> None:
    """Un projet sans accès distant n'a aucun montage SSH.

    Le motif `config*` du `Include` rend l'absence de fichier inoffensive : un
    `Include` sur un chemin littéral absent ferait échouer tout `ssh`.
    """
    proc = _docker("run", "--rm", "--entrypoint", "ssh", image, "-G", "une-machine")
    assert "hostname une-machine" in proc.stdout
```

- [ ] **Step 3: Lancer les tests pour les voir échouer**

Run: `cd backend && uv run pytest tests/integration/test_isolement_sessions.py -v -m docker`
Expected: FAIL au build de l'image (`backend/docker/session/Dockerfile` n'existe pas)

- [ ] **Step 4: Écrire l'entrée de l'image**

Créer `backend/docker/session/entree-session` :

```sh
#!/bin/sh
# Entrée de l'image de session. Un seul travail : poser le PATH du toolchain
# quand il y en a un.
#
# Pourquoi ici et pas dans l'enrobage : le chemin du toolchain est connu du
# backend, mais le PATH de base est celui de cette image. Transmettre celui du
# backend y mettrait des dossiers qui n'existent pas dans ce conteneur.
if [ -n "${ELDIR_TOOLCHAIN:-}" ]; then
    PATH="$ELDIR_TOOLCHAIN/bin:$PATH"
    export PATH
fi
exec "$@"
```

- [ ] **Step 5: Écrire le Dockerfile**

Créer `backend/docker/session/Dockerfile` :

```dockerfile
# Image des sessions Eldir : le CLI Claude, git, ssh, et rien de plus.
#
# Le toolchain du projet n'est pas ici : il est monté en lecture seule depuis
# le volume des toolchains, au même chemin absolu que chez le backend. Une
# image par projet serait une image à reconstruire à chaque ajout d'outil,
# pour un gain nul.
#
# Construite par `docker build -t eldir-session:local backend/docker/session`
# (cf. scripts/install-eldir.sh et docs/deployment.md).
FROM node:20-bookworm-slim

# Épinglée, et pas `latest` : le backend et la session doivent parler la même
# version du protocole de contrôle. À remonter en même temps que celle du
# backend (cf. backend/Dockerfile).
ARG CLAUDE_CLI_VERSION=2.1.316
ARG DEBIAN_FRONTEND=noninteractive

ENV CI=true \
    npm_config_fund=false \
    npm_config_audit=false \
    npm_config_update_notifier=false \
    npm_config_progress=false

RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      git ca-certificates openssh-client \
 && rm -rf /var/lib/apt/lists/*

RUN npm install -g @anthropic-ai/claude-code@${CLAUDE_CLI_VERSION} \
 && command -v claude

# La session lit son `config` SSH là où l'enrobage le monte. Sans cette ligne
# `ssh` ne le trouverait pas : son chemin n'est ni `~/.ssh/config` ni un
# chemin système. Le motif `config*` rend l'absence de fichier inoffensive,
# pour un projet qui n'a pas d'accès distant.
RUN sed -i '1i Include /eldir/ssh/config*' /etc/ssh/ssh_config

# node:20 fournit déjà un utilisateur d'uid 1000. L'enrobage lance le
# conteneur avec l'uid du backend (1000 aussi), et les fichiers des volumes
# appartiennent à cet uid. Le CLI refuse par ailleurs `bypassPermissions` en
# root.
#
# Les deux points de montage existent dans l'image : Docker crée un parent de
# montage manquant en root, et un dossier root dans la maison empêcherait le
# CLI d'y écrire.
RUN mkdir -p /eldir/maison /eldir/ssh \
 && chown -R 1000:1000 /eldir

COPY entree-session /usr/local/bin/entree-session
RUN chmod 0755 /usr/local/bin/entree-session

USER 1000:1000
WORKDIR /eldir/maison
ENTRYPOINT ["/usr/local/bin/entree-session"]
```

- [ ] **Step 6: Lancer les tests pour les voir passer**

Run: `cd backend && uv run pytest tests/integration/test_isolement_sessions.py -v -m docker`
Expected: PASS, 4 tests (le build prend une minute la première fois)

- [ ] **Step 7: Vérifier le saut propre sans démon**

Run: `cd backend && DOCKER_HOST=tcp://127.0.0.1:1 uv run pytest tests/integration/test_isolement_sessions.py -q`
Expected: tous sautés, aucun échec

- [ ] **Step 8: Portes de qualité et commit**

```bash
cd backend && uv run ruff check . && uv run ruff format --check . && uv run mypy app && uv run pytest -q
cd .. && git add -A && git commit -m "feat(sessions): l'image des sessions, le CLI epingle et le config SSH monte

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Task 8: L'enrobage, et les trois tests d'isolement

Le coeur du lot. L'enrobage est ce que le SDK lance à la place du CLI : il se remplace par un `docker run -i`, et le protocole de contrôle traverse le tube stdio sans adaptation.

Deux familles de tests, et les deux comptent :

- **Sans démon**, un faux `docker` dans le PATH, qui imprime ses arguments : c'est la ligne de commande qui est la décision, et elle se vérifie en quelques millisecondes.
- **Avec démon**, les trois tests d'isolement de la spec : le worktree voisin, la clé SSH voisine, la maison `.claude` voisine.

**Files:**
- Create: `backend/docker/session/claude-dans-un-conteneur`, `backend/tests/unit/test_enrobage.py`
- Test: `backend/tests/integration/test_isolement_sessions.py` (complété)

**Interfaces:**
- Consumes: les variables produites par `env_pour_enrobage` (tâche 5) et le sous-chemin SSH (tâche 6).
- Produces: le script `backend/docker/session/claude-dans-un-conteneur`, chemin que la tâche 9 passe à `cli_path`.

- [ ] **Step 1: Écrire les tests de ligne de commande**

Créer `backend/tests/unit/test_enrobage.py` :

```python
"""La ligne de commande que l'enrobage construit.

C'est la commande qui est la décision : ce qui n'y figure pas n'existe pas
dans le conteneur. On la lit avec un faux `docker` qui imprime ses arguments,
donc sans démon, en quelques millisecondes.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

ENROBAGE = Path(__file__).parents[2] / "docker" / "session" / "claude-dans-un-conteneur"

BASE = {
    "ELDIR_IMAGE": "eldir-session:local",
    "ELDIR_NETWORK": "eldir-sessions",
    "ELDIR_WORKSPACES_VOLUME": "vol_ws",
    "ELDIR_WORKTREE_ABS": "/var/eldir/workspaces/u1/depot.s1",
    "ELDIR_WORKTREE_SUBPATH": "u1/depot.s1",
    "ELDIR_CLAUDE_HOME_VOLUME": "vol_maisons",
    "ELDIR_CLAUDE_HOME_SUBPATH": "p1",
}


@pytest.fixture
def faux_docker(tmp_path: Path) -> Path:
    binaire = tmp_path / "bin"
    binaire.mkdir()
    (binaire / "docker").write_text('#!/bin/sh\nprintf "%s\\n" "$@"\n', encoding="utf-8")
    os.chmod(binaire / "docker", 0o755)
    return binaire


def lancer(faux_docker: Path, variables: dict[str, str], *args: str) -> list[str]:
    env = {
        "PATH": f"{faux_docker}:{os.environ['PATH']}",
        "PWD": variables.get("ELDIR_WORKTREE_ABS", "/"),
        **variables,
    }
    proc = subprocess.run(
        ["sh", str(ENROBAGE), *args],
        capture_output=True,
        text=True,
        check=True,
        env=env,
        cwd="/",
        timeout=30,
    )
    return proc.stdout.splitlines()


def test_les_montages_de_base_sont_la(faux_docker: Path) -> None:
    sortie = lancer(faux_docker, BASE, "--version")

    assert "run" in sortie
    assert "-i" in sortie and "--rm" in sortie and "--init" in sortie
    assert "eldir-sessions" in sortie
    assert (
        "type=volume,src=vol_ws,dst=/var/eldir/workspaces/u1/depot.s1,volume-subpath=u1/depot.s1"
        in sortie
    )
    assert "type=volume,src=vol_maisons,dst=/eldir/maison,volume-subpath=p1" in sortie
    # le cwd du worktree, que le SDK a posé, devient celui du conteneur
    assert "/var/eldir/workspaces/u1/depot.s1" in sortie
    # les arguments du CLI passent tels quels, après le nom de l'image
    assert sortie[-1] == "--version"
    assert sortie[-2] == "claude"
    assert sortie[-3] == "eldir-session:local"


def test_ce_qui_est_en_lecture_seule_l_est(faux_docker: Path) -> None:
    """Le toolchain, la collecte et la matière SSH : la session les lit."""
    sortie = lancer(
        faux_docker,
        {
            **BASE,
            "ELDIR_TOOLCHAINS_VOLUME": "vol_tc",
            "ELDIR_TOOLCHAIN_ABS": "/var/eldir/toolchains/p1",
            "ELDIR_TOOLCHAIN_SUBPATH": "p1",
            "ELDIR_COLLECTES_VOLUME": "vol_co",
            "ELDIR_COLLECTE_ABS": "/var/eldir/collectes/p1",
            "ELDIR_COLLECTE_SUBPATH": "p1",
            "ELDIR_SSH_SUBPATH": "p1-ssh/s1",
        },
    )

    assert (
        "type=volume,src=vol_tc,dst=/var/eldir/toolchains/p1,volume-subpath=p1,readonly"
        in sortie
    )
    assert (
        "type=volume,src=vol_co,dst=/var/eldir/collectes/p1,volume-subpath=p1,readonly"
        in sortie
    )
    assert (
        "type=volume,src=vol_maisons,dst=/eldir/ssh,volume-subpath=p1-ssh/s1,readonly"
        in sortie
    )


def test_le_clone_canonique_est_monte_en_ecriture(faux_docker: Path) -> None:
    """`git commit` depuis un worktree écrit ses objets dans le dépôt partagé."""
    sortie = lancer(
        faux_docker,
        {
            **BASE,
            "ELDIR_CLONE_ABS": "/var/eldir/workspaces/u1/depot",
            "ELDIR_CLONE_SUBPATH": "u1/depot",
        },
    )

    montage = next(m for m in sortie if "dst=/var/eldir/workspaces/u1/depot," in m)
    assert montage.endswith("volume-subpath=u1/depot")
    assert "readonly" not in montage


def test_ce_qui_n_est_pas_nomme_n_est_pas_monte(faux_docker: Path) -> None:
    """Un sous-chemin absent ferait échouer `docker run` en code 127.

    Un projet sans toolchain, sans collecte et sans accès distant ne porte
    aucun de ces trois montages.
    """
    sortie = lancer(faux_docker, BASE)

    assert not [m for m in sortie if "toolchains" in m]
    assert not [m for m in sortie if "collectes" in m]
    assert not [m for m in sortie if "/eldir/ssh" in m]


def test_la_maison_et_le_temporaire_sont_poses(faux_docker: Path) -> None:
    """`CLAUDE_CODE_TMPDIR` est explicite, et ce n'est pas un détail.

    Le CLI se calcule sinon un temporaire `/tmp/claude-<uid>` et refuse de
    démarrer s'il le trouve possédé par un autre utilisateur : « Temp
    directory /tmp/claude-1000 is owned by uid 0, expected 1000. Refusing to
    use it ». Docker crée les parents de montage en root, donc un montage dont
    le chemin passe par `/tmp` suffit à déclencher ça.
    """
    sortie = lancer(faux_docker, BASE)

    assert "HOME=/eldir/maison" in sortie
    assert "CLAUDE_CODE_TMPDIR=/eldir/maison/tmp" in sortie


def test_aucun_secret_du_backend_ne_passe(faux_docker: Path) -> None:
    """Le filet devient un choix : on nomme ce qui entre, pas ce qu'on retire.

    `env_a_masquer_pour_cli` est une liste de refus dérivée de `Settings` :
    correcte, mais elle protège ce qu'Eldir connaît. Ici `DATABASE_URL` et
    `JWT_SECRET` n'existent pas dans le conteneur, qu'Eldir y ait pensé ou non.
    """
    sortie = lancer(
        faux_docker,
        {**BASE, "DATABASE_URL": "postgres://x", "JWT_SECRET": "s3cr3t"},
    )

    rendu = "\n".join(sortie)
    assert "DATABASE_URL" not in rendu
    assert "JWT_SECRET" not in rendu
    assert "s3cr3t" not in rendu


def test_une_variable_obligatoire_absente_fait_echouer_tot(faux_docker: Path) -> None:
    """Mieux vaut un refus nommé qu'un `docker run` sur un montage vide."""
    partiel = {c: v for c, v in BASE.items() if c != "ELDIR_WORKTREE_SUBPATH"}
    proc = subprocess.run(
        ["sh", str(ENROBAGE), "-v"],
        capture_output=True,
        text=True,
        check=False,
        env={"PATH": f"{faux_docker}:{os.environ['PATH']}", **partiel},
        timeout=30,
    )

    assert proc.returncode != 0
    assert "ELDIR_WORKTREE_SUBPATH" in proc.stderr


def test_un_chemin_avec_un_espace_est_refuse(faux_docker: Path) -> None:
    """`sh` n'a pas de tableaux : les montages optionnels passent par un
    découpage de mots. `slugify` et les UUID n'en produisent jamais ; si ça
    change un jour, mieux vaut un refus ici qu'un montage coupé en deux."""
    proc = subprocess.run(
        ["sh", str(ENROBAGE), "-v"],
        capture_output=True,
        text=True,
        check=False,
        env={
            "PATH": f"{faux_docker}:{os.environ['PATH']}",
            **{**BASE, "ELDIR_WORKTREE_ABS": "/var/eldir/mon dossier/depot.s1"},
        },
        timeout=30,
    )

    assert proc.returncode != 0
    assert "espace" in proc.stderr
```

- [ ] **Step 2: Lancer les tests pour les voir échouer**

Run: `cd backend && uv run pytest tests/unit/test_enrobage.py -v`
Expected: FAIL, le script n'existe pas (`sh: can't open ...claude-dans-un-conteneur`)

- [ ] **Step 3: Écrire l'enrobage**

Créer `backend/docker/session/claude-dans-un-conteneur` :

```sh
#!/bin/sh
# Passé à `ClaudeAgentOptions(cli_path=...)` : le SDK nous lance à la place du
# CLI `claude`, avec le cwd du worktree et son environnement, puis parle au
# processus par stdin/stdout. On remplace ce processus par un `docker run -i`,
# et le protocole de contrôle traverse le tube sans adaptation (mesuré).
#
# Le SDK reste dans le processus du backend : les hooks `PreToolUse` et
# `PostToolUse` continuent donc de s'exécuter côté backend, en Python. La
# porte de publication et la garde d'accès distant restent hors du périmètre
# qu'elles contraignent, et c'est tout l'intérêt de cette approche.
#
# Deuxième intérêt : le conteneur ne reçoit QUE ce que ce script nomme.
# `DATABASE_URL`, `JWT_SECRET`, `ENCRYPTION_KEY` et le reste n'existent pas
# dedans, qu'Eldir y ait pensé ou non. Le masque d'environnement du backend
# redevient un filet au lieu d'être la seule garde.
#
# Ce que ce script lit est calculé par `app/services/session_container.py`.
set -e

: "${ELDIR_IMAGE:?manque pour lancer la session}"
: "${ELDIR_NETWORK:?manque pour lancer la session}"
: "${ELDIR_WORKSPACES_VOLUME:?manque pour lancer la session}"
: "${ELDIR_WORKTREE_ABS:?manque pour lancer la session}"
: "${ELDIR_WORKTREE_SUBPATH:?manque pour lancer la session}"
: "${ELDIR_CLAUDE_HOME_VOLUME:?manque pour lancer la session}"
: "${ELDIR_CLAUDE_HOME_SUBPATH:?manque pour lancer la session}"

# `sh` n'a pas de tableaux : les montages optionnels ci-dessous passent par un
# découpage de mots. `slugify` et les UUID ne produisent jamais d'espace ; si
# ça change un jour, mieux vaut un refus ici qu'un montage coupé en deux.
case "$ELDIR_WORKTREE_ABS$ELDIR_WORKTREE_SUBPATH$ELDIR_CLAUDE_HOME_SUBPATH" in
*" "*)
    echo "enrobage: un chemin de montage contient un espace, refuse" >&2
    exit 2
    ;;
esac

montages=""

# Le clone canonique du projet, en écriture. Pas un confort : le `.git` d'un
# worktree est un fichier qui pointe vers `<clone>/.git/worktrees/<nom>`, et
# `git commit` depuis un worktree écrit ses objets dans le dépôt partagé.
# Monté sans lui, git répond « fatal: not a git repository ». Mesuré.
if [ -n "${ELDIR_CLONE_SUBPATH:-}" ]; then
    montages="$montages --mount type=volume,src=$ELDIR_WORKSPACES_VOLUME,dst=$ELDIR_CLONE_ABS,volume-subpath=$ELDIR_CLONE_SUBPATH"
fi

# Le toolchain du projet, en lecture seule : la session l'exécute, elle n'a pas
# à l'écrire. Monté au même chemin absolu que chez le backend, pour que
# `$ELDIR_TOOLCHAIN` et les chemins inscrits dans les outils installés restent
# vrais. Conditionnel : un projet sans toolchain n'a pas de sous-chemin, et un
# `volume-subpath` absent fait échouer `docker run` (code 127).
if [ -n "${ELDIR_TOOLCHAIN_SUBPATH:-}" ]; then
    montages="$montages --mount type=volume,src=$ELDIR_TOOLCHAINS_VOLUME,dst=$ELDIR_TOOLCHAIN_ABS,volume-subpath=$ELDIR_TOOLCHAIN_SUBPATH,readonly"
fi

# Ce qui a été ramené d'un serveur avant le démarrage (cf. `CollectService`),
# en lecture seule et au même chemin absolu, pour la même raison.
if [ -n "${ELDIR_COLLECTE_SUBPATH:-}" ]; then
    montages="$montages --mount type=volume,src=$ELDIR_COLLECTES_VOLUME,dst=$ELDIR_COLLECTE_ABS,volume-subpath=$ELDIR_COLLECTE_SUBPATH,readonly"
fi

# La clé SSH du projet et un `config` à un seul bloc, en lecture seule. Le
# `config` partagé du backend porte les machines de tous les projets : le
# monter entier ferait fuiter leur inventaire.
if [ -n "${ELDIR_SSH_SUBPATH:-}" ]; then
    montages="$montages --mount type=volume,src=$ELDIR_CLAUDE_HOME_VOLUME,dst=/eldir/ssh,volume-subpath=$ELDIR_SSH_SUBPATH,readonly"
fi

# `-w "$PWD"` : le SDK règle le cwd du processus sur le worktree, donc notre
# `$PWD` EST le worktree. Le worktree est monté au même chemin absolu que sur
# l'hôte, sinon les chemins que la session manipule, que les hooks inspectent
# et que le diff viewer affiche désigneraient des fichiers que le backend ne
# connaît pas.
#
# `CLAUDE_CODE_TMPDIR` est explicite : le CLI se calcule sinon un temporaire
# `/tmp/claude-<uid>` et refuse de démarrer s'il le trouve possédé par un
# autre utilisateur. Docker crée les parents de montage en root, donc un
# montage dont le chemin passe par `/tmp` suffit à déclencher ça.
#
# Les `-e` sans valeur transmettent la variable du backend si elle existe, et
# rien sinon : le credential Claude (sous celui des deux noms qui est
# présent), le marqueur d'entrée du SDK, et les trois variables du projet.
exec docker run -i --rm --init \
    --network "$ELDIR_NETWORK" \
    -u "$(id -u):$(id -g)" \
    --mount "type=volume,src=$ELDIR_WORKSPACES_VOLUME,dst=$ELDIR_WORKTREE_ABS,volume-subpath=$ELDIR_WORKTREE_SUBPATH" \
    --mount "type=volume,src=$ELDIR_CLAUDE_HOME_VOLUME,dst=/eldir/maison,volume-subpath=$ELDIR_CLAUDE_HOME_SUBPATH" \
    $montages \
    -e HOME=/eldir/maison \
    -e CLAUDE_CODE_TMPDIR=/eldir/maison/tmp \
    -e ANTHROPIC_API_KEY \
    -e CLAUDE_CODE_OAUTH_TOKEN \
    -e CLAUDE_CODE_ENTRYPOINT \
    -e ELDIR_TOOLCHAIN \
    -e ELDIR_COLLECTE \
    -e ELDIR_REMOTE_HOST \
    -w "$PWD" \
    "$ELDIR_IMAGE" claude "$@"
```

Le rendre exécutable : `chmod 0755 backend/docker/session/claude-dans-un-conteneur`

- [ ] **Step 4: Lancer les tests de ligne de commande**

Run: `cd backend && uv run pytest tests/unit/test_enrobage.py -v`
Expected: PASS, 8 tests

- [ ] **Step 5: Écrire les trois tests d'isolement**

Ajouter à `backend/tests/integration/test_isolement_sessions.py` :

```python
def _run_session(image: str, volume: str, *montages: str, commande: str) -> subprocess.CompletedProcess[str]:
    """Un conteneur de session monté comme l'enrobage le monterait."""
    return _docker(
        "run",
        "--rm",
        "--network",
        "none",
        *[arg for montage in montages for arg in ("--mount", montage)],
        "--entrypoint",
        "sh",
        image,
        "-c",
        commande,
        attendu=None,
    )


def test_une_session_ne_lit_pas_le_worktree_voisin(image: str, volume: str) -> None:
    """Le test central de la Phase 6 bis.

    Mutation qui doit le faire tomber : monter la racine `workspaces` au lieu
    du sous-chemin du worktree.
    """
    proc = _run_session(
        image,
        volume,
        f"type=volume,src={volume},dst={WORKSPACES}/projet-a/depot.s1,volume-subpath=projet-a/depot.s1",
        f"type=volume,src={volume},dst={WORKSPACES}/projet-a/depot,volume-subpath=projet-a/depot",
        commande=f"""
        cd {WORKSPACES}/projet-a/depot.s1
        echo "git chez moi : $(git rev-parse --abbrev-ref HEAD)"
        echo "mon secret   : $(cat secret.txt)"
        cat {WORKSPACES}/projet-b/depot.s1/secret.txt 2>&1
        """,
    )

    # son propre travail marche, git compris
    assert "git chez moi : claude/t" in proc.stdout
    assert "secret de projet-a" in proc.stdout
    # et le voisin n'existe pas, sans refus de permission à négocier
    assert "secret de projet-b" not in proc.stdout
    assert "No such file or directory" in proc.stdout


def test_une_session_ne_lit_pas_la_cle_ssh_d_un_autre_projet(
    image: str, volume: str, tmp_path: Path
) -> None:
    """Mutation qui doit le faire tomber : monter `ssh_home` au lieu du seul
    dossier de la session."""
    maisons = tmp_path / "maisons"
    (maisons / "projet-a-ssh" / "s1").mkdir(parents=True)
    (maisons / "projet-a-ssh" / "s1" / "cle").write_text("cle de projet-a", encoding="utf-8")
    (maisons / "projet-b-ssh" / "s9").mkdir(parents=True)
    (maisons / "projet-b-ssh" / "s9" / "cle").write_text("cle de projet-b", encoding="utf-8")

    proc = _run_session(
        image,
        volume,
        f"type=bind,src={maisons / 'projet-a-ssh' / 's1'},dst=/eldir/ssh,readonly",
        commande="""
        echo "ma cle : $(cat /eldir/ssh/cle)"
        cat /eldir/ssh/../../projet-b-ssh/s9/cle 2>&1
        """,
    )

    assert "ma cle : cle de projet-a" in proc.stdout
    assert "cle de projet-b" not in proc.stdout


def test_une_session_ne_lit_pas_la_maison_claude_d_un_autre_projet(
    image: str, volume: str, tmp_path: Path
) -> None:
    """Les transcripts sont des conversations entières : les partager, c'est
    partager tout ce qui a été dit dans les autres projets.

    Mutation qui doit le faire tomber : monter le volume sans `volume-subpath`.
    """
    maisons = "eldir-test-maisons"
    _docker("volume", "create", maisons)
    try:
        _docker(
            "run",
            "--rm",
            "-v",
            f"{maisons}:/m",
            "--entrypoint",
            "sh",
            image,
            "-c",
            'mkdir -p /m/projet-a/.claude/projects /m/projet-b/.claude/projects '
            '&& echo "conversation de projet-b" > /m/projet-b/.claude/projects/t.jsonl',
        )
        proc = _run_session(
            image,
            volume,
            f"type=volume,src={maisons},dst=/eldir/maison,volume-subpath=projet-a",
            commande="""
            mkdir -p /eldir/maison/.claude/projects
            echo ok > /eldir/maison/.claude/projects/moi.jsonl
            echo "j'ecris chez moi : $(cat /eldir/maison/.claude/projects/moi.jsonl)"
            ls /eldir/maison/../projet-b 2>&1
            """,
        )

        assert "j'ecris chez moi : ok" in proc.stdout
        assert "conversation de projet-b" not in proc.stdout
    finally:
        _docker("volume", "rm", "-f", maisons, attendu=None)
```

- [ ] **Step 6: Lancer les tests d'isolement**

Run: `cd backend && uv run pytest tests/integration/test_isolement_sessions.py -v -m docker`
Expected: PASS, 7 tests

- [ ] **Step 7: Vérifier les mutations à la main**

Pour chacun des trois tests, appliquer la mutation nommée dans son docstring, relancer, constater l'échec, revenir en arrière. Un test d'isolement qui passe aussi sans isolement ne protège rien.

```bash
cd backend
# 1. racine workspaces au lieu du sous-chemin, dans le premier test
# 2. dossier parent `projet-a-ssh` au lieu de `projet-a-ssh/s1`, dans le deuxieme
# 3. montage sans volume-subpath, dans le troisieme
uv run pytest tests/integration/test_isolement_sessions.py -v -m docker
```
Expected: le test muté ÉCHOUE à chaque fois. Annuler la mutation avant de committer (`git diff` doit être propre sur ce fichier).

- [ ] **Step 8: Portes de qualité et commit**

```bash
cd backend && uv run ruff check . && uv run ruff format --check . && uv run mypy app && uv run pytest -q
cd .. && git add -A && git commit -m "feat(sessions): l'enrobage docker, et les trois tests qui tiennent l'isolement

Le voisin n'est pas refuse : il n'existe pas. Une regle qui refuse se negocie
par injection de prompt, un fichier absent de l'univers de la session non.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Task 9: Le branchement dans `SessionManager`

Deux lignes de décision, et un invariant : pas de repli.

**Files:**
- Modify: `backend/app/services/session_manager.py` (`start`, `stop`)
- Test: `backend/tests/unit/test_session_manager.py`

**Interfaces:**
- Consumes: `env_pour_enrobage`, `preparer_la_maison` (tâche 5), `materiel_de_session`, `supprimer_materiel_de_session` (tâche 6), `Settings.session_runtime` (tâche 4).
- Produces: `CHEMIN_ENROBAGE: Path` dans `app/services/session_manager.py`, et `options_kwargs["cli_path"]` posé quand le mode est `conteneur`.

- [ ] **Step 1: Écrire les tests qui échouent**

Ajouter à `backend/tests/unit/test_session_manager.py` :

```python
def test_en_mode_processus_rien_ne_change(monkeypatch: pytest.MonkeyPatch) -> None:
    """L'invariant que la suite entière prouve déjà, nommé une fois.

    La suite tourne en mode `processus`, donc elle prouve ce comportement à
    chaque exécution. Ce test le nomme pour que personne ne l'abîme sans le
    voir : en mode `processus`, aucune option de conteneur n'est posée, et le
    CLI reste celui que le SDK trouve tout seul.
    """
    from app.core.config import get_settings
    from app.services.session_manager import options_de_conteneur

    assert get_settings().session_runtime == "processus"
    assert options_de_conteneur(project_id="p1", session_id="s1", cwd="/tmp/x") == {}


def test_en_mode_conteneur_le_cli_devient_l_enrobage(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.core.config import get_settings
    from app.services.session_manager import CHEMIN_ENROBAGE, options_de_conteneur

    worktree = tmp_path / "workspaces" / "u1" / "depot.s1"
    (tmp_path / "workspaces" / "u1" / "depot").mkdir(parents=True)
    worktree.mkdir()
    monkeypatch.setenv("SESSION_RUNTIME", "conteneur")
    monkeypatch.setenv("WORKSPACES_ROOT", str(tmp_path / "workspaces"))
    monkeypatch.setenv("CLAUDE_HOME_ROOT", str(tmp_path / "maisons"))
    get_settings.cache_clear()
    try:
        options = options_de_conteneur(project_id="p1", session_id="s1", cwd=str(worktree))

        assert options["cli_path"] == str(CHEMIN_ENROBAGE)
        assert options["env"]["ELDIR_WORKTREE_SUBPATH"] == "u1/depot.s1"
        # la maison a été créée : `volume-subpath` l'exige
        assert (tmp_path / "maisons" / "p1" / "tmp").is_dir()
    finally:
        get_settings.cache_clear()


def test_l_enrobage_existe_et_est_executable() -> None:
    """Un `cli_path` qui ne pointe sur rien donne une erreur illisible du SDK."""
    from app.services.session_manager import CHEMIN_ENROBAGE

    assert CHEMIN_ENROBAGE.is_file()
    assert os.access(CHEMIN_ENROBAGE, os.X_OK)


async def test_un_echec_de_demarrage_ne_retombe_pas_en_mode_processus(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Le repli silencieux est exactement ce qu'un attaquant veut provoquer.

    Image inexistante : on attend une erreur, et surtout **pas** une session
    vivante dans le pool.
    """
    from app.core.config import get_settings
    from app.services.event_bus import EventBus
    from app.services.session_manager import SessionManager

    worktree = tmp_path / "workspaces" / "u1" / "depot.s1"
    (tmp_path / "workspaces" / "u1" / "depot").mkdir(parents=True)
    worktree.mkdir()
    monkeypatch.setenv("SESSION_RUNTIME", "conteneur")
    monkeypatch.setenv("SESSION_IMAGE", "eldir-session:image-qui-n-existe-pas")
    monkeypatch.setenv("WORKSPACES_ROOT", str(tmp_path / "workspaces"))
    monkeypatch.setenv("CLAUDE_HOME_ROOT", str(tmp_path / "maisons"))
    get_settings.cache_clear()
    manager = SessionManager(EventBus())
    try:
        with pytest.raises(Exception):
            await manager.start(
                session_id="s1",
                project_id="p1",
                user_id="u1",
                cwd=str(worktree),
            )
        assert manager.active_count == 0
        assert not manager.is_active("s1")
    finally:
        get_settings.cache_clear()
```

Ce dernier test a besoin d'un démon Docker pour échouer au bon endroit : le marquer `@pytest.mark.docker` et ajouter en tête du fichier le saut déjà utilisé en intégration, ou le déplacer dans `tests/integration/test_isolement_sessions.py`. **Le mettre en intégration** : il lance un vrai `docker run`, sa place est là-bas.

- [ ] **Step 2: Lancer les tests pour les voir échouer**

Run: `cd backend && uv run pytest tests/unit/test_session_manager.py -v`
Expected: FAIL avec `ImportError: cannot import name 'options_de_conteneur'`

- [ ] **Step 3: Écrire la décision**

Dans `backend/app/services/session_manager.py`, en tête de fichier :

```python
from app.services import session_container
from app.services.remote_access_service import remote_access_service

# L'enrobage vit sous `backend/` et pas à la racine du dépôt, parce que le
# SDK le lance depuis le processus du backend : il doit donc être DANS l'image
# du backend, dont le contexte de build est `./backend`. Chemin résolu depuis
# ce fichier : `app/services/session_manager.py` -> `backend/` en dev comme
# `/app` dans le conteneur.
CHEMIN_ENROBAGE = (
    Path(__file__).resolve().parents[2] / "docker" / "session" / "claude-dans-un-conteneur"
)
```

Vérifier que `Path` est importé, et que l'import de `remote_access_service` ne crée pas de cycle (il importe `config` et `exceptions`, pas `session_manager`).

Puis, au niveau module, avant `SessionManager` :

```python
def options_de_conteneur(
    *, project_id: str | None, session_id: str, cwd: str
) -> dict[str, Any]:
    """Les options SDK qui mettent le CLI de cette session dans un conteneur.

    Vide en mode `processus` : le CLI tourne alors dans le conteneur du
    backend, comme avant la Phase 6 bis, et le masque d'environnement reste sa
    seule garde.

    En mode `conteneur`, le SDK lance l'enrobage à la place du CLI. Il reçoit
    son environnement, donc les variables calculées ici, et ne transmet au
    conteneur que ce qu'il nomme lui-même.
    """
    if get_settings().session_runtime != "conteneur":
        return {}

    session_container.preparer_la_maison(project_id)
    ssh_subpath = (
        remote_access_service.materiel_de_session(project_id, session_id)
        if project_id
        else None
    )
    return {
        "cli_path": str(CHEMIN_ENROBAGE),
        "env": session_container.env_pour_enrobage(
            project_id=project_id,
            worktree_abs=Path(cwd),
            ssh_subpath=ssh_subpath,
        ),
    }
```

- [ ] **Step 4: Brancher dans `start`**

Dans `SessionManager.start`, après `options_kwargs.update(_optional_options(...))` :

```python
        # Le mode conteneur, s'il est demandé. Les variables de l'enrobage
        # s'ajoutent à l'environnement de la session : l'enrobage les lit pour
        # construire sa ligne de commande et ne les transmet pas au conteneur.
        conteneur = options_de_conteneur(
            project_id=project_id, session_id=session_id, cwd=cwd
        )
        if conteneur:
            options_kwargs["cli_path"] = conteneur["cli_path"]
            options_kwargs["env"] = {**options_kwargs["env"], **conteneur["env"]}
```

- [ ] **Step 5: Nettoyer la matière SSH à l'arrêt**

Dans `SessionManager.stop`, dans le bloc `finally`, avant le `logger.info` :

```python
            if active.project_id:
                # La copie de clé et le `config` à un seul bloc de cette
                # session. Idempotent : un arrêt qui suit un crash ne lève pas.
                remote_access_service.supprimer_materiel_de_session(
                    active.project_id, session_id
                )
```

- [ ] **Step 6: Lancer la suite entière**

Run: `cd backend && uv run pytest -q && uv run pytest tests/integration/test_isolement_sessions.py -q -m docker`
Expected: PASS des deux côtés

- [ ] **Step 7: Portes de qualité et commit**

```bash
cd backend && uv run ruff check . && uv run ruff format --check . && uv run mypy app && uv run pytest -q
cd .. && git add -A && git commit -m "feat(sessions): SessionManager met le CLI dans un conteneur, sans repli possible

Un echec de demarrage en mode conteneur ne retombe pas en mode processus : un
repli silencieux vers le mode non isole est exactement ce qu'un attaquant
cherche a provoquer.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Task 10: Le proxy de socket, le réseau, le compose

Le backend doit pouvoir créer des conteneurs. Lui monter `/var/run/docker.sock` suffirait, et n'affaiblirait pas l'objectif de la phase, mais une faille de l'API Eldir passerait alors de « toutes les données d'Eldir » à « root sur le VPS ». On interpose un proxy qui n'autorise que ce qu'il faut.

**Files:**
- Modify: `docker-compose.yml`, `backend/Dockerfile`, `scripts/install-eldir.sh`
- Test: `backend/tests/unit/test_session_container.py` (deux tests de plus)

**Interfaces:**
- Consumes: les noms de volumes de la tâche 4, l'image de la tâche 7.
- Produces: le service `docker-proxy`, `DOCKER_HOST` dans l'environnement du backend, le volume `eldir_collectes` monté, le réseau `eldir-sessions` créé par l'installateur.

- [ ] **Step 1: Écrire les tests qui échouent**

Ajouter à `backend/tests/unit/test_session_container.py` :

```python
def test_le_proxy_de_socket_n_autorise_que_ce_qu_il_faut() -> None:
    """Le backend crée, démarre et supprime des conteneurs. Rien d'autre.

    `EXEC` donnerait un shell dans n'importe quel conteneur, donc sur le
    backend lui-même ; l'écriture sur `NETWORKS` permettrait de rebrancher une
    session sur le réseau interne où vivent Postgres et Redis. Ce test existe
    parce qu'ajouter une permission au proxy est une ligne, et que la ligne ne
    dit pas ce qu'elle ouvre.
    """
    texte = COMPOSE_PROD.read_text(encoding="utf-8")
    bloc = texte.split("docker-proxy:", 1)[1].split("\n  frontend:", 1)[0]

    for permis in ("CONTAINERS: 1", "POST: 1", "IMAGES: 1", "VOLUMES: 1"):
        assert permis in bloc
    for interdit in ("EXEC", "SWARM", "NETWORKS", "INFO", "AUTH", "SECRETS"):
        assert interdit not in bloc, interdit
    # le socket du démon n'est jamais monté ailleurs que dans le proxy
    assert texte.count("/var/run/docker.sock") == 1
    assert "/var/run/docker.sock:/var/run/docker.sock:ro" in bloc


def test_le_backend_parle_au_proxy_et_pas_au_socket() -> None:
    texte = COMPOSE_PROD.read_text(encoding="utf-8")
    assert "DOCKER_HOST: tcp://docker-proxy:2375" in texte
```

- [ ] **Step 2: Lancer les tests pour les voir échouer**

Run: `cd backend && uv run pytest tests/unit/test_session_container.py -v -k proxy`
Expected: FAIL (`docker-proxy:` absent du compose)

- [ ] **Step 3: Ajouter le proxy et le reste au compose**

Dans `docker-compose.yml`, après le service `redis` et avant `backend` :

```yaml
  # Le backend doit pouvoir créer les conteneurs des sessions. Lui monter le
  # socket du démon suffirait et n'affaiblirait pas l'isolement des sessions
  # (après cette phase, une session n'est plus dans le conteneur du backend,
  # donc elle ne peut pas joindre ce socket). Mais une faille de l'API Eldir
  # passerait alors de « toutes les données d'Eldir » à « root sur la
  # machine », et ce serait une régression introduite par un changement censé
  # durcir. D'où ce proxy : image existante, aucune ligne de code à écrire.
  docker-proxy:
    image: tecnativa/docker-socket-proxy:0.3.0
    container_name: eldir-docker-proxy
    environment:
      # Le backend crée, démarre et supprime des conteneurs, et c'est la
      # totalité de ce qu'il a le droit de demander. Tout le reste reste à 0
      # par défaut, et chaque ajout ici ouvre quelque chose : cf.
      # `test_le_proxy_de_socket_n_autorise_que_ce_qu_il_faut`.
      CONTAINERS: 1
      POST: 1
      IMAGES: 1
      VOLUMES: 1
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock:ro
    restart: unless-stopped
```

Dans le service `backend`, bloc `environment`, après `SESSION_RUNTIME` :

```yaml
      # Le CLI `docker` de l'enrobage lit cette variable tout seul : il ne sait
      # rien du proxy, et n'a pas à le savoir.
      DOCKER_HOST: tcp://docker-proxy:2375
      # Les noms que le démon connaît. Compose préfixe le nom d'un volume par
      # celui du projet (`name: eldir` en tête de ce fichier) : un `docker run`
      # sur `eldir_workspaces` monterait un volume vide tout neuf. Une
      # installation qui renomme le projet compose met ces quatre lignes à jour.
      WORKSPACES_VOLUME: eldir_eldir_workspaces
      TOOLCHAINS_VOLUME: eldir_eldir_toolchains
      CLAUDE_HOME_VOLUME: eldir_eldir_claude_home
      COLLECTES_VOLUME: eldir_eldir_collectes
```

dans son bloc `volumes`, après `eldir_toolchains` :

```yaml
      # Ce qui a été ramené d'un serveur avant le démarrage d'une session
      # (cf. CollectService). Dans un volume et plus dans la couche du
      # conteneur, parce que le démon ne peut monter dans un conteneur de
      # session que ce qu'il voit lui-même : un chemin interne au conteneur du
      # backend n'existe pas pour lui. Conséquence assumée : une collecte
      # survit à un redéploiement, alors qu'elle était jetable avant. Elle est
      # refaite à chaque création de session, donc jamais périmée.
      - eldir_collectes:/var/eldir/collectes
```

et dans son `depends_on` :

```yaml
      docker-proxy:
        condition: service_started
```

- [ ] **Step 4: Ajouter le CLI `docker` à l'image du backend**

Dans `backend/Dockerfile`, dans le `RUN apt-get install` existant, ajouter le dépôt Docker et le paquet `docker-ce-cli` (le client, **pas** le démon) :

```dockerfile
# `docker-ce-cli` sert à l'enrobage des sessions : le backend lance le CLI
# Claude dans un conteneur par session (cf. backend/docker/session/). Le client
# seulement, pas le démon : il parle au proxy de socket par `DOCKER_HOST`.
RUN install -m 0755 -d /etc/apt/keyrings \
 && curl -fsSL https://download.docker.com/linux/debian/gpg \
      -o /etc/apt/keyrings/docker.asc \
 && chmod a+r /etc/apt/keyrings/docker.asc \
 && echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/debian $(. /etc/os-release && echo "$VERSION_CODENAME") stable" \
      > /etc/apt/sources.list.d/docker.list \
 && apt-get update \
 && apt-get install -y --no-install-recommends docker-ce-cli \
 && rm -rf /var/lib/apt/lists/* \
 && docker --version
```

À placer après le bloc qui installe `curl` et `ca-certificates`, et avant l'installation de Node.

- [ ] **Step 5: Faire créer le réseau et l'image par l'installateur**

Compose ne crée **pas** un réseau qu'aucun de ses services n'utilise (mesuré : seul `<projet>_default` apparaît). Le réseau des sessions n'est utilisé par aucun service du compose, par construction : c'est tout son intérêt. Il se crée donc explicitement.

Dans `scripts/install-eldir.sh`, dans la section « 0. prérequis », après la vérification de `docker compose` :

```bash
# ── 0 bis. le réseau et l'image des sessions ─────────────────────
# Un conteneur par session (Phase 6 bis). Le réseau est dédié et n'a pas de
# route vers le réseau interne qui porte Postgres, Redis et le proxy de
# socket : une session ne peut donc pas joindre la base, même si un
# credential lui échappait. Compose ne le crée pas tout seul, puisqu'aucun de
# ses services ne l'utilise.
if ! docker network inspect eldir-sessions >/dev/null 2>&1; then
    docker network create eldir-sessions >/dev/null
    ok "réseau eldir-sessions créé"
else
    ok "réseau eldir-sessions déjà là"
fi

# L'image des sessions. Reconstruite à chaque install : elle épingle la
# version du CLI Claude, qui doit suivre celle du backend.
docker build -q -t eldir-session:local "$(dirname "$0")/../backend/docker/session" >/dev/null
ok "image eldir-session:local construite"
```

- [ ] **Step 6: Lancer les tests et valider le compose**

Run: `cd backend && uv run pytest tests/unit/test_session_container.py -v && cd .. && docker compose config >/dev/null && echo "compose valide"`
Expected: PASS, et `compose valide`

- [ ] **Step 7: Portes de qualité et commit**

```bash
cd backend && uv run ruff check . && uv run ruff format --check . && uv run mypy app && uv run pytest -q
cd .. && git add -A && git commit -m "feat(infra): un proxy de socket, un reseau dedie, et le CLI docker cote backend

Le backend ne tient jamais le socket du demon : une faille de l'API passerait
sinon de 'toutes les donnees d'Eldir' a 'root sur la machine'.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Task 11: La mesure mémoire, le plafond, et la doc

La spec laisse une mesure à faire : « le coût mémoire d'un conteneur par session est à mesurer pendant l'implémentation, et le plafond à revoir **sur cette mesure**, pas sur une estimation ». Cette tâche la fait, puis écrit ce que le lot a changé.

**Files:**
- Modify: `backend/app/core/config.py` (commentaire de `max_concurrent_sessions`), `docs/securite-sessions.md`, `docs/sessions.md`, `docs/deployment.md`, `ROADMAP.md`

- [ ] **Step 1: Mesurer le coût mémoire d'un conteneur de session**

```bash
cd backend
docker build -q -t eldir-session:local ../backend/docker/session
# un conteneur au repos, sans CLI lance : le cout de structure
docker run -d --name eldir-mesure --entrypoint sleep eldir-session:local 600 >/dev/null
sleep 2
docker stats --no-stream --format '{{.Name}} {{.MemUsage}}' eldir-mesure
docker rm -f eldir-mesure >/dev/null
```

Noter le chiffre. Le coût du processus `claude` lui-même (150 à 450 Mo selon la taille de la conversation, cf. le commentaire actuel de `max_concurrent_sessions`) ne change pas : il était déjà payé dans le conteneur du backend. Ce qu'on mesure ici est le **surcoût** de l'enveloppe.

- [ ] **Step 2: Mettre le commentaire du plafond à jour avec le chiffre mesuré**

Dans `backend/app/core/config.py`, compléter le commentaire de `max_concurrent_sessions` avec le surcoût relevé et la date de la mesure. Ne pas changer la valeur si le surcoût est négligeable : le dire explicitement est plus utile qu'un chiffre changé sans raison.

- [ ] **Step 3: Mettre `docs/securite-sessions.md` à jour**

Le risque nº 2 (« pas d'isolement inter-projets ») n'est plus structurel. Réécrire son entrée avec :
- ce qui est fermé : worktrees, toolchains, maisons `.claude`, clés SSH et `config` des autres projets ;
- comment : un conteneur par session, montages par sous-chemin de volume, et le fait qu'un voisin **n'existe pas** au lieu d'être refusé ;
- ce qui reste ouvert, nommément : le sortant complet vers Internet (second lot de la Phase 6 bis), le credential Claude lisible par la session (risque nº 1, inchangé), et le clone canonique du projet accessible en écriture aux sessions de ce projet (même domaine de confiance, et c'était déjà le cas) ;
- le fait que le mode `processus` existe toujours et que, dans ce mode, rien de tout ça n'est fermé.

- [ ] **Step 4: Mettre `docs/sessions.md` à jour**

Ajouter une section « Ce qu'une session voit de son disque », avec la table des montages (son worktree en écriture, le clone de son projet en écriture, son toolchain en lecture seule, sa maison `.claude` en écriture, sa clé et son `config` à un bloc en lecture seule) et ce qui n'est pas monté.

- [ ] **Step 5: Mettre `docs/deployment.md` à jour**

Documenter, dans l'ordre d'une mise en production :
1. Docker 25 minimum sur l'hôte (`--mount volume-subpath`).
2. `docker network create eldir-sessions`, et pourquoi compose ne le fait pas.
3. `docker build -t eldir-session:local backend/docker/session`, à refaire à chaque mise à jour du CLI.
4. Les quatre variables de noms de volumes, à ajuster si le projet compose est renommé, avec `docker volume ls` comme façon de lire les vrais noms.
5. `SESSION_RUNTIME`, ses deux valeurs, et le fait qu'un échec ne retombe jamais en mode `processus`.
6. Le proxy de socket, et ce qu'il n'autorise pas.

- [ ] **Step 6: Mettre `ROADMAP.md` à jour**

Phase 6 bis : cocher les points 1, 2 et 4, laisser le point 3 (réseau sortant restreint) au second lot en le nommant comme tel, et renseigner le point 5 (plafond de sessions) avec la mesure de l'étape 1.

- [ ] **Step 7: Vérifier qu'aucun tiret long n'est entré dans la doc**

La même commande que le job CI `ponctuation`, en PCRE pour nommer les points de code plutôt que de coller les caractères dans un fichier qui se ferait alors signaler lui-même. `git grep` ne lit que les fichiers suivis, donc ni `.venv` ni `node_modules`.

Run: `git grep -I -n -P '[\x{2014}\x{2013}]' -- . ; test $? -eq 1 && echo "aucun tiret long"`
Expected: `aucun tiret long`

- [ ] **Step 8: Portes de qualité, suite complète, et commit**

```bash
cd backend && uv run ruff check . && uv run ruff format --check . && uv run mypy app && uv run pytest -q
uv run pytest tests/integration/test_isolement_sessions.py -q -m docker
cd .. && git add -A && git commit -m "docs(securite): le risque no 2 est ferme, et voila ce qui reste ouvert

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

- [ ] **Step 9: Ouvrir la PR du lot**

Le lot est fini : une seule PR, maintenant.

```bash
gh pr list --head feat/conteneur-par-session --state all
```

Lire le résultat avant de décider. Aucune PR : la créer. PR ouverte sur le même sujet : pousser dedans et mettre son titre et sa description à jour. PR mergée ou fermée : branche morte, repartir de `main` à jour.

---

## Auto-revue du plan

**Couverture de la spec.** Chaque section de `docs/specs/2026-11-03-conteneur-par-session.md` a sa tâche :

| Section de la spec | Tâche |
|---|---|
| Le mécanisme, `session_container.py` | 5 |
| Nouveaux champs de `Settings` | 2, 4 |
| `claude-dans-un-conteneur` | 8 |
| `backend/docker/session/Dockerfile` | 7 |
| Ce que le conteneur monte | 5, 8 (plus le clone canonique, mesuré) |
| L'environnement, le masque qui redevient un filet | 1, 8 |
| Le proxy de socket | 10 |
| La maison `.claude`, une par projet | 2 |
| Migration des transcripts | 3 |
| SSH, sa clé à elle en lecture seule | 6 |
| Le réseau | 8 (le drapeau), 10 (la création) |
| Bascule et repli | 4 (le réglage), 9 (l'absence de repli) |
| Erreurs et cas limites | 5 (sous-chemin absent, projet sans accès distant), 8 (variables manquantes), 9 (échec de démarrage) |
| Tests 1 à 8 | 8 (1, 2, 3, 5), 5 (4), 9 (6, 7), 3 (8) |
| Hors périmètre, plafond à mesurer | 11 |

Les huit tests nommés par la spec ont tous une tâche, et les trois premiers portent la mutation qui doit les faire tomber, vérifiée à la main en tâche 8, étape 7.

**Ce que ce plan ajoute à la spec**, et pourquoi (tout est mesuré, rien n'est déduit) : le montage du clone canonique (sans quoi git ne fonctionne pas du tout), les noms de volumes préfixés par le projet compose, la matière SSH recopiée dans un dossier voisin de la maison plutôt que montée en bind, le `Include` dans la config SSH de l'image, les montages conditionnels du toolchain et de la collecte avec le volume que la collecte n'avait pas, la création explicite du réseau, le sous-chemin de maison du superviseur, et la fusion du masque d'environnement qui était écrasée sur `main`.

**Ce que ce plan ne fait pas**, et qui est bien hors périmètre : le réseau sortant restreint (second lot, sa propre spec), le credential Claude lisible par la session (risque nº 1, inchangé), Podman et le mode rootless, le multi-processus du backend.
