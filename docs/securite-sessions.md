# Ce qu'une session voit

Une session Eldir est un process `claude` lancé par le backend, en
`bypassPermissions`. Elle exécute donc des commandes sans demander
d'autorisation, sur des consignes qui ne viennent pas toutes de John : la
surface d'agent externe (`/api/mcp/`) sert à transmettre des suggestions et des
tickets écrits par des utilisateurs de La Boutique. Ce texte n'est pas fiable,
et une injection de prompt y est un scénario normal, pas un cas limite.

Ce document liste ce qu'une session peut lire, ce qui lui a été retiré, et ce
qui reste un risque accepté. Le modèle de menace est simple : **tout ce qu'une
session voit, considère-le comme public.**

Une session s'exécute dans l'un de deux modes (`SESSION_RUNTIME`, cf.
[`deployment.md`](./deployment.md)). En **`conteneur`**, le défaut depuis la
Phase 6 bis, le CLI de chaque session tourne dans son propre conteneur. En
**`processus`**, il tourne dans le conteneur du backend, comme avant cette
phase. Ce document dit ce qui vaut dans chacun. Le mode `processus` n'a rien
fermé de ce qui suit, ni sur le disque ni sur le réseau : il existe pour les
machines dont le backend n'a pas de démon Docker joignable, et ce n'est pas un
mode sûr. Sur le compose de prod, une session en `processus` hérite en plus de
`DOCKER_HOST` et du réseau `docker-api` du backend, donc elle peut faire créer
par le proxy de socket un conteneur privilégié, soit root sur l'hôte (création
mesurée, héritage et root déduits, pas essayés : cf. « Le proxy de socket ») ; si
tu dois retomber sur `processus`, retire d'abord `DOCKER_HOST` et le
rattachement du backend à `docker-api`.

**Le mode `conteneur` isole une session du disque des autres projets, pas du
backend.** Le backend lance git dans des dossiers que la session écrit, et git
exécute ce qu'il y trouve (risque nº 3, fermé en mode `conteneur` pour git depuis
le 2026-11-12, mais git est le vecteur qui a été essayé, pas forcément le seul) ;
et le proxy de socket, par lequel le backend crée les conteneurs, ne le sépare
pas de root sur l'hôte (« Le proxy de socket »). Une session qui fait exécuter du
code au backend obtient donc tout ce que le backend a. Tant que le proxy de
socket est ouvert, et le risque nº 3 en mode `processus`, **n'héberge pas sur la
même instance un projet sensible et un projet alimenté par des tickets
publics.**

## Son environnement

Le SDK Claude transmet au process de la session l'environnement du backend en
entier (`inherited_env` dans `subprocess_cli.py`), et `options.env` est fusionné
par-dessus plutôt qu'à la place. Eldir ne choisit donc pas ce qu'il donne : il
écrase nommément ce qu'il retire, c'est le rôle de
`env_a_masquer_pour_cli()` dans `app/core/config.py`.

**Masqué** (valeur vide) : tous les champs de `Settings`, c'est-à-dire tout ce
qu'Eldir lit dans l'environnement. La liste se dérive des champs eux-mêmes, donc
un secret ajouté demain à la configuration est couvert sans qu'on y pense. Les
plus importants :

| Variable | Ce qu'elle donnait à une session |
|---|---|
| `JWT_SECRET` | Forger un jeton de connexion (aucun claim `kind`, donc accepté par `decode_session_token`) et appeler l'API en tant que John, `allow_publish` compris. **La porte de publication tombait sans qu'une seule commande git passe devant le hook.** |
| `ENCRYPTION_KEY` | Déchiffrer les credentials Git stockés, de tous les projets. |
| `DATABASE_URL` | Lire et écrire la base directement, donc contourner toute règle applicative. |
| `GITHUB_OAUTH_CLIENT_SECRET` | Se faire passer pour l'OAuth App d'Eldir. |
| `TURN_WEBHOOK_SECRET` | Signer de faux pings de fin de tour. |

