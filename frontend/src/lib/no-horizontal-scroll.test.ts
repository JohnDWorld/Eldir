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
 *
 * Chaque règle est une fonction qui rend ce qu'elle reproche à un source. Le dépôt
 * étant conforme, elles n'y trouvent rien : seul un source écrit pour elle prouve
 * qu'elle verrait quelque chose. Les derniers `describe` donnent donc à chaque
 * branche de chaque règle son témoin (ce qu'elle signale, chaque exemption qui
 * l'en empêche), et à la lecture du JSX les cas qui l'ont mise en défaut.
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

function relative(file: string): string {
  return file.slice(SRC.length + 1);
}

// ── Lecture du JSX ──────────────────────────────────────────────────────
// Une regex `[^>]*` s'arrête au `>` d'une flèche (`onChange={(e) => f(e)}`) et ne
// voit plus un `className` placé après un gestionnaire ; `[^}]*` s'arrête à
// l'accolade d'un objet (`cn({ a: b }, 'x')`). Les règles lisent donc le JSX par
// accolades appariées, en ignorant celles des chaînes.

/** Index de l'accolade fermante qui répond à l'ouvrante située en `debut`. */
function accoladeFermante(source: string, debut: number): number {
  let profondeur = 0;
  let guillemet: string | null = null;
  for (let i = debut; i < source.length; i++) {
    const c = source[i];
    if (guillemet !== null) {
      if (c === '\\') i++;
      else if (c === guillemet) guillemet = null;
    } else if (c === '"' || c === "'" || c === '`') {
      guillemet = c;
    } else if (c === '{') {
      profondeur++;
    } else if (c === '}' && --profondeur === 0) {
      return i;
    }
  }
  return source.length;
}

interface BaliseOuvrante {
  /** Les attributs, entre le nom de la balise et son `>`. */
  attributs: string;
  /** Index du `>` qui ferme la balise ouvrante. */
  fin: number;
}

/** Les balises ouvrantes `<nom ...>` : le `>` ne ferme que hors expression `{...}` et hors chaîne. */
function balisesOuvrantes(source: string, nom: string): BaliseOuvrante[] {
  return [...source.matchAll(new RegExp(`<${nom}\\b`, 'g'))].map((m) => {
    const debut = m.index + m[0].length;
    let guillemet: string | null = null;
    let i = debut;
    for (; i < source.length; i++) {
      const c = source[i];
      if (guillemet !== null) {
        if (c === guillemet) guillemet = null;
      } else if (c === '"' || c === "'") {
        guillemet = c;
      } else if (c === '{') {
        i = accoladeFermante(source, i);
      } else if (c === '>') {
        break;
      }
    }
    return { attributs: source.slice(debut, i), fin: i };
  });
}

/** Les valeurs de `className`, y compris celles composées via `cn(...)` ou un gabarit. */
function classAttributes(source: string): string[] {
  return [...source.matchAll(/className=/g)].map((m) => {
    const debut = m.index + m[0].length;
    if (source[debut] === '"') return source.slice(debut + 1, source.indexOf('"', debut + 1));
    if (source[debut] === '{') return source.slice(debut + 1, accoladeFermante(source, debut));
    return '';
  });
}

// ── Les règles, une fonction chacune : elles rendent ce qu'elles reprochent ──

/** 1. `whitespace-pre-wrap` sans `break-words` ni `break-all`. */
function preWrapSansCoupure(source: string): string[] {
  return classAttributes(source).filter(
    (cls) =>
      cls.includes('whitespace-pre-wrap') &&
      !cls.includes('break-words') &&
      !cls.includes('break-all'),
  );
}

/** 2. `<input>` / `<textarea>` en `flex-1` sans `min-w-0`. */
function champsFlexSansMinW0(source: string): string[] {
  return ['input', 'textarea'].flatMap((nom) =>
    balisesOuvrantes(source, nom)
      .filter((b) => /\bflex-1\b/.test(b.attributs) && !/\bmin-w-0\b/.test(b.attributs))
      .map(() => `<${nom} flex-1 sans min-w-0>`),
  );
}

/**
 * 3. `<table>` sans `overflow-x-auto`. Au niveau du fichier, pas de la balise : on ne
 * sait pas à la lecture du source quel conteneur enveloppe quel tableau.
 */
function tableauSansDefilement(source: string): string[] {
  return /<table\b/.test(source) && !source.includes('overflow-x-auto')
    ? ['<table> sans overflow-x-auto']
    : [];
}

/** 3 bis. `<pre>` ni défilable, ni coupé (`whitespace-pre-wrap` ET `break-words`/`break-all`). */
function presSansDefilementNiCoupure(source: string): string[] {
  return balisesOuvrantes(source, 'pre')
    .filter((b) => {
      const defile = /overflow-x-auto|overflow-auto/.test(b.attributs);
      const coupe =
        /whitespace-pre-wrap/.test(b.attributs) && /break-words|break-all/.test(b.attributs);
      return !defile && !coupe;
    })
    .map(() => '<pre> ni défilable ni coupé');
}

/**
 * 4. `<code>` en bloc, ou portant une valeur dynamique, et sans `break-all` /
 * `break-words` / conteneur défilable.
 */
function codesSansCoupure(source: string): string[] {
  return balisesOuvrantes(source, 'code')
    .filter((b) => {
      const fermeture = source.indexOf('</code>', b.fin);
      // `{' '}` est une espace de mise en page, pas une valeur.
      const contenu = source
        .slice(b.fin + 1, fermeture < 0 ? source.length : fermeture)
        .replace(/\{' '\}/g, '');
      const enBloc = /\bblock\b/.test(b.attributs);
      const dynamique = /\{[^}]*\}/.test(contenu);
      const coupe = /\b(break-all|break-words|overflow-x-auto|overflow-auto)\b/.test(b.attributs);
      return (enBloc || dynamique) && !coupe;
    })
    .map((b) => `<code${b.attributs.slice(0, 60)}>`);
}

