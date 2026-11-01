/**
 * Garde-fou du voile de dialogue.
 *
 * Neuf fichiers recopiaient la même déclaration au caractère près, et elle
 * était fausse sur un téléphone : un élément `fixed` échappe au positionnement
 * de la coquille, donc il ne reçoit aucune de ses marges d'encoche. Les neuf
 * voiles passaient sous l'encoche en paysage et sous la barre de geste en
 * portrait, sans que ça se voie, parce qu'ils sont centrés et plus étroits que
 * l'écran : ils échappaient au défaut par chance.
 *
 * Ce test lit les sources. jsdom ne calcule aucune mise en page et ne connaît
 * ni encoche ni barre de geste : il ne pourrait pas mesurer ça.
 */

import { readdirSync, readFileSync, statSync } from 'node:fs';
import { join } from 'node:path';

import { describe, expect, it } from 'vitest';

// Vitest fournit `__dirname` même en ESM. `import.meta.url` ne convient pas
// ici : l'environnement de test est jsdom, l'URL n'est donc pas en `file:`.
// eslint-disable-next-line no-undef
const SRC = join(__dirname, '..');

const CSS = readFileSync(join(SRC, 'styles/globals.css'), 'utf8');

/** Tous les `.tsx` de l'app, fichiers de test exclus. */
function sourcesTsx(dir: string = SRC): string[] {
  return readdirSync(dir).flatMap((entree) => {
    const complet = join(dir, entree);
    if (statSync(complet).isDirectory()) return sourcesTsx(complet);
    return /\.tsx$/.test(complet) && !complet.endsWith('.test.tsx') ? [complet] : [];
  });
}

function relatif(fichier: string): string {
  return fichier.slice(SRC.length + 1);
}

/** La déclaration `.eldir-overlay { … }`. */
function regleVoile(): string {
  return /\.eldir-overlay\s*\{[\s\S]*?\n {2}\}/.exec(CSS)?.[0] ?? '';
}

describe('.eldir-overlay', () => {
  it('porte les quatre marges d’encoche, puisqu’il est `fixed`', () => {
    const regle = regleVoile();
    expect(regle, 'déclaration introuvable').not.toBe('');
    for (const cote of ['top', 'right', 'bottom', 'left']) {
      expect(regle, `marge ${cote} absente`).toContain(`env(safe-area-inset-${cote})`);
    }
  });

  it('garde un plancher, pour un écran sans encoche', () => {
    // `env(safe-area-inset-*)` vaut 0 sur un écran qui n'en a pas : sans le
    // `max()`, le dialogue se collerait alors au bord. Le plancher est l'ancien
    // `p-4`.
    const regle = regleVoile();
    expect((regle.match(/max\(1rem, env\(safe-area-inset-\w+\)\)/g) ?? []).length).toBe(4);
  });
});

describe('aucun voile refait à la main', () => {
  it('ne laisse plus `fixed inset-0` dans un `.tsx`', () => {
    // Un voile recopié à la main repartirait sans marge d'encoche, et le défaut
    // ne se verrait que sur un téléphone, en paysage.
    const fautifs = sourcesTsx().filter((f) => readFileSync(f, 'utf8').includes('fixed inset-0'));
    expect(fautifs.map(relatif)).toEqual([]);
  });
});
