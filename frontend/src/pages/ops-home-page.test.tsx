import { render, screen, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import type { SessionRead } from '@/lib/types/api';

const donnees = vi.hoisted(() => ({
  sessions: [] as SessionRead[],
}));

vi.mock('@/lib/api/queries', () => ({
  useProjects: () => ({
    data: [
      { id: 'p-chaud', name: 'Projet chaud', provider: 'github', default_branch: 'main' },
      { id: 'p-froid', name: 'Projet froid', provider: 'github', default_branch: 'main' },
    ],
    isPending: false,
  }),
  useSessions: () => ({ data: donnees.sessions, isPending: false }),
  useCostsDashboard: () => ({ data: undefined }),
  useDeleteSession: () => ({ mutate: vi.fn(), isPending: false }),
}));

import { OpsHomePage } from '@/pages/ops-home-page';

const MINUTE = 60_000;
const JOUR = 24 * 60 * MINUTE;

/** Une session ouverte il y a `ouverteJours` jours, dont la dernière activité date de `activeMinutes`. */
function session(
  id: string,
  surcharge: Partial<SessionRead> & { ouverteJours: number; activeMinutes: number },
): SessionRead {
  const { ouverteJours, activeMinutes, ...reste } = surcharge;
  return {
    id,
    project_id: 'p-chaud',
    user_id: 'u',
    sdk_session_id: null,
    branch: 'claude/x',
    worktree_path: null,
    state: 'idle',
    summary: null,
    model: null,
    is_system: false,
    system_kind: null,
    publish_allowed: false,
    created_at: new Date(Date.now() - ouverteJours * JOUR).toISOString(),
    updated_at: new Date(Date.now() - activeMinutes * MINUTE).toISOString(),
    ...reste,
  };
}

function renderPage(): void {
  render(
    <MemoryRouter>
      <OpsHomePage />
    </MemoryRouter>,
  );
}

beforeEach(() => {
  donnees.sessions = [];
});

describe('OpsHomePage, âge des sessions', () => {
  it('lit la dernière activité, pas l’ouverture : une session chaude ne paraît pas abandonnée', () => {
    donnees.sessions = [session('chaude-0001', { ouverteJours: 5, activeMinutes: 10 })];
    renderPage();
    expect(screen.getByText('il y a 10 min')).toBeInTheDocument();
    expect(screen.queryByText('il y a 5 j')).not.toBeInTheDocument();
  });

  it('dit « il y a 5 j » d’une session qu’on n’a pas touchée depuis cinq jours', () => {
    donnees.sessions = [session('froide-0001', { ouverteJours: 9, activeMinutes: 5 * 24 * 60 })];
    renderPage();
    expect(screen.getByText('il y a 5 j')).toBeInTheDocument();
  });

  it('range à égalité d’urgence la session la plus récemment travaillée en premier', () => {
    donnees.sessions = [
      // Ouverte récemment mais laissée de côté.
      session('froide-0001', { project_id: 'p-froid', ouverteJours: 1, activeMinutes: 24 * 60 }),
      // Ouverte il y a longtemps mais travaillée à l'instant.
      session('chaude-0001', { project_id: 'p-chaud', ouverteJours: 9, activeMinutes: 2 }),
    ];
    renderPage();
    const [premiere, seconde] = screen.getAllByRole('button', { name: /projet (chaud|froid)/i });
    expect(within(premiere!).getByText('Projet chaud')).toBeInTheDocument();
    expect(within(seconde!).getByText('Projet froid')).toBeInTheDocument();
  });

  it('lit aussi la dernière activité dans la liste des tâches internes', () => {
    donnees.sessions = [
      session('superv-0001', {
        project_id: null,
        is_system: true,
        system_kind: 'supervisor',
        ouverteJours: 5,
        activeMinutes: 10,
      }),
    ];
    renderPage();
    const ligne = screen.getByText('Eldir · superviseur').closest('a') as HTMLElement;
    expect(within(ligne).getByText('il y a 10 min')).toBeInTheDocument();
  });

  it('dit sur la carte de quoi l’âge est l’âge', () => {
    donnees.sessions = [session('chaude-0001', { ouverteJours: 5, activeMinutes: 10 })];
    renderPage();
    expect(screen.getByTitle('Dernière activité')).toHaveTextContent('il y a 10 min');
  });
});