**Pas masqué, et c'est voulu** : `PATH`, `HOME` et ce qui fait tourner la
toolchain du projet. Une session qui ne peut pas lancer ses outils ne sert à
rien.

**En mode `conteneur`, le masque est un filet et plus la seule garde.** Le SDK
lance l'enrobage (`backend/docker/session/claude-dans-un-conteneur`) avec
l'environnement du backend, mais l'enrobage ne passe au conteneur que ce que sa
commande `docker run` nomme : le credential Claude, le marqueur d'entrée du SDK,
`HOME`, `CLAUDE_CODE_TMPDIR` et les trois variables du projet
(`ELDIR_TOOLCHAIN`, `ELDIR_COLLECTE`, `ELDIR_REMOTE_HOST`).
`JWT_SECRET`, `ENCRYPTION_KEY` et `DATABASE_URL` n'existent donc pas dans le
conteneur, que le masque les ait couverts ou non. `tests/unit/test_enrobage.py`
épingle cette liste. Cela ne dit rien de ce que le backend lance lui-même dans
un dossier que la session écrit : c'est le risque nº 3.

**En mode `processus`, le masque est la seule garde, et elle ne suffit pas.** La
session tourne sous l'uid du backend, dans son espace de PID : le fichier
`/proc/<pid du backend>/environ` lui est lisible, et il porte l'environnement
initial du backend, celui que le masque devait cacher. Un processus qui lit
l'`environ` de son parent ne voit donc pas les valeurs vides que le masque a posées
dans son propre environnement, il voit les vraies. **Mesuré le 2026-11-06 pour un
enfant du même uid** (sur l'hôte, puis dans un conteneur jetable de l'image des
sessions, en uid 1000) : l'enfant, dont la variable était vidée, a relu la valeur
réelle dans l'`environ` de son parent. **Pas essayé dans le vrai conteneur du
backend.** Cela contourne le masque plutôt que de l'affaiblir. Il reste utile pour
ce que le CLI hérite directement, mais ce n'est pas un secret gardé : en mode
`processus`, considère l'environnement du backend comme lisible par la session.

### Risque connu nº 1 : le credential Claude

`ANTHROPIC_API_KEY` ou `CLAUDE_CODE_OAUTH_TOKEN` reste lisible : le CLI de la
session s'authentifie avec. Une session peut donc consommer du crédit Anthropic
au-delà de ce qu'Eldir lui a demandé. C'est la contrepartie directe du fait de
faire tourner le CLI, et il n'y a pas de correctif côté Eldir : il faudrait un
credential par session, ce que l'API ne propose pas.

**Ce qui limite les dégâts** : le suivi de consommation par session, et le
plafond d'alerte (`DAILY_COST_CAP_USD`). La politique maison est l'alerte,
jamais le blocage, donc c'est une détection, pas une garde.

## Son disque

