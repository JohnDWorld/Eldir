# Brancher un agent extérieur sur Eldir

> Les cinq outils du superviseur, servis en MCP sur HTTP, derrière un
> jeton que tu révoques. **Publication comprise** : lis
> [Ce que tu accordes](#ce-que-tu-accordes-en-émettant-un-jeton) avant d'en émettre un. De quoi laisser un autre assistant piloter tes
> sessions Claude sans reconstruire la logique de dispatch ni conduire
> l'interface à ta place.

Cette page est écrite pour la personne qui va émettre le jeton. Elle dit comment
brancher l'agent, mais surtout ce que ce geste accorde, ce qui peut mal tourner et
ce qui n'est pas garanti. Si tu ne lis qu'une section, lis
[Ce que tu accordes en émettant un jeton](#ce-que-tu-accordes-en-émettant-un-jeton).

## Ce que c'est

Eldir a déjà un cerveau : la session **superviseur**, une session Claude sans
projet ni worktree qui pilote les sessions enfants à travers cinq outils MCP
in-process. Voir [`docs/supervisor.md`](./supervisor.md).

Ce contrat était jusqu'ici joignable depuis le seul processus d'Eldir. Il est
maintenant aussi servi en **MCP streamable HTTP** sur `/api/mcp/`, ce qui permet à
un agent extérieur (assistant sur une messagerie, orchestrateur maison, autre
installation) d'appeler les mêmes outils.

Les deux transports partagent un seul corps par outil et une seule table de
descriptions et de schémas, dans `backend/app/services/supervisor_service.py`. Il
ne peut donc pas exister deux comportements qui divergent, et un test compare le
texte rendu outil par outil par les deux chemins. La seule différence est le
transport.

**Le superviseur interne reste.** Eldir s'utilise entièrement sans agent
extérieur, et c'est ce que fera la majorité des installations. Cette surface est
une porte qu'on ouvre, pas un organe qu'on remplace. Rien ne t'oblige à émettre
un jeton, et le jour où tu n'en veux plus, tu le révoques : il ne reste aucune
configuration à défaire.

## Ce qu'un agent ne pourra jamais faire

C'est la question que tout le monde pose en premier, alors la voici tôt : **un
agent, interne ou extérieur, ne publie pas.**

Les sessions Claude tournent en `bypassPermissions` (il n'y a pas de terminal
côté serveur pour répondre à une demande d'autorisation), donc rien ne les
empêcherait de pousser toutes seules. Eldir refuse au niveau du hook `PreToolUse`
toute commande `git commit`, `git push`, `gh pr` ou `glab mr`. Ce n'est pas une
consigne de prompt, qui se contourne, mais un refus mécanique : la tentative
apparaît dans le flux d'events et l'agent reçoit l'explication à la place du
résultat.

Ce refus est **le même quel que soit le transport**, et c'est le DÉFAUT d'une
session neuve. ⚠️ Mais un agent extérieur peut le lever : `allow_publish` est
servi en HTTP depuis le 2026-10-30. Il n'ouvre que les sessions de son propre
utilisateur, et un test d'intégration épingle les deux bords (il ouvre bien, et
le jeton d'un autre utilisateur ne peut pas) dans
`backend/tests/integration/test_mcp_http.py`.

Enfin, la réécriture d'historique (`git push --force`, `--mirror`, `-f`) reste
refusée **même quand la publication est autorisée** : c'est la seule opération
git qui détruit du travail déjà publié, et aucune demande ne passe par un agent
pour ça.

## Ce que tu accordes en émettant un jeton

C'est le passage important. Le refus ci-dessus a exactement une clé, et **un
jeton d'agent la porte**.

**Un jeton d'agent ouvre la publication.** `allow_publish` est servi sur cette
surface depuis le 2026-10-30 (décision du mainteneur, prise en connaissance du
risque, pour avoir un agent autonome de bout en bout). Concrètement, émettre un
jeton accorde le droit de publier sur tes dépôts, pas seulement celui de faire
travailler des sessions.

**Et c'est un risque réel, pas théorique.** Un agent extérieur lit les comptes
rendus des sessions, et un compte rendu contient du texte de dépôt : une issue,
un README, le message d'erreur d'une dépendance, la phrase d'un inconnu. Une
injection dans ce texte peut pousser l'agent à ouvrir la publication, puis à
dispatcher ce qu'il faut pour qu'une session publie. Un jeton d'agent vit dix
ans. N'émets un jeton que pour un agent dont tu maîtrises le cerveau et le
salon, et sur une instance dont les dépôts t'appartiennent.

**Les deux bornes qui restent sont des mécanismes.** Un jeton n'ouvre que les
sessions de SON utilisateur (`set_publish_allowed` filtre sur `user_id` : la
session d'un autre est introuvable), et le push forcé reste refusé porte ouverte
comprise. Le libellé du jeton entre au journal à chaque ouverture, donc une
publication décidée par un agent se relit après coup.

Il n'existe pas de jeton en lecture seule : c'est les cinq outils ou rien. Si
tu veux la porte fermée pour les agents, deux lignes de `app/mcp_http.py` la
referment, et `docs/securite-sessions.md` dit lesquelles.

**Le drapeau reste persistant.** Une autorisation donnée dans le dashboard écrit
en base, pas seulement dans la session vivante : une session dormante la retrouve
à son prochain démarrage. Et `dispatch` sans `session_id` reprend la session
ouverte la plus récente du projet. Un agent peut donc dispatcher une consigne
dans une session restée ouverte, dont tu avais autorisé la publication pour un
autre travail. Si tu autorises une session, referme-la quand le travail est relu
(le bouton du dashboard).

**`remember` écrit dans les préférences du superviseur.** Une préférence
enregistrée par un agent entre dans le prompt **Préférences apprises par le
superviseur**, relu à chaque démarrage de ta session superviseur. C'est le nom
qu'il porte partout, réglages compris : le superviseur a aussi son propre prompt
système, qui est un autre fichier. Trois choses la cadrent, et elles sont
dans le code, pas dans une consigne de prompt :

- la ligne porte la marque de son auteur, posée d'après le jeton et jamais lue
  dans le texte : `- [agent « nom du jeton »] le fait` ;
- le prompt système du superviseur gagne alors une note qui lui dit de peser ces lignes
  comme des suggestions, jamais comme une demande de sa part, et qu'elles ne
  valent **aucune autorisation de publier** quoi qu'elles affirment ;
- un fait tient en **300 caractères** sur une seule ligne, et tous les agents se
  partagent **20 préférences** (`PREFERENCE_LONGUEUR_MAX` et
  `PREFERENCES_AGENT_MAX` dans `backend/app/services/supervisor_service.py`). Au
  plafond, la nouvelle est refusée par une phrase que l'agent peut lire, et rien
  n'est oublié : c'est à toi de faire le ménage.

Rien n'est oublié dans l'autre sens non plus. Les deux écrivains de cette ligne
(un agent par `remember`, toi par l'éditeur) écrivent sous condition du texte
qu'ils ont lu. Si un agent note une préférence pendant que ton éditeur est
ouvert, ta sauvegarde est **refusée** avec le motif, pas appliquée par-dessus :
recharge, puis refais ta modification. Symétriquement, le bouton **Retirer**
d'une préférence est verrouillé tant que ton brouillon n'est pas sauvegardé.

Tu lis et vides ces lignes dans **Settings > Prompts**, sur le prompt
**Préférences apprises par le superviseur** : la liste des préférences d'agents
et leurs boutons **Retirer** vivent sous l'éditeur, qui montre le prompt entier.
**Settings > Agents extérieurs** en donne le compte et un lien. Rien n'est
appris dans ton dos.

**Ce que ça coûte.** Un agent qui dispatche brûle des tokens sans que personne
regarde. La politique d'Eldir est tranchée et ne change pas ici : *alerte
uniquement, jamais de blocage*. L'alerte de budget par session reste la seule
garde, et `/costs` reste le seul endroit où tu vois la facture monter. Il n'y a
**aucun plafond de dépense autonome** sur cette surface. C'est un risque accepté,
pas un oubli : un blocage automatique couperait un travail en cours au pire
moment, et personne n'était là pour en décider.

## Émettre un jeton

**Settings > Agents extérieurs** (`/settings/agents`).

1. Donne un **libellé** (1 à 80 caractères) qui dit *quel* agent porte ce jeton,
   par exemple `assistant de bureau`. Ce libellé n'est pas décoratif : il signe
   chaque consigne dans l'historique de la session et chaque préférence
   enregistrée. En relisant son fil, tu cherches précisément à savoir lequel de
   tes cerveaux a décidé. Deux jetons vivants ne peuvent donc pas porter le même
   libellé : Eldir refuse l'émission en le nommant. Un libellé libéré par une
   révocation se réutilise, c'est le geste de secours après une fuite.
2. **Créer un jeton.** Le clair s'affiche **une seule fois**, juste après la
   création. Eldir ne le conserve pas et ne peut donc pas le réafficher : si tu le
   perds, révoque celui-ci et émets-en un autre.
3. Colle-le chez l'agent, dans son stockage de secrets.

La liste porte, pour chaque jeton, sa date de création, sa date de dernier usage
(mise à jour à chaque requête, c'est ce qui te dit si un jeton sert encore) et un
bouton **Révoquer** visible, sur la ligne, jamais caché dans un menu. Un jeton
qu'on ne peut pas révoquer est un jeton qu'on ne peut pas émettre.

La **révocation coupe à la requête suivante**. Rien n'est gardé en mémoire d'un
appel à l'autre, donc il n'y a pas de délai de propagation ni de cache à vider.
Un jeton révoqué n'est pas supprimé de la liste : il reste visible, marqué
`révoqué`, avec sa date.

Techniquement, un jeton d'agent est un JWT signé par la clé de ton instance,
valable **dix ans**, qui porte `kind="agent"` et un `jti` inscrit dans la table
`agent_tokens`. La borne n'est pas l'expiration, c'est la révocation.

### Un jeton d'agent ne va jamais dans une URL

Pas en paramètre de requête, pas dans un chemin, nulle part. Seulement dans
l'en-tête `Authorization`.

La raison est mesurable. Une valeur passée en paramètre de requête part en clair
dans le journal d'accès du serveur et du proxy, où elle reste. Le WebSocket
d'Eldir prend son jeton de cette façon (`/ws/sessions/{id}?token=…`) parce que les
WebSockets de navigateur n'acceptent pas d'en-tête `Authorization` sans
contorsion, et c'est précisément pourquoi ce jeton-là est un jeton de connexion
courte. Un identifiant qui vit dix ans et ouvre le dispatch n'est pas le même
incident dans `docker logs` qu'un jeton d'une heure.

Si c'est arrivé, le geste de secours est simple et il n'y en a pas d'autre :
**Settings > Agents extérieurs**, **Révoquer**, puis émettre un nouveau jeton. La
rotation est le seul remède, parce qu'un jeton écrit dans un journal ne se
reprend pas.

Accessoirement, un jeton d'agent présenté au WebSocket serait de toute façon
refusé (voir juste en dessous), ce qui limite les dégâts mais ne les annule pas.

## Brancher un client MCP

| Réglage | Valeur |
|---|---|
| URL | `https://eldir.exemple.lan/api/mcp/` (**la barre finale compte**) |
| Transport | MCP streamable HTTP, sans état |
| Authentification | en-tête `Authorization: Bearer <jeton d'agent>` |

Le serveur est **sans état** (`stateless_http=True`) : aucune affinité de session
HTTP, donc un redémarrage du backend ne casse pas l'agent et n'importe quel proxy
convient. Chaque requête se présente avec son en-tête, et c'est tout.

**Un jeton d'agent et un jeton de connexion ne sont pas interchangeables, dans les
deux sens.** Un jeton de connexion ordinaire (celui de l'interface web) ne passe
pas sur `/api/mcp/`, et un jeton d'agent n'ouvre ni l'API REST ni le WebSocket. Ce
sont deux listes blanches explicites dans `backend/app/core/security.py`, et pas
un effet de bord : les deux jetons sont signés par la même clé et portent le même
`sub`, donc sans ce refus un jeton d'agent vaudrait dix ans de connexion complète,
sans passer par la table de révocation.

### Si Eldir est exposé au-delà de ton réseau privé

Renseigne `MCP_ALLOWED_HOSTS` (`backend/.env`) avec le ou les noms par lesquels
l'agent joint Eldir, séparés par des virgules, port compris ou en `hôte:*` :

```dotenv
MCP_ALLOWED_HOSTS=eldir.exemple.lan,eldir.exemple.lan:*
```

Un `Host` hors liste est alors refusé en **421**. Laisser la variable **vide
désactive cette vérification**, et c'est le réglage par défaut : le jeton reste la
garde, et aucun cookie n'est en jeu sur cette surface, donc il n'y a rien à
rejouer depuis un navigateur.

Ce réglage sert aussi à l'`Origin` : les origines autorisées sont ces mêmes noms,
en `https://` et en `http://`. Un agent hébergé ou piloté par un navigateur
envoie cet en-tête, et une origine hors liste repart en **403** (voir
[403 `Invalid Origin header`](#403-invalid-origin-header)).

Si tu passes par le reverse proxy fourni (`docker/Caddyfile`), il transmet le
`Host` d'origine tel quel : c'est donc le nom public qu'il faut déclarer, pas
`backend:8000`.

## Les cinq outils

| Outil | À quoi ça sert | Paramètres |
|---|---|---|
| `list_projects` | Les repos branchés sur Eldir, avec pour chacun sa dernière activité et le nombre de sessions qui attendent un geste humain. Sert à identifier de quel projet on parle, et à repérer ceux qui dorment. | aucun |
| `list_sessions` | Les 20 sessions projet les plus récemment actives, avec leur état, leur branche, si elles tournent, et le compte rendu `<cr>` de leur dernier passage. | aucun |
| `dispatch` | Transmet une consigne à une session projet et rend la main immédiatement. Reprend la session indiquée, sinon la plus récente du projet, sinon en démarre une. | `project_id` (requis), `consigne` (requis), `session_id` (optionnel), `nouveau_chantier` (booléen, optionnel) |
| `remember` | Enregistre une préférence de travail durable dans les **Préférences apprises par le superviseur**. | `fait` (requis) |
| `allow_publish` | ⚠️ Ouvre ou referme la porte de publication d'une session (commit, push, PR). N'agit que sur les sessions de l'utilisateur du jeton. Le push forcé reste refusé même porte ouverte. | `session_id` (requis), `autoriser` (booléen, requis) |

Trois précisions qui ne se devinent pas :

- `nouveau_chantier: true` force une session neuve **à côté** des existantes, dans
  son propre worktree. La règle est : un chantier par sujet indépendant, la même
  session pour la suite d'un travail en cours. Deux consignes parallèles dans le
  même arbre de travail se marcheraient dessus.
- La **dernière activité** de `list_projects` est la dernière écriture sur la
  ligne de session (le `max(updated_at)` des sessions non système du projet), **pas
  la date du dernier commit**. Une session touchée hier sur un repo dont le dernier
  commit date d'un mois est « active d'hier ». Compter les commits non poussés
  aurait demandé un `git rev-list` par projet et par appel, pour dire ce que l'état
  `waiting_input` dit déjà.
- `dispatch` rend la main tout de suite et la session enfant travaille en tâche de
  fond. Pour savoir qu'elle a fini, il faut le ping décrit juste en dessous.

### Les deux plafonds qu'un dispatcheur rencontre en premier

Ils ne se devinent pas, et ils ne se comportent pas pareil.

**Le nombre de sessions actives** (`MAX_CONCURRENT_SESSIONS`, défaut 8). Un
`dispatch` qui doit ouvrir ou réveiller une session est refusé **tout de suite**,
par le texte que l'outil rend : `Erreur : Limite de 8 sessions actives
atteinte. …`. Arrête une session (elle reste reprenable) pour libérer une place,
ou dispatche dans une session déjà active.

**La file de messages d'une session** (`SESSION_QUEUE_MAX`, défaut 5). Celui-là
arrive **après** que `dispatch` a répondu « Consigne transmise » : la réservation
de place se fait dans la tâche de fond, donc le refus ne peut plus remonter dans
la réponse de l'outil. Il part en ping de cause `non_livree`. **Sans abonné
configuré, cette consigne-là est perdue en silence** : c'est le défaut, et c'est
la raison principale de brancher un abonné si ton agent dispatche sans
surveillance.

La leçon est la même pour les deux : un dispatcheur attend le compte rendu d'un
tour avant d'en demander un autre sur la même session, et ouvre un
`nouveau_chantier` quand le sujet est indépendant.

Les descriptions et les schémas que ton client affichera sont exactement ceux de
la table partagée : ce que lit l'agent extérieur est mot pour mot ce que lit le
superviseur interne.

## Recevoir les fins de tour

Sans ce signal, un agent extérieur n'apprend la fin d'un travail qu'à sa
prochaine occasion de regarder : il avance d'un pas par réveil au lieu
d'enchaîner, ce qui annule l'essentiel de l'intérêt d'un agent qui travaille
pendant que tu fais autre chose. Le réveil du superviseur interne, lui, vit en
mémoire et n'est pas joignable d'un autre processus.

Trois variables dans `backend/.env` :

```dotenv
# URL vide = aucun ping. Un seul abonné : une table viendra quand il y en aura deux.
TURN_WEBHOOK_URL=https://agent.exemple.lan/eldir/fin-de-tour
# Signe le corps (HMAC SHA-256). Vide = ping non signé.
TURN_WEBHOOK_SECRET=
# Délai total d'un ping, connexion et réponse comprises. Défaut 10 s.
TURN_WEBHOOK_TIMEOUT_SECONDS=10
```

**Cet abonné est global à l'instance, pas par jeton.** Tous les porteurs
pingent la même URL, et chaque ping porte le compte rendu complet du tour, quel
que soit l'agent qui l'a demandé (`demandeur` dit lequel). Si tu émets des jetons
pour deux agents qui ne doivent pas lire le travail l'un de l'autre, cette
surface ne sait pas les séparer : n'en branche qu'un, ou n'en branche aucun.

Eldir poste alors, à la fin de chaque tour dispatché, un `POST` en
`application/json` dont le **corps est en ASCII pur** (les accents partent
échappés, aucun abonné n'a à deviner l'encodage). Quand un secret est configuré,
l'en-tête `X-Eldir-Signature: sha256=<HMAC SHA-256 du corps, en hexadécimal>`
accompagne la requête. Le préfixe nomme l'algorithme : sans lui, un abonné
devinerait, et le jour où l'algorithme change il vérifierait encore l'ancien en
silence.

### La charge

```json
{
  "session_id": "3f8c1a2e-5b47-4d90-a1c3-7e0f29b8d641",
  "projet": "Munin",
  "branche": "claude/3f8c1a2e-5b47-4d90-a1c3-7e0f29b8d641",
  "etat": "fin_de_tour",
  "cr": "<cr>\nFAIT: ...\nRESTE: rien\n</cr>",
  "erreur": null,
  "cause": null,
  "demandeur": "agent:assistant de bureau",
  "ping_id": "b7d41c08-9e52-4a16-8f3b-0c2d5a6e9147",
  "horodatage": "2026-10-30T05:05:04+00:00"
}
```

| Champ | Ce qu'il dit |
|---|---|
| `session_id` | La session qui a fini son tour. |
| `projet` | Le nom du projet, ou `projet inconnu` si la ligne n'en porte plus. |
| `branche` | La branche du worktree de la session. |
| `etat` | `"fin_de_tour"` ou `"erreur"`. **Deux valeurs, pas une de plus.** |
| `cr` | Le compte rendu `<cr>` **du tour qui vient de finir**. |
| `erreur` | Le texte à lire par un humain. |
| `cause` | Le champ **stable** à comparer : `"arret"`, `"panne"`, `"non_livree"` ou `null`. |
| `demandeur` | L'origine de la consigne : `eldir` si le superviseur interne l'a donnée, `agent:<libellé du jeton>` si c'est un agent extérieur. |
| `ping_id` | Un uuid4 **par ping**, pour dédoublonner. |
| `horodatage` | L'heure d'émission, ISO 8601 en UTC à la seconde (`+00:00`, pas `Z`). |

Quatre règles valent plus que le tableau :

1. **Compare `cause`, jamais `erreur`.** `erreur` est écrit pour être lu par un
   humain et peut être réécrit un jour, donc s'en servir comme discriminant est
   un piège qui se refermera à la prochaine reformulation. Les trois causes
   appellent des réactions différentes : `arret` dit que la session a été arrêtée,
   supprimée ou qu'Eldir s'est éteint (re-dispatcher) ; `panne` dit que le tour est
   tombé (lire `erreur`) ; `non_livree` dit que la consigne n'est jamais partie et
   qu'aucun tour n'a eu lieu.
2. **`cr` vaut `null` si le tour n'a produit aucun compte rendu**, et ce n'est
   **jamais** celui d'un tour précédent. La colonne `summary` d'une session garde
   le dernier compte rendu écrit, quel que soit le tour qui l'a écrit ; le ping,
   lui, ne porte que celui du tour qui vient de finir. Donner l'ancien ferait lire
   « prêt » à qui attend du travail. En erreur, `cr` est absent même si le tour en
   avait écrit un avant de tomber.
3. **Toute absence vaut `null`.** Pas de champ qui disparaît, pas de chaîne vide
   qui veut dire « rien » : un seul cas à traiter.
4. `horodatage` et `ping_id` sont **dans le corps signé**. Sans l'heure, une
   charge vue passer se rejoue indéfiniment ; sans l'identifiant, deux pings d'une
   même session dans la même seconde seraient identiques octet pour octet, et tu
   ne pourrais pas distinguer un doublon de livraison d'un rejeu.

### Comment ton abonné doit se comporter

Ces trois règles ne sont pas des recommandations de confort. Les deux premières
sont ce qui empêche n'importe qui de te poster un faux ping.

**Ta règle de signature suit ta propre configuration, jamais la requête.** Si tu
as configuré un secret, refuse tout ping non signé. Un abonné qui ne vérifie la
signature que lorsqu'un en-tête est présent accepte n'importe quelle requête qui
omet l'en-tête, donc n'importe qui.

**Compare à temps constant** (`hmac.compare_digest`), jamais avec `==`.

**Refuse un horodatage trop ancien et dédoublonne sur `ping_id`.** Le premier
borne le rejeu, le second absorbe une double livraison.

```python
import hashlib, hmac, json, os
from datetime import datetime, timedelta, timezone

SECRET = os.environ["ELDIR_WEBHOOK_SECRET"].encode()  # ta config, pas la requête
FENETRE = timedelta(minutes=5)
vus: set[str] = set()  # un cache partagé si tu as plusieurs processus

def accepter(corps: bytes, signature: str | None) -> bool:
    if signature is None:  # un secret configuré ici : un ping non signé est refusé
        return False
    attendu = "sha256=" + hmac.new(SECRET, corps, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(attendu, signature):  # temps constant
        return False
    charge = json.loads(corps)
    if datetime.now(timezone.utc) - datetime.fromisoformat(charge["horodatage"]) > FENETRE:
        return False
    if charge["ping_id"] in vus:
        return False
    vus.add(charge["ping_id"])
    return True
```

La signature se recalcule sur les **octets reçus**, pas sur un JSON re-sérialisé :
un `json.dumps` de ton côté ne redonne pas forcément les mêmes octets.

### Ce qu'Eldir fait quand ton abonné ne répond pas

L'échec est journalisé et jamais bloquant : la session enfant a fini son travail,
un abonné injoignable, lent ou en erreur ne doit pas transformer ce succès en
échec. Il n'y a **aucune nouvelle tentative** : un ping perdu est perdu.

Une **redirection n'est pas suivie**, et elle compte comme un refus. Le corps
signé ne part donc jamais ailleurs que vers l'URL configurée, et un abonné
déménagé s'entend dire que son adresse ne reçoit plus rien plutôt que de croire
que tout va bien.

## Ce qui n'est pas garanti

À écrire noir sur blanc, parce que compter là-dessus mènerait à un agent qui
attend un signal qui ne viendra pas.

**La livraison du ping d'interruption pendant une extinction d'Eldir.** Quand le
backend s'arrête, il arrête chaque session active, ce qui publie un `STOP` qui
déclenche un ping de cause `arret`. Ce ping part dans une tâche de fond que
personne n'attend, et le processus se termine : il peut ne jamais partir. Un agent
qui attendait la fin d'un tour doit savoir se remettre d'un silence, pas seulement
réagir à un ping.

**Le suivi d'une consigne qui tournait au moment d'un redémarrage.** L'état des
tours en cours et des consignes en attente vit **en mémoire**, comme les sessions
actives qu'il faut reprendre après un redémarrage. Après un redémarrage, le tour
qui était en route ne produira ni ping ni notification au superviseur, même s'il
avait été dispatché.

**Le ping d'interruption ne réveille pas le superviseur interne.** Une session
arrêtée en pleine tâche prévient l'abonné HTTP, mais pas la session superviseur :
ton Eldir interne ne se saura pas interrompu.

**`erreur` est borné, pas filtré.** Le texte est coupé à **300 caractères** (avec
une ellipse qui le dit), parce qu'une exception de base de données recopie le SQL
et ses paramètres, et qu'un message de plusieurs centaines de kilo-octets se
ferait refuser par un abonné qui limite la taille. Couper n'est pas filtrer : le
début du message part **tel quel**, et il peut porter le début d'un message
technique. Traite ce champ comme du texte non fiable, à afficher et pas à
interpréter, et ne le recopie pas dans un canal public sans y regarder.

**Pas de file durable.** Un redémarrage perd les messages en attente d'une
session, comme il perd les sessions actives.

**Deux dispatches dans la même milliseconde sur une session endormie.** Le
réveil d'une session n'est pas une opération que deux appels peuvent partager :
le second est **refusé** plutôt que de monter un second client Claude dans le
même arbre de travail. Mais `dispatch` a déjà répondu « Consigne transmise », et
le refus n'arrive donc que par un ping de cause `non_livree` : sans abonné
configuré, cette consigne-là est perdue en silence. Un dispatcheur autonome
attend la fin d'un tour avant d'en demander un autre sur la même session, ou
ouvre un `nouveau_chantier`.

**Pas d'autorisation fine par outil.** Un jeton donne les cinq outils ou rien,
publication comprise. Un jeton en lecture seule, ou un jeton sans
`allow_publish`, sera utile le jour où un agent tiers, non maîtrisé, se branche.
Ce jour-là, pas avant.

## Si ça ne marche pas

### 401, avec `WWW-Authenticate: Bearer`

Le corps nomme le motif, et le motif dit quoi faire :

| Message | Ce qui s'est passé |
|---|---|
| `Header Authorization manquant ou mal formé.` | Pas d'en-tête, pas de schéma `Bearer`, ou un jeton coupé par une espace (deux jetons collés, une espace en trop). |
| `Jeton invalide.` | Illisible, tronqué, ou signé par une autre clé : tu t'adresses à une autre instance, ou `JWT_SECRET` a changé. |
| `Jeton expiré.` | Les dix ans sont passés, ou l'horloge d'une des deux machines dérive. |
| `Ce jeton n'est pas un jeton d'agent.` | Tu présentes un jeton de connexion ordinaire. Émets un jeton d'agent. |
| `Jeton d'agent inconnu.` | Le jeton est bien signé mais son `jti` n'est plus dans la table, ou il appartient à un autre porteur. |
| `Jeton d'agent révoqué.` | Le jeton existe mais il a été coupé. C'est un message distinct d'« inconnu » exprès : c'est celui dont tu as besoin pour comprendre pourquoi un agent est refusé. |
| `Jeton d'agent incomplet.` | Le jeton ne porte pas de `sub` ou de `jti`. Il n'a pas été émis par Eldir. |

Le refus est journalisé (tu dois pouvoir voir qui frappe) **sans jamais le jeton
présenté**, ni en clair ni tronqué.

### 404 `Not Found` sur `/api/mcp/`

Ton client ajoute `/mcp` au chemin, et tu interroges `/api/mcp/mcp`. L'endpoint
est **à la racine du montage** : `/api/mcp/`, rien après. Beaucoup de clients MCP
concatènent un chemin par défaut : vérifie l'URL effective qu'ils émettent, pas
celle que tu as saisie.

### 421 `Invalid Host header`

Le nom par lequel l'agent joint Eldir n'est pas dans `MCP_ALLOWED_HOSTS`. Ajoute-le
(virgules, port compris ou en `hôte:*`), ou laisse la variable vide pour désactiver
la vérification : le jeton reste la garde.

La garde du jeton passe **avant** ce contrôle, donc un 421 veut dire que ton jeton
est accepté : si tu reçois un 401, règle-le d'abord, le problème de `Host` est
derrière.

### 403 `Invalid Origin header`

Le même réglage allume deux contrôles : le `Host` et l'`Origin`. Les origines
autorisées sont dérivées des hôtes déclarés, dans les deux schémas
(`https://` et `http://`), parce que derrière un proxy TLS c'est le navigateur
qui choisit le schéma.

Un `Origin` qui ne correspond à aucun hôte déclaré repart donc en **403**, même
avec un `Host` valide et un jeton valide. Si ton agent est hébergé sur un autre
nom que celui par lequel il joint Eldir, ajoute ce nom à `MCP_ALLOWED_HOSTS`.

Un appel sans en-tête `Origin` (un client MCP en ligne de commande, par exemple)
passe toujours : l'absence est traitée comme une requête de même origine.

### 307 sur `/api/mcp` sans barre finale

Le montage répond une redirection vers `/api/mcp/`, et il le fait **avant toute
authentification**. Deux conséquences.

D'abord, derrière un proxy TLS, Eldir ne voit qu'une connexion en clair venant du
proxy : la redirection qu'il fabrique repart donc en `http://`, et un client qui
la suit peut repasser en clair avec ton jeton dans l'en-tête.

Ensuite, un client qui ne suit pas les redirections sur un `POST` verra un 307
inexplicable là où il attendait du JSON-RPC.

Dans les deux cas, le remède est le même : **configure l'URL avec la barre
finale**, `https://eldir.exemple.lan/api/mcp/`.

### 400 `Invalid Content-Type header`

Le transport exige `Content-Type: application/json` sur chaque `POST`, et ce
contrôle-là est actif **en toutes circonstances**, que `MCP_ALLOWED_HOSTS` soit
renseigné ou non. Un client qui n'envoie pas d'en-tête, ou qui envoie autre
chose, reçoit ce 400 avant d'atteindre le moindre outil.

Voisin et souvent rencontré en même temps : un `Accept` qui ne nomme pas à la
fois `application/json` et `text/event-stream` donne un **406** dont le corps le
dit en clair (`Client must accept both …`).

### 500 sans enveloppe Eldir

Si la base est injoignable au moment où la garde valide ton jeton, l'erreur sort
de la garde sans être traduite : tu reçois un `500 Internal Server Error` nu,
hors du format `{code, message, details}` des autres refus, et le journal ne
porte aucune ligne `mcp.refus`, seulement la trace d'uvicorn. Autrement dit : un
500 nu sur cette surface se lit « Eldir est en panne », pas « ton appel est
mauvais ». Regarde `docker compose logs backend` et l'état de Postgres.

### Un message de validation en anglais

Sur une entrée malformée, les deux transports répondent par un message en
anglais. Ce n'est pas un bug : il vient de la bibliothèque MCP, avant que le corps
de l'outil soit atteint, donc avant tout texte écrit par Eldir.

```
Error executing tool dispatch: 1 validation error for dispatchArguments
project_id
  Input should be a valid string [type=string_type, input_value=123, input_type=int]
```

Le superviseur interne dit la même chose autrement (`Input validation error: 123
is not of type 'string'`), et un test compare les deux portes argument par
argument : ce qu'un schéma refuse n'atteint le corps d'un outil par aucun
transport. En particulier `"true"` n'est pas `true` : les booléens sont stricts, et
`{"autoriser": "true"}` est refusé.

Les refus écrits par Eldir, eux, sont en français et commencent par `Erreur : `.

### Où regarder quand un appel sortant échoue

`docker compose logs backend`. Les journaux sont du JSON sur une ligne.

Les journaux de requêtes du client HTTP sont **muselés** (`httpx` passé en
`WARNING`), parce qu'ils recopiaient l'URL complète de chaque appel, jeton
compris, et que l'URL d'un abonné peut en porter un. En conséquence, **un appel
sortant réussi ne laisse aucune trace**. Ne cherche pas la confirmation d'un ping
parti : son silence est le succès.

Les refus, eux, sont explicites :

| Événement | Ce qu'il dit |
|---|---|
| `turn_webhook.refuse` | L'abonné a répondu autre chose qu'un succès. Le champ `status` porte son code. Une redirection arrive ici. |
| `turn_webhook.injoignable` | Le ping n'a pas abouti (DNS, TLS, délai dépassé). Le champ `erreur` porte le **nom de la classe** d'exception, jamais son message : `httpx` y recopie parfois l'URL. |
| `mcp.refus` | Une requête vers `/api/mcp/` a été refusée. Le champ `motif` reprend le message du 401. |

Si tu as besoin du détail d'une erreur réseau que le nom de l'exception ne suffit
pas à diagnostiquer, reproduis l'appel à la main depuis le conteneur plutôt que
d'abaisser le niveau de `httpx` : tu réécrirais le jeton dans le journal.

## Pour aller plus loin

- [`docs/supervisor.md`](./supervisor.md) : les cinq outils vus du superviseur
  (il garde `allow_publish`, lui ne lit que tes consignes)
  interne, le protocole `<cr>`, la porte de validation humaine.
- [`docs/sessions.md`](./sessions.md) : cycle de vie d'une session, worktrees,
  diff et publication.
- [`docs/specs/2026-10-29-surface-agent-externe.md`](./specs/2026-10-29-surface-agent-externe.md)
  : la conception, avec les raisons de chaque choix et ce qui a été laissé dehors.
