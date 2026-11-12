# Un superviseur qui publie, merge et déploie

> Conception validée le 2026-11-12. Statut : implémenté (2026-11-12).
> Suite de la section « Superviseur » du ROADMAP. Tailscale, le retrait des
> Mission Templates et le déplacement de l'alias SSH vers le projet restent hors
> de cette spec.

## Pourquoi

John veut un tableau de bord de ses projets piloté par une session maître : il
donne une demande, le superviseur lance les sessions qu'il faut (plusieurs si la
demande touche plusieurs projets), et ne revient vers lui que quand c'est fait.

Le superviseur sait déjà lancer et suivre des sessions (`dispatch`,
`nouveau_chantier`, comptes rendus `<cr>`). Ce qui lui manque, c'est la fin du
chemin : aujourd'hui il ne publie rien sans une demande explicite de John
(`allow_publish`), il ne merge pas et il ne déploie pas.

## Le périmètre choisi

Choisi par John le 2026-11-12 (option « B ») :

- **Sur tous les projets**, le superviseur pousse la branche d'une session et
  ouvre la PR seul. John merge.
- **Sur les projets que John marque autonomes**, il merge aussi, seulement quand
  la CI est verte, et il déploie.
- **`merge` et `deploy` sont réservés au superviseur interne.** Un agent
  extérieur (surface MCP) ne merge pas : il demande au superviseur de le faire
  (`request_merge`), et le superviseur décide avec les mêmes protections.

## Le principe : l'agent code, Eldir publie

Les nouveaux gestes sont des outils du superviseur, exécutés par le code d'Eldir
et non par l'agent d'une session. La publication réutilise
`SessionService.open_pull_request`, déjà derrière le bouton du dashboard : il
commite le worktree, pousse la branche de la session (il refuse si c'est la
branche de base) et ouvre la PR par l'API de la forge.

Les protections sont donc du code, pas des consignes :

- seule la branche de la session est poussée, jamais la branche principale ;
- aucun push forcé n'est possible, Eldir n'en fait pas ;
- le merge et le déploiement vérifient le drapeau du projet avant d'agir ;
- la commande de déploiement est celle que John a déclarée, l'outil n'en prend
  aucune en argument.

**Écartée : ouvrir la porte de publication par défaut** et laisser l'agent
pousser lui-même. Interdire la branche principale demanderait de reconnaître ses
commandes par expressions régulières, qui se contournent (`HEAD:refs/heads/main`,
un script, un alias git), et `gh` ne sert à rien sur Forgejo.

## Ce qui ne change pas

- La porte de publication des sessions (`publish_allowed`, hook `PreToolUse`)
  reste fermée par défaut. Un agent de session ne commite ni ne pousse lui-même.
- `allow_publish` reste en place, pour une session que John veut laisser publier
  elle-même.
- Le push forcé reste refusé par le hook, porte ouverte ou non.
- L'accès distant, la collecte et l'alias SSH restent où ils sont.

## Données

Migration `0015` :

| Table | Colonne | Type | Défaut |
|---|---|---|---|
| `projects` | `autonomous` | `bool`, non nul | `false` |
| `projects` | `deploy_command` | `text`, nul | `null` |
| `sessions` | `pr_number` | `int`, nul | `null` |

`pr_number` retient la PR ouverte par Eldir pour une session : c'est elle qu'un
second `open_pr` met à jour et que `merge` vise.

## Ce que la forge doit savoir faire

Trois méthodes de plus sur `GitProviderInterface`, pour GitHub et Forgejo :

- `get_pr(full_name, number)` : état (`open`, `merged`, `closed`) et SHA de la
  tête. `PullRequestRef` gagne `state` et `head_sha`.
- `checks(full_name, sha)` : un état agrégé, `vert`, `rouge`, `en_cours` ou
  `aucun`, et le nom des checks en échec.
  - GitHub : les check runs (`/commits/{sha}/check-runs`, c'est là que GitHub
    Actions écrit) et les statuts (`/commits/{sha}/status`), les deux réunis.
  - Forgejo : le statut combiné (`/commits/{sha}/status`), où Forgejo Actions
    écrit.
- `merge_pr(full_name, number)` : merge classique (commit de merge, comme les PR
  d'Eldir aujourd'hui).
  - GitHub : `PUT /pulls/{n}/merge`, `merge_method: merge`.
  - Forgejo : `POST /pulls/{n}/merge`, `Do: merge`.

