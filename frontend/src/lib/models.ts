/**
 * Modèles Claude proposés par Eldir - source unique côté frontend.
 *
 * Trois écrans les listaient chacun de leur côté (nouvelle session, template
 * de projet, génération de template) : une montée de version en oubliait
 * forcément un. Le backend a sa propre liste dans
 * `app/core/constants.py`, elles doivent rester alignées.
 *
 * Les identifiants ne portent jamais de suffixe de date.
 */

export interface ClaudeModelOption {
  value: string;
  /** Libellé court, pour un menu déroulant. */
  label: string;
  /** Une ligne d'aide, pour les écrans qui ont la place. */
  hint: string;
}

export const CLAUDE_MODELS: readonly ClaudeModelOption[] = [
  {
    value: 'claude-opus-5',
    label: 'Opus 5 (raisonnement long)',
    hint: 'Le plus capable. Pour les refactos et les tâches à forte incertitude.',
  },
  {
    value: 'claude-sonnet-5',
    label: 'Sonnet 5 (équilibré)',
    hint: 'Le bon défaut : rapide, solide sur le code du quotidien.',
  },
  {
    value: 'claude-haiku-4-5',
    label: 'Haiku 4.5 (économe)',
    hint: "Le moins cher. Pour l'analyse, la classification, les tâches cadrées.",
  },
];

/** Modèle du "mode économe" et des tâches internes d'Eldir. */
export const ECO_MODEL = 'claude-haiku-4-5';

/** Défaut serveur (cf. CLAUDE_DEFAULT_MODEL). */
export const DEFAULT_MODEL = 'claude-sonnet-5';
