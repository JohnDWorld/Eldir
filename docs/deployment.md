# Déployer Eldir sur un serveur

> Guide pour une mise en prod self-hosted derrière un VPN (Tailscale ou
> Headscale), avec un vrai certificat TLS mais **aucun port ouvert sur
> Internet**. Pour une install locale de découverte, voir
> [`installation.md`](./installation.md).

## Ce que suppose ce guide

- Un serveur Debian 13 (ou Ubuntu LTS), 4 Go de RAM minimum, 40 Go de disque.
- Un nom de domaine dont tu contrôles la zone DNS via une API (ici OVH).
- Un tailnet Tailscale ou Headscale déjà en place.

**Pourquoi TLS est obligatoire** : le service worker de la PWA n'est activé que
dans un contexte sécurisé. En HTTP, Eldir reste utilisable dans un onglet mais
ne s'installe pas sur un téléphone, et le mode hors-ligne ne fonctionne pas.

**Pourquoi DNS-01 plutôt que HTTP-01** : le challenge DNS-01 pose un
enregistrement TXT via l'API de ton hébergeur DNS. Aucun port n'a besoin d'être
joignable depuis Internet, donc le serveur peut rester entièrement derrière le
VPN, certificat valide inclus. C'est ce que fait
[`docker/caddy/Dockerfile`](../docker/caddy/Dockerfile), qui recompile Caddy avec
le plugin DNS (l'image officielle n'en embarque aucun).

## 1. Le système

```bash
# Docker + compose v2 (dépôt officiel Docker)
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker "$USER" && newgrp docker

sudo apt install -y git

# 4 Go de swap : pas pour tourner dessus, pour survivre au build du frontend
sudo fallocate -l 4G /swapfile && sudo chmod 600 /swapfile
sudo mkswap /swapfile && sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
echo 'vm.swappiness=10' | sudo tee /etc/sysctl.d/99-swap.conf
```

Docker doit être en version 26 au moins : les sessions en conteneur montent des
sous-dossiers de volumes. Les raisons et la vérification sont en section 5 bis.

## 2. Le VPN

```bash
curl -fsSL https://tailscale.com/install.sh | sh

# Tailscale
sudo tailscale up --hostname eldir
# Headscale : générer d'abord la clé côté serveur Headscale
#   sudo headscale users list                    # relève l'ID
#   sudo headscale preauthkeys create -u <id> -e 1h
sudo tailscale up --login-server https://headscale.example.com \
  --authkey <clé> --hostname eldir

tailscale ip -4   # note cette IP, elle sert aux étapes 3 et 5
```

## 3. Le DNS

Un seul enregistrement, dans la zone de ton domaine :

```
eldir    A    100.64.0.2       # l'IP du VPN, pas l'IP publique
```

Pointer un nom public vers une IP privée est volontaire et sans risque : seuls
tes appareils connectés au VPN pourront joindre l'adresse. Let's Encrypt n'a
pas besoin de l'atteindre, il ne lit que le TXT.

## 4. Le token API DNS

