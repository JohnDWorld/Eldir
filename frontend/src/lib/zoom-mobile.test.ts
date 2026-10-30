/**
 * Deux invariants sur le zoom mobile, que seul le source peut dire : jsdom ne
 * calcule pas de mise en page et ne charge pas Tailwind.
 *
 * WebKit zoome la page quand un champ sous 16px prend le focus, et ne dézoome
 * jamais. Il y a deux façons de l'éviter, une bonne et une qui casse l'app
 * pour qui a besoin de zoomer. Ce fichier garde la bonne en place et interdit
 * l'autre.
 */

import { readFileSync } from 'node:fs';

import { describe, expect, it } from 'vitest';

function lire(chemin: string): string {
  return readFileSync(new URL(chemin, import.meta.url), 'utf8');
}

describe('zoom mobile', () => {
  it('pose un plancher de 16px sur les champs, sous le point de rupture tactile', () => {
    const css = lire('../styles/globals.css');
    const bloc = /@media[^{]*max-width:\s*767px[^{]*\{([\s\S]*?)\n\}/.exec(css);

    expect(bloc, 'aucune règle mobile dans globals.css').not.toBeNull();
    const regle = bloc![1];
    expect(regle).toMatch(/font-size:\s*16px\s*!important/);
    for (const champ of ['input', 'textarea', 'select']) {
      expect(regle, `${champ} hors du plancher`).toContain(champ);
    }
  });

  it("n'achète jamais ce confort en interdisant le zoom", () => {
    const html = lire('../../index.html');
    const viewport = /<meta name="viewport"[^>]*>/.exec(html)?.[0] ?? '';

    expect(viewport, 'pas de meta viewport').not.toBe('');
    // `maximum-scale=1` et `user-scalable=no` empêchent aussi le zoom au focus,
    // en retirant le zoom à qui en a besoin pour lire. Jamais ce compromis.
    expect(viewport).not.toMatch(/maximum-scale/);
    expect(viewport).not.toMatch(/user-scalable/);
    expect(viewport).toContain('width=device-width');
  });
});
