/**
 * Mocks Phase 0 — copies fidèles des données DA/shared.jsx pour permettre
 * de monter la D1 Mission Control sans backend live. À supprimer une fois
 * que les hooks `useProjects` / `useSessions` retournent des données réelles.
 */

import type { SessionCardData } from '@/components/eldir/session-card';
import type { EventEntry } from '@/components/eldir/event-row';
import type { LogLine } from '@/components/eldir/logs-panel';
import type { Provider, SessionState } from '@/lib/constants';

export interface MockProject {
  id: string;
  name: string;
  provider: Provider;
  branch: string;
  sessions: number;
  last: string;
  primaryState: SessionState;
}

export const MOCK_PROJECTS: readonly MockProject[] = [
  {
    id: 'eldir',
    name: 'eldir',
    provider: 'forgejo',
    branch: 'feat/sessions',
    sessions: 2,
    last: '2m ago',
    primaryState: 'thinking',
  },
  {
    id: 'lumen',
    name: 'lumen-web',
    provider: 'github',
    branch: 'main',
    sessions: 1,
    last: '14m ago',
    primaryState: 'waiting_input',
  },
  {
    id: 'atelier',
    name: 'atelier-api',
    provider: 'forgejo',
    branch: 'fix/auth-token',
    sessions: 1,
    last: '1h ago',
    primaryState: 'idle',
  },
  {
    id: 'kiln',
    name: 'kiln-cli',
    provider: 'github',
    branch: 'release/0.4',
    sessions: 0,
    last: '3h ago',
    primaryState: 'idle',
  },
  {
    id: 'mire',
    name: 'mire-notebook',
    provider: 'github',
    branch: 'main',
    sessions: 0,
    last: '2d ago',
    primaryState: 'idle',
  },
];

export const MOCK_SESSIONS: readonly SessionCardData[] = [
  {
    id: 's1',
    projectSlug: 'eldir',
    state: 'thinking',
    summary: 'Refactor session router for SSE reconnect',
    duration: '14:22',
    tokens: '64k',
    cost: '$0.21',
  },
  {
    id: 's2',
    projectSlug: 'eldir',
    state: 'tool_use',
    summary: 'Run pnpm test --filter=core',
    duration: '02:11',
    tokens: '12k',
    cost: '$0.04',
  },
  {
    id: 's3',
    projectSlug: 'lumen',
    state: 'waiting_input',
    summary: 'Tailwind purge — confirm safelist?',
    duration: '08:45',
    tokens: '67k',
    cost: '$0.21',
  },
  {
    id: 's4',
    projectSlug: 'atelier',
    state: 'idle',
    summary: 'Auth token rotation — done.',
    duration: '32:09',
    tokens: '212k',
    cost: '$0.74',
  },
];

export const MOCK_LOG_LINES: readonly LogLine[] = [
  {
    id: 'log-1',
    prefix: { tone: 'orange', text: 's1' },
    kind: { tone: 'gray', text: 'tool_use' },
    message: 'read_file src/server/sessions/router.ts',
    messageTone: 'gray',
  },
  {
    id: 'log-2',
    prefix: { tone: 'gold', text: 's2' },
    kind: { tone: 'gray', text: 'tool_use' },
    message: 'run_bash pnpm test --filter=core',
    messageTone: 'gray',
  },
  {
    id: 'log-3',
    prefix: { tone: 'amber', text: 's3' },
    kind: { tone: 'gray', text: 'awaiting_input' },
    message: '// safelist confirmation',
    messageTone: 'gray',
  },
  {
    id: 'log-4',
    prefix: { tone: 'orange', text: 's1' },
    kind: { tone: 'gray', text: 'claude' },
    message: '"switching to per-session ring buffer"',
    messageTone: 'cream',
  },
  {
    id: 'log-5',
    prefix: { tone: 'orange', text: 's1' },
    kind: { tone: 'gray', text: 'tool_use' },
    message: 'edit_file +18 −7',
    messageTone: 'gray',
  },
];

export const MOCK_EVENTS: readonly EventEntry[] = [
  { time: '09:41', source: 's1', message: 'edit_file router.ts' },
  { time: '09:39', source: 's3', message: 'awaiting input' },
  { time: '09:36', source: 's2', message: 'test passed' },
  { time: '09:33', source: 's4', message: 'session ended' },
  { time: '09:18', source: '—', message: 'forgejo webhook · push' },
  { time: '09:02', source: 's1', message: 'session started' },
];

export const MOCK_SPEND_7D: readonly number[] = [2, 4, 3, 7, 5, 8, 6, 11];
export const MOCK_TOKENS_TODAY: readonly number[] = [3, 5, 4, 7, 6, 8, 5, 9, 7, 11, 9, 12, 10, 13];
