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
 * Les sources sont lues par l'analyseur de TypeScript, pas par des regex ni par un
 * appariement d'accolades écrit ici. Ce dépôt est commenté en français : une
 * apostrophe dans un commentaire (« comme l'annonce le »), une chaîne JSX ou un
 * regex, à l'intérieur d'un `{...}`, faisait perdre l'appariement et attribuait à un
 * `<textarea>` 8 000 caractères d'attributs, donc la règle `flex-1` ne voyait plus
 * le composeur de la page de session et restait verte sans rien avoir regardé.
 *
 * Chaque règle est une fonction qui rend ce qu'elle reproche à un source. Le dépôt
 * étant conforme, elles n'y trouvent rien : seul un source écrit pour elle prouve
 * qu'elle verrait quelque chose. Les derniers `describe` donnent donc à chaque
 * branche de chaque règle son témoin (ce qu'elle signale, chaque exemption qui
 * l'en empêche), à la lecture des sources les cas qui l'ont mise en défaut, et au
 * câblage (quelle règle regarde quels fichiers) le sien.
 */

import { readdirSync, readFileSync, statSync } from 'node:fs';
import { join } from 'node:path';

import ts from 'typescript';
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

// ── Lecture des sources ─────────────────────────────────────────────────

/** Une balise JSX, réduite à ce que les règles regardent. */
interface Balise {
  /** `input`, `pre`, `Foo.Bar`... */
  nom: string;
  /** Les classes de son `className`, lues dans ses littéraux de chaîne et de gabarit. */
  classes: string;
  /** Son contenu porte-t-il une valeur (`{x}`) ? Une espace `{' '}` et un commentaire n'en sont pas une. */
  aUneValeur: boolean;
}

/** Les littéraux de chaîne d'une expression : ce que `cn(a, b && 'c')` écrit comme classes. */
function litteraux(racine: ts.Node): string[] {
  const morceaux: string[] = [];
  const visite = (n: ts.Node): void => {
    if (
      ts.isStringLiteralLike(n) ||
      ts.isTemplateHead(n) ||
      ts.isTemplateMiddle(n) ||
      ts.isTemplateTail(n)
    ) {
      morceaux.push(n.text);
    } else {
      ts.forEachChild(n, visite);
    }
  };
  visite(racine);
  return morceaux;
}

function aUneValeur(enfants: readonly ts.JsxChild[]): boolean {
  return enfants.some((enfant) => {
    if (ts.isJsxExpression(enfant)) {
      const e = enfant.expression;
      return e !== undefined && !(ts.isStringLiteral(e) && e.text.trim() === '');
    }
    if (ts.isJsxElement(enfant) || ts.isJsxFragment(enfant)) return aUneValeur(enfant.children);
    return false;
  });
}

/** Toutes les balises JSX d'un source (ouvrantes et auto-fermantes), à tous les niveaux. */
function balises(source: string): Balise[] {
  const fichier = ts.createSourceFile(
    'source.tsx',
    source,
    ts.ScriptTarget.Latest,
    true,
    ts.ScriptKind.TSX,
  );
  const trouvees: Balise[] = [];
  const visite = (n: ts.Node): void => {
    if (ts.isJsxOpeningElement(n) || ts.isJsxSelfClosingElement(n)) {
      const attribut = n.attributes.properties.find(
        (p): p is ts.JsxAttribute =>
          ts.isJsxAttribute(p) && p.name.getText(fichier) === 'className',
      );
      trouvees.push({
        nom: n.tagName.getText(fichier),
        classes: attribut?.initializer ? litteraux(attribut.initializer).join(' ') : '',
        aUneValeur:
          ts.isJsxOpeningElement(n) && ts.isJsxElement(n.parent) && aUneValeur(n.parent.children),
      });
    }
    ts.forEachChild(n, visite);
  };
  visite(fichier);
  return trouvees;
}

// ── Les règles, une fonction chacune : elles rendent ce qu'elles reprochent ──

/** 1. `whitespace-pre-wrap` sans `break-words` ni `break-all`. */
function preWrapSansCoupure(source: string): string[] {
  return balises(source)
    .map((b) => b.classes)
    .filter(
      (cls) =>
        cls.includes('whitespace-pre-wrap') &&
        !cls.includes('break-words') &&
        !cls.includes('break-all'),
    );
}

/** 2. `<input>` / `<textarea>` en `flex-1` sans `min-w-0`. */
function champsFlexSansMinW0(source: string): string[] {
  return balises(source)
    .filter((b) => b.nom === 'input' || b.nom === 'textarea')
    .filter((b) => /\bflex-1\b/.test(b.classes) && !/\bmin-w-0\b/.test(b.classes))
    .map((b) => `<${b.nom} flex-1 sans min-w-0>`);
}

/**
 * 3. `<table>` sans `overflow-x-auto`. Au niveau du fichier, pas de la balise : on ne
 * sait pas à la lecture du source quel conteneur enveloppe quel tableau.
 */
function tableauSansDefilement(source: string): string[] {
  const toutes = balises(source);
  const aUnTableau = toutes.some((b) => b.nom === 'table');
  const defile = toutes.some((b) => b.classes.includes('overflow-x-auto'));
  return aUnTableau && !defile ? ['<table> sans overflow-x-auto'] : [];
}

/** 3 bis. `<pre>` ni défilable, ni coupé (`whitespace-pre-wrap` ET `break-words`/`break-all`). */
function presSansDefilementNiCoupure(source: string): string[] {
  return balises(source)
    .filter((b) => b.nom === 'pre')
    .filter((b) => {
      const defile = /overflow-x-auto|overflow-auto/.test(b.classes);
      const coupe =
        /whitespace-pre-wrap/.test(b.classes) && /break-words|break-all/.test(b.classes);
      return !defile && !coupe;
    })
    .map(() => '<pre> ni défilable ni coupé');
}

/**
 * 4. `<code>` en bloc, ou portant une valeur dynamique, et sans `break-all` /
 * `break-words` / conteneur défilable.
 */
function codesSansCoupure(source: string): string[] {
  return balises(source)
    .filter((b) => b.nom === 'code')
    .filter((b) => {
      const enBloc = /\bblock\b/.test(b.classes);
      const coupe = /\b(break-all|break-words|overflow-x-auto|overflow-auto)\b/.test(b.classes);
      return (enBloc || b.aUneValeur) && !coupe;
    })
    .map((b) => `<code className="${b.classes.slice(0, 60)}">`);
}

// ── Le câblage : quelle règle regarde quels fichiers ────────────────────

/** Ce qu'une règle reproche à un ensemble de sources (nom de fichier -> source). */
function reprochesDe(depot: Record<string, string>, regle: (source: string) => string[]): string[] {
  return Object.entries(depot).flatMap(([fichier, source]) =>
    regle(source).map((reproche) => `${fichier} : ${reproche.slice(0, 80)}`),
  );
}

const FILES = sourceFiles(SRC);
const DEPOT = Object.fromEntries(FILES.map((file) => [relative(file), readFileSync(file, 'utf8')]));

/** Ce qu'une règle reproche aux sources réelles du dépôt, tous fichiers confondus. */
function reprochesAuDepot(regle: (source: string) => string[]): string[] {
  return reprochesDe(DEPOT, regle);
}

/**
 * Les règles et, pour chacune, un source qu'elle est la seule à devoir signaler. Une
 * seule table sert aux deux usages (le dépôt réel, le source écrit pour elle) : on
 * ne peut donc pas brancher sur le dépôt la fonction d'une autre règle sans que le
 * test du sujet tombe.
 */
const REGLES = [
  { nom: 'pre-wrap', regle: preWrapSansCoupure, sujet: '<p className="whitespace-pre-wrap" />' },
  { nom: 'flex-1', regle: champsFlexSansMinW0, sujet: '<input className="flex-1" />' },
  { nom: 'table', regle: tableauSansDefilement, sujet: '<table />' },
  { nom: 'pre', regle: presSansDefilementNiCoupure, sujet: '<pre />' },
  { nom: 'code', regle: codesSansCoupure, sujet: '<code className="block" />' },
];

describe('pas de scroll horizontal', () => {
  it('trouve les sources à vérifier', () => {
    expect(FILES.length).toBeGreaterThan(10);
    expect(Object.keys(DEPOT)).toHaveLength(FILES.length);
  });

  it('lit les sources de l’app, dans tous les dossiers, et pas les fichiers de test', () => {
    expect(DEPOT['features/settings/agent-tokens.tsx']).toBeDefined();
    expect(DEPOT['components/eldir/session-card.tsx']).toBeDefined();
    expect(Object.keys(DEPOT).filter((f) => f.endsWith('.test.tsx'))).toEqual([]);
    expect(Object.keys(DEPOT).filter((f) => !f.endsWith('.tsx'))).toEqual([]);
  });

  it.each(REGLES)('le dépôt respecte la règle $nom', ({ regle }) => {
    expect(reprochesAuDepot(regle)).toEqual([]);
  });

  it('voit le composeur de la page de session, un champ en `flex-1` précédé d’un gestionnaire', () => {
    // Le cas qui a mis la lecture en défaut : un commentaire à apostrophe dans `onKeyDown`.
    // Dépouillé de son `min-w-0`, ce champ doit être reproché ; tel quel, il est en règle.
    const source = DEPOT['pages/session-page.tsx'] ?? '';
    expect(source).toContain("comme l'annonce le");
    expect(champsFlexSansMinW0(source)).toEqual([]);
    const sans = source.replace('min-h-11 min-w-0 flex-1', 'min-h-11 flex-1');
    expect(sans).not.toBe(source);
    expect(champsFlexSansMinW0(sans)).toEqual(['<textarea flex-1 sans min-w-0>']);
  });
});

describe('le câblage des règles', () => {
  it.each(REGLES)('la règle $nom signale son sujet, et elle seule', ({ regle, sujet }) => {
    expect(regle(sujet)).toHaveLength(1);
    for (const autre of REGLES.filter((r) => r.regle !== regle)) {
      expect(autre.regle(sujet)).toEqual([]);
    }
  });

  it('applique la règle à chaque fichier du dépôt réel, aucun de laissé de côté', () => {
    // Une règle qui signale tout : il doit y avoir un reproche par fichier source.
    const reproches = reprochesAuDepot(() => ['x']);
    expect(reproches).toHaveLength(FILES.length);
    expect(reproches).toContain('pages/session-page.tsx : x');
  });

  it('donne chaque source à la règle, pas une source vide', () => {
    const vues: string[] = [];
    reprochesDe({ 'a.tsx': 'A', 'b.tsx': 'B' }, (source) => {
      vues.push(source);
      return [];
    });
    expect(vues).toEqual(['A', 'B']);
  });

  it('nomme le fichier de chaque reproche, tous les fichiers fautifs', () => {
    const fautif = '<p className="whitespace-pre-wrap" />';
    const depot = { 'a.tsx': fautif, 'b.tsx': '<p />', 'c.tsx': fautif };
    expect(reprochesDe(depot, preWrapSansCoupure)).toEqual([
      'a.tsx : whitespace-pre-wrap',
      'c.tsx : whitespace-pre-wrap',
    ]);
  });

  it('ne dit rien d’un dépôt en règle', () => {
    expect(reprochesDe({ 'a.tsx': '<p />' }, preWrapSansCoupure)).toEqual([]);
    expect(reprochesDe({}, preWrapSansCoupure)).toEqual([]);
  });

  it('tronque un reproche trop long', () => {
    const [reproche] = reprochesDe({ 'a.tsx': 'x' }, () => ['y'.repeat(200)]);
    expect(reproche).toBe(`a.tsx : ${'y'.repeat(80)}`);
  });
});

describe('lecture des sources', () => {
  it('lit les balises ouvrantes, auto-fermantes et imbriquées', () => {
    const lues = balises('<div><pre className="a">x</pre><input className="b" /></div>');
    expect(lues.map((b) => [b.nom, b.classes])).toEqual([
      ['div', ''],
      ['pre', 'a'],
      ['input', 'b'],
    ]);
  });

  it('lit les classes en chaîne, en `cn(...)`, en objet et en gabarit', () => {
    expect(balises('<p className="a b" />')[0]?.classes).toBe('a b');
    expect(balises("<p className={cn('a', open && 'b')} />")[0]?.classes).toBe('a b');
    // Une clé d'objet en chaîne est une classe ; une clé nue (`{ a: b }`) n'est pas un littéral.
    expect(balises("<p className={cn({ 'a': b, c: d }, 'e')} />")[0]?.classes).toBe('a e');
    expect(balises('<p className={`a ${x} b`} />')[0]?.classes.split(/\s+/)).toEqual(['a', 'b']);
    // Début, milieu et fin d'un gabarit à deux valeurs, et gabarit sans valeur.
    expect(balises('<p className={`a ${x} b ${y} c`} />')[0]?.classes.split(/\s+/)).toEqual([
      'a',
      'b',
      'c',
    ]);
    expect(balises('<p className={`a b`} />')[0]?.classes).toBe('a b');
  });

  it('ne prend pas pour des classes ce qui n’est pas une chaîne', () => {
    expect(balises('<p className={cls} />')[0]?.classes).toBe('');
    expect(balises('<p />')[0]?.classes).toBe('');
    expect(balises('<p id="flex-1" />')[0]?.classes).toBe('');
  });

  // Le français met des apostrophes partout. Aucune ne doit faire perdre la balise.
  const AVEC_APOSTROPHE = [
    [
      'un commentaire de ligne dans un gestionnaire',
      "onKeyDown={(e) => {\n // comme l'annonce le\n go(e);\n }}",
    ],
    ['un commentaire de bloc dans un gestionnaire', "onKeyDown={(e) => { /* l'ordre */ go(e); }}"],
    ['un commentaire entre deux attributs', '/* l\'ordre */ id="x"'],
    ['du JSX à apostrophe passé en attribut', "hint={<p>l'éditeur</p>}"],
    ['un regex à apostrophe', "onChange={(e) => e.target.value.replace(/'/g, '')}"],
    ['une chaîne à guillemets droits qui contient une apostrophe', 'title={"l\'agent"}'],
    ['un attribut entre apostrophes', 'title=\'a "b"\''],
    ['un gabarit à accolades et apostrophe', "title={`l'${x} }`}"],
    ['une apostrophe échappée', "title={'l\\'agent'}"],
  ] as const;

  it.each(AVEC_APOSTROPHE)('garde le `className` qui suit : %s', (_cas, attribut) => {
    const source = `<input ${attribut} className="flex-1" />`;
    expect(balises(source)[0]?.classes).toBe('flex-1');
    expect(champsFlexSansMinW0(source)).toEqual(['<input flex-1 sans min-w-0>']);
  });

  it('garde le `className` qui précède une apostrophe, et les balises qui suivent', () => {
    const source = `<div><input className="flex-1" title="l'agent" /><pre>x</pre></div>`;
    expect(balises(source).map((b) => b.nom)).toEqual(['div', 'input', 'pre']);
  });

  it('dit si le contenu porte une valeur', () => {
    const valeur = (source: string) => balises(source).find((b) => b.nom === 'code')?.aUneValeur;
    expect(valeur('<code>{x}</code>')).toBe(true);
    expect(valeur('<code>a{x}b</code>')).toBe(true);
    expect(valeur('<code><b>{x}</b></code>')).toBe(true);
    expect(valeur('<code><>{x}</></code>')).toBe(true);
    expect(valeur('<code>abc</code>')).toBe(false);
    expect(valeur("<code>a{' '}b</code>")).toBe(false);
    expect(valeur('<code>{/* un commentaire */}</code>')).toBe(false);
    expect(valeur('<code className={x} />')).toBe(false);
    // Une valeur dans un attribut d'un enfant n'est pas une valeur du contenu.
    expect(valeur('<code><b className={x}>a</b></code>')).toBe(false);
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
    expect(
      preWrapSansCoupure("<p className={cn({ a: b }, 'whitespace-pre-wrap')} />"),
    ).toHaveLength(1);
    expect(preWrapSansCoupure('<p className={`whitespace-pre-wrap ${x}`} />')).toHaveLength(1);
    expect(preWrapSansCoupure('<p className={`whitespace-pre-wrap ${x} break-words`} />')).toEqual(
      [],
    );
  });

  it('juge chaque attribut, pas le fichier : un `break-words` ailleurs n’excuse pas', () => {
    const source = '<><a className="break-words" /><p className="whitespace-pre-wrap" /></>';
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

  it('ne tient pour exemption que `min-w-0` : un autre `min-w-*` ne laisse pas rétrécir', () => {
    expect(champsFlexSansMinW0('<input className="flex-1 min-w-full" />')).toHaveLength(1);
    expect(champsFlexSansMinW0('<input className="flex-1 min-w-fit" />')).toHaveLength(1);
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
    expect(champsFlexSansMinW0('<Input className="flex-1" />')).toEqual([]);
    expect(champsFlexSansMinW0('<inputGroup className="flex-1" />')).toEqual([]);
  });

  it('ne lit que le `className` : `flex-1` dans un autre attribut n’en est pas un', () => {
    expect(champsFlexSansMinW0('<input title="flex-1" />')).toEqual([]);
    expect(champsFlexSansMinW0('<input className="flex-1 min-w-0" title="a" />')).toEqual([]);
    expect(champsFlexSansMinW0('<input className="flex-1" data-x="min-w-0" />')).toHaveLength(1);
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
    const source = '<><input className="flex-1 min-w-0" /><input className="flex-1" /></>';
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

  it('ne prend pas un commentaire ou une chaîne pour un tableau ou pour son conteneur', () => {
    expect(tableauSansDefilement('<p>{/* <table> */}</p>')).toEqual([]);
    expect(tableauSansDefilement('<><table /><p title="overflow-x-auto" /></>')).toHaveLength(1);
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
    const source = '<><pre className="overflow-x-auto">a</pre><pre>b</pre></>';
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
    expect(codesSansCoupure('<><code>a</code><code>{x}</code></>')).toHaveLength(1);
    expect(codesSansCoupure('<><code>{x}</code><code>b</code></>')).toHaveLength(1);
  });
});
