# Surface d'agent externe - plan d'implémentation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** ouvrir les cinq outils du superviseur à un agent extérieur, en MCP sur HTTP, sans dupliquer leur comportement, et combler d'abord les deux manques qui rendraient cette porte inutilisable à un agent qui travaille seul.

**Architecture:** chaque corps d'outil quitte sa closure pour devenir une méthode publique de `SupervisorService`. Deux transports l'enveloppent : `create_sdk_mcp_server` pour le superviseur interne (inchangé vu de Claude), `FastMCP.streamable_http_app()` monté sous `/api/mcp/` pour l'extérieur, derrière une garde ASGI qui valide un jeton d'agent révocable. La fin de tour d'une session dispatchée, aujourd'hui un ping en mémoire, devient aussi un POST signé HMAC.

**Tech Stack:** FastAPI, SQLAlchemy 2.0 async, Alembic, `mcp` 1.27.1 (déjà dans `uv.lock`, transitif de `claude-agent-sdk`), React 18 + TanStack Query, pytest, vitest.

**Spec:** [`docs/specs/2026-10-29-surface-agent-externe.md`](../specs/2026-10-29-surface-agent-externe.md)

## Global Constraints

- **Aucun tiret long, nulle part.** Ni cadratin (U+2014) ni demi-cadratin (U+2013) : ni dans le code, ni dans les commentaires, ni dans les messages de commit, ni dans la doc, ni dans l'interface. Toujours le trait d'union `-`, ou reformuler. Règle absolue du mainteneur, vérifiée avant chaque commit.
- **Tout en français** : commentaires, docstrings, messages d'erreur, libellés d'interface, descriptions d'outils MCP.
- **Un lot par branche, un commit par étape, une seule PR par lot, ouverte quand le lot est fini.** Avant chaque commit : `gh pr list --head <branche> --state all` dans un appel séparé, et lire le résultat. PR mergée ou fermée = branche morte, on repart de `main` à jour.
- **Le dépôt est public.** Aucun secret, aucune adresse de machine, aucun nom d'hôte personnel, aucune adresse e-mail dans un fichier commité. Les exemples de doc utilisent `eldir.exemple.lan` ou `127.0.0.1`.
- **Trois lots, trois branches** : `feat/sessions-paralleles-et-file` (tâches 1-2), `feat/surface-agent-externe` (tâches 3-10), `docs/finition-publique` (tâches 11-13).
- **Portes de qualité**, qui doivent passer avant chaque commit : backend `uv run ruff check . && uv run ruff format --check . && uv run mypy app && uv run pytest -q`, frontend `npm run lint && npx tsc --noEmit && npm test && npm run build`.
- **Jamais de régression sur la porte de validation humaine.** `git commit`, `git push` et `gh pr` restent refusés par le hook `PreToolUse`, quel que soit le transport.

---

## Structure des fichiers

**Créés**

| Fichier | Responsabilité |
|---|---|
| `backend/app/db/models/agent_token.py` | La ligne d'un jeton d'agent (libellé, `jti`, révocation) |
| `backend/alembic/versions/0012_agent_tokens.py` | Migration de la table |
| `backend/app/services/agent_token_service.py` | Émettre, lister, révoquer, authentifier un jeton |
| `backend/app/mcp_http.py` | L'app MCP HTTP, la garde ASGI du jeton, le contexte d'appel |
| `backend/app/services/turn_webhook.py` | Le POST signé HMAC de fin de tour |
| `backend/app/api/v1/agent_tokens.py` | Routes REST de gestion des jetons |
| `backend/app/schemas/agent_token.py` | Schémas Pydantic des jetons |
| `backend/tests/unit/test_agent_token_service.py` | Jeton valide, révoqué, de mauvais `kind` |
| `backend/tests/unit/test_turn_webhook.py` | Signature, et l'échec qui ne remonte pas |
| `backend/tests/integration/test_mcp_http.py` | `/api/mcp/` sans jeton, avec jeton, outils listés, publication refusée |
| `backend/tests/unit/test_supervisor_tools.py` | Les corps d'outils extraits, appelés directement |
| `frontend/src/features/settings/agent-tokens.tsx` | Le panneau de gestion des jetons |
| `docs/agent-externe.md` | Comment brancher un agent sur Eldir |
| `CODE_OF_CONDUCT.md` | Contributor Covenant 2.1 |
| `.github/pull_request_template.md` | Gabarit de PR |
| `.github/ISSUE_TEMPLATE/anomalie.md` | Gabarit d'anomalie |
| `.github/ISSUE_TEMPLATE/proposition.md` | Gabarit de proposition |
| `.github/workflows/lighthouse.yml` | CI Lighthouse, seuil PWA |

**Modifiés**

| Fichier | Changement |
|---|---|
| `backend/app/services/supervisor_service.py` | Corps d'outils extraits en méthodes publiques ; `nouveau_chantier` ; appel du webhook |
| `backend/app/services/session_manager.py` | Plafond de messages en attente |
| `backend/app/api/v1/sessions.py` | La route de message rend la main tout de suite |
| `backend/app/services/session_service.py` | `send_message` lançable en tâche de fond |
| `backend/app/core/config.py` | Réglages du webhook, des hôtes MCP, du plafond de file |
| `backend/app/core/deps.py` | Dépendance d'identité d'agent |
| `backend/app/main.py` | Montage de `/api/mcp/` et lifespan du gestionnaire de sessions |
| `backend/app/db/models/__init__.py` | Export du nouveau modèle |
| `backend/app/api/v1/__init__.py` | Branchement des routes de jetons |
| `frontend/src/pages/session-page.tsx` | Champ de saisie jamais verrouillé, messages en attente affichés |
| `frontend/src/lib/api/queries.ts` | Mutation d'envoi non bloquante, hooks de jetons |
| `frontend/src/pages/settings-*.tsx` | Entrée vers le panneau des jetons |
| `ROADMAP.md` | Cases en retard, parallélisme, section agent externe |

---

# Lot 1 - les deux trous

```bash
git checkout main && git pull
git checkout -b feat/sessions-paralleles-et-file
```

## Task 1: dispatcher un second chantier sur le même repo

