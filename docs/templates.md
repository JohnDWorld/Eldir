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
                    ├── setup_commands (json|null)  ← toolchain du repo
                    ├── skills (1↔N) → name, description, content (md)
                    ├── sub_agents (1↔N) → name, description, system_prompt, allowed_tools
                    └── versions (1↔N) → snapshot JSON pour rollback
```

Tables Postgres : `mission_templates`, `template_skills`, `template_sub_agents`, `template_versions`. Migrations `0002_mission_templates.py` et `0008_template_setup_commands.py`.

## Toolchain du repo (`setup_commands`)

Le conteneur backend n'embarque que **git, node 20, npm, python 3.12, uv et le CLI Claude**. Un agent sur un repo Flutter ne peut donc pas lancer `flutter analyze` : il le signale dans son `RESTE:` et son travail reste non vérifié.

Tout mettre dans l'image donnerait une image de 15 Go reconstruite à chaque déploiement, avec Flutter installé pour les projets Python. À la place, chaque projet **déclare** ses commandes d'installation, et Eldir les exécute **à la demande** :

```
/var/eldir/toolchains/<project_id>/        ← $ELDIR_TOOLCHAIN (volume eldir_toolchains)
/var/eldir/toolchains/<project_id>/bin/    ← en tête du PATH des sessions du projet
```

Exemple, un repo Flutter (analyse seule, sans SDK Android) :

```json
"setup_commands": [
  "git clone --depth 1 -b stable https://github.com/flutter/flutter.git",
  "ln -sf $ELDIR_TOOLCHAIN/flutter/bin/flutter $ELDIR_TOOLCHAIN/bin/flutter",
  "ln -sf $ELDIR_TOOLCHAIN/flutter/bin/dart $ELDIR_TOOLCHAIN/bin/dart",
  "flutter --version"
]
```

Ce que ça coûte, en ordre de grandeur : SDK Flutter + Dart ~3 Go de disque et 0,7 à 1,5 Go de RAM au pic pour le serveur d'analyse Dart ; SDK Android **+8 à 12 Go**, inutile pour `analyze` ; JDK + caches Gradle 1 à 2 Go ; `node_modules` d'un repo JS 0,2 à 1 Go.

Garde-fous côté serveur :

- **rien ne s'installe tout seul** : il faut cliquer dans l'éditeur de template, et l'UI affiche le poids obtenu ;
- **une seule installation à la fois** sur tout le serveur (4 cœurs, 4 Go de RAM : deux clones de SDK en parallèle mettent la machine à genoux) ;
- **refus si le disque libre passe sous `TOOLCHAIN_MIN_FREE_GB`** (5 Go par défaut) ;
- timeout à `TOOLCHAIN_INSTALL_TIMEOUT_S` (30 min par défaut), log conservé et consultable.

Les commandes tournent avec les droits du backend (utilisateur `eldir`, pas de sudo) : c'est du shell arbitraire, écrit ou relu par toi. `apt-get install` ne marchera pas, il faut des installations en espace utilisateur.

L'état vit dans le dossier du toolchain (`.eldir-state.json`, `install.log`), pas en base : purger le volume purge l'état, il n'y a rien à resynchroniser. Le dossier est un volume distinct des workspaces, donc on peut le supprimer pour rendre du disque sans toucher aux clones.

API : `GET /api/v1/projects/{id}/toolchain`, `POST …/toolchain/install` (202, suivi par polling), `DELETE …/toolchain`.

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
- **Model** : `Défaut` / `claude-opus-5` / `claude-sonnet-5` / `claude-haiku-4-5`
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
  "model": "claude-opus-5",
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
