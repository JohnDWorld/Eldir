# Bien démarrer avec Eldir

> Guide pas à pas pour t'amener du `git clone` à ta première session Claude opérationnelle. Compte 10 minutes.

## 0. Prérequis

- **Docker 24+** et **docker compose v2** installés
- Un compte **Claude Pro** ou **Max** (recommandé) OU une clé API Anthropic Console
- Un compte **GitHub** OU un PAT d'une instance **Forgejo / Codeberg**

Pas obligatoire mais utile : `curl`, `python3 ≥ 3.10`, Node.js ≥ 18 (pour le script `install-eldir.sh`).

## 1. Cloner et démarrer

```bash
git clone https://github.com/JohnDWorld/Eldir.git
cd Eldir
./scripts/install-eldir.sh
```

Le script te guide à travers :

1. Démarrage de Postgres + Redis + backend FastAPI + frontend Vite
2. Récupération du **bootstrap token** dans les logs
3. Choix du mot de passe admin + email
4. *(Optionnel)* génération d'un token Claude Pro/Max via `npx -y @anthropic-ai/claude-code setup-token` (navigateur, ~30s)
5. *(Optionnel)* ajout d'une clé API Console en fallback
6. Bootstrap final via `/api/v1/setup/bootstrap`

À la fin, ouvre **http://localhost:5173** dans ton navigateur, login avec ton admin, et tu arrives sur l'**Ops home**.

Détails et installation manuelle : [`docs/installation.md`](./installation.md).

## 2. Connecter un Git provider

### GitHub (recommandé pour la première fois)

Va dans **Settings > Git** et :

- Option facile : clique **Connect with GitHub** (OAuth) — *requiert que ton admin Eldir ait configuré une app OAuth GitHub. Sinon utilise un PAT.*
- Option PAT : suis [`docs/github.md`](./github.md) pour générer un Personal Access Token avec les bonnes permissions, puis colle-le dans Eldir.

### Forgejo / Codeberg

Va dans **Settings > Git**, sélectionne Forgejo, renseigne :

- **Base URL** : ex. `https://forge.example.org` ou `https://codeberg.org`
- **Token** : un PAT généré depuis `{base_url}/user/settings/applications`

Détails : [`docs/providers/forgejo.md`](./providers/forgejo.md).

## 3. Cloner ton premier projet

Va dans **Projects** (menu du haut) et clique **+ ajouter un repo**.

1. Choisis ton provider (GitHub / Forgejo)
2. Eldir liste les repos accessibles via ton token
3. Coche **un ou plusieurs** repos, clique **Valider**
4. Eldir clone côté serveur dans `/var/eldir/workspaces/{user_id}/{repo_slug}/`

Si tu n'as **qu'un seul** repo coché, après le clone, Eldir te propose immédiatement de **générer un Mission Template avec Claude** (~30s à 2min). C'est fortement recommandé pour la première fois — tu auras un template adapté à ton repo sans avoir à le rédiger à la main.

## 4. (Optionnel mais conseillé) Générer un Mission Template

Un *Mission Template* dit à Claude :

- Quel est ton repo (stack, conventions, sources de vérité)
- Quels modèles utiliser (Opus / Sonnet / Haiku)
- Quels outils autoriser
- Quelles commandes idiomatiques sont disponibles (les *skills*)
- Quels agents spécialisés sont à sa disposition (les *sub-agents*)

Trois façons d'avoir un template :

| Mode | Quand l'utiliser |
|---|---|
| **✨ Générer avec Claude** | Tu démarres, tu ne veux pas réfléchir. Eldir analyse ton repo et propose un template. Recommandé. |
| **Appliquer un preset** | Tu veux partir d'un template communautaire (Django, FastAPI, etc.) — voir presets dans `backend/app/data/template_presets/`. |
| **Configurer manuellement** | Tu sais exactement ce que tu veux, tu pars de zéro. |

Le template est éditable à tout moment depuis **Projects > [ton projet] > Template**. Détails dans [`docs/templates.md`](./templates.md).

