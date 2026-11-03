# Un conteneur par session

> Conception validée le 2026-11-03. Statut : à implémenter.
> Phase 6 bis du ROADMAP, premier des deux lots. Le réseau sortant restreint
> reste hors de cette spec, et aura la sienne.

## Pourquoi

Une session Eldir travaille dans son propre worktree, mais son processus tourne
dans le conteneur du backend, sous le même utilisateur. Elle voit donc le
disque entier : les clones et worktrees de **tous** les projets, les transcripts
des autres conversations, et les clés SSH des machines des autres projets.
C'est le risque connu nº 2 de [`securite-sessions.md`](../securite-sessions.md),
et il est structurel : aucun garde applicatif ne le ferme, parce qu'il ne s'agit
pas de ce qu'une session a le droit de demander mais de ce qu'elle peut atteindre
sans rien demander.

Les durcissements du 2026-10-30 (masque d'environnement, porte de publication,
jeton Git hors de portée, drapeau « source externe ») réduisent ce qu'une session
obtient en le demandant. Ils ne changent rien à ce qu'elle lit directement.

Tant que ce trou est ouvert, Eldir ne peut pas héberger sur la même instance un
projet sensible et un projet alimenté par des tickets publics, et le README le
dit. Cette spec le ferme.

## Ce qui est mesuré, et ce qui est déduit

Une sonde jetable a tourné le 2026-11-03 sur la machine de John (Docker 29.9.2,
rootful). Tout ce qui suit est **mesuré**, pas supposé :

| Question | Résultat |
|---|---|
| `ClaudeAgentOptions(cli_path=<enrobage>)` accepté | `claude -v` rend `2.1.316` à travers `docker run` |
| Handshake du protocole de contrôle à travers `docker run -i` | `connect()` OK |
| Les hooks s'exécutent toujours dans le processus du backend | 2 appels `PreToolUse` : `Write`, puis `Read` |
| Ce que la session écrit atterrit sur l'hôte | `bonjour.txt` = `SALUT`, au bon propriétaire |
| La session lit-elle le worktree voisin | Non : « No such file or directory » |
| `resume` d'un tour à l'autre | La session se souvient du mot écrit et du fichier refusé |
| Fuite de conteneurs | Aucune, ni après `disconnect()`, ni après SIGKILL du backend |
| Coût en latence au démarrage | +0,19 s à la médiane (0,53 s → 0,72 s, 3 essais) |
| `volume-subpath` isole un sous-dossier d'un volume nommé | Oui : seul `projet-a` visible, voisin introuvable |
| Ce que la session écrit remonte dans le volume nommé | Oui, visible depuis un second conteneur |
| Sous-chemin absent | Échec net, code 127, message explicite du démon |

La phrase la plus importante vient de la session de la sonde elle-même :

> « je n'ai pas réussi à lire `secret-du-voisin.txt` : l'outil Read a répondu
> que le fichier n'existe pas, **sans aucun refus de permission** »

C'est le critère de réussite de cette spec. L'isolement ne doit pas être une
règle qui refuse, parce qu'une règle qui refuse se négocie par injection de
prompt. Le fichier doit ne pas exister dans l'univers de la session.

**Rien n'est déduit dans cette conception.** Chaque brique a été mesurée avant
d'être écrite ici. Deux fausses pistes ont été écartées par la mesure et non par
la lecture du code, et elles sont consignées plus bas.

## Ce qui ne change pas

Le SDK Claude reste dans le processus du backend. Seul le processus `claude`
s'en va dans un conteneur. Par conséquent, et c'est l'intérêt principal de cette
approche :

- Les hooks `PreToolUse` et `PostToolUse` continuent de s'exécuter **côté
  backend**, en Python, dans le processus du backend. La porte de publication
  (`_publish_denial`), la garde d'accès distant (`_remote_denial`) et la
  publication d'events vers Redis sont inchangées.
- `SessionManager` garde sa structure : pool de `ClaudeSDKClient`, garde de
  ré-entrée, `ActiveSession`, plafond de sessions.
- Le bus Redis, les WebSocket, le diff viewer, le superviseur, la surface MCP :
  aucun changement.
- `resume` continue de fonctionner, via la maison `.claude` décrite plus bas.
- Aucun fork du SDK, aucun sidecar, aucune réécriture du SessionManager.

