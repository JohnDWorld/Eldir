/**
 * Le déclencheur du menu ne porte qu'un symbole : la pastille.
 *
 * Il en portait deux sur mobile, une icône burger collée à la pastille. Ce
 * test tombe si un glyphe revient à côté d'elle, quel qu'il soit, et pas
 * seulement le burger.
 */

import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it } from 'vitest';

import { ProfileMenu } from '@/components/eldir/profile-menu';

function declencheur(): HTMLElement {
  render(
    <MemoryRouter>
      <ProfileMenu pathname="/" />
    </MemoryRouter>,
  );
  return screen.getByRole('button', { name: 'Menu du compte et navigation' });
}

describe('ProfileMenu', () => {
  it('ne porte que la pastille, jamais un second glyphe', () => {
    const bouton = declencheur();

    expect(bouton).toHaveTextContent('J');
    // Lucide rend ses icônes en <svg> : aucune ne doit cohabiter avec la pastille.
    expect(bouton.querySelector('svg')).toBeNull();
  });

  it('reste une cible tactile de 44px et garde son nom accessible', () => {
    const bouton = declencheur();

    expect(bouton.className).toContain('min-h-11');
    expect(bouton.className).toContain('min-w-11');
  });
});
