/**
 * NewSessionDialog - sélecteur projet + bouton "lancer la session".
 */

import { useState } from 'react';
import { useNavigate } from 'react-router-dom';

import { GitMark } from '@/components/eldir/git-mark';
import { ApiError } from '@/lib/api/client';
import { useCreateSession, useProjects } from '@/lib/api/queries';
import type { ProjectRead } from '@/lib/types/api';

const ECO_MODEL = 'claude-haiku-4-5-20251001';

export function NewSessionDialog({ onClose }: { onClose: () => void }): JSX.Element {
  const navigate = useNavigate();
  const projects = useProjects();
  const createSession = useCreateSession();
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<ProjectRead | null>(null);
  const [ecoMode, setEcoMode] = useState(false);

  const launch = async (project: ProjectRead) => {
    setError(null);
    setSelected(project);
    try {
      const payload = ecoMode
        ? { project_id: project.id, model: ECO_MODEL }
        : { project_id: project.id };
      const session = await createSession.mutateAsync(payload);
      onClose();
      navigate(`/sessions/${session.id}`);
    } catch (err) {
      setSelected(null);
      setError(err instanceof ApiError ? err.message : 'Erreur création session');
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-eldir-ink/60 p-4">
      <div className="flex max-h-[80vh] w-full max-w-lg flex-col rounded-eldir border border-eldir-gray-3 bg-eldir-paper">
        <header className="flex items-center justify-between border-b border-eldir-gray-3 px-4 py-3">
          <div className="eldir-caps">Nouvelle session</div>
          <button
            type="button"
            onClick={onClose}
            className="font-mono text-xs uppercase tracking-caps text-eldir-gray hover:text-eldir-ink"
          >
            fermer
          </button>
        </header>

        <p className="border-b border-eldir-gray-3 px-4 py-3 text-sm text-eldir-ink-2">
          Choisis un projet - Eldir va instancier un agent Claude dans son
          workspace.
        </p>

        <label className="flex items-center justify-between gap-3 border-b border-eldir-gray-3 px-4 py-2.5 text-xs">
          <div>
            <div className="font-mono font-semibold uppercase tracking-caps text-eldir-ink">
              Mode économe
            </div>
            <div className="font-mono text-2xs text-eldir-gray">
              Force Haiku 4.5 (le moins cher) au lieu du modèle du template.
            </div>
          </div>
          <input
            type="checkbox"
            checked={ecoMode}
            onChange={(e) => setEcoMode(e.target.checked)}
            className="h-4 w-4 accent-eldir-orange"
          />
        </label>

        <div className="flex-1 overflow-y-auto px-2 py-2">
          {projects.isPending && (
            <p className="py-6 text-center font-mono text-xs text-eldir-gray">
              chargement…
            </p>
          )}
          {projects.data && projects.data.length === 0 && (
            <p className="py-6 text-center font-mono text-xs text-eldir-gray">
              Aucun projet. Ajoute-en un dans Projects.
            </p>
          )}
          <ul className="divide-y divide-eldir-gray-3">
            {(projects.data ?? []).map((p) => (
              <li
                key={p.id}
                className="flex items-center justify-between gap-3 px-3 py-3"
              >
                <div className="flex items-center gap-3">
                  <GitMark
                    provider={p.provider}
                    size={14}
                    className="text-eldir-gray"
                  />
                  <div>
                    <div className="font-mono text-xs font-semibold text-eldir-ink">
                      {p.repo_full_name}
                    </div>
                    <div className="font-mono text-2xs text-eldir-gray">
                      branch: {p.default_branch}
                    </div>
                  </div>
                </div>
                <button
                  type="button"
                  onClick={() => launch(p)}
                  disabled={createSession.isPending}
                  className="rounded-eldir bg-eldir-orange px-3 py-1.5 font-mono text-xs font-semibold uppercase tracking-caps text-white hover:bg-eldir-orange/90 disabled:opacity-50"
                >
                  {selected?.id === p.id ? 'démarrage…' : 'lancer'}
                </button>
              </li>
            ))}
          </ul>
        </div>

        {error && (
          <div className="border-t border-eldir-gray-3 px-4 py-2 font-mono text-xs text-eldir-red">
            {error}
          </div>
        )}
      </div>
    </div>
  );
}