**En mode `conteneur`**, une session voit son worktree, le clone de son projet,
le toolchain et la collecte de son projet, la maison `.claude` de son projet, et
sa propre clé SSH avec un `config` à un seul bloc. La table des montages, avec
les droits et la raison de chacun, est dans
[`sessions.md`](./sessions.md#ce-quune-session-voit-de-son-disque). Rien d'autre
du disque du serveur n'y est monté : ni la base, ni le volume des clés SSH du
backend, ni le socket du démon.

**En mode `processus`**, elle voit tout le disque du conteneur du backend :

| Volume | Ce qu'une session y trouve |
|---|---|
| `/var/eldir/workspaces` | **Les clones et worktrees de tous les projets**, pas seulement le sien. |
| `/var/eldir/toolchains` | Les SDK installés. Sans intérêt pour un attaquant. |
| `/home/eldir/.claude` | Les transcripts du CLI, donc les conversations des autres sessions. |
| `/home/eldir/.ssh` | **Les clés SSH des machines de projet**, celles qu'Eldir génère pour le bouton « Connecter au serveur ». |

### Risque connu nº 2 : l'isolement entre projets

**Fermé en mode `conteneur`, pour ce que la session voit elle-même. Ouvert en
mode `processus`**, où une session d'un projet lit le code d'un autre, ses
transcripts et la clé SSH de sa machine, comme avant. Même en mode `conteneur`,
un chemin passait par le backend : c'est le risque nº 3, fermé depuis pour git.

**Ce qui est fermé.** Une session ne voit ni le worktree, ni le clone, ni le
toolchain, ni la maison `.claude` (donc ni les transcripts), ni la clé SSH, ni
l'inventaire de machines d'un autre projet. Le `config` SSH du backend porte les
machines de tous les projets ; la session reçoit un `config` à un seul bloc.

**Comment.** Un conteneur par session, dont chaque montage est un sous-chemin de
volume (`volume-subpath`) : le dossier du worktree de la session, pas le volume
des workspaces. Le voisin n'est pas refusé, **il n'existe pas** dans l'univers
de la session. Une règle qui refuse se négocie par injection de prompt ; un
fichier absent ne se négocie pas.

Trois tests sur un vrai démon (`tests/integration/test_isolement_sessions.py`)
le vérifient pour le worktree, la clé SSH et la maison d'un autre projet.
Chacun cherche le voisin dans tout le conteneur et exige qu'il n'y soit pas, au
lieu de constater qu'une lecture échoue. Chacun a été vérifié par mutation :
monter plus large fait tomber l'assertion d'absence. Ils vérifient ce que le
démon fait de ces montages, pas l'enrobage qui les construit, que les chaînes
exactes de `tests/unit/test_enrobage.py` épinglent. Le toolchain et la collecte
relèvent du même mécanisme sans test d'absence à eux : c'est déduit. Le clone
du voisin a été trouvé introuvable une fois, à la main, pas par un test.

**Ce qui reste ouvert**, nommément :

- **Le sortant est complet.** Une session joint n'importe quelle destination
  (cf. « Son réseau »). Le réseau sortant restreint est le second lot de la
  Phase 6 bis, avec sa propre spec.
- **Le credential Claude reste lisible par la session**, puisque son CLI
  s'authentifie avec : c'est le risque nº 1, inchangé.
- **Le clone de son projet est accessible en écriture à ses sessions.** Un
  worktree git a un `.git` qui pointe dans le clone, et `git commit` y écrit ses
  objets : sans ce montage, git ne marche pas (mesuré : « fatal: not a git
  repository »). Entre sessions d'un même projet, c'est le même domaine de
  confiance, elles partagent déjà leur code et leur clé de projet, et c'était
  déjà le cas. Vers le backend, c'est une autre histoire : risque nº 3.
- **Le proxy de socket ne sépare pas le backend de root sur l'hôte** (cf. « Le
  proxy de socket »).
- **Le mode `processus` n'a rien de tout ça.**

### Risque connu nº 3 : le backend exécute git dans ce que la session écrit

**Fermé en mode `conteneur` le 2026-11-12. Ouvert en mode `processus`.** Spec :
[`2026-11-12-risque-3-git-du-backend.md`](./specs/2026-11-12-risque-3-git-du-backend.md).
Git ne prend ses ordres que dans la configuration du dépôt et dans ses hooks ; le
lot retire donc à la session la main sur ces endroits, au lieu de bloquer des
réglages un par un.

- **En lecture seule dans le conteneur de la session** : `<clone>/.git/config`,
  `<clone>/.git/hooks` et `<clone>/.git/modules`. `<clone>/.git` est un montage à
  part, en écriture : un point de montage ne se renomme ni ne se supprime, la
  session ne peut pas le remplacer par un `.git` à elle. Le backend crée `hooks` et
  `modules` s'ils manquent (un montage de sous-chemin absent fait échouer
  `docker run`). Conséquence voulue : dans une session, une commande git qui écrit
  `.git/config` (définir un amont, ajouter un remote) échoue en lecture seule.
