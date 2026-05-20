# AGENTS.md

Instructions pour les agents IA travaillant sur Eldir (Claude Code, Cursor, Copilot, Codex, Devin…).

> Ce fichier suit le standard [agents.md](https://agents.md/). Pour les humains, voir `README.md`. Pour la vision et le phasage, voir `ROADMAP.md`.

## Project overview

Eldir est un dashboard web open-source self-hosted pour orchestrer plusieurs sessions Claude Code en parallèle sur différents repos Git (GitHub et Forgejo). Mono-utilisateur en V1, multi-utilisateurs en V2.

## Setup commands

```bash
# Backend
cd backend
uv sync                       # Install deps
uv run alembic upgrade head   # Run DB migrations
uv run uvicorn app.main:app --reload --port 8000

# Frontend
cd frontend
pnpm install
pnpm dev                      # Dev server on :5173

# Full stack via Docker
docker compose -f docker-compose.dev.yml up
```

## Quality commands (run before commit)

```bash
# Backend
cd backend
uv run ruff check --fix
uv run ruff format
uv run mypy app
uv run pytest

# Frontend
cd frontend
pnpm lint
pnpm typecheck
pnpm test
pnpm build                    # Vérifie que la build PWA passe
```

## Stack - versions imposées

- **Python 3.12+** (types modernes : `list[str]`, jamais `List[str]`)
- **FastAPI** (async exclusif, jamais de routes sync)
- **SQLAlchemy 2.0+** style async, **Alembic** pour migrations
- **Pydantic v2** pour les schemas
- **Claude Agent SDK Python** pour les sessions Claude (jamais le CLI en subprocess)
- **uv** package manager (jamais pip)
- **React 18 + TypeScript strict mode** (jamais `any` sans justification commentée)
- **Vite + vite-plugin-pwa** (PWA dès la Phase 0)
- **Tailwind CSS + shadcn/ui**
- **TanStack Query** pour le server state, **Zustand** pour le client state
- **Zod** pour validation runtime
- **pnpm** package manager (jamais npm)
- **PostgreSQL 16 + Redis 7**

## Code style - règles strictes

### Python
- Formatage : `ruff format`. Linting : `ruff check`. Types : `mypy --strict`.
- Docstrings style Google sur toutes les fonctions publiques.
- Pas de `print()` en code de prod, utiliser `logger`.
- Toute exception métier hérite de `EldirError` (`core/exceptions.py`).
- Logique métier dans `services/`, jamais dans les routes.
- Constantes dans `core/constants.py`, jamais hardcodées.
- Configuration via Pydantic Settings dans `core/config.py`, jamais de `os.getenv()` éparpillés.

### TypeScript
- Function components uniquement, jamais de class components.
- Naming : `PascalCase` pour composants, `camelCase` pour le reste, `kebab-case.tsx` pour les fichiers.
- Pas de `useEffect` pour fetch - utiliser TanStack Query.
- Pas de `fetch()` direct dans les composants - passer par le client API centralisé dans `lib/api/`.
- Pas de CSS inline ni fichiers `.css` - Tailwind exclusivement.
- Types partagés avec le backend : générés depuis Pydantic, jamais redéfinis à la main.

### Git
- Conventional Commits obligatoire : `feat(scope): description`, `fix(scope): …`, `docs(scope): …`, etc.
- Branches : `feature/[slug]`, `fix/[slug]`, `docs/[slug]`.
- PR obligatoire même en solo. Pas de force push sur `main`.

## Trois règles non-négociables

### 1. Mobile-first
Toute UI conçue pour 375×667px d'abord, adaptée pour tablette/desktop ensuite. Tap targets ≥ 44×44px. Pas d'interactions hover-only. Tester en DevTools mobile avant chaque merge.

```tsx
// ✅ Bon : mobile-first
<div className="flex flex-col gap-4 p-4 md:flex-row md:gap-6 md:p-8">

// ❌ Mauvais : desktop-first
<div className="flex flex-row gap-6 p-8 sm:flex-col sm:gap-4 sm:p-4">
```

### 2. PWA
Eldir est installable. Score Lighthouse PWA > 90 obligatoire. Mode hors-ligne géré élégamment (jamais de crash réseau down). Manifest, Service Worker, splash screen aux couleurs Claude - tout configuré dès la Phase 0 via `vite-plugin-pwa`.

### 3. DRY strict
Aucune duplication tolérée. **Règle des 3** : à la 3ème duplication, factorisation OBLIGATOIRE. Composant UI dupliqué → composant réutilisable. Logique stateful dupliquée → hook custom. Validation dupliquée → schéma Zod/Pydantic réutilisable. Type TS dupliqué → générer depuis le backend.

## Architecture - règles spécifiques au domaine

### Sessions Claude
- **Une session = un `ClaudeSDKClient`** instancié par `SessionManager`.
- Le `session_id` est capturé au premier message et stocké en DB.
- Reprise : `ClaudeAgentOptions(resume=session_id)`.
- Hooks SDK (`PreToolUse`, `PostToolUse`, `Stop`, `SessionStart`, `SessionEnd`) émettent des events Redis pubsub.
- Frontend s'abonne via WebSocket au channel `session:{session_id}`.

### Workspaces
- Stockés dans `/var/eldir/workspaces/{user_id}/{repo_slug}/`.
- Sessions multiples sur même repo via **git worktrees** : `{repo_slug}.{session_id}/`.
- Une session = une branche `claude/{session_id}-{slug}`.

### Git Providers
- Toute interaction passe par `GitProviderInterface`. Jamais de couplage à GitHub spécifiquement.
- Méthodes : `list_repos`, `clone_repo`, `create_repo`, `create_pr`, `get_branches`, `get_default_branch`.
- Implémentations V1 : `GitHubProvider`, `ForgejoProvider`.
- Credentials chiffrés en DB.

### Tokens
- **Toujours alerter, jamais bloquer** quand un budget est dépassé.
- Prompt caching activé par défaut sur les system prompts longs.
- OpenTelemetry du SDK pour tracker les coûts dans `session_costs`.

## Anti-patterns à proscrire

- ❌ Spawner Claude Code en subprocess (utiliser le SDK Python directement)
- ❌ Parser de l'output texte de Claude Code (le SDK fournit des objets typés)
- ❌ Utiliser `tmux` pour gérer les sessions (le SDK gère ça nativement)
- ❌ Bloquer l'utilisateur (budget, action…) - toujours alerter, laisser le contrôle
- ❌ Stocker des secrets en clair en DB (chiffrement obligatoire)
- ❌ Coupler le code à GitHub spécifiquement (passer par `GitProviderInterface`)
- ❌ CSS inline ou fichiers `.css` (Tailwind exclusivement)
- ❌ `useEffect` pour fetch (TanStack Query)
- ❌ `npm`/`pip` (utiliser `pnpm`/`uv`)
- ❌ UI desktop-first (toujours mobile-first)
- ❌ Hover-only interactions (inutilisable sur mobile)
- ❌ Dupliquer 3+ fois un même pattern sans factoriser
- ❌ Définir un type TS manuellement quand il existe côté backend (utiliser les types générés)
- ❌ Casser le mode hors-ligne PWA

## En cas de doute

Si une décision n'est pas couverte par ce fichier, par `CLAUDE.md` (détails additionnels), ou par `ROADMAP.md` (vision et phasage) : **demander à John avant d'agir**, ne pas inventer.

Privilégier toujours la **simplicité**, l'**alignement avec la stack imposée**, et le **respect des principes directeurs** (self-hosted first, l'utilisateur reste maître, mobile-first, PWA, DRY).