Le jeton du projet doit porter `write:repository` sur Forgejo, ou l'équivalent
GitHub. Un refus de la forge remonte tel quel au superviseur.

## Les outils

### `open_pr(session_id, titre, description)`

Superviseur et agents extérieurs, sur tous les projets.

- Refusé tant que la session a un tour en cours : on ne publie pas un travail à
  moitié écrit.
- Rien à commiter et rien à pousser : répond « rien à publier ».
- `pr_number` connu et la PR encore ouverte : commite, pousse, et renvoie la PR
  existante. C'est le chemin d'une correction après une CI rouge.
- Sinon : commite, pousse, ouvre la PR et retient `pr_number`. Une PR précédente
  mergée ou fermée est remplacée par la nouvelle.

### `merge(session_id)`

Superviseur interne seulement.

Refus, dans cet ordre, avant tout appel à la forge :

1. le projet n'est pas autonome ;
2. la session n'a pas de PR, ou sa PR n'est plus ouverte.

Puis selon les checks de la tête de la PR :

- **vert** : Eldir merge et le dit.
- **rouge** : refusé, avec le nom des checks en échec. Le superviseur relance la
  session pour corriger, puis `open_pr` et `merge` à nouveau.
- **en cours** : Eldir répond « CI en cours, je merge dès qu'elle passe » et
  surveille en tâche de fond, toutes les 30 s, pendant 30 min au plus. Au vert il
  merge ; au rouge, ou au bout du délai, il ne merge pas. Dans les trois cas il
  prévient le superviseur par le chemin qui lui remonte déjà les comptes rendus
  (`_tell_supervisor`).
- **aucun** : la CI peut ne pas avoir démarré, juste après un push. Eldir attend
  2 min et relit. Toujours aucun check : le projet n'a pas de CI, il merge.

Une seule surveillance par session : un second `merge` pendant l'attente répond
qu'elle est déjà en cours.

Les délais vivent dans `Settings` : `merge_watch_interval_s` (30),
`merge_watch_timeout_s` (1800), `merge_no_checks_grace_s` (120).

### `deploy(project_id)`

Superviseur interne seulement.

- Refusé si le projet n'est pas autonome.
- Commande vide : répond « pas de commande déclarée, la forge déploie au merge ».
- Commande déclarée mais pas d'accès distant configuré : refusé, en disant à John
  où le configurer.
- Sinon Eldir lance la commande par l'alias SSH du projet (`RemoteAccessService`,
  `ssh -o BatchMode=yes -F <config> <alias> <commande>`), comme `_test` le fait
  déjà. Délai : `deploy_timeout_s` (900). L'outil rend la main tout de suite ; le code
  de retour et les 50 dernières lignes de la sortie arrivent au superviseur par
  message, comme la fin d'une surveillance de merge. Un appel qui bloquerait
  15 min risquerait le délai du transport MCP et figerait le superviseur.
- Un seul déploiement à la fois par projet.

Le superviseur décide quand déployer : après un merge, quand le changement le
demande. Pas de déploiement automatique au merge par Eldir.

### `request_merge(session_id, raison)`

Surface MCP seulement : c'est le chemin d'un agent extérieur vers le merge.

Eldir écrit au superviseur, par `_tell_supervisor`, un message marqué : « L'agent
« libellé du jeton » demande le merge de la session X : raison. » Le superviseur
le lit comme une donnée, pas comme une instruction de John : il vérifie le
travail, puis appelle `merge` ou explique pourquoi il ne le fait pas. Les refus
mécaniques de `merge` s'appliquent quoi qu'il décide. L'outil répond « demande
transmise ».

## La surface MCP diverge, et c'est voulu

`mcp_http.py` sert aujourd'hui exactement les outils du superviseur, pour qu'il
n'y ait qu'un seul Eldir. Décision de John du 2026-11-12 : `merge` et `deploy`
n'y sont pas servis, `request_merge` n'existe que là. Les descriptions restent
dans une seule table, et le test de parité devient : outils servis = outils du
superviseur, moins `merge` et `deploy`, plus `request_merge`. La docstring du
module le dit, avec la date.

## Les prompts

