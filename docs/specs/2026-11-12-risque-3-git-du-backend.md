# Le backend ne lit plus de git ce qu'une session écrit

> Conception du 2026-11-12, lot demandé par John après la PR #56. Statut : à
> implémenter. Ferme, en mode `conteneur`, le risque nº 3 de
> [`securite-sessions.md`](../securite-sessions.md) pour ce que git exécute.

## Pourquoi

Le backend lance git (`status`, `diff`, `add`, `commit`, `push`, `fetch`) dans le
worktree d'une session et dans le clone de son projet. Git exécute ce que la
configuration du dépôt lui dit d'exécuter. Une session qui écrit cette
configuration fait donc exécuter une commande au backend, avec son environnement
et le jeton de la forge. Depuis la PR #56, le superviseur publie seul : ce chemin
ne demande plus aucun geste humain.

`securite-sessions.md` le disait : bloquer des réglages un par un ne ferme pas la
classe. Ce lot ne bloque donc pas des réglages, il retire à la session la main
sur l'endroit où ils vivent.

## Le principe

Git ne prend ses ordres que dans sa configuration (la config du dépôt, celle des
sous-modules, l'extension `worktreeConfig` qui s'active depuis elle) et dans ses
hooks. Les fichiers qu'une session écrit par ailleurs (`.gitattributes`, les
refs, l'index) ne font que désigner des pilotes que seule la configuration
définit : sans config inscriptible, ils sont inertes.

## Ce qui change

### 1. Dans le conteneur de la session : ce que git lit comme des ordres, en lecture seule

L'enrobage (`backend/docker/session/claude-dans-un-conteneur`) monte en plus du
clone, quand il le monte :

| Montage | Mode | Pourquoi |
|---|---|---|
| `<clone>/.git` | écriture, montage à part | un point de montage ne se renomme ni ne se supprime : la session ne peut pas remplacer `.git` par le sien |
| `<clone>/.git/config` | lecture seule | la config du dépôt, d'où viennent `core.fsmonitor`, les filtres, `diff.external`, les URL |
| `<clone>/.git/hooks` | lecture seule | les hooks |
| `<clone>/.git/modules` | lecture seule | là où vivraient les dépôts de sous-modules et leurs configs |

Le backend crée `.git/hooks` et `.git/modules` s'ils manquent avant de démarrer
le conteneur : un `volume-subpath` absent fait échouer `docker run`.

**Mesuré le 2026-11-12** (Docker 29.9, image `alpine/git`, uid 1000, volume
jetable) : écrire, déplacer ou supprimer `.git/config` est refusé, écrire dans
`.git/hooks` est refusé, renommer `.git` est refusé, et un `git add` puis
`git commit` dans le worktree passent. Le serveur est en Docker 29.8 : déduit,
à vérifier par John après déploiement.

### 2. Côté backend : Eldir fixe les chemins de git

Pour un worktree de session (reconnu à son chemin, `<user>/<slug>.<session>`,
jamais à un fichier qu'il contient), `_run_git` passe `GIT_DIR`,
`GIT_COMMON_DIR` et `GIT_WORK_TREE` calculés par Eldir. Le fichier `.git` du
worktree et le `commondir` de son dossier d'administration, que la session peut
réécrire, ne décident plus de la config lue.

**Mesuré le 2026-11-12** (git 2.56) : chemins fixés, un `.git` de worktree
réécrit vers un dépôt leurre est ignoré, et la config lue est celle du vrai
clone même quand `commondir` pointe ailleurs. Un `commondir` falsifié fait
seulement échouer la résolution des refs : git échoue, il n'exécute rien.

En profondeur, pour le mode `processus` et pour ce qui aurait échappé :
`_run_git` passe toujours `-c core.hooksPath=/dev/null -c core.fsmonitor=false`
(déjà en place) et `-c submodule.recurse=false -c diff.ignoreSubmodules=all`.

### 3. Le jeton ne part que vers la forge

L'aide de credential est déclarée pour l'origine de la forge seulement
(`credential.<origine>.helper`, après `credential.helper=` qui vide la liste) :
`https://github.com` pour GitHub, la `base_url` du credential pour Forgejo.
L'origine vient du provider (`origine_git`), jamais de la config du dépôt.

**Mesuré le 2026-11-12** (git 2.56) : avec cette aide, `git credential fill`
rend le jeton pour l'hôte de la forge et rien pour un autre hôte.

## Ce qui reste ouvert

- **Le mode `processus`** : la session tourne avec l'uid du backend sur le même
  disque, aucun montage ne la retient. Les chemins fixés et les `-c` réduisent
  la surface, ils ne la ferment pas.
- **Les métadonnées de données** (refs, index, objets, `info/`) restent
  inscriptibles : git ne les exécute pas.
- **Un bac à sable pour le git du backend** (lancer ses commandes dans un
  conteneur jetable sans l'environnement du backend) fermerait aussi ce que git
  pourrait un jour lire ailleurs. C'est un chantier plus lourd, à faire si une
  version de git ajoute un tel endroit.

## Tests

- Enrobage : les quatre montages, avec les bons modes, seulement quand le clone
  est monté.
- Préparation du conteneur : `.git/hooks` et `.git/modules` existent.
- `_run_git` : préfixe toujours présent ; avec jeton, aide vidée puis déclarée
  pour l'origine seule ; jeton sans origine refusé.
- `git credential fill` réel avec ce préfixe : jeton pour la forge, rien
  ailleurs.
- Vrai clone et vrai worktree au chemin d'Eldir : `.git` du worktree réécrit
  vers un leurre, la config lue reste celle du clone ; un commit et un push
  passent toujours.

## Hors périmètre

Le bac à sable git, le mode `processus`, les tickets de Mission Templates.