- **Chemins fixés par Eldir** : pour le clone d'un projet et pour un worktree de
  session (reconnus à leur chemin, jamais à un fichier qu'ils contiennent),
  `_run_git` passe `GIT_DIR`, `GIT_COMMON_DIR` et `GIT_WORK_TREE`. Le fichier `.git`
  du worktree et les `commondir` (celui de son dossier d'administration, celui du
  clone), que la session peut réécrire, ne décident plus de la config lue.
  En profondeur, il passe toujours `-c core.hooksPath=/dev/null`,
  `core.fsmonitor=false`, `submodule.recurse=false` et
  `diff.ignoreSubmodules=all`.
- **Pas de démarrage sur un `.git` piégé** : si `<clone>/.git`, `.git/config`,
  `.git/hooks` ou `.git/modules` est un lien symbolique, Eldir refuse de lancer la
  session (« Vérifie le clone ou reclone le projet »). Les clones existants ont été
  audités une fois au déploiement de ce lot (instance de John, 2026-11-12 : un seul
  clone, sain). Pour refaire l'audit, en lecture seule, sur chaque clone :
  `find <clone>/.git -type l`, `ls <clone>/.git/commondir`,
  `find <clone>/.git/hooks -type f ! -name '*.sample'` et
  `git -C <clone> config --local --name-only --list`.
- **Le jeton ne part que vers la forge** : l'aide de credential n'est déclarée que
  pour l'origine du provider (`https://github.com`, ou la `base_url` du credential
  Forgejo), jamais pour un hôte lu dans la config du dépôt.

**Mesuré le 2026-11-12** (quatre mesures) :

1. Docker 29.9, image `alpine/git`, uid 1000, volume jetable : écrire, déplacer ou
   supprimer `.git/config` est refusé, écrire dans `.git/hooks` est refusé,
   renommer `.git` est refusé, et `git add` puis `git commit` dans le worktree
   passent. Rejoué ensuite par un test sur un vrai démon
   (`test_une_session_n_ecrit_ni_la_config_ni_les_hooks_du_clone`). Le serveur est
   en Docker 29.8 : déduit, à vérifier après déploiement.
2. Git 2.56, chemins fixés : un `.git` de worktree réécrit vers un dépôt leurre est
   ignoré, et la config lue est celle du vrai clone même quand `commondir` pointe
   ailleurs. Un `commondir` falsifié fait seulement échouer la résolution des refs
   (git échoue, il n'exécute rien).
3. Git 2.56 : avec l'aide de credential réservée à la forge, `git credential fill`
   rend le jeton pour l'hôte de la forge et rien pour un autre hôte.
4. Vrai clone et vrai worktree au chemin d'Eldir (tests) : la config lue reste
   celle du clone, un commit et un push passent toujours.

**Ce qui reste ouvert** : le mode `processus` (la session a l'uid du backend sur le
même disque, aucun montage ne la retient : les chemins fixés et les `-c` réduisent
la surface, ils ne la ferment pas) ; les métadonnées de données (refs, index,
objets, `info/`), inscriptibles mais non exécutées par git ; et un bac à sable
pour le git du backend. Pas mesuré : la chaîne complète contre le vrai backend, ni
le git de son image.

L'historique ci-dessous (ce qui a été mesuré le 2026-11-06, avant ce lot) reste
exact pour le mode `processus` et pour l'état d'avant.

Le conteneur de la session ne voit pas la base. Mais le backend lance `git`
(`status`, `diff`, `add`, `commit`, `merge`, `fetch`) dans le worktree de la
session et dans le clone de son projet, avec son propre environnement, et git
exécute ce que la configuration du dépôt lui dit d'exécuter : un
`core.fsmonitor` dans `.git/config`, les scripts de `.git/hooks`. Une session qui
écrit l'un ou l'autre fait exécuter une commande au backend, à la prochaine
commande git concernée qu'il lance dans cet arbre : un `git status` pour
`core.fsmonitor`, un `git commit` pour un hook `pre-commit`.

**Mesuré le 2026-11-06**, avec le git de l'hôte (2.56.0), sans le backend, dans
un clone et un worktree jetables :

- un `core.fsmonitor` écrit dans le `.git/config` du clone, puis
  `git status` lancé dans le worktree : la commande s'exécute ;
- un hook `pre-commit` écrit dans le `.git/hooks` du clone, puis `git commit`
  depuis le worktree : le hook s'exécute ;
- sans toucher au clone, une session qui ne contrôle que son worktree remplace
  son fichier `.git` par un dépôt à elle qui porte le même `core.fsmonitor` : un
  `git status` dans ce dossier l'exécute aussi.

Dans les trois cas la commande tourne avec l'uid de celui qui lance git, sans
frontière d'uid entre les deux (celui du backend est 1000 par défaut, et la
session tourne en 1000 aussi), et reçoit les variables d'environnement qu'on lui
a passées : une variable factice posée sur la commande git y était lisible.

