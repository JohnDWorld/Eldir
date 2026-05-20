# CLAUDE.md - Eldir

> Ce fichier contient les détails approfondis spécifiques à **Claude Code** sur le projet Eldir.
>
> **À lire en complément** :
> - `AGENTS.md` - règles standards pour tous les agents IA (commandes, conventions, anti-patterns)
> - `ROADMAP.md` - vision globale, phasage, décisions architecturales
> - `README.md` - présentation du projet (humains)

Si une info est dans `AGENTS.md`, je ne la duplique pas ici. Ce fichier ajoute uniquement ce qui est utile à Claude Code spécifiquement ou ce qui mérite plus de détails.

---

## 🎯 Contexte projet (ce que les autres agents ne lisent pas)

**Maintainer principal** : John, auto-entrepreneur basé à Lorient, opère "La Boutique à Automatisations". Stack habituelle : n8n, Django, React/Tailwind, Supabase, Docker. Philosophie anti-vendor-lock-in et souveraineté numérique.

**Slogan du projet** : *"On t'as promis une usine à gaz alors que tu n'avais besoin que d'un bouton qui fonctionne"*

Eldir est un projet open-source destiné à durer et à fédérer une communauté. Chaque ligne de code doit être maintenable par quelqu'un d'autre que son auteur dans 6 mois.

---

## 🏗️ Architecture haut niveau

```
┌─────────────────────────────────────────────┐
│  Frontend (React + Vite + TypeScript + PWA) │
│  - Dashboard mobile-first installable       │
│  - Tabs sessions actives                    │
│  - Chat par session + diff viewer           │
│  - Couleurs Claude (orange/crème/noir)      │
└──────────────┬──────────────────────────────┘
               │ REST + WebSocket
┌──────────────▼──────────────────────────────┐
│  Backend (FastAPI + Python 3.12+)           │
│  - SessionManager (orchestre les agents)    │
│  - GitProviderInterface (GitHub|Forgejo)    │
│  - WorktreeService (isole les repos)        │
│  - WebSocketManager (streaming temps réel)  │
└──────────────┬──────────────────────────────┘
               │
       ┌───────┴────────┐
       ▼                ▼
  Claude Agent SDK   PostgreSQL + Redis
  (1 instance/session)
```

---

## 📂 Structure du repo

```
eldir/
├── backend/                  # FastAPI + Claude Agent SDK
│   ├── app/
│   │   ├── api/              # Routes REST (FINES, déléguer aux services)
│   │   ├── ws/               # WebSocket handlers
│   │   ├── core/             # Config, sécurité, deps, constants, exceptions
│   │   ├── db/               # Modèles SQLAlchemy + migrations Alembic
│   │   ├── services/         # Logique métier (SessionManager, GitProviders…)
│   │   ├── schemas/          # Pydantic models (source de vérité des types)
│   │   └── main.py
│   ├── tests/
│   ├── alembic/
│   ├── pyproject.toml
│   └── Dockerfile
├── frontend/                 # React + Vite + PWA
│   ├── public/
│   │   ├── icons/            # Icônes PWA (192, 512, maskable)
│   │   └── manifest.webmanifest
│   ├── src/
│   │   ├── components/       # Composants UI réutilisables (shadcn/ui + custom)
│   │   ├── features/         # Modules par feature (sessions, projects…)
│   │   ├── hooks/            # Hooks React custom réutilisables
│   │   ├── lib/
│   │   │   ├── api/          # Client API centralisé
│   │   │   ├── types/        # Types TS (générés depuis backend)
│   │   │   ├── constants.ts
│   │   │   └── validation/   # Schémas Zod
│   │   ├── pages/            # Routes
│   │   ├── styles/           # Tailwind config + thème Claude
│   │   └── pwa/              # Service worker custom, hooks PWA
│   ├── vite.config.ts        # Config Vite + vite-plugin-pwa
│   ├── package.json
│   └── Dockerfile
├── shared/                   # Types et constantes partagés backend ↔ frontend
│   └── README.md             # Pipeline de génération des types
├── docs/
├── docker/
├── scripts/
├── docker-compose.yml
├── docker-compose.dev.yml
├── ROADMAP.md
├── AGENTS.md                 # Standards pour tous les agents IA
├── CLAUDE.md                 # Ce fichier
├── README.md
├── CONTRIBUTING.md
├── LICENSE                   # AGPL v3
└── .github/
```

---

## 🎨 Design system détaillé

