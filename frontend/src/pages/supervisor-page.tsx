/**
 * SupervisorPage - point d'entrée vers la session Eldir.
 *
 * La session superviseur est une session comme les autres : on la démarre
 * (ou on la reprend) puis on redirige vers l'UI de chat existante. Aucune
 * duplication de l'écran de session.
 */

import { useEffect, useRef, useState } from 'react';
import { Navigate } from 'react-router-dom';

import { useEnsureSupervisor } from '@/lib/api/queries';

export function SupervisorPage(): JSX.Element {
  const ensure = useEnsureSupervisor();
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const started = useRef(false);

  useEffect(() => {
    if (started.current) return;
    started.current = true;
    ensure
      .mutateAsync()
      .then((session) => setSessionId(session.id))
      .catch((err: unknown) =>
        setError(
          err instanceof Error ? err.message : 'Impossible de démarrer Eldir',
        ),
      );
  }, [ensure]);

  if (sessionId) return <Navigate to={`/sessions/${sessionId}`} replace />;

  return (
    <main className="flex h-full flex-col items-center justify-center gap-3 p-6 text-center">
      {error ? (
        <>
          <p className="font-mono text-xs text-eldir-red">{error}</p>
          <p className="max-w-sm font-sans text-sm text-eldir-gray">
            Eldir a besoin d&apos;un credential Claude actif. Configure-le dans
            Settings &gt; Claude puis reviens.
          </p>
        </>
      ) : (
        <div className="eldir-caps animate-pulse">réveil du superviseur…</div>
      )}
    </main>
  );
}