Le changement tient en un script d'enrobage, un service dans le compose, une
image, et le calcul des montages par session.

## Le mécanisme

`ClaudeAgentOptions` accepte `cli_path`. Le SDK lance alors
`[cli_path, "--output-format", "stream-json", "--verbose", ...]` et pipe
stdin/stdout/stderr (`subprocess_cli.py`, `_build_command` puis
`anyio.open_process`). Il appelle aussi `[cli_path, "-v"]` pour vérifier la
version.

On pointe `cli_path` vers un script d'enrobage qui remplace le processus par un
`docker run -i`, en transmettant les arguments tels quels. Le canal stdio du
protocole de contrôle traverse `docker run -i` sans adaptation : c'est ce que la
sonde a mesuré.

### `backend/app/services/session_container.py` (nouveau)

Un seul rôle : calculer, pour une session donnée, l'environnement que l'enrobage
lit. Rien d'autre. Pas de lancement, pas d'appel à Docker : le lancement reste
au SDK, ce service ne fait que dire quoi monter.

```python
def env_pour_enrobage(
    *,
    project_id: str,
    worktree_rel: str,
    worktree_abs: Path,
    cle_ssh: Path | None,
    config_ssh: Path | None,
) -> dict[str, str]:
    """Ce que l'enrobage a besoin de savoir, et rien de plus."""
```

Les clés produites, toutes obligatoires sauf les deux dernières :

| Clé | Contenu |
|---|---|
| `ELDIR_IMAGE` | l'image de session, depuis `Settings` |
| `ELDIR_WORKSPACES_VOLUME` | le nom du volume des workspaces, depuis `Settings` |
| `ELDIR_WORKTREE_SUBPATH` | le chemin du worktree **relatif au volume** |
| `ELDIR_WORKTREE_ABS` | son chemin absolu, identique dans le conteneur et sur l'hôte |
| `ELDIR_TOOLCHAINS_VOLUME` | le nom du volume des toolchains |
| `ELDIR_TOOLCHAIN_SUBPATH` | le sous-chemin du toolchain du projet |
| `ELDIR_CLAUDE_HOME_VOLUME` | le nom du volume des maisons `.claude` |
| `ELDIR_CLAUDE_HOME_SUBPATH` | `project_id`, cf. « La maison `.claude` » |
| `ELDIR_SSH_KEY` | chemin de la clé du projet, absent si le projet n'a pas d'accès distant |
| `ELDIR_SSH_CONFIG` | chemin du `config` à un seul bloc, absent de même |

### Nouveaux champs de `Settings`

`workspaces_root` et `toolchains_root` existent déjà (`config.py:59` et `:67`).
Tout le reste est à ajouter, avec ces valeurs par défaut :

| Champ | Défaut | Rôle |
|---|---|---|
| `session_runtime` | `"conteneur"` | cf. « Bascule et repli ». `"processus"` en test et en dev. |
| `session_image` | `"eldir-session:local"` | l'image construite par `docker/session/Dockerfile` |
| `session_network` | `"eldir-sessions"` | le réseau dédié |
| `workspaces_volume` | `"eldir_workspaces"` | nom du volume, distinct de `workspaces_root` qui en est le point de montage |
| `toolchains_volume` | `"eldir_toolchains"` | idem |
| `claude_home_volume` | `"eldir_claude_home"` | idem |

Les trois noms de volumes sont nécessaires parce que `docker run` monte un
volume **par son nom**, alors que le backend ne connaît aujourd'hui que le
chemin où ce volume est monté chez lui. Les deux informations ne sont pas
déductibles l'une de l'autre.

Ces valeurs partent dans `ClaudeAgentOptions(env=...)`. Le SDK fusionne `env`
par-dessus l'environnement hérité et le passe à `open_process`, donc l'enrobage
les reçoit. Elles ne sont **pas** transmises au conteneur : l'enrobage les lit
pour construire sa ligne de commande, et le conteneur ne reçoit que ce que la
section suivante nomme.

### `docker/session/claude-dans-un-conteneur` (nouveau)

