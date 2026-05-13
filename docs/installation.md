# Installation — Eldir

> Phase 1. Installation mono-utilisateur. Multi-user en V2.

## Prérequis

- Docker 24+ et docker compose v2
- `curl`, `python3` (≥ 3.10) — utilisés par le script d'install
- Node.js ≥ 18 (pour `npx`) **si tu veux le mode "génération automatique du token Pro/Max"**
- Un compte Claude **Pro** ou **Max** (recommandé) **ou** une clé API Anthropic Console

## Installation guidée (recommandée)

```bash
git clone https://github.com/<owner>/eldir.git
cd eldir
./scripts/install-eldir.sh
```

Le script :

1. Démarre Postgres, Redis, backend FastAPI et frontend Vite via `docker compose -f docker-compose.dev.yml up -d`.
2. Attend que le backend soit prêt.
3. Récupère le **bootstrap token** émis dans les logs du container backend.
4. Te demande email, mot de passe et nom affiché pour l'administrateur.
5. Te propose de lancer `npx -y @anthropic-ai/claude-code setup-token` pour te connecter à ton compte Pro/Max et capturer un token longue durée (1 an). Ce token est **chiffré** (Fernet) avant d'être persisté en base.
6. Te propose, en option, d'ajouter une **clé API Console** en fallback.
7. POST le tout sur `/api/v1/setup/bootstrap` qui crée l'admin et finalise l'installation.

Une fois le script terminé :

- Frontend : http://localhost:5173
- API : http://localhost:8000/api/v1
- Login : l'email et le mot de passe que tu viens de choisir

## Installation manuelle

Si tu préfères ne pas utiliser le script (debug, CI, dev) :

```bash
# 1. Démarrer la stack
docker compose -f docker-compose.dev.yml up -d

# 2. Récupérer le bootstrap token depuis les logs
docker logs eldir-backend 2>&1 | grep ELDIR_BOOTSTRAP_TOKEN
# → ELDIR_BOOTSTRAP_TOKEN=...

# 3. (Optionnel) Générer un token Pro/Max
npx -y @anthropic-ai/claude-code setup-token
# Suivre le flow navigateur, copier la valeur sk-ant-oat...

# 4. POST /api/v1/setup/bootstrap
curl -X POST http://localhost:8000/api/v1/setup/bootstrap \
  -H 'Content-Type: application/json' \
  -d '{
    "bootstrap_token": "...",
    "admin_email": "you@example.com",
    "admin_password": "yourpassword",
    "admin_display_name": "You",
    "claude_credentials": [
      { "kind": "oauth_token", "value": "sk-ant-oat01-...", "label": "Pro/Max" }
    ]
  }'
```

## Authentification Claude — détails

Eldir supporte deux modes, **non exclusifs** :

| Mode | Variable d'env injectée au SDK | Usage |
|---|---|---|
| `oauth_token` (Pro/Max) | `CLAUDE_CODE_OAUTH_TOKEN` | Prioritaire. Consommation imputée sur ton abonnement Pro/Max. |
| `api_key` (Console) | `ANTHROPIC_API_KEY` | Fallback. Consommation facturée au pay-as-you-go. |

Tu peux configurer **les deux**. Eldir préfèrera toujours le token Pro/Max ; l'API key servira si le token expire ou est révoqué.

### Générer un token Pro/Max

Le script d'install détecte automatiquement le binaire `claude` :

1. Si `claude` est déjà dans ton `$PATH` (installé via `curl -fsSL https://claude.ai/install.sh | bash` ou `npm i -g @anthropic-ai/claude-code`), il l'utilise directement.
2. Sinon, si `npx` est dispo, il lance `npx -y @anthropic-ai/claude-code setup-token` (téléchargement éphémère).
3. Sinon, il te propose de coller un token déjà généré.

Manuellement :

```bash
# Si claude est installé globalement
claude setup-token

# Sinon (ponctuel)
npx -y @anthropic-ai/claude-code setup-token
```

Cette commande :

1. Ouvre un onglet sur claude.ai.
2. Te demande d'autoriser le CLI Claude Code.
3. Affiche un token long durée `sk-ant-oat01-...` (valable ~1 an).

⚠️ Doit être lancée sur une machine **avec un navigateur**. Si Eldir tourne sur un VPS headless, génère le token sur ta machine de bureau puis colle-le dans le script ou dans Settings > Claude.

### À propos du CLI dans le container backend

Le SDK Python `claude-agent-sdk` **bundle son propre binaire `claude`** ; il n'a strictement pas besoin du CLI Node pour fonctionner. L'image Docker d'Eldir installe quand même `@anthropic-ai/claude-code` globalement pour :

- pouvoir exécuter `docker exec eldir-backend claude --version` (debug)
- override le binaire bundlé via `ClaudeAgentOptions(cli_path=...)` si on veut tester une version plus récente
- offrir `claude setup-token` depuis l'intérieur du container si besoin

Tu peux désactiver cette install en commentant le bloc `npm install -g` dans [`backend/Dockerfile`](../backend/Dockerfile) (gain ~250 MB sur l'image finale).

### Modifier les credentials plus tard

UI : http://localhost:5173/settings/claude

- Remplacer le token Pro/Max (utile à l'expiration)
- Ajouter / remplacer la clé API
- Supprimer un credential

## Variables d'environnement

Voir [`backend/.env.example`](../backend/.env.example).

Critiques en prod :

- `JWT_SECRET` — régénérer en prod
- `ENCRYPTION_KEY` — clé Fernet, **ne jamais perdre** (sinon les credentials chiffrés deviennent illisibles)
- `DATABASE_URL`, `REDIS_URL` — pointer vers tes services
- `WORKSPACES_ROOT` — où Eldir clone les repos et crée les worktrees

## Réinitialiser l'installation

⚠️ Détruit l'admin, tous les credentials, et toutes les sessions.

```bash
docker compose -f docker-compose.dev.yml down -v
```

Puis relancer `./scripts/install-eldir.sh`.

## Dépannage

### Le script ne trouve pas le bootstrap token

```bash
docker logs eldir-backend 2>&1 | grep ELDIR_BOOTSTRAP_TOKEN
```

S'il n'apparaît pas, c'est que le backend a déjà passé le bootstrap (un admin existe en DB).
Soit tu te connectes avec ses credentials, soit tu réinitialises (voir ci-dessus).

### `npx` indisponible

Installe Node.js ≥ 18 ou génère le token sur une autre machine et colle-le dans le prompt.

### Le token Pro/Max a expiré

Va dans Settings > Claude depuis l'UI et remplace-le.
