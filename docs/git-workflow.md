# Workflow Git dans une session Eldir

> Phase 1, chantier 5. Permet de matérialiser le travail d'une session Claude en commit + push + pull request, sans quitter Eldir.

## Vue d'ensemble

```
session Claude → édite/écrit dans /var/eldir/workspaces/{user}/{slug}/
                                              │
                                              ▼
                  ┌──────────────────────────────────────────┐
                  │  Topbar de la session :                  │
                  │   [N changes] [commit & push] [open PR]  │
                  └──────────────────────────────────────────┘
                                              │
        ┌─────────────────────────────────────┼─────────────────────────────────┐
        ▼                                     ▼                                 ▼
  GET /sessions/:id/git-status         POST /sessions/:id/commit-push     POST /sessions/:id/pull-request
  (poll auto 5s)                       { message, push? }                 { title, body?, base? }
        │                                     │                                 │
        │                                     ▼                                 ▼
        │                              git add -A                         (commit s'il reste des changes)
        │                              git commit -m …                    git push origin <branch>
        │                              git push origin <branch> (auto)    GitProvider.create_pr(...)
        ▼
  { branch, has_changes, modified, added, deleted, untracked }
```

## Cycle de travail conseillé

1. Pose ta tâche à Claude dans la session → il édite les fichiers via `Write`/`Edit`.
2. La topbar affiche en temps réel `N changes` ou `clean` (refetch toutes les 5s).
3. Quand tu es satisfait :
   - **Commit & Push** : entre un message conventionnel commit ; Eldir stage tout, commit avec l'auteur de l'admin, et push sur la branche courante (l'upstream est défini si nécessaire).
   - **Open PR** : crée la PR directement contre la branche par défaut du repo (configurable via le champ "Base branch"). Eldir commit d'abord ce qui reste de non-commité, puis pousse, puis appelle l'API du provider.

## Détails techniques

### Auteur des commits

Le commit utilise le compte Eldir admin :
- `user.name` = `display_name` ou "Eldir"
- `user.email` = email de l'admin ou `eldir@local`

Ces valeurs sont injectées via `git config user.name/user.email` **localement** au workspace, pas globalement.

### Auth push

L'URL du remote `origin` n'est pas modifiée en base. Pour pousser, Eldir résout l'URL courante du remote puis injecte temporairement le PAT du provider dans une URL ad hoc :

```
https://x-access-token:<PAT>@github.com/owner/repo.git
```

Cette URL n'est utilisée que pour la commande `git push`. Elle n'est jamais persistée sur le filesystem.

### Branche

Eldir push la **branche courante** du worktree, pas systématiquement la branche de session. Si tu as fait un `git checkout` dans un terminal hors Claude, c'est ta branche manuelle qui sera poussée.

### "Rien à commiter"

Si le worktree est clean, Eldir lève une `WorkspaceError` 500 (frontend l'affiche dans le dialog). Aucun commit vide n'est créé.

### PR : head == base

Eldir refuse d'ouvrir une PR si la branche courante == la base. Tu dois soit changer de branche (`git checkout -b feat/x`), soit demander à Claude de créer une branche dédiée.

### PR sur Forgejo

L'API REST de Forgejo est très proche de GitHub. La V1 ne supporte que GitHub via `GitHubProvider`. Forgejo arrive en Phase 3 et la route `/pull-request` fonctionnera dès que `ForgejoProvider.create_pr` sera implémenté.

## Limites Phase 1

- **Pas de signature GPG** : on ne signe pas les commits. À ajouter en Phase 7 (souveraineté).
- **Pas de squash / rebase** : Eldir laisse l'historique brut. La compaction se fait côté plateforme (Squash & Merge).
- **Pas de gestion des conflits** : si `git push` échoue (rebase amont), Eldir remonte l'erreur ; il faut alors résoudre manuellement (Claude peut t'aider à pull/rebase via la session).
- **Pas de PR draft** : la PR est ouverte directement comme "ready for review". Une option `draft: true` viendra plus tard.
- **Pas d'auto-link** des issues : si tu veux référencer une issue, écris `Closes #123` dans le body de la PR à la main.

## Endpoints

| Méthode | Route | Description |
|---|---|---|
| `GET` | `/api/v1/sessions/{id}/git-status` | Branche + compteurs de fichiers modifiés |
| `POST` | `/api/v1/sessions/{id}/commit-push` | Stage all + commit + push (optionnel) |
| `POST` | `/api/v1/sessions/{id}/pull-request` | Commit si nécessaire + push + create PR via provider |
