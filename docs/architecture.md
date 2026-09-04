# Architecture d'Eldir

> Vue technique pour développeurs voulant comprendre, modifier ou étendre Eldir.

## Vue d'ensemble

```
┌────────────────────────────────────────────────────────────┐
│  Frontend (React + Vite + PWA)                             │
│  - Pages : OpsHome, Projects, ProjectTemplate, Session,    │
│    Costs, Settings (Claude/Git)                            │
│  - State : TanStack Query (server) + Zustand (client)      │
│  - WS client pour le stream de chaque session              │
└──────────────┬─────────────────────────────────────────────┘
               │ REST /api/v1/* + WS /ws/sessions/{id}
┌──────────────▼─────────────────────────────────────────────┐
│  Backend (FastAPI async)                                   │
│                                                            │
│  ┌─ Routes (api/v1/) ─────────────────────────────────┐    │
│  │  auth · projects · sessions · costs · settings ·   │    │
│  │  providers · mission_templates · setup             │    │
│  └─────────────┬──────────────────────────────────────┘    │
│                │ (routes fines, déléguent aux services)    │
│  ┌─ Services (services/) ──────────────────────────────┐   │
│  │  SessionManager · SessionService · CostService ·    │   │
│  │  SupervisorService · RepoWatcher ·                  │   │
│  │  WorktreeService · GitProviderInterface ·           │   │
│  │  MissionTemplateService · TemplatePresetService ·   │   │
│  │  ClaudeCredentialService · GitCredentialService     │   │
│  └─────────────┬──────────────────────────────────────┘    │
│                │                                            │
│       ┌────────┴────────┐                                  │
│       ▼                 ▼                                  │
│  Claude Agent SDK   PostgreSQL + Redis                     │
│  (1 ClaudeSDKClient (sessions, events, templates,         │
│  par session active) costs, credentials chiffrés)         │
└────────────────────────────────────────────────────────────┘
```

## Stack figée

Cf. [`AGENTS.md`](../AGENTS.md) pour le détail. Résumé :

| Couche | Techno | Pourquoi |
|---|---|---|
| Backend | FastAPI + Python 3.12 | Async natif, WS robuste |
| Agent | `claude-agent-sdk` (Python) | Officiel Anthropic, sessions persistantes |
| DB | PostgreSQL 16 | Sessions, projects, templates, costs |
| Pub/Sub | Redis 7 | Stream live des events SDK vers le WS |
| Frontend | React 18 + Vite + TS strict | Standard 2026 |
| UI | Tailwind + shadcn/ui | Design system cohérent |
| Server state | TanStack Query | Cache + invalidations |
| Auth user | JWT (mono-user V1) | Simple, suffit en mono-user |
| Auth Claude | OAuth Pro/Max OU API key | Choix utilisateur, Fernet en DB |
| Auth Git | OAuth GitHub OU PAT | Fernet en DB |
| Worktrees | `git worktree` | N sessions sur même repo |
| Deploy | Docker Compose | Standard self-host |

## Modèle de données

```
┌─────────────┐         ┌──────────────────┐
│ users       │◄────────┤ sessions          │
└──┬──────────┘         │ (project, branch, │
   │                    │  worktree_path,   │
   │                    │  state, sdk_id)   │
   │                    └──┬───────────┬────┘
   │                       │           │
   │                       │           ▼
   │                       │    ┌──────────────────┐
   │                       │    │ session_events  │
   │                       │    │ (type, payload) │
   │                       │    └──────────────────┘
   │                       │
   │                       ▼
   │                ┌──────────────────┐
   │                │ session_costs   │  ← Phase 5
   │                │ (1 ligne / tour)│
   │                │ project_id,     │
   │                │ user_id, model, │
   │                │ tokens, cost   │
   │                └──────────────────┘
   │
   ▼
┌─────────────┐    ┌──────────────────┐
│ projects    │◄───┤ mission_templates│   1↔1
└──────┬──────┘    │ (system_prompt,  │
       │           │  model, tools)   │
       │           └──┬───────────────┘
       │              │
       │              ├─► template_skills    (*)
       │              ├─► template_sub_agents (*)
       │              └─► template_versions   (snapshots JSON, rollback)
       │
       ▼
┌──────────────────┐    ┌──────────────────┐
│ git_credentials  │    │ claude_credentials│
│ (Fernet)         │    │ (Fernet)          │
└──────────────────┘    └──────────────────┘
```

Migrations Alembic : `backend/alembic/versions/`
- `0001_initial_schema.py` — base Phase 0-3
- `0002_mission_templates.py` — Phase 4
- `0003_session_costs_per_turn.py` — Phase 5
- `0004_system_prompt_overrides.py` — prompts système éditables
- `0005_sessions_is_system.py` — sessions internes Eldir
- `0006_ollama_settings.py` — Phase 6
- `0007_sessions_nullable_project.py` — session superviseur (sans repo)

Le superviseur et le protocole `<cr>` sont détaillés dans [`supervisor.md`](./supervisor.md).

## Le flow complet d'un message utilisateur

