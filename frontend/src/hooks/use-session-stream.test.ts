import { act, cleanup, renderHook } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { useAuthStore } from '@/lib/store/auth';

import { useSessionStream } from './use-session-stream';

/**
 * WebSocket de test. Le serveur accepte AVANT d'authentifier, pour que le
 * client reçoive le code et le motif d'un refus : `onopen` part donc même
 * pour un jeton qui sera refusé une milliseconde plus tard.
 */
class FauxWebSocket {
  static readonly OPEN = 1;
  static instances: FauxWebSocket[] = [];

  readyState = 0;
  onopen: (() => void) | null = null;
  onmessage: ((e: { data: string }) => void) | null = null;
  onclose: (() => void) | null = null;
  onerror: (() => void) | null = null;

  constructor(readonly url: string) {
    FauxWebSocket.instances.push(this);
  }

  send() {}

  close() {
    if (this.readyState === 3) return;
    this.readyState = 3;
    this.onclose?.();
  }
}

const dernier = (): FauxWebSocket => {
  const ws = FauxWebSocket.instances.at(-1);
  if (!ws) throw new Error("aucun WebSocket n'a été ouvert");
  return ws;
};

/** Le serveur accepte, puis ferme aussitôt : c'est un jeton refusé. */
const accepterPuisRefuser = () =>
  act(() => {
    const ws = dernier();
    ws.readyState = FauxWebSocket.OPEN;
    ws.onopen?.();
    ws.close();
  });

const attendre = (ms: number) =>
  act(() => {
    vi.advanceTimersByTime(ms);
  });

describe('useSessionStream, reconnexion', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    FauxWebSocket.instances = [];
    vi.stubGlobal('WebSocket', FauxWebSocket);
    useAuthStore.setState({ token: 'jeton-de-test' });
  });

  afterEach(() => {
    // Démonter avant de toucher au store, sinon le changement de jeton re-rend
    // le hook hors de `act`.
    cleanup();
    vi.useRealTimers();
    vi.unstubAllGlobals();
    useAuthStore.setState({ token: null });
  });

  it('espace de plus en plus les tentatives quand le serveur accepte puis refuse', () => {
    renderHook(() => useSessionStream('session-1'));
    expect(FauxWebSocket.instances).toHaveLength(1);

    // Sans cela le délai restait collé à une seconde : une tentative par
    // seconde, indéfiniment, avec un indicateur « ouvert » qui clignote.
    const paliers: [attenteAvant: number, tentatives: number][] = [
      [1000, 2],
      [2000, 3],
      [4000, 4],
      [8000, 5],
      [16000, 6],
      // Le palier se plafonne ici : une boucle de reconnexion indéfinie sur un
      // jeton refusé n'est acceptable que parce qu'elle est bornée. Sans le
      // plafond, l'attente suivante serait de 32 s.
      [30000, 7],
      // Et il reste plafonné : il ne redouble pas une fois atteint.
      [30000, 8],
    ];
    for (const [attenteAvant, tentatives] of paliers) {
      accepterPuisRefuser();
      attendre(attenteAvant - 1);
      expect(FauxWebSocket.instances).toHaveLength(tentatives - 1);
      attendre(1);
      expect(FauxWebSocket.instances).toHaveLength(tentatives);
    }
  });

  it('revient à une seconde dès que le serveur envoie vraiment quelque chose', () => {
    renderHook(() => useSessionStream('session-1'));
    accepterPuisRefuser();
    attendre(1000);
    accepterPuisRefuser();
    attendre(2000);
    expect(FauxWebSocket.instances).toHaveLength(3);

    // Cette connexion-ci est vivante : une trame arrive, puis le réseau tombe.
    act(() => {
      const ws = dernier();
      ws.readyState = FauxWebSocket.OPEN;
      ws.onopen?.();
      ws.onmessage?.({ data: JSON.stringify({ type: 'text' }) });
      ws.close();
    });
    attendre(999);
    expect(FauxWebSocket.instances).toHaveLength(3);
    attendre(1);
    expect(FauxWebSocket.instances).toHaveLength(4);
  });

  it("annonce « ouvert » dès l'ouverture, avant toute trame", () => {
    const { result } = renderHook(() => useSessionStream('session-1'));
    act(() => {
      const ws = dernier();
      ws.readyState = FauxWebSocket.OPEN;
      ws.onopen?.();
    });
    expect(result.current.state).toBe('open');
  });
});
