# Mission Templates

> Phase 4 du ROADMAP. Configure une fois les conventions d'un projet (system prompt, skills, sub-agents, modèle, outils autorisés), Eldir applique automatiquement à chaque session sur ce repo.

## Pourquoi ?

Sans template, tu dois reformuler tes conventions à chaque nouvelle session ("utilise pnpm pas npm", "lance les tests avec X", "voilà la structure du repo…"). C'est de la perte de tokens et de la friction.

Avec un Mission Template, chaque session démarre déjà briefée :

- Un **system prompt** rappelant les sources de vérité, les règles non-négociables, le workflow
- Un **modèle** par défaut (Opus pour les gros refactos, Haiku pour le boring)
- Une liste **d'outils autorisés** (optionnel, sinon tous les built-ins)
- Des **skills** : commandes nommées, accessibles à l'agent (`backend-tests`, `frontend-typecheck`, `gen-types`…)
- Des **sub-agents** : "experts" spécialisés que l'agent principal peut invoquer (test-runner, doc-keeper…)

## Modèle de données

```
project ──1↔1──► mission_template
                    ├── system_prompt (text)
                    ├── model (string|null)
                    ├── allowed_tools (json|null)
                    ├── skills (1↔N) → name, description, content (md)
                    ├── sub_agents (1↔N) → name, description, system_prompt, allowed_tools
                    └── versions (1↔N) → snapshot JSON pour rollback
```

Tables Postgres : `mission_templates`, `template_skills`, `template_sub_agents`, `template_versions`. Migration `0002_mission_templates.py`.

## Matérialisation côté worktree

Quand une session démarre, le template est écrit dans le worktree de la session :

```
{worktree}/
└── .claude/
    ├── skills/
    │   ├── backend-tests/SKILL.md
    │   ├── frontend-typecheck/SKILL.md
    │   └── …
    └── agents/
        ├── test-runner.md
        ├── doc-keeper.md
        └── …
```

Le Claude Agent SDK détecte automatiquement ces fichiers et les rend disponibles à l'agent.

**Concurrent editing** : si tu modifies le template pendant qu'une session tourne, le changement n'est appliqué qu'à la **prochaine** session. Les sessions actives gardent leur matérialisation initiale.

## UI

Va sur **Projects > [ton projet] > Template** (ou `/projects/{id}/template`).

### Bloc principal

- **System prompt** : textarea longue, prompt envoyé à l'agent au boot
- **Model** : `Défaut` / `claude-opus-4-7` / `claude-sonnet-4-6` / `claude-haiku-4-5`
- **Tools** : multi-select de tool pills (laisser vide = tous les built-ins autorisés)

### Skills

Chaque skill = un fichier `.md` avec frontmatter. Edite via la modale :

- **Name** (slug filesystem-safe : `[a-zA-Z0-9_-]+`)
- **Description** : 1 ligne, visible par l'agent dans la liste
- **Content** : markdown libre — commandes, exemples, contraintes

Exemple :

```markdown
# backend-tests

Lance la suite de tests backend avec couverture.

\`\`\`bash
cd backend
uv run pytest -x --cov=app --cov-report=term-missing
\`\`\`

- `-x` : stoppe au premier échec.
- Coverage minimum visé : 70% sur le backend.
```

### Sub-agents

Un sub-agent = un agent spécialisé, invocable par l'agent principal pour une tâche cadrée.

- **Name** (slug filesystem-safe)
- **Description** : visible par l'agent principal
- **System prompt** : briefing du sub-agent
- **Allowed tools** : restreindre ses capacités (un sub-agent "doc-keeper" n'a pas besoin de `Bash` par exemple)

### Apply preset

Bouton **Apply preset** → modale qui liste les presets dispos avec preview à droite.

Deux modes :
- **Overwrite** : remplace complètement le template existant (skills/sub-agents inclus)
- **Merge** : ajoute, skip les noms qui existent déjà

### Versions / rollback

Chaque modification de template prend un snapshot JSON dans `template_versions`. La section **Historique** liste les N dernières versions avec timestamp + diff résumé. Bouton **Restore** pour rollback (qui crée lui aussi un nouveau snapshot — pas de perte).

## Presets fournis

Stockés dans `backend/app/data/template_presets/*.json`. Listés par `GET /api/v1/templates/presets`.

Phase 4 livre :

- **`eldir`** (self-hosted) — le preset pour bosser sur Eldir lui-même. Référence AGENTS.md / CLAUDE.md / ROADMAP.md comme sources de vérité, 8 skills (`backend-tests`, `frontend-typecheck`, `gen-types`, `alembic-migrate`, …), 3 sub-agents (`test-runner`, `doc-keeper`, `roadmap-checker`).

Plus de presets viendront (Django, FastAPI standalone, React + Vite générique, n8n…). Cf. [`docs/extending.md`](./extending.md) pour ajouter le tien.

## Format JSON d'un preset

```json
{
  "slug": "ton-preset",
  "title": "Affichage UI",
  "description": "1-2 phrases sur l'usage du preset",
  "tags": ["django", "rest"],
  "model": "claude-opus-4-7",
  "allowed_tools": null,
  "system_prompt": "Tu es ...",
  "skills": [
    {
      "name": "run-tests",
      "description": "Lance la suite de tests Django.",
      "content": "# run-tests\n\n```bash\npython manage.py test\n```"
    }
  ],
  "sub_agents": [
    {
      "name": "migration-keeper",
      "description": "Vérifie que les migrations Django sont cohérentes.",
      "system_prompt": "Tu es responsable...",
      "allowed_tools": ["Bash", "Read", "Grep"]
    }
  ]
}
```

Déposer le fichier dans `backend/app/data/template_presets/<slug>.json` et redémarrer le backend (cache un peu).

## API

| Endpoint | Effet |
|---|---|
| `GET /api/v1/projects/{id}/template` | Lire le template du projet |
| `PUT /api/v1/projects/{id}/template` | Upsert (system_prompt, model, allowed_tools) |
| `DELETE /api/v1/projects/{id}/template` | Reset le template du projet |
| `GET/POST/PUT/DELETE /api/v1/projects/{id}/template/skills[/{id}]` | CRUD skills |
| `GET/POST/PUT/DELETE /api/v1/projects/{id}/template/sub-agents[/{id}]` | CRUD sub-agents |
| `GET /api/v1/projects/{id}/template/versions` | Historique versions |
| `POST /api/v1/projects/{id}/template/versions/{version_id}/restore` | Rollback |
| `GET /api/v1/templates/presets` | Liste presets dispo |
| `GET /api/v1/templates/presets/{slug}` | Détail d'un preset (preview) |
| `POST /api/v1/projects/{id}/template/apply-preset` | Body : `{slug, overwrite}` |

## Voir aussi

- [`sessions.md`](./sessions.md) — comment le template est appliqué à chaque session
- [`extending.md`](./extending.md) — ajouter ton propre preset