**Lu dans le code, pas exécuté** : l'endpoint `git-status` lance un
`git status` dans le worktree, et la sync périodique des clones
(`REPO_SYNC_INTERVAL_MINUTES`, 15 minutes par défaut) en lance un dans le clone,
sans geste de personne (`ProjectService.sync_with_remote`, appelée par
`RepoWatcher`).

**Pas mesuré** : la chaîne complète contre le vrai backend ; le git de l'image du
backend (même mécanisme, version plus ancienne : déduit) ; et les autres endroits
où le backend lit ou exécute quelque chose dans un dossier que la session écrit.
Git est le vecteur qui a été essayé, pas forcément le seul.

**Ce que cela veut dire.** Le backend a la base, `JWT_SECRET`, `ENCRYPTION_KEY`,
les volumes de tous les projets et, par le proxy, le démon. Le mode `conteneur`
ferme ce que la session voit directement, pas ce qu'elle peut faire exécuter au
backend. Ce n'est pas nouveau en nature : avant la Phase 6 bis, la session était
déjà dans le conteneur du backend. C'est ce que le conteneur par session ne
sépare pas. Les gardes 1 et 3 plus bas (le masque, le jeton Git) ne couvrent pas ce
chemin : l'environnement du backend, et le jeton d'un `fetch`, sont justement ce
que reçoit la commande lancée par git. Déduit, pas essayé.

**Pourquoi en bloquer trois ne fermerait pas la classe.** Ces trois exemples
ne sont pas les seuls réglages de git qui lancent une commande. Mesuré le même
jour, avec le même git, dans la config du dépôt : `diff.external` (exécuté par
`git diff <ref> -- <fichier>`, pas par `--numstat`), `filter.<nom>.clean` avec
un `.gitattributes` du worktree (exécuté par `git add -A`) et `core.sshCommand`
(exécuté par `git fetch` sur un remote ssh). La documentation de git en
nomme d'autres, que je n'ai pas essayés et qu'une commande du backend
n'atteint pas forcément : `core.pager`, `core.editor`, `credential.helper`,
`filter.<nom>.smudge`. Tous ne sont pas des vecteurs : git réserve
`uploadpack.packObjectsHook` à la config protégée (système, globale, ligne de
commande), et mesuré, il n'est pas exécuté depuis la config d'un dépôt. Et git
n'a pas de réglage qui ignore la config du dépôt, alors que `GIT_CONFIG_GLOBAL`
et `GIT_CONFIG_NOSYSTEM` le font pour le global et le système (lu dans la
documentation de git, pas essayé).

Passer `-c core.fsmonitor=false -c core.hooksPath=/dev/null` arrêterait donc les
trois exemples du début et laisserait la classe ouverte, et celui qui
l'appliquerait croirait le problème réglé. Une liste noire suit l'évolution de
git, pas celle de nos tests.

