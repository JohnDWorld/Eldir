/**
 * TemplateHistory - historique versionné du template d'un projet.
 *
 * Snapshot automatique avant chaque mutation (cf. backend). Permet de
 * restaurer une version antérieure ; la restauration crée elle-même un
 * snapshot pour pouvoir défaire.
 */

import { useState } from 'react';

import { ApiError } from '@/lib/api/client';
import {
  useRestoreTemplateVersion,
  useTemplateVersions,
} from '@/lib/api/queries';
import type { TemplateVersion } from '@/lib/api/queries';

interface TemplateHistoryProps {
  projectId: string;
}

export function TemplateHistory({ projectId }: TemplateHistoryProps): JSX.Element {
  const versions = useTemplateVersions(projectId);
  const restore = useRestoreTemplateVersion(projectId);
  const [error, setError] = useState<string | null>(null);

  const handleRestore = async (v: TemplateVersion) => {
    if (
      !confirm(
        `Restaurer la version v${v.version_index} ? L'état actuel sera snapshotté avant.`,
      )
    )
      return;
    setError(null);
    try {
      await restore.mutateAsync({
        versionId: v.id,
        note: `restauration v${v.version_index}`,
      });
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Erreur lors de la restauration.');
    }
  };

  return (
    <section className="rounded-eldir border border-eldir-gray-3 bg-eldir-cream p-5">
      <header className="mb-3">
        <div className="eldir-caps">Historique</div>
        <p className="mt-1 text-xs text-eldir-ink-2">
          Une version est snapshottée avant chaque modification. La
          restauration crée elle-même un snapshot avant écrasement.
        </p>
      </header>

      {versions.isPending && (
        <p className="font-mono text-xs text-eldir-gray">chargement…</p>
      )}
      {versions.data && versions.data.length === 0 && !versions.isPending && (
        <p className="font-mono text-xs text-eldir-gray">
          Aucun snapshot encore. Sauvegarde ton template ou applique un preset
          pour créer le premier.
        </p>
      )}
      {versions.data && versions.data.length > 0 && (
        <ul className="divide-y divide-eldir-gray-3">
          {versions.data.map((v) => {
            const snap = v.snapshot as {
              skills?: unknown[];
              sub_agents?: unknown[];
            };
            const date = new Date(v.created_at).toLocaleString('fr-FR', {
              dateStyle: 'short',
              timeStyle: 'short',
            });
            return (
              <li
                key={v.id}
                className="flex items-center justify-between gap-3 py-2"
              >
                <div className="min-w-0">
                  <div className="font-mono text-xs font-semibold text-eldir-ink">
                    v{v.version_index} · {date}
                  </div>
                  <div className="mt-0.5 font-mono text-2xs text-eldir-gray">
                    {(snap.skills ?? []).length} skill(s) ·{' '}
                    {(snap.sub_agents ?? []).length} agent(s)
                    {v.note && ` · ${v.note}`}
                  </div>
                </div>
                <button
                  type="button"
                  onClick={() => handleRestore(v)}
                  disabled={restore.isPending}
                  className="rounded-eldir border border-eldir-gray-3 px-3 py-1.5 font-mono text-xs uppercase tracking-caps text-eldir-ink hover:bg-eldir-cream-2 disabled:opacity-50"
                >
                  {restore.isPending ? 'restauration…' : 'restaurer'}
                </button>
              </li>
            );
          })}
        </ul>
      )}

      {error && (
        <div className="mt-3 rounded-eldir border border-eldir-red bg-eldir-red/10 px-3 py-2 font-mono text-xs text-eldir-red">
          {error}
        </div>
      )}
    </section>
  );
}
