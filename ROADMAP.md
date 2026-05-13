# 🔥 Eldir — Roadmap

> **Eldir** : du vieux norrois, "feu". Hub multi-agents Claude qui allume et orchestre plusieurs sessions Claude Code en parallèle sur tes repos.

---

## 🎯 Vision

Dashboard web open-source self-hosted pour orchestrer plusieurs sessions Claude Code en parallèle sur différents repos Git (GitHub et/ou Forgejo).

**Philosophie** : souveraineté numérique, anti-vendor-lock-in, données chez l'utilisateur, installation simple, communauté ouverte.

**Promesse utilisateur** : `git clone` → `docker compose up` → setup wizard web → opérationnel en moins de 10 minutes.

---

## 🧭 Principes directeurs (non-négociables)

1. **Self-hosted first** — conçu pour tourner sur le serveur de l'utilisateur, pas en SaaS centralisé
2. **Multi-Git-provider** — GitHub et Forgejo natifs en V1, autres providers via plugins communautaires
3. **Claude only** — pas de support pour OpenAI, Gemini ou autres LLM cloud (sauf Ollama local en complément)
4. **Token-conscious by design** — chaque feature pensée pour minimiser la consommation de tokens
5. **L'utilisateur reste maître** — alertes, jamais de blocages forcés
6. **Easy install** — Docker Compose + setup wizard web, sans expertise DevOps requise
7. **Documentation > code** — chaque feature livrée avec sa doc utilisateur ET sa doc dev
8. **Open governance** — l'install propose Headscale + Forgejo pour souveraineté complète
9. **Identité visuelle Claude** — palette aux couleurs Anthropic (orange `#D97757`, crème, noir)
10. **Mobile-first** 📱 — chaque interface conçue pour mobile en premier, puis adaptée
11. **Progressive Web App** 📲 — installable, mode hors-ligne, expérience native dès la Phase 0
12. **DRY strict** 🔁 — aucune duplication tolérée, factorisation systématique, types partagés générés depuis le backend

---

## 🏗️ Stack technique

| Couche | Techno | Justification |
|---|---|---|
| Backend | FastAPI + Python 3.12+ | Async natif, WebSocket robuste, écosystème AI |
| Agent runtime | Claude Agent SDK Python | Officiel Anthropic, sessions persistantes natives |
| DB principale | PostgreSQL 16 | Sessions, users, projets, mission templates |
| Cache + pub/sub | Redis 7 | Events temps réel, queue de tâches |
| Frontend | React 18 + Vite + TypeScript | Standard 2026 |
| UI components | Tailwind CSS + shadcn/ui | Design system cohérent |
| State client | TanStack Query + Zustand | Server state + client state |
| Realtime | WebSocket natif FastAPI | Streaming tokens + events hooks |
| Workspaces | Git worktrees | Plusieurs sessions simultanées sur même repo |
| Auth utilisateur | JWT local | Mono-user en V1 |
| Auth Claude | API key OU compte Pro/Max | Choix utilisateur |
| Auth Git | OAuth GitHub + PAT Forgejo | Multi-provider |
| Deploy | Docker Compose | Standard self-host |

---

## 🎨 Identité visuelle

**Palette** (couleurs Claude / Anthropic) :
- Orange principal : `#D97757`
- Crème / fond : `#F4F1EA`
- Noir profond : `#1A1A1A`
- Gris subtil : `#8B8680`
- Accents : `#C9A87C` (sable doré)

**Typo** : à choisir en Phase 0 (suggestions : Inter pour UI, JetBrains Mono pour code)

**Esprit** : minimaliste, chaleureux, terreux, pas de néon ni gradient SaaS générique.

---

## 📦 Phasage

### Phase 0 — Fondations (semaine 1-2)

**Objectif** : poser les bases techniques et identitaires.

- [ ] Init repo public GitHub `eldir` avec licence **AGPL v3**
- [ ] README "vision + statut" avec animation de l'identité
- [ ] Charte graphique aux couleurs Claude
- [ ] Logo et favicon
- [ ] Monorepo : `/backend` (FastAPI), `/frontend` (React+Vite), `/shared`, `/docs`, `/docker`, `/scripts`
- [ ] CI GitHub Actions : tests, lint, build images Docker, push Docker Hub
- [ ] CI Lighthouse sur PR : score PWA > 90 obligatoire
- [ ] `docker-compose.yml` minimal qui boot Postgres + Redis + backend + frontend
- [ ] Setup wizard web v0 : première connexion → admin + tokens
- [ ] **Configuration PWA complète dès le bootstrap** :
  - [ ] `vite-plugin-pwa` configuré dans `vite.config.ts`
  - [ ] `manifest.webmanifest` complet (icônes 192/512/maskable, theme_color)
  - [ ] Service Worker avec stratégies de cache
  - [ ] Splash screen aux couleurs Claude
  - [ ] Test installation iOS Safari + Android Chrome
