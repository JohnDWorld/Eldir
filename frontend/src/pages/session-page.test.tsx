/**
 * Le fil d'une session : qui a parlé.
 *
 * Avec deux Eldir possibles (le superviseur interne et un agent extérieur), le fil
 * doit dire lequel a donné une consigne, et ne jamais la faire passer pour une
 * demande de John. Ces tests rendent le vrai `ChatStream` avec de vrais events.
 */

import { render, screen } from '@testing-library/react';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import type { ComponentProps } from 'react';
import { describe, expect, it } from 'vitest';

import {
  MESSAGE_ORIGIN_AGENT_PREFIX,
  MESSAGE_ORIGIN_ELDIR,
  MESSAGE_ORIGIN_USER,
} from '@/lib/constants';
import { ChatStream } from '@/pages/session-page';

type Evenements = ComponentProps<typeof ChatStream>['events'];

/** Un `user_message`. `origin` omis veut dire : champ absent, comme avant son ajout. */
function message(texte: string, origin?: unknown, cle = texte): Evenements[number] {
  const data: Record<string, unknown> = { text: texte };
  if (origin !== undefined) data.origin = origin;
  return { key: cle, type: 'user_message', timestamp: '2026-10-30T10:00:00Z', data };
}

function rend(...events: Evenements): void {
  render(<ChatStream events={events} />);
}

/** Les libellés d'encart d'Eldir : John n'en porte aucun, c'est sa bulle. */
const ENCART = /Eldir ·|agent|origine/;

describe('ChatStream - l’auteur d’un message', () => {
  it('une consigne d’agent porte le nom de son jeton', () => {
    rend(message('Ajoute un test', 'agent:eldir du village'));
    expect(screen.getByText('agent « eldir du village »')).toBeInTheDocument();
    expect(screen.getByText('Ajoute un test')).toBeInTheDocument();
  });

  it('deux agents se lisent différemment, et ni l’un ni l’autre n’est Eldir', () => {
    rend(
      message('Un', 'agent:eldir du village'),
      message('Deux', 'agent:assistant de bureau'),
      message('Trois', 'eldir'),
    );
    expect(screen.getByText('agent « eldir du village »')).toBeInTheDocument();
    expect(screen.getByText('agent « assistant de bureau »')).toBeInTheDocument();
    expect(screen.getAllByText('Eldir · automatique')).toHaveLength(1);
  });

  it('le superviseur interne reste « Eldir · automatique »', () => {
    rend(message('Ping de fin de tour', 'eldir'));
    expect(screen.getByText('Eldir · automatique')).toBeInTheDocument();
  });

  it.each([
    ['sans origine, comme avant l’ajout du champ', undefined],
    ['user', 'user'],
  ])('un message de John (%s) n’a pas d’encart', (_cas, origin) => {
    rend(message('Fais ça', origin));
    expect(screen.getByText('Fais ça')).toBeInTheDocument();
    expect(screen.queryByText(ENCART)).toBeNull();
  });

  it('une origine inconnue n’est pas John, et se lit', () => {
    rend(message('Depuis ailleurs', 'webhook'));
    expect(screen.getByText('origine « webhook »')).toBeInTheDocument();
  });

  it('une origine qui n’est pas du texte n’est pas John non plus', () => {
    rend(message('Étrange', 42));
    expect(screen.getByText('origine inconnue')).toBeInTheDocument();
  });

  it('un agent au libellé vide se lit quand même', () => {
    rend(message('Anonyme', 'agent:'));
    expect(screen.getByText('agent sans nom')).toBeInTheDocument();
  });
});

describe('les origines de message, miroir du backend', () => {
  // Vitest fournit `__dirname` même en ESM (cf. no-horizontal-scroll.test.ts).
  // eslint-disable-next-line no-undef
  const RACINE = join(__dirname, '../../..');
  const constantes = readFileSync(join(RACINE, 'backend/app/core/constants.py'), 'utf-8');
  const miroir = {
    MESSAGE_ORIGIN_USER,
    MESSAGE_ORIGIN_ELDIR,
    MESSAGE_ORIGIN_AGENT_PREFIX,
  };

  it.each(Object.entries(miroir))('%s est ce que le backend écrit', (nom, valeur) => {
    const ecrit = new RegExp(`^${nom}: Final\\[str\\] = "([^"]*)"$`, 'm').exec(constantes);
    expect(ecrit?.[1]).toBe(valeur);
  });

  it('le backend n’a pas d’origine que le frontend ne connaisse pas', () => {
    const noms = [...constantes.matchAll(/^(MESSAGE_ORIGIN_\w+): Final/gm)].map((m) => m[1]);
    expect(noms.sort()).toEqual(Object.keys(miroir).sort());
  });

  it('la CI du frontend se lance quand ce fichier change', () => {
    // Sans cela, une PR qui ne change que les constantes du backend est verte sans
    // que les tests ci-dessus aient tourné.
    const workflow = readFileSync(join(RACINE, '.github/workflows/frontend.yml'), 'utf-8');
    const lignes = workflow.match(/^\s+- 'backend\/app\/core\/constants\.py'$/gm);
    // Une fois pour `pull_request`, une fois pour `push`.
    expect(lignes).toHaveLength(2);
  });
});
