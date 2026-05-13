/**
 * ProjectsPage — liste des projets Eldir + bouton "Ajouter depuis un repo".
 */

import { useMemo, useState } from 'react';

import { GitMark } from '@/components/eldir/git-mark';
import { NewRepoDialog } from '@/features/projects/new-repo-dialog';
import { ApiError } from '@/lib/api/client';
import {
  useCreateProject,
  useDeleteProject,
  useProjects,
  useRemoteRepos,
} from '@/lib/api/queries';
import type { Provider } from '@/lib/constants';
import { PROVIDERS } from '@/lib/constants';
import type { ProjectRead, RemoteRepo } from '@/lib/types/api';
import { cn } from '@/lib/utils';

export function ProjectsPage(): JSX.Element {
  const projects = useProjects();
  const [addOpen, setAddOpen] = useState(false);
  const [newRepoOpen, setNewRepoOpen] = useState(false);

  return (
    <main className="mx-auto flex max-w-5xl flex-col gap-6 p-4 md:p-8">
      <header className="flex items-end justify-between gap-3">
        <div>
          <div className="eldir-caps">Projects</div>
          <h1 className="mt-1 font-mono text-xl font-bold text-eldir-ink">
            Projets clonés
          </h1>
        </div>
        <div className="flex gap-2">
          <button
            type="button"
            onClick={() => setNewRepoOpen(true)}
            className="rounded-eldir border border-eldir-gray-3 bg-eldir-cream px-4 py-2 font-mono text-xs font-semibold uppercase tracking-caps text-eldir-ink hover:bg-eldir-cream-2"
          >
            + nouveau repo
          </button>
          <button
            type="button"
            onClick={() => setAddOpen(true)}
            className="rounded-eldir bg-eldir-orange px-4 py-2 font-mono text-xs font-semibold uppercase tracking-caps text-white hover:bg-eldir-orange/90"
          >
            + ajouter un repo
          </button>
        </div>
      </header>

      <section className="rounded-eldir border border-eldir-gray-3 bg-eldir-cream">
        {projects.isPending ? (
          <p className="px-4 py-6 font-mono text-xs text-eldir-gray">chargement…</p>
        ) : (projects.data ?? []).length === 0 ? (
          <p className="px-4 py-6 font-mono text-xs text-eldir-gray">
            Aucun projet. Ajoute-en un depuis GitHub ou Forgejo.
          </p>
        ) : (
          <ul className="divide-y divide-eldir-gray-3">
            {(projects.data ?? []).map((p) => (
              <ProjectRow key={p.id} project={p} />
            ))}
          </ul>
        )}
      </section>

      {addOpen && <AddProjectDialog onClose={() => setAddOpen(false)} />}
      {newRepoOpen && <NewRepoDialog onClose={() => setNewRepoOpen(false)} />}
    </main>
  );
}

function ProjectRow({ project }: { project: ProjectRead }): JSX.Element {
  const deleteMut = useDeleteProject();
  return (
    <li className="flex items-center justify-between gap-3 px-4 py-3">
      <div className="flex items-center gap-3">
        <GitMark provider={project.provider} size={14} className="text-eldir-gray" />
        <div>
          <div className="font-mono text-sm font-semibold text-eldir-ink">
            {project.repo_full_name}
          </div>
          <div className="mt-0.5 font-mono text-xs text-eldir-gray">
            slug: {project.slug} · branch: {project.default_branch}
          </div>
        </div>
      </div>
      <button
        type="button"
        onClick={() => {
          if (confirm(`Supprimer ${project.repo_full_name} ? Le workspace local sera détruit.`)) {
            deleteMut.mutate(project.id);
          }
        }}
        disabled={deleteMut.isPending}
        className="rounded-eldir border border-eldir-gray-3 px-3 py-2 font-mono text-xs uppercase tracking-caps text-eldir-red hover:bg-eldir-red/10 disabled:opacity-50"
      >
        supprimer
      </button>
    </li>
  );
}

