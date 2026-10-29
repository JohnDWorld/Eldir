# Surface d'agent externe

> Conception validée le 2026-10-29. Statut : à implémenter.
> Lots 1 à 3. Le lot 4 (brancher un agent concret) vit hors de ce repo :
> il dépend d'une installation d'agents privée et n'a pas sa place ici.

## Pourquoi

Eldir a déjà un cerveau : la session superviseur, une session Claude sans projet
ni worktree qui pilote les sessions enfants à travers cinq outils MCP
in-process (`list_projects`, `list_sessions`, `dispatch`, `allow_publish`,
`remember`). Ce contrat est le bon. Son seul défaut est de n'être joignable que
de l'intérieur du processus.

Un agent extérieur, quel qu'il soit (assistant personnel sur une messagerie,
orchestrateur maison, autre installation), ne peut donc rien piloter dans Eldir.
Il lui faudrait ou bien reconstruire la logique de dispatch, ou bien conduire
l'interface web à la main. Les deux sont du travail jeté.

Cette conception ouvre le contrat existant sans le dupliquer, et comble d'abord
les deux trous qui le rendraient inutilisable à un agent autonome.

## Ce qui ne change pas

- **La porte de validation humaine reste mécanique.** `git commit`, `git push`
  et `gh pr` sont refusés au niveau du hook `PreToolUse`, pas par une consigne
  de prompt. Un agent externe hérite de ce refus comme le superviseur interne.
  Rien ne sort du serveur sans un geste humain depuis le dashboard.
- **Le superviseur interne reste.** Eldir s'utilise entièrement sans agent
  externe, et c'est ce que fera la grande majorité des installations. La
  surface décrite ici est une porte qu'on ouvre, pas un organe qu'on remplace.
- **Aucune dépendance nouvelle.** `mcp` est déjà dans `uv.lock` (1.27.1), en
  dépendance transitive de `claude-agent-sdk`.

---

## Lot 1 - les deux trous

Ces deux manques sont supportables tant qu'un humain est au clavier. Ils
deviennent bloquants dès qu'un agent travaille seul : il n'a personne pour
contourner le mur à sa place.

### 1.1 Dispatcher deux chantiers sur un même repo

`SupervisorService._resolve_target` réutilise toujours la session projet la plus
récente, et n'en crée une que s'il n'en existe aucune. Impossible donc d'ouvrir
un second chantier parallèle sur le même repo depuis `dispatch` : il faut passer
par la création manuelle d'une session dans l'interface.

L'infrastructure, elle, est déjà là : les git worktrees isolent N sessions sur
un même repo depuis la phase 2. Il ne manque que le choix.

**Changement** : un paramètre optionnel `nouveau_chantier` (booléen) sur
`dispatch`. À `true`, on force `create_and_start` au lieu de réutiliser. La
description de l'outil doit dire quand s'en servir, sinon un agent l'utilisera
soit jamais, soit à chaque tour : *un chantier par sujet indépendant ; la même
session pour la suite d'un travail en cours.*

### 1.2 Écrire à une session qui travaille

Il n'y a pas de file d'attente à construire : `ActiveSession.message_lock`
sérialise déjà les envois d'une même session. Ce qui bloque est ailleurs, et la
route l'écrit noir sur blanc : *« Long-poll style : on bloque jusqu'à fin du
tour »* (`POST /sessions/{id}/messages`). Elle rend déjà `202 Accepted`, mais
après avoir attendu la fin du tour, parfois plusieurs minutes. Le front, en
conséquence, verrouille le champ de saisie pendant tout ce temps.

C'est le geste central pour débloquer un agent, et c'est celui qu'on ne peut pas
faire.

**Changement** :
- la route lance le tour en tâche de fond et rend la main immédiatement ;
- le front n'éteint plus le champ : il affiche le message en attente, grisé,
  sous le fil. Le streaming WebSocket existe déjà pour la suite ;
