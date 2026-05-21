# Connecter Forgejo à Eldir

> Phase 3. Configuration d'un instance Forgejo self-hosted (ou Codeberg).

Forgejo est traité en first-class par Eldir au même titre que GitHub. Toute opération git (list repos, clone, create repo, open PR) passe par `GitProviderInterface` — donc tout marche identiquement, modulo l'URL d'instance.

## Créer un Personal Access Token

1. Sur ton instance Forgejo : **Settings > Applications > Generate new token** (ou `https://{ton-instance}/user/settings/applications`).
2. **Nom** : ex. "Eldir".
3. **Scopes** :
   - `read:user` — lire ton profil
   - `read:repository`, `write:repository` — list/clone/create
   - `read:issue`, `write:issue` — pour les PRs
4. Génère et copie le token immédiatement (Forgejo ne le réaffiche jamais).

## Configurer dans Eldir

Va sur **Settings > Git** (ou `/settings/git`).

- **Provider** : Forgejo
- **Base URL** : URL de ton instance Forgejo, ex. `https://forge.example.org` (sans trailing slash, sans `/api/v1`)
- **Token** : colle ton PAT
- *(Optionnel)* **Label** : ex. "perso", "boulot"

Le token est **chiffré** (Fernet) avant d'être persisté en base.

## Cloner un repo Forgejo

1. Va sur **Projects** (`/projects`).
2. Sélecteur de provider : **Forgejo**.
3. Eldir liste les repos accessibles via ton token.
4. Coche un ou plusieurs repos, clique **Cloner la sélection**.

Le clone côté serveur est fait avec une URL injectée du token (pour permettre les push ultérieurs sans réauth) :

```
https://oauth2:{token}@{base_url}/{owner}/{repo}.git
```

Le token est rotaté/rafraîchi dynamiquement dans l'URL lors des opérations git (fetch/push) — utile si tu changes le PAT dans Settings sans avoir à re-cloner.

## Travailler sur un repo Forgejo

Identique à GitHub :

1. Crée une session sur le projet
2. Discute avec Claude, il modifie les fichiers dans le worktree
3. Commit & push via la topbar de la session
4. **Open PR** → `POST /api/v1/sessions/{id}/pull-request` appelle `ForgejoProvider.create_pr(...)` qui POST sur l'API Forgejo

L'URL de la PR retournée pointe vers ton instance Forgejo.

## Limites connues / résiduels

- **Création de repo Forgejo depuis le dashboard** — pas encore exposée dans l'UI (le backend implémente `ForgejoProvider.create_repo` mais l'UI n'expose le bouton que pour GitHub). Workaround : crée le repo depuis l'interface Forgejo, puis clone-le dans Eldir. À corriger en résiduel Phase 3.
- **OAuth Forgejo** — pas implémenté. Forgejo supporte OAuth2 mais le flux n'est pas branché dans Eldir. PAT uniquement pour V1.
- **Webhooks** — pas (encore) exposés. Pour recevoir les push events Forgejo dans Eldir, c'est V2.

## Codeberg

[Codeberg.org](https://codeberg.org) est une instance Forgejo publique opérée par une association allemande à but non lucratif. Tu peux l'utiliser comme provider Forgejo dans Eldir :

- **Base URL** : `https://codeberg.org`
- **Token** : généré depuis `https://codeberg.org/user/settings/applications`

## Multi-instances

Tu peux configurer **plusieurs credentials Forgejo** avec des base URLs différentes (ton instance perso + Codeberg + l'instance de ta boîte par exemple). Eldir route les opérations vers la bonne instance selon le projet.

## Dépannage

### "Erreur : Forgejo API returned 401"

Token invalide ou révoqué. Régénère-en un et remplace dans Settings > Git.

### "Erreur : Cannot reach Forgejo at {url}"

Base URL incorrecte (typo, trailing slash, ou réseau). Vérifie que `curl {base_url}/api/v1/version` répond.

### Le clone échoue avec "Authentication failed"

Le token n'a pas les scopes requis. Régénère-le avec `read:repository` + `write:repository`.

## Voir aussi

- [`docs/github.md`](../github.md) — l'équivalent GitHub
- [`docs/architecture.md#points-dextension`](../architecture.md) — ajouter un autre provider (GitLab, Gitea, Bitbucket)
- [`docs/extending.md`](../extending.md) — implémenter un nouveau `GitProviderInterface`