```sh
#!/bin/sh
# Passé à `ClaudeAgentOptions(cli_path=...)`. Le SDK nous lance avec le cwd du
# worktree et nous passe son environnement ; on ne transmet au conteneur QUE ce
# qu'on nomme ici, et c'est tout l'intérêt : le masque d'environnement redevient
# un filet au lieu d'être la seule garde.
set -e
: "${ELDIR_IMAGE:?}"
: "${ELDIR_WORKSPACES_VOLUME:?}"
: "${ELDIR_WORKTREE_SUBPATH:?}"
: "${ELDIR_WORKTREE_ABS:?}"
: "${ELDIR_TOOLCHAINS_VOLUME:?}"
: "${ELDIR_CLAUDE_HOME_VOLUME:?}"
: "${ELDIR_CLAUDE_HOME_SUBPATH:?}"

set -- "$@"
monte_ssh=""
if [ -n "$ELDIR_SSH_KEY" ]; then
  monte_ssh="--mount type=bind,src=$ELDIR_SSH_KEY,dst=/eldir/ssh/cle,ro
             --mount type=bind,src=$ELDIR_SSH_CONFIG,dst=/eldir/ssh/config,ro"
fi

exec docker run -i --rm --init \
  --network "$ELDIR_NETWORK" \
  -u "$(id -u):$(id -g)" \
  --mount "type=volume,src=$ELDIR_WORKSPACES_VOLUME,dst=$ELDIR_WORKTREE_ABS,volume-subpath=$ELDIR_WORKTREE_SUBPATH" \
  --mount "type=volume,src=$ELDIR_TOOLCHAINS_VOLUME,dst=/var/eldir/toolchains,volume-subpath=$ELDIR_TOOLCHAIN_SUBPATH,ro" \
  --mount "type=volume,src=$ELDIR_CLAUDE_HOME_VOLUME,dst=/eldir/maison,volume-subpath=$ELDIR_CLAUDE_HOME_SUBPATH" \
  $monte_ssh \
  -e HOME=/eldir/maison \
  -e CLAUDE_CODE_TMPDIR=/eldir/maison/tmp \
  -e ANTHROPIC_API_KEY \
  -e CLAUDE_CODE_OAUTH_TOKEN \
  -e CLAUDE_CODE_ENTRYPOINT \
  -w "$PWD" \
  "$ELDIR_IMAGE" claude "$@"
```

Trois détails qui ne sont pas des détails :

**`-w "$PWD"`.** Le SDK règle le cwd du processus sur le worktree, donc `$PWD`
de l'enrobage **est** le worktree. On le réutilise tel quel.

**Le worktree est monté au même chemin absolu que sur l'hôte.** Sans ça, les
chemins que la session manipule, que les hooks inspectent et que le diff viewer
affiche désigneraient des fichiers que le backend ne connaît pas.

**`CLAUDE_CODE_TMPDIR` est explicite.** Le CLI se calcule sinon un temporaire
`/tmp/claude-<uid>` et **refuse de démarrer** s'il le trouve possédé par un autre
utilisateur. La sonde s'y est cassée les dents avant qu'on comprenne : le message
est « Temp directory /tmp/claude-1000 is owned by uid 0, expected 1000. Refusing
to use it ». Un montage dont le chemin passe par `/tmp` suffit à déclencher ça,
parce que Docker crée les dossiers parents en root.

### `docker/session/Dockerfile` (nouveau)

Une seule image pour toutes les sessions : Node 20, `git`, et
`@anthropic-ai/claude-code` épinglé à la version que le backend attend. Un
utilisateur non root `session` d'uid 1000.

Le toolchain du projet n'est **pas** dans l'image : il est monté en lecture seule
depuis le volume existant. Une image par projet serait une image à reconstruire
à chaque ajout d'outil, pour un gain nul.

## Ce que le conteneur monte, et rien d'autre

| Monté | Mode | Pourquoi |
|---|---|---|
| son worktree, au chemin absolu de l'hôte | rw | c'est son travail, et les chemins doivent coïncider |
| le toolchain de son projet | **ro** | elle l'exécute, elle n'a pas à l'écrire |
| la maison `.claude` de son projet | rw | le CLI y écrit son transcript, et `resume` le relit |
| la clé SSH de son projet, si elle existe | **ro** | cf. « SSH » |
| un `config` SSH à un seul bloc, généré | **ro** | cf. « SSH » |

