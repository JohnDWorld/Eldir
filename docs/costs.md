# Tokens & coûts

> Phase 5 du ROADMAP. Suivi en temps réel des tokens et coûts USD basé sur `ResultMessage.usage` du Claude Agent SDK.

## Source des données

À chaque fin de tour, le SDK émet un `ResultMessage` qui contient :

```python
ResultMessage(
    subtype="success",
    duration_ms=12345,
    num_turns=1,
    total_cost_usd=0.0247,
    usage={
        "input_tokens": 1234,
        "output_tokens": 567,
        "cache_read_input_tokens": 8900,    # tokens lus depuis le cache (90% moins chers)
        "cache_creation_input_tokens": 0,
    },
    model_usage={
        "claude-opus-4-7": { ... },
    },
    ...
)
```

Le `SessionManager` capture ces valeurs dans `_consume_response` et publie un event `usage` qui est :

1. Diffusé en temps réel sur le WS (UI)
2. Persisté en DB dans `session_costs` via `CostService.record_turn()`

Une ligne `session_costs` par tour SDK — pas un agrégat par session — pour permettre toutes les agrégations possibles (par jour, par projet, par modèle).

## Quand ça se met à jour ?

**À la fin de chaque tour**, pas pendant. Le SDK ne renvoie l'usage qu'avec le `ResultMessage` final, pas en streaming token-par-token. Tu vois donc le coût sauter d'un coup quand l'agent annonce "TOUR TERMINÉ".

Le hook frontend `useSessionCostTotals` re-fetch toutes les 15s pour mettre à jour le panneau Cost en session. Le dashboard `/costs` re-fetch toutes les 30s.

## Dashboard `/costs`

Page complète accessible depuis la topbar **Costs**.

3 KPI cards :
- **Aujourd'hui** — depuis 00h UTC
- **7 derniers jours**
- **30 derniers jours**

Chaque card affiche : coût USD, nombre de tours, breakdown input/output/cache read/cache write, et le **cache ratio** (proportion de tokens lus depuis le cache vs envoyés).

3 sections :
- **Coût par jour (7 derniers jours)** — sparkline + tableau jour par jour
- **Tokens par jour** — sparkline d'évolution
- **Répartition par projet (30 jours)** — tableau trié par coût décroissant

Bouton **Export CSV** en haut à droite → télécharge `eldir-costs-YYYY-MM-DD.csv` avec une ligne par tour (utilisable pour facturation/comptabilité).

## Panneau Cost · session

Visible dans le rail droit de chaque session ouverte. Affiche :

- Coût USD total de la session
- Nombre de tours
- Tokens input / output / cache read avec ratio cache
- **Alerte rouge** si > 1 000 000 tokens cumulés (seuil dans `session-page.tsx:439`)

Cohérent avec le principe directeur #5 : **l'utilisateur reste maître, alertes uniquement, jamais de blocage**.

## Telemetry topbar (Ops home)

Sur `/` (Ops home), le rail telemetry du haut affiche :

- **Tokens** — total tokens du jour (input + output), avec sparkline 7 jours
- **Spend** — coût USD sur 7 jours, avec sparkline 7 jours

Le rail droit affiche un panneau "Spend · 7-day" plus large avec lien vers `/costs`.

## Mode économe

Switch dans la modale **+ NEW SESSION**. Quand activé, force `model: claude-haiku-4-5-20251001` pour la session courante, ignorant le modèle configuré dans le Mission Template.

Haiku ≈ 1/15 du prix d'Opus en output token. À utiliser pour les tâches déterministes (recherche, classification, refactos simples).

## Prompt caching

Géré **automatiquement** par le CLI Claude Code dès qu'on passe par `ClaudeAgentOptions(system_prompt=…)`. Le CLI injecte les marqueurs `cache_control` sur le system_prompt + la liste d'outils, ce qui rend les tours suivants jusqu'à 90% moins coûteux côté tokens d'entrée.

Pré-requis : le system_prompt + tools doit dépasser ~1024 tokens (le seuil Anthropic). Pour la majorité des templates Eldir, c'est largement atteint.

Métrique observable : `cache_read_tokens` dans le dashboard. Si la part de `cache_read` croît tour après tour, c'est que le caching joue son rôle.

Important : Eldir attache le `system_prompt` **une seule fois au boot** d'une session, pas à chaque `query()`. Régénérer le prompt à chaque tour casserait le cache. Voir le commentaire dans `session_manager.py:173`.

## API

| Endpoint | Effet |
|---|---|
| `GET /api/v1/costs/dashboard` | Snapshot complet (today / 7d / 30d / daily / by_project) |
| `GET /api/v1/costs/sessions/{id}` | Totaux d'une session précise |
| `GET /api/v1/costs/export.csv` | CSV brut de toutes les lignes session_costs de l'utilisateur |

Toutes les agrégations sont scoppées sur `user_id` (mono-user V1 mais multi-user-ready).

## Schéma DB `session_costs`

```sql
session_costs (
  id              uuid PK,
  session_id      uuid FK (sessions, ON DELETE CASCADE),
  project_id      uuid FK (projects, ON DELETE SET NULL),  -- dénormalisé
  user_id         uuid FK (users, ON DELETE SET NULL),     -- dénormalisé
  model           varchar(64),                              -- ex "claude-opus-4-7"
  input_tokens    int,
  output_tokens   int,
  cache_read_tokens   int,
  cache_write_tokens  int,
  cost_usd        numeric(10,6),
  duration_ms     int,
  num_turns       int,
  created_at      timestamptz,
  updated_at      timestamptz
)
```

Index sur `session_id`, `project_id`, `user_id`, `model`, `created_at` pour les agrégations rapides.

## Limites connues / dette V2

- **Pas de tracking live token-par-token** : limitation du SDK (l'usage n'arrive qu'à la fin du tour).
- **Cost en USD uniquement** : pas de conversion devise. Anthropic facture en USD, on garde la vérité comptable.
- **Compaction automatique du contexte** : pas implémentée, remise à V2. Anthropic gère déjà le rolling context côté SDK.
- **Mode plan-only** : remis à V2.
- **Sub-agents Haiku auto-route** : déjà possible manuellement dans le template, l'auto-routing intelligent est V2.

## Voir aussi

- [`sessions.md#types-devents-stream%C3%A9s`](./sessions.md#types-devents-stream%C3%A9s) — l'event `usage`
- [`templates.md`](./templates.md) — choisir le modèle au niveau projet
- [`architecture.md#le-flow-complet-dun-message-utilisateur`](./architecture.md) — où l'`usage` est capturé dans le code
