<div align="center">

# 🔥 Eldir

**Le hub multi-agents Claude pour orchestrer plusieurs sessions Claude Code en parallèle.**

*Du vieux norrois : "feu". Eldir allume et orchestre tes agents.*

[![License: AGPL v3](https://img.shields.io/badge/License-AGPL_v3-D97757.svg)](https://www.gnu.org/licenses/agpl-3.0)
[![Status: Alpha](https://img.shields.io/badge/Status-Alpha-orange.svg)]()
[![Self-hosted](https://img.shields.io/badge/Self--hosted-First-1A1A1A.svg)]()
[![PWA](https://img.shields.io/badge/PWA-Ready-D97757.svg)]()

[Démo](#) · [Installation](#-installation) · [Documentation](./docs) · [Roadmap](./ROADMAP.md) · [Contribuer](./CONTRIBUTING.md)

</div>

---

## 🎯 Le problème

Tu jongles entre plusieurs projets de dev. Tu lances une session Claude Code sur ton appli React, puis tu veux faire avancer ton backend Django, puis ton script Flutter. Aujourd'hui, c'est :

- 🪟 Plusieurs terminaux ouverts en même temps
- 🤯 Du contexte mental éclaté entre plusieurs sessions
- 📱 Impossible de piloter tout ça depuis ton téléphone
- 💸 Aucune visibilité sur les coûts en tokens
- 🔌 Coupler ton workflow à un éditeur ou un OS

## 💡 La solution

Eldir est un **dashboard web self-hosted** qui te permet de :

- 🚀 Lancer **plusieurs sessions Claude Code en parallèle** sur différents repos
- 💬 **Chatter avec chaque agent** depuis une seule interface
- 🌐 Travailler avec **GitHub ET Forgejo** dans la même vue unifiée
- 📲 Tout piloter depuis ton **téléphone** (PWA installable)
- 💰 Voir les coûts en tokens **en temps réel**
- 🏠 Tout héberger **sur ton serveur**, tes données restent chez toi

## ✨ Fonctionnalités clés

### 🔄 Multi-sessions parallèles
Lance autant d'agents Claude que tu veux, sur autant de repos que tu veux. Chaque session est isolée dans son propre git worktree. Switch entre les sessions en un clic, les autres continuent à bosser en background.

### 🌍 Multi-Git providers natif
GitHub et Forgejo sont supportés en first-class. Liste tes repos, crée des nouveaux repos, ouvre des PRs — tout depuis le dashboard. Provider-agnostic by design.

### 🎨 Mission Templates par projet
Configure une fois les conventions de chaque repo (system prompt, skills, sub-agents, branches…), Eldir applique automatiquement le bon template à chaque session sur ce repo.

### 🧠 Sub-agents et Skills depuis l'UI
Crée et édite tes skills `.claude/skills/` et tes sub-agents directement depuis le dashboard. Plus besoin d'éditer des fichiers à la main.

### 💸 Optimisation tokens by design
Prompt caching activé par défaut, mode "économe" avec Haiku, compaction automatique du contexte, dashboard de coûts par session/projet/jour. Tu restes maître : alertes uniquement, jamais de blocage forcé.

### 🛡️ Souveraineté totale
Self-hosted dès le départ. Setup wizard qui propose à terme l'installation de Forgejo et Headscale pour une stack 100% chez toi.

### 📲 PWA mobile-first
Installable sur ton téléphone comme une app native. Conçu d'abord pour mobile, puis adapté pour desktop. Travaille où que tu sois.

## 🚀 Installation

> **Prérequis** : un serveur avec Docker et Docker Compose installés.

```bash
# Cloner le repo
git clone https://github.com/[your-username]/eldir.git
cd eldir

# Lancer la stack
docker compose up -d

# Ouvrir le navigateur sur http://your-server:8080
# Le setup wizard te guide pour la première configuration
```

C'est tout. En moins de 10 minutes tu chattes avec ton premier agent Claude depuis le dashboard.

📖 [Guide d'installation détaillé](./docs/install.md) · [Configuration Forgejo](./docs/providers/forgejo.md) · [Mode hors-ligne PWA](./docs/pwa.md)

## 🏗️ Stack

| Couche | Techno |
|---|---|
| Backend | FastAPI + Python 3.12 |
| Agent runtime | Claude Agent SDK |
| Frontend | React 18 + Vite + TypeScript |
| UI | Tailwind CSS + shadcn/ui |
| DB | PostgreSQL 16 + Redis 7 |
| Deploy | Docker Compose |

[→ Voir l'architecture complète](./docs/architecture.md)

## 🗺️ Roadmap

Eldir est en développement actif. La V1 est prévue en ~3 mois avec un développement phasé :

- ✅ **Phase 0** — Fondations (en cours)
- ⏳ **Phase 1** — MVP : 1 session Claude depuis le dashboard
- ⏳ **Phase 2** — Multi-sessions parallèles
- ⏳ **Phase 3** — Multi-provider Git (GitHub + Forgejo)
- ⏳ **Phase 4** — Mission Templates & Skills
- ⏳ **Phase 5** — Optimisation tokens
- ⏳ **Phase 6** — Intégration Ollama
- ⏳ **Phase 7** — Souveraineté complète (Headscale + Forgejo intégrés)

[→ Roadmap détaillée](./ROADMAP.md)

## 🤝 Contribuer

Eldir est un projet open-source destiné à la communauté des devs qui veulent reprendre la main sur leurs outils. Toute contribution est la bienvenue : code, doc, retours UX, idées.

[→ Guide de contribution](./CONTRIBUTING.md)

## 💬 Communauté

- 🐛 [Signaler un bug](https://github.com/[your-username]/eldir/issues/new?template=bug.md)
- 💡 [Proposer une feature](https://github.com/[your-username]/eldir/issues/new?template=feature.md)
- 💬 [Discussions](https://github.com/[your-username]/eldir/discussions)

## 📜 Licence

Eldir est distribué sous licence **[AGPL v3](./LICENSE)**.

En clair : tu peux utiliser, modifier et redistribuer Eldir librement. Si tu en fais un service en ligne (SaaS), tu dois publier tes modifications sous la même licence. Cette clause garantit que les améliorations bénéficient à toute la communauté plutôt qu'à des forks fermés.

## 🙏 Crédits

Eldir est construit sur les épaules de géants :

- [Claude Agent SDK](https://github.com/anthropics/claude-agent-sdk-python) par Anthropic
- [FastAPI](https://fastapi.tiangolo.com/) par Sebastián Ramírez
- [shadcn/ui](https://ui.shadcn.com/) par shadcn
- [Forgejo](https://forgejo.org/) par la communauté Forgejo

---

<div align="center">

**Arrêtons d'être l'esclave de nos outils informatiques.**

*Made with 🔥 by [La Boutique à Automatisations](#)*

</div>