**Ce qu'il faudrait** : une réponse d'architecture. Soit le backend ne lance pas
git dans un arbre qu'une session peut écrire, soit il le lance dans un bac à
sable (par exemple un conteneur sans l'environnement du backend, sans la base ni
le proxy, avec le dépôt monté). Le lot du 2026-11-12 en a pris une
troisième pour la configuration et les hooks, en mode `conteneur` : le backend
lance toujours git dans l'arbre, mais ce que git y obéit (config, hooks) est en
lecture seule pour la session. Le bac à sable reste la suite, à faire si une
version de git ajoute un tel endroit, et le mode `processus` reste ouvert. Tant que ce mode
existe, n'héberge pas sur la même instance un projet sensible et un projet
alimenté par des tickets publics, avec ou sans conteneur par session.

**Ce qui limite les dégâts** : le `.env` du backend n'est pas monté dans les
worktrees, et la case « Ce projet reçoit des consignes de l'extérieur » du
Mission Template refuse l'accès SSH aux projets alimentés par du texte non
fiable, y compris à leurs sessions déjà ouvertes.

## Son réseau

**En mode `conteneur`**, la session est sur le réseau dédié `eldir-sessions`, qui
n'a de route vers aucun réseau du compose : ni celui de Postgres et Redis, ni
celui du proxy de socket. Mesuré le 2026-11-06 sur deux réseaux jetables bâtis
comme ceux du compose : depuis le réseau des sessions, un service de l'autre
réseau ne répond pas à son IP (délai de 4 s) et son nom n'est pas résolu ; le même
test depuis l'autre réseau se connecte. La session ne joint donc ni la base ni
Redis.

Son accès sortant, lui, est complet. Mesuré : depuis ce réseau, une connexion TCP
vers `1.1.1.1:443` et vers `github.com:443` aboutit. Le hook `PreToolUse` filtre
des commandes, pas des destinations. Elle peut donc joindre n'importe quoi.

C'est ce qui rend l'exfiltration plus grave que la publication : refuser
`git push` n'empêche pas un `curl` vers l'API GitHub avec un jeton trouvé dans
un fichier.

**En mode `processus`**, la session est dans le conteneur du backend : elle joint
tout ce qu'il joint, Postgres, Redis et Internet, et le proxy de socket (déduit
du compose, où le backend est sur le réseau `docker-api`) ; ce que ça vaut est
dit en tête de ce document.

## Le proxy de socket

Le backend doit pouvoir créer les conteneurs des sessions. Il ne monte pas le
socket du démon : `docker-proxy` (`docker/docker-proxy/`, une image de l'amont,
`tecnativa/docker-socket-proxy`, à un réglage près) le monte à sa place et ne
transmet que les pans de l'API que ses variables ouvrent.

**Le proxy ne sépare pas le backend de root sur l'hôte.** Mesuré contre le vrai
démon : `POST /containers/create` avec `Privileged: true` et
`Binds: ["/:/hote"]` répond 201. `docker inspect` montre le conteneur
privilégié qui monte la racine, jamais démarré, supprimé aussitôt. Le proxy
filtre les chemins de l'API, pas le contenu des requêtes : créer un conteneur
étant permis, la requête peut en demander un qui monte la racine de la machine,
ou qui rejoint n'importe quel réseau. Déduit, pas fait : le démarrer est permis
par les mêmes réglages (`CONTAINERS` et `POST`), et un conteneur privilégié qui
monte `/` est root sur l'hôte. Filtrer le contenu des requêtes demanderait un
autre outil, qui n'est pas dans ce lot.

**Ce qu'il achète, et c'est tout** :

- pas d'`exec` dans un conteneur : démarrer un exec répond 403 (mesuré) ;
- pas de swarm ni de secrets : refusés par la configuration de l'image (lu, pas
  mesuré un par un) ;
- pas de manipulation du réseau : connecter un conteneur à un réseau répond 403
  (mesuré) ;
- pas de `info`, pas de liste des volumes, pas de construction d'image (403,
  mesuré) ;
