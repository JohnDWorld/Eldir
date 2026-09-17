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

export const PROVIDERS = ['github', 'forgejo'] as const;
export type Provider = (typeof PROVIDERS)[number];