Et par `-e` : le credential Claude, sous celui des deux noms qui est présent.

**Pas montés, et c'est tout l'objet de la spec** : les worktrees des autres
projets, leurs toolchains, leurs maisons `.claude`, leurs clés SSH, le socket
Docker, et rien du backend.

## L'environnement : le masque redevient un filet

Aujourd'hui le SDK transmet l'environnement du backend **en entier**
(`inherited_env` dans `subprocess_cli.py`), et `env_a_masquer_pour_cli()` efface
nommément ce qu'Eldir lit. C'est une liste de refus, dérivée des champs de
`Settings`, donc correcte mais fragile par nature : elle protège ce qu'Eldir
connaît.

Avec l'enrobage, le conteneur ne reçoit que les quatre variables nommées
ci-dessus. `DATABASE_URL`, `REDIS_URL`, `JWT_SECRET`, `ENCRYPTION_KEY`,
`GITHUB_OAUTH_CLIENT_SECRET`, `TURN_WEBHOOK_SECRET` et tout le reste
**n'existent pas** dans le conteneur, qu'Eldir y ait pensé ou non.

`env_a_masquer_pour_cli()` **reste en place**. Elle ne devient pas inutile : elle
protège encore le CLI quand `ELDIR_SESSION_EN_CONTENEUR` est à faux (cf.
« Bascule »), et elle ne coûte rien.

## Le proxy de socket

Le backend doit pouvoir créer des conteneurs. Lui monter `/var/run/docker.sock`
suffirait, et n'affaiblirait pas l'objectif de cette phase : après le changement
la session n'est plus dans le conteneur du backend, donc elle ne peut pas joindre
ce socket. Mais une faille de l'API Eldir passerait alors de « toutes les données
d'Eldir » à « root sur le VPS », et ce serait une régression introduite par un
changement censé durcir.

On interpose donc un proxy de socket, service du compose, image existante, aucune
ligne de code à écrire :

```yaml
  docker-proxy:
    image: tecnativa/docker-socket-proxy:0.3.0
    environment:
      CONTAINERS: 1
      POST: 1
      IMAGES: 1
      VOLUMES: 1
      # Tout le reste reste à 0 par défaut : ni EXEC, ni SWARM, ni NETWORKS en
      # écriture, ni INFO. Le backend crée, démarre et supprime des conteneurs,
      # et c'est la totalité de ce qu'il a le droit de demander.
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock:ro
    networks:
      - eldir-interne
    restart: unless-stopped
```

Le backend reçoit `DOCKER_HOST=tcp://docker-proxy:2375`, et le CLI `docker` est
ajouté à son image (`docker-ce-cli`, pas le démon). L'enrobage n'a rien à savoir
de tout ça : `docker run` lit `DOCKER_HOST` tout seul.

## La maison `.claude`, une par projet

Le volume `eldir_claude_home` est aujourd'hui partagé par toutes les sessions :
il porte les transcripts du CLI, donc les conversations de tous les projets. Le
monter tel quel dans chaque conteneur ne fermerait le trou qu'à moitié.

**Granularité retenue : une par projet**, sous-dossier `<project_id>` du volume.
Deux sessions d'un même projet partagent déjà leur worktree de base, leur clé et
leur code : elles sont le même domaine de confiance, et les séparer
compliquerait le fork de conversation prévu en V2 pour un gain nul. Deux projets
différents, en revanche, ne se voient plus.

### Migration

Les transcripts existants vivent à plat dans `/home/eldir/.claude/projects/`.
Le CLI nomme chaque dossier d'après **le chemin absolu du cwd, slugifié** : les
séparateurs deviennent des tirets. Vérifié sur la sonde, où le worktree
`/tmp/.../spike/workspaces/projet-a` a donné le dossier
`-tmp-...-spike-workspaces-projet-a`.

C'est déterministe, donc la migration n'a rien à devenir. Et comme le worktree
est monté au même chemin absolu dans le conteneur que sur l'hôte, le slug reste
identique après la bascule : un transcript rattaché continue de se résoudre.

Un script `scripts/migre-maisons-claude.py`, appelé une fois au boot et
idempotent :

