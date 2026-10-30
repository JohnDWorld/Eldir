import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { act, fireEvent, render, screen, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import type * as ClientModule from '@/lib/api/client';

const api = vi.hoisted(() => ({ get: vi.fn(), post: vi.fn() }));

// Le vrai `ApiError` est gardé : le composant le reconnaît avec `instanceof`.
vi.mock('@/lib/api/client', async (importOriginal) => {
  const reel = await importOriginal<typeof ClientModule>();
  return {
    ...reel,
    apiClient: {
      get: (...args: unknown[]) => api.get(...args),
      post: (...args: unknown[]) => api.post(...args),
    },
  };
});

import { AgentMemoryPanel, AgentMemoryStatus } from '@/features/settings/agent-memory';
import { ApiError } from '@/lib/api/client';
import { queryKeys } from '@/lib/api/queries';
import type { AgentMemoryEntry, AgentMemoryRead } from '@/lib/types/api';

function entree(agent: string, text: string): AgentMemoryEntry {
  return { agent, text, line: `- [agent « ${agent} »] ${text}` };
}

function memoire(entries: AgentMemoryEntry[], max_entries = 5, max_length = 300): AgentMemoryRead {
  return { entries, max_entries, max_length };
}

const laisserPasser = () => act(() => new Promise<void>((fin) => setTimeout(fin, 20)));

function renderAvec(ui: JSX.Element): QueryClient {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={qc}>
      <MemoryRouter>{ui}</MemoryRouter>
    </QueryClientProvider>,
  );
  return qc;
}

beforeEach(() => {
  vi.clearAllMocks();
  api.get.mockResolvedValue(memoire([]));
});

