/**
 * Vérifie que la build est installable.
 *
 * Lighthouse portait cette garantie jusqu'à la version 11 : `installable-manifest`
 * et `service-worker`. La 12 a supprimé la catégorie PWA et ces audits avec, et
 * n'offre aucun remplacement. Le ROADMAP promet pourtant une app installable
 * depuis la phase 0, et rien d'autre ne le vérifie : un manifeste sans `display`,
 * une icône renommée ou un service worker absent ne font échouer ni `tsc`, ni les
 * tests, ni la build elle-même. L'app continue de s'afficher dans un navigateur,
 * elle cesse seulement de pouvoir s'installer, ce qui ne se voit que sur un
 * téléphone.
 *
 * Ce contrôle lit `dist/`, pas la config : c'est ce que le navigateur recevra.
 * Un manifeste correct dans `vite.config.ts` ne prouve pas qu'il soit arrivé
 * dans la build, ni que les icônes qu'il désigne existent.
 *
 *   npm run build && node scripts/verifie-pwa.mjs
 */

import { readFileSync, existsSync, statSync } from 'node:fs';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const DIST = join(dirname(fileURLToPath(import.meta.url)), '..', 'dist');
const fautes = [];

function exige(condition, message) {
  if (!condition) fautes.push(message);
}

// 1. Le service worker. `autoUpdate` le génère à la racine de dist ; il
//    s'enregistre depuis le bundle (src/pwa/use-register-sw.ts), donc on ne
//    peut pas le chercher dans index.html.
const sw = join(DIST, 'sw.js');
exige(existsSync(sw), 'dist/sw.js est absent : la build ne produit plus de service worker.');
if (existsSync(sw)) {
  exige(
    statSync(sw).size > 500,
    `dist/sw.js ne fait que ${statSync(sw).size} octets : un service worker vide ne met rien en cache.`,
  );
}

// 2. Le manifeste, et le lien qui y mène. Sans la balise, le navigateur ne le
//    cherche pas, même s'il est bien là.
const manifeste = join(DIST, 'manifest.webmanifest');
exige(existsSync(manifeste), 'dist/manifest.webmanifest est absent.');

const index = join(DIST, 'index.html');
exige(existsSync(index), 'dist/index.html est absent.');
if (existsSync(index)) {
  exige(
    /<link[^>]+rel=["']manifest["']/.test(readFileSync(index, 'utf8')),
    'dist/index.html ne contient pas de <link rel="manifest"> : le manifeste ne sera jamais lu.',
  );
}

// 3. Le contenu du manifeste : les champs sans lesquels aucun navigateur ne
//    propose l'installation.
if (existsSync(manifeste)) {
  let m;
  try {
    m = JSON.parse(readFileSync(manifeste, 'utf8'));
  } catch (e) {
    fautes.push(`dist/manifest.webmanifest n'est pas du JSON valide : ${e.message}`);
  }

  if (m) {
    exige(typeof m.name === 'string' && m.name.length > 0, 'manifeste : `name` manquant.');
    exige(
      typeof m.short_name === 'string' && m.short_name.length > 0,
      'manifeste : `short_name` manquant, c\'est lui qui s\'affiche sous l\'icône.',
    );
    exige(typeof m.start_url === 'string', 'manifeste : `start_url` manquant.');
    exige(
      ['standalone', 'fullscreen', 'minimal-ui'].includes(m.display),
      `manifeste : \`display\` vaut ${JSON.stringify(m.display)}. Avec "browser", ou sans valeur, l'app s'ouvre dans un onglet et n'est pas installable.`,
    );

    const icones = Array.isArray(m.icons) ? m.icons : [];
    const taille = (px) => icones.some((i) => String(i.sizes || '').split(' ').includes(`${px}x${px}`));
    exige(taille(192), 'manifeste : aucune icône 192x192.');
    exige(taille(512), 'manifeste : aucune icône 512x512.');
    exige(
      icones.some((i) => String(i.purpose || '').split(' ').includes('maskable')),
      'manifeste : aucune icône `maskable`. Sans elle, Android recadre l\'icône dans un carré blanc.',
    );

    // Une icône listée mais absente du disque : le cas que seul un vrai
    // téléphone révélait, puisque la build ne vérifie pas ses propres chemins.
    for (const icone of icones) {
      const chemin = join(DIST, String(icone.src || '').replace(/^\//, ''));
      exige(
        icone.src && existsSync(chemin),
        `manifeste : l'icône ${icone.src} est annoncée mais absente de dist/.`,
      );
    }
  }
}

if (fautes.length > 0) {
  console.error('\nLa build n\'est pas installable :\n');
  for (const f of fautes) console.error(`  - ${f}`);
  console.error('');
  process.exit(1);
}

console.log('PWA : service worker, manifeste, lien et icônes présents et cohérents.');