- le socket du démon n'est jamais dans le système de fichiers du backend : une
  évasion de ce conteneur n'hérite pas d'un socket ouvert.

Ce qu'il laisse passer, mesuré : lire l'environnement, les journaux et les
fichiers de n'importe quel conteneur de la machine, pas seulement ceux des
sessions, y écrire un fichier, le redémarrer, le tuer, le supprimer. Et, par
`IMAGES`, lister, télécharger depuis un registre, exporter, étiqueter, charger et
pousser des images (mesuré ; en supprimer aussi, lu dans le modèle de l'image,
non mesuré). L'image de l'amont ouvre en plus d'office `_ping`, `version` et
`events`, le flux des événements du démon, tous conteneurs confondus.

**Pourquoi seuls `docker-proxy` et `backend` sont sur le réseau `docker-api`.**
Créer un conteneur par ce proxy équivaut à être root sur la machine (la création
est mesurée, 201 ; root une fois le conteneur démarré est déduit, pas essayé), et
le proxy n'a pas d'authentification : la vraie garde est l'ensemble des
conteneurs qui peuvent le joindre. Caddy, le frontend, Postgres et Redis restent sur le réseau
par défaut. Mesuré sur une réplique jetable de ce câblage (pas sur la vraie
stack) : depuis le réseau par défaut, l'IP du proxy ne répond pas et son nom
n'est pas résolu ; le backend, lui, le joint. `test_seul_le_backend_joint_le_proxy_de_socket`
épingle le compose.

**La conséquence, sans l'adoucir** : un backend compromis est root sur l'hôte.
Avec le risque nº 3 (ouvert en mode `processus`, fermé pour git en mode
`conteneur`), le chemin de la session à root tient en deux étapes (faire
exécuter une commande au backend, puis lui faire créer un conteneur privilégié),
mesurées chacune séparément et jamais enchaînées.

## Ce qui tient face à une injection de prompt

Deux gardes mécaniques, et une troisième qui a été **retirée volontairement**
le 2026-10-30 et qui figure quand même ici, à sa place, parce qu'un document de
sécurité qui ne liste que ce qui tient ne dit pas où se trouve le trou. Ce
document suit l'état réel de chacune.

**Ces gardes lient ce qu'une session atteint elle-même, pas ce qu'elle peut
faire exécuter au backend** : une commande que le backend lance sur sa demande
(risque nº 3) reçoit l'environnement du backend, pas celui de la session.

1. **Le masque d'environnement** (ce document). ✅ En place contre ce que le
   CLI de la session hérite directement, ⚠️ pas contre le risque nº 3 en mode
   `processus` (fermé pour git en mode `conteneur` le 2026-11-12 ; déduit, pas
   essayé : la commande lancée par git reçoit l'environnement du backend), et ⚠️
   contourné en mode `processus` par la lecture de `/proc/<pid du backend>/environ`
   (mesuré pour un enfant du même uid, pas dans le vrai backend : cf. « Son
   environnement »). Sans lui les deux autres seraient décoratives : une session
   se réautorise elle-même. En mode `conteneur`, c'est un filet (cf. « Son
   environnement »).
