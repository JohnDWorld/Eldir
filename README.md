<div align="center">

# 🔥 Eldir

**Le hub multi-agents Claude pour orchestrer plusieurs sessions Claude Code en parallèle.**

*Du vieux norrois : "feu". Eldir allume et orchestre tes agents.*

[![License: AGPL v3](https://img.shields.io/badge/License-AGPL_v3-D97757.svg)](https://www.gnu.org/licenses/agpl-3.0)
[![Status: Alpha](https://img.shields.io/badge/Status-Alpha-orange.svg)]()
[![Self-hosted](https://img.shields.io/badge/Self--hosted-First-1A1A1A.svg)]()
[![PWA](https://img.shields.io/badge/PWA-Ready-D97757.svg)]()

[Installation](./docs/installation.md) · [Architecture](./docs/architecture.md) · [Documentation](./docs) · [Roadmap](./ROADMAP.md) · [Contribuer](./CONTRIBUTING.md)

</div>

---

> **Eldir est à Claude Cowork ce que Forgejo est à GitHub, ou Mastodon à Twitter :**
> *la même idée, en version souveraine, open-source, et chez toi.*

---

## 🎯 Le problème

Tu jongles entre plusieurs projets de dev. Tu lances une session Claude Code sur ton appli React, puis tu veux faire avancer ton backend Django, puis ton script Flutter. Aujourd'hui, c'est :

- 🪟 Plusieurs terminaux ouverts en même temps
- 🤯 Du contexte mental éclaté entre plusieurs sessions
- 📱 Impossible de piloter tout ça depuis ton téléphone
- 💸 Aucune visibilité sur les coûts en tokens
- 🔌 Tes données et ton workflow couplés à un SaaS

## 💡 La solution

Eldir est un **dashboard web self-hosted** qui te permet de :

- 🚀 Lancer **plusieurs sessions Claude Code en parallèle** sur différents repos
- 💬 **Chatter avec chaque agent** depuis une seule interface
- 🌐 Travailler avec **GitHub ET Forgejo** dans la même vue unifiée
- 📲 Tout piloter depuis ton **téléphone** (PWA installable)
- 💰 Voir les coûts en tokens **en temps réel**
- 🏠 Tout héberger **sur ton serveur**, tes données restent chez toi

## ⚖️ Eldir vs Claude Cowork

Anthropic a lancé Cowork pour orchestrer des agents IA. Eldir part de la même idée, mais pour un public différent et avec une philosophie radicalement opposée.

|  | **Claude Cowork** | **Eldir** |
|---|---|---|
| **Hébergement** | SaaS Anthropic | Self-hosted, chez toi |
| **Données** | Stockées par Anthropic | Restent sur ton serveur |
| **Cible** | Knowledge workers, équipes pro | Devs souverains, indie hackers |
| **Domaine** | Generic (docs, mail, slides…) | Dev pur (repos Git, code) |
| **Git providers** | GitHub uniquement | GitHub **+ Forgejo** natifs |
| **Licence** | Propriétaire | AGPL v3 - modifiable, forkable |
| **Mobile** | Desktop-first | **Mobile-first PWA** installable |
| **Coût** | Abonnement Anthropic | Gratuit (hors tokens API) |
| **Extensible** | Limité aux connecteurs officiels | Skills, sub-agents et templates custom |

**Cowork s'adresse aux équipes qui veulent un outil clé en main.**
**Eldir s'adresse aux devs qui veulent reprendre la main sur leurs outils.**

## ✨ Fonctionnalités clés

### 🔄 Multi-sessions parallèles
Lance autant d'agents Claude que tu veux, sur autant de repos que tu veux. Chaque session est isolée dans son propre git worktree. Switch entre les sessions en un clic, les autres continuent à bosser en background.

### 🌍 Multi-Git providers natif
GitHub et Forgejo sont supportés en first-class. Liste tes repos, crée des nouveaux repos, ouvre des PRs - tout depuis le dashboard. Provider-agnostic by design, GitLab et Gitea via plugins communautaires.

### 🎨 Mission Templates par projet
Configure une fois les conventions de chaque repo (system prompt, skills, sub-agents, branches…), Eldir applique automatiquement le bon template à chaque session sur ce repo. Tes conventions deviennent automatiques.

### 🧠 Sub-agents et Skills depuis l'UI
Crée et édite tes skills `.claude/skills/` et tes sub-agents directement depuis le dashboard. Plus besoin d'éditer des fichiers à la main. À terme, une library communautaire pour partager les skills entre utilisateurs.

### 💸 Optimisation tokens by design
Prompt caching activé par défaut, mode "économe" avec Haiku, compaction automatique du contexte, dashboard de coûts par session/projet/jour. **Tu restes maître : alertes uniquement, jamais de blocage forcé.**

### 🛡️ Souveraineté totale
Self-hosted dès le départ. À terme, le setup wizard propose l'installation de Forgejo et Headscale pour une stack 100% chez toi. Eldir devient une porte d'entrée vers la souveraineté numérique complète.

### 🦙 Mode données sensibles (Ollama)
Branche Ollama en local pour pré-traiter les données sensibles (anonymisation, masquage) avant envoi à Claude. Tes secrets ne quittent jamais ton réseau.

### 📲 PWA mobile-first
Installable sur ton téléphone comme une app native. Conçu d'abord pour mobile, puis adapté pour desktop. Pilote tes agents en bivouac, en déplacement, ou depuis ton canapé.

## 🚀 Installation

> **Prérequis** : un serveur avec Docker et Docker Compose installés.

```bash
# Cloner le repo
git clone https://github.com/JohnDWorld/Eldir.git
cd Eldir

# Lancer la stack dev (script guidé)
./scripts/install-eldir.sh

# Ou manuellement
docker compose -f docker-compose.dev.yml up -d
# puis suivre les étapes dans docs/installation.md
```

Une fois en route :

- Frontend : http://localhost:5173
- API : http://localhost:8000/api/v1

C'est tout. En moins de 10 minutes tu chattes avec ton premier agent Claude depuis le dashboard.

📖 [Bien démarrer](./docs/getting-started.md) · [Le superviseur](./docs/supervisor.md) · [Guide d'installation](./docs/installation.md) · [Configuration GitHub](./docs/github.md) · [Configuration Forgejo](./docs/providers/forgejo.md)

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

Développement phasé. Statut à jour dans [ROADMAP.md](./ROADMAP.md).

- ✅ **Phase 0** - Fondations
- ✅ **Phase 1** - MVP : 1 session Claude depuis le dashboard
- ✅ **Phase 2** - Multi-sessions parallèles (worktrees, diff live)
- ✅ **Phase 3** - Multi-provider Git (GitHub + Forgejo)
- ✅ **Phase 4** - Mission Templates & Skills
- ✅ **Phase 5** - Optimisation tokens (dashboard de coûts, prompt caching, mode économe)
- ✅ **Phase 6** - Intégration Ollama (mode "données sensibles" — masquage/anonymisation/résumé en local)
- ✅ **Superviseur** - une seule conversation qui pilote toutes les sessions, comptes rendus `<cr>`, sync auto des repos
- ⏳ **Phase 7** - Souveraineté complète (Headscale + Forgejo intégrés) — V2

[→ Roadmap détaillée](./ROADMAP.md)

## 🎯 Pour qui ?

Eldir est fait pour toi si :

- 🧑‍💻 Tu es **dev solo ou en petite équipe** et tu jongles entre plusieurs projets
- 🛡️ Tu veux **garder le contrôle de tes données** et de ton workflow
- 🏗️ Tu utilises **Forgejo, Gitea ou un Git self-hosted** (et tu en as marre que personne ne le supporte)
- 📲 Tu bosses parfois en **mobilité** et tu veux pouvoir piloter tes projets depuis ton téléphone
- 🔧 Tu aimes **modifier tes outils** et que ton outillage reflète ta façon de bosser
- 💸 Tu veux **maîtriser tes coûts en tokens** plutôt que de subir un abonnement opaque

Eldir n'est **pas** fait pour toi si tu cherches un outil clé en main que tu paies et qui décide tout pour toi. Pour ça, Cowork est très bien.

## 🤝 Contribuer

Eldir est un projet open-source destiné à la communauté des devs qui veulent reprendre la main sur leurs outils. Toute contribution est la bienvenue : code, doc, retours UX, idées, skills à partager.

[→ Guide de contribution](./CONTRIBUTING.md)

## 💬 Communauté

- 🐛 [Signaler un bug](https://github.com/JohnDWorld/Eldir/issues/new)
- 💡 [Proposer une feature](https://github.com/JohnDWorld/Eldir/issues/new)
- 💬 [Discussions](https://github.com/JohnDWorld/Eldir/discussions)

## 📜 Licence

Eldir est distribué sous licence **[AGPL v3](./LICENSE)**.

En clair : tu peux utiliser, modifier et redistribuer Eldir librement. Si tu en fais un service en ligne (SaaS), tu dois publier tes modifications sous la même licence. Cette clause garantit que les améliorations bénéficient à toute la communauté plutôt qu'à des forks fermés.

## 🙏 Crédits et inspirations

Eldir est construit sur les épaules de géants :

- [Claude Agent SDK](https://github.com/anthropics/claude-agent-sdk-python) par Anthropic
- [FastAPI](https://fastapi.tiangolo.com/) par Sebastián Ramírez
- [shadcn/ui](https://ui.shadcn.com/) par shadcn
- [Forgejo](https://forgejo.org/) par la communauté Forgejo

Inspiré dans sa philosophie par tous les projets qui prouvent qu'on peut faire mieux en open-source : Forgejo, Mastodon, Nextcloud, Headscale, n8n, Ollama. Eldir prolonge leur combat.

---

<div align="center">

**Arrêtons d'être l'esclave de nos outils informatiques.**

*Made with 🔥 by [La Boutique à Automatisations](#)*

</div>