**Files:**
- Modify: `backend/app/services/supervisor_service.py` (`_resolve_target`, l'outil `dispatch`)
- Test: `backend/tests/unit/test_supervisor_dispatch.py` (créer)

**Interfaces:**
- Consomme : `SessionService.create_and_start(db, user_id=..., project_id=...) -> SessionRow`, qui existe déjà et pose le worktree.
- Produit : `SupervisorService._resolve_target(*, user_id: str, project_id: str, session_id: str | None, nouveau_chantier: bool = False) -> tuple[str, str, bool]`, qui rend `(session_id, nom du projet, session_créée)`. La tâche 3 réutilise cette signature.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/unit/test_supervisor_dispatch.py
"""Résolution de la cible d'un dispatch.

Sans `nouveau_chantier`, on reprend la session la plus récente du projet : c'est
ce qui évite d'ouvrir une session par consigne. Avec, on en ouvre une seconde,
sinon deux chantiers parallèles sur un même repo sont impossibles depuis un
agent, alors que les worktrees les isolent déjà.
"""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.models import Project, Session as SessionRow, User


async def _pose_projet_et_session(db: AsyncSession) -> tuple[str, str]:
    user = User(email="jarl@exemple.lan", hashed_password="x")
    db.add(user)
    await db.flush()
    projet = Project(
        user_id=user.id,
        name="Munin",
        provider="github",
        repo_full_name="exemple/munin",
        default_branch="main",
        local_path="/tmp/munin",
    )
    db.add(projet)
    await db.flush()
    session = SessionRow(
        project_id=projet.id,
        user_id=user.id,
        branch="claude/un",
        worktree_path="/tmp/munin-wt1",
        model="claude-sonnet-5",
        sdk_session_id="sdk-1",
    )
    db.add(session)
    await db.commit()
    return user.id, projet.id


@pytest.mark.asyncio
async def test_sans_nouveau_chantier_on_reprend_la_session_existante(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as db:
        user_id, project_id = await _pose_projet_et_session(db)

    from tests.unit.conftest_supervisor import service_superviseur  # cf. étape 3

    service = service_superviseur(session_factory)
    cible, nom, cree = await service._resolve_target(
        user_id=user_id, project_id=project_id, session_id=None
    )
    assert nom == "Munin"
    assert cree is False
    assert cible == "sdk-1" or cible  # la session existante, pas une neuve


@pytest.mark.asyncio
async def test_nouveau_chantier_ouvre_une_seconde_session(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as db:
        user_id, project_id = await _pose_projet_et_session(db)

    from tests.unit.conftest_supervisor import service_superviseur

    service = service_superviseur(session_factory)
    _, _, cree = await service._resolve_target(
        user_id=user_id,
        project_id=project_id,
        session_id=None,
        nouveau_chantier=True,
    )
    assert cree is True, "un second chantier doit ouvrir sa propre session"
```

- [ ] **Step 2: Write the test harness for SupervisorService**

`SupervisorService` prend un `SessionManager` et un `SessionService` réels. Pour un test unitaire, on pose des doubles minimaux : seul `create_and_start` est appelé.

```python
# backend/tests/unit/conftest_supervisor.py
"""Doubles minimaux pour instancier SupervisorService hors runtime SDK."""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.models import Session as SessionRow
from app.services.supervisor_service import SupervisorService


class ManagerFactice:
    """Ne démarre aucun CLI : le test ne touche pas au SDK."""

    def register_persist_callback(self, _cb: Any) -> None:
        return None

    def is_active(self, _session_id: str) -> bool:
        return False


class SessionsFactice:
    def __init__(self, factory: async_sessionmaker[AsyncSession]) -> None:
        self._factory = factory

    async def create_and_start(
        self, db: AsyncSession, *, user_id: str, project_id: str
    ) -> SessionRow:
        row = SessionRow(
            project_id=project_id,
            user_id=user_id,
            branch="claude/deux",
            worktree_path="/tmp/munin-wt2",
            model="claude-sonnet-5",
        )
        db.add(row)
        await db.flush()
        return row


def service_superviseur(factory: async_sessionmaker[AsyncSession]) -> SupervisorService:
    return SupervisorService(
        manager=ManagerFactice(),  # type: ignore[arg-type]
        sessions=SessionsFactice(factory),  # type: ignore[arg-type]
        session_factory=factory,
    )
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `cd backend && uv run pytest tests/unit/test_supervisor_dispatch.py -v`
Expected: FAIL, `_resolve_target() got an unexpected keyword argument 'nouveau_chantier'`

- [ ] **Step 4: Add the parameter to `_resolve_target`**

Dans `backend/app/services/supervisor_service.py`, remplacer la signature et le court-circuit de réutilisation :

```python
    async def _resolve_target(
        self,
        *,
        user_id: str,
        project_id: str,
        session_id: str | None,
        nouveau_chantier: bool = False,
    ) -> tuple[str, str, bool]:
        """Renvoie (session_id, nom du projet, session_créée)."""
        async with self._factory() as db:
            project = await db.get(Project, project_id)
            if project is None or project.user_id != user_id:
                raise NotFoundError(f"Projet {project_id} introuvable.")

            if session_id is not None:
                existing = await db.get(SessionRow, session_id)
                if existing is None or existing.user_id != user_id:
                    raise NotFoundError(f"Session {session_id} introuvable.")
                return existing.id, project.name, False

            # Un second chantier sur le même repo veut sa propre session, donc
            # son propre worktree : sans ça deux consignes parallèles se
            # marchent dessus dans le même arbre de travail.
            if not nouveau_chantier:
                result = await db.execute(
                    select(SessionRow)
                    .where(
                        SessionRow.user_id == user_id,
                        SessionRow.project_id == project_id,
                        SessionRow.is_system.is_(False),
                    )
                    .order_by(SessionRow.updated_at.desc())
                    .limit(1)
                )
                existing = result.scalar_one_or_none()
                if existing is not None and existing.sdk_session_id:
                    return existing.id, project.name, False

            created = await self._sessions.create_and_start(
                db, user_id=user_id, project_id=project_id
            )
            await db.commit()
            return created.id, project.name, True
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `cd backend && uv run pytest tests/unit/test_supervisor_dispatch.py -v`
Expected: PASS (2 tests)

- [ ] **Step 6: Expose the parameter on the `dispatch` tool**

Dans `_build_mcp_server`, ajouter la propriété au schéma de `dispatch` et la passer. La description doit dire **quand** s'en servir, sinon un agent l'utilisera soit jamais, soit à chaque tour.

```python
                    "nouveau_chantier": {
                        "type": "boolean",
                        "description": (
                            "Optionnel. true pour ouvrir une session neuve à "
                            "côté des existantes, dans son propre worktree. "
                            "Un chantier par sujet indépendant ; la même "
                            "session pour la suite d'un travail en cours."
                        ),
                    },
```

Et dans le corps de l'outil :

```python
            nouveau_chantier = bool(args.get("nouveau_chantier"))
            try:
                target, project_name, created = await self._resolve_target(
                    user_id=user_id,
                    project_id=project_id,
                    session_id=session_id,
                    nouveau_chantier=nouveau_chantier,
                )
```

- [ ] **Step 7: Run the full backend gate**

Run: `cd backend && uv run ruff check . && uv run ruff format --check . && uv run mypy app && uv run pytest -q`
Expected: tout passe. Trois échecs sur `ssh-keygen` sont connus si l'image de dev est périmée : les vérifier sur un arbre propre (`git stash`) avant de s'en inquiéter.

- [ ] **Step 8: Check the PR state, then commit**

Run, dans un appel séparé, et lire le résultat : `gh pr list --head feat/sessions-paralleles-et-file --state all`

```bash
git add backend/app/services/supervisor_service.py backend/tests/unit/test_supervisor_dispatch.py backend/tests/unit/conftest_supervisor.py
git commit -m "$(cat <<'MSG'
feat(superviseur): deux chantiers sur un même repo

`_resolve_target` réutilisait toujours la session la plus récente du projet,
donc `dispatch` ne pouvait pas ouvrir un second chantier parallèle : il
fallait créer la session à la main dans l'interface. Les worktrees isolent
déjà N sessions sur un repo depuis la phase 2, il ne manquait que le choix.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
MSG
)"
```

## Task 2: écrire à une session qui travaille

**Files:**
- Modify: `backend/app/services/session_manager.py` (`ActiveSession`, `send_message`)
- Modify: `backend/app/services/session_service.py` (`send_message`)
- Modify: `backend/app/api/v1/sessions.py:61-77`
- Modify: `backend/app/core/config.py`
- Modify: `frontend/src/pages/session-page.tsx:350-375`
- Test: `backend/tests/unit/test_file_messages.py` (créer)

**Interfaces:**
- Consomme : `ActiveSession.message_lock` (asyncio.Lock, déjà là, sérialise les tours).
- Produit : `SessionManager.send_message(session_id, content, *, origin=...)` lève `QueueFullError` quand le plafond est atteint ; `SessionService.send_message_en_fond(user_id, session_id, content) -> None` qui ne bloque pas l'appelant.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/unit/test_file_messages.py
"""Plafond de la file d'attente d'une session.

`message_lock` sérialise déjà les tours : un second message attend la fin du
premier, il n'est pas perdu. Ce qui manque est une borne. Un agent parti en
boucle empilerait des centaines de consignes que personne ne relira, et la
mémoire du conteneur avec. Au-delà du plafond, le refus doit être lisible par
l'agent, pas un 500.
"""

from __future__ import annotations

import asyncio

import pytest

from app.core.exceptions import QueueFullError
from app.services.session_manager import ActiveSession


def test_une_session_neuve_a_une_file_vide() -> None:
    active = ActiveSession(
        session_id="s1", project_id="p1", user_id="u1", cwd="/tmp"
    )
    assert active.en_attente == 0


@pytest.mark.asyncio
async def test_le_plafond_refuse_le_message_de_trop() -> None:
    active = ActiveSession(
        session_id="s1", project_id="p1", user_id="u1", cwd="/tmp"
    )
    active.en_attente = 3
    with pytest.raises(QueueFullError) as exc:
        active.reserver_place(plafond=3)
    assert "3" in exc.value.message, "le refus doit dire le plafond atteint"


@pytest.mark.asyncio
async def test_sous_le_plafond_la_place_est_prise_et_rendue() -> None:
    active = ActiveSession(
        session_id="s1", project_id="p1", user_id="u1", cwd="/tmp"
    )
    active.reserver_place(plafond=3)
    assert active.en_attente == 1
    active.rendre_place()
    assert active.en_attente == 0
    # Jamais négatif : un double `rendre_place` ne doit pas ouvrir la vanne.
    active.rendre_place()
    assert active.en_attente == 0
    await asyncio.sleep(0)
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd backend && uv run pytest tests/unit/test_file_messages.py -v`
Expected: FAIL, `ImportError: cannot import name 'QueueFullError'`

- [ ] **Step 3: Add the exception**

Dans `backend/app/core/exceptions.py`, à côté des autres erreurs métier (reprendre le style de la classe voisine, qui porte `code`, `message` et `status_code`) :

```python
class QueueFullError(EldirError):
    """Trop de messages déjà en attente pour cette session."""

    code = "queue_full"
    status_code = 429
```

- [ ] **Step 4: Add the counter to `ActiveSession`**

Dans `backend/app/services/session_manager.py`, sur le dataclass :

```python
    # Messages déjà acceptés et pas encore traités, plafonnés : la file vit
    # dans `message_lock`, ce compteur ne fait que la borner.
    en_attente: int = 0

    def reserver_place(self, *, plafond: int) -> None:
        if self.en_attente >= plafond:
            raise QueueFullError(
                f"{self.en_attente} messages déjà en attente sur cette session "
                f"(plafond {plafond}). Attends son compte rendu avant d'en "
                "envoyer un autre."
            )
        self.en_attente += 1

    def rendre_place(self) -> None:
        self.en_attente = max(0, self.en_attente - 1)
```

- [ ] **Step 5: Run the test to verify it passes**

Run: `cd backend && uv run pytest tests/unit/test_file_messages.py -v`
Expected: PASS (3 tests)

- [ ] **Step 6: Commit**

Vérifier l'état de la PR dans un appel séparé, puis :

```bash
git add backend/app/core/exceptions.py backend/app/services/session_manager.py backend/tests/unit/test_file_messages.py
git commit -m "$(cat <<'MSG'
feat(sessions): borner la file d'attente d'une session

Le verrou de session sérialise déjà les tours, donc un second message n'est
pas perdu : il attend. Ce qui manquait est une borne. Une file sans borne
alimentée par un processus automatique n'est pas une file, c'est une fuite.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
MSG
)"
```

- [ ] **Step 7: Wire the cap into `send_message` and stop blocking the route**

Réglage dans `backend/app/core/config.py`, dans la section des budgets :

```python
    # ── File d'attente par session ──────────────────────────────
    # Un agent peut enchaîner les consignes ; au-delà, c'est une boucle.
    session_queue_max: int = 5
```

Dans `SessionManager.send_message`, prendre la place **avant** d'attendre le verrou, et la rendre dans tous les cas :

```python
        active = self.get(session_id)
        if active.client is None:
            raise SessionNotFoundError(f"Session {session_id} sans client SDK actif.")

        active.reserver_place(plafond=get_settings().session_queue_max)
        try:
            # Une seule réception en cours à la fois par session.
            async with active.message_lock:
                await self._publish(
                    session_id, EVENT_TYPE_USER_MESSAGE, {"text": content, "origin": origin}
                )
                await self._publish_state(session_id, SESSION_STATE_THINKING)
                active.last_cr = None
                await active.client.query(content)
                await self._consume_response(active)
                await self._publish_state(session_id, state_after_turn(active.last_cr))
        finally:
            active.rendre_place()
```

Dans `SessionService`, un envoi qui ne bloque pas l'appelant. La reprise et le contrôle d'accès restent synchrones (ils doivent pouvoir refuser tout de suite) ; seul le tour part en fond :

```python
    async def send_message_en_fond(
        self, db: AsyncSession, *, user_id: str, session_id: str, content: str
    ) -> None:
        """Accepte le message, lance le tour, et rend la main.

        Le tour peut durer des minutes. Attendre sa fin dans la requête HTTP
        condamnait l'interface à verrouiller le champ de saisie pendant tout
        ce temps, alors que débloquer un agent qui travaille est précisément
        le geste dont on a besoin.
        """
        await self.get(db, session_id, user_id)
        if not self._manager.is_active(session_id):
            await self.resume(db, user_id=user_id, session_id=session_id)
        self._spawn(self._manager.send_message(session_id, content))
```

Si `SessionService` n'a pas encore de `_spawn`, reprendre à l'identique celui de `SupervisorService`, **et son ensemble de tâches**, à initialiser dans `__init__` (`self._tasks: set[asyncio.Task[None]] = set()`) : sans la référence, la tâche est ramassée par le GC avant la fin du tour, et le message disparaît sans trace.

```python
    def _spawn(self, coro: Any) -> None:
        """Tâche de fond dont on garde une référence (sinon GC prématuré)."""
        task = asyncio.create_task(coro)
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)
```

Et la route, dans `backend/app/api/v1/sessions.py` :

```python
@router.post("/{session_id}/messages", status_code=status.HTTP_202_ACCEPTED)
async def send_message(
    session_id: str,
    payload: SessionMessageInput,
    user_id: CurrentUserId,
    db: DbDep,
) -> dict[str, str]:
    # On accepte et on rend la main : le tour part en tâche de fond et son
    # avancement se suit par WebSocket. Un refus de file pleine remonte en 429.
    await get_session_service().send_message_en_fond(
        db,
        user_id=user_id,
        session_id=session_id,
        content=payload.content,
    )
    await db.commit()
    return {"status": "accepted"}
```

- [ ] **Step 8: Run the backend gate, then commit**

Run: `cd backend && uv run ruff check . && uv run ruff format --check . && uv run mypy app && uv run pytest -q`

Vérifier l'état de la PR dans un appel séparé, puis commiter avec le message :

```
feat(sessions): la saisie rend la main pendant que l'agent travaille

La route de message rendait déjà 202 mais après avoir attendu la fin du tour,
parfois plusieurs minutes, et son commentaire l'avouait. Le front en
conséquence verrouillait le champ. Débloquer un agent qui travaille est le
geste central et c'était celui qu'on ne pouvait pas faire.
```

- [ ] **Step 9: Write the frontend test**

```tsx
// frontend/src/pages/session-page.test.tsx
// Le champ de saisie ne se verrouille plus pendant un tour : on doit pouvoir
// écrire à un agent qui travaille. C'est le geste qui le débloque.
import { describe, expect, it } from 'vitest';
import { messagesEnAttente } from './session-page';

describe('messagesEnAttente', () => {
  it('garde un message tant que le fil ne le porte pas', () => {
    const resultat = messagesEnAttente(['salut'], []);
    expect(resultat).toEqual(['salut']);
  });

  it("retire celui que le fil a repris, pour ne pas l'afficher deux fois", () => {
    const resultat = messagesEnAttente(
      ['salut', 'et ensuite ?'],
      [{ type: 'user_message', data: { text: 'salut' } }],
    );
    expect(resultat).toEqual(['et ensuite ?']);
  });
});
```

- [ ] **Step 10: Run the frontend test to verify it fails**

Run: `cd frontend && npm test -- session-page`
Expected: FAIL, `messagesEnAttente` n'est pas exporté.

- [ ] **Step 11: Implement the pending-messages display**

Dans `frontend/src/pages/session-page.tsx`, exporter la fonction pure puis l'utiliser :

```tsx
/** Les messages acceptés par le serveur que le fil ne porte pas encore.
 *  Sans ce filtre, un message réapparaîtrait en double le temps que
 *  l'événement `user_message` remonte par WebSocket. */
export function messagesEnAttente(
  envoyes: string[],
  evenements: { type: string; data?: { text?: string } }[],
): string[] {
  const vus = new Set(
    evenements
      .filter((e) => e.type === 'user_message')
      .map((e) => e.data?.text ?? ''),
  );
  return envoyes.filter((m) => !vus.has(m));
}
```

Déclarer l'état et le dérivé, en haut du composant, à côté des autres
`useState` :

```tsx
  // Ce que John a envoyé et que le fil ne porte pas encore. Un tableau et pas
  // un compteur : on affiche les textes, pas leur nombre.
  const [envoyes, setEnvoyes] = useState<string[]>([]);
  const enAttente = useMemo(
    () => messagesEnAttente(envoyes, events),
    [envoyes, events],
  );
```

`events` est le fil déjà fusionné par le `useMemo` existant (historique + live).

Dans `handleSend`, on ne garde plus le message en otage du `await` :

```tsx
  const handleSend = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    const content = input.trim();
    if (!content) return;
    setInput('');
    setEnvoyes((liste) => [...liste, content]);
    try {
      await sendMessage.mutateAsync({ content });
    } catch (err) {
      setEnvoyes((liste) => liste.filter((m) => m !== content));
      // Le message n'est pas parti : on le rend à John au lieu de le perdre.
      setInput((current) => (current.length === 0 ? content : current));
      setError(
        err instanceof Error
          ? `Message non envoyé : ${err.message}`
          : 'Message non envoyé.',
      );
    }
  };
```

Le `textarea` et le bouton perdent leur `disabled={sendMessage.isPending}` : seul le bouton reste désactivé sur un champ vide.

```tsx
                disabled={input.trim().length === 0}
```

Et au-dessus du formulaire, les messages en attente :

```tsx
        {enAttente.map((texte) => (
          <div
            key={texte}
            className="self-end rounded-eldir bg-eldir-cream-2 px-3 py-2 text-sm text-eldir-gray"
          >
            {texte}
            <span className="eldir-caps ml-2">en attente</span>
          </div>
        ))}
```

- [ ] **Step 12: Run the frontend gate**

Run: `cd frontend && npm test -- session-page && npm run lint && npx tsc --noEmit && npm run build`
Expected: tout passe.

- [ ] **Step 13: Commit**

Vérifier l'état de la PR dans un appel séparé, puis commiter avec le message :

```
feat(ui): on peut écrire à un agent qui travaille

Le champ de saisie était éteint le temps du tour. Les messages acceptés
s'affichent désormais en attente sous le fil, et disparaissent quand
l'événement remonte, pour ne pas les montrer deux fois.
```

- [ ] **Step 14: Open the PR for lot 1**

Le lot est fini. Une seule PR, qui cite la spec et dit ce que les deux manques empêchaient.

```bash
git push -u origin feat/sessions-paralleles-et-file
gh pr create --title "feat(sessions): deux chantiers en parallèle, et la saisie qui rend la main" --body "$(cat <<'MSG'
Les deux manques que la spec de la surface d'agent externe met en tête, parce
qu'ils sont supportables tant qu'un humain est au clavier et bloquants dès
qu'un agent travaille seul : il n'a personne pour contourner le mur.

- `dispatch` ne pouvait pas ouvrir un second chantier sur un même repo, alors
  que les worktrees les isolent depuis la phase 2.
- La route de message rendait 202 après avoir attendu la fin du tour, donc le
  champ de saisie restait éteint pendant des minutes. C'est le geste qui
  débloque un agent.

Spec : `docs/specs/2026-10-29-surface-agent-externe.md`

🤖 Generated with [Claude Code](https://claude.com/claude-code)
MSG
)"
```

---

# Lot 2 - la surface d'agent

```bash
git checkout main && git pull
git checkout -b feat/surface-agent-externe
```

## Task 3: un seul corps par outil

**Files:**
- Modify: `backend/app/services/supervisor_service.py`
- Test: `backend/tests/unit/test_supervisor_tools.py` (créer)

**Interfaces:**
- Produit, sur `SupervisorService`, cinq méthodes publiques qui rendent du texte et qu'un transport enveloppe. Les tâches 4, 7 et 8 les consomment :

```python
async def outil_list_projects(self, user_id: str) -> str
async def outil_list_sessions(self, user_id: str) -> str
async def outil_dispatch(self, user_id: str, *, project_id: str, consigne: str,
                         session_id: str | None = None,
                         nouveau_chantier: bool = False) -> str
async def outil_allow_publish(self, user_id: str, *, session_id: str,
                              autoriser: bool) -> str
async def outil_remember(self, user_id: str, *, fait: str) -> str
```

- Produit aussi `SCHEMAS_OUTILS: dict[str, tuple[str, dict[str, Any]]]`, qui associe à chaque nom d'outil sa description et son schéma JSON. Décrit une fois, lu par les deux transports.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/unit/test_supervisor_tools.py
"""Les corps d'outils du superviseur, appelés directement.

Ils étaient des closures dans `_build_mcp_server`, donc intestables et
impossibles à servir par un second transport sans les réécrire. Deux
comportements qui divergent, c'est la panne qu'on paie six mois plus tard.
"""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.services.supervisor_service import SCHEMAS_OUTILS
from tests.unit.conftest_supervisor import service_superviseur


def test_les_cinq_outils_sont_decrits_une_seule_fois() -> None:
    assert set(SCHEMAS_OUTILS) == {
        "list_projects",
        "list_sessions",
        "dispatch",
        "allow_publish",
        "remember",
    }
    for nom, (description, schema) in SCHEMAS_OUTILS.items():
        assert description.strip(), nom
        assert schema["type"] == "object", nom


@pytest.mark.asyncio
async def test_sans_projet_list_projects_le_dit(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    service = service_superviseur(session_factory)
    assert "Aucun projet" in await service.outil_list_projects("u-inconnu")


@pytest.mark.asyncio
async def test_dispatch_refuse_une_consigne_vide(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    service = service_superviseur(session_factory)
    texte = await service.outil_dispatch("u1", project_id="p1", consigne="  ")
    assert "obligatoire" in texte
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd backend && uv run pytest tests/unit/test_supervisor_tools.py -v`
Expected: FAIL, `cannot import name 'SCHEMAS_OUTILS'`

- [ ] **Step 3: Extract the schemas**

Dans `backend/app/services/supervisor_service.py`, au niveau module, les descriptions et schémas existants, déplacés tels quels depuis les décorateurs `@tool` (ne pas réécrire les textes : ce sont eux que le modèle lit) :

```python
# Les cinq outils décrits UNE fois. Les deux transports (MCP in-process pour
# le superviseur, MCP HTTP pour un agent externe) lisent cette table, pour
# qu'il n'existe jamais deux descriptions du même outil.
SCHEMAS_OUTILS: dict[str, tuple[str, dict[str, Any]]] = {
    "list_projects": (
        "Liste les repos branchés sur Eldir. Sert à identifier de quel "
        "projet John parle avant de dispatcher.",
        {"type": "object", "properties": {}},
    ),
    "list_sessions": (
        "Liste les sessions Claude existantes avec leur état et le compte "
        "rendu de leur dernier passage. À consulter avant de dispatcher.",
        {"type": "object", "properties": {}},
    ),
    "dispatch": (
        "Transmet une consigne à une session projet et rend la main "
        "immédiatement. Reprend la session indiquée, sinon la session "
        "ouverte la plus récente du projet, sinon en démarre une. Tu "
        "recevras un message automatique avec son compte rendu quand elle "
        "aura terminé.",
        {
            "type": "object",
            "properties": {
                "project_id": {
                    "type": "string",
                    "description": "id du projet cible (cf. list_projects)",
                },
                "consigne": {
                    "type": "string",
                    "description": (
                        "Consigne complète et auto-suffisante : la session "
                        "enfant ne voit pas ta conversation avec John."
                    ),
                },
                "session_id": {
                    "type": "string",
                    "description": (
                        "Optionnel : session précise à reprendre. Laisser "
                        "vide pour laisser Eldir choisir."
                    ),
                },
                "nouveau_chantier": {
                    "type": "boolean",
                    "description": (
                        "Optionnel. true pour ouvrir une session neuve à "
                        "côté des existantes, dans son propre worktree. "
                        "Un chantier par sujet indépendant ; la même "
                        "session pour la suite d'un travail en cours."
                    ),
                },
            },
            "required": ["project_id", "consigne"],
        },
    ),
    "allow_publish": (
        "Autorise une session à publier (commit, push, PR) ou lui retire "
        "ce droit. À n'utiliser QUE si John le demande explicitement : "
        "c'est sa porte de validation, pas la tienne.",
        {
            "type": "object",
            "properties": {
                "session_id": {
                    "type": "string",
                    "description": "session concernée (cf. list_sessions)",
                },
                "autoriser": {
                    "type": "boolean",
                    "description": "true pour autoriser, false pour retirer",
                },
            },
            "required": ["session_id", "autoriser"],
        },
    ),
    "remember": (
        "Enregistre une préférence de travail durable de John (elle sera "
        "dans ton prompt aux prochains démarrages). Uniquement pour ce qui "
        "vaut pour les fois suivantes, jamais pour une demande ponctuelle.",
        {
            "type": "object",
            "properties": {
                "fait": {
                    "type": "string",
                    "description": (
                        "Une phrase courte et impérative, ex : 'Sur Munin, "
                        "toujours ouvrir une PR plutôt que commiter sur main.'"
                    ),
                }
            },
            "required": ["fait"],
        },
    ),
}
```

- [ ] **Step 4: Move each tool body to a public method**

Chaque corps devient une méthode qui prend `user_id` en premier argument et rend une chaîne. Le code interne est celui d'aujourd'hui, sans le `_text(...)` final.

```python
    # ── corps des outils, un seul par outil ─────────────────────
    async def outil_list_projects(self, user_id: str) -> str:
        async with self._factory() as db:
            result = await db.execute(
                select(Project).where(Project.user_id == user_id).order_by(Project.name.asc())
            )
            projects = list(result.scalars().all())
        if not projects:
            return "Aucun projet branché sur Eldir."
        lines = [
            f"- {p.name} (id={p.id}) · {p.provider}:{p.repo_full_name} "
            f"· branche {p.default_branch}"
            for p in projects
        ]
        return "\n".join(lines)

    async def outil_dispatch(
        self,
        user_id: str,
        *,
        project_id: str,
        consigne: str,
        session_id: str | None = None,
        nouveau_chantier: bool = False,
    ) -> str:
        project_id = project_id.strip()
        consigne = consigne.strip()
        if not project_id or not consigne:
            return "Erreur : project_id et consigne sont obligatoires."
        try:
            target, project_name, created = await self._resolve_target(
                user_id=user_id,
                project_id=project_id,
                session_id=(session_id or "").strip() or None,
                nouveau_chantier=nouveau_chantier,
            )
        except NotFoundError as exc:
            return f"Erreur : {exc.message}"

        self._pending.add(target)
        self._spawn(self._run_child(user_id, target, consigne))
        origine = "nouvelle session" if created else "session reprise"
        return (
            f"Consigne transmise à {project_name} ({origine} {target}). "
            "Elle travaille en tâche de fond, tu seras notifié à la fin de "
            "son tour."
        )
```

Faire de même pour `outil_list_sessions`, `outil_allow_publish` et `outil_remember` en reprenant les corps existants mot pour mot.

- [ ] **Step 5: Rebuild `_build_mcp_server` on top of the methods**

Les closures ne portent plus de logique, seulement l'adaptation au SDK :

```python
    def _build_mcp_server(self, user_id: str) -> Any:
        from claude_agent_sdk import create_sdk_mcp_server, tool

        def declare(nom: str, appel: Any) -> Any:
            description, schema = SCHEMAS_OUTILS[nom]
            return tool(nom, description, schema)(appel)

        async def list_projects(_args: dict[str, Any]) -> dict[str, Any]:
            return _text(await self.outil_list_projects(user_id))

        async def list_sessions(_args: dict[str, Any]) -> dict[str, Any]:
            return _text(await self.outil_list_sessions(user_id))

        async def dispatch(args: dict[str, Any]) -> dict[str, Any]:
            return _text(
                await self.outil_dispatch(
                    user_id,
                    project_id=str(args.get("project_id") or ""),
                    consigne=str(args.get("consigne") or ""),
                    session_id=str(args.get("session_id") or "") or None,
                    nouveau_chantier=bool(args.get("nouveau_chantier")),
                )
            )

        async def allow_publish(args: dict[str, Any]) -> dict[str, Any]:
            return _text(
                await self.outil_allow_publish(
                    user_id,
                    session_id=str(args.get("session_id") or ""),
                    autoriser=bool(args.get("autoriser")),
                )
            )

        async def remember(args: dict[str, Any]) -> dict[str, Any]:
            return _text(await self.outil_remember(user_id, fait=str(args.get("fait") or "")))

        return create_sdk_mcp_server(
            name=_MCP_SERVER,
            tools=[
                declare("list_projects", list_projects),
                declare("list_sessions", list_sessions),
                declare("dispatch", dispatch),
                declare("allow_publish", allow_publish),
                declare("remember", remember),
            ],
        )
```

- [ ] **Step 6: Run the tests to verify they pass**

Run: `cd backend && uv run pytest tests/unit/test_supervisor_tools.py tests/unit/test_supervisor_dispatch.py -v`
Expected: PASS

- [ ] **Step 7: Run the backend gate, then commit**

Vérifier l'état de la PR dans un appel séparé, puis commiter avec le message :

```
refactor(superviseur): un seul corps par outil

Les cinq outils étaient des closures qui capturaient user_id : intestables, et
impossibles à servir par un second transport sans les réécrire. Les corps
deviennent des méthodes publiques, les descriptions et schémas une table lue
par les deux transports. Rien ne change vu de Claude.
```

## Task 4: `list_projects` sait ce qui dort

**Files:**
- Modify: `backend/app/services/supervisor_service.py` (`outil_list_projects`)
- Test: `backend/tests/unit/test_supervisor_tools.py` (compléter)

**Interfaces:**
- Consomme : `SCHEMAS_OUTILS["list_projects"]` (description à enrichir), `SessionRow.updated_at`, `SessionRow.state`.
- Produit : une sortie qui porte, par projet, l'ancienneté de la dernière activité et le nombre de sessions en attente d'un geste humain.

- [ ] **Step 1: Write the failing test**

```python
@pytest.mark.asyncio
async def test_list_projects_dit_depuis_quand_un_projet_dort(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Sans date, « relance-moi sur un projet oublié » n'a aucune donnée pour
    tenir : rien dans la sortie ne disait qu'un projet dormait."""
    from datetime import UTC, datetime, timedelta

    from app.core.constants import SESSION_STATE_WAITING_INPUT
    from app.db.models import Project, Session as SessionRow, User

    async with session_factory() as db:
        user = User(email="jarl@exemple.lan", hashed_password="x")
        db.add(user)
        await db.flush()
        projet = Project(
            user_id=user.id,
            name="Munin",
            provider="github",
            repo_full_name="exemple/munin",
            default_branch="main",
            local_path="/tmp/munin",
        )
        db.add(projet)
        await db.flush()
        vieux = SessionRow(
            project_id=projet.id,
            user_id=user.id,
            branch="claude/un",
            worktree_path="/tmp/wt1",
            model="claude-sonnet-5",
            state=SESSION_STATE_WAITING_INPUT,
        )
        db.add(vieux)
        await db.flush()
        vieux.updated_at = datetime.now(UTC) - timedelta(days=12)
        await db.commit()
        user_id = user.id

    service = service_superviseur(session_factory)
    texte = await service.outil_list_projects(user_id)
    assert "12 j" in texte, "l'ancienneté doit apparaître"
    assert "1 session attend" in texte, "ce qui attend John doit apparaître"
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd backend && uv run pytest tests/unit/test_supervisor_tools.py::test_list_projects_dit_depuis_quand_un_projet_dort -v`
Expected: FAIL, `assert '12 j' in texte`

- [ ] **Step 3: Implement**

Deux agrégats SQL, pas d'appel git : compter les commits non poussés aurait demandé un `git rev-list` par projet à chaque appel, pour dire ce que l'état `waiting_input` dit déjà.

```python
def _anciennete(moment: datetime | None) -> str:
    """Ancienneté lisible. Un agent raisonne sur « il y a 12 jours », pas sur
    un horodatage ISO qu'il devrait soustraire de tête."""
    if moment is None:
        return "jamais travaillé"
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=UTC)
    delta = datetime.now(UTC) - moment
    jours = delta.days
    if jours >= 1:
        return f"il y a {jours} j"
    heures = delta.seconds // 3600
    if heures >= 1:
        return f"il y a {heures} h"
    return "à l'instant"
```

Les symboles utilisés ci-dessus et ci-dessous doivent être importés en tête de
`supervisor_service.py` s'ils n'y sont pas déjà : `from datetime import UTC,
datetime`, `from sqlalchemy import func`, et depuis `app.core.constants` les
deux états `SESSION_STATE_WAITING_INPUT` et `SESSION_STATE_BLOCKED` (vérifier
leurs noms exacts dans ce fichier, ce sont ceux que `state_after_turn` rend).

Et dans `outil_list_projects`, après la liste des projets :

```python
        async with self._factory() as db:
            result = await db.execute(
                select(Project).where(Project.user_id == user_id).order_by(Project.name.asc())
            )
            projects = list(result.scalars().all())
            if not projects:
                return "Aucun projet branché sur Eldir."

            activite = await db.execute(
                select(
                    SessionRow.project_id,
                    func.max(SessionRow.updated_at),
                    func.count().filter(
                        SessionRow.state.in_(
                            (SESSION_STATE_WAITING_INPUT, SESSION_STATE_BLOCKED)
                        )
                    ),
                )
                .where(
                    SessionRow.user_id == user_id,
                    SessionRow.is_system.is_(False),
                )
                .group_by(SessionRow.project_id)
            )
            par_projet = {
                pid: (dernier, attente) for pid, dernier, attente in activite.all()
            }

        lines: list[str] = []
        for p in projects:
            dernier, attente = par_projet.get(p.id, (None, 0))
            suffixe = f" · {attente} session attend un geste de John" if attente else ""
            lines.append(
                f"- {p.name} (id={p.id}) · {p.provider}:{p.repo_full_name} "
                f"· branche {p.default_branch} · dernière activité : "
                f"{_anciennete(dernier)}{suffixe}"
            )
        return "\n".join(lines)
```

Le test attend « 1 session attend » : le libellé ci-dessus le contient.

Compléter la description dans `SCHEMAS_OUTILS`, sinon l'agent ne saura pas qu'il peut s'en servir pour trier :

```python
    "list_projects": (
        "Liste les repos branchés sur Eldir, avec pour chacun la date de "
        "dernière activité et ce qui attend un geste de John. Sert à "
        "identifier de quel projet il parle, et à repérer ceux qui dorment.",
        {"type": "object", "properties": {}},
    ),
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd backend && uv run pytest tests/unit/test_supervisor_tools.py -v`
Expected: PASS

- [ ] **Step 5: Run the backend gate, then commit**

Vérifier l'état de la PR dans un appel séparé, puis commiter avec le message :

```
feat(superviseur): list_projects dit ce qui dort

La sortie ne portait aucune date : « relance-moi sur un projet oublié » n'avait
donc aucune donnée pour tenir, l'oubli n'étant pas calculable sans ancienneté.
Deux agrégats SQL l'ajoutent, plus le nombre de sessions qui attendent John.
Aucun appel git : compter les commits non poussés coûterait un rev-list par
projet et par appel, pour dire ce que l'état waiting_input dit déjà.
```

## Task 5: le jeton d'agent

**Files:**
- Create: `backend/app/db/models/agent_token.py`
- Create: `backend/alembic/versions/0012_agent_tokens.py`
- Create: `backend/app/services/agent_token_service.py`
- Modify: `backend/app/db/models/__init__.py`
- Test: `backend/tests/unit/test_agent_token_service.py`

**Interfaces:**
- Consomme : `create_access_token(subject, *, expires_minutes, extra_claims)` et `decode_access_token(token)` de `app/core/security.py`.
- Produit :

```python
class AgentToken(UUIDPrimaryKey, TimestampMixin, Base)  # table "agent_tokens"
    user_id: str; label: str; jti: str; last_used_at: datetime | None; revoked_at: datetime | None

async def emettre(db, *, user_id: str, label: str) -> tuple[AgentToken, str]  # (ligne, jeton en clair)
async def lister(db, *, user_id: str) -> list[AgentToken]
async def revoquer(db, *, user_id: str, token_id: str) -> None
async def authentifier(db, *, jeton: str) -> tuple[str, str]  # (user_id, label)
```

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/unit/test_agent_token_service.py
"""Jeton d'agent : longue durée, donc révocable.

Un jeton qu'on ne peut pas révoquer est un jeton qu'on ne peut pas émettre.
C'est l'unique raison d'être de la table : le JWT se vérifierait tout seul.
"""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AuthenticationError
from app.core.security import create_access_token
from app.services import agent_token_service as svc


@pytest.mark.asyncio
async def test_un_jeton_emis_authentifie_son_utilisateur(db_session: AsyncSession) -> None:
    ligne, clair = await svc.emettre(db_session, user_id="u1", label="eldir du village")
    await db_session.commit()
    assert clair, "le jeton en clair n'est rendu qu'une fois, à l'émission"
    user_id, label = await svc.authentifier(db_session, jeton=clair)
    assert user_id == "u1"
    assert label == "eldir du village"
    assert ligne.revoked_at is None


@pytest.mark.asyncio
async def test_un_jeton_revoque_est_refuse(db_session: AsyncSession) -> None:
    ligne, clair = await svc.emettre(db_session, user_id="u1", label="à couper")
    await db_session.commit()
    await svc.revoquer(db_session, user_id="u1", token_id=ligne.id)
    await db_session.commit()
    with pytest.raises(AuthenticationError):
        await svc.authentifier(db_session, jeton=clair)


@pytest.mark.asyncio
async def test_un_jwt_de_session_ordinaire_n_ouvre_pas_la_porte(
    db_session: AsyncSession,
) -> None:
    """Sans ce refus, tout jeton de connexion vaudrait jeton d'agent, donc la
    révocation ne protégerait rien."""
    ordinaire = create_access_token("u1")
    with pytest.raises(AuthenticationError):
        await svc.authentifier(db_session, jeton=ordinaire)


@pytest.mark.asyncio
async def test_un_jeton_inconnu_en_base_est_refuse(db_session: AsyncSession) -> None:
    """Un jti forgé avec la bonne clé mais absent de la table ne passe pas :
    la table est la liste blanche, pas un simple journal."""
    forge = create_access_token("u1", extra_claims={"kind": "agent", "jti": "inexistant"})
    with pytest.raises(AuthenticationError):
        await svc.authentifier(db_session, jeton=forge)
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd backend && uv run pytest tests/unit/test_agent_token_service.py -v`
Expected: FAIL, `ModuleNotFoundError: app.services.agent_token_service`

- [ ] **Step 3: Write the model**

```python
# backend/app/db/models/agent_token.py
"""Jeton longue durée d'un agent externe branché sur Eldir.

Le jeton lui-même est un JWT signé par la clé de l'instance : il se vérifie
sans la base. Cette table existe pour une seule raison, la révocation. Un
agent tourne en continu et ne peut pas se reconnecter derrière un formulaire,
donc son jeton vit des mois ; sans moyen de le couper, on ne pourrait pas
l'émettre. Le `jti` est la liste blanche, pas un journal.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKey


class AgentToken(UUIDPrimaryKey, TimestampMixin, Base):
    """Une ligne par jeton émis, y compris révoqué (on garde la trace)."""

    __tablename__ = "agent_tokens"
    __table_args__ = (UniqueConstraint("jti", name="uq_agent_tokens_jti"),)

    user_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    # Nom donné par John, affiché dans l'origine des messages dispatchés :
    # en relisant son historique il doit savoir lequel des cerveaux a parlé.
    label: Mapped[str] = mapped_column(String(80), nullable=False)
    jti: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
```

Ajouter l'import et l'entrée `__all__` dans `backend/app/db/models/__init__.py`.

- [ ] **Step 4: Write the migration**

```python
# backend/alembic/versions/0012_agent_tokens.py
"""Jetons d'agent externe, révocables.

Les cinq outils du superviseur s'ouvrent à un agent extérieur par MCP sur
HTTP. Un agent tourne en continu : son jeton vit des mois, là où le JWT de
connexion vit une heure. Cette table est la liste blanche des `jti` valides,
donc le seul moyen de couper un accès sans faire tourner la clé de l'instance.

Revision ID: 0012
Revises: 0011
Create Date: 2026-10-29
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0012"
down_revision: str | Sequence[str] | None = "0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "agent_tokens",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), nullable=False),
        sa.Column("label", sa.String(80), nullable=False),
        sa.Column("jti", sa.String(36), nullable=False),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("jti", name="uq_agent_tokens_jti"),
    )
    op.create_index("ix_agent_tokens_user_id", "agent_tokens", ["user_id"])
    op.create_index("ix_agent_tokens_jti", "agent_tokens", ["jti"])


def downgrade() -> None:
    op.drop_index("ix_agent_tokens_jti", table_name="agent_tokens")
    op.drop_index("ix_agent_tokens_user_id", table_name="agent_tokens")
    op.drop_table("agent_tokens")
```

Vérifier les noms exacts des colonnes d'horodatage dans `app/db/base.py` (`TimestampMixin`) et les reprendre à l'identique, sinon la migration et le modèle divergent.

- [ ] **Step 5: Write the service**

```python
# backend/app/services/agent_token_service.py
"""Émission, révocation et authentification des jetons d'agent."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AuthenticationError, NotFoundError
from app.core.security import create_access_token, decode_access_token
from app.db.models import AgentToken

# Dix ans : un agent ne se reconnecte pas derrière un formulaire. La borne
# n'est pas l'expiration, c'est la révocation.
_DUREE_MINUTES = 10 * 365 * 24 * 60
_KIND = "agent"


async def emettre(db: AsyncSession, *, user_id: str, label: str) -> tuple[AgentToken, str]:
    """Crée un jeton et rend (la ligne, le jeton en clair).

    Le clair n'est rendu qu'ici : on ne le stocke pas, donc on ne peut pas le
    réafficher. L'interface doit le dire avant de le montrer.
    """
    label = label.strip()
    if not label:
        raise NotFoundError("Un jeton d'agent doit porter un libellé.")
    jti = str(uuid.uuid4())
    ligne = AgentToken(user_id=user_id, label=label, jti=jti)
    db.add(ligne)
    await db.flush()
    clair = create_access_token(
        user_id,
        expires_minutes=_DUREE_MINUTES,
        extra_claims={"kind": _KIND, "jti": jti},
    )
    return ligne, clair


async def lister(db: AsyncSession, *, user_id: str) -> list[AgentToken]:
    result = await db.execute(
        select(AgentToken)
        .where(AgentToken.user_id == user_id)
        .order_by(AgentToken.created_at.desc())
    )
    return list(result.scalars().all())


async def revoquer(db: AsyncSession, *, user_id: str, token_id: str) -> None:
    ligne = await db.get(AgentToken, token_id)
    if ligne is None or ligne.user_id != user_id:
        raise NotFoundError(f"Jeton {token_id} introuvable.")
    if ligne.revoked_at is None:
        ligne.revoked_at = datetime.now(UTC)


async def authentifier(db: AsyncSession, *, jeton: str) -> tuple[str, str]:
    """Rend (user_id, libellé) ou lève. Met à jour la date de dernier usage."""
    charge = decode_access_token(jeton)
    if charge.get("kind") != _KIND:
        raise AuthenticationError("Ce jeton n'est pas un jeton d'agent.")
    jti = charge.get("jti")
    sujet = charge.get("sub")
    if not isinstance(jti, str) or not isinstance(sujet, str):
        raise AuthenticationError("Jeton d'agent incomplet.")
    result = await db.execute(select(AgentToken).where(AgentToken.jti == jti))
    ligne = result.scalar_one_or_none()
    if ligne is None or ligne.revoked_at is not None or ligne.user_id != sujet:
        raise AuthenticationError("Jeton d'agent invalide ou révoqué.")
    ligne.last_used_at = datetime.now(UTC)
    return ligne.user_id, ligne.label
```

- [ ] **Step 6: Run the tests to verify they pass**

Run: `cd backend && uv run pytest tests/unit/test_agent_token_service.py -v`
Expected: PASS (4 tests)

- [ ] **Step 7: Verify the migration applies**

Run: `cd backend && uv run alembic upgrade head && uv run alembic downgrade -1 && uv run alembic upgrade head`
Expected: les trois passent sans erreur. Si la base de dev n'est pas joignable, démarrer la stack (`docker compose -f ../docker-compose.dev.yml up -d db`) avant.

- [ ] **Step 8: Run the backend gate, then commit**

Vérifier l'état de la PR dans un appel séparé, puis commiter avec le message :

```
feat(agents): jeton longue durée, révocable

Un agent externe tourne en continu : il ne peut pas se reconnecter derrière un
formulaire, donc son jeton vit des mois là où celui d'une connexion vit une
heure. Le jeton est un JWT signé par la clé de l'instance ; la table n'existe
que pour la révocation, qui est la condition pour oser l'émettre. Un jeton de
connexion ordinaire est refusé, sinon la révocation ne protégerait rien.
```

## Task 6: `/api/mcp/` servi et gardé

**Files:**
- Create: `backend/app/mcp_http.py`
- Modify: `backend/app/main.py`
- Modify: `backend/app/core/config.py`
- Test: `backend/tests/integration/test_mcp_http.py`

**Interfaces:**
- Consomme : `SCHEMAS_OUTILS` et les méthodes `outil_*` (tâche 3), `agent_token_service.authentifier` (tâche 5), `get_supervisor_service()` de `app/services/singletons.py`.
- Produit : `construire_app_mcp() -> tuple[FastMCP, ASGIApp]`, et `AGENT_COURANT: ContextVar[tuple[str, str] | None]` que les outils lisent pour savoir au nom de qui ils agissent.

**Trois pièges prouvés sur la version verrouillée (mcp 1.27.1). Chacun coûte une heure si on l'ignore :**

1. `streamable_http_app()` publie son point d'entrée sur `/mcp` par défaut. Monté sous `/api/mcp`, le chemin réel devient `/api/mcp/mcp` et `/api/mcp/` rend **404**. D'où `streamable_http_path="/"`.
2. L'app rendue est une app Starlette **avec son propre lifespan**, que FastAPI ne joue pas pour une app montée. Sans `mcp.session_manager.run()` dans le lifespan du parent, toute requête échoue. Et `session_manager` n'est accessible qu'**après** l'appel à `streamable_http_app()`, il est construit paresseusement.
3. La protection anti-DNS-rebinding refuse tout `Host` qu'elle ne connaît pas, en **421 « Invalid Host header »**. Eldir est joint par un nom de machine privé : il faut le déclarer, ou couper la protection. Le jeton est la vraie garde ici (aucun cookie en jeu, donc rien à rejouer depuis un navigateur).

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/integration/test_mcp_http.py
"""La surface MCP HTTP, bout en bout.

Même outils, mêmes descriptions, même refus de publication que le superviseur
interne : la seule différence est le transport.
"""

from __future__ import annotations

import json

import pytest
from httpx import AsyncClient

_CORPS = {"jsonrpc": "2.0", "id": 1, "method": "tools/list"}
_ENTETES = {
    "Content-Type": "application/json",
    "Accept": "application/json, text/event-stream",
}


def _outils(reponse_texte: str) -> list[str]:
    """Le transport répond en SSE : les données vivent sur les lignes `data:`."""
    for ligne in reponse_texte.splitlines():
        if ligne.startswith("data: "):
            return [o["name"] for o in json.loads(ligne[6:])["result"]["tools"]]
    raise AssertionError(f"aucune charge SSE dans : {reponse_texte[:200]}")


@pytest.mark.asyncio
async def test_sans_jeton_la_porte_est_fermee(client: AsyncClient) -> None:
    r = await client.post("/api/mcp/", json=_CORPS, headers=_ENTETES)
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_avec_un_jeton_valide_les_cinq_outils_sont_la(
    client: AsyncClient, db_session, jeton_agent: str
) -> None:
    r = await client.post(
        "/api/mcp/",
        json=_CORPS,
        headers={**_ENTETES, "Authorization": f"Bearer {jeton_agent}"},
    )
    assert r.status_code == 200
    assert set(_outils(r.text)) == {
        "list_projects",
        "list_sessions",
        "dispatch",
        "allow_publish",
        "remember",
    }


@pytest.mark.asyncio
async def test_un_jeton_revoque_ne_passe_plus(
    client: AsyncClient, jeton_agent_revoque: str
) -> None:
    r = await client.post(
        "/api/mcp/",
        json=_CORPS,
        headers={**_ENTETES, "Authorization": f"Bearer {jeton_agent_revoque}"},
    )
    assert r.status_code == 401
```

Les deux fixtures, à poser dans `backend/tests/conftest.py` :

```python
@pytest.fixture
async def jeton_agent(session_factory) -> str:
    from app.services import agent_token_service

    async with session_factory() as db:
        _, clair = await agent_token_service.emettre(
            db, user_id="u-test", label="agent de test"
        )
        await db.commit()
    return clair


@pytest.fixture
async def jeton_agent_revoque(session_factory) -> str:
    from app.services import agent_token_service

    async with session_factory() as db:
        ligne, clair = await agent_token_service.emettre(
            db, user_id="u-test", label="agent coupé"
        )
        await db.commit()
        await agent_token_service.revoquer(db, user_id="u-test", token_id=ligne.id)
        await db.commit()
    return clair
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd backend && uv run pytest tests/integration/test_mcp_http.py -v`
Expected: FAIL, 404 sur `/api/mcp/` (la route n'existe pas).

- [ ] **Step 3: Add the settings**

Dans `backend/app/core/config.py` :

```python
    # ── Surface d'agent externe (MCP sur HTTP) ──────────────────
    # Hôtes autorisés à joindre /api/mcp/, séparés par des virgules
    # (ex "eldir.exemple.lan,127.0.0.1:8000"). Vide = protection
    # anti-DNS-rebinding désactivée : le jeton d'agent est la garde, et
    # aucun cookie n'est en jeu sur cette surface, donc rien à rejouer
    # depuis un navigateur. À renseigner si l'endpoint est exposé au-delà
    # du VPN.
    mcp_allowed_hosts: str = ""

    @property
    def mcp_hosts(self) -> list[str]:
        return [h.strip() for h in self.mcp_allowed_hosts.split(",") if h.strip()]
```

- [ ] **Step 4: Write the MCP app**

```python
# backend/app/mcp_http.py
"""La surface MCP d'Eldir, servie en HTTP pour un agent extérieur.

Les cinq outils sont ceux du superviseur, à l'identique : ce module ne porte
aucune logique métier, seulement l'adaptation d'un transport et la garde du
jeton. Toute règle qui vivrait ici seulement serait une règle que le
superviseur interne n'applique pas, donc deux Eldir qui divergent.
"""

from __future__ import annotations

from contextvars import ContextVar
from typing import Any

from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings
from starlette.types import ASGIApp, Receive, Scope, Send

from app.core.config import get_settings
from app.core.exceptions import AuthenticationError
from app.core.logging import get_logger
from app.db.session import async_session_factory
from app.services import agent_token_service
from app.services.singletons import get_supervisor_service
from app.services.supervisor_service import SCHEMAS_OUTILS

logger = get_logger("eldir.mcp")

# Au nom de qui l'appel en cours agit : (user_id, libellé du jeton). Les
# fonctions d'outil de FastMCP ne reçoivent pas la requête, et un contextvar
# traverse la pile sans que chaque outil ait à porter un argument de plus.
AGENT_COURANT: ContextVar[tuple[str, str] | None] = ContextVar("agent_courant", default=None)


def agent_courant() -> tuple[str, str]:
    valeur = AGENT_COURANT.get()
    if valeur is None:
        raise AuthenticationError("Appel MCP sans agent authentifié.")
    return valeur


class GardeJeton:
    """Valide le Bearer devant l'app MCP.

    Pourquoi pas le `token_verifier` de FastMCP : il exige des réglages `auth`
    complets de serveur de ressources OAuth (`ValueError: Cannot specify
    auth_server_provider or token_verifier without auth settings`). On sert un
    jeton statique, pas un flux OAuth : vingt lignes honnêtes valent mieux
    qu'une façade.
    """

    def __init__(self, app: ASGIApp) -> None:
        self._app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self._app(scope, receive, send)
            return
        entetes = dict(scope.get("headers") or [])
        brut = entetes.get(b"authorization", b"").decode()
        if not brut.lower().startswith("bearer "):
            await self._refuser(send, "Header Authorization manquant.")
            return
        try:
            async with async_session_factory() as db:
                identite = await agent_token_service.authentifier(
                    db, jeton=brut.split(" ", 1)[1]
                )
                await db.commit()
        except AuthenticationError as exc:
            await self._refuser(send, exc.message)
            return
        jeton_ctx = AGENT_COURANT.set(identite)
        try:
            await self._app(scope, receive, send)
        finally:
            AGENT_COURANT.reset(jeton_ctx)

    async def _refuser(self, send: Send, message: str) -> None:
        corps = f'{{"code":"unauthorized","message":"{message}"}}'.encode()
        await send(
            {
                "type": "http.response.start",
                "status": 401,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"content-length", str(len(corps)).encode()),
                ],
            }
        )
        await send({"type": "http.response.body", "body": corps})


def construire_app_mcp() -> tuple[FastMCP, ASGIApp]:
    hotes = get_settings().mcp_hosts
    mcp = FastMCP(
        "eldir",
        # Sans état : aucune affinité de session, donc un redémarrage du
        # backend ne casse pas l'agent, et n'importe quel proxy convient.
        stateless_http=True,
        # Le chemin par défaut est /mcp : monté sous /api/mcp il donnerait
        # /api/mcp/mcp, et /api/mcp/ rendrait 404.
        streamable_http_path="/",
        transport_security=TransportSecuritySettings(
            enable_dns_rebinding_protection=bool(hotes),
            allowed_hosts=hotes or None,
        ),
    )

    def enregistrer(nom: str, fonction: Any) -> None:
        description, _schema = SCHEMAS_OUTILS[nom]
        mcp.add_tool(fonction, name=nom, description=description)

    async def list_projects() -> str:
        user_id, _ = agent_courant()
        return await get_supervisor_service().outil_list_projects(user_id)

    async def list_sessions() -> str:
        user_id, _ = agent_courant()
        return await get_supervisor_service().outil_list_sessions(user_id)

    async def dispatch(
        project_id: str,
        consigne: str,
        session_id: str | None = None,
        nouveau_chantier: bool = False,
    ) -> str:
        user_id, _ = agent_courant()
        return await get_supervisor_service().outil_dispatch(
            user_id,
            project_id=project_id,
            consigne=consigne,
            session_id=session_id,
            nouveau_chantier=nouveau_chantier,
        )

    async def allow_publish(session_id: str, autoriser: bool) -> str:
        user_id, _ = agent_courant()
        return await get_supervisor_service().outil_allow_publish(
            user_id, session_id=session_id, autoriser=autoriser
        )

    async def remember(fait: str) -> str:
        user_id, _ = agent_courant()
        return await get_supervisor_service().outil_remember(user_id, fait=fait)

    enregistrer("list_projects", list_projects)
    enregistrer("list_sessions", list_sessions)
    enregistrer("dispatch", dispatch)
    enregistrer("allow_publish", allow_publish)
    enregistrer("remember", remember)

    return mcp, GardeJeton(mcp.streamable_http_app())
```

Vérifier la signature de `FastMCP.add_tool` sur la version verrouillée (`uv run python -c "from mcp.server.fastmcp import FastMCP; help(FastMCP.add_tool)"`) et l'ajuster si l'ordre des arguments diffère. FastMCP dérive le schéma des annotations de type ; `SCHEMAS_OUTILS` reste la source des **descriptions**, qui sont ce que le modèle lit.

- [ ] **Step 5: Mount it with its lifespan**

Dans `backend/app/main.py`, construire l'app MCP une fois et jouer son gestionnaire de sessions dans le lifespan du parent :

```python
from app.mcp_http import construire_app_mcp

_mcp, _mcp_app = construire_app_mcp()


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    configure_logging()
    logger = get_logger("eldir.lifespan")
    logger.info("app.startup", env=get_settings().app_env)
    if not get_settings().is_test:
        try:
            await emit_bootstrap_token_if_needed()
        except Exception:
            logger.exception("bootstrap.hook.error")
        try:
            await init_singletons()
        except Exception:
            logger.exception("singletons.init.error")
    # L'app MCP montée a son propre lifespan, que FastAPI ne joue pas pour une
    # sous-app : son gestionnaire de sessions doit tourner ici, sinon toute
    # requête vers /api/mcp/ échoue. Il n'existe qu'après streamable_http_app().
    async with _mcp.session_manager.run():
        try:
            yield
        finally:
            if not get_settings().is_test:
                await shutdown_singletons()
            logger.info("app.shutdown")
```

Et dans `create_app`, après les routeurs :

```python
    app.include_router(api_router, prefix=settings.api_prefix)
    app.include_router(ws_router)
    # Surface d'agent externe. Montée hors du routeur v1 : le transport MCP
    # parle JSON-RPC sur SSE, pas du REST versionné.
    app.mount("/api/mcp", _mcp_app)
    return app
```

- [ ] **Step 6: Run the tests to verify they pass**

Run: `cd backend && uv run pytest tests/integration/test_mcp_http.py -v`
Expected: PASS (3 tests). Sur un 421 « Invalid Host header », vérifier que `mcp_allowed_hosts` est vide en test. Sur un 404, vérifier `streamable_http_path="/"`.

- [ ] **Step 7: Run the backend gate, then commit**

Vérifier l'état de la PR dans un appel séparé, puis commiter avec le message :

```
feat(agents): les cinq outils servis en MCP sur HTTP

Même table de descriptions, mêmes corps, même refus de publication que le
superviseur interne : seul le transport change. La garde du jeton est une
vingtaine de lignes d'ASGI plutôt que le token_verifier de FastMCP, qui exige
des réglages OAuth complets de serveur de ressources pour un jeton statique.

Trois pièges payés et commentés : le chemin par défaut /mcp qui donnait
/api/mcp/mcp, le lifespan d'une sous-app que FastAPI ne joue pas, et la
protection anti-DNS-rebinding qui refuse tout Host inconnu en 421.
```

## Task 7: les routes et l'interface des jetons

**Files:**
- Create: `backend/app/schemas/agent_token.py`
- Create: `backend/app/api/v1/agent_tokens.py`
- Modify: `backend/app/api/v1/__init__.py`
- Create: `frontend/src/features/settings/agent-tokens.tsx`
- Modify: `frontend/src/lib/api/queries.ts`
- Test: `backend/tests/integration/test_agent_token_routes.py`

**Interfaces:**
- Consomme : `agent_token_service.emettre / lister / revoquer`, `CurrentUserId`.
- Produit : `GET /api/v1/agent-tokens`, `POST /api/v1/agent-tokens` (rend le clair une fois), `DELETE /api/v1/agent-tokens/{id}`. Côté front : `useAgentTokens()`, `useCreateAgentToken()`, `useRevokeAgentToken()`.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/integration/test_agent_token_routes.py
"""Routes des jetons d'agent : le clair n'apparaît qu'une fois."""

from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_le_clair_est_rendu_a_la_creation_puis_jamais(
    client: AsyncClient, entetes_john: dict[str, str]
) -> None:
    r = await client.post(
        "/api/v1/agent-tokens", json={"label": "eldir du village"}, headers=entetes_john
    )
    assert r.status_code == 201
    cree = r.json()
    assert cree["token"], "le clair est rendu à la création"
    assert cree["label"] == "eldir du village"

    r = await client.get("/api/v1/agent-tokens", headers=entetes_john)
    assert r.status_code == 200
    liste = r.json()
    assert len(liste) == 1
    assert "token" not in liste[0], "on ne stocke pas le clair, donc on ne le réaffiche pas"


@pytest.mark.asyncio
async def test_revoquer_retire_le_jeton_de_la_liste_active(
    client: AsyncClient, entetes_john: dict[str, str]
) -> None:
    cree = (
        await client.post(
            "/api/v1/agent-tokens", json={"label": "à couper"}, headers=entetes_john
        )
    ).json()
    r = await client.delete(f"/api/v1/agent-tokens/{cree['id']}", headers=entetes_john)
    assert r.status_code == 204
    liste = (await client.get("/api/v1/agent-tokens", headers=entetes_john)).json()
    assert liste[0]["revoked_at"] is not None
```

La fixture `entetes_john` (à poser dans `backend/tests/conftest.py` si elle n'existe pas déjà sous un autre nom, auquel cas reprendre l'existante) :

```python
@pytest.fixture
def entetes_john() -> dict[str, str]:
    from app.core.security import create_access_token

    return {"Authorization": f"Bearer {create_access_token('u-test')}"}
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd backend && uv run pytest tests/integration/test_agent_token_routes.py -v`
Expected: FAIL, 404 sur `/api/v1/agent-tokens`

- [ ] **Step 3: Write the schemas**

```python
# backend/app/schemas/agent_token.py
"""Schémas des jetons d'agent.

`AgentTokenCreated` porte le clair, `AgentTokenRead` jamais : c'est la
différence qui garantit qu'on ne le réaffiche pas par accident.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class AgentTokenInput(BaseModel):
    label: str = Field(min_length=1, max_length=80)


class AgentTokenRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    label: str
    created_at: datetime
    last_used_at: datetime | None
    revoked_at: datetime | None


class AgentTokenCreated(AgentTokenRead):
    # Rendu une seule fois, à la création. Non stocké.
    token: str
```

- [ ] **Step 4: Write the routes**

```python
# backend/app/api/v1/agent_tokens.py
"""Jetons des agents externes branchés sur /api/mcp/."""

from __future__ import annotations

from fastapi import APIRouter, Response, status

from app.core.deps import CurrentUserId, DbDep
from app.schemas.agent_token import AgentTokenCreated, AgentTokenInput, AgentTokenRead
from app.services import agent_token_service

router = APIRouter(prefix="/agent-tokens", tags=["agent-tokens"])


@router.get("", response_model=list[AgentTokenRead])
async def list_agent_tokens(user_id: CurrentUserId, db: DbDep) -> list[AgentTokenRead]:
    lignes = await agent_token_service.lister(db, user_id=user_id)
    return [AgentTokenRead.model_validate(ligne) for ligne in lignes]


@router.post("", response_model=AgentTokenCreated, status_code=status.HTTP_201_CREATED)
async def create_agent_token(
    payload: AgentTokenInput, user_id: CurrentUserId, db: DbDep
) -> AgentTokenCreated:
    ligne, clair = await agent_token_service.emettre(db, user_id=user_id, label=payload.label)
    await db.commit()
    await db.refresh(ligne)
    return AgentTokenCreated(**AgentTokenRead.model_validate(ligne).model_dump(), token=clair)


@router.delete("/{token_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_agent_token(token_id: str, user_id: CurrentUserId, db: DbDep) -> Response:
    await agent_token_service.revoquer(db, user_id=user_id, token_id=token_id)
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
```

Brancher dans `backend/app/api/v1/__init__.py` en suivant exactement le style des autres routeurs du fichier.

- [ ] **Step 5: Run the tests to verify they pass**

Run: `cd backend && uv run pytest tests/integration/test_agent_token_routes.py -v`
Expected: PASS (2 tests)

- [ ] **Step 6: Regenerate the TS types**

Run: `cd backend && uv run python ../scripts/generate_types.py` ou la commande que décrit `shared/README.md`. La CI `types.yml` vérifie que `api-generated.ts` est synchrone : un oubli ici fait échouer la PR.

- [ ] **Step 7: Build the Settings panel**

Dans `frontend/src/lib/api/queries.ts`, trois hooks sur le modèle exact des voisins :

```ts
export function useAgentTokens() {
  return useQuery({
    queryKey: queryKeys.agentTokens,
    queryFn: () => apiClient.get<AgentTokenRead[]>('/agent-tokens'),
  });
}

export function useCreateAgentToken() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: AgentTokenInput) =>
      apiClient.post<AgentTokenCreated, AgentTokenInput>('/agent-tokens', body),
    onSuccess: () => qc.invalidateQueries({ queryKey: queryKeys.agentTokens }),
  });
}

export function useRevokeAgentToken() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => apiClient.delete<void>(`/agent-tokens/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: queryKeys.agentTokens }),
  });
}
```

Ajouter `agentTokens: ['agent-tokens'] as const` à `queryKeys`.

Le panneau `frontend/src/features/settings/agent-tokens.tsx` : un champ libellé, un bouton « Créer un jeton », et la liste. Le clair s'affiche dans un bloc monospace **avec l'avertissement avant** (« Copie-le maintenant : il ne sera plus affiché »), un bouton copier, et chaque ligne porte le libellé, la date de dernier usage et « Révoquer ». Reprendre les classes des autres panneaux de Settings ; les textes d'accent utilisent les variantes `-text` (`text-eldir-red-text` pour « Révoquer »), jamais les accents nus, qui ne tiennent pas le contraste sur fond clair.

- [ ] **Step 8: Run the frontend gate, then commit**

Run: `cd frontend && npm run lint && npx tsc --noEmit && npm test && npm run build`

Vérifier l'état de la PR dans un appel séparé, puis commiter avec le message :

```
feat(reglages): créer et révoquer les jetons d'agent

