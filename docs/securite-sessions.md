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

Une session travaille dans son propre worktree, mais le process voit tout le
système de fichiers du conteneur backend. Les volumes montés :

| Volume | Ce qu'une session y trouve |
|---|---|
| `/var/eldir/workspaces` | **Les clones et worktrees de tous les projets**, pas seulement le sien. |
| `/var/eldir/toolchains` | Les SDK installés. Sans intérêt pour un attaquant. |
| `/home/eldir/.claude` | Les transcripts du CLI, donc les conversations des autres sessions. |
| `/home/eldir/.ssh` | **Les clés SSH des machines de projet**, celles qu'Eldir génère pour le bouton « Connecter au serveur ». |

### Risque connu nº 2 : l'isolement entre projets n'existe pas

C'est le trou principal qui reste, et il est structurel : les sessions
partagent le conteneur du backend. Une session d'un projet peut lire le code
d'un autre, ses transcripts, et la clé SSH de sa machine.

**Ce qui limite les dégâts** : le `.env` du backend n'est pas monté dans les
worktrees, et la case « Ce projet reçoit des consignes de l'extérieur » du
Mission Template refuse l'accès SSH aux projets alimentés par du texte non
fiable, y compris à leurs sessions déjà ouvertes. Mais une session reste un
voisin de palier, pas un locataire isolé : elle lit les clés SSH des *autres*
projets dans `/home/eldir/.ssh`.

**Le correctif** est la V2 inscrite au ROADMAP : un conteneur par session, sans
accès à la base, avec un réseau sortant restreint. Tant qu'il n'est pas là,
n'héberge pas sur la même instance Eldir un projet sensible et un projet
alimenté par des tickets publics.

## Son réseau

Une session a un accès sortant complet, et le hook `PreToolUse` filtre des
commandes, pas des destinations. Elle peut donc joindre n'importe quoi.

C'est ce qui rend l'exfiltration plus grave que la publication : refuser
`git push` n'empêche pas un `curl` vers l'API GitHub avec un jeton trouvé dans
un fichier.

## Ce qui tient face à une injection de prompt

Trois gardes, dans cet ordre d'importance. Ce document suit l'état réel de
chacune.

1. **Le masque d'environnement** (ce document). ✅ En place. Sans lui les deux
   autres seraient décoratives : une session se réautorise elle-même.
2. **La publication n'est ouverte que par un geste humain dans le dashboard.**
   ✅ En place. `allow_publish` n'est pas servi sur la surface externe
   (`HORS_SURFACE_EXTERNE` dans `app/mcp_http.py`) : un jeton d'agent ne peut
   pas l'ouvrir, même compromis.
3. **Le jeton Git n'est jamais à portée d'une session.** ✅ En place. Il ne
   touche ni le disque ni la ligne de commande : git le demande à un credential
   helper qui le lit dans l'environnement du seul sous-processus concerné, et
   chaque sync assainit les dépôts clonés par une version d'avant.

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
