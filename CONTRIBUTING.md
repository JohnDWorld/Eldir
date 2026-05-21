# Contribuer à Eldir

Merci de t'intéresser à Eldir. Ce projet est destiné à durer et à fédérer une communauté autour de la souveraineté numérique des devs.

## Avant de coder

1. **Lis [`AGENTS.md`](./AGENTS.md)** — conventions strictes (DRY, types partagés, anti-patterns, commandes).
2. **Lis [`CLAUDE.md`](./CLAUDE.md)** — détails Claude Agent SDK + design system.
3. **Lis [`ROADMAP.md`](./ROADMAP.md)** — phase actuelle, dette résiduelle, décisions actées.
4. **Identifie ta phase** — pas d'anticipation sans valider avec John dans une issue.

Si une décision n'est pas claire dans ces 3 fichiers : ouvre une issue, ne devine pas.

## Setup local

Voir [`docs/installation.md`](./docs/installation.md). Résumé :

```bash
git clone https://github.com/JohnDWorld/Eldir.git
cd Eldir
./scripts/install-eldir.sh
```

## Workflow

1. Crée une branche `feature/<slug>` ou `fix/<slug>` depuis `main`.
2. Code en respectant les règles d'`AGENTS.md`.
3. Lance les checks avant chaque commit (cf. ci-dessous).
4. Commits **conventionnels** : `feat(scope): …`, `fix(scope): …`, `chore(scope): …`, `docs(scope): …`.
5. Ouvre une PR contre `main`. Description : *quoi* + *pourquoi* + lien vers l'issue/phase concernée.

## Checks obligatoires avant commit

```bash
# Backend
cd backend
uv run ruff check --fix .
uv run ruff format .
uv run mypy app
uv run pytest -x --cov=app

# Frontend
cd frontend
npx eslint . --fix
npx prettier --write "src/**/*.{ts,tsx,css}"
npx tsc --noEmit -p tsconfig.app.json
npm test -- --run
```

Aucune erreur tolérée. Le mode TypeScript est strict (`noUncheckedIndexedAccess`, `exactOptionalPropertyTypes`) — pas de `any`, pas de `!` non-justifié.

## Types backend ↔ frontend

Les types TS sont **générés** depuis les schemas Pydantic. Jamais maintenus à la main.

```bash
./scripts/gen-types.sh           # ou gen-types-docker.sh si pas de venv local
```

Résultat : `frontend/src/lib/types/api-generated.ts`. Le façade `frontend/src/lib/types/api.ts` ré-exporte.

## Migrations DB

```bash
docker exec eldir-backend uv run alembic revision --autogenerate -m "description courte"
```

⚠️ **Relis le fichier généré** dans `backend/alembic/versions/` — Alembic rate parfois les renames, contraintes complexes, data migrations.

Puis :

```bash
docker exec eldir-backend uv run alembic upgrade head
```

(Auto au démarrage du container backend en dev.)

## Tests

- **Backend** : pytest + coverage minimum 70% sur les services métier.
- **Frontend** : Vitest + Testing Library, coverage minimum 50% (V1).

Un test qui échoue se fixe en corrigeant **le code**, jamais le test (sauf si le test était faux dès le départ).

## Documentation

Toute feature qui change le contrat utilisateur (route API, commande CLI, env var, UI majeure) doit être documentée dans `docs/`. Toute décision architecturale doit apparaître dans `ROADMAP.md` (section *Décisions actées*).

## Ce qu'on accepte / refuse

✅ **Accepté** :
- Bug fixes ciblés, avec test de non-régression
- Features alignées sur la phase courante du ROADMAP
- Doc et tests
- Nouveaux presets de templates dans `backend/app/data/template_presets/`
- Nouveaux providers Git (cf. [`docs/extending.md`](./docs/extending.md))
- Améliorations d'accessibilité / mobile / PWA

❌ **Refusé sans discussion préalable** :
- Refactor large sans issue ouverte avant
- Nouvelle dépendance hors stack imposée (cf. `AGENTS.md`)
- Anticipation d'une phase ROADMAP ultérieure
- Code qui casse les règles non-négociables (mobile-first, DRY, types partagés)
- Suppression de la licence AGPL

## Signaler un bug

Ouvre une [issue](https://github.com/JohnDWorld/Eldir/issues) avec :

1. **Stack** (host OS, Docker version)
2. **Branche/commit Eldir**
3. **Reproduction minimale**
4. **Logs** (`docker logs eldir-backend`, console navigateur)
5. **Comportement attendu** vs constaté

## Code of Conduct

Restons respectueux, factuels, et concentrés sur le code. Les attaques personnelles, harcèlement ou comportements discriminatoires entraîneront une exclusion immédiate du projet.

## Licence des contributions

En contribuant, tu acceptes que tes modifications soient distribuées sous [AGPL v3](./LICENSE), comme le reste d'Eldir.
