/**
 * Constantes globales du frontend.
 * Aucune valeur hardcodée ailleurs (cf. AGENTS.md).
 */

export const API_BASE_URL = '/api/v1';
export const WS_BASE_URL = '/ws';

export const APP_NAME = 'Eldir';
export const APP_TAGLINE = 'Mission Control';

/**
 * États possibles d'une session - miroir de backend/app/core/constants.py.
 * Voir DA/d1.jsx · STATES pour les couleurs associées.
 */
export const SESSION_STATES = [
  'idle',
  'thinking',
  'tool_use',
  'waiting_input',
  'blocked',
] as const;

export type SessionState = (typeof SESSION_STATES)[number];

export const SESSION_STATE_LABEL: Record<SessionState, string> = {
  idle: 'au repos',
  thinking: 'réfléchit',
  tool_use: 'outil',
  waiting_input: 'attend',
  blocked: 'bloquée',
};

/**
 * Slug du prompt où le superviseur range ses préférences durables, celles de John
 * et celles des agents extérieurs. Miroir de `SUPERVISOR_PREFS_SLUG` dans
 * backend/app/services/supervisor_service.py.
 */
export const SUPERVISOR_PREFS_SLUG = 'supervisor_prefs';

/**
 * Qui a écrit un `user_message` (champ `origin` de l'event). Miroir de
 * `MESSAGE_ORIGIN_*` dans backend/app/core/constants.py. Un agent extérieur y est
 * `agent:<libellé de son jeton>` : c'est ce qui dit, en relisant une session, lequel
 * des deux Eldir a donné la consigne.
 */
export const MESSAGE_ORIGIN_USER = 'user';
export const MESSAGE_ORIGIN_ELDIR = 'eldir';
export const MESSAGE_ORIGIN_AGENT_PREFIX = 'agent:';

export const PROVIDERS = ['github', 'forgejo'] as const;
export type Provider = (typeof PROVIDERS)[number];
