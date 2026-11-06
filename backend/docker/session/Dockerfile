# Image des sessions Eldir : le CLI Claude (donc Node), git et ssh, sans aucun
# outil de projet.
#
# Le toolchain du projet n'est pas ici : il est monté en lecture seule depuis
# le volume des toolchains, au même chemin absolu que chez le backend. Une
# image par projet serait une image à reconstruire à chaque ajout d'outil,
# pour un gain nul.
#
# Construite par `docker build -t eldir-session:local backend/docker/session`.
FROM node:20-bookworm-slim

# Épinglée, et pas `latest` : un `docker build` refait dans six mois ne doit pas
# changer, sous un déploiement qui marche, le CLI qui exécute les sessions. C'est
# la version mesurée avec le SDK du backend (cf.
# docs/specs/2026-11-03-conteneur-par-session.md). On la remonte
# volontairement, avec `claude-agent-sdk` (backend/uv.lock), puis on vérifie
# avec une vraie session.
#
# Ce n'est pas le seul CLI du système, et les autres ne suivent pas ce numéro :
# le backend a le sien, installé à part. Le SDK en embarque un (celui des
# sessions en mode `processus`), et backend/Dockerfile en installe un en
# `latest` (celui que lance la sonde de credential,
# backend/app/services/claude_credential_service.py). Rien ne les aligne.
ARG CLAUDE_CLI_VERSION=2.1.316
ARG DEBIAN_FRONTEND=noninteractive

# Pour le build seulement, d'où des ARG et pas des ENV : elles servent à faire
# taire `npm install -g`, et n'ont rien à faire dans l'environnement d'une
# session, où `CI=true` en tête changerait le comportement des outils que
# l'agent lance.
ARG CI=true
ARG npm_config_fund=false
ARG npm_config_audit=false
ARG npm_config_update_notifier=false
ARG npm_config_progress=false

RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      git ca-certificates openssh-client \
 && rm -rf /var/lib/apt/lists/*

# Le cache npm (root, donc inutilisable par l'uid 1000) n'a pas sa place dans la
# couche.
RUN npm install -g @anthropic-ai/claude-code@${CLAUDE_CLI_VERSION} \
 && npm cache clean --force \
 && command -v claude

# La session lit son `config` SSH dans `/eldir/ssh/config` (cf.
# CONFIG_DANS_LE_CONTENEUR, backend/app/services/remote_access_service.py).
# Sans cette ligne `ssh` ne le trouverait pas : son chemin n'est ni
# `~/.ssh/config` ni un chemin système.
#
# Un projet sans accès distant n'a aucun montage SSH, donc rien à inclure. Le
# motif `config*` rend ce cas sûr par construction : un motif qui ne trouve rien
# est un usage que la config système de Debian fait elle-même (son
# `Include /etc/ssh/ssh_config.d/*.conf`, vide ici). Rien dans cette image
# n'épingle OpenSSH, donc on ne compte pas sur le comportement d'un chemin
# littéral absent, que celui de bookworm (9.2) se trouve ignorer aussi.
RUN sed -i '1i Include /eldir/ssh/config*' /etc/ssh/ssh_config

# node:20 fournit déjà un utilisateur d'uid 1000, qu'on garde. Le conteneur doit
# tourner avec l'uid du backend (1000 par défaut, cf. backend/Dockerfile) : les
# fichiers des volumes lui appartiennent, et `ssh` refuse un `config` qui n'est
# ni à son uid ni à root. Le CLI refuse par ailleurs `bypassPermissions` en
# root.
#
# Les deux points de montage existent dans l'image, à l'uid 1000 : sans eux,
# Docker créerait `/eldir` en root au premier montage.
RUN mkdir -p /eldir/maison /eldir/ssh \
 && chown -R 1000:1000 /eldir

# `--chmod` : le bit exécutable ne doit pas dépendre du mode du fichier dans le
# contexte de build (une archive ou un checkout peuvent le perdre).
COPY --chmod=0755 entree-session /usr/local/bin/entree-session

USER 1000:1000
WORKDIR /eldir/maison
ENTRYPOINT ["/usr/local/bin/entree-session"]
