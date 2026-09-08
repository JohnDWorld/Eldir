/**
 * AuthedLayout - wrappe toutes les routes authentifiées avec la topbar
 * persistante et la guard `RequireAuth`. Le contenu de la route s'affiche
 * dans l'Outlet.
 */

import { Outlet } from 'react-router-dom';

import { AppTopbar } from '@/components/eldir/app-topbar';
import { RequireAuth } from '@/features/auth/require-auth';
import { useSessionNotifier } from '@/hooks/use-session-notifier';

export function AuthedLayout(): JSX.Element {
  return (
    <RequireAuth>
      <AuthedInner />
    </RequireAuth>
  );
}

function AuthedInner(): JSX.Element {
  // Hook global : surveille les transitions d'état des sessions et
  // déclenche les notifs natives quand un tour termine en arrière-plan.
  useSessionNotifier();

  return (
    <div className="flex h-full flex-col bg-eldir-paper">
      <AppTopbar />
      {/* `overflow-x-hidden` est un garde-fou : un identifiant ou un chemin
          trop long ne doit jamais rendre toute l'app scrollable de côté. Les
          blocs qui doivent défiler horizontalement (tableau de coûts, logs,
          commandes shell) portent leur propre `overflow-x-auto`. */}
      <div className="min-h-0 min-w-0 flex-1 overflow-y-auto overflow-x-hidden">
        <Outlet />
      </div>
    </div>
  );
}
