# Sessions Claude — Eldir Phase 1

## Concept

Une **session** = une instance vivante de `ClaudeSDKClient` (Anthropic Claude Agent SDK Python), pilotée par Eldir, qui travaille dans le workspace cloné d'un de tes projets.

- Chaque session a un `cwd` égal au chemin du workspace : `/var/eldir/workspaces/{user_id}/{repo_slug}/`.
- Au premier message, le SDK retourne un `session_id` (UUID Anthropic) qu'Eldir capture et persiste — pour pouvoir **reprendre** la session plus tard.
- Les hooks `PreToolUse` / `PostToolUse` / `Stop` du SDK sont câblés vers Redis pub/sub → WebSocket → frontend, ce qui donne le streaming live des outils utilisés et des réponses Claude.

## Lancer une session

1. Va sur la **home** (`/`).
2. Clique **+ NEW SESSION**.
3. Choisis un de tes projets (préalablement cloné via [docs/github.md](github.md)).
4. Eldir :
   - Récupère ton credential Claude actif (token Pro/Max prioritaire, sinon API key Console).
   - L'injecte dans `os.environ` avant d'instancier le `ClaudeSDKClient`.
   - Crée la row Session en base.
   - Démarre la connexion SDK.
   - Te redirige vers `/sessions/{id}`.
5. Tape ta première instruction → l'UI affiche les blocs `text` (réponses) et `tool_use` (édits, runs) en live.

## Cycle de vie

| Action | Backend | Effet |
|---|---|---|
| Créer | `POST /api/v1/sessions` | Row Session + `ClaudeSDKClient.connect()` |
| Envoyer message | `POST /api/v1/sessions/{id}/messages` | `client.query(content)`, lit le stream, publie events |
| WebSocket live | `WS /ws/sessions/{id}?token=…` | Relais Redis → client (text, tool_use, tool_result, state, stop, error) |
| Récupérer historique | `GET /api/v1/sessions/{id}/events` | SessionEvent persistés en DB |
| Reprendre | `POST /api/v1/sessions/{id}/resume` | `ClaudeAgentOptions(resume=sdk_session_id)` |
| Stopper | `POST /api/v1/sessions/{id}/stop` | `client.disconnect()` + retire du pool |

## États

Une session a un état parmi `idle | thinking | tool_use | waiting_input | blocked`. Mis à jour automatiquement par le SessionManager (depuis les events `state` et les hooks SDK), persisté en DB, diffusé sur le WS.

## Limites Phase 1

- **Mono-tour** : `send_message` bloque jusqu'à fin du tour (`ResultMessage`). Le streaming arrive en parallèle sur le WS.
- **Pas de tools restreints** : `allowed_tools` est laissé au défaut du SDK. Restriction granulaire en Phase 4 (Mission Templates).
- **Pas de diff viewer en temps réel** : les fichiers modifiés apparaissent comme `tool_use` (avec `Edit`/`Write`) dans la chat. Diff viewer côté repo en Phase 4.
- **Pas de tracking de coût** : `SessionCost` existe en table mais n'est pas alimenté. OTel SDK arrive en Phase 5.
- **Limite hard de sessions parallèles** : `MAX_CONCURRENT_SESSIONS = 8` (constants.py). On lève `SessionLimitError` au-delà.

## Reprendre une session après un redémarrage Eldir

Une fois ton container redémarré, le pool en mémoire est vide. Mais les `sdk_session_id` sont persistés :

1. Va sur `/sessions/{id}`.
2. Envoie un message — Eldir détecte que la session n'est plus active, appelle automatiquement `resume()` (qui réinstance un `ClaudeSDKClient` avec `resume=sdk_session_id`).
3. Le contexte est restauré côté Anthropic, tu reprends où tu en étais.

## Modèles

Par défaut, Eldir utilise `claude-sonnet-4-6` (override dans `backend/.env` via `CLAUDE_DEFAULT_MODEL`). Le `POST /api/v1/sessions` accepte un champ `model` pour outrepasser au cas par cas. Modèles supportés Phase 1 :

- `claude-sonnet-4-6` — par défaut
- `claude-opus-4-7` — plus puissant
- `claude-haiku-4-5` — plus rapide / moins cher

## Sécurité

- Le WebSocket exige un JWT en query param : `?token=<access_token>`. Eldir vérifie le token avant de joindre le pubsub Redis.
- Les credentials Claude ne sont **jamais** retournés en clair par l'API — uniquement masqués (`…aB12`).
- Les hooks SDK ne sont jamais exposés directement au frontend — ils passent par Redis pubsub, ce qui empêche tout client malveillant d'écouter les events d'une session qui ne lui appartient pas (l'auth WS vérifie `Session.user_id`).
