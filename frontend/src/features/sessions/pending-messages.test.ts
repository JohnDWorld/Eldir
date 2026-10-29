// Le champ de saisie ne se verrouille plus pendant un tour : écrire à un
// agent qui travaille est le geste qui le débloque. Les messages acceptés
// s'affichent donc en attente, et disparaissent quand le fil les porte.
import { describe, expect, it } from 'vitest';

import { messagesEnAttente } from './pending-messages';

describe('messagesEnAttente', () => {
  it('garde un message tant que le fil ne le porte pas', () => {
    expect(messagesEnAttente(['salut'], [])).toEqual(['salut']);
  });

  it("retire celui que le fil a repris, pour ne pas l'afficher deux fois", () => {
    const resultat = messagesEnAttente(
      ['salut', 'et ensuite ?'],
      [{ type: 'user_message', data: { text: 'salut' } }],
    );
    expect(resultat).toEqual(['et ensuite ?']);
  });

  it('ignore les events qui ne sont pas des messages', () => {
    const resultat = messagesEnAttente(
      ['salut'],
      [{ type: 'tool_use', data: { text: 'salut' } }],
    );
    expect(resultat).toEqual(['salut']);
  });

  it('garde les deux copies quand John envoie deux fois le même texte', () => {
    // Un seul event remonté ne doit retirer qu'une seule des deux copies :
    // sinon le second « ok » disparaîtrait de l'écran alors qu'il attend.
    const resultat = messagesEnAttente(
      ['ok', 'ok'],
      [{ type: 'user_message', data: { text: 'ok' } }],
    );
    expect(resultat).toEqual(['ok']);
  });
});
