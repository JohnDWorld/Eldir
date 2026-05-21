# 🔥 Eldir - Roadmap

> **Eldir** : du vieux norrois, "feu". Hub multi-agents Claude qui allume et orchestre plusieurs sessions Claude Code en parallèle sur tes repos.

---

## 🎯 Vision

Dashboard web open-source self-hosted pour orchestrer plusieurs sessions Claude Code en parallèle sur différents repos Git (GitHub et/ou Forgejo).

**Philosophie** : souveraineté numérique, anti-vendor-lock-in, données chez l'utilisateur, installation simple, communauté ouverte.

**Promesse utilisateur** : `git clone` → `docker compose up` → setup wizard web → opérationnel en moins de 10 minutes.

---

## 🧭 Principes directeurs (non-négociables)

1. **Self-hosted first** - conçu pour tourner sur le serveur de l'utilisateur, pas en SaaS centralisé
2. **Multi-Git-provider** - GitHub et Forgejo natifs en V1, autres providers via plugins communautaires
3. **Claude only** - pas de support pour OpenAI, Gemini ou autres LLM cloud (sauf Ollama local en complément)
4. **Token-conscious by design** - chaque feature pensée pour minimiser la consommation de tokens
5. **L'utilisateur reste maître** - alertes, jamais de blocages forcés
6. **Easy install** - Docker Compose + setup wizard web, sans expertise DevOps requise
7. **Documentation > code** - chaque feature livrée avec sa doc utilisateur ET sa doc dev
8. **Open governance** - l'install propose Headscale + Forgejo pour souveraineté complète
9. **Identité visuelle Claude** - palette aux couleurs Anthropic (orange `#D97757`, crème, noir)
10. **Mobile-first** 📱 - chaque interface conçue pour mobile en premier, puis adaptée
11. **Progressive Web App** 📲 - installable, mode hors-ligne, expérience native dès la Phase 0
12. **DRY strict** 🔁 - aucune duplication tolérée, factorisation systématique, types partagés générés depuis le backend

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

> **Statut au 2026-05-21** : Phases 0 → 6 livrées (V1 complet).
> Prochain chantier potentiel : **Phase 7 - Souveraineté complète** (Forgejo/Headscale dans le wizard, mode agent local, backup chiffré) — c'est V2.
> Reste pour V2 : compaction auto contexte, mode plan-only, sub-agents Haiku auto-routing, OllamaSubAgent invocable par Claude.

### Phase 0 - Fondations ✅

**Objectif** : poser les bases techniques et identitaires.

- [x] Init repo public GitHub `eldir` avec licence **AGPL v3**
- [x] README "vision + statut" avec animation de l'identité
- [x] Charte graphique aux couleurs Claude
- [x] Logo et favicon
- [x] Monorepo : `/backend` (FastAPI), `/frontend` (React+Vite), `/shared`, `/docs`, `/docker`, `/scripts`
- [x] CI GitHub Actions : tests, lint, build (Docker Hub remis à V2)
- [ ] CI Lighthouse sur PR : score PWA > 90 obligatoire
- [x] `docker-compose.yml` minimal qui boot Postgres + Redis + backend + frontend
- [x] Setup wizard web v0 : première connexion → admin + tokens
- [x] **Configuration PWA complète dès le bootstrap** :
  - [x] `vite-plugin-pwa` configuré dans `vite.config.ts`
  - [x] `manifest.webmanifest` complet (icônes 192/512/maskable, theme_color)
  - [x] Service Worker avec stratégies de cache
  - [x] Splash screen aux couleurs Claude
  - [ ] Test installation iOS Safari + Android Chrome
- [x] **Configuration mobile-first** :
  - [x] Layout root responsive testé sur 375×667px
  - [x] Tailwind config avec breakpoints standards
  - [x] Tap targets 44×44px minimum dans le design system
- [x] **Pipeline DRY** :
  - [x] Génération automatique des types TS depuis schémas Pydantic (script + CI)
  - [x] Client API frontend généré ou centralisé
- [x] Doc d'installation v0 (`docs/install.md`)
- [ ] Templates de PR et issues GitHub
- [ ] `CONTRIBUTING.md` et `CODE_OF_CONDUCT.md`

### Phase 1 - MVP : 1 user, 1 projet, 1 session ✅

**Objectif** : pouvoir lancer une session Claude sur un repo et chatter avec depuis le web.

- [x] Auth utilisateur locale (JWT)
- [x] Choix du mode auth Claude :
  - [x] Mode API key (`ANTHROPIC_API_KEY` configuré dans settings)
  - [x] Mode compte Claude Pro/Max (auth via session Claude Code locale)
- [x] OAuth GitHub → liste des repos accessibles
- [x] Sélection d'un repo → clone automatique côté serveur dans `/var/eldir/workspaces/{user}/{repo}/`
- [x] Création d'un nouveau repo GitHub depuis le dashboard
- [x] Bouton "Nouvelle session" → instancie un `ClaudeSDKClient`
- [x] Chat UI minimal : input, messages, streaming tokens via WebSocket
- [x] Capture du `session_id` SDK + persistence en Postgres
- [x] Bouton "Reprendre session" → utilise `resume=session_id`
- [x] Bouton "Commit & Push" → git ops via le SDK
- [x] Documentation utilisateur de la phase (`docs/getting-started.md`)

### Phase 2 - Multi-sessions parallèles ✅ (quasi)

**Objectif** : le cœur du projet. Bosser sur 3 repos en même temps.