const FILES = sourceFiles(SRC);

/** Ce qu'une règle reproche aux sources réelles, fichier par fichier. */
function reprochesAuDepot(regle: (source: string) => string[]): string[] {
  return FILES.flatMap((file) =>
    regle(readFileSync(file, 'utf8')).map(
      (reproche) => `${relative(file)} : ${reproche.slice(0, 80)}`,
    ),
  );
}

describe('pas de scroll horizontal', () => {
  it('trouve les sources à vérifier', () => {
    expect(FILES.length).toBeGreaterThan(10);
  });

  it('coupe les longues chaînes dans le texte pré-formaté', () => {
    expect(reprochesAuDepot(preWrapSansCoupure)).toEqual([]);
  });

  it('laisse les champs de saisie rétrécir dans une ligne flex', () => {
    expect(reprochesAuDepot(champsFlexSansMinW0)).toEqual([]);
  });

  it('coupe les longues chaînes dans un <code> en bloc ou à valeur dynamique', () => {
    expect(reprochesAuDepot(codesSansCoupure)).toEqual([]);
  });

  it('donne un conteneur défilable aux tableaux', () => {
    expect(reprochesAuDepot(tableauSansDefilement)).toEqual([]);
  });

  it('donne un conteneur défilable, ou coupe, les blocs pré-formatés', () => {
    expect(reprochesAuDepot(presSansDefilementNiCoupure)).toEqual([]);
  });
});

// Le dépôt est conforme : les règles ci-dessus n'y trouvent rien, donc rien ne
// prouve qu'elles verraient quelque chose. Une règle dont les branches ne sont
// exercées par aucune source n'est qu'une porte décorative : on cesse de regarder
// alors qu'elle laisse passer. Chaque branche a donc son témoin ici, sur des
// sources écrites pour elle : ce qu'elle doit signaler, et chaque exemption qui
// doit l'empêcher de signaler.
describe('lecture du JSX', () => {
  it('ne ferme pas une balise au `>` d’une flèche', () => {
    const [balise] = balisesOuvrantes('<input onChange={(e) => set(e)} className="a" />', 'input');
    expect(balise?.attributs).toContain('className="a"');
  });

  it('ne ferme pas une balise au `>` d’une chaîne', () => {
    const [balise] = balisesOuvrantes('<pre title="a > b" className="c">', 'pre');
    expect(balise?.attributs).toContain('className="c"');
  });

  it('lit une expression `className` jusqu’à son accolade appariée', () => {
    expect(classAttributes("<p className={cn({ a: b }, 'whitespace-pre-wrap')} />")).toEqual([
      "cn({ a: b }, 'whitespace-pre-wrap')",
    ]);
    expect(classAttributes('<p className={`x ${y} break-words`} />')).toEqual([
      '`x ${y} break-words`',
    ]);
    expect(classAttributes('<p className="a b" />')).toEqual(['a b']);
  });

  it('ignore les accolades qui sont dans une chaîne, un gabarit ou après un échappement', () => {
    expect(classAttributes("<p className={cn('a}b', 'c')} />")).toEqual(["cn('a}b', 'c')"]);
    expect(classAttributes('<p className={`a } b`} />')).toEqual(['`a } b`']);
    expect(classAttributes(String.raw`<p className={cn('it\'s}', 'x')} />`)).toEqual([
      String.raw`cn('it\'s}', 'x')`,
    ]);
  });

  it('ne confond pas deux balises du même nom', () => {
    expect(balisesOuvrantes('<pre className="a"><pre className="b">', 'pre')).toHaveLength(2);
    expect(balisesOuvrantes('<preview className="a">', 'pre')).toEqual([]);
  });
});