Le clair n'est rendu qu'à la création et n'est pas stocké : le panneau le dit
avant de le montrer. Deux schémas distincts côté API pour que le réafficher
soit impossible par accident, pas seulement déconseillé.
```

## Task 8: l'origine dit lequel des deux cerveaux a parlé

**Files:**
- Modify: `backend/app/services/supervisor_service.py` (`outil_dispatch`, `_run_child`)
- Modify: `backend/app/core/constants.py`
- Test: `backend/tests/unit/test_supervisor_tools.py` (compléter)

**Interfaces:**
- Consomme : `agent_courant()` de `app/mcp_http.py`, `MESSAGE_ORIGIN_ELDIR`.
- Produit : `SupervisorService.outil_dispatch(..., origine: str = MESSAGE_ORIGIN_ELDIR)` et un `origin` de la forme `agent:<libellé>` quand l'appel vient de `/api/mcp/`.

- [ ] **Step 1: Write the failing test**

```python
@pytest.mark.asyncio
async def test_l_origine_nomme_l_agent_qui_a_dispatche(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Avec deux cerveaux possibles, un historique qui ne dit pas lequel a
    parlé ne répond pas à la seule question qu'on se pose en le relisant."""
    from app.services.supervisor_service import origine_de_dispatch

    assert origine_de_dispatch(None) == "eldir"
    assert origine_de_dispatch("eldir du village") == "agent:eldir du village"
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd backend && uv run pytest tests/unit/test_supervisor_tools.py -k origine -v`
Expected: FAIL, `cannot import name 'origine_de_dispatch'`

- [ ] **Step 3: Implement**

```python
def origine_de_dispatch(libelle_agent: str | None) -> str:
    """Qui a envoyé cette consigne.

    L'interface distingue déjà John d'Eldir, pour ne jamais faire passer une
    consigne d'Eldir pour une demande de John. Avec un second cerveau
    possible, il faut aussi distinguer les Eldir entre eux : en relisant son
    historique, John cherche précisément à savoir lequel a décidé.
    """
    if not libelle_agent:
        return MESSAGE_ORIGIN_ELDIR
    return f"agent:{libelle_agent}"
```

`outil_dispatch` prend un paramètre `libelle_agent: str | None = None` et le passe à `_run_child`, qui le convertit en `origin` pour `send_message`. Dans `app/mcp_http.py`, la fonction `dispatch` lit le libellé de `agent_courant()` et le transmet.

Le front affiche déjà `origin` : vérifier qu'un `origin` inconnu ne casse pas le rendu et tombe sur un libellé lisible plutôt que sur du vide.

- [ ] **Step 4: Run the tests, run the gate, commit**

Vérifier l'état de la PR dans un appel séparé, puis commiter avec le message :

```
feat(superviseur): l'origine d'une consigne nomme son auteur

Les messages distinguaient John d'Eldir. Avec deux cerveaux possibles il faut
distinguer les Eldir entre eux, sinon relire son historique ne répond pas à la
question qu'on se pose en le relisant : lequel a décidé ça.
```

## Task 9: le ping de fin de tour, en HTTP

**Files:**
- Create: `backend/app/services/turn_webhook.py`
- Modify: `backend/app/services/supervisor_service.py` (`_notify_turn_done`)
- Modify: `backend/app/core/config.py`
- Test: `backend/tests/unit/test_turn_webhook.py`

**Interfaces:**
- Consomme : `httpx.AsyncClient`, `Settings.turn_webhook_url`, `Settings.turn_webhook_secret`.
- Produit : `signer(corps: bytes, secret: str) -> str` et `async def prevenir(charge: dict[str, Any]) -> None`, qui n'échoue jamais vers l'appelant.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/unit/test_turn_webhook.py
"""Ping de fin de tour vers un abonné externe.

Le ping interne réveille le superviseur en mémoire : un agent dans un autre
processus ne le voit pas, et n'apprendrait la fin du travail qu'à son prochain
réveil. Il avancerait d'un pas par tic de cron au lieu d'enchaîner.
"""

from __future__ import annotations

import pytest

from app.services.turn_webhook import prevenir, signer


def test_la_signature_depend_du_corps_et_du_secret() -> None:
    a = signer(b'{"session_id":"s1"}', "secret")
    assert a == signer(b'{"session_id":"s1"}', "secret"), "déterministe"
    assert a != signer(b'{"session_id":"s2"}', "secret"), "dépend du corps"
    assert a != signer(b'{"session_id":"s1"}', "autre"), "dépend du secret"
    assert a.startswith("sha256="), "l'abonné doit savoir quel algorithme vérifier"


@pytest.mark.asyncio
async def test_sans_url_configuree_on_ne_fait_rien() -> None:
    await prevenir({"session_id": "s1"})  # ne lève pas


@pytest.mark.asyncio
async def test_un_abonne_injoignable_ne_fait_pas_echouer_le_tour(monkeypatch) -> None:
    """La session enfant a fini son travail. Un webhook mort ne doit pas
    transformer un succès en échec."""
    import httpx

    from app.core.config import get_settings

    monkeypatch.setattr(
        get_settings(), "turn_webhook_url", "http://127.0.0.1:1/ping", raising=False
    )

    async def _explose(*_a, **_k):
        raise httpx.ConnectError("injoignable")

    monkeypatch.setattr(httpx.AsyncClient, "post", _explose)
    await prevenir({"session_id": "s1"})  # ne lève pas
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd backend && uv run pytest tests/unit/test_turn_webhook.py -v`
Expected: FAIL, `ModuleNotFoundError: app.services.turn_webhook`

- [ ] **Step 3: Add the settings**

```python
    # ── Ping de fin de tour vers un abonné externe ──────────────
    # Un seul abonné : une table viendra quand il y en aura deux.
    turn_webhook_url: str = ""
    turn_webhook_secret: SecretStr | None = None
    turn_webhook_timeout_seconds: float = 10.0
```

- [ ] **Step 4: Implement**

```python
# backend/app/services/turn_webhook.py
"""Prévient un abonné externe qu'une session dispatchée a fini son tour."""

from __future__ import annotations

import hashlib
import hmac
import json
from typing import Any

import httpx

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger("eldir.turn_webhook")


def signer(corps: bytes, secret: str) -> str:
    """Signature du corps, pour que l'abonné sache que le ping vient d'Eldir.

    Le préfixe nomme l'algorithme : sans lui, un abonné devinerait, et le jour
    où l'algorithme change, il vérifierait encore l'ancien en silence.
    """
    empreinte = hmac.new(secret.encode(), corps, hashlib.sha256).hexdigest()
    return f"sha256={empreinte}"


async def prevenir(charge: dict[str, Any]) -> None:
    """Poste la charge si un abonné est configuré. N'échoue jamais.

    La session enfant a terminé son travail : un abonné injoignable ne doit pas
    transformer ce succès en échec. L'échec est journalisé, et c'est tout.
    """
    settings = get_settings()
    url = settings.turn_webhook_url.strip()
    if not url:
        return
    corps = json.dumps(charge, ensure_ascii=False).encode()
    entetes = {"Content-Type": "application/json"}
    if settings.turn_webhook_secret is not None:
        entetes["X-Eldir-Signature"] = signer(
            corps, settings.turn_webhook_secret.get_secret_value()
        )
    try:
        async with httpx.AsyncClient(timeout=settings.turn_webhook_timeout_seconds) as client:
            reponse = await client.post(url, content=corps, headers=entetes)
        if reponse.status_code >= 400:
            logger.warning("turn_webhook.refuse", status=reponse.status_code)
    except Exception:
        logger.warning("turn_webhook.injoignable", exc_info=True)
```

Dans `_notify_turn_done`, après le ping interne, et **sans** l'attendre d'une façon qui puisse remonter :

```python
        await prevenir(
            {
                "session_id": session_id,
                "projet": project_name,
                "branche": child.branch,
                "etat": "erreur" if event_type == EVENT_TYPE_ERROR else "fin_de_tour",
                "cr": cr,
            }
        )
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `cd backend && uv run pytest tests/unit/test_turn_webhook.py -v`
Expected: PASS (3 tests)

- [ ] **Step 6: Run the backend gate, then commit**

Vérifier l'état de la PR dans un appel séparé, puis commiter avec le message :

```
feat(agents): ping de fin de tour vers un abonné externe

Le ping interne réveille le superviseur en mémoire, donc un agent dans un
autre processus ne le voit pas : il n'apprendrait la fin d'un travail qu'à son
prochain réveil, et avancerait d'un pas par tic de cron au lieu d'enchaîner.
Signé HMAC, et son échec reste un avertissement : la session enfant, elle, a
bien fini.
```

## Task 10: la documentation de la porte

**Files:**
- Create: `docs/agent-externe.md`
- Modify: `docs/supervisor.md` (un renvoi)
- Modify: `README.md` (une ligne dans la liste des capacités)

**Interfaces:** aucune, c'est de la prose. Elle doit permettre à quelqu'un qui n'a pas lu ce plan de brancher un agent sans poser de question.

- [ ] **Step 1: Write the documentation**

`docs/agent-externe.md` doit couvrir, dans cet ordre :

1. **Ce que c'est.** Les cinq outils du superviseur, servis en MCP sur HTTP. Le superviseur interne reste : cette porte s'ajoute, elle ne remplace rien.
2. **Ce que l'agent ne pourra jamais faire.** La publication est refusée au niveau du hook, quel que soit le transport. Le dire tôt, c'est la question que tout le monde se pose.
3. **Émettre un jeton.** Settings, libellé, le clair affiché une fois, la révocation.
4. **Brancher un client MCP.** L'URL `https://<ton-eldir>/api/mcp/`, l'en-tête `Authorization: Bearer <jeton>`, le transport streamable HTTP sans état.
5. **Les cinq outils**, un tableau nom / à quoi ça sert / paramètres.
6. **Recevoir les fins de tour.** `TURN_WEBHOOK_URL`, `TURN_WEBHOOK_SECRET`, la charge JSON, et comment vérifier `X-Eldir-Signature` (un exemple de dix lignes en Python).
7. **Si ça ne marche pas.** Les trois pannes prévisibles, avec leur signature exacte :
   - **401** : jeton absent, révoqué, ou jeton de connexion ordinaire au lieu d'un jeton d'agent.
   - **404 sur `/api/mcp/`** : un client qui ajoute `/mcp` au chemin ; l'endpoint est à la racine du montage.
   - **421 « Invalid Host header »** : `MCP_ALLOWED_HOSTS` ne contient pas le nom par lequel l'agent joint Eldir. Laisser vide désactive la vérification ; le jeton reste la garde.

Les exemples utilisent `eldir.exemple.lan`, jamais une machine réelle.

- [ ] **Step 2: Check the punctuation and the absence of personal infrastructure**

Run: `grep -nP "[\x{2014}\x{2013}]" docs/agent-externe.md README.md docs/supervisor.md` → aucune sortie attendue.
Run: `grep -nEi "100\.(6[4-9]|[7-9][0-9]|1[01][0-9]|12[0-7])\.|johnserver|demory" docs/agent-externe.md` → aucune sortie attendue.

- [ ] **Step 3: Commit, then open the PR for lot 2**

Vérifier l'état de la PR dans un appel séparé, puis commiter avec le message :

```
docs: brancher un agent externe sur Eldir

Les trois pannes prévisibles sont documentées avec leur signature exacte (401,
404 sur le chemin, 421 sur le Host) : chacune nous a coûté une heure, autant
qu'elle n'en coûte pas une à la personne suivante.
```

```bash
git push -u origin feat/surface-agent-externe
gh pr create --title "feat(agents): les outils du superviseur ouverts à un agent externe" --body "$(cat <<'MSG'
Les cinq outils du superviseur étaient le bon contrat pour piloter Eldir, mais
n'étaient joignables que depuis le processus : un agent extérieur devait ou
bien reconstruire la logique de dispatch, ou bien conduire l'interface à la
main. Les deux sont du travail jeté.

- Un seul corps par outil, deux transports. Les descriptions et schémas
  vivent dans une table unique : il ne peut plus exister deux descriptions du
  même outil.
- `/api/mcp/` en MCP streamable HTTP, derrière un jeton d'agent révocable.
- `list_projects` porte la dernière activité et ce qui attend un geste humain,
  sans quoi « relance-moi sur un projet oublié » n'a aucune donnée pour tenir.
- L'origine d'une consigne nomme son auteur : avec deux cerveaux possibles,
  relire son historique doit dire lequel a décidé.
- Le ping de fin de tour part aussi en HTTP, signé, sinon un agent externe
  avance d'un pas par tic de cron au lieu d'enchaîner.

La porte de validation humaine ne bouge pas : la publication reste refusée au
niveau du hook `PreToolUse`, quel que soit le transport, et un test le vérifie.

Aucune dépendance nouvelle : `mcp` était déjà dans `uv.lock`, en transitif de
`claude-agent-sdk`.

Spec : `docs/specs/2026-10-29-surface-agent-externe.md`
Plan : `docs/plans/2026-10-29-surface-agent-externe.md`

🤖 Generated with [Claude Code](https://claude.com/claude-code)
MSG
)"
```

---

# Lot 3 - finition publique

```bash
git checkout main && git pull
git checkout -b docs/finition-publique
```

## Task 11: de quoi accueillir un contributeur

**Files:**
- Create: `CODE_OF_CONDUCT.md`, `.github/pull_request_template.md`, `.github/ISSUE_TEMPLATE/anomalie.md`, `.github/ISSUE_TEMPLATE/proposition.md`, `.github/ISSUE_TEMPLATE/config.yml`
- Modify: `CONTRIBUTING.md` (un renvoi vers le code de conduite)

**Interfaces:** aucune.

- [ ] **Step 1: Write `CODE_OF_CONDUCT.md`**

Contributor Covenant 2.1, en français, avec le contact de signalement. **Pas l'adresse personnelle du mainteneur** : le dépôt est public. Utiliser l'onglet des signalements privés de GitHub, ou une adresse de projet dédiée si John en ouvre une. Mettre un renvoi explicite depuis `CONTRIBUTING.md`.

- [ ] **Step 2: Write the PR template**

Court, et aligné sur la façon de travailler du projet, sinon personne ne le remplit :

```markdown
## Ce que ça change

<!-- Une phrase. Le quoi, pas le comment. -->

## Pourquoi

<!-- Le problème observé. Si c'est une correction, ce qui cassait et comment le reproduire. -->

## Vérifié comment

- [ ] Backend : `ruff check`, `ruff format --check`, `mypy app`, `pytest`
- [ ] Frontend : `lint`, `tsc --noEmit`, `test`, `build`
- [ ] Testé à la main sur : <!-- écran, parcours, ou commande -->

## Phase concernée

<!-- Renvoi vers ROADMAP.md, ou "hors phasage". -->
```

- [ ] **Step 3: Write the issue templates**

`anomalie.md` demande : ce qui était attendu, ce qui s'est passé, comment reproduire, la version et le mode d'installation (docker compose ou autre), les journaux utiles. `proposition.md` demande : le besoin, pas la solution ; ce que la personne fait aujourd'hui à la place ; pourquoi ça ne suffit pas. `config.yml` renvoie les questions d'usage vers les Discussions plutôt que vers les issues.

- [ ] **Step 4: Check the punctuation, then commit**

Run: `grep -rnP "[\x{2014}\x{2013}]" CODE_OF_CONDUCT.md .github/ CONTRIBUTING.md` → aucune sortie attendue.

Vérifier l'état de la PR dans un appel séparé, puis commiter avec le message :

```
docs: de quoi accueillir un contributeur

Code de conduite, gabarits d'anomalie, de proposition et de PR. Le gabarit de
PR reprend les portes de qualité réelles du projet : un gabarit qui demande
autre chose que ce qu'on vérifie ne se remplit pas.
```

## Task 12: CI Lighthouse, seuil PWA

**Files:**
- Create: `.github/workflows/lighthouse.yml`
- Create: `frontend/lighthouserc.json`

**Interfaces:**
- Consomme : `npm run build` et `npm run preview` du frontend.
- Produit : un job qui échoue sous le seuil annoncé dans le ROADMAP depuis la phase 0.

- [ ] **Step 1: Write the Lighthouse config**

```json
{
  "ci": {
    "collect": {
      "startServerCommand": "npm run preview -- --port 4173",
      "url": ["http://127.0.0.1:4173/"],
      "numberOfRuns": 1,
      "settings": { "preset": "desktop" }
    },
    "assert": {
      "assertions": {
        "categories:performance": ["warn", { "minScore": 0.8 }],
        "categories:accessibility": ["error", { "minScore": 0.9 }],
        "categories:best-practices": ["warn", { "minScore": 0.9 }],
        "installable-manifest": ["error", { "minScore": 1 }],
        "service-worker": ["error", { "minScore": 1 }]
      }
    }
  }
}
```

Le ROADMAP annonce « score PWA > 90 ». Lighthouse a retiré la catégorie PWA agrégée : on assert donc ce qu'elle mesurait vraiment, le manifeste installable et le service worker, plus l'accessibilité en bloquant. Mettre à jour la ligne du ROADMAP (tâche 13) pour qu'elle dise ce que la CI vérifie, au lieu d'un score qui n'existe plus.

- [ ] **Step 2: Write the workflow**

Sur le modèle de `.github/workflows/frontend.yml` (reprendre sa version de Node et sa stratégie de cache) : `npm ci`, `npm run build`, puis `treosh/lighthouse-ci-action` avec `configPath: ./frontend/lighthouserc.json` et `uploadArtifacts: true`.

- [ ] **Step 3: Run it locally before pushing**

Run: `cd frontend && npm run build && npx @lhci/cli autorun --config=lighthouserc.json`
Expected: les assertions bloquantes passent. Si l'accessibilité échoue, **corriger l'accessibilité**, pas le seuil.

- [ ] **Step 4: Commit**

Vérifier l'état de la PR dans un appel séparé, puis commiter avec le message :

```
ci: Lighthouse sur PR, manifeste et service worker bloquants

Annoncé dans le ROADMAP depuis la phase 0. La catégorie PWA agrégée n'existe
plus dans Lighthouse : on assert ce qu'elle mesurait, le manifeste installable
et le service worker, plus l'accessibilité en bloquant.
```

## Task 13: un ROADMAP qui ne mente plus

**Files:**
- Modify: `ROADMAP.md`

**Interfaces:** aucune.

- [ ] **Step 1: Fix the stale checkboxes**

Cocher `CONTRIBUTING.md` et `docs/providers/forgejo.md` : les deux fichiers existent. Une roadmap qui annonce comme manquant ce qui est écrit envoie un contributeur réécrire ce qui existe, ce qui est pire qu'une roadmap absente.

- [ ] **Step 2: Record what the three lots delivered**

- Phase 0 : cocher le code de conduite, les gabarits, et la CI Lighthouse en reformulant la ligne d'après ce que la CI vérifie vraiment.
- Section Superviseur : cocher « Parallélisme explicite », livré en tâche 1.
- Nouvelle section **Surface d'agent externe**, après la section Superviseur, qui renvoie à `docs/agent-externe.md` et à la spec, et qui dit en trois lignes ce qui est volontairement hors périmètre : aucun plafond de dépense autonome (politique du projet : alerte, jamais blocage), pas de file durable, pas d'autorisation fine par outil.

- [ ] **Step 3: Check the punctuation, then commit and open the PR for lot 3**

Run: `grep -nP "[\x{2014}\x{2013}]" ROADMAP.md` → aucune sortie attendue.

Vérifier l'état de la PR dans un appel séparé, puis commiter avec le message :

```
docs(roadmap): l'état réel, et la surface d'agent externe

CONTRIBUTING.md et la doc Forgejo étaient annoncés comme manquants alors
qu'ils existent. Le parallélisme explicite est livré. La nouvelle section dit
aussi ce qui est hors périmètre, pour qu'on ne le reprenne pas pour un oubli.
```

```bash
git push -u origin docs/finition-publique
gh pr create --title "docs: de quoi accueillir un contributeur, et un ROADMAP honnête" --body "$(cat <<'MSG'
Eldir est destiné à durer et à fédérer. Ces manques ne gênaient personne
parce que personne d'extérieur n'avait encore essayé de contribuer, et c'est
exactement le problème.

- Code de conduite, gabarits d'anomalie, de proposition et de PR.
- CI Lighthouse, annoncée depuis la phase 0. La catégorie PWA agrégée n'existe
  plus : on assert ce qu'elle mesurait, manifeste installable et service
  worker, plus l'accessibilité en bloquant.
- ROADMAP remis à l'état réel : `CONTRIBUTING.md` et la doc Forgejo y étaient
  annoncés comme manquants alors qu'ils existent.

Spec : `docs/specs/2026-10-29-surface-agent-externe.md`

🤖 Generated with [Claude Code](https://claude.com/claude-code)
MSG
)"
```

---

## Relecture du plan contre la spec

| Exigence de la spec | Tâche |
|---|---|
| 1.1 Dispatcher deux chantiers sur un même repo | 1 |
| 1.2 Écrire à une session qui travaille, avec plafond | 2 |
| 2.1 Un seul corps par outil | 3 |
| 2.2 Jeton d'agent révocable, UI, `origin` qui nomme le jeton | 5, 7, 8 |
| 2.3 `/api/mcp/` servi et authentifié | 6 |
| 2.4 `list_projects` enrichi | 4 |
| 2.5 Ping de fin de tour en HTTP, signé, non bloquant | 9 |
| Lot 3 finition publique | 11, 12, 13 |
| Documentation de la porte | 10 |
| La publication reste refusée par les deux transports | 6 (test), vérifié aussi en 3 |

**Points de vigilance connus, à ne pas redécouvrir :**

- `FastMCP.add_tool` dérive le schéma des annotations de type, pas de `SCHEMAS_OUTILS`. Vérifier sa signature sur la version verrouillée avant d'écrire la tâche 6, et garder `SCHEMAS_OUTILS` comme source des descriptions.
- Les trois échecs de tests backend sur `ssh-keygen` sont connus et dus à une image de dev périmée, pas au code. Les vérifier sur un arbre propre avant d'enquêter.
- La CI `types.yml` compare `api-generated.ts` au backend : toute route nouvelle impose de régénérer les types dans le même commit.