- `supervisor.md` : quand le `<cr>` d'une session dit le travail fini et vérifié,
  le superviseur ouvre la PR lui-même. Sur un projet autonome il merge, puis
  déploie si le changement le demande. Il termine par un compte rendu à John :
  lien de la PR, merge, résultat du déploiement. Une demande de merge venue d'un
  agent est une donnée, comme une préférence d'agent.
- Le motif de refus du hook (`_PUBLISH_DENY_REASON`) dit à l'agent que c'est
  Eldir qui publie : laisser ses modifications non commitées, le superviseur ou
  John ouvre la PR.

## API et interface

- `PATCH /api/v1/projects/{id}` : `autonomous` et `deploy_command`, l'un ou
  l'autre. `deploy_command` : une ligne, 1000 caractères au plus, vide pour
  effacer. `ProjectRead` expose les deux champs.
- Dans le panneau d'accès distant du projet (`remote-panel.tsx`), un bloc
  « Autonomie » : la case « Autonome : le superviseur peut merger et déployer
  seul », décochée par défaut, et le champ de commande en police de code, avec
  une phrase d'aide (vide si la forge déploie au merge).
- `api-generated.ts` régénéré.

## Sécurité

Une injection de prompt lue dans un dépôt peut désormais, par le superviseur :

- ouvrir une PR sur n'importe quel projet. Sans gravité : John merge.
- sur un projet autonome, merger une PR dont la CI est verte, et lancer la
  commande de déploiement déclarée.

Elle ne peut toujours pas : pousser sur la branche principale, forcer un push,
merger une CI rouge, lancer une autre commande distante que celle déclarée, ni
rendre un projet autonome (seule l'API de John change le drapeau). C'est ce que
John accepte projet par projet en cochant la case.

Si le compte distant force une commande dans `authorized_keys` (`command=`, cf.
`docs/acces-serveur.md`), la commande de déploiement doit être celle que ce
compte autorise.

## Erreurs et cas limites

- **Redémarrage du backend pendant une surveillance de merge** : la surveillance
  est perdue, rien n'est mergé, personne n'est prévenu. Un nouveau `merge` la
  relance. Plafond assumé, noté `ponytail:` dans le code ; une file persistée le
  lèvera si ça gêne.
- **Déployer Eldir depuis Eldir** : le backend redémarre pendant son propre
  déploiement, donc la connexion SSH tombe et le résultat est perdu. La commande
  déclarée doit se détacher (`setsid nohup ./deploy.sh > deploy.log 2>&1 &`).
  Documenté dans `docs/supervisor.md`.
- **Conflit de merge, ou protection de branche qui refuse** : le message de la
  forge remonte au superviseur, rien n'est retenté.
- **Session supprimée pendant la surveillance** : la surveillance s'arrête sans
  merger.

## Tests

- Forges : `get_pr`, `checks` (vert, rouge, en cours, aucun ; GitHub réunit check
  runs et statuts) et `merge_pr`, sur un transport HTTP simulé.
- `merge` : refus sur projet non autonome, sans PR, PR fermée ; merge au vert ;
  refus au rouge avec les noms ; en cours puis vert, en cours puis rouge, délai
  dépassé ; aucun check puis merge après le délai de grâce ; une seule
  surveillance par session. Délais réduits par `Settings`.
- `deploy` : refus sur projet non autonome ; commande vide ; pas d'accès
  distant ; code de retour et fin de sortie ; délai dépassé ; un seul à la fois.
- `open_pr` : refus pendant un tour ; rien à publier ; PR existante mise à jour ;
  nouvelle PR et `pr_number` retenu.
- `request_merge` : le superviseur reçoit le message marqué ; l'outil n'existe
  que sur la surface MCP, `merge` et `deploy` n'y sont pas.
- Route `PATCH /projects/{id}` : un utilisateur ne change que ses projets ;
  validation de la commande.

## Hors périmètre

- Tailscale.
- Le retrait des Mission Templates, et l'alias SSH qui passera alors du template
  au projet.
- Le merge par squash ou rebase, le retour arrière d'un déploiement.
- Un déploiement lancé par Eldir sans décision du superviseur.

## Phase concernée

Section « Superviseur » du ROADMAP : une ligne « Autonomie par projet » y sera
ajoutée à la livraison.