1. Pour chaque session connue en base ayant un `sdk_session_id`, calculer le
   slug de son worktree.
2. Déplacer le dossier de ce nom sous `<volume>/<project_id>/.claude/projects/`.
3. Ce qu'il ne sait pas rattacher reste où il est, et le script le journalise
   nommément. Rien n'est supprimé.

Le slugifieur est à **dériver de l'observation, pas à deviner** : la première
tâche du plan le vérifie sur un dossier réel de `eldir_claude_home` avant que
le script soit écrit. Un slug mal reproduit ne casse rien mais perd tous les
`resume`, silencieusement.

Une session dont le transcript n'a pas été rattaché perd son `resume` : elle
redémarre une conversation neuve au lieu d'échouer. C'est le comportement voulu,
et il doit être testé.

## SSH : sa clé à elle, en lecture seule

Les clés sont déjà une par projet, à `ssh_home/<keys>/<project_id>`
(`RemoteAccessService.key_path`). Le conteneur monte **cette seule clé**, en
lecture seule. La fonctionnalité « Connecter au serveur » survit telle quelle, et
le vrai trou se ferme : une session ne lit plus les clés des autres projets.

Le `config` SSH, lui, est un fichier unique contenant les blocs de tous les
projets, avec leurs noms de machines, utilisateurs et ports. Le monter entier
ferait fuiter l'inventaire des machines des autres projets. On génère donc un
`config` à un seul bloc, dans un fichier par session, en réutilisant la
génération existante :

- `RemoteAccessService._write_block` est extrait en une fonction pure
  `bloc_ssh(project_id, alias, host, user, port) -> str`, utilisée par le
  fichier partagé comme par le fichier par session. Pas de duplication.
- Le fichier par session est écrit dans la maison `.claude` du projet, hors du
  worktree, et supprimé à l'arrêt de la session.

`_remote_denial` dans le hook reste en place, inchangé : il garde toujours les
projets marqués « alimentés de l'extérieur », et il s'exécute côté backend.

## Le réseau

Un réseau Docker dédié, `eldir-sessions`, sans route vers le réseau interne qui
porte Postgres, Redis et le proxy de socket. Une session ne peut donc plus
joindre la base ni Redis **même si** un credential lui échappait.

Le sortant vers Internet reste **complet**, comme aujourd'hui. Le restreindre
(API Anthropic et provider Git du projet seulement) est le second lot de la
Phase 6 bis, et aura sa spec : c'est le point qui risque le plus de casser les
toolchains qui téléchargent leurs dépendances, et il mérite d'être mesuré seul.

La sonde utilisait `--network host`, qui n'est aucun isolement. C'était un
raccourci de sonde, et il ne doit pas survivre dans l'implémentation.

## Bascule et repli

Un réglage `SESSION_RUNTIME` dans `Settings`, à deux valeurs :

- `processus` : comportement actuel, le CLI tourne dans le conteneur du backend.
- `conteneur` : le CLI tourne dans son conteneur.

Défaut `conteneur` en production, `processus` en test et en développement local,
où Docker n'est pas garanti disponible. Le réglage n'est pas un drapeau de
fonctionnalité à retirer plus tard : il reste, parce qu'une installation sans
Docker accessible au backend doit pouvoir faire tourner Eldir.

Quand le démarrage en conteneur échoue, la session **ne retombe pas** en mode
processus. Un repli silencieux vers le mode non isolé serait exactement le
comportement qu'un attaquant cherche à provoquer. Le démarrage échoue avec un
message explicite, et le mode processus ne s'obtient que par le réglage.

## Erreurs et cas limites

| Cas | Comportement attendu |
|---|---|
| sous-chemin de worktree absent dans le volume | `docker run` échoue, code 127, message du démon. L'enrobage le relaie tel quel sur stderr, et `SessionManager` lève une erreur de démarrage lisible. Mesuré. |
| image de session absente | même chemin : échec au démarrage, message explicite, pas de repli |
| proxy de socket injoignable | échec au démarrage de la session, pas du backend. Les sessions déjà vivantes ne sont pas affectées : leur `docker run` tourne déjà. |
| backend tué pendant un tour | le conteneur s'arrête, mesuré au SIGKILL. Pas de conteneur orphelin. |
| projet sans accès distant | `ELDIR_SSH_KEY` absent, aucun montage SSH, la session n'a pas de clé du tout |
| deux sessions sur le même projet | deux conteneurs, deux worktrees, **une** maison `.claude` partagée. Voulu. |