function AddProjectDialog({ onClose }: { onClose: () => void }): JSX.Element {
  const [provider, setProvider] = useState<Provider>('github');
  const [filter, setFilter] = useState('');
  const repos = useRemoteRepos(provider);
  const createProject = useCreateProject();
  const [error, setError] = useState<string | null>(null);

  const filtered = useMemo(() => {
    if (!repos.data) return [];
    const q = filter.trim().toLowerCase();
    if (!q) return repos.data;
    return repos.data.filter((r) => r.full_name.toLowerCase().includes(q));
  }, [repos.data, filter]);

  const handlePick = async (repo: RemoteRepo) => {
    setError(null);
    try {
      await createProject.mutateAsync({
        provider,
        repo_full_name: repo.full_name,
      });
      onClose();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Erreur lors du clone.');
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-eldir-ink/60 p-4">
      <div className="flex max-h-[80vh] w-full max-w-2xl flex-col rounded-eldir border border-eldir-gray-3 bg-eldir-paper">
        <header className="flex items-center justify-between border-b border-eldir-gray-3 px-4 py-3">
          <div className="eldir-caps">Ajouter un repo</div>
          <button
            type="button"
            onClick={onClose}
            className="font-mono text-xs uppercase tracking-caps text-eldir-gray hover:text-eldir-ink"
          >
            fermer
          </button>
        </header>

        <div className="flex gap-2 border-b border-eldir-gray-3 px-4 py-2">
          {PROVIDERS.map((p) => (
            <button
              key={p}
              type="button"
              onClick={() => setProvider(p)}
              className={cn(
                'flex items-center gap-2 rounded-eldir border px-3 py-1.5 font-mono text-xs uppercase tracking-caps',
                provider === p
                  ? 'border-eldir-orange bg-eldir-orange/10 text-eldir-ink'
                  : 'border-eldir-gray-3 text-eldir-gray hover:text-eldir-ink',
              )}
            >
              <GitMark provider={p} size={12} className="text-current" />
              {p}
            </button>
          ))}
        </div>

        <div className="border-b border-eldir-gray-3 px-4 py-2">
          <input
            type="text"
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            placeholder="filtrer par nom (owner/repo)…"
            className="w-full rounded-eldir border border-eldir-gray-3 bg-eldir-cream px-3 py-2 font-mono text-sm text-eldir-ink focus:border-eldir-orange focus:outline-none"
          />
        </div>

        <div className="flex-1 overflow-y-auto px-4 py-2">
          {repos.isPending && (
            <p className="py-6 text-center font-mono text-xs text-eldir-gray">
              récupération des repos…
            </p>
          )}
          {repos.isError && (
            <p className="py-6 text-center font-mono text-xs text-eldir-red">
              {repos.error.message}
            </p>
          )}
          {repos.data && filtered.length === 0 && !repos.isPending && (
            <p className="py-6 text-center font-mono text-xs text-eldir-gray">
              aucun repo correspondant.
            </p>
          )}
          <ul className="divide-y divide-eldir-gray-3">
            {filtered.map((r) => (
              <li key={r.full_name} className="flex items-center justify-between gap-3 py-2">
                <div className="min-w-0">
                  <div className="truncate font-mono text-xs font-semibold text-eldir-ink">
                    {r.full_name}
                    {r.is_private && (
                      <span className="ml-2 rounded-sm bg-eldir-gold/30 px-1 text-[9px] uppercase tracking-caps text-eldir-ink-2">
                        private
                      </span>
                    )}
                  </div>
                  {r.description && (
                    <div className="truncate text-xs text-eldir-gray">
                      {r.description}
                    </div>
                  )}
                </div>
                <button
                  type="button"
                  onClick={() => handlePick(r)}
                  disabled={createProject.isPending}
                  className="rounded-eldir bg-eldir-orange px-3 py-1.5 font-mono text-xs font-semibold uppercase tracking-caps text-white hover:bg-eldir-orange/90 disabled:opacity-50"
                >
                  cloner
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
