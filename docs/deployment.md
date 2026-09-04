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

## 5 bis. Versionner ses secrets (optionnel, SOPS + age)

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

**Le build du frontend échoue sans message clair.** Manque de RAM pendant
`vite build`. Vérifie le swap de l'étape 1, ou construis l'image ailleurs et
pousse-la sur un registre.