2. **La porte de publication n'est plus une garde du chemin extérieur.**
   ⚠️ Retirée volontairement le 2026-10-30. `allow_publish` est servi sur la
   surface externe : un jeton d'agent ouvre la publication des sessions de son
   utilisateur, sans geste humain.

   **Décision de John, le 2026-10-30, en toute connaissance du risque.** Il
   veut un agent extérieur autonome de bout en bout, qui publie sans
   l'attendre. L'outil avait été retiré de cette surface le matin même ; il
   l'a remis l'après-midi. Les deux états ont existé dans la même journée, et
   c'est le second qui tient.

   **Ce que le risque est, précisément.** Un agent extérieur lit des comptes
   rendus de sessions. Un compte rendu contient du texte de dépôt : une issue,
   un README, le message d'erreur d'une dépendance, la phrase d'un inconnu. Une
   injection dans ce texte peut donc pousser l'agent à appeler `allow_publish`,
   puis à dispatcher ce qu'il faut pour que la session publie. Un jeton d'agent
   vit dix ans. Le chemin est réel et il n'est gardé par aucun mécanisme.

   **Ce qui reste, et ce sont des mécanismes.** Deux bornes, qui ne dépendent
   d'aucune lecture de prompt :

   - **un jeton n'ouvre que les sessions de son propre utilisateur.**
     `set_publish_allowed` filtre sur `user_id` ; la session d'un autre est
     introuvable, donc refusée ;
   - **le push forcé reste refusé, porte ouverte comprise.** Le hook
     `PreToolUse` le refuse dans tous les cas : ce qui est publié se relit et
     se révoque, un historique réécrit ne se récupère pas.

   S'y ajoute une trace, qui n'est pas une borne mais ce qui rend l'après
   lisible : le libellé du jeton entre au journal à chaque ouverture, donc une
   publication décidée par un agent ne se confond pas avec un geste de John.

   Et une garde voisine, qui tient toujours et qu'il ne faut pas confondre avec
   celle-ci : `_NOTE_AGENTS` interdit au superviseur de lire une ligne de
   `remember` marquée d'un agent comme une demande de John, comme une
   autorisation de publier ou comme une dérogation à ses règles. Elle protège
   le prompt durable du superviseur, pas la surface HTTP, et ce chemin n'a pas
   changé. La ligne porte la marque de son auteur, posée d'après le jeton et
   jamais lue dans le texte, et elle tient sur une seule ligne, donc elle ne
   peut ni ouvrir une ligne sans marque ni en imiter une.

   **Comment refermer, si John change d'avis.** Deux lignes dans
   `app/mcp_http.py` : retirer `"allow_publish"` de la table `OUTILS`, et
   retirer son adaptateur. Une fonction absente ne s'appelle pas. Les tests
   d'alors sont dans l'historique (`a096faa` les retourne, le commit d'avant
   les porte).

3. **Le jeton Git n'est ni sur le disque ni sur une ligne de commande.**
   ✅ En place contre ce qu'une session lit sur le disque ou dans une ligne de
   commande, ⚠️ pas contre le risque nº 3 en mode `processus` (en mode
   `conteneur`, l'aide n'est déclarée que pour la forge, cf. plus haut). Git le demande à un credential
   helper qui le lit dans l'environnement du seul sous-processus concerné, et
   chaque sync assainit les dépôts clonés par une version d'avant.

   **Ce que cette garde ne tient pas** : ce sous-processus est un `fetch` ou un
   `push` du backend, lancé avec `{**os.environ, "ELDIR_GIT_TOKEN": ...}`
   (`WorktreeService._run_git`), et sans jeton il hérite de l'environnement
   entier du backend. Une commande que git exécute depuis la config d'un dépôt
   que la session écrit reçoit cet environnement, jeton compris le temps d'un
   `fetch`, plus `ENCRYPTION_KEY` et `DATABASE_URL`. Déduit de ce code et des
   mesures du risque nº 3, pas essayé contre le vrai backend.

   Un jeton peut en plus être limité à un projet (Settings > Git, champ
   « Portée »), pour qu'une fuite n'expose que le dépôt qu'il sert. **C'est le
   jeton lui-même qui doit être restreint** côté provider : PAT fine-grained
   GitHub limité à ce dépôt, jeton d'accès Forgejo par dépôt. Eldir choisit
   lequel employer, il ne peut pas réduire la portée du secret à la place du
   provider. Sans jeton propre, un projet utilise celui de « tous les
   projets », et la création d'un projet emploie toujours ce dernier,
   puisqu'il n'existe pas encore de projet auquel rattacher un jeton.

Chaque garde a son test, vérifié par mutation : on casse la ligne qu'il prétend
couvrir et on confirme qu'il tombe.

## Signaler une faille

`SECURITY.md`.
