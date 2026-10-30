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
    // Marges latérales ici et pas dans la topbar : en paysage, l'encoche mange
    // un côté de l'écran entier, donc la barre ET le contenu doivent s'en
    // écarter. En portrait et sur desktop les insets valent zéro, rien ne bouge.
    <div className="flex h-full flex-col bg-eldir-paper pl-[env(safe-area-inset-left)] pr-[env(safe-area-inset-right)]">
      <AppTopbar />
      {/* `overflow-x-hidden` est un garde-fou : un identifiant ou un chemin
          trop long ne doit jamais rendre toute l'app scrollable de côté. Les
          blocs qui doivent défiler horizontalement (tableau de coûts, logs,
          commandes shell) portent leur propre `overflow-x-auto`. */}
      {/* La marge du bas va sur la zone de défilement, pas sur la coquille :
          posée sur la coquille elle rognerait la hauteur utile en permanence,
          alors qu'ici elle ne fait que laisser le dernier élément d'une liste
          remonter au-dessus de la barre de geste. Aucun élément de l'app n'est
          collé en bas (ni `fixed`, ni `sticky`), sinon c'est lui qui la
          porterait. */}
      <div className="min-h-0 min-w-0 flex-1 overflow-y-auto overflow-x-hidden pb-[env(safe-area-inset-bottom)]">
        <Outlet />
      </div>
    </div>
  );
}
