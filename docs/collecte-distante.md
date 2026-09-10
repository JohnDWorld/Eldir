# Collecte distante

Une session Eldir ne voit que le worktree git de son projet. Or une partie de
ce qu'il faut lire n'est pas dans le repo : le code d'un service qui vit dans
une image Docker, une config générée sur l'hôte, un log de production.

Sans ça, l'agent a deux mauvaises options : deviner, ou s'arrêter. La bonne
réponse est qu'il lise le fichier. La question est comment le lui donner sans
lui donner la machine.

## Le principe

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

### 2. Côté machine distante : verrouiller la clé

Le CLI Claude tourne **dans le conteneur backend**. Tout ce qui y est monté
est donc lisible par une session, qui tourne en `bypassPermissions`. Une clé
SSH sans restriction dans ce conteneur revient à donner un shell de
production à un agent. Ce serait annuler le reste : Eldir refuse déjà tout
`git push` sans ton accord explicite, ça n'a aucun sens si l'agent peut se
connecter ailleurs et faire ce qu'il veut.

La restriction se pose côté machine distante, pas côté Eldir. Compte dédié,
sans mot de passe, et une commande forcée qui n'accepte qu'une liste fermée
d'actions :

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

## Ce que voit l'agent

`$ELDIR_COLLECTE` est dans son environnement, et le protocole enfant lui dit
de regarder `collecte.log` avant de conclure qu'un fichier est introuvable. Si
un fichier lui manque encore, il doit le nommer dans son `RESTE:` avec la
commande qui le récupérerait, plutôt que de patcher à l'aveugle.

C'est le signal qui dit quoi ajouter à la collecte du projet, exactement comme
un outil manquant dit quoi ajouter au toolchain.
