/**
 * Garde-fou anti-scroll horizontal.
 *
 * Quatre motifs ont chacun déjà rendu (ou pu rendre) une page scrollable de côté sur mobile,
 * et aucun ne se voit en relecture de diff. On les interdit à la source, ici,
 * plutôt que de les redécouvrir sur un téléphone :
 *
 * 1. `whitespace-pre-wrap` sans `break-words` : un chemin de fichier de 60
 *    caractères n'a aucun espace où se couper, il pousse la page entière.
 * 2. un `<input>`/`<textarea>` en `flex-1` sans `min-w-0` : un champ a une
 *    largeur intrinsèque (~180px) et ne descend pas en dessous.
 * 3. un `<table>` ou un `<pre>` sans conteneur défilable : ils sont plus
 *    larges que 375px par nature.
 * 4. un `<code>` en bloc, ou qui porte une valeur dynamique, sans `break-all` :
 *    un jeton, un alias, un chemin n'ont aucune espace où se couper. Le jeton
 *    d'agent fait ~200 caractères d'un seul tenant et pousserait la page hors
 *    cadre. Une valeur dynamique, on ne la connaît pas à la lecture du source :
 *    on suppose donc qu'elle peut être longue.
 *
 * Ce test lit les sources, il ne rend rien : jsdom ne fait pas de mise en
 * page, il ne pourrait de toute façon pas mesurer un débordement.
 */

import { readdirSync, readFileSync, statSync } from 'node:fs';
import { join } from 'node:path';

import { describe, expect, it } from 'vitest';

// Vitest fournit `__dirname` même en ESM. `import.meta.url` ne convient pas
// ici : l'environnement de test est jsdom, l'URL n'est donc pas en `file:`.
// eslint-disable-next-line no-undef
const SRC = join(__dirname, '..');

function sourceFiles(dir: string): string[] {
  return readdirSync(dir).flatMap((entry) => {
    const full = join(dir, entry);
    if (statSync(full).isDirectory()) return sourceFiles(full);
    return /\.tsx$/.test(full) && !full.endsWith('.test.tsx') ? [full] : [];
  });
}

/** Les valeurs de `className`, y compris celles composées via `cn(...)`. */
function classAttributes(source: string): string[] {
  return [...source.matchAll(/className=(?:"([^"]*)"|\{([^}]*)\})/g)].map(
    (m) => m[1] ?? m[2] ?? '',
  );
}

function relative(file: string): string {
  return file.slice(SRC.length + 1);
}

/**
 * Les `<code>` d'un source qui peuvent pousser la page : en bloc, ou portant une
 * valeur dynamique, et sans `break-all` / `break-words` / conteneur défilable.
 */
function codesSansCoupure(source: string): string[] {
  return [...source.matchAll(/<code\b([^>]*)>([\s\S]*?)<\/code>/g)]
    .filter((m) => {
      const attributs = m[1] ?? '';
      // `{' '}` est une espace de mise en page, pas une valeur.
      const contenu = (m[2] ?? '').replace(/\{' '\}/g, '');
      const enBloc = /\bblock\b/.test(attributs);
      const dynamique = /\{[^}]*\}/.test(contenu);
      const coupe = /\b(break-all|break-words|overflow-x-auto|overflow-auto)\b/.test(attributs);
      return (enBloc || dynamique) && !coupe;
    })
    .map((m) => `<code${(m[1] ?? '').slice(0, 60)}>`);
}

const FILES = sourceFiles(SRC);

describe('pas de scroll horizontal', () => {
  it('trouve les sources à vérifier', () => {
    expect(FILES.length).toBeGreaterThan(10);
  });

  it('coupe les longues chaînes dans le texte pré-formaté', () => {
    const offenders = FILES.flatMap((file) =>
      classAttributes(readFileSync(file, 'utf8'))
        .filter(
          (cls) =>
            cls.includes('whitespace-pre-wrap') &&
            !cls.includes('break-words') &&
            !cls.includes('break-all'),
        )
        .map((cls) => `${relative(file)} : ${cls.slice(0, 80)}`),
    );
    expect(offenders).toEqual([]);
  });

  it('laisse les champs de saisie rétrécir dans une ligne flex', () => {
    const offenders = FILES.flatMap((file) => {
      const source = readFileSync(file, 'utf8');
      return [...source.matchAll(/<(input|textarea)\b[^>]*>/gs)]
        .filter((m) => /\bflex-1\b/.test(m[0]) && !/\bmin-w-0\b/.test(m[0]))
        .map((m) => `${relative(file)} : <${m[1]} flex-1 sans min-w-0>`);
    });
    expect(offenders).toEqual([]);
  });

  it('coupe les longues chaînes dans un <code> en bloc ou à valeur dynamique', () => {
    const offenders = FILES.flatMap((file) =>
      codesSansCoupure(readFileSync(file, 'utf8')).map(
        (balise) => `${relative(file)} : ${balise} sans break-all`,
      ),
    );
    expect(offenders).toEqual([]);
  });

  it('donne un conteneur défilable aux tableaux et aux blocs pré-formatés', () => {
    const offenders = FILES.flatMap((file) => {
      const source = readFileSync(file, 'utf8');
      const found: string[] = [];
      if (/<table\b/.test(source) && !source.includes('overflow-x-auto')) {
        found.push(`${relative(file)} : <table> sans overflow-x-auto`);
      }
      for (const m of source.matchAll(/<pre\b[^>]*>/gs)) {
        const cls = m[0];
        const scrolls = /overflow-x-auto|overflow-auto/.test(cls);
        const wraps = /whitespace-pre-wrap/.test(cls) && /break-words|break-all/.test(cls);
        if (!scrolls && !wraps) {
          found.push(`${relative(file)} : <pre> ni défilable ni coupé`);
        }
      }
      return found;
    });
    expect(offenders).toEqual([]);
  });
});

describe('la règle du <code>, sur des sources écrits pour elle', () => {
  it('signale un <code> en bloc sans coupure, même à contenu statique', () => {
    expect(codesSansCoupure('<code className="block">abc</code>')).toHaveLength(1);
  });

  it('signale un <code> à valeur dynamique sans coupure, même en ligne', () => {
    expect(codesSansCoupure('<code>{jeton}</code>')).toHaveLength(1);
  });

  it('laisse passer un <code> en ligne à contenu statique', () => {
    expect(codesSansCoupure('<code>OLLAMA_BASE_URL</code>')).toEqual([]);
    expect(codesSansCoupure("<code>a{' '}b</code>")).toEqual([]);
  });

  it('laisse passer ce qui se coupe ou défile', () => {
    expect(codesSansCoupure('<code className="block break-all">{x}</code>')).toEqual([]);
    expect(codesSansCoupure('<code className="break-words">{x}</code>')).toEqual([]);
    expect(codesSansCoupure('<code className="block overflow-x-auto">{x}</code>')).toEqual([]);
  });
});
