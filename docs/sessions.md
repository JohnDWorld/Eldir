# Sessions Claude dans Eldir

> Cycle de vie complet d'une session, du clic *+ NEW SESSION* à `git push`.

## Concept

Une **session** = une instance vivante de `ClaudeSDKClient` (Claude Agent SDK Python), pilotée par Eldir, qui travaille dans un **git worktree isolé** d'un de tes projets.

- Chaque session a son propre worktree : `/var/eldir/workspaces/{user_id}/{repo_slug}.{session_id}/`
- Chaque session vit sur sa propre branche : `claude/{session_id}`
- N sessions peuvent tourner en parallèle sur le **même** repo sans se gêner
- Au premier message, le SDK renvoie un `sdk_session_id` (UUID Anthropic) qu'Eldir capture et persiste — pour pouvoir **reprendre** la session plus tard
- Les hooks SDK + `ResultMessage` sont câblés vers Redis pub/sub → WebSocket → frontend, ce qui donne le **streaming live** des outils utilisés, des réponses et de l'usage en tokens

Chaque session obéit en plus au **protocole enfant** d'Eldir : elle termine ses tours par un compte rendu `<cr>` et n'a pas le droit de commiter ni de pousser elle-même. Voir [`docs/supervisor.md`](./supervisor.md).

## Démarrer une session

1. Va sur la **Ops home** (`/`).
2. Clique **+ NEW SESSION**.
3. Choisis un de tes projets (préalablement cloné via [`docs/github.md`](./github.md) ou [`docs/providers/forgejo.md`](./providers/forgejo.md)).
4. *(Optionnel)* coche **Mode économe** pour forcer Haiku au lieu du modèle du template.
5. Clique **lancer**. Eldir :
   - Récupère le credential Claude actif (token Pro/Max prioritaire, sinon API key Console)
   - Synchronise le repo (best-effort `git fetch origin`)
   - Crée la row `sessions` en DB
   - Crée un worktree sur `origin/{default_branch}`
   - **Matérialise le Mission Template** du projet : écrit les `.claude/skills/{name}/SKILL.md` et `.claude/agents/{name}.md`
   - Instancie `ClaudeSDKClient` avec le system_prompt + model + allowed_tools du template
   - Te redirige vers `/sessions/{id}`
6. Tape ton premier message → l'UI affiche le streaming live (texte, outils utilisés, état).

## Cycle de vie API

| Action | Endpoint | Effet backend |
|---|---|---|
| Lister | `GET /api/v1/sessions` | Toutes les sessions de l'utilisateur courant |
| Récupérer | `GET /api/v1/sessions/{id}` | Une session précise |
| Créer | `POST /api/v1/sessions` | Row Session + worktree + matérialisation template + `ClaudeSDKClient.connect()` |
| Envoyer message | `POST /api/v1/sessions/{id}/messages` | `client.query(content)`, lit le stream, publie events |
| Historique | `GET /api/v1/sessions/{id}/events` | `session_events` persistés en DB |
| Coûts session | `GET /api/v1/costs/sessions/{id}` | Totaux tokens/coût de la session |
| WS live | `WS /ws/sessions/{id}?token=…` | Relais Redis → client (text, tool_use, tool_result, state, stop, error, user_message, usage) |
| Git status | `GET /api/v1/sessions/{id}/git-status` | `branch`, `has_changes`, `modified`, `added`, `deleted`, `untracked` |
| Diff résumé | `GET /api/v1/sessions/{id}/diff` | Liste fichiers changés avec stats |
| Diff fichier | `GET /api/v1/sessions/{id}/diff/file?path=…` | Patch unifié d'un fichier |
| Commit & push | `POST /api/v1/sessions/{id}/commit-push` | `git add -A`, commit, push origin |
| Open PR | `POST /api/v1/sessions/{id}/pull-request` | `GitProvider.create_pr(...)` |
| Stopper | `POST /api/v1/sessions/{id}/stop` | `client.disconnect()`, retire du pool |
| Supprimer | `DELETE /api/v1/sessions/{id}` | Stop + suppression worktree + suppression DB (cascade events + costs) |

## États

```
idle ──► thinking ──► tool_use ──► thinking ──► ... ──► idle
                          │
                          └──► waiting_input  (V4+)
                          └──► blocked        (V4+)
```

Calculé automatiquement par le `SessionManager` à partir :
- Des events `state` publiés par les hooks SDK
- Du `ResultMessage` qui repasse à `idle` en fin de tour