Sur [api.ovh.com/createToken](https://api.ovh.com/createToken/), avec pour seuls
droits la zone concernée :

```
GET    /domain/zone/mondomaine.fr/*
POST   /domain/zone/mondomaine.fr/*
PUT    /domain/zone/mondomaine.fr/*
DELETE /domain/zone/mondomaine.fr/*
```

Validité **unlimited**, sinon le renouvellement automatique cassera dans trois
mois. Tu obtiens trois valeurs : application key, application secret, consumer
key.

## 5. Eldir

```bash
git clone https://github.com/JohnDWorld/Eldir.git ~/eldir && cd ~/eldir

# Variables de la stack (Caddy, DNS, Postgres)
cp .env.example .env && $EDITOR .env

# Variables applicatives du backend
cp backend/.env.example backend/.env
python3 -c "import secrets; print('JWT_SECRET=' + secrets.token_urlsafe(48))"
python3 -c "from cryptography.fernet import Fernet; print('ENCRYPTION_KEY=' + Fernet.generate_key().decode())"
$EDITOR backend/.env
```

Dans `backend/.env`, en prod :

| Variable | Valeur |
|---|---|
| `APP_ENV` | `prod` |
| `JWT_SECRET` | la valeur générée ci-dessus |
| `ENCRYPTION_KEY` | la clé Fernet générée ci-dessus, **à sauvegarder** (sans elle, tous les credentials chiffrés sont perdus) |
| `CORS_ORIGINS` | `["https://eldir.mondomaine.fr"]` |
| `FRONTEND_BASE_URL` | `https://eldir.mondomaine.fr` |
| `GITHUB_OAUTH_REDIRECT_URL` | `https://eldir.mondomaine.fr/api/v1/auth/github/oauth/callback` (à reporter à l'identique dans ton OAuth App GitHub) |
| `MAX_CONCURRENT_SESSIONS` | `4` sur un serveur à 4 Go (le superviseur occupe un slot) |
| `OLLAMA_BASE_URL` | l'URL d'une instance Ollama existante sur le VPN, ou vide |

Puis :

```bash
docker compose up -d --build          # le build du frontend prend quelques minutes
docker compose logs -f caddy          # le certificat doit sortir en ~30 s
docker compose logs -f backend        # relève ELDIR_BOOTSTRAP_TOKEN
```

Les migrations Alembic sont jouées automatiquement au démarrage du backend.

## 5 bis. Les sessions en conteneur

Depuis la Phase 6 bis, le CLI de chaque session tourne par défaut dans son propre
conteneur (`SESSION_RUNTIME=conteneur`), et non plus dans celui du backend. Ce que
ça ferme et ce que ça laisse ouvert est dans
[`securite-sessions.md`](./securite-sessions.md). Ce qui suit est ce que le serveur
doit avoir pour que ça démarre, dans l'ordre où on le rencontre.
`./scripts/install-eldir.sh` (section 6) crée le réseau et construit l'image à ta
place ; les commandes sont données pour qui ne l'utilise pas.

**Ce que ça ne sépare pas** : le conteneur isole une session du disque des autres
projets, pas du backend. Le backend lance git dans des dossiers que la session
écrit, et git exécute ce qu'il y trouve (risque nº 3) ; et le proxy de socket ne
sépare pas le backend de root sur l'hôte (section 6). N'héberge donc pas sur la
même instance un projet sensible et un projet alimenté par des tickets publics.

### 1. Docker 26 minimum sur l'hôte

Une session monte des sous-dossiers de volumes nommés (`--mount
type=volume,...,volume-subpath=...`). Les notes de version de Docker placent cette
option dans la 26.0 (API 1.45) ; la 25 s'arrête à l'API 1.44. **Mesuré
uniquement sur la 29.9.2** : aucune version plus ancienne n'a été essayée, et le
minimum est celui de la documentation de Docker, pas une mesure. Vérifie avec
`docker version --format '{{.Server.Version}}'`.

Ce qu'un démon plus ancien ferait n'est pas mesuré non plus, et le pire cas
compte : il peut refuser l'option, ce qui est net, ou **ignorer le champ
`Subpath` qu'il ne connaît pas et monter le volume entier**, ce qui retirerait
l'isolement sans un message. Le script d'install refuse donc de continuer sous la
26 quand les sessions tournent en conteneur, et se contente d'un avertissement en
mode `processus`, qui n'emploie pas l'option.

### 2. BuildKit, et l'image des sessions

```bash
DOCKER_BUILDKIT=1 docker build -t eldir-session:local backend/docker/session
```

BuildKit est requis (`COPY --chmod` dans le Dockerfile). Il est le constructeur par
défaut depuis Docker 23 ; `DOCKER_BUILDKIT=1` le demande aux versions d'avant,
dont le constructeur historique refuse l'option.

L'image porte Node, git, ssh et le CLI Claude, dont la version est épinglée
(`ARG CLAUDE_CLI_VERSION`) : un `docker build` refait dans six mois donne le même
CLI. On la remonte à la main, avec `claude-agent-sdk` (`backend/uv.lock`), puis on
vérifie avec une vraie session. `deploy.sh` reconstruit l'image dès que
`backend/docker/session/` change. Sans cette image, une session échoue au
démarrage avec le message du démon (« pull access denied for eldir-session »).

### 3. Le réseau `eldir-sessions`

```bash
docker network create eldir-sessions
```

Le script d'install le crée s'il manque. Compose ne peut pas le faire : il ne crée
pas un réseau qu'aucun de ses services n'utilise, et aucun service ne peut utiliser
celui-ci par construction, puisque tout son sens est qu'une session n'ait de route
ni vers Postgres et Redis ni vers le proxy de socket. Un réseau manquant fait
échouer chaque session au `docker run`, bruyamment : « network ... not found »
(mesuré avec un autre nom de réseau, code de sortie 125).

### 4. Les noms des volumes

Quatre variables du backend, posées dans `docker-compose.yml` (section
`environment` du service `backend`) :

| Variable | Valeur du compose de prod |
|---|---|
| `WORKSPACES_VOLUME` | `eldir_eldir_workspaces` |
| `TOOLCHAINS_VOLUME` | `eldir_eldir_toolchains` |
| `CLAUDE_HOME_VOLUME` | `eldir_eldir_claude_home` |
| `COLLECTES_VOLUME` | `eldir_eldir_collectes` |

Le préfixe est doublé parce que compose préfixe le nom d'un volume par celui du
projet : le volume `eldir_workspaces` du fichier, dans le projet `eldir` (`name:
eldir` en tête), s'appelle `eldir_eldir_workspaces` pour le démon. Un `docker run`
sur `eldir_workspaces` pointerait vers un volume vide créé à la volée, où le
sous-chemin du worktree n'existe pas, et `docker run` échouerait en code 127
(mesuré, pour un sous-chemin absent).

Si tu renommes le projet compose (`-p`, `COMPOSE_PROJECT_NAME` ou `name:`), ces
quatre noms changent, et un `COMPOSE_PROJECT_NAME` exporté les renomme d'un coup.
Lis les vrais noms sur l'hôte (le proxy refuse la liste des volumes, mesuré, donc
pas depuis le backend) :

```bash
docker volume ls --format '{{.Name}}' | grep -E 'workspaces|toolchains|claude_home|collectes'
```

### 5. `SESSION_RUNTIME`

| Valeur | Ce que fait le backend |
|---|---|
| `conteneur` (défaut) | Un conteneur par session. Il faut un démon joignable (`DOCKER_HOST`, ici le proxy), l'image, le réseau et les quatre noms de volumes. |
| `processus` | Le CLI tourne dans le conteneur du backend. Marche sans démon Docker, et n'isole rien : ce n'est pas le mode sûr. |

Le défaut est `conteneur`, le mode isolant : un réglage oublié coûte de la
disponibilité (la session échoue au démarrage), jamais l'isolement. Le compose de
prod le pose quand même, pour que tu le lises. La suite de tests
(`backend/tests/conftest.py`) et le compose de dev posent `processus`
explicitement ; pour lancer le backend à la main sur un poste sans démon, c'est la
même variable.

**Un démarrage de conteneur qui échoue ne retombe jamais en mode `processus`.** La
session échoue, avec le message du démon. Un repli silencieux donnerait une
session non isolée à quelqu'un qui croit l'être. Un test l'épingle.

**Avant de basculer un projet en `conteneur`, vérifie qu'il déclare le toolchain
dont il a besoin** (`setup_commands`, cf. [`templates.md`](./templates.md#toolchain-du-repo-setup_commands)).
L'image des sessions est `node:20-bookworm-slim` plus `git`, `ca-certificates` et
`openssh-client` (et le CLI Claude) : **elle n'a ni python, ni uv, ni `curl`**, que
l'image du backend porte (lu dans `backend/Dockerfile`). Vérifié dans l'image des
sessions : `python3`, `python`, `pip`, `uv`, `curl`, `make` et `gcc` y sont
absents. Un projet qui comptait sur le python 3.12, l'uv ou le `curl` du backend
les perd s'il ne les installe pas lui-même, et beaucoup de workflows d'agent
passent par `curl`.

**Le CLI qui exécute une session dépend du mode**, et trois versions peuvent
diverger sans que rien ne les aligne. Lis ceci avant de choisir un mode :

- en `conteneur`, c'est le CLI épinglé de l'image des sessions ;
- en `processus`, c'est le CLI embarqué dans le SDK Python (`claude-agent-sdk`,
  `backend/uv.lock`), et pas le `claude` du backend ;
- le `claude` installé en `@latest` dans l'image du backend (`backend/Dockerfile`)
  ne lance pas de session : il sert à la sonde de credential, et de repli au SDK.

### 6. Le proxy de socket

Le backend ne monte pas le socket du démon : `docker-proxy` le monte et ne
transmet que les chemins d'API que `docker-compose.yml` ouvre (`CONTAINERS`,
`POST`, `IMAGES`). Lis le commentaire du service avant d'y ajouter une ligne :
chacune ouvre quelque chose.

**Il ne sépare pas le backend de root sur l'hôte.** Il filtre les chemins de
l'API, pas le contenu des requêtes : `POST /containers/create` avec `Privileged`
et `Binds: ["/:/hote"]` répond 201 (mesuré contre le vrai démon). Ce qu'il
apporte, et c'est tout : pas d'`exec` dans un conteneur, pas de swarm, pas de
manipulation du réseau, pas d'`info`, et le socket du démon n'est jamais dans le
système de fichiers du backend. Le détail, mesures comprises, est dans
[`securite-sessions.md`](./securite-sessions.md#le-proxy-de-socket).

Créer un conteneur par lui équivaut à être root sur la machine (la création est
mesurée, 201 ; root une fois le conteneur démarré est déduit, pas essayé), et il
n'a pas d'authentification : la vraie garde est l'ensemble des conteneurs qui le
joignent.
Seuls `docker-proxy` et `backend` sont sur le réseau `docker-api`. Ne branche rien
d'autre dessus, et ne publie jamais son port (2375).

**Son image est dérivée de celle de l'amont**
([`docker/docker-proxy/Dockerfile`](../docker/docker-proxy/Dockerfile)), pour un
seul réglage : le délai d'inactivité. L'image de l'amont coupe toute connexion
muette à 10 minutes. Mesuré : un `docker run -i` muet sort à 600 s pile, en code
125 (« error waiting for container: unexpected EOF »). Une session qui n'a rien dit
pendant dix minutes, en attente de toi ou sur une commande longue, aurait été
tuée. L'image dérivée relève ce délai à **7 jours**, et c'est un choix, pas une
mesure : la valeur n'a été essayée qu'à 24 h (un `docker run -i` muet a tenu 11
minutes et fini en code 0). Au-delà de 7 jours muets, la coupure reviendrait
(déduit de l'observation à 10 minutes).

## 5 ter. Versionner ses secrets (optionnel, SOPS + age)

Recopier des `.env` à la main entre sa machine et son serveur finit toujours par
produire un fichier perdu ou divergent. Eldir prévoit de les versionner
**chiffrés**, avec [SOPS](https://github.com/getsops/sops) et
[age](https://github.com/FiloSottile/age).

**Dans un dépôt privé séparé**, pas dans celui d'Eldir. Le chiffrement protège
les valeurs, il n'annule pas la publication : un fichier poussé sur un dépôt
public y reste pour toujours, via les forks, les caches et les archives.

```bash
# Une fois : une clé age si tu n'en as pas déjà une
age-keygen -o ~/.config/sops/age/keys.txt
grep 'public key' ~/.config/sops/age/keys.txt

# Le dépôt privé, à côté de celui d'Eldir
mkdir ../eldir-secrets && cd ../eldir-secrets && git init
printf '*.env\n!*.enc.env\n' > .gitignore
cat > .sops.yaml <<'YAML'
creation_rules:
  - path_regex: .*\.env$
    age: age1... # ta clé publique
YAML

# Tes vraies valeurs, en clair (gitignorées)
cp ../Eldir/.env.example root.env
cp ../Eldir/backend/.env.example backend.env
$EDITOR root.env backend.env

cd ../Eldir && ./scripts/secrets.sh encrypt   # -> *.enc.env, versionnables
```

Déploiement, depuis ta machine :

```bash
./scripts/secrets.sh deploy         # ou : deploy <hôte-ssh>
```

Le déchiffrement se fait **dans le tuyau SSH** : le fichier en clair n'est jamais
écrit sur le disque local pendant un deploy, et le serveur n'a besoin ni de SOPS,
ni d'age, ni de la clé privée. Un serveur compromis ne livre donc que son propre
`.env`, pas la capacité de déchiffrer le reste.

Le script cherche le dépôt dans `../eldir-secrets`, surchargeable avec
`ELDIR_SECRETS_DIR`. Les noms de fichiers pilotent la destination :
`root.env` va vers `.env`, `backend.env` vers `backend/.env`.

Deux précautions :

- **La clé privée age est le seul secret qui compte.** Sauvegarde
  `~/.config/sops/age/keys.txt` hors de la machine (gestionnaire de mots de passe,
  papier). Sans elle, les `.enc.env` sont définitivement illisibles.
- **Rotation** : ajouter une clé publique dans `.sops.yaml` puis
  `sops updatekeys *.enc.env`. Si une valeur a fuité, la seule vraie correction
  est de la régénérer, pas de supprimer le fichier.

## 5 quater. Les mises à jour suivantes

Une fois la stack en place, tout passe par le script à la racine :

```bash
ssh <serveur>
cd eldir && ./deploy.sh
```

Il fait un `git pull --ff-only`, regarde **ce qui a changé** entre l'ancien et
le nouveau HEAD, et ne reconstruit que ce qui est concerné :

| Ce qui change | Ce que `deploy.sh` reconstruit |
|---|---|
| `backend/` | le service `backend` |
| `backend/docker/session/` | l'image des sessions `eldir-session:local`, construite **avant** le redémarrage du backend pour qu'il lance ses sessions sur l'image neuve. Et aussi le `backend`, puisque ce dossier est sous `backend/` |
| `docker/docker-proxy/` | le service `docker-proxy` |
| `frontend/` | le service `frontend` |
| `docker/caddy/`, `docker/Caddyfile` | le service `caddy` |
| `docker-compose.yml` | toute la stack |

Une PR qui ne touche que la doc ne reconstruit rien. L'image des sessions n'est
pas un service du compose : sans sa règle, un CLI épinglé qui change ne la
reconstruirait pas, et les nouvelles sessions démarreraient sans bruit sur
l'ancienne. Les sessions déjà ouvertes gardent l'image qu'elles ont.

**Pas mesuré : un déploiement qui recrée `docker-proxy` coupe probablement les flux
`attach` des sessions vivantes**, puisque le `docker run -i` de chacune passe par
lui. Évite de le déclencher pendant qu'une session travaille.

**Pas mesuré non plus : rien ne retire le conteneur d'une session si son CLI
ignore à la fois la fin de stdin et SIGTERM.** À l'arrêt, le SDK ferme stdin,
attend, envoie SIGTERM, attend, puis SIGKILL (lu dans `subprocess_cli.py`). Ce
SIGKILL ne touche que le client `docker run`, qui ne le relaie pas : le conteneur
resterait vivant. Pour voir s'il en traîne : `docker ps --filter
ancestor=eldir-session:local`.

Il prévient aussi quand un `.env.example` a changé, puisque ton `.env`, lui,
n'est pas versionné et ne se met pas à jour tout seul. Les migrations Alembic
sont jouées au démarrage du backend, il n'y a rien à lancer à la main.

`./deploy.sh --force` reconstruit tout, même sans nouveau commit.

## 6. Le compte admin

Le script d'install détecte une stack déjà lancée et lit le nom d'hôte dans
`.env` : il ne redémarre rien et parle à l'API publique.

```bash
cd ~/eldir && ./scripts/install-eldir.sh
```

Il te demande l'email, le mot de passe admin, et le mode d'authentification
Claude. Si tu préfères garder la main, le POST équivalent :

```bash
curl -sS https://eldir.mondomaine.fr/api/v1/setup/bootstrap \
  -H 'Content-Type: application/json' -d '{
    "bootstrap_token": "<celui des logs>",
    "admin_email": "moi@exemple.fr",
    "admin_password": "…",
    "admin_display_name": "Moi"
  }'
```

Le **token Claude Pro/Max se génère sur une machine avec navigateur**, donc pas
sur un VPS headless. Tu peux le poser après coup dans Settings > Claude.

Ensuite, `https://eldir.mondomaine.fr` depuis un appareil connecté au VPN, et
**Ajouter à l'écran d'accueil** sur ton téléphone.

## 7. Fermer la porte

```bash
sudo sed -i 's/^#\?PasswordAuthentication.*/PasswordAuthentication no/' /etc/ssh/sshd_config
sudo systemctl restart ssh
```

L'auth d'Eldir est mono-utilisateur : sa seule vraie protection, c'est de ne pas
être joignable. Vérifie que rien n'écoute en public :

```bash
ss -tlnp | grep -vE '127\.0\.0\.1|100\.64\.'   # seul :22 devrait rester
```

## Dépannage

**Le certificat ne sort pas.** `docker compose logs caddy` : une erreur 403 de
l'API OVH signifie des droits de token insuffisants (il faut les quatre verbes)
ou un endpoint qui ne correspond pas (`ovh-eu` pour un domaine .fr/.com acheté
en Europe).

**Tout répond 404 derrière Caddy.** Vérifie que le
[`Caddyfile`](../docker/Caddyfile) utilise `handle` et non `handle_path` : ce
dernier retire le préfixe, alors que le backend écoute bien sur `/api/v1/…` et
`/ws/sessions/…`.

**Une session Claude meurt en pleine tâche.** C'est l'OOM killer :
`dmesg | grep -i oom`. Baisse `MAX_CONCURRENT_SESSIONS`, ou stoppe une session
depuis le dashboard (elle reste reprenable).

**Une session échoue au démarrage (mode `conteneur`).** Le message est celui du
démon. Trois causes mesurées : `network ... not found` (créer `eldir-sessions`,
section 5 bis), `pull access denied for eldir-session` (construire l'image), et un
code de sortie 127 (un sous-chemin de volume absent : relis les noms de volumes,
section 5 bis). Il n'y a pas de repli en mode `processus`, c'est voulu.

**Après un échec de démarrage, la session repart de zéro et ne reprend plus.**
`resume` traite n'importe quel échec de démarrage comme un transcript perdu : il
efface `sdk_session_id` avant de réessayer. Un `docker run` qui échoue un instant
suffit, sans rapport avec le transcript. Connu, non corrigé (cf.
[`sessions.md`](./sessions.md#reprendre-une-session-après-redémarrage-eldir)).

**Le build du frontend échoue sans message clair.** Manque de RAM pendant
`vite build`. Vérifie le swap de l'étape 1, ou construis l'image ailleurs et
pousse-la sur un registre.