- [x] Architecture `SessionManager` : pool d'agents SDK actifs en mémoire
- [x] Git worktrees pour avoir N sessions sur le même repo
- [x] UI à onglets : tab par session active, switch rapide (Ops Home)
- [x] Badge "agent en train de bosser" par tab
- [x] Indicateurs visuels d'état : `idle` / `thinking` / `tool_use` / `waiting_input` / `blocked`
- [x] Hooks SDK `PreToolUse` / `PostToolUse` → events Redis pubsub → frontend (Stop dédupliqué via ResultMessage)
- [x] Diff viewer en temps réel (fichiers modifiés en live)
- [x] Background tasks : sessions qui continuent même quand tab fermé, avec notifications au retour (polling 5s + Notifications API + bouton activer dans Settings)
- [x] Indicateur "X agents actifs" dans le header (topbar + telemetry)

### Phase 3 - Multi-provider Git ✅ (quasi)

**Objectif** : élargir aux utilisateurs Forgejo et offrir une vue unifiée.

- [x] Refactor en `GitProviderInterface` (clone, list_repos, create_repo, create_pr, get_branches…)
- [x] Implémentation `GitHubProvider` (déjà fait phase 1)
- [x] Implémentation `ForgejoProvider`
- [x] Vue unifiée GitHub + Forgejo dans le dashboard
- [x] Création de repo Forgejo depuis le dashboard (`ForgejoProvider.create_repo` implémenté via API REST v1)
- [x] UI "Ajouter un Git provider" dans les settings
- [x] Gestion multi-providers simultanés (un user peut avoir GitHub + Forgejo connectés)
- [ ] Documentation provider Forgejo (`docs/providers/forgejo.md`)

### Phase 4 - Mission Templates & Skills ✅

**Objectif** : rendre le hub vraiment puissant pour l'usage quotidien.

- [x] Concept `MissionTemplate` : system prompt + tools autorisés + skills + sub-agents associés à un repo
- [x] UI "Configurer le template du projet" : éditeur visuel
- [x] Templates pré-définis téléchargeables : preset `eldir` (self-hosted) livré ; preset par stack à enrichir au fil de l'eau
- [x] Éditeur de skills `.claude/skills/` directement depuis le dashboard
- [x] Éditeur de sub-agents (description + system prompt + outils)
- [x] Versionnage des templates dans Postgres (rollback possible)
- [ ] Library publique de skills partagée par la communauté (V2)

### Phase 5 - Optimisation tokens ✅ (livré)

**Objectif** : rendre Eldir économe en tokens par défaut.

- [x] **Capture usage** : parser `ResultMessage.usage` du SDK → table `session_costs` (tokens in/out/cache_read/cache_create + cost_usd, une ligne par tour)
- [x] **Dashboard de coûts** : agrégations par jour/projet/session + UI réelle (page `/costs`, télémétrie topbar)
- [x] **Prompt caching** : géré automatiquement par le CLI Claude Code sur system_prompt + tools stables (métrique `cache_read_tokens` visible dans le dashboard)
- [x] **Mode "économe"** : switch dans NewSessionDialog qui force Haiku 4.5 pour la session courante
- [x] **Token budget par session** : alerte visuelle dans le rail (seuil 1M tokens, jamais bloquant)
- [x] Export CSV des coûts pour facturation/comptabilité (`/api/v1/costs/export.csv`)
- [ ] **Compaction automatique du contexte** : hook qui détecte l'approche des limites et résume la conversation ancienne *(remis à V2)*
- [ ] **Mode plan-only** : forcer Claude à proposer un plan avant action *(remis à V2)*
- [ ] **Sub-agents Haiku** pour tâches déterministes (recherche, classification) *(déjà possible via le template, V2 pour l'auto-routing)*

### Phase 6 - Intégration Ollama ✅ (V1 livré, scope adapté)

**Objectif** : tirer parti d'Ollama local pour économies et données sensibles.

V1 livré :
- [x] Configuration Ollama (env `OLLAMA_BASE_URL` + `OLLAMA_DEFAULT_MODEL`)
- [x] `OllamaService` (httpx) + endpoints `/ollama/status` et `/ollama/transform`
- [x] **Mode "données sensibles"** : transformations locales `mask` / `anonymize` / `summarize` (le texte ne traverse JAMAIS Internet)
- [x] UI Settings > Ollama avec playground des 3 modes
- [x] Documentation (`docs/ollama-integration.md`)

Remis à V2 :
- [ ] **Mode dual backend par session** : Claude SDK reste la seule façon de piloter une session (trop de surface pour V1)
- [ ] Sub-agent type `OllamaSubAgent` directement invocable par Claude (V2)
- [ ] Auto-routing intelligent ("résumer ce gros fichier en local avant de l'envoyer à Claude" sans intervention manuelle)

### Phase 7 - Souveraineté complète (V2/V3)

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

1. **Mission Templates par repo** - Phase 4 ✅
2. **Cross-session awareness** - Phase 5/6 - un agent peut consulter (read-only) le state d'un autre
3. **Mode "supervisor"** - V2 - un agent chef d'orchestre qui délègue aux agents-projets selon des instructions de haut niveau
4. **Library de skills communautaires** - V2 - partage et installation de skills depuis une marketplace open-source
5. **Setup wizard souveraineté** - Phase 7 ✅
6. **Mode données sensibles via Ollama** - Phase 6 ✅
7. **Templates téléchargeables par stack** - Phase 4 ✅

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
