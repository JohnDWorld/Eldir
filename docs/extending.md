# Étendre Eldir

> Comment ajouter un provider Git, un preset de template, un type d'event, ou un endpoint sans casser l'archi.

## Ajouter un Git provider (GitLab, Gitea, Bitbucket…)

Eldir est provider-agnostic by design via `GitProviderInterface`. Pour ajouter un nouveau provider, tu implémentes le contrat et tu enregistres ton implémentation.

### 1. Implémenter `GitProviderInterface`

Crée `backend/app/services/git_providers/{nom}.py` :

```python
from app.services.git_providers.base import (
    GitProviderInterface, RepoRef, PullRequestRef,
)


class GitLabProvider(GitProviderInterface):
    name = "gitlab"

    def __init__(self, token: str, base_url: str | None = None) -> None:
        self._token = token
        self._base_url = (base_url or "https://gitlab.com").rstrip("/")

    async def list_repos(self) -> list[RepoRef]:
        ...  # GET /api/v4/projects?membership=true

    async def get_default_branch(self, full_name: str) -> str:
        ...

    async def clone_url_with_auth(self, full_name: str) -> str:
        return f"https://oauth2:{self._token}@gitlab.com/{full_name}.git"

    async def create_repo(self, name: str, *, private: bool, description: str | None) -> RepoRef:
        ...  # POST /api/v4/projects

    async def create_pr(
        self, *, full_name: str, head: str, base: str, title: str, body: str | None
    ) -> PullRequestRef:
        ...  # POST /api/v4/projects/.../merge_requests
```

### 2. Enregistrer dans la factory

Édite `backend/app/services/git_providers/__init__.py` :

```python
def make_provider(provider: str, token: str, base_url: str | None = None) -> GitProviderInterface:
    if provider == "github":
        return GitHubProvider(token=token)
    if provider == "forgejo":
        return ForgejoProvider(token=token, base_url=base_url)
    if provider == "gitlab":
        return GitLabProvider(token=token, base_url=base_url)
    raise UnsupportedProviderError(provider)
```

### 3. Mettre à jour la liste des providers supportés

`backend/app/core/constants.py` :

```python
PROVIDER_GITLAB: Final[str] = "gitlab"
SUPPORTED_PROVIDERS: Final[frozenset[str]] = frozenset(
    {PROVIDER_GITHUB, PROVIDER_FORGEJO, PROVIDER_GITLAB}
)
```

### 4. Côté frontend

Ajoute le provider à `frontend/src/lib/constants.ts` :

```ts
export const PROVIDERS = ['github', 'forgejo', 'gitlab'] as const;
export type Provider = (typeof PROVIDERS)[number];
```

Et un `GitMark` icon pour le provider dans `frontend/src/components/eldir/git-mark.tsx`.

### 5. Documenter

Crée `docs/providers/{nom}.md` sur le modèle de `docs/providers/forgejo.md`.

Ouvre une PR — pas besoin de migration DB, tout est déjà pluggable.

## Ajouter un preset de Mission Template

Phase 4 t'a fourni un loader automatique pour les presets — pas de code à toucher.

### 1. Créer le JSON

Dépose un fichier dans `backend/app/data/template_presets/{slug}.json` :

```json
{
  "slug": "django-rest",
  "title": "Django + DRF",
  "description": "Projet Django REST Framework standard.",
  "tags": ["python", "django", "rest"],
  "model": "claude-sonnet-4-6",
  "allowed_tools": null,
  "system_prompt": "Tu es l'agent maintainer d'un projet Django + DRF...\n\n## Conventions\n- ...",
  "skills": [
    {
      "name": "run-tests",
      "description": "Lance les tests Django.",
      "content": "# run-tests\n\n```bash\npython manage.py test\n```"
    }
  ],
  "sub_agents": [
    {
      "name": "migration-keeper",
      "description": "Vérifie cohérence des migrations Django.",
      "system_prompt": "Tu es responsable...",
      "allowed_tools": ["Bash", "Read", "Grep", "Glob"]
    }
  ]
}
```

