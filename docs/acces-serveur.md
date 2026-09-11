# Accès serveur

Une session Eldir ne voit que le worktree git de son projet. Or une partie de
ce qu'il faut lire, et parfois corriger, n'est pas dans le repo : le code d'un
service qui vit dans une image Docker, une config générée sur l'hôte, un log
de production.

Deux mécanismes, à utiliser dans cet ordre :

1. **La collecte** ramène des fichiers précis avant que la session démarre.
   Automatique, hors du worktree, aucune connexion ouverte par l'agent. Ça
   suffit quand tu sais d'avance ce qu'il faut lire.
2. **L'accès SSH** laisse la session se connecter à la machine du projet et y
   travailler. Ça s'adapte à n'importe quel projet, et ça sort du modèle
   « je relis le diff avant que ça parte ». Lis la section dédiée avant de
   l'activer.

## La collecte : le principe

Le projet **déclare** ce qu'il faut ramener, une commande par fichier, dans
son Mission Template. Eldir les lance à la création de chaque session et
dépose le résultat dans un dossier à part :

```
/var/eldir/collectes/<project_id>/            ← $ELDIR_COLLECTE
/var/eldir/collectes/<project_id>/collecte.log
```

Ce que ça donne :

- l'agent lit des fichiers, il n'ouvre jamais de connexion vers tes serveurs ;
- le dossier est **hors du worktree**, donc rien de ce qui vient de la prod ne
  peut partir dans un commit ;
- ce qui sort d'une machine est écrit dans le template : ça se relit, ça se
  versionne, ça se retire ;
- une collecte qui échoue n'empêche pas la session de démarrer, elle laisse
  une ligne dans `collecte.log` que l'agent est invité à lire et à remonter
  dans son compte rendu.

Le dossier n'est **pas** un volume : il est reconstruit à chaque création de
session et disparaît au redéploiement. Une donnée de prod rapatriée n'a pas à
survivre.

## Déclarer une collecte

Dans **Projects → un projet → Template**, champ « Collecte distante », une
ligne par fichier :

```
fichier = commande
```

Exemple :

```
adapter-matrix.py = ssh mon-serveur docker exec passerelle cat /opt/app/plugins/matrix/adapter.py
config-prod.yaml = ssh mon-serveur cat /etc/monapp/config.yaml
erreurs.log = ssh mon-serveur docker logs --tail 200 passerelle
```

La sortie standard de la commande devient le fichier. Le nom de fichier est
limité à `[A-Za-z0-9._-]` : pas de sous-dossier, pas de `../`.

Garde-fous appliqués à chaque commande :

| Garde-fou | Réglage | Défaut |
|---|---|---|
| Délai max | `COLLECT_TIMEOUT_S` | 60 s |
| Taille max du fichier | `COLLECT_MAX_FILE_MB` | 2 Mo |
| Code de retour non nul | fichier supprimé, ligne d'échec dans le log | - |

Un fichier à moitié écrit qui ressemble à du code source est pire qu'un
fichier absent : l'agent le lirait pour argent comptant. Donc en cas d'échec,
rien n'est laissé sur disque.

## Donner l'accès SSH à Eldir

Deux étapes, l'une côté Eldir, l'autre côté machine distante. **La seconde
n'est pas optionnelle.**

### 1. Côté Eldir : monter une clé

Génère une clé **dédiée à Eldir**, jamais une de tes clés personnelles :

```
ssh-keygen -t ed25519 -f ./secrets/ssh/id_ed25519 -C eldir -N ""
```

Crée `./secrets/ssh/config` avec un alias par machine :

```
Host mon-serveur
    HostName <hote>
    User eldir-collecte
    IdentityFile /home/eldir/.ssh/id_ed25519
    IdentitiesOnly yes
    StrictHostKeyChecking accept-new
```

Puis décommente le montage dans `docker-compose.yml` :

```yaml
      - ./secrets/ssh:/home/eldir/.ssh:ro
```

### 2. Côté machine distante : choisir le régime

Le CLI Claude tourne **dans le conteneur backend**. Tout ce qui y est monté
est donc lisible par une session, qui tourne en `bypassPermissions`. Ce que la
clé permet là-bas, l'agent peut le faire. La restriction se pose donc côté
machine distante, pas côté Eldir.

Deux régimes, selon ce que tu veux :

| Régime | Ce que la clé permet | Pour quoi |
|---|---|---|
| **Verrouillé** | une liste fermée de commandes | collecte de fichiers |
| **Ouvert** | un shell sur un compte dédié | laisser la session travailler sur la machine |

