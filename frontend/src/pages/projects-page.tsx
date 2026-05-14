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
import type { ProjectRead } from '@/lib/types/api';
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

type CloneFailure = { full_name: string; message: string };

function AddProjectDialog({ onClose }: { onClose: () => void }): JSX.Element {
  const [provider, setProvider] = useState<Provider>('github');
  const [filter, setFilter] = useState('');
  const repos = useRemoteRepos(provider);
  const createProject = useCreateProject();
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [submitting, setSubmitting] = useState(false);
  const [progress, setProgress] = useState<{ done: number; total: number } | null>(null);
  const [failures, setFailures] = useState<CloneFailure[]>([]);

  const filtered = useMemo(() => {
    if (!repos.data) return [];
    const q = filter.trim().toLowerCase();
    if (!q) return repos.data;
    return repos.data.filter((r) => r.full_name.toLowerCase().includes(q));
  }, [repos.data, filter]);

  const toggle = (full_name: string) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(full_name)) next.delete(full_name);
      else next.add(full_name);
      return next;
    });
  };

  const allFilteredSelected =
    filtered.length > 0 && filtered.every((r) => selected.has(r.full_name));
  const toggleAllFiltered = () => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (allFilteredSelected) {
        filtered.forEach((r) => next.delete(r.full_name));
      } else {
        filtered.forEach((r) => next.add(r.full_name));
      }
      return next;
    });
  };

  // Reset la sélection quand on change de provider (les full_name ne se mélangent pas)
  const handleProviderChange = (p: Provider) => {
    setProvider(p);
    setSelected(new Set());
    setFailures([]);
  };

  const handleValidate = async () => {
    if (selected.size === 0) return;
    setSubmitting(true);
    setFailures([]);
    const targets = Array.from(selected);
    setProgress({ done: 0, total: targets.length });
    const errors: CloneFailure[] = [];
    // Séquentiel : un worktree à la fois pour éviter la pression I/O et les collisions de slug.
    for (let i = 0; i < targets.length; i++) {
      const full_name = targets[i]!;
      try {
        await createProject.mutateAsync({ provider, repo_full_name: full_name });
      } catch (err) {
        errors.push({
          full_name,
          message: err instanceof ApiError ? err.message : 'Erreur lors du clone.',
        });
      }
      setProgress({ done: i + 1, total: targets.length });
    }
    setSubmitting(false);
    if (errors.length === 0) {
      onClose();
    } else {
      setFailures(errors);
      // Désélectionne ceux qui ont réussi
      setSelected(new Set(errors.map((e) => e.full_name)));
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-eldir-ink/60 p-4">
      <div className="flex max-h-[80vh] w-full max-w-2xl flex-col rounded-eldir border border-eldir-gray-3 bg-eldir-paper">
        <header className="flex items-center justify-between border-b border-eldir-gray-3 px-4 py-3">
          <div className="eldir-caps">Ajouter des repos</div>
          <button
            type="button"
            onClick={onClose}
            disabled={submitting}
            className="font-mono text-xs uppercase tracking-caps text-eldir-gray hover:text-eldir-ink disabled:opacity-50"
          >
            fermer
          </button>
        </header>

        <div className="flex gap-2 border-b border-eldir-gray-3 px-4 py-2">
          {PROVIDERS.map((p) => (
            <button
              key={p}
              type="button"
              onClick={() => handleProviderChange(p)}
              disabled={submitting}
              className={cn(
                'flex items-center gap-2 rounded-eldir border px-3 py-1.5 font-mono text-xs uppercase tracking-caps disabled:opacity-50',
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

        <div className="flex items-center gap-2 border-b border-eldir-gray-3 px-4 py-2">
          <input
            type="text"
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            placeholder="filtrer par nom (owner/repo)…"
            className="flex-1 rounded-eldir border border-eldir-gray-3 bg-eldir-cream px-3 py-2 font-mono text-sm text-eldir-ink focus:border-eldir-orange focus:outline-none"
          />
          {filtered.length > 0 && (
            <button
              type="button"
              onClick={toggleAllFiltered}
              disabled={submitting}
              className="rounded-eldir border border-eldir-gray-3 px-3 py-2 font-mono text-xs uppercase tracking-caps text-eldir-gray hover:text-eldir-ink disabled:opacity-50"
            >
              {allFilteredSelected ? 'tout désél.' : 'tout sél.'}
            </button>
          )}
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
            {filtered.map((r) => {
              const checked = selected.has(r.full_name);
              const failure = failures.find((f) => f.full_name === r.full_name);
              return (
                <li key={r.full_name}>
                  <label
                    className={cn(
                      'flex cursor-pointer items-center gap-3 py-2',
                      submitting && 'cursor-not-allowed opacity-60',
                    )}
                  >
                    <input
                      type="checkbox"
                      checked={checked}
                      onChange={() => toggle(r.full_name)}
                      disabled={submitting}
                      className="h-4 w-4 accent-eldir-orange"
                    />
                    <div className="min-w-0 flex-1">
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
                      {failure && (
                        <div className="mt-1 font-mono text-[11px] text-eldir-red">
                          {failure.message}
                        </div>
                      )}
                    </div>
                  </label>
                </li>
              );
            })}
          </ul>
        </div>

        <footer className="flex items-center justify-between gap-3 border-t border-eldir-gray-3 px-4 py-3">
          <div className="font-mono text-xs text-eldir-gray">
            {submitting && progress
              ? `clonage ${progress.done}/${progress.total}…`
              : `${selected.size} sélectionné${selected.size > 1 ? 's' : ''}`}
            {failures.length > 0 && !submitting && (
              <span className="ml-2 text-eldir-red">
                ({failures.length} échec{failures.length > 1 ? 's' : ''})
              </span>
            )}
          </div>
          <div className="flex gap-2">
            <button
              type="button"
              onClick={onClose}
              disabled={submitting}
              className="rounded-eldir border border-eldir-gray-3 px-3 py-2 font-mono text-xs uppercase tracking-caps text-eldir-gray hover:text-eldir-ink disabled:opacity-50"
            >
              annuler
            </button>
            <button
              type="button"
              onClick={handleValidate}
              disabled={selected.size === 0 || submitting}
              className="rounded-eldir bg-eldir-orange px-4 py-2 font-mono text-xs font-semibold uppercase tracking-caps text-white hover:bg-eldir-orange/90 disabled:opacity-50"
            >
              {submitting
                ? 'clonage…'
                : `valider${selected.size > 0 ? ` (${selected.size})` : ''}`}
            </button>
          </div>
        </footer>
      </div>
    </div>
  );
}