- **plafond de messages en attente par session.** Un agent parti en boucle
  empilerait sinon des centaines de consignes que personne ne relira. Au-delà du
  plafond, l'envoi est refusé avec un message que l'agent peut lire et
  comprendre, pas un 500.

> Pourquoi un plafond ici alors qu'Eldir n'en met nulle part ailleurs : la
> politique maison est *alerte, jamais blocage*, et elle vise la dépense. Ce
> plafond-là ne protège pas un budget, il protège l'intégrité d'une file. Une
> file sans borne alimentée par un processus automatique n'est pas une file,
> c'est une fuite.

---

## Lot 2 - la surface d'agent

### 2.1 Un seul corps par outil

Les cinq outils sont aujourd'hui des closures définies dans
`SupervisorService._build_mcp_server`, qui capturent `user_id`. Les servir en
HTTP en l'état obligerait à les réécrire, donc à maintenir deux comportements
qui divergeront.

**Changement** : chaque corps sort vers une méthode publique de
`SupervisorService` qui prend ses arguments et rend du texte. Les deux
transports les enveloppent :

- `create_sdk_mcp_server` pour le superviseur interne, inchangé vu de Claude ;
- `FastMCP` pour l'extérieur.

Les schémas d'outils, eux, sont décrits une seule fois et partagés.

### 2.2 Jeton d'agent

L'authentification actuelle est un JWT de session courte, décodé par
`get_current_user_id`. Un agent tourne en continu et ne peut pas se reconnecter
derrière un formulaire.

**Changement** : un jeton d'agent, JWT longue durée signé par la clé existante,
portant `kind="agent"`, le `sub` de l'utilisateur et un `jti`.
`core/security.py` sait déjà le décoder.

Une table `agent_tokens` (migration 0012) : `id`, `label`, `jti`,
`created_at`, `last_used_at`, `revoked_at`. Son unique raison d'être est la
révocation : un jeton longue durée qu'on ne peut pas révoquer est un jeton
qu'on ne peut pas émettre. La dépendance `AgentIdentity` refuse un `jti`
absent ou révoqué.

UI dans Settings : création avec libellé, valeur affichée **une seule fois**,
date de dernier usage, révocation. Documentation dans `docs/agent-externe.md`.

**`origin` des messages.** Un message dispatché porte déjà un `origin`
(`user` / `eldir`) pour que l'interface ne fasse jamais passer une consigne
d'Eldir pour une demande de l'utilisateur. Avec deux cerveaux possibles, cet
`origin` doit porter le libellé du jeton. Sans ça, en relisant son historique,
on ne sait plus lequel des deux a parlé, et c'est précisément l'information
qu'on cherche quand on se demande pourquoi un agent a fait ça.

### 2.3 `/api/mcp/`

`FastMCP(...).streamable_http_app()` monté sous `/api/mcp/`, authentifié par le
`token_verifier` de FastMCP (point d'extension prévu pour ça ; si la version
verrouillée ne l'expose pas encore, un middleware ASGI devant l'app, et on
remonte la version au prochain passage).

Même outils, mêmes descriptions, même refus de publication que le superviseur
interne. La seule différence est le transport.

### 2.4 `list_projects` enrichi

L'outil rend aujourd'hui nom, identifiant, provider, dépôt et branche par
défaut. Suffisant pour choisir une cible quand un humain dit de quel projet il
parle.

Insuffisant pour un agent censé relancer sur un projet oublié : rien dans cette
sortie ne dit qu'un projet dort. Il n'y a pas de notion d'oubli faute de date.

**Changement** : on ajoute à la sortie existante la dernière activité et le
travail non publié qui attend (`dernière activité : il y a 12 j · 2 commits non
poussés`). Pas de sixième outil : la question « quoi avancer » et la question
« quel projet » sont la même, et deux outils qui se consultent toujours
ensemble sont un outil.