Le verrouillé se pose avec une commande forcée dans `authorized_keys` : compte
dédié, sans mot de passe, et un script qui n'accepte qu'une liste fermée
d'actions.

```
# /home/eldir-collecte/.ssh/authorized_keys
command="/usr/local/bin/eldir-collecte",no-agent-forwarding,no-port-forwarding,no-pty,no-X11-forwarding ssh-ed25519 AAAA... eldir
```

```bash
#!/usr/bin/env bash
# /usr/local/bin/eldir-collecte - seule commande atteignable par la clé Eldir.
set -euo pipefail
case "${SSH_ORIGINAL_COMMAND:-}" in
  "docker exec passerelle cat /opt/app/plugins/"*.py) ;;
  "docker logs --tail "[0-9]*" passerelle") ;;
  "cat /etc/monapp/config.yaml") ;;
  *) echo "refusé par eldir-collecte : ${SSH_ORIGINAL_COMMAND:-vide}" >&2; exit 1 ;;
esac
exec bash -c "$SSH_ORIGINAL_COMMAND"
```

Avec ça, une clé qui fuiterait ne donne que la lecture des fichiers que tu as
toi-même listés. C'est le même principe que la barrière de publication : ce
qui est irréversible passe par une décision humaine, écrite quelque part où
l'agent ne peut pas la réécrire.

Ajuste la liste à ce que tu déclares dans les templates. Si une collecte
échoue avec « refusé par eldir-collecte », c'est que la commande n'est pas
dans la liste : c'est le comportement attendu.

## Laisser la session travailler sur la machine

Déclarer les fichiers un par un ne passe pas à l'échelle : sur un projet
déployé, l'agent a besoin de parcourir la machine, pas de recevoir trois
fichiers choisis d'avance. D'où le régime ouvert.

Dans **Projects → un projet → Template**, champ « Machine du projet », mets
l'alias SSH. Les sessions de ce projet verront `$ELDIR_REMOTE_HOST` et
pourront s'y connecter. Vide = aucun accès, c'est le défaut.

### Ce que ça change

Le modèle d'Eldir est : l'agent travaille dans un worktree, tu relis le diff,
tu déclenches la publication. Sur la machine distante, **rien de tout ça
n'existe**. Pas de branche, pas de diff, pas d'annulation. Ce que la session
modifie est appliqué.

Ce n'est pas un défaut d'implémentation, c'est la nature de ce que tu
autorises. Trois conséquences à accepter avant d'activer :

- n'active l'accès que sur une machine dont tu as une **sauvegarde ou un
  snapshot** récent ;
- utilise un **compte dédié sans sudo**, dont les droits d'écriture se
  limitent à l'application (`/opt/monapp`, pas `/etc` ni `/var/lib/postgresql`) ;
- traite le compte rendu comme ton seul journal : le protocole enfant impose
  à l'agent de lister dans `FICHIERS:` chaque fichier modifié à distance
  (préfixé de l'hôte) et dans `FAIT:` chaque commande qui a changé l'état de
  la machine.

### Ce qu'Eldir garantit quand même

Le hook `PreToolUse` refuse toute connexion sortante qui ne vise pas l'alias
déclaré par le projet : le conteneur porte ta configuration SSH complète, donc
sans ça une session ouverte sur un projet pourrait atteindre tes autres
machines. Une session sans alias déclaré ne sort pas du tout.

L'alias est **figé à la création de la session** : le modifier dans le
template ne change rien pour les sessions déjà lancées, et un `resume` repart
avec exactement le même périmètre.

C'est un garde-fou contre l'écart, pas un bac à sable. Un agent décidé
contournerait un filtre sur une ligne de commande (script intermédiaire,
`base64 -d | bash`). Le refus de publication a exactement la même propriété
depuis le début : il empêche la dérive ordinaire, il n'arrête pas une
intention hostile. Ce qui tient vraiment, c'est le compte dédié et la
sauvegarde.

## Ce que voit l'agent

`$ELDIR_COLLECTE` est dans son environnement, et le protocole enfant lui dit
de regarder `collecte.log` avant de conclure qu'un fichier est introuvable. Si
un fichier lui manque encore, il doit le nommer dans son `RESTE:` avec la
commande qui le récupérerait, plutôt que de patcher à l'aveugle.

C'est le signal qui dit quoi ajouter à la collecte du projet, exactement comme
un outil manquant dit quoi ajouter au toolchain.

Si le projet déclare une machine, `$ELDIR_REMOTE_HOST` est lui aussi dans son
environnement, et le protocole enfant lui dit d'y aller voir plutôt que de
deviner, de sauvegarder un fichier avant de l'écraser, et de tout reporter
dans son compte rendu.