describe('AgentMemoryPanel', () => {
  it('dit où en est la mémoire, avec les bornes que le serveur donne', async () => {
    api.get.mockResolvedValue(memoire([entree('A', 'Fait A.'), entree('B', 'Fait B.')], 5, 250));
    renderAvec(<AgentMemoryPanel />);
    expect(await screen.findByText(/2 sur 5 préférences/)).toBeInTheDocument();
    expect(api.get).toHaveBeenCalledWith('/supervisor/agent-memory');
    const jauge = screen.getByRole('meter');
    expect(jauge).toHaveAttribute('aria-valuenow', '2');
    expect(jauge).toHaveAttribute('aria-valuemax', '5');
    // Le plafond de longueur vient aussi du serveur.
    expect(screen.getByText(/5 lignes de 250 caractères au plus/)).toBeInTheDocument();
  });

  it('explique que ces lignes ne sont pas de John et ne valent pas sa parole', async () => {
    api.get.mockResolvedValue(memoire([entree('A', 'Fait A.')]));
    renderAvec(<AgentMemoryPanel />);
    const texte = (await screen.findByText(/ces lignes ne sont pas de toi/i)).textContent ?? '';
    expect(texte).toMatch(/suggestions/);
    expect(texte).toMatch(/jamais une demande de ta part/);
    expect(texte).toMatch(/autorisation de publier/);
  });

  it('montre qui a écrit chaque ligne', async () => {
    api.get.mockResolvedValue(
      memoire([entree('assistant de bureau', 'Toujours une PR.'), entree('script', 'Un commit.')]),
    );
    renderAvec(<AgentMemoryPanel />);
    const premiere = (await screen.findByText('Toujours une PR.')).closest('li') as HTMLElement;
    expect(within(premiere).getByText(/agent « assistant de bureau »/)).toBeInTheDocument();
    expect(screen.getByText('Un commit.')).toBeInTheDocument();
  });

  it('dit que la mémoire est pleine, et que seul l’agent lit le refus', async () => {
    api.get.mockResolvedValue(memoire([entree('A', 'a'), entree('B', 'b')], 2));
    renderAvec(<AgentMemoryPanel />);
    expect(await screen.findByText(/mémoire pleine/)).toBeInTheDocument();
    expect(screen.getByText(/seul l'agent lit ce refus/)).toBeInTheDocument();
  });

  it('ne dit pas « pleine » une place avant la borne', async () => {
    api.get.mockResolvedValue(memoire([entree('A', 'a')], 2));
    renderAvec(<AgentMemoryPanel />);
    await screen.findByText(/1 sur 2 préférences/);
    expect(screen.queryByText(/mémoire pleine/)).not.toBeInTheDocument();
    expect(screen.queryByText(/seul l'agent lit ce refus/)).not.toBeInTheDocument();
  });

  it('dit qu’aucun agent n’a rien enregistré', async () => {
    renderAvec(<AgentMemoryPanel />);
    expect(await screen.findByText(/aucun agent n'a enregistré de préférence/i)).toBeVisible();
  });

  it('retire la ligne désignée, montre ce qui reste et invalide le prompt édité à côté', async () => {
    const a = entree('A', 'Fait A.');
    const b = entree('B', 'Fait B.');
    api.get.mockResolvedValue(memoire([a, b]));
    api.post.mockResolvedValue(memoire([b]));
    const qc = renderAvec(<AgentMemoryPanel />);
    qc.setQueryData(queryKeys.systemPrompts, []);

    fireEvent.click(await screen.findByRole('button', { name: /retirer.*agent A/i }));

    expect(await screen.findByText(/1 sur 5 préférences/)).toBeInTheDocument();
    expect(api.post).toHaveBeenCalledWith('/supervisor/agent-memory/forget', { line: a.line });
    expect(screen.queryByText('Fait A.')).not.toBeInTheDocument();
    // Sans cela l'éditeur garderait la ligne retirée, et « sauvegarder » la remettrait.
    expect(qc.getQueryState(queryKeys.systemPrompts)?.isInvalidated).toBe(true);
  });

  it('dit pourquoi une ligne ne part pas, et relit ce qui reste', async () => {
    api.get.mockResolvedValue(memoire([entree('A', 'Fait A.')]));
    api.post.mockRejectedValue(
      new ApiError(404, {
        code: 'not_found',
        message: "Cette préférence n'existe plus.",
        details: {},
      }),
    );
    renderAvec(<AgentMemoryPanel />);
    fireEvent.click(await screen.findByRole('button', { name: /retirer.*agent A/i }));
    expect(await screen.findByText("Cette préférence n'existe plus.")).toBeInTheDocument();
    await laisserPasser();
    expect(api.get).toHaveBeenCalledTimes(2);
  });

  it('refuse de retirer une ligne tant que le prompt à côté a des modifications non sauvegardées', async () => {
    api.get.mockResolvedValue(memoire([entree('A', 'Fait A.')]));
    renderAvec(<AgentMemoryPanel verrouille />);
    const bouton = await screen.findByRole('button', { name: /retirer.*agent A/i });
    expect(bouton).toBeDisabled();
    expect(screen.getByText(/modifications non sauvegardées/)).toBeInTheDocument();
    fireEvent.click(bouton);
    await laisserPasser();
    expect(api.post).not.toHaveBeenCalled();
  });

  it('garde au « Retirer » une cible tactile de 44px', async () => {
    api.get.mockResolvedValue(memoire([entree('A', 'Fait A.')]));
    renderAvec(<AgentMemoryPanel />);
    // `.eldir-btn` porte `min-h-11` (44px).
    expect(await screen.findByRole('button', { name: /retirer.*agent A/i })).toHaveClass(
      'eldir-btn',
    );
  });
});

describe('AgentMemoryPanel, vers les jetons', () => {
  it('renvoie vers les jetons quand des agents ont écrit, pour couper celui qui en occupe trop', async () => {
    api.get.mockResolvedValue(memoire([entree('A', 'Fait A.')]));
    renderAvec(<AgentMemoryPanel />);
    const lien = await screen.findByRole('link', { name: /voir les jetons/i });
    expect(lien).toHaveAttribute('href', '/settings/agents');
    // `.eldir-btn` porte `min-h-11` (44px).
    expect(lien).toHaveClass('eldir-btn');
  });

  it('verrouille « Voir les jetons » comme « Retirer » tant que le brouillon du prompt n’est pas sauvegardé', async () => {
    api.get.mockResolvedValue(memoire([entree('A', 'Fait A.')]));
    renderAvec(<AgentMemoryPanel verrouille />);
    // Quitter la page perdrait le brouillon : plus de lien, un bouton inerte à sa place.
    const bouton = await screen.findByRole('button', { name: /voir les jetons/i });
    expect(bouton).toBeDisabled();
    expect(screen.queryByRole('link', { name: /voir les jetons/i })).not.toBeInTheDocument();
    expect(screen.getByText(/quitter cette page/)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /retirer.*agent A/i })).toBeDisabled();
  });

  it('ne propose pas de couper un jeton quand aucun agent n’a rien écrit', async () => {
    renderAvec(<AgentMemoryPanel />);
    await screen.findByText(/aucun agent n'a enregistré de préférence/i);
    expect(screen.queryByRole('link', { name: /voir les jetons/i })).not.toBeInTheDocument();
  });
});

const QUATRE = ['A', 'B', 'C', 'D'].map((agent) => entree(agent, `Fait ${agent}.`));

describe('AgentMemoryPanel, liste repliée', () => {
  it('replie la liste au-delà de quelques lignes, et garde le sens au-dessus', async () => {
    api.get.mockResolvedValue(memoire(QUATRE, 4));
    renderAvec(<AgentMemoryPanel />);
    const details = (await screen.findByText(/les 4 lignes des agents/i)).closest('details');
    expect(details).not.toBeNull();
    expect(details).not.toHaveAttribute('open');
    // Ce qui porte le sens reste visible, hors du repli : le compte, la jauge,
    // l'explication et le bandeau de mémoire pleine.
    for (const sens of [
      screen.getByText(/4 sur 4 préférences/),
      screen.getByRole('meter'),
      screen.getByText(/ces lignes ne sont pas de toi/i),
      screen.getByText(/seul l'agent lit ce refus/),
    ]) {
      expect(details).not.toContainElement(sens);
    }
    // La liste, elle, est dans le repli.
    expect(details).toContainElement(screen.getByText('Fait A.'));
  });

  it('ne replie pas une liste courte', async () => {
    api.get.mockResolvedValue(memoire(QUATRE.slice(0, 3), 20));
    renderAvec(<AgentMemoryPanel />);
    await screen.findByText('Fait A.');
    expect(document.querySelector('details')).toBeNull();
  });

  it('retire une ligne une fois la liste dépliée, et le message d’erreur est dans la liste', async () => {
    api.get.mockResolvedValue(memoire(QUATRE, 20));
    api.post.mockRejectedValue(
      new ApiError(404, {
        code: 'not_found',
        message: "Cette préférence n'existe plus.",
        details: {},
      }),
    );
    renderAvec(<AgentMemoryPanel />);
    const details = (await screen.findByText(/les 4 lignes des agents/i)).closest(
      'details',
    ) as HTMLDetailsElement;
    details.open = true;
    fireEvent.click(screen.getByRole('button', { name: /retirer.*agent B/i }));
    const erreur = await screen.findByText("Cette préférence n'existe plus.");
    // À côté des lignes, pas au-dessus d'une liste que John a fait défiler.
    expect(details).toContainElement(erreur);
    expect(api.post).toHaveBeenCalledWith('/supervisor/agent-memory/forget', {
      line: QUATRE[1]!.line,
    });
  });

  it('dit pourquoi tout est verrouillé, même liste repliée', async () => {
    api.get.mockResolvedValue(memoire(QUATRE, 20));
    renderAvec(<AgentMemoryPanel verrouille />);
    const details = (await screen.findByText(/les 4 lignes des agents/i)).closest('details');
    const rappel = screen.getByText(/modifications non sauvegardées/);
    // Visible hors du repli : fermée, la liste ne dirait pas pourquoi « Retirer » est inerte.
    expect(details).not.toContainElement(rappel);
    expect(rappel.textContent).toMatch(/quitter cette page/);
  });

  it('garde au repli une cible tactile de 44px', async () => {
    api.get.mockResolvedValue(memoire(QUATRE, 20));
    renderAvec(<AgentMemoryPanel />);
    // `min-h-11` = 44px : le repli est un bouton de plus à toucher, pas un lien de texte.
    expect(await screen.findByText(/les 4 lignes des agents/i)).toHaveClass('min-h-11');
  });
});

/** Ce que la jauge MONTRE (largeur et couleur du remplissage), pas seulement ce qu'elle annonce. */
function remplissage(): HTMLElement {
  return screen.getByRole('meter').firstElementChild as HTMLElement;
}

function lignes(n: number): AgentMemoryEntry[] {
  return Array.from({ length: n }, (_, i) => entree('A', `Fait ${i}.`));
}

describe('AgentMemoryPanel, jauge', () => {
  it.each([
    // [lignes, borne, largeur, couleur] : la couleur change à 80 % puis à la borne.
    [0, 20, '0%', 'bg-eldir-orange'],
    [1, 5, '20%', 'bg-eldir-orange'],
    [15, 20, '75%', 'bg-eldir-orange'],
    [16, 20, '80%', 'bg-eldir-amber'],
    [19, 20, '95%', 'bg-eldir-amber'],
    [20, 20, '100%', 'bg-eldir-red'],
    // John peut écrire plus de lignes à la main que la borne n'en laisse aux agents :
    // le remplissage ne déborde pas de la jauge.
    [25, 20, '100%', 'bg-eldir-red'],
  ])('avec %i lignes sur %i, remplit %s en %s', async (n, borne, largeur, couleur) => {
    api.get.mockResolvedValue(memoire(lignes(n), borne));
    renderAvec(<AgentMemoryPanel />);
    await screen.findByRole('meter');
    expect(remplissage().style.width).toBe(largeur);
    expect(remplissage()).toHaveClass(couleur);
    // Une seule couleur à la fois : un remplissage qui les cumulerait mentirait.
    for (const autre of ['bg-eldir-orange', 'bg-eldir-amber', 'bg-eldir-red'].filter(
      (c) => c !== couleur,
    )) {
      expect(remplissage()).not.toHaveClass(autre);
    }
  });
});

describe('AgentMemoryStatus', () => {
  it('dit le compte et renvoie vers le prompt des préférences', async () => {
    api.get.mockResolvedValue(memoire([entree('A', 'a'), entree('B', 'b')], 5));
    renderAvec(<AgentMemoryStatus />);
    expect(await screen.findByText(/2 sur 5 préférences enregistrées/)).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /voir et nettoyer/i })).toHaveAttribute(
      'href',
      '/settings/prompts?prompt=supervisor_prefs',
    );
    expect(screen.queryByText(/pleine/i)).not.toBeInTheDocument();
  });

  it('dit « pleine » à la borne', async () => {
    api.get.mockResolvedValue(memoire([entree('A', 'a')], 1));
    renderAvec(<AgentMemoryStatus />);
    expect(await screen.findByText(/pleine : les nouvelles sont refusées/i)).toBeInTheDocument();
  });

  it('dit qu’il ne peut pas lire la mémoire, au lieu de disparaître', async () => {
    api.get.mockRejectedValue(
      new ApiError(500, { code: 'eldir_error', message: 'boom', details: {} }),
    );
    renderAvec(<AgentMemoryStatus />);
    const message = await screen.findByText(/impossible de lire la mémoire des agents/i);
    // Ce que ça coûte de ne pas savoir : l'agent est refusé et lui seul le lit.
    expect(message.textContent).toMatch(/seul l'agent le sait/);
  });

  it('permet de réessayer quand la lecture échoue', async () => {
    api.get.mockRejectedValueOnce(
      new ApiError(500, { code: 'eldir_error', message: 'boom', details: {} }),
    );
    api.get.mockResolvedValue(memoire([entree('A', 'a'), entree('B', 'b')], 5));
    renderAvec(<AgentMemoryStatus />);
    fireEvent.click(await screen.findByRole('button', { name: /réessayer/i }));
    expect(await screen.findByText(/2 sur 5 préférences enregistrées/)).toBeInTheDocument();
    expect(screen.queryByText(/impossible de lire/i)).not.toBeInTheDocument();
  });

  it('ne montre rien le temps du premier chargement', () => {
    api.get.mockReturnValue(new Promise(() => undefined));
    renderAvec(<AgentMemoryStatus />);
    expect(screen.queryByText(/mémoire des agents/i)).not.toBeInTheDocument();
  });
});
