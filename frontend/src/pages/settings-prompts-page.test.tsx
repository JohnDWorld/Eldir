import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import type * as ClientModule from '@/lib/api/client';

const api = vi.hoisted(() => ({ get: vi.fn(), put: vi.fn(), post: vi.fn() }));

vi.mock('@/lib/api/client', async (importOriginal) => {
  const reel = await importOriginal<typeof ClientModule>();
  return {
    ...reel,
    apiClient: {
      get: (...args: unknown[]) => api.get(...args),
      put: (...args: unknown[]) => api.put(...args),
      post: (...args: unknown[]) => api.post(...args),
    },
  };
});

import { SettingsPromptsPage } from '@/pages/settings-prompts-page';
import type { SystemPromptRead } from '@/lib/types/api';

const LIGNE = '- [agent « A »] Fait A.';

function prompt(slug: string, content: string): SystemPromptRead {
  return {
    slug,
    title: `Titre ${slug}`,
    description: '',
    content,
    is_overridden: true,
    default_content: '',
  };
}

const PROMPTS = [prompt('supervisor', '# Superviseur'), prompt('supervisor_prefs', LIGNE)];
const MEMOIRE = {
  entries: [{ agent: 'A', text: 'Fait A.', line: LIGNE }],
  max_entries: 20,
  max_length: 300,
};

function renderPage(url: string): void {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={[url]}>
        <SettingsPromptsPage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

const laisserPasser = () => act(() => new Promise<void>((fin) => setTimeout(fin, 20)));

beforeEach(() => {
  vi.clearAllMocks();
  api.get.mockImplementation((chemin: string) =>
    Promise.resolve(chemin === '/supervisor/agent-memory' ? MEMOIRE : PROMPTS),
  );
});

describe('SettingsPromptsPage, mémoire des agents', () => {
  it('ouvre le prompt des préférences quand le lien le demande, avec la mémoire des agents', async () => {
    renderPage('/settings/prompts?prompt=supervisor_prefs');
    expect(await screen.findByText(/1 sur 20 préférences/)).toBeInTheDocument();
    expect(screen.getByText('Fait A.')).toBeInTheDocument();
  });

  it('ne montre la mémoire des agents que sur le prompt des préférences', async () => {
    renderPage('/settings/prompts');
    // Le premier prompt est ouvert par défaut : ce n'est pas celui des préférences.
    await screen.findByDisplayValue('# Superviseur');
    await laisserPasser();
    expect(screen.queryByText(/mémoire des agents extérieurs/i)).not.toBeInTheDocument();
    expect(api.get).not.toHaveBeenCalledWith('/supervisor/agent-memory');

    fireEvent.click(screen.getByRole('button', { name: /titre supervisor_prefs/i }));
    expect(await screen.findByText(/1 sur 20 préférences/)).toBeInTheDocument();
  });

  it('retombe sur le premier prompt quand le lien en nomme un qui n’existe pas', async () => {
    renderPage('/settings/prompts?prompt=inconnu');
    expect(await screen.findByDisplayValue('# Superviseur')).toBeInTheDocument();
  });

  it('bloque le ménage tant que le prompt a des modifications non sauvegardées', async () => {
    renderPage('/settings/prompts?prompt=supervisor_prefs');
    const bouton = await screen.findByRole('button', { name: /retirer.*agent A/i });
    expect(bouton).toBeEnabled();
    // Avant toute modification : un vrai lien vers les jetons.
    expect(screen.getByRole('link', { name: /voir les jetons/i })).toHaveAttribute(
      'href',
      '/settings/agents',
    );
    fireEvent.change(screen.getByDisplayValue(LIGNE), { target: { value: `${LIGNE}\n- Autre.` } });
    expect(screen.getByRole('button', { name: /retirer.*agent A/i })).toBeDisabled();
    // Le brouillon se perdrait aussi en quittant la page : même verrou pour le lien.
    expect(screen.getByRole('button', { name: /voir les jetons/i })).toBeDisabled();
    expect(screen.queryByRole('link', { name: /voir les jetons/i })).not.toBeInTheDocument();
  });

  it('relit la mémoire des agents quand John restaure le défaut du prompt', async () => {
    vi.spyOn(window, 'confirm').mockReturnValue(true);
    api.post.mockResolvedValue({ ...prompt('supervisor_prefs', ''), is_overridden: false });
    renderPage('/settings/prompts?prompt=supervisor_prefs');
    await screen.findByText(/1 sur 20 préférences/);
    fireEvent.click(screen.getByRole('button', { name: 'restaurer le défaut' }));
    await waitFor(() =>
      expect(
        api.get.mock.calls.filter(([chemin]) => chemin === '/supervisor/agent-memory'),
      ).toHaveLength(2),
    );
  });

  it('envoie le texte chargé avec la sauvegarde, et dit à John si le prompt a bougé', async () => {
    const { ApiError } = await import('@/lib/api/client');
    api.put.mockRejectedValue(
      new ApiError(409, {
        code: 'conflict',
        message: "Ce prompt a changé depuis que tu l'as ouvert.",
        details: {},
      }),
    );
    renderPage('/settings/prompts?prompt=supervisor_prefs');
    await screen.findByText(/1 sur 20 préférences/);
    fireEvent.change(screen.getByDisplayValue(LIGNE), { target: { value: '- Autre.' } });
    fireEvent.click(screen.getByRole('button', { name: 'sauvegarder' }));

    // Le texte chargé part avec l'écriture : c'est ce qui la rend conditionnelle.
    await waitFor(() =>
      expect(api.put).toHaveBeenCalledWith('/system-prompts/supervisor_prefs', {
        content: '- Autre.',
        base_content: LIGNE,
      }),
    );
    // Et le motif du refus est affiché, pas remplacé par une erreur générique.
    expect(await screen.findByText(/a changé depuis que tu l'as ouvert/)).toBeInTheDocument();
  });

  it('relit la mémoire des agents quand John édite le prompt à la main', async () => {
    api.put.mockResolvedValue(prompt('supervisor_prefs', '- Autre.'));
    renderPage('/settings/prompts?prompt=supervisor_prefs');
    await screen.findByText(/1 sur 20 préférences/);
    fireEvent.change(screen.getByDisplayValue(LIGNE), { target: { value: '- Autre.' } });
    fireEvent.click(screen.getByRole('button', { name: 'sauvegarder' }));
    await waitFor(() =>
      expect(
        api.get.mock.calls.filter(([chemin]) => chemin === '/supervisor/agent-memory'),
      ).toHaveLength(2),
    );
  });
});
