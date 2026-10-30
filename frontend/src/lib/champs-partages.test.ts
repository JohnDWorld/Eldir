/**
 * Garde-fou de la classe de champ partagée.
 *
 * Les 32 champs de l'app recopiaient la même déclaration à la main, à deux
 * tailles de police, avec deux fonds et sans plancher de hauteur. Ils tiennent
 * maintenant dans `.eldir-field`. Rien n'empêche le prochain champ de repartir
 * d'un copier-coller : c'est ce que ce fichier surveille.
 *
 * Il lit les sources, il ne rend rien. Un test de rendu dirait qu'un champ
 * porte la classe, pas que la classe est la seule façon d'en écrire un, et
 * jsdom ne calcule aucune mise en page : il ne verrait ni la hauteur, ni la
 * cascade.
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

/** Le corps de `@layer components { … }`, accolades appariées. */
function calqueComponents(css: string): string {
  const debut = css.indexOf('@layer components {');
  if (debut === -1) return '';
  let profondeur = 0;
  for (let i = css.indexOf('{', debut); i < css.length; i += 1) {
    if (css[i] === '{') profondeur += 1;
    else if (css[i] === '}') {
      profondeur -= 1;
      if (profondeur === 0) return css.slice(debut, i + 1);
    }
  }
  return '';
}

/** La déclaration `.eldir-field { … }`, où qu'elle soit. */
function regleChamp(css: string): string {
  const m = /\.eldir-field\s*\{[^}]*\}/.exec(css);
  return m ? m[0] : '';
}

describe('.eldir-field', () => {
  it('tient le plancher de 44px que les champs n’avaient pas', () => {
    // `py-2` plus le plancher de 16px du bas de globals.css donnent 37px :
    // sous la règle des 44×44 d'AGENTS.md, que les boutons appliquent déjà.
    expect(regleChamp(CSS)).toMatch(/\bmin-h-11\b/);
  });

  it('porte un fond par défaut, pour qu’un fond oublié reste lisible', () => {
    // Un champ prend l'inverse du fond de son conteneur. Le défaut est papier
    // (le cas des pages, dont les sections sont crème) ; les dialogues, qui
    // sont papier, posent `bg-eldir-cream` par-dessus. Sans défaut, un fond
    // oublié rendrait le champ transparent, donc crème sur crème.
    expect(regleChamp(CSS)).toMatch(/\bbg-eldir-paper\b/);
  });

  it('est déclarée dans `@layer components`, sinon les surcharges ne passent plus', () => {
    // Tailwind émet `components` avant `utilities`. C'est ce qui permet à
    // `bg-eldir-cream`, `text-xs`, `p-3` et `min-h-[400px]` écrits au point
    // d'appel de battre la classe : à spécificité égale (une classe contre une
    // classe), seul l'ordre d'émission tranche. Déplacée dans `utilities` ou
    // après, la classe gagnerait et les quatre surcharges tomberaient sans
    // qu'aucun type ni aucun lint ne bronche.
    expect(calqueComponents(CSS)).toContain('.eldir-field');
  });
});

describe('aucun champ refait à la main', () => {
  it('ne laisse `focus:border-eldir-orange` que dans la feuille de style', () => {
    // Ce marqueur ne servait qu'aux champs. Hors de globals.css, il signe un
    // champ recopié à la main au lieu de `.eldir-field` : c'est très
    // exactement la duplication que ce lot a retirée.
    const fautifs = sourcesTsx().filter((f) =>
      readFileSync(f, 'utf8').includes('focus:border-eldir-orange'),
    );
    expect(fautifs.map(relatif)).toEqual([]);
  });
});
