/**
 * ProjectsPage - liste des projets Eldir + bouton "Ajouter depuis un repo".
 */

import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';

import { GitMark } from '@/components/eldir/git-mark';
import { GenerateTemplateDialog } from '@/features/projects/generate-template-dialog';
import { NewRepoDialog } from '@/features/projects/new-repo-dialog';
import { ApiError } from '@/lib/api/client';
import {
  useCreateProject,
  useDeleteProject,
  useGenerateMissingTemplates,
  useProjects,
  useRemoteRepos,
  useSyncAllRepos,
  useSyncProject,
  useTemplateBatchState,
} from '@/lib/api/queries';
import type {
  ProjectSyncResult,
  RepoSyncItem,
  TemplateBatchItem,
} from '@/lib/api/queries';
import type { Provider } from '@/lib/constants';
import { PROVIDERS } from '@/lib/constants';
import type { ProjectRead } from '@/lib/types/api';
import { cn } from '@/lib/utils';

export function ProjectsPage(): JSX.Element {
  const projects = useProjects();
  const syncAll = useSyncAllRepos();
  const generateMissing = useGenerateMissingTemplates();
  const batch = useTemplateBatchState();
  const [syncReport, setSyncReport] = useState<RepoSyncItem[] | null>(null);
  const [batchError, setBatchError] = useState<string | null>(null);
  const [addOpen, setAddOpen] = useState(false);
  const [newRepoOpen, setNewRepoOpen] = useState(false);
  // Quand UN seul projet vient d'être cloné via le dialog, on propose
  // immédiatement la génération automatique de son Mission Template.
  // Si plusieurs ont été clonés en série, on n'embête pas l'utilisateur
  // - il fera le tour des projets et générera depuis Template > Générer.
  const [pendingClones, setPendingClones] = useState<
    { id: string; name: string }[]
  >([]);
  const [generateForProject, setGenerateForProject] = useState<{
    id: string;
    name: string;
  } | null>(null);

  const nbProjets = (projects.data ?? []).length;
  // Chaque template appliqué par le lot change l'indicateur d'un projet :
  // on rafraîchit la liste à chaque avancement plutôt qu'en boucle.
  const lotAvancement = (batch.data?.items ?? []).filter(
    (i) => i.state === 'done' || i.state === 'error',
  ).length;
  useEffect(() => {
    if (lotAvancement > 0) void projects.refetch();
    // `projects` est stable côté TanStack Query, seul l'avancement compte.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [lotAvancement]);

  const handleSyncAll = async () => {
    setSyncReport(null);
    setBatchError(null);
    try {
      const { items } = await syncAll.mutateAsync();
      setSyncReport(items);
    } catch (err) {
      setBatchError(
        err instanceof ApiError ? err.message : 'Erreur pendant la synchro.',
      );
    }
  };

  const handleGenerateMissing = async () => {
    if (
      !confirm(
        `Générer le Mission Template des repos qui n'en ont pas ?\n\n` +
          `Un tour Claude par repo, enchaînés un par un, facturés comme ` +
          `n'importe quelle session. Les repos déjà configurés sont sautés, ` +
          `et le template généré est appliqué directement (la version ` +
          `précédente reste dans l'historique).`,
      )
    ) {
      return;
    }
    setSyncReport(null);
    setBatchError(null);
    try {
      await generateMissing.mutateAsync();
    } catch (err) {
      setBatchError(
        err instanceof ApiError ? err.message : 'Impossible de lancer le lot.',
      );
    }
  };

  return (
    <main className="mx-auto flex max-w-5xl flex-col gap-6 p-4 md:p-8">
      <header className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div className="min-w-0">
          <div className="eldir-caps">Projects</div>
          <h1 className="mt-1 font-mono text-xl font-bold text-eldir-ink">
            Projets clonés
          </h1>
        </div>
        <div className="flex flex-wrap gap-2">
          {nbProjets > 0 && (
            <>
              <button
                type="button"
                onClick={handleSyncAll}
                disabled={syncAll.isPending}
                className="min-h-11 rounded-eldir border border-eldir-gray-3 bg-eldir-cream px-4 py-2 font-mono text-xs font-semibold uppercase tracking-caps text-eldir-ink hover:bg-eldir-cream-2 disabled:opacity-50"
                title="Fetch et fast-forward de tous les repos clonés"
              >
                {syncAll.isPending ? 'synchro…' : '↻ sync all'}
              </button>
              <button
                type="button"
                onClick={handleGenerateMissing}
                disabled={generateMissing.isPending || batch.data?.running === true}
                className="min-h-11 rounded-eldir border border-eldir-gold bg-eldir-gold/10 px-4 py-2 font-mono text-xs font-semibold uppercase tracking-caps text-eldir-ink hover:bg-eldir-gold/20 disabled:opacity-50"
                title="Génère et applique le Mission Template des repos qui n'en ont pas"
              >
                {batch.data?.running ? 'génération…' : '✨ templates manquants'}
              </button>
            </>
          )}
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

      {batchError && (
        <div className="rounded-eldir border border-eldir-red bg-eldir-red/10 px-3 py-2 font-mono text-xs text-eldir-red">
          {batchError}
        </div>
      )}

      {syncReport && <SyncReport items={syncReport} />}

      {batch.data && batch.data.items.length > 0 && (
        <TemplateBatchReport
          running={batch.data.running}
          items={batch.data.items}
        />
      )}
      {batch.data && !batch.data.running && batch.data.items.length === 0 && (
        <div className="rounded-eldir border border-eldir-gray-3 bg-eldir-cream px-3 py-2 font-mono text-xs text-eldir-gray">
          Tous les repos ont déjà un Mission Template : rien à générer.
        </div>
      )}

      <section className="rounded-eldir border border-eldir-gray-3 bg-eldir-cream">
        {projects.isPending ? (
          <p className="px-4 py-6 font-mono text-xs text-eldir-gray">chargement…</p>
        ) : (projects.data ?? []).length === 0 ? (
          <div className="flex flex-col items-center gap-3 px-4 py-10 text-center">
            <span className="text-3xl text-eldir-gray-2" aria-hidden="true">
              ⌥
            </span>
            <div className="font-mono text-sm font-semibold text-eldir-ink">
              Aucun projet pour l'instant
            </div>
            <p className="max-w-md text-xs text-eldir-ink-2">
              Connecte GitHub ou Forgejo dans{' '}
              <a href="/settings/git" className="text-eldir-orange underline">
                Settings → Git
              </a>{' '}
              puis ajoute un repo existant ou crées-en un nouveau.
            </p>
            <div className="mt-1 flex gap-2">
              <button
                type="button"
                onClick={() => setAddOpen(true)}
                className="rounded-eldir bg-eldir-orange px-4 py-2 font-mono text-xs font-semibold uppercase tracking-caps text-white hover:bg-eldir-orange/90"
              >
                + ajouter un repo
              </button>
              <button
                type="button"
                onClick={() => setNewRepoOpen(true)}
                className="rounded-eldir border border-eldir-gray-3 bg-eldir-paper px-4 py-2 font-mono text-xs font-semibold uppercase tracking-caps text-eldir-ink hover:bg-eldir-cream-2"
              >
                + nouveau repo
              </button>
            </div>
          </div>
        ) : (
          <ul className="divide-y divide-eldir-gray-3">
            {(projects.data ?? []).map((p) => (
              <ProjectRow key={p.id} project={p} />
            ))}
          </ul>
        )}
      </section>

      {addOpen && (
        <AddProjectDialog
          onClose={() => {
            setAddOpen(false);
            // Si exactement 1 projet vient d'être cloné, propose la génération
            if (pendingClones.length === 1) {
              setGenerateForProject(pendingClones[0]!);
            }
            setPendingClones([]);
          }}
          onProjectCreated={(p) =>
            setPendingClones((prev) => [...prev, p])
          }
        />
      )}
      {generateForProject && (
        <PostCloneOfferDialog
          projectId={generateForProject.id}
          projectName={generateForProject.name}
          onClose={() => setGenerateForProject(null)}
        />
      )}
      {newRepoOpen && <NewRepoDialog onClose={() => setNewRepoOpen(false)} />}
    </main>
  );
}

/**
 * Dit d'un coup d'œil si le repo a un Mission Template. Sans template, une
 * session démarre avec le prompt par défaut : elle ne connaît ni la stack ni
 * les conventions du projet.
 */
function TemplateBadge({ filled }: { filled: boolean }): JSX.Element {
  return (
    <span
      title={
        filled
          ? 'Mission Template configuré'
          : 'Aucun Mission Template : les sessions partiront avec le prompt par défaut'
      }
      className={cn(
        'shrink-0 rounded-eldir border px-1.5 py-0.5 font-mono text-2xs uppercase tracking-caps',
        filled
          ? 'border-eldir-green text-eldir-green'
          : 'border-eldir-gold bg-eldir-gold/10 text-eldir-ink-2',
      )}
    >
      {filled ? '✓ template' : '○ sans template'}
    </span>
  );
}

/** Résumé d'un « sync all » : une ligne par repo, l'essentiel d'abord. */
function SyncReport({ items }: { items: RepoSyncItem[] }): JSX.Element {
  const bouges = items.filter((i) => i.fast_forwarded);
  const rates = items.filter((i) => i.error);
  return (
    <div className="rounded-eldir border border-eldir-gray-3 bg-eldir-cream px-3 py-2">
      <div className="font-mono text-xs text-eldir-ink">
        {items.length} repo(s) synchronisé(s) · {bouges.length} mis à jour ·{' '}
        {rates.length} en erreur
      </div>
      {(bouges.length > 0 || rates.length > 0) && (
        <ul className="mt-2 flex flex-col gap-1">
          {bouges.map((i) => (
            <li key={i.project_id} className="font-mono text-2xs text-eldir-green">
              ↓ {i.project_name} · {i.pulled} commit(s) récupéré(s)
            </li>
          ))}
          {rates.map((i) => (
            <li key={i.project_id} className="font-mono text-2xs text-eldir-red">
              ✕ {i.project_name} · {i.error}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

/** Avancement du lot de génération, une ligne par repo. */
function TemplateBatchReport({
  running,
  items,
}: {
  running: boolean;
  items: TemplateBatchItem[];
}): JSX.Element {
  const finis = items.filter((i) => i.state === 'done' || i.state === 'error');
  const tone: Record<TemplateBatchItem['state'], string> = {
    pending: 'text-eldir-gray',
    running: 'text-eldir-orange',
    done: 'text-eldir-green',
    error: 'text-eldir-red',
  };
  const mark: Record<TemplateBatchItem['state'], string> = {
    pending: '·',
    running: '⋯',
    done: '✓',
    error: '✕',
  };
  return (
    <div className="rounded-eldir border border-eldir-gold bg-eldir-gold/5 px-3 py-2">
      <div className="font-mono text-xs text-eldir-ink">
        {running ? (
          <span className="animate-pulse">
            Génération des templates · {finis.length}/{items.length}
          </span>
        ) : (
          <>Génération terminée · {finis.length}/{items.length}</>
        )}
      </div>
      <ul className="mt-2 flex flex-col gap-1">
        {items.map((i) => (
          <li
            key={i.project_id}
            className={cn('min-w-0 font-mono text-2xs', tone[i.state])}
          >
            {mark[i.state]} {i.project_name}
            {i.detail && <span className="text-eldir-gray"> · {i.detail}</span>}
            {i.session_id && i.state !== 'pending' && (
              <Link
                to={`/sessions/${i.session_id}`}
                className="ml-2 text-eldir-orange hover:underline"
              >
                voir la session →
              </Link>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}

function ProjectRow({ project }: { project: ProjectRead }): JSX.Element {
  const deleteMut = useDeleteProject();
  const syncMut = useSyncProject();
  const [syncFeedback, setSyncFeedback] = useState<
    { kind: 'success' | 'error'; text: string } | null
  >(null);

  const handleSync = async () => {
    setSyncFeedback(null);
    try {
      const result = await syncMut.mutateAsync(project.id);
      setSyncFeedback({ kind: 'success', text: formatSyncResult(result) });
    } catch (err) {
      setSyncFeedback({
        kind: 'error',
        text: err instanceof ApiError ? err.message : 'Échec sync.',
      });
    }
  };

  return (
    <li className="flex flex-col gap-1 px-4 py-3">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between sm:gap-3">
        <div className="flex min-w-0 items-start gap-3">
          <GitMark
            provider={project.provider}
            size={14}
            className="mt-0.5 shrink-0 text-eldir-gray"
          />
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <span className="break-all font-mono text-sm font-semibold text-eldir-ink">
                {project.repo_full_name}
              </span>
              <TemplateBadge filled={project.has_template} />
            </div>
            <div className="mt-0.5 break-all font-mono text-xs text-eldir-gray">
              slug: {project.slug} · branch: {project.default_branch}
            </div>
          </div>
        </div>
        <div className="flex flex-wrap gap-2 sm:shrink-0">
          <Link
            to={`/projects/${project.id}/template`}
            className="inline-flex min-h-11 items-center rounded-eldir border border-eldir-gray-3 px-3 font-mono text-xs uppercase leading-none tracking-caps text-eldir-ink hover:bg-eldir-cream-2"
          >
            template
          </Link>
          <button
            type="button"
            onClick={handleSync}
            disabled={syncMut.isPending}
            className="min-h-11 rounded-eldir border border-eldir-gray-3 px-3 font-mono text-xs uppercase tracking-caps text-eldir-ink hover:bg-eldir-cream-2 disabled:opacity-50"
          >
            {syncMut.isPending ? 'sync…' : 'sync'}
          </button>
          <button
            type="button"
            onClick={() => {
              if (confirm(`Supprimer ${project.repo_full_name} ? Le workspace local sera détruit.`)) {
                deleteMut.mutate(project.id);
              }
            }}
            disabled={deleteMut.isPending}
            className="min-h-11 rounded-eldir border border-eldir-gray-3 px-3 font-mono text-xs uppercase tracking-caps text-eldir-red hover:bg-eldir-red/10 disabled:opacity-50"
          >
            supprimer
          </button>
        </div>
      </div>
      {syncFeedback && (
        <div
          className={cn(
            'mt-1 font-mono text-[11px]',
            syncFeedback.kind === 'success' ? 'text-eldir-gray' : 'text-eldir-red',
          )}
        >
          {syncFeedback.text}
        </div>
      )}
    </li>
  );
}

function formatSyncResult(r: ProjectSyncResult): string {
  if (!r.fetched) return r.message ?? 'fetch impossible.';
  if (r.fast_forwarded) {
    return `${r.pulled} commit(s) récupéré(s) · à jour avec origin/${r.branch}`;
  }
  if (r.behind === 0 && r.ahead === 0) {
    return `déjà à jour avec origin/${r.branch}`;
  }
  if (r.behind > 0 && r.message) {
    return `${r.behind} commit(s) en retard - ${r.message}`;
  }
  if (r.ahead > 0) {
    return `${r.ahead} commit(s) local(aux) non poussé(s)`;
  }
  return r.message ?? 'sync terminée.';
}

type CloneFailure = { full_name: string; message: string };

interface AddProjectDialogProps {
  onClose: () => void;
  /** Appelé pour chaque projet cloné avec succès (id, nom). */
  onProjectCreated?: (project: { id: string; name: string }) => void;
}

function AddProjectDialog({
  onClose,
  onProjectCreated,
}: AddProjectDialogProps): JSX.Element {
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
        const created = await createProject.mutateAsync({
          provider,
          repo_full_name: full_name,
        });
        onProjectCreated?.({ id: created.id, name: created.name });
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
        <header className="flex items-center justify-between gap-3 border-b border-eldir-gray-3 px-4 py-3">
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
            className="min-w-0 flex-1 rounded-eldir border border-eldir-gray-3 bg-eldir-cream px-3 py-2 font-mono text-sm text-eldir-ink focus:border-eldir-orange focus:outline-none"
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

        <footer className="flex flex-wrap items-center justify-between gap-3 border-t border-eldir-gray-3 px-4 py-3">
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

/**
 * Modale qui apparaît juste après qu'un projet ait été cloné, proposant
 * trois options :
 *  - Analyser : ouvre GenerateTemplateDialog pour générer le template via Claude
 *  - Configurer manuellement : redirige vers /projects/{id}/template
 *  - Plus tard : ferme simplement
 */
function PostCloneOfferDialog({
  projectId,
  projectName,
  onClose,
}: {
  projectId: string;
  projectName: string;
  onClose: () => void;
}): JSX.Element {
  const [openGenerate, setOpenGenerate] = useState(false);

  if (openGenerate) {
    return (
      <GenerateTemplateDialog
        projectId={projectId}
        projectName={projectName}
        onClose={onClose}
      />
    );
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-eldir-ink/60 p-4">
      <div className="flex w-full max-w-md flex-col rounded-eldir border border-eldir-gray-3 bg-eldir-paper">
        <header className="border-b border-eldir-gray-3 px-4 py-3">
          <div className="eldir-caps">Mission Template</div>
          <h2 className="mt-1 font-mono text-sm font-bold text-eldir-ink">
            {projectName} cloné ✓
          </h2>
        </header>
        <div className="flex flex-col gap-3 px-4 py-4 text-sm text-eldir-ink-2">
          <p>
            Veux-tu qu'Eldir lance Claude pour analyser le repo et te générer
            un Mission Template adapté ? (~30s à 2min, coût visible dans le
            dashboard Costs)
          </p>
          <div className="rounded-eldir border border-eldir-gray-3 bg-eldir-cream p-3 text-xs">
            Le template peut toujours être édité ensuite à la main depuis{' '}
            <code>Projects → {projectName} → Template</code>.
          </div>
        </div>
        <footer className="flex flex-col gap-2 border-t border-eldir-gray-3 px-4 py-3">
          <button
            type="button"
            onClick={() => setOpenGenerate(true)}
            className="rounded-eldir bg-eldir-orange px-4 py-2 font-mono text-xs font-semibold uppercase tracking-caps text-white hover:bg-eldir-orange/90"
          >
            ✨ analyser avec claude
          </button>
          <Link
            to={`/projects/${projectId}/template`}
            onClick={onClose}
            className="rounded-eldir border border-eldir-gray-3 bg-eldir-paper px-4 py-2 text-center font-mono text-xs font-semibold uppercase tracking-caps text-eldir-ink hover:bg-eldir-cream-2"
          >
            configurer manuellement
          </Link>
          <button
            type="button"
            onClick={onClose}
            className="px-4 py-1 font-mono text-2xs uppercase tracking-caps text-eldir-gray hover:text-eldir-ink"
          >
            plus tard
          </button>
        </footer>
      </div>
    </div>
  );
}