- [ ] **Configuration mobile-first** :
  - [ ] Layout root responsive testé sur 375×667px
  - [ ] Tailwind config avec breakpoints standards
  - [ ] Tap targets 44×44px minimum dans le design system
- [ ] **Pipeline DRY** :
  - [ ] Génération automatique des types TS depuis schémas Pydantic (script + CI)
  - [ ] Client API frontend généré ou centralisé
- [ ] Doc d'installation v0 (`docs/install.md`)
- [ ] Templates de PR et issues GitHub
- [ ] `CONTRIBUTING.md` et `CODE_OF_CONDUCT.md`

### Phase 1 — MVP : 1 user, 1 projet, 1 session (semaine 3-5)

**Objectif** : pouvoir lancer une session Claude sur un repo et chatter avec depuis le web.

- [ ] Auth utilisateur locale (JWT)
- [ ] Choix du mode auth Claude :
  - [ ] Mode API key (`ANTHROPIC_API_KEY` configuré dans settings)
  - [ ] Mode compte Claude Pro/Max (auth via session Claude Code locale)
- [ ] OAuth GitHub → liste des repos accessibles
- [ ] Sélection d'un repo → clone automatique côté serveur dans `/var/eldir/workspaces/{user}/{repo}/`
- [ ] Création d'un nouveau repo GitHub depuis le dashboard
- [ ] Bouton "Nouvelle session" → instancie un `ClaudeSDKClient`
- [ ] Chat UI minimal : input, messages, streaming tokens via WebSocket
- [ ] Capture du `session_id` SDK + persistence en Postgres
- [ ] Bouton "Reprendre session" → utilise `resume=session_id`
- [ ] Bouton "Commit & Push" → git ops via le SDK
- [ ] Documentation utilisateur de la phase (`docs/getting-started.md`)

### Phase 2 — Multi-sessions parallèles (semaine 6-7)

**Objectif** : le cœur du projet. Bosser sur 3 repos en même temps.

- [ ] Architecture `SessionManager` : pool d'agents SDK actifs en mémoire
- [ ] Git worktrees pour avoir N sessions sur le même repo
- [ ] UI à onglets : tab par session active, switch rapide
- [ ] Badge "agent en train de bosser" par tab
- [ ] Indicateurs visuels d'état : `idle` / `thinking` / `tool_use` / `waiting_input` / `blocked`
- [ ] Hooks SDK `PreToolUse` / `PostToolUse` / `Stop` → events Redis pubsub → frontend
- [ ] Diff viewer en temps réel (fichiers modifiés en live)
- [ ] Background tasks : sessions qui continuent même quand tab fermé, avec notifications au retour
- [ ] Indicateur "X agents actifs" dans le header

### Phase 3 — Multi-provider Git (semaine 8)

**Objectif** : élargir aux utilisateurs Forgejo et offrir une vue unifiée.

- [ ] Refactor en `GitProviderInterface` (clone, list_repos, create_repo, create_pr, get_branches…)
- [ ] Implémentation `GitHubProvider` (déjà fait phase 1)
- [ ] Implémentation `ForgejoProvider`
- [ ] Vue unifiée GitHub + Forgejo dans le dashboard
- [ ] Création de repo Forgejo depuis le dashboard
- [ ] UI "Ajouter un Git provider" dans les settings
- [ ] Gestion multi-providers simultanés (un user peut avoir GitHub + Forgejo connectés)
- [ ] Documentation provider Forgejo (`docs/providers/forgejo.md`)

### Phase 4 — Mission Templates & Skills (semaine 9-10)

**Objectif** : rendre le hub vraiment puissant pour l'usage quotidien.

- [ ] Concept `MissionTemplate` : system prompt + tools autorisés + skills + sub-agents associés à un repo
- [ ] UI "Configurer le template du projet" : éditeur visuel
- [ ] Templates pré-définis téléchargeables : Django, FastAPI, React, Flutter, n8n, Astro…
- [ ] Éditeur de skills `.claude/skills/` directement depuis le dashboard
- [ ] Éditeur de sub-agents (description + system prompt + outils)
- [ ] Versionnage des templates dans Postgres (rollback possible)
- [ ] Library publique de skills partagée par la communauté (V2)

### Phase 5 — Optimisation tokens (semaine 11)

**Objectif** : rendre Eldir économe en tokens par défaut.