```
[UI session-page.tsx]
   │ user tape "ajoute un endpoint /foo" + Enter
   ▼
[POST /api/v1/sessions/:id/messages] (sessions.py route)
   │
   ▼
[SessionService.send_message()] (services/session_service.py)
   │
   ▼
[SessionManager.send_message()] (services/session_manager.py)
   │
   ├─► publish EVENT_TYPE_USER_MESSAGE   ─┐
   ├─► publish EVENT_TYPE_STATE=thinking ─┤
   │                                       │
   ▼                                       ▼
[ClaudeSDKClient.query(content)]   [EventBus → Redis pub session:{id}]
   │                                       │
   ▼                                       ▼
[receive_response() loop]          [WS handler /ws/sessions/{id}]
   │                                       │
   │ pour chaque message reçu :            ▼
   ├── AssistantMessage(TextBlock)  ─► publish text     ─► UI ChatStream
   ├── AssistantMessage(ToolUseBlock) ─► publish state=tool_use
   │   (hook PreToolUse)            ─► publish tool_use ─► UI ToolRow
   │   (hook PostToolUse)           ─► publish tool_result
   ├── SystemMessage(init)          ─► capture sdk_session_id, persist DB
   └── ResultMessage                ─► publish usage (cost, tokens) ─► persist SessionCost
                                    ─► publish stop  ─► UI "TOUR TERMINÉ"
                                    ─► state=idle
```

Tous les events publiés sont à la fois :
1. Diffusés en temps réel via WS (pub/sub Redis)
2. Persistés en DB dans `session_events` via `_persist_event()` (callback enregistré par `SessionService`)

Cela permet de **recharger l'historique** d'une session même après reboot d'Eldir.

## Worktrees & isolation

Chaque session a son propre git worktree pour éviter les conflits entre sessions parallèles sur le même repo.

```
/var/eldir/workspaces/
└── {user_id}/
    └── {repo_slug}/                ← clone "principal" (default_branch)
        └── .git/
            └── worktrees/
                ├── {repo_slug}.{session_id_1}/   ← worktree branche claude/{session_1}
                └── {repo_slug}.{session_id_2}/   ← worktree branche claude/{session_2}
```

Côté disque, ces worktrees sont à `/var/eldir/workspaces/{user_id}/{repo_slug}.{session_id}/` — montés en volume dans le container backend.

Chaque session démarre :
1. `git fetch origin` (best-effort)
2. `git worktree add {path} -b claude/{session_id} origin/{default_branch}`
3. Matérialise le template du projet (skills `.claude/skills/{name}/SKILL.md`, sub-agents `.claude/agents/{name}.md`)
4. Démarre `ClaudeSDKClient(cwd={worktree_path})`

## Conteneurisation

```yaml
# docker-compose.dev.yml
services:
  postgres: # 16-alpine
  redis:    # 7-alpine
  backend:  # build local, user 1000:1000, monte /var/eldir et le code
  frontend: # node:20 + vite dev server
```

Le backend tourne en **non-root** (UID 1000) parce que le CLI Claude Code refuse `--dangerously-skip-permissions` en root pour des raisons de sécurité. Le Dockerfile crée un user `eldir` et chown les dossiers nécessaires.

`alembic upgrade head` tourne au démarrage du container backend, donc les migrations sont appliquées automatiquement.

## Communication Redis ↔ WebSocket

```
[SessionManager._publish()]
   │
   ▼
[EventBus.publish(channel, event)]  ─► PUBLISH session:{session_id} {...}
                                            │
                                            ▼
[WS handler ws/sessions.py]         ─► SUBSCRIBE session:{session_id}
                                            │
                                            ▼
[websocket.send_json(event)]        ─► UI useSessionStream hook
```

Channel naming : voir `app/core/constants.py` → `REDIS_SESSION_CHANNEL_TEMPLATE`.

## Sécurité

- **Mots de passe utilisateur** : bcrypt
- **Credentials Claude / Git** : chiffrés Fernet avec `ENCRYPTION_KEY` (variable env, à régénérer en prod)
- **JWT** : signé avec `JWT_SECRET`, à régénérer en prod
- **OAuth state** : stocké en Redis avec TTL 600s, anti-CSRF
- **Pas de secret loggé** : tokens masqués (`masked_token`, `masked_value` côté schemas)
- **Tools Claude** : `permission_mode=bypassPermissions` (pas de TTY côté serveur) — sécurité = worktree isolé + stream des `tool_use` visibles à l'utilisateur

## Points d'extension

| Je veux ajouter… | Voir |
|---|---|
| Un Git provider (GitLab, Gitea, Bitbucket) | [`docs/extending.md`](./extending.md) |
| Un preset de Mission Template (Django, n8n, …) | [`docs/templates.md#presets`](./templates.md) |
| Un skill ou sub-agent à un projet existant | UI `/projects/:id/template` |
| Un nouveau type d'event SDK | `core/constants.py` + `SessionManager._consume_response` + `SessionService._persist_event` |
| Une migration DB | `docker exec eldir-backend uv run alembic revision --autogenerate -m "…"` |

## Tests

```bash
# Backend
docker exec eldir-backend uv run pytest -x --cov=app

# Frontend
cd frontend && npm test -- --run
cd frontend && npx tsc --noEmit -p tsconfig.app.json
```

Coverage cible V1 : 70% backend, 50% frontend.

## Pour aller plus loin

- [`docs/sessions.md`](./sessions.md) — détail du cycle de vie d'une session
- [`docs/templates.md`](./templates.md) — Mission Templates, skills, sub-agents, presets
- [`docs/costs.md`](./costs.md) — dashboard de coûts, prompt caching, mode économe
- [`docs/git-workflow.md`](./git-workflow.md) — commit/push/PR depuis Eldir
- [`docs/extending.md`](./extending.md) — comment étendre Eldir
- [`docs/github.md`](./github.md) — connecter GitHub
- [`docs/providers/forgejo.md`](./providers/forgejo.md) — connecter Forgejo