**Palette** :
```css
--eldir-orange: #D97757;     /* Action principale, accent */
--eldir-cream: #F4F1EA;      /* Fond clair */
--eldir-black: #1A1A1A;      /* Texte principal */
--eldir-gray: #8B8680;       /* Texte secondaire */
--eldir-gold: #C9A87C;       /* Accent doré, highlights */
```

**Typo** :
- UI : `Inter`
- Code : `JetBrains Mono`

**Esprit** : minimaliste, chaleureux, terreux. Pas de néon ni gradient SaaS générique. Inspiration : la palette de Claude/Anthropic, l'aesthetic naturel et terreux.

**Composants** : utiliser **shadcn/ui** par défaut. Customiser le theme dans `tailwind.config.ts` pour matcher la palette. Tout composant utilisé 2+ fois doit vivre dans `components/`.

**États visuels d'une session** :
- `idle` : gris subtil
- `thinking` : pulse orange
- `tool_use` : bordure orange animée
- `waiting_input` : badge gold qui clignote
- `blocked` : bordure rouge

---

## 🔧 Workflow de développement

### Pour démarrer une nouvelle feature

1. Lire la phase concernée dans `ROADMAP.md`
2. Créer une branche `feature/[slug-explicite]`
3. Si la feature touche le backend ET le frontend, commencer par le backend (API + tests)
4. Écrire les tests AVANT l'implémentation quand c'est raisonnable
5. Mettre à jour la doc dans `docs/` au fur et à mesure
6. PR avec description détaillée, lien vers la phase concernée
7. Merge en `main` après CI verte

### Tests obligatoires

- **Backend** : tests unitaires sur les services, tests d'intégration sur les routes
- **Frontend** : tests sur les hooks custom et les composants critiques (Vitest + Testing Library)
- **Coverage minimum** : 70% sur le backend, 50% sur le frontend (V1)

### Décomposition des tâches

Pour toute feature non-triviale, décomposer en :
1. Migration DB (si applicable)
2. Schémas Pydantic + génération types TS
3. Service métier + tests unitaires
4. Route API + tests d'intégration
5. Hook frontend + tests
6. Composants UI (mobile-first)
7. Tests E2E si critique
8. Documentation

---

## 🧠 Patterns spécifiques au Claude Agent SDK

### Création d'une session

```python
from claude_agent_sdk import ClaudeSDKClient, ClaudeAgentOptions

async def create_session(repo_path: str, system_prompt: str) -> ClaudeSDKClient:
    options = ClaudeAgentOptions(
        cwd=repo_path,
        system_prompt=system_prompt,
        # Le session_id sera capturé au premier message
    )
    client = ClaudeSDKClient(options)
    await client.connect()
    return client
```

### Reprise d'une session existante

```python
options = ClaudeAgentOptions(
    cwd=repo_path,
    resume=stored_session_id,  # Récupéré depuis Postgres
)
```

### Hooks pour pubsub Redis

Tous les hooks SDK doivent émettre vers Redis sur le channel `session:{session_id}` au format JSON :

```python
{
    "type": "tool_use" | "tool_result" | "text" | "stop" | "error",
    "session_id": "...",
    "timestamp": "...",
    "data": { ... }
}
```

Le frontend s'abonne via WebSocket et relaie les events à l'UI.

### Forks de conversation (V2)

Le SDK supporte le fork de session : à partir d'un point donné, créer une branche conversationnelle. À utiliser pour permettre à l'utilisateur d'explorer des alternatives sans perdre l'original.

---

## 📚 Ressources

- **Standards agents** : `AGENTS.md` (commandes, conventions, anti-patterns)
- **Vision et roadmap** : `ROADMAP.md`
- **Doc Claude Agent SDK** : https://docs.claude.com/en/agent-sdk/overview
- **Doc Forgejo API** : https://forgejo.org/docs/latest/user/api-usage/
- **Doc GitHub API** : https://docs.github.com/en/rest
- **Doc vite-plugin-pwa** : https://vite-pwa-org.netlify.app/

---

## 🆘 Règle d'or

Si une décision n'est pas claire :

1. Vérifier `AGENTS.md` pour les conventions strictes
2. Vérifier `ROADMAP.md` pour la vision et le phasage
3. **Si toujours pas clair, demander à John avant d'agir** - jamais inventer

Eldir est un projet qui doit durer. Chaque choix technique doit être justifiable dans 1 an, 2 ans, 5 ans.
