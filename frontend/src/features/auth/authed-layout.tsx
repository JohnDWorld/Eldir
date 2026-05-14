/**
 * AuthedLayout — wrappe toutes les routes authentifiées avec la topbar
 * persistante et la guard `RequireAuth`. Le contenu de la route s'affiche
 * dans l'Outlet.
 */

import { Outlet } from 'react-router-dom';

import { AppTopbar } from '@/components/eldir/app-topbar';
import { RequireAuth } from '@/features/auth/require-auth';

export function AuthedLayout(): JSX.Element {
  return (
    <RequireAuth>
      <div className="flex h-full flex-col bg-eldir-paper">
        <AppTopbar />
        <div className="min-h-0 flex-1 overflow-auto">
          <Outlet />
        </div>
      </div>
    </RequireAuth>
  );
}
