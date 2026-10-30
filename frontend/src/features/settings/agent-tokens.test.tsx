import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import type * as ClientModule from '@/lib/api/client';

const api = vi.hoisted(() => ({ get: vi.fn(), post: vi.fn(), del: vi.fn() }));

// Le vrai `ApiError` est gardé : le composant le reconnaît avec `instanceof`.
vi.mock('@/lib/api/client', async (importOriginal) => {
  const reel = await importOriginal<typeof ClientModule>();
  return {
    ...reel,
    apiClient: {
      get: (...args: unknown[]) => api.get(...args),
      post: (...args: unknown[]) => api.post(...args),
      delete: (...args: unknown[]) => api.del(...args),
    },
  };
});

import { AgentTokensPanel } from '@/features/settings/agent-tokens';
import { ApiError } from '@/lib/api/client';
import type { AgentTokenRead } from '@/lib/types/api';

const CLAIR = 'clair-de-test-a-ne-jamais-reafficher';

function jeton(surcharge: Partial<AgentTokenRead> = {}): AgentTokenRead {
  return {
    id: 'j1',
    label: 'agent du bureau',
    created_at: new Date(Date.now() - 5 * 86_400_000).toISOString(),
    last_used_at: null,
    revoked_at: null,
    ...surcharge,
  };
}

function renderPanel(): QueryClient {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={qc}>
      <AgentTokensPanel />
    </QueryClientProvider>,
  );
  return qc;
}

/** Laisse les promesses en attente se résoudre : un « jamais appelé » mesuré trop tôt ne prouve rien. */
const laisserPasser = () => act(() => new Promise<void>((fin) => setTimeout(fin, 20)));

