# Sessions Claude dans Eldir

> Cycle de vie complet d'une session, du clic *+ NEW SESSION* à `git push`.

## Concept

Une **session** = une instance vivante de `ClaudeSDKClient` (Claude Agent SDK Python), pilotée par Eldir, qui travaille dans un **git worktree isolé** d'un de tes projets.

- Chaque session a son propre worktree : `/var/eldir/workspaces/{user_id}/{repo_slug}.{session_id}/`
- Chaque session vit sur sa propre branche : `claude/{session_id}`
- Le CLI `claude` que le SDK pilote tourne **dans son propre conteneur** (`SESSION_RUNTIME=conteneur`, le défaut), qui ne monte que le disque de cette session et de son projet. En mode `processus`, il tourne dans le conteneur du backend et voit tout. Voir « Ce qu'une session voit de son disque » plus bas
- N sessions peuvent tourner en parallèle sur le **même** repo sans se gêner
- Au premier message, le SDK renvoie un `sdk_session_id` (UUID Anthropic) qu'Eldir capture et persiste - pour pouvoir **reprendre** la session plus tard
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
   - Instancie `ClaudeSDKClient` avec le system_prompt + model + allowed_tools du template (en mode `conteneur`, le CLI qu'il lance est le `docker run` de l'enrobage, et le conteneur démarre là)
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
2. Envoie un message - Eldir détecte que la session n'est plus active, instancie un nouveau `ClaudeSDKClient` avec `resume=sdk_session_id`.
3. Anthropic restaure le contexte côté SDK, tu reprends où tu en étais.