- [ ] **Compaction automatique du contexte** : hook qui détecte l'approche des limites et résume la conversation ancienne
- [ ] **Prompt caching** : système Anthropic activé par défaut sur les system prompts longs (économie 90% sur cache hits)
- [ ] **Mode "économe"** : Haiku par défaut, escalade vers Sonnet/Opus si nécessaire
- [ ] **Token budget par session** : alerte (jamais blocage) quand X tokens dépassés
- [ ] **Dashboard de coûts** : OpenTelemetry du SDK + visualisation par session/projet/jour/mois
- [ ] **Mode plan-only** : forcer Claude à proposer un plan avant action
- [ ] **Sub-agents Haiku** pour tâches déterministes (recherche, classification)
- [ ] Export CSV des coûts pour facturation/comptabilité

### Phase 6 — Intégration Ollama (semaine 12)

**Objectif** : tirer parti d'Ollama local pour économies et données sensibles.

- [ ] Configuration Ollama dans les settings (URL, modèles disponibles)
- [ ] **Mode dual backend par session** :
  - [ ] Backend "Claude Agent SDK" (par défaut)
  - [ ] Backend "Claude Code CLI + Ollama" (modèle local pilote, outils Claude Code)
- [ ] Sub-agent type `OllamaSubAgent` pour tâches simples
- [ ] **Mode "données sensibles"** : pré-traitement Ollama (anonymisation/masquage) avant envoi à Claude
- [ ] Routes spécifiques : "résumer ce gros fichier en local avant de l'envoyer à Claude"
- [ ] Documentation des modes (`docs/ollama-integration.md`)

### Phase 7 — Souveraineté complète (V2/V3)

**Objectif** : l'install d'Eldir devient une porte d'entrée vers la souveraineté numérique.

- [ ] Setup wizard étendu : option "installer aussi Forgejo et Headscale"
- [ ] Configuration Forgejo depuis le dashboard : ajout admins, règles, hooks, runners
- [ ] Configuration Headscale depuis le dashboard : ajout/suppression de nœuds, ACLs, pre-auth keys
- [ ] Tutoriels intégrés : Headscale, Forgejo, sécurisation VPS, sauvegardes
- [ ] **Mode "agent local" via Headscale** : exécuter les sessions sur la machine de l'utilisateur (PC pop-os, laptop) plutôt que sur le serveur
- [ ] Backup automatique chiffré des sessions (S3-compatible / Backblaze / local)
- [ ] Restauration en un clic depuis le dashboard

---

## 💎 Idées différenciatrices (les "game changers")

Ces idées sont à intégrer au bon moment dans le phasage :

1. **Mission Templates par repo** — Phase 4 ✅
2. **Cross-session awareness** — Phase 5/6 — un agent peut consulter (read-only) le state d'un autre
3. **Mode "supervisor"** — V2 — un agent chef d'orchestre qui délègue aux agents-projets selon des instructions de haut niveau
4. **Library de skills communautaires** — V2 — partage et installation de skills depuis une marketplace open-source
5. **Setup wizard souveraineté** — Phase 7 ✅
6. **Mode données sensibles via Ollama** — Phase 6 ✅
7. **Templates téléchargeables par stack** — Phase 4 ✅

---

## 🚧 Décisions actées

| Décision | Choix |
|---|---|
| **Nom du projet** | Eldir |
| **Licence** | AGPL v3 (à valider définitivement) |
| **Déploiement V1 cible** | johnserver |
| **Mono-user vs multi-user V1** | Mono-user (multi-user en V2) |
| **Stratégie tokens** | Alerte uniquement, jamais de blocage |
| **LLM providers** | Claude only + Ollama local en complément |
| **Git providers V1** | GitHub + Forgejo natifs |

---

## 🎯 Métriques de succès

**V1 (fin Phase 5)** :
- [ ] Installation fonctionnelle en moins de 10 minutes sur un VPS frais
- [ ] 3 sessions Claude actives simultanément sur 3 repos différents sans crash
- [ ] Documentation complète permettant à un dev externe de contribuer
- [ ] Au moins 5 templates de mission pré-définis utilisables

**V2 (fin Phase 7)** :
- [ ] 50+ stars GitHub
- [ ] 5+ contributeurs externes
- [ ] Setup wizard "souveraineté complète" qui installe Eldir + Forgejo + Headscale
- [ ] Library communautaire avec 20+ skills partagés

---

## 🗓️ Timeline estimée

| Phase | Durée | Cumul |
|---|---|---|
| Phase 0 | 2 semaines | 2 sem |
| Phase 1 | 3 semaines | 5 sem |
| Phase 2 | 2 semaines | 7 sem |
| Phase 3 | 1 semaine | 8 sem |
| Phase 4 | 2 semaines | 10 sem |
| Phase 5 | 1 semaine | 11 sem |
| Phase 6 | 1 semaine | 12 sem |
| **V1 livrable** | | **~3 mois** |
| Phase 7 | 4-6 semaines | V2 |

> Estimation basée sur un travail à temps partiel (un projet parmi d'autres). À ajuster selon disponibilité.