`list_sessions` porte déjà ce qu'il faut pour le reste : l'état de la session
(`blocked`, `waiting_input`) et le compte rendu `<cr>` du dernier passage, avec
son `RESTE`.

### 2.5 Ping de fin de tour, en HTTP

`dispatch` rend la main immédiatement et la session enfant travaille en tâche de
fond. Son `STOP` réveille alors le superviseur, qui lit le compte rendu et
décide de la suite. Ce réveil est **en mémoire** (l'ensemble `_pending`), donc
inaccessible à un processus externe.

Un agent externe, sans ce signal, n'apprend la fin d'un travail qu'à sa
prochaine occasion de regarder. Il avance alors d'un pas par réveil au lieu
d'enchaîner les étapes, ce qui annule l'essentiel de l'intérêt d'un agent qui
travaille pendant qu'on fait autre chose.

**Changement** : à la fin d'un tour dispatché, en plus du ping interne, un
`POST` signé en HMAC vers une URL configurée, avec
`{session_id, projet, état, cr}`.

- URL et secret en variables d'environnement, pas en table : il y a un abonné.
  Quand il y en aura deux, ce sera le moment d'une table, pas avant.
- Échec journalisé, jamais bloquant : la session enfant a fini son travail, un
  webhook injoignable ne doit pas transformer ça en échec.
- Signature HMAC sur le corps, pour que l'abonné sache que le ping vient bien
  d'Eldir.

---

## Lot 3 - finition publique

Eldir est un projet ouvert destiné à durer et à fédérer. Ces manques ne gênent
personne aujourd'hui parce que personne d'extérieur n'a encore essayé de
contribuer, et c'est exactement le problème.

- `CODE_OF_CONDUCT.md` (Contributor Covenant 2.1).
- `.github/pull_request_template.md` et `.github/ISSUE_TEMPLATE/` (anomalie,
  proposition).
- CI Lighthouse sur PR, seuil PWA > 90, annoncé dans le ROADMAP depuis la
  phase 0.
- ROADMAP remis à jour. Il annonce aujourd'hui `CONTRIBUTING.md` et
  `docs/providers/forgejo.md` comme manquants alors que les deux existent, et
  une roadmap qui ment sur son propre état est pire qu'une roadmap absente :
  elle envoie un contributeur écrire ce qui est déjà écrit.

---

## Hors périmètre

- **Aucun plafond de dépense autonome.** Un agent externe qui dispatche brûle
  des tokens sans qu'un humain regarde. La politique du projet est explicite et
  tranchée : *alerte uniquement, jamais de blocage*. L'alerte de budget
  existante (seuil par session, non bloquante) reste la seule garde. C'est un
  risque accepté, pas un oubli.
- **Pas de file de messages durable.** Le plafond du lot 1.2 borne une file en
  mémoire. Un redémarrage du backend perd les messages en attente, comme il perd
  déjà les sessions actives, qu'il faut reprendre.
- **Pas d'autorisation fine par outil.** Un jeton d'agent donne les cinq
  outils ou rien. Un jeton en lecture seule serait utile le jour où un agent
  tiers, non maîtrisé, se branche. Ce jour-là, pas avant.

## Tests

- `nouveau_chantier` ouvre bien une seconde session sur le même projet, avec son
  propre worktree, et sans `nouveau_chantier` on réutilise.
- Un message envoyé à une session occupée rend la main tout de suite, et le tour
  part quand le précédent finit.
- Le plafond refuse le message de trop avec un texte lisible.
- Un jeton révoqué est refusé ; un jeton valide passe ; un JWT de session
  ordinaire ne passe pas sur `/api/mcp/`.
- Les cinq outils rendent le même texte par les deux transports : c'est la
  garantie qu'il n'y a qu'un comportement. Un test par outil.
- Le webhook de fin de tour part avec une signature vérifiable, et son échec ne
  fait pas échouer le tour.
- La publication reste refusée par `/api/mcp/` comme en interne.
