# Connecter GitHub à Eldir

> Phase 1. Authentification par **Personal Access Token (PAT)**.
> OAuth Device Flow ajouté en Phase 3 (multi-provider).

## Créer un PAT

1. Va sur [github.com/settings/tokens?type=beta](https://github.com/settings/tokens?type=beta) (PAT « fine-grained », recommandé).
2. Clique **Generate new token**.
3. Permissions :
   - **Repository access** : `All repositories` ou seulement celles que tu veux exposer à Eldir.
   - **Repository permissions** :
     - `Contents` → Read and write
     - `Pull requests` → Read and write
     - `Metadata` → Read-only (sélectionné automatiquement)
   - **Account permissions** :
     - `Email addresses` → Read-only (optionnel)
4. Expiration : à toi de voir (30 jours minimum recommandé, 90 jours pour un projet personnel).
5. Copie le token `github_pat_…` immédiatement (GitHub ne le réaffiche jamais).

## Le configurer dans Eldir

Va sur **Settings > Git** (ou `/settings/git`).

- **GitHub** → colle ton PAT.
- Laisse l'URL d'instance vide (Eldir cible `api.github.com` par défaut).
- Optionnel : ajoute un label pour t'y retrouver (ex. "perso", "boulot").

Le token est **chiffré** (Fernet) avant d'être persisté en base.

## Lister et cloner un repo

1. Va sur **Projects** (ou `/projects`).
2. Clique **+ Ajouter un repo**.
3. Eldir liste tous les repos accessibles via ton PAT (paginé, max 2000).
4. Clique **Cloner** sur celui qui t'intéresse.

Eldir :

1. Récupère les métadonnées du repo (branch par défaut, URL de clone).
2. Clone vers `/var/eldir/workspaces/{user_id}/{repo_slug}/` (volume `eldir_workspaces`).
3. Crée le `Project` en base, lie le workspace path.

Le clone utilise le PAT en injection HTTPS (`x-access-token:<pat>@github.com`).
Aucune clé SSH n'est requise.

## Créer un nouveau repo depuis Eldir

> Phase 1 — UI à venir. L'API est déjà prête.

```bash
POST /api/v1/providers/github/repos
{
  "provider": "github",
  "name": "mon-nouveau-repo",
  "private": true,
  "description": "...",
  "create_project": true
}
```

Si `create_project=true`, Eldir crée le repo distant **puis** le clone et le persiste comme projet.

## Permissions des scopes utilisés

| Action | Scope requis |
|---|---|
| Lister les repos | `repo` ou `Contents: Read` |
| Cloner un repo | `repo` ou `Contents: Read` |
| Créer un repo | `Administration: Write` (sur la cible) ou `public_repo` |
| Créer une PR | `pull_requests:write` |

## Sécurité

- Le PAT n'est **jamais** affiché en clair via l'API d'Eldir. Seuls les 4 derniers caractères sont visibles (`…aB12`).
- Le token est chiffré au repos avec ta clé `ENCRYPTION_KEY` (Fernet, AES-128-CBC + HMAC).
- En cas de fuite, **révoque le PAT** sur GitHub puis remplace-le dans Settings > Git.
- Eldir ne stocke aucune information sur tes repos en clair — juste le `full_name` et la branche par défaut.

## Dépannage

### "GitHub API 401: Bad credentials"

Le PAT a expiré ou été révoqué. Régénère-le et mets-le à jour dans Settings > Git.

### "GitHub API 403: Resource not accessible"

Le scope du PAT est trop restrictif. Régénère-le avec `Contents: Read and write` minimum.

### Le clone échoue avec "Permission denied"

Vérifie que le PAT a accès au repo en question (côté GitHub, dans les permissions du token).

### Eldir tourne sur un VPS et le clone est lent

Normal — le clone passe par HTTPS via le tunnel du container. Pour de gros repos, la première fois prend du temps. Eldir est **idempotent** : si le clone échoue, relance ; si le clone réussit, le repo n'est pas re-cloné.