describe('règle 1 : `whitespace-pre-wrap` sans `break-words`', () => {
  it('signale `whitespace-pre-wrap` seul, même au milieu d’autres classes', () => {
    expect(preWrapSansCoupure('<p className="whitespace-pre-wrap" />')).toHaveLength(1);
    expect(
      preWrapSansCoupure('<p className="font-mono whitespace-pre-wrap text-xs" />'),
    ).toHaveLength(1);
  });

  it('laisse passer ce qui coupe : `break-words` ou `break-all`', () => {
    expect(preWrapSansCoupure('<p className="whitespace-pre-wrap break-words" />')).toEqual([]);
    expect(preWrapSansCoupure('<p className="whitespace-pre-wrap break-all" />')).toEqual([]);
  });

  it('ne reproche rien à un élément sans `whitespace-pre-wrap`', () => {
    expect(preWrapSansCoupure('<p className="break-words" />')).toEqual([]);
    expect(preWrapSansCoupure('<p className="font-mono" />')).toEqual([]);
  });

  it('lit les classes composées par `cn(...)`, par un objet et par un gabarit', () => {
    expect(
      preWrapSansCoupure("<p className={cn('whitespace-pre-wrap', open && 'x')} />"),
    ).toHaveLength(1);
    expect(
      preWrapSansCoupure("<p className={cn('whitespace-pre-wrap', 'break-words')} />"),
    ).toEqual([]);
    // Classe placée APRÈS l'accolade d'un objet : `[^}]*` ne la lisait pas.
    expect(
      preWrapSansCoupure("<p className={cn({ a: b }, 'whitespace-pre-wrap')} />"),
    ).toHaveLength(1);
    expect(preWrapSansCoupure('<p className={`whitespace-pre-wrap ${x}`} />')).toHaveLength(1);
    expect(preWrapSansCoupure('<p className={`whitespace-pre-wrap ${x} break-words`} />')).toEqual(
      [],
    );
  });

  it('juge chaque attribut, pas le fichier : un `break-words` ailleurs n’excuse pas', () => {
    const source = '<a className="break-words" /><p className="whitespace-pre-wrap" />';
    expect(preWrapSansCoupure(source)).toHaveLength(1);
  });
});

describe('règle 2 : `<input>` / `<textarea>` en `flex-1` sans `min-w-0`', () => {
  it('signale un champ en `flex-1` sans `min-w-0`', () => {
    expect(champsFlexSansMinW0('<input className="flex-1" />')).toEqual([
      '<input flex-1 sans min-w-0>',
    ]);
    expect(champsFlexSansMinW0('<textarea className="flex-1 p-2"></textarea>')).toEqual([
      '<textarea flex-1 sans min-w-0>',
    ]);
  });

  it('laisse passer un champ qui peut rétrécir', () => {
    expect(champsFlexSansMinW0('<input className="flex-1 min-w-0" />')).toEqual([]);
    expect(champsFlexSansMinW0('<textarea className="min-w-0 flex-1" />')).toEqual([]);
  });

  it('ne reproche rien à un champ qui n’est pas en `flex-1`', () => {
    expect(champsFlexSansMinW0('<input className="w-full" />')).toEqual([]);
    expect(champsFlexSansMinW0('<input />')).toEqual([]);
  });

  it('ne reproche rien à ce qui n’est pas un champ de saisie', () => {
    expect(champsFlexSansMinW0('<div className="flex-1" />')).toEqual([]);
    expect(champsFlexSansMinW0('<inputGroup className="flex-1" />')).toEqual([]);
  });

  it('voit un `className` placé après un gestionnaire à flèche dans la même balise', () => {
    const source = '<input onChange={(e) => set(e.target.value)} className="flex-1" />';
    expect(champsFlexSansMinW0(source)).toHaveLength(1);
    const exempte = '<input onChange={(e) => set(e.target.value)} className="flex-1 min-w-0" />';
    expect(champsFlexSansMinW0(exempte)).toEqual([]);
  });

  it('lit une balise écrite sur plusieurs lignes', () => {
    const source = '<input\n  type="text"\n  value={v}\n  className="flex-1"\n/>';
    expect(champsFlexSansMinW0(source)).toHaveLength(1);
  });

  it('juge chaque balise : un champ en règle n’excuse pas son voisin', () => {
    const source = '<input className="flex-1 min-w-0" /><input className="flex-1" />';
    expect(champsFlexSansMinW0(source)).toHaveLength(1);
  });

  it('lit les variantes : `sm:flex-1` est un `flex-1`', () => {
    expect(champsFlexSansMinW0('<input className="sm:flex-1" />')).toHaveLength(1);
  });
});