### 2. Redémarrer le backend

```bash
docker compose -f docker-compose.dev.yml restart backend
```

Le `TemplatePresetService` charge tous les `*.json` du dossier au boot.

### 3. Tester

Va dans **Projects > [un projet] > Template > Apply preset** → ton preset apparaît dans la liste.

### Règles pour les presets uploadés à la communauté

- `slug` filesystem-safe : `[a-zA-Z0-9_-]+`
- `system_prompt` rédigé en français (cohérent avec le reste du projet)
- Préfère des skills atomiques (1 commande / 1 contexte) plutôt que des skills fourre-tout
- Documente toujours **pourquoi** dans le system prompt, pas juste **quoi**
- Pas de credentials, tokens, URLs internes dans le JSON

PR avec ton preset dans `backend/app/data/template_presets/` accueillie avec joie.

## Ajouter un type d'event SDK

Tu veux capturer un nouvel event du Claude Agent SDK (par exemple `SubagentStart`) qu'on n'écoute pas encore ?

### 1. Constante

`backend/app/core/constants.py` :

```python
EVENT_TYPE_SUBAGENT_START: Final[str] = "subagent_start"
```

### 2. Capture dans `SessionManager`

`backend/app/services/session_manager.py`, dans `_consume_response` ou via un nouveau hook :

```python
async def _subagent_start_hook(input_data, tool_use_id, _context):
    await self._publish(
        session_id,
        EVENT_TYPE_SUBAGENT_START,
        {"name": input_data.get("subagent_name"), ...},
    )
    return {}

options_kwargs["hooks"]["SubagentStart"] = [HookMatcher(hooks=[_subagent_start_hook])]
```

### 3. Côté schemas

`backend/app/schemas/session.py` :

```python
SessionEventType = Literal[..., "subagent_start"]
```

### 4. Côté frontend

`frontend/src/lib/types/api.ts` :

```ts
export type SessionEventType = ... | 'subagent_start';
```

Puis affiche-le dans `session-page.tsx` (`ChatStream` ou `LogLine`) selon ton intention.

### 5. Persistance

Aucune action — `SessionService._persist_event` enregistre tous les events publiés. Si tu veux un traitement spécial (comme `usage` qui crée une ligne `session_costs`), ajoute un `if event_type == EVENT_TYPE_SUBAGENT_START: ...` dans la callback.

## Ajouter un endpoint API

1. Crée un module dans `backend/app/api/v1/{nom}.py` avec un `APIRouter`.
2. Délègue à un service dans `backend/app/services/` — **jamais** de logique métier dans les routes.
3. Schemas Pydantic dans `backend/app/schemas/{nom}.py`.
4. Inclus le router dans `backend/app/api/v1/__init__.py` :

```python
from app.api.v1.{nom} import router as {nom}_router
api_router.include_router({nom}_router)
```

5. Côté frontend, ajoute la queryKey + le hook dans `frontend/src/lib/api/queries.ts`. Pas de `fetch()` direct dans les composants — toujours via `apiClient`.

6. Ajoute les types TS via `./scripts/gen-types.sh` (depuis Pydantic) plutôt que de les écrire à la main.

## Ajouter une migration DB

```bash
docker exec eldir-backend uv run alembic revision --autogenerate -m "description courte"
```

⚠️ **Toujours relire** le fichier généré dans `backend/alembic/versions/{NNNN}_*.py`. Alembic autogenerate rate parfois :

- Les renames (vu comme drop + add)
- Les contraintes complexes
- Les data migrations

Applique :

```bash
docker exec eldir-backend uv run alembic upgrade head
```

(Auto au démarrage du container backend en dev.)

## Voir aussi

- [`AGENTS.md`](../AGENTS.md) — conventions strictes pour les contributeurs
- [`CONTRIBUTING.md`](../CONTRIBUTING.md) — workflow PR
- [`architecture.md`](./architecture.md) — vue d'ensemble pour comprendre où ton code s'insère
