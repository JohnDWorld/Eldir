# Intégration Ollama — mode "données sensibles"

> Phase 6 du ROADMAP. Permet de pré-traiter du texte localement (masquage de secrets, anonymisation PII, résumé court) avant tout appel à Claude. Tes données sensibles ne traversent jamais Internet.

## Pourquoi ?

Claude est puissant mais c'est un SaaS centralisé. Si tu as :

- Un fichier `.env` à analyser
- Un dump de logs avec des emails et des tokens
- Du code source contenant des credentials hard-codés
- Un export de DB avec des données utilisateurs

... tu ne veux pas balancer ça tel quel à Anthropic. Eldir te permet de **brancher Ollama en local**, faire passer le texte par un modèle qui tourne sur ta machine, et n'envoyer à Claude que la version masquée/anonymisée.

C'est aussi utile pour économiser des tokens : un fichier de 50k tokens peut être **résumé localement** en 200 tokens avant d'aller alimenter Claude.

## Installer Ollama

Sur l'host (PC ou serveur où tourne Eldir) :

```bash
# Linux
curl -fsSL https://ollama.com/install.sh | sh

# macOS
brew install ollama

# Ou en container Docker
docker run -d -v ollama:/root/.ollama -p 11434:11434 --name ollama ollama/ollama
```

Démarre le service :

```bash
# Linux/macOS (s'il n'est pas auto-start)
ollama serve
```

Pull au moins un modèle :

```bash
# Léger (1.3 GB) - parfait pour le masquage et l'anonymisation
ollama pull llama3.2

# Plus précis (4.7 GB) - pour des résumés de qualité
ollama pull llama3.1:8b
```

Vérifie que le serveur répond :

```bash
curl http://localhost:11434/api/tags
```

## Brancher Ollama à Eldir

Dans `backend/.env` (ou ton fichier d'env de prod), ajoute :

```bash
# URL du serveur Ollama vu DEPUIS le container backend Eldir
OLLAMA_BASE_URL=http://host.docker.internal:11434

# Modèle utilisé par défaut pour les transformations
OLLAMA_DEFAULT_MODEL=llama3.2

# Timeout (60s par défaut, augmente pour les gros résumés)
OLLAMA_TIMEOUT_SECONDS=60
```

Notes selon ton setup :

| Setup | `OLLAMA_BASE_URL` |
|---|---|
| Ollama sur l'host, Eldir dans Docker Compose dev | `http://host.docker.internal:11434` |
| Ollama dans un service Docker Compose voisin (ex. `ollama:`) | `http://ollama:11434` |
| Ollama sur une autre machine du réseau local | `http://192.168.x.x:11434` |
| Ollama sur l'host, Eldir directement (sans Docker) | `http://localhost:11434` |

Redémarre le backend :

```bash
docker compose -f docker-compose.dev.yml restart backend
```

## Vérifier dans l'UI

Va dans **Settings > Ollama · local**. Tu dois voir :

- `enabled: ✓ oui`
- `reachable: ✓ accessible`
- `default_model: llama3.2`
- `models: llama3.2, ...` (liste de tes modèles installés)

Si `reachable: ✗ inaccessible`, vérifie :
1. `curl <OLLAMA_BASE_URL>/api/tags` depuis l'host fonctionne
2. Le container backend peut bien atteindre cette URL (problème courant : `localhost` dans le container ne pointe pas vers l'host — utiliser `host.docker.internal`)
3. Le firewall n'est pas en train de bloquer le port 11434

## Utilisation depuis l'UI

**Playground** : la page Settings > Ollama propose un mini playground pour tester les 3 modes :

| Mode | Cas d'usage |
|---|---|
| **Masquer secrets** | Colle un `.env` ou un fragment de code avec tokens → récupère la version avec `[REDACTED_TOKEN]`, `[REDACTED_EMAIL]`, etc. Puis copie le résultat dans ta session Claude. |
| **Anonymiser PII** | Colle un export contenant noms / IDs / entreprises → récupère la version avec `Personne A`, `USER_1`, `Entreprise X`. Garde la cohérence (même personne → même placeholder). |
| **Résumer** | Colle un gros fichier ou un log → récupère un résumé 10 lignes max qui garde les détails techniques importants. Économie massive de tokens. |

## Utilisation depuis Claude (V2)

V1 = utilisation **manuelle** : tu transformes via le playground, tu copies, tu colles dans ta session.

V2 (prévu) : Claude pourra appeler `POST /api/v1/ollama/transform` lui-même comme un outil (MCP-like). Ça permettra par exemple de l'instruire avec un sub-agent dédié : *"avant de me montrer un fichier de plus de 5k tokens, fais-le résumer par Ollama d'abord"*. Le ROADMAP V2 prévoit aussi un sub-agent type `OllamaSubAgent` exposé directement dans le Mission Template.

## Comment ça marche techniquement

```
[UI Settings > Ollama]
    │ POST /api/v1/ollama/transform {text, mode}
    ▼
[FastAPI ollama.py]
    │
    ▼
[OllamaService.transform()]
    │ system_prompt = MODE_PROMPTS[mode]  (mask/anonymize/summarize)
    │ POST {OLLAMA_BASE_URL}/api/generate {model, prompt, system, stream:false}
    ▼
[Ollama local]                                          ┌─ Anthropic ─┐
    │                                                   │             │
    └─► retourne le texte transformé ──────► [UI] ──────► (manuel)    │
                                                        │  copy/paste │
                                                        └─────────────┘
```

Les system prompts utilisés sont définis en haut de `backend/app/services/ollama_service.py`. Si tu veux les modifier, c'est juste du Python à l'heure actuelle.

**À venir** : les déplacer dans `backend/app/data/system_prompts/` pour qu'ils deviennent éditables depuis **Settings > Prompts** comme le `template_generator`. C'est dans la dette V2.

## Choisir un modèle

| Modèle | Taille | Vitesse | Précision | Cas d'usage |
|---|---|---|---|---|
| `llama3.2` (3B) | 1.3 GB | Très rapide | Bonne pour mask/anonymize | Défaut recommandé |
| `llama3.1:8b` | 4.7 GB | Moyen | Meilleure pour résumés | Si tu veux des résumés de qualité |
| `qwen2.5-coder:7b` | 4.4 GB | Moyen | Excellent sur code | Si tu masques surtout du code |
| `phi3:mini` (3.8B) | 2.3 GB | Rapide | Variable | Alternative à llama3.2 |

Tu peux changer le modèle par défaut via `OLLAMA_DEFAULT_MODEL` ou override par requête.

## Limites V1

- **Pas de cache** : chaque transformation refait un appel à Ollama. Pour des transformations identiques répétées, c'est gaspillé.
- **Pas de streaming** : on attend la réponse complète. Pour des résumés longs, ça peut prendre ~10-30s.
- **Pas d'auto-routing** : tu choisis manuellement le mode à chaque fois. V2 prévoit un sub-agent intelligent qui décide tout seul.
- **Pas de "dual backend"** : on n'utilise pas Ollama pour piloter une session Claude entière (cf. ROADMAP Phase 6 point 2). Le SDK Claude reste le seul orchestrateur de session. Trop de surface pour V1.
- **Coûts non capturés dans Costs** : Ollama tourne en local, pas de coût USD. Le dashboard Costs ne le mesure donc pas.

## Voir aussi

- [`architecture.md`](./architecture.md) — où s'insère Ollama dans la stack
- [`ROADMAP.md`](../ROADMAP.md) — Phase 6 et 7
- Site officiel Ollama : <https://ollama.com>
- Liste des modèles : <https://ollama.com/library>
