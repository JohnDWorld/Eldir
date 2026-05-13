# Eldir — Frontend

React 18 + Vite + TypeScript strict + Tailwind + shadcn/ui (hybride) + PWA. DA portée depuis [`../DA/d1.jsx`](../DA/d1.jsx) — Direction 1 · Mission Control.

Voir [`AGENTS.md`](../AGENTS.md), [`CLAUDE.md`](../CLAUDE.md), [`ROADMAP.md`](../ROADMAP.md) à la racine.

## Démarrage (Docker — pas de pnpm local requis)

```bash
# Build de l'image dev (cible `dev` du Dockerfile multi-stage)
docker build --target dev -t eldir-frontend:dev frontend/
docker run --rm -p 5173:5173 -v "$PWD/frontend:/app" -v /app/node_modules eldir-frontend:dev
```

Avec le `docker-compose.dev.yml` (à venir Phase 0), tout est branché en une commande :

```bash
docker compose -f docker-compose.dev.yml up
```

## Démarrage (local — si pnpm dispo)

```bash
cp .env.example .env.local
pnpm install
pnpm dev
```

## Qualité (avant commit)

```bash
pnpm lint
pnpm typecheck
pnpm test
pnpm build       # build PWA — score Lighthouse > 90 obligatoire
```

## Structure

```
src/
├── components/
│   └── ui/              # shadcn primitives (à ajouter via `pnpm dlx shadcn@latest add ...`)
├── features/            # modules par feature (sessions, projects, auth)
├── hooks/               # hooks React custom réutilisables
├── lib/
│   ├── api/             # client API centralisé + queries TanStack
│   ├── types/           # types miroir backend (Phase 0 — généré ensuite)
│   ├── validation/      # schémas Zod
│   ├── store/           # Zustand stores
│   ├── constants.ts
│   └── utils.ts         # cn() shadcn
├── pages/               # routes
├── pwa/                 # registerSW
├── styles/              # globals.css + tokens.css
├── app.tsx
└── main.tsx
```

## Tokens

Source de vérité : [`../DA/tokens.css`](../DA/tokens.css). Les valeurs hex
sont reportées en HSL dans [`src/styles/tokens.css`](src/styles/tokens.css)
pour compat alpha-value Tailwind.

Couleurs Eldir : `bg-eldir-paper`, `text-eldir-ink`, `border-eldir-gray-3`,
`bg-eldir-orange`, etc. Palette complète dans [`tailwind.config.ts`](tailwind.config.ts).

## Phase actuelle

Phase 0 — fondations posées. La D1 Mission Control desktop sera portée à
l'étape suivante (composants `Tile`, `StatePill`, `ToolRow`, `DiffViewer`,
`LogsPanel`, layout `260px | 1fr | 320px`).