describe('règle 3 : `<table>` sans conteneur défilable', () => {
  it('signale un tableau sans `overflow-x-auto`', () => {
    expect(tableauSansDefilement('<table className="w-full"></table>')).toHaveLength(1);
    expect(tableauSansDefilement('<table></table>')).toHaveLength(1);
  });

  it('laisse passer un tableau dans un conteneur `overflow-x-auto`', () => {
    const source = '<div className="overflow-x-auto"><table></table></div>';
    expect(tableauSansDefilement(source)).toEqual([]);
  });

  it('ne reproche rien à un source sans tableau', () => {
    expect(tableauSansDefilement('<div className="w-full" />')).toEqual([]);
    expect(tableauSansDefilement('<tablet />')).toEqual([]);
  });
});

describe('règle 3 bis : `<pre>` ni défilable ni coupé', () => {
  it('signale un `<pre>` nu, ou sans coupure ni défilement', () => {
    expect(presSansDefilementNiCoupure('<pre>x</pre>')).toHaveLength(1);
    expect(presSansDefilementNiCoupure('<pre className="font-mono">x</pre>')).toHaveLength(1);
  });

  it('laisse passer un `<pre>` défilable', () => {
    expect(presSansDefilementNiCoupure('<pre className="overflow-x-auto">x</pre>')).toEqual([]);
    expect(presSansDefilementNiCoupure('<pre className="overflow-auto">x</pre>')).toEqual([]);
  });

  it('laisse passer un `<pre>` qui se coupe : `whitespace-pre-wrap` avec `break-words` ou `break-all`', () => {
    expect(
      presSansDefilementNiCoupure('<pre className="whitespace-pre-wrap break-words">x</pre>'),
    ).toEqual([]);
    expect(
      presSansDefilementNiCoupure('<pre className="whitespace-pre-wrap break-all">x</pre>'),
    ).toEqual([]);
  });

  it('exige les DEUX pour la coupure : un `<pre>` ne revient pas à la ligne par défaut', () => {
    expect(
      presSansDefilementNiCoupure('<pre className="whitespace-pre-wrap">x</pre>'),
    ).toHaveLength(1);
    expect(presSansDefilementNiCoupure('<pre className="break-words">x</pre>')).toHaveLength(1);
    expect(presSansDefilementNiCoupure('<pre className="break-all">x</pre>')).toHaveLength(1);
  });

  it('voit un `className` placé après un gestionnaire à flèche, dans les deux sens', () => {
    expect(
      presSansDefilementNiCoupure('<pre onClick={() => f()} className="overflow-x-auto">x</pre>'),
    ).toEqual([]);
    expect(
      presSansDefilementNiCoupure('<pre onClick={() => f()} className="x">x</pre>'),
    ).toHaveLength(1);
  });

  it('juge chaque `<pre>` : un défilable n’excuse pas son voisin', () => {
    const source = '<pre className="overflow-x-auto">a</pre><pre>b</pre>';
    expect(presSansDefilementNiCoupure(source)).toHaveLength(1);
  });
});

describe('règle 4 : `<code>` en bloc ou à valeur dynamique, sans coupure', () => {
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
    expect(codesSansCoupure('<code className="block overflow-auto">{x}</code>')).toEqual([]);
  });

  it('voit un `className` placé après un gestionnaire à flèche', () => {
    expect(
      codesSansCoupure('<code onClick={() => f()} className="block break-all">{x}</code>'),
    ).toEqual([]);
    expect(codesSansCoupure('<code onClick={() => f()}>{x}</code>')).toHaveLength(1);
  });

  it('ne prend pas le contenu d’un autre <code> pour le sien', () => {
    expect(codesSansCoupure('<code>a</code><code>{x}</code>')).toHaveLength(1);
    expect(codesSansCoupure('<code>{x}</code><code>b</code>')).toHaveLength(1);
  });
});