async function creerUnJeton(nom = 'agent du bureau'): Promise<void> {
  fireEvent.change(screen.getByLabelText(/nom de l'agent/i), { target: { value: nom } });
  fireEvent.click(screen.getByRole('button', { name: 'Créer un jeton' }));
  await screen.findByText(CLAIR);
}

beforeEach(() => {
  vi.clearAllMocks();
  api.get.mockResolvedValue([]);
  api.post.mockResolvedValue({ ...jeton(), token: CLAIR });
});

afterEach(() => {
  vi.restoreAllMocks();
  Reflect.deleteProperty(navigator, 'clipboard');
});

describe('AgentTokensPanel, création', () => {
  it('dit que le clair ne sera montré qu’une fois AVANT d’en créer un', async () => {
    renderPanel();
    expect(await screen.findByText(/ne sera montré qu'une seule fois/i)).toBeInTheDocument();
    expect(screen.queryByText(CLAIR)).not.toBeInTheDocument();
  });

  it('envoie le nom saisi, sans les blancs autour', async () => {
    renderPanel();
    await creerUnJeton('  agent du bureau  ');
    expect(api.post).toHaveBeenCalledWith('/agent-tokens', { label: 'agent du bureau' });
  });

  it('montre le clair une fois, avec l’avertissement placé avant lui', async () => {
    renderPanel();
    await creerUnJeton();
    const avertissement = screen.getByText(/copie-le maintenant : il ne sera plus affiché/i);
    const clair = screen.getByText(CLAIR);
    expect(
      avertissement.compareDocumentPosition(clair) & Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
    // La liste rafraîchie ne le porte pas : il n'y a qu'un seul endroit où il s'affiche.
    await waitFor(() => expect(api.get).toHaveBeenCalledTimes(2));
    expect(screen.getAllByText(CLAIR)).toHaveLength(1);
  });

  it('ne réaffiche jamais le clair une fois le jeton fermé', async () => {
    renderPanel();
    await creerUnJeton();
    fireEvent.click(screen.getByRole('button', { name: /j'ai copié le jeton/i }));
    expect(screen.queryByText(CLAIR)).not.toBeInTheDocument();
    expect(screen.queryByText(/copie-le maintenant/i)).not.toBeInTheDocument();
  });

  it('ne garde pas le clair dans le cache des mutations', async () => {
    const qc = renderPanel();
    await creerUnJeton();
    await waitFor(() => expect(qc.getMutationCache().getAll()).toHaveLength(0));
  });

  it('refuse d’en créer un second tant que le premier n’est pas fermé', async () => {
    renderPanel();
    await creerUnJeton();
    expect(screen.getByRole('button', { name: 'Créer un jeton' })).toBeDisabled();
    fireEvent.click(screen.getByRole('button', { name: /j'ai copié le jeton/i }));
    expect(screen.getByRole('button', { name: 'Créer un jeton' })).toBeEnabled();
  });

  it('copie le clair dans le presse-papiers', async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, 'clipboard', { value: { writeText }, configurable: true });
    renderPanel();
    await creerUnJeton();
    fireEvent.click(screen.getByRole('button', { name: 'Copier' }));
    await screen.findByText('copié');
    expect(writeText).toHaveBeenCalledWith(CLAIR);
  });

  it('dit qu’il faut copier à la main quand le navigateur refuse', async () => {
    // jsdom n'a pas de presse-papiers : c'est le cas d'Eldir servi en http sur un LAN.
    renderPanel();
    await creerUnJeton();
    fireEvent.click(screen.getByRole('button', { name: 'Copier' }));
    expect(await screen.findByText(/copie impossible ici/i)).toBeInTheDocument();
    expect(screen.getByText(CLAIR)).toBeInTheDocument();
  });

  it('refuse un nom vide sans appeler le serveur', async () => {
    renderPanel();
    fireEvent.change(screen.getByLabelText(/nom de l'agent/i), { target: { value: '   ' } });
    fireEvent.click(screen.getByRole('button', { name: 'Créer un jeton' }));
    expect(await screen.findByText('Donne un nom à cet agent.')).toBeInTheDocument();
    await laisserPasser();
    expect(api.post).not.toHaveBeenCalled();
  });

  it('affiche le message du serveur quand il refuse', async () => {
    api.post.mockRejectedValue(
      new ApiError(422, {
        code: 'validation_error',
        message: "Un jeton d'agent doit porter un libellé de 1 à 80 caractères.",
        details: {},
      }),
    );
    renderPanel();
    fireEvent.change(screen.getByLabelText(/nom de l'agent/i), { target: { value: 'x' } });
    fireEvent.click(screen.getByRole('button', { name: 'Créer un jeton' }));
    expect(await screen.findByText(/libellé de 1 à 80 caractères/)).toBeInTheDocument();
    expect(screen.queryByText(/copie-le maintenant/i)).not.toBeInTheDocument();
  });
});

describe('AgentTokensPanel, liste et révocation', () => {
  it('dit qu’aucun agent ne peut piloter Eldir quand il n’y a aucun jeton', async () => {
    renderPanel();
    expect(await screen.findByText(/aucun agent extérieur ne peut piloter eldir/i)).toBeVisible();
    expect(api.get).toHaveBeenCalledWith('/agent-tokens');
  });

  it('dit pour chaque jeton s’il a servi, quand, ou s’il est coupé', async () => {
    api.get.mockResolvedValue([
      jeton({
        id: 'a',
        label: 'sert encore',
        last_used_at: new Date(Date.now() - 3 * 3_600_000).toISOString(),
      }),
      jeton({ id: 'b', label: 'jamais servi' }),
      jeton({ id: 'c', label: 'agent coupé', revoked_at: new Date().toISOString() }),
    ]);
    renderPanel();
    const sert = (await screen.findByText('sert encore')).closest('li') as HTMLElement;
    expect(within(sert).getByText(/dernier usage il y a 3 h/)).toBeInTheDocument();
    const jamais = screen.getByText('jamais servi').closest('li') as HTMLElement;
    expect(within(jamais).getByText(/jamais utilisé/)).toBeInTheDocument();
    const coupe = screen.getByText('agent coupé').closest('li') as HTMLElement;
    expect(within(coupe).getByText('révoqué')).toBeInTheDocument();
    expect(within(coupe).queryByText('actif')).not.toBeInTheDocument();
    expect(within(sert).getByText('actif')).toBeInTheDocument();
    expect(within(jamais).getByText('actif')).toBeInTheDocument();
  });

  it('ne propose « Révoquer » que sur les jetons encore actifs', async () => {
    api.get.mockResolvedValue([
      jeton({ id: 'a', label: 'agent du bureau' }),
      jeton({ id: 'c', label: 'agent coupé', revoked_at: new Date().toISOString() }),
    ]);
    renderPanel();
    await screen.findByText('agent du bureau');
    expect(
      screen.getByRole('button', { name: 'Révoquer le jeton agent du bureau' }),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole('button', { name: 'Révoquer le jeton agent coupé' }),
    ).not.toBeInTheDocument();
  });

  it('révoque après confirmation, puis relit la liste', async () => {
    vi.spyOn(window, 'confirm').mockReturnValue(true);
    api.get.mockResolvedValueOnce([jeton({ id: 'a', label: 'agent du bureau' })]);
    api.get.mockResolvedValue([
      jeton({ id: 'a', label: 'agent du bureau', revoked_at: new Date().toISOString() }),
    ]);
    api.del.mockResolvedValue(undefined);
    renderPanel();
    fireEvent.click(
      await screen.findByRole('button', { name: 'Révoquer le jeton agent du bureau' }),
    );
    await waitFor(() => expect(api.del).toHaveBeenCalledWith('/agent-tokens/a'));
    await waitFor(() =>
      expect(
        screen.queryByRole('button', { name: 'Révoquer le jeton agent du bureau' }),
      ).not.toBeInTheDocument(),
    );
  });

  it('ne révoque rien si on refuse la confirmation', async () => {
    vi.spyOn(window, 'confirm').mockReturnValue(false);
    api.get.mockResolvedValue([jeton({ id: 'a', label: 'agent du bureau' })]);
    renderPanel();
    fireEvent.click(
      await screen.findByRole('button', { name: 'Révoquer le jeton agent du bureau' }),
    );
    await laisserPasser();
    expect(api.del).not.toHaveBeenCalled();
  });

  it('dit quand la révocation échoue, au lieu de se taire', async () => {
    vi.spyOn(window, 'confirm').mockReturnValue(true);
    api.get.mockResolvedValue([jeton({ id: 'a', label: 'agent du bureau' })]);
    api.del.mockRejectedValue(
      new ApiError(404, { code: 'not_found', message: 'Jeton a introuvable.', details: {} }),
    );
    renderPanel();
    fireEvent.click(
      await screen.findByRole('button', { name: 'Révoquer le jeton agent du bureau' }),
    );
    expect(await screen.findByText('Jeton a introuvable.')).toBeInTheDocument();
  });

  it('garde au « Révoquer » une cible tactile de 44px', async () => {
    api.get.mockResolvedValue([jeton({ id: 'a', label: 'agent du bureau' })]);
    renderPanel();
    // `.eldir-btn` porte `min-h-11` (44px) : une classe locale ne la remplace pas sans le dire.
    expect(
      await screen.findByRole('button', { name: 'Révoquer le jeton agent du bureau' }),
    ).toHaveClass('eldir-btn');
  });
});
