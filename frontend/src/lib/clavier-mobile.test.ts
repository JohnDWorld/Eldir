/**
 * Ce que le clavier tactile fait à la mise en page, que seul le source peut dire.
 *
 * Le composeur de la page de session vit en bas de l'écran, et écrire à Claude
 * est le geste le plus fréquent de l'app sur un téléphone. Sans
 * `interactive-widget=resizes-content`, le clavier ne rétrécit pas la vue de
 * mise en page (le défaut de la spec est `resizes-visual`) : l'app reste en
 * `height: 100%` d'une vue inchangée, et le composeur se retrouve SOUS le
 * clavier. Rien n'échoue, et ça ne se voit sur aucun écran de bureau.
 *
 * jsdom ne calcule pas de mise en page et n'a pas de clavier tactile : il ne
 * pourrait pas mesurer ça. On garde donc la clé en place, à la source.
 */

import { readFileSync } from 'node:fs';
import { join } from 'node:path';

import { describe, expect, it } from 'vitest';

// Vitest fournit `__dirname` même en ESM. `import.meta.url` ne convient pas ici :
// l'environnement de test est jsdom, l'URL n'est donc pas en `file:`, et
// `readFileSync` refuse avec « The URL must be of scheme file » AU CHARGEMENT du
// module, donc avant qu'aucun test n'ait pu s'exécuter.
// eslint-disable-next-line no-undef
const HTML = readFileSync(join(__dirname, '..', '..', 'index.html'), 'utf8');

describe('clavier tactile', () => {
  it('fait rétrécir la vue, pour que le composeur reste au-dessus du clavier', () => {
    const viewport = /<meta\s+name="viewport"[\s\S]*?\/>/.exec(HTML)?.[0] ?? '';

    expect(viewport, 'pas de meta viewport').not.toBe('');
    expect(viewport).toContain('interactive-widget=resizes-content');
  });

  it('garde la marge sous l’encoche, qui dépend de la même balise', () => {
    // `viewport-fit=cover` est ce qui donne une valeur à `env(safe-area-inset-*)`.
    // Sans lui, les marges d'encoche posées au lot précédent valent 0 partout,
    // et l'app redessine sous l'encoche sans qu'aucun test ne bronche.
    const viewport = /<meta\s+name="viewport"[\s\S]*?\/>/.exec(HTML)?.[0] ?? '';
    expect(viewport).toContain('viewport-fit=cover');
  });
});
