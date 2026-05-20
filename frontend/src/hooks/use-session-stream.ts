/**
 * useSessionStream - WS client pour les events live d'une session.
 *
 * Auth via query param `?token=<jwt>` (les WS browser ne supportent pas les
 * headers Authorization).
 * Reconnexion automatique avec backoff exponentiel borné.
 */

import { useEffect, useRef, useState } from 'react';

import type { SessionEvent } from '@/lib/types/api';
import { useAuthStore } from '@/lib/store/auth';

const MAX_RECONNECT_DELAY = 30_000;
const KEEPALIVE_INTERVAL = 25_000;

type ConnectionState = 'idle' | 'connecting' | 'open' | 'closed';

export interface UseSessionStreamOptions {
  enabled?: boolean;
  bufferSize?: number;
}

export interface UseSessionStreamResult {
  state: ConnectionState;
  events: SessionEvent[];
  clear: () => void;
}

export function useSessionStream(
  sessionId: string,
  { enabled = true, bufferSize = 500 }: UseSessionStreamOptions = {},
): UseSessionStreamResult {
  const token = useAuthStore((s) => s.token);
  const [events, setEvents] = useState<SessionEvent[]>([]);
  const [state, setState] = useState<ConnectionState>('idle');
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeout = useRef<number | null>(null);
  const reconnectDelay = useRef(1000);
  const keepalive = useRef<number | null>(null);

  useEffect(() => {
    if (!enabled || !sessionId || !token) {
      setState('idle');
      return undefined;
    }

    let cancelled = false;

    const connect = () => {
      if (cancelled) return;
      setState('connecting');
      const proto = window.location.protocol === 'https:' ? 'wss' : 'ws';
      const url = `${proto}://${window.location.host}/ws/sessions/${sessionId}?token=${encodeURIComponent(token)}`;
      const ws = new WebSocket(url);
      wsRef.current = ws;

      ws.onopen = () => {
        if (cancelled) return;
        setState('open');
        reconnectDelay.current = 1000;
        keepalive.current = window.setInterval(() => {
          if (ws.readyState === WebSocket.OPEN) {
            ws.send('ping');
          }
        }, KEEPALIVE_INTERVAL);
      };

      ws.onmessage = (e) => {
        try {
          const data = JSON.parse(e.data) as SessionEvent;
          setEvents((prev) => {
            const next = [...prev, data];
            return next.length > bufferSize ? next.slice(-bufferSize) : next;
          });
        } catch {
          /* ignore non-JSON */
        }
      };

      ws.onclose = () => {
        if (keepalive.current) {
          window.clearInterval(keepalive.current);
          keepalive.current = null;
        }
        if (cancelled) return;
        setState('closed');
        reconnectTimeout.current = window.setTimeout(() => {
          reconnectDelay.current = Math.min(
            reconnectDelay.current * 2,
            MAX_RECONNECT_DELAY,
          );
          connect();
        }, reconnectDelay.current);
      };

      ws.onerror = () => {
        ws.close();
      };
    };

    connect();

    return () => {
      cancelled = true;
      if (reconnectTimeout.current) {
        window.clearTimeout(reconnectTimeout.current);
        reconnectTimeout.current = null;
      }
      if (keepalive.current) {
        window.clearInterval(keepalive.current);
        keepalive.current = null;
      }
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }
    };
  }, [enabled, sessionId, token, bufferSize]);

  return {
    state,
    events,
    clear: () => setEvents([]),
  };
}