**À savoir.** `resume` traite n'importe quel échec de démarrage comme un transcript
perdu : il efface `sdk_session_id`, commit, puis repart d'une session neuve
(l'historique reste lisible, il vit dans `session_events`). En mode `conteneur`, un
échec passager de `docker run` (démon qui répond mal, réseau ou image absents un
instant) prend donc ce chemin, et tu perds le pointeur de reprise pour une raison
sans rapport avec ton transcript. Connu, et non corrigé dans ce lot.

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

## Ce qu'une session voit de son disque

En mode `conteneur` (le défaut), le conteneur d'une session monte ceci, et rien
d'autre du disque du serveur. Chaque montage est un sous-chemin d'un volume
nommé (`volume-subpath`) : la session ne reçoit pas le volume, elle reçoit un
dossier.

| Dans le conteneur | Ce que c'est | Accès | Pourquoi |
|---|---|---|---|
| son worktree, au même chemin absolu que chez le backend | `workspaces/{user_id}/{repo_slug}.{session_id}` | écriture | c'est là qu'elle travaille |
| le clone de son projet, au même chemin absolu | `workspaces/{user_id}/{repo_slug}` | écriture | le `.git` d'un worktree est un fichier qui pointe dans le clone, et `git commit` y écrit ses objets. Mesuré : sans ce montage, `git status` répond « not a git repository ». Le superviseur, dont le cwd n'est le worktree de rien, n'en a pas |
| le toolchain de son projet (`$ELDIR_TOOLCHAIN`), au même chemin absolu | `toolchains/{project_id}` | lecture seule | elle exécute les outils, elle ne les écrit pas. Monté seulement si le projet en a un d'installé |
| ce qui a été collecté sur son serveur (`$ELDIR_COLLECTE`), au même chemin absolu | `collectes/{project_id}` | lecture seule | monté seulement s'il y a une collecte |
| sa maison `.claude` (`/eldir/maison`, aussi `$HOME`) | `claude_home/{project_id}` | écriture | transcripts du CLI, `known_hosts`, temporaire du CLI. Une maison par **projet**, pas par session : deux sessions d'un même projet la partagent, c'est le même domaine de confiance |
| sa clé SSH et son `config` (`/eldir/ssh/cle`, `/eldir/ssh/config`) | une copie propre à la session, dans un dossier voisin de la maison du projet | lecture seule | monté seulement si le projet a un accès distant. Le `config` n'a qu'un bloc : celui de la machine du projet |

Les chemins sont les mêmes que chez le backend pour que ceux que la session
manipule, que les hooks inspectent et que le diff viewer affiche désignent les
mêmes fichiers.

**Ce qui n'est pas monté.** Le worktree, le clone, le toolchain, la collecte, la
maison `.claude`, la clé et le `config` de tout autre projet ; le `config` SSH du
backend, qui porte les machines de tous les projets ; le volume `eldir_ssh` du
backend ; le socket du démon. La base et Redis ne sont pas joignables : la
session est sur un réseau dédié qui n'a de route vers aucun réseau du compose. Et
le voisin n'est pas refusé, **il n'existe pas** dans l'univers de la session : les
trois tests d'isolement vérifient l'absence, pas une erreur de permission.
Détail, mesures et ce qui reste ouvert : [`securite-sessions.md`](./securite-sessions.md).

**L'image.** `backend/docker/session/` : Node 20, `git`, `ssh`, et le CLI Claude
épinglé (`ARG CLAUDE_CLI_VERSION`), avec `ca-certificates` et `openssh-client`.
Pas d'outil de projet, ils viennent du toolchain monté. **Ni python ni uv**, que
l'image du backend porte : un projet qui comptait dessus doit les déclarer dans
son toolchain (cf. [`templates.md`](./templates.md#toolchain-du-repo-setup_commands)).
Le conteneur tourne avec l'utilisateur d'uid 1000 que
`node:20-bookworm-slim` fournit déjà, `node`. La spec de ce lot le nommait
`session` : on a gardé `node`, parce qu'en créer un second sur l'uid 1000
échouerait. Le backend doit tourner en uid 1000 lui aussi (c'est le défaut de
`backend/Dockerfile`) : l'enrobage refuse de lancer une session sinon.

**Quel CLI exécute ta session** dépend du mode, et trois versions peuvent
diverger sans que rien ne les aligne :

- en mode `conteneur`, le CLI épinglé de l'image des sessions ;
- en mode `processus`, le CLI embarqué dans le SDK Python (`claude-agent-sdk`,
  `backend/uv.lock`), et pas celui du backend ;
- le `claude` installé en `@latest` dans l'image du backend (`backend/Dockerfile`)
  ne lance pas de session : il sert à la sonde de credential, et de repli au SDK.

**En mode `processus`**, rien de cette table ne s'applique : le CLI tourne dans
le conteneur du backend et voit le disque de tous les projets.

## Modèles Claude supportés

Configurables au niveau du Mission Template du projet, ou override par session :

- `claude-opus-5` - le plus puissant (par défaut sur le preset Eldir)
- `claude-sonnet-5` - équilibré
- `claude-haiku-4-5` - le plus rapide / le moins cher (utilisé par "Mode économe")

> Haiku n'a pas de version 5 : la génération courante reste Haiku 4.5. Les
> identifiants ne portent jamais de suffixe de date.

Le SDK suit aussi le défaut configuré côté Anthropic si on ne précise rien.

## Sécurité

- Le WebSocket exige un JWT en query param (`?token=…`). Le handler vérifie l'ownership (`Session.user_id` = user courant) avant d'attacher au pubsub.
- Les credentials Claude ne sont jamais retournés en clair par l'API - uniquement masqués (`…aB12`).
- Les events SDK passent par Redis pubsub, pas exposés directement.
- Mode `bypassPermissions` côté SDK : pas de TTY côté serveur, le filet de sécurité est l'**isolation worktree** (et, en mode `conteneur`, celle du conteneur pour le disque des autres projets) + le **stream visible** de tous les `tool_use` côté UI. Ce filet n'isole pas une session du backend : par git, elle peut lui faire exécuter une commande (risque nº 3), et le proxy de socket ne sépare pas le backend de root sur l'hôte. N'héberge pas sur la même instance un projet sensible et un projet alimenté par des tickets publics. Détail : [`securite-sessions.md`](./securite-sessions.md).

## Limites connues

- **Mono-tour bloquant** : `send_message` attend la fin du tour (`ResultMessage`) côté backend. Le streaming arrive en parallèle sur le WS, donc l'UI reste responsive.
- **Hard cap** : `MAX_CONCURRENT_SESSIONS` (env, défaut 8). Au-delà : `SessionLimitError`. Chaque session active fait vivre un process `claude` (Node) de 150 à 450 Mo et le superviseur en occupe une : sur un serveur à 4 Go de RAM, mets 4. En mode `conteneur`, l'enveloppe du conteneur ajoute de 15 à 45 Mo par session (mesuré le 2026-11-06, détail dans le commentaire de `max_concurrent_sessions`, `backend/app/core/config.py`) : le plafond n'a pas bougé. Aucune limite mémoire n'est posée aux conteneurs, ce plafond est la seule borne. Une session stoppée libère sa RAM et reste reprenable (`resume`).
- **Pas de fork conversationnel** : prévu V2 (le SDK le supporte nativement).
- **Background tasks + notif PWA quand un tour finit pendant qu'on est ailleurs** : prévu en résiduel Phase 2 / début Phase 6.

## Voir aussi

- [`templates.md`](./templates.md) - Mission Templates appliqués à chaque session
- [`costs.md`](./costs.md) - usage tokens capturé par session
- [`git-workflow.md`](./git-workflow.md) - commit & push depuis la session
- [`architecture.md`](./architecture.md) - flow complet d'un message
