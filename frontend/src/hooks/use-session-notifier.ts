/**
 * useSessionNotifier - notifs natives quand un tour Claude se termine
 * pendant qu'on n'est pas sur la page de la session.
 *
 * V1 : pas de Web Push (pas de VAPID/backend), juste l'API Notification
 * couplée au polling régulier de useSessions(). Latence ~5s.
 *
 * Comportement :
 *  - watch les transitions "thinking" ou "tool_use" → "idle" sur les
 *    sessions non-system de l'utilisateur
 *  - si la session concernée n'est PAS dans l'URL actuelle, déclenche
 *    une Notification cliquable qui redirige sur /sessions/{id}
 *  - silencieux si la permission n'est pas accordée (le user doit cliquer
 *    "Activer les notifs" depuis l'UI)
 */

import { useEffect, useRef } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';

import { useProjects, useSessions } from '@/lib/api/queries';
import type { SessionRead } from '@/lib/types/api';

const BUSY_STATES = new Set(['thinking', 'tool_use']);

export function useSessionNotifier(): void {
  const sessions = useSessions();
  const projects = useProjects();
  const navigate = useNavigate();
  const location = useLocation();
  const prevStateBySession = useRef<Map<string, string>>(new Map());

  useEffect(() => {
    const data = sessions.data;
    if (!data) return;

    const prev = prevStateBySession.current;
    const next = new Map<string, string>();

    for (const s of data) {
      next.set(s.id, s.state);
      // On ne notifie que pour les sessions utilisateur (pas les systèmes)
      if (s.is_system) continue;
      const previousState = prev.get(s.id);
      if (
        previousState !== undefined &&
        BUSY_STATES.has(previousState) &&
        s.state === 'idle'
      ) {
        // Transition détectée : tour terminé.
        // On ne notifie pas si l'utilisateur EST sur la page de la session.
        if (location.pathname === `/sessions/${s.id}`) continue;
        notify(s, projects.data ?? [], (sid) => navigate(`/sessions/${sid}`));
      }
    }

    prevStateBySession.current = next;
  }, [sessions.data, projects.data, location.pathname, navigate]);
}

function notify(
  session: SessionRead,
  projects: { id: string; name: string }[],
  onClick: (sessionId: string) => void,
): void {
  if (typeof Notification === 'undefined') return;
  if (Notification.permission !== 'granted') return;

  const project = projects.find((p) => p.id === session.project_id);
  const projectName = project?.name ?? 'projet';
  const title = `Claude · ${projectName}`;
  const body = session.summary
    ? session.summary.slice(0, 120)
    : 'Tour terminé.';

  try {
    const n = new Notification(title, {
      body,
      tag: `eldir-session-${session.id}`,
      icon: '/icons/icon-192.png',
      badge: '/icons/icon-192.png',
    });
    n.onclick = () => {
      window.focus();
      onClick(session.id);
      n.close();
    };
  } catch {
    /* certains navigateurs (iOS Safari) restreignent les Notification hors SW */
  }
}

/**
 * État de la permission de notification, pour pilotage UI.
 * Retourne 'unsupported' si l'API n'existe pas.
 */
export type NotificationPermissionState =
  | 'unsupported'
  | 'default'
  | 'granted'
  | 'denied';

export function getNotificationPermission(): NotificationPermissionState {
  if (typeof Notification === 'undefined') return 'unsupported';
  return Notification.permission as NotificationPermissionState;
}

export async function requestNotificationPermission(): Promise<NotificationPermissionState> {
  if (typeof Notification === 'undefined') return 'unsupported';
  if (Notification.permission === 'granted') return 'granted';
  if (Notification.permission === 'denied') return 'denied';
  const result = await Notification.requestPermission();
  return result as NotificationPermissionState;
}