## 5. Lancer ta première session

Va sur **Ops home** (`/`), clique **+ NEW SESSION**.

1. Choisis ton projet
2. *(Optionnel)* coche **Mode économe** pour forcer Haiku au lieu du modèle du template (moins cher, suffisant pour les tâches simples)
3. Clique **lancer**

Eldir :

- Crée un **git worktree isolé** : branche `claude/{session_id}` partant de `origin/{default_branch}`
- Matérialise ton template (skills `.claude/skills/`, sub-agents `.claude/agents/`)
- Démarre une instance `ClaudeSDKClient` avec ton system prompt + modèle + outils
- T'amène sur `/sessions/{id}`

Tape ton premier message → tu vois Claude streamer ses réponses + les outils qu'il utilise en temps réel.

Détails : [`docs/sessions.md`](./sessions.md).

## 6. Activer les notifs (optionnel mais agréable)

Va dans **Settings > Notifications · push** et clique **Activer**.

Eldir te préviendra par une notif native quand un tour Claude se termine pendant que tu es sur un autre onglet / écran verrouillé / PWA en arrière-plan. Pratique sur mobile.

## 7. Suivre tes coûts

Va dans **Costs** (menu du haut). Tu y vois :

- Coût USD aujourd'hui / 7 derniers jours / 30 derniers jours
- Tokens input / output / **cache read** (avec ratio cache, plus c'est haut moins tu paies)
- Répartition par projet
- Bouton **Export CSV** pour ta compta

Tout ce que tu consommes via Eldir y apparaît, **y compris les sessions internes** d'Eldir (génération de template, etc.). Pas de coût caché.

Détails : [`docs/costs.md`](./costs.md).

## 8. Workflow git depuis une session

Quand tu as bossé avec Claude et que tu veux pousser ton travail :

- **Commit & push** : bouton dans la topbar de la session
- **Open PR** : bouton à côté (fonctionne pour GitHub et Forgejo)

Détails : [`docs/git-workflow.md`](./git-workflow.md).

## Aller plus loin

| Tu veux… | Va voir |
|---|---|
| Comprendre l'architecture | [`docs/architecture.md`](./architecture.md) |
| Modifier les prompts qu'Eldir envoie à Claude | Settings > Prompts (dans l'UI) |
| Ajouter un Git provider (GitLab, Bitbucket…) | [`docs/extending.md`](./extending.md) |
| Ajouter un preset partagé à la communauté | [`docs/templates.md#format-json-dun-preset`](./templates.md) |
| Contribuer du code | [`CONTRIBUTING.md`](../CONTRIBUTING.md) |
| Lire le code de l'agent quand il bosse sur Eldir | [`backend/app/data/template_presets/eldir.json`](../backend/app/data/template_presets/eldir.json) |

## Si quelque chose cloche

- **Le bootstrap token n'apparaît pas** → `docker logs eldir-backend | grep ELDIR_BOOTSTRAP_TOKEN`. S'il n'est pas là, un admin existe déjà ; reset avec `docker compose -f docker-compose.dev.yml down -v` puis recommence.
- **Erreur "Aucun credential Claude configuré"** → Settings > Claude et ajoute soit un OAuth token (Pro/Max) soit une clé API Console.
- **Une session bloque sur "thinking"** → ouvre `docker logs eldir-backend -f`, regarde s'il y a une stack trace côté Claude SDK.
- **Le clone d'un repo échoue** → vérifie que ton token Git a les bonnes permissions (cf. [`docs/github.md`](./github.md) ou [`docs/providers/forgejo.md`](./providers/forgejo.md)).
- **Le mode économe ne semble pas avoir d'effet** → vérifie le panneau "Cost · session" dans le rail droit de ta session : le champ `model` doit afficher `haiku`. Si non, tu as peut-être un override projet qui prime.

Pour le reste : [issues GitHub](https://github.com/JohnDWorld/Eldir/issues).