## Tests

Les trois premiers sont le cœur : ils échouent si l'isolement se défait.

1. **Une session ne lit pas le worktree voisin.** Test d'intégration marqué
   `docker`, sauté si le démon n'est pas joignable. Deux worktrees dans le
   volume de test, un conteneur monté sur le premier, un `cat` sur le second :
   il doit échouer. Mutation qui doit le faire tomber : monter la racine
   `workspaces` au lieu du sous-chemin.
2. **Une session ne lit pas la clé SSH d'un autre projet.** Même forme.
   Mutation : monter `ssh_home` au lieu de la seule clé.
3. **Une session ne lit pas la maison `.claude` d'un autre projet.** Même forme.
   Mutation : monter le volume sans `volume-subpath`.
4. **`env_pour_enrobage` ne produit jamais un secret.** Test unitaire : aucune
   valeur de `Settings` marquée secrète n'apparaît dans le dictionnaire rendu.
5. **Les montages sont en lecture seule là où la table le dit.** Test unitaire
   sur la ligne de commande construite, pas sur un conteneur : plus rapide, et
   c'est la commande qui est la décision.
6. **`SESSION_RUNTIME=processus` reproduit exactement le comportement actuel.**
   La suite existante tourne dans ce mode, donc elle le prouve déjà ; un test
   nomme l'invariant pour que personne ne l'abîme sans le voir.
7. **Un échec de démarrage en conteneur ne retombe pas en mode processus.**
   Image inexistante, on attend une erreur, et surtout **pas** une session
   vivante.
8. **La migration des maisons `.claude` est idempotente**, et une session dont
   le transcript n'a pas été rattaché démarre une conversation neuve sans
   échouer.

Les tests 1 à 3 demandent un démon Docker. Ils sont marqués, et la CI les
exécute : GitHub Actions en fournit un. Ils ne lancent pas le CLI Claude, donc
ils ne consomment aucun credit.

## Hors périmètre

- **Le réseau sortant restreint.** Second lot de la Phase 6 bis, spec à part.
- **Le risque nº 1, le credential Claude.** Une session continue de le lire,
  parce que son CLI s'authentifie avec. Inchangé, et toujours écrit dans
  `securite-sessions.md`.
- **Le plafond de sessions concurrentes.** +0,19 s au démarrage est négligeable ;
  le coût mémoire d'un conteneur par session est à mesurer pendant
  l'implémentation, et le plafond à revoir **sur cette mesure**, pas sur une
  estimation.
- **Le multi-processus du backend.** Le pool de clients SDK vit dans la mémoire
  d'un processus, et cette spec ne change pas ça.
- **Podman et le mode rootless.** La vraie réduction de surface, mais c'est une
  migration de tout le stack, Caddy sur 80 et 443 compris. Le proxy de socket
  couvre le besoin de cette phase sans y toucher.

## Deux fausses pistes, écartées par la mesure

Elles figurent ici pour qu'on ne les refasse pas.

**Un sidecar qui porte le SDK.** L'idée était de déplacer le SDK lui-même dans le
conteneur de session, qui parlerait au backend par HTTP ou Redis. Elle est
écartée parce qu'elle déplace **les hooks** dans le conteneur : la porte de
publication et la garde d'accès distant s'exécuteraient alors dans le périmètre
qu'elles sont censées contraindre. L'enrobage les garde côté backend.

**Un bind mount de l'hôte pour les workspaces.** Plus simple que
`volume-subpath`, et c'est ce que la sonde a utilisé. Écarté après vérification
que `volume-subpath` fonctionne sur Docker 29.9.2 : garder les volumes nommés
évite de toucher au compose existant et au script de déploiement.

## Phase concernée

ROADMAP, « Phase 6 bis - Isoler les sessions du backend (V2) », premier lot.
Cette spec coche les points 1, 2 et 4 de la phase, laisse le point 3 (réseau
sortant) au second lot, et transforme le point 5 (plafond) en une mesure à faire
pendant l'implémentation.
