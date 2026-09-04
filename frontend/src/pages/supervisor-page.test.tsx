import { render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { describe, expect, it, vi } from 'vitest';

const mutateAsync = vi.fn();

vi.mock('@/lib/api/queries', () => ({
  useEnsureSupervisor: () => ({ mutateAsync }),
}));

import { SupervisorPage } from '@/pages/supervisor-page';

function renderPage(): void {
  render(
    <MemoryRouter initialEntries={['/supervisor']}>
      <Routes>
        <Route path="/supervisor" element={<SupervisorPage />} />
        <Route path="/sessions/:sessionId" element={<div>chat superviseur</div>} />
      </Routes>
    </MemoryRouter>,
  );
}

describe('SupervisorPage', () => {
  it('redirige vers le chat de la session superviseur', async () => {
    mutateAsync.mockResolvedValueOnce({ id: 'sup-1' });
    renderPage();
    expect(await screen.findByText('chat superviseur')).toBeInTheDocument();
  });

  it('affiche l’erreur si Eldir ne peut pas démarrer', async () => {
    mutateAsync.mockRejectedValueOnce(new Error('Aucun credential Claude'));
    renderPage();
    expect(await screen.findByText('Aucun credential Claude')).toBeInTheDocument();
  });
});
