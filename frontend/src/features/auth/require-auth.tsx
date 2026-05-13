/**
 * RequireAuth — garde de route Eldir.
 *
 * Décision en cascade :
 * 1. Si /setup/status === needs_bootstrap → redirige vers /setup-pending
 * 2. Si pas de token JWT → redirige vers /login
 * 3. Si token mais /me échoue (token expiré) → purge + /login
 * 4. Sinon → rend les children
 */

import type { ReactNode } from 'react';
import { Navigate, useLocation } from 'react-router-dom';

import { useMe, useSetupStatus } from '@/lib/api/queries';
import { useAuthStore } from '@/lib/store/auth';

export function RequireAuth({ children }: { children: ReactNode }): JSX.Element {
  const location = useLocation();
  const token = useAuthStore((s) => s.token);
  const logout = useAuthStore((s) => s.logout);
  const setupStatus = useSetupStatus();
  const me = useMe(Boolean(token));

  if (setupStatus.isPending) {
    return <FullscreenLoader label="vérification de l'installation…" />;
  }
  if (setupStatus.data?.needs_bootstrap) {
    return <Navigate to="/setup-pending" replace />;
  }

  if (!token) {
    return <Navigate to="/login" replace state={{ from: location }} />;
  }

  if (me.isPending) {
    return <FullscreenLoader label="chargement de la session…" />;
  }

  if (me.isError) {
    // Token invalide / expiré → purge et redirige
    logout();
    return <Navigate to="/login" replace />;
  }

  return <>{children}</>;
}

function FullscreenLoader({ label }: { label: string }): JSX.Element {
  return (
    <div className="flex h-full items-center justify-center bg-eldir-paper">
      <div className="eldir-caps animate-pulse">{label}</div>
    </div>
  );
}