Diffusé sur le WS, affiché par badge couleur dans l'UI :
- gris : `idle`
- pulse orange : `thinking`
- bordure orange animée : `tool_use`
- gold clignotant : `waiting_input`
- bordure rouge : `blocked`

## Types d'events streamés

| Type | Quand | Payload |
|---|---|---|
| `user_message` | L'utilisateur envoie un message | `{text}` |
| `state` | Changement d'état | `{state}` ou `{sdk_session_id}` |
| `text` | Bloc texte de Claude | `{text}` |
| `tool_use` | Claude utilise un outil (hook PreToolUse) | `{tool_name, tool_input, tool_use_id}` |
| `tool_result` | Résultat de l'outil (hook PostToolUse) | `{tool_name, tool_response, tool_use_id}` |
| `usage` | Fin de tour, coût/tokens | `{input_tokens, output_tokens, cache_read_tokens, cache_write_tokens, cost_usd, duration_ms, num_turns, model}` |
| `stop` | Fin de tour | `{reason: "turn_complete"}` |
| `error` | Erreur SDK | `{message, type}` |

Tous sont à la fois publiés sur Redis (WS) et persistés en DB (`session_events`).

## Reprendre une session après redémarrage Eldir

Le pool en mémoire est vide après reboot. Mais les `sdk_session_id` sont en DB :

1. Va sur `/sessions/{id}` après reboot.
2. Envoie un message — Eldir détecte que la session n'est plus active, instancie un nouveau `ClaudeSDKClient` avec `resume=sdk_session_id`.
3. Anthropic restaure le contexte côté SDK, tu reprends où tu en étais.

## Worktrees & travail parallèle

Une session = un worktree isolé. C'est *la* feature qui permet plusieurs Claude en parallèle sur le même repo.

```bash
# Sur l'host
ls /var/eldir/workspaces/{user_id}/

# Exemple
johndworld-eldir/                              # clone principal (default branch)
johndworld-eldir.abc12345-…/                   # worktree session 1, branche claude/abc12345-…
johndworld-eldir.def67890-…/                   # worktree session 2, branche claude/def67890-…
```

Chaque worktree partage le même `.git/` (objets), donc le clonage de N sessions reste cheap en disque.

## Modèles Claude supportés

Configurables au niveau du Mission Template du projet, ou override par session :

- `claude-opus-4-7` — le plus puissant (par défaut sur le preset Eldir)
- `claude-sonnet-4-6` — équilibré
- `claude-haiku-4-5-20251001` — le plus rapide / le moins cher (utilisé par "Mode économe")

Le SDK suit aussi le défaut configuré côté Anthropic si on ne précise rien.

## Sécurité

- Le WebSocket exige un JWT en query param (`?token=…`). Le handler vérifie l'ownership (`Session.user_id` = user courant) avant d'attacher au pubsub.
- Les credentials Claude ne sont jamais retournés en clair par l'API — uniquement masqués (`…aB12`).
- Les events SDK passent par Redis pubsub, pas exposés directement.
- Mode `bypassPermissions` côté SDK : pas de TTY côté serveur, le filet de sécurité est l'**isolation worktree** + le **stream visible** de tous les `tool_use` côté UI.

## Limites connues

- **Mono-tour bloquant** : `send_message` attend la fin du tour (`ResultMessage`) côté backend. Le streaming arrive en parallèle sur le WS, donc l'UI reste responsive.
- **Hard cap** : `MAX_CONCURRENT_SESSIONS` (env, défaut 8). Au-delà : `SessionLimitError`. Chaque session active fait vivre un process `claude` (Node) de 150 à 450 Mo et le superviseur en occupe une : sur un serveur à 4 Go de RAM, mets 4. Une session stoppée libère sa RAM et reste reprenable (`resume`).
- **Pas de fork conversationnel** : prévu V2 (le SDK le supporte nativement).
- **Background tasks + notif PWA quand un tour finit pendant qu'on est ailleurs** : prévu en résiduel Phase 2 / début Phase 6.

## Voir aussi

- [`templates.md`](./templates.md) — Mission Templates appliqués à chaque session
- [`costs.md`](./costs.md) — usage tokens capturé par session
- [`git-workflow.md`](./git-workflow.md) — commit & push depuis la session
- [`architecture.md`](./architecture.md) — flow complet d'un message
