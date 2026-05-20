/**
 * ApplyPresetDialog - modale pour appliquer un preset bundlé au template
 * du projet. Liste les presets, montre une preview "joli rendu" du preset
 * sélectionné, et offre le choix overwrite/merge.
 */

import { useState } from 'react';

import { ApiError } from '@/lib/api/client';
import {
  useApplyTemplatePreset,
  useTemplatePreset,
  useTemplatePresets,
} from '@/lib/api/queries';
import type {
  TemplatePresetDetail,
  TemplatePresetSummary,
} from '@/lib/api/queries';
import { cn } from '@/lib/utils';

interface ApplyPresetDialogProps {
  projectId: string;
  onClose: () => void;
  onApplied?: () => void;
}

export function ApplyPresetDialog({
  projectId,
  onClose,
  onApplied,
}: ApplyPresetDialogProps): JSX.Element {
  const presets = useTemplatePresets();
  const [selectedSlug, setSelectedSlug] = useState<string | null>(null);
  const [overwrite, setOverwrite] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const apply = useApplyTemplatePreset(projectId);
  const detail = useTemplatePreset(selectedSlug);

  const handleApply = async () => {
    if (!selectedSlug) return;
    setError(null);
    try {
      await apply.mutateAsync({ slug: selectedSlug, overwrite });
      onApplied?.();
      onClose();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Erreur lors de l\'application.');
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-eldir-ink/60 p-4">
      <div className="flex max-h-[85vh] w-full max-w-4xl flex-col rounded-eldir border border-eldir-gray-3 bg-eldir-paper">
        <header className="flex items-center justify-between border-b border-eldir-gray-3 px-4 py-3">
          <div className="eldir-caps">Appliquer un preset</div>
          <button
            type="button"
            onClick={onClose}
            className="font-mono text-xs uppercase tracking-caps text-eldir-gray hover:text-eldir-ink"
          >
            fermer
          </button>
        </header>

        <div className="grid min-h-0 flex-1 grid-cols-1 md:grid-cols-[260px_1fr]">
          <aside className="overflow-y-auto border-r border-eldir-gray-3">
            {presets.isPending && (
              <p className="px-4 py-4 font-mono text-xs text-eldir-gray">chargement…</p>
            )}
            {presets.isError && (
              <p className="px-4 py-4 font-mono text-xs text-eldir-red">
                {presets.error.message}
              </p>
            )}
            {presets.data && presets.data.length === 0 && (
              <p className="px-4 py-4 font-mono text-xs text-eldir-gray">
                Aucun preset bundlé.
              </p>
            )}
            <ul className="divide-y divide-eldir-gray-3">
              {(presets.data ?? []).map((p) => (
                <PresetRow
                  key={p.slug}
                  preset={p}
                  selected={selectedSlug === p.slug}
                  onClick={() => setSelectedSlug(p.slug)}
                />
              ))}
            </ul>
          </aside>

          <section className="min-w-0 overflow-y-auto bg-eldir-cream">
            {!selectedSlug && (
              <p className="px-5 py-6 font-mono text-xs text-eldir-gray">
                Sélectionne un preset à gauche pour voir son contenu.
              </p>
            )}
            {selectedSlug && detail.data && <PresetPreview preset={detail.data} />}
            {selectedSlug && detail.isPending && (
              <p className="px-5 py-6 font-mono text-xs text-eldir-gray">
                chargement du preset…
              </p>
            )}
          </section>
        </div>

        <footer className="flex flex-col gap-3 border-t border-eldir-gray-3 px-4 py-3 md:flex-row md:items-center md:justify-between">
          <label className="flex items-center gap-2 font-mono text-xs text-eldir-ink-2">
            <input
              type="checkbox"
              checked={overwrite}
              onChange={(e) => setOverwrite(e.target.checked)}
              className="h-4 w-4 accent-eldir-orange"
            />
            <span>
              Écraser le contenu existant (sinon : merge - les noms en conflit sont conservés)
            </span>
          </label>
          {error && (
            <span className="font-mono text-xs text-eldir-red">{error}</span>
          )}
          <div className="flex gap-2">
            <button
              type="button"
              onClick={onClose}
              className="rounded-eldir border border-eldir-gray-3 px-3 py-2 font-mono text-xs uppercase tracking-caps text-eldir-gray hover:text-eldir-ink"
            >
              annuler
            </button>
            <button
              type="button"
              onClick={handleApply}
              disabled={!selectedSlug || apply.isPending}
              className="rounded-eldir bg-eldir-orange px-4 py-2 font-mono text-xs font-semibold uppercase tracking-caps text-white hover:bg-eldir-orange/90 disabled:opacity-50"
            >
              {apply.isPending ? 'application…' : 'appliquer'}
            </button>
          </div>
        </footer>
      </div>
    </div>
  );
}

function PresetRow({
  preset,
  selected,
  onClick,
}: {
  preset: TemplatePresetSummary;
  selected: boolean;
  onClick: () => void;
}): JSX.Element {
  return (
    <li>
      <button
        type="button"
        onClick={onClick}
        className={cn(
          'flex w-full flex-col items-start gap-1 border-l-2 px-4 py-3 text-left transition-colors',
          selected
            ? 'border-l-eldir-orange bg-eldir-cream'
            : 'border-l-transparent hover:bg-eldir-cream-2',
        )}
      >
        <span className="font-mono text-sm font-semibold text-eldir-ink">
          {preset.title}
        </span>
        <span className="line-clamp-2 text-xs text-eldir-ink-2">
          {preset.description}
        </span>
        <span className="mt-1 font-mono text-2xs text-eldir-gray">
          {preset.skill_count} skill{preset.skill_count > 1 ? 's' : ''} ·{' '}
          {preset.sub_agent_count} agent{preset.sub_agent_count > 1 ? 's' : ''}
          {preset.model && ` · ${preset.model}`}
        </span>
      </button>
    </li>
  );
}

function PresetPreview({ preset }: { preset: TemplatePresetDetail }): JSX.Element {
  return (
    <article className="flex flex-col gap-5 p-5">
      <header>
        <h2 className="font-mono text-lg font-bold text-eldir-ink">{preset.title}</h2>
        <p className="mt-1 text-sm text-eldir-ink-2">{preset.description}</p>
        {preset.tags.length > 0 && (
          <div className="mt-2 flex flex-wrap gap-1.5">
            {preset.tags.map((t) => (
              <span
                key={t}
                className="rounded-eldir bg-eldir-gold/20 px-2 py-0.5 font-mono text-2xs uppercase tracking-caps text-eldir-ink-2"
              >
                {t}
              </span>
            ))}
          </div>
        )}
      </header>

      <PreviewSection title="System prompt">
        <pre className="whitespace-pre-wrap break-words rounded-eldir border border-eldir-gray-3 bg-eldir-paper p-3 font-mono text-xs text-eldir-ink">
          {preset.system_prompt}
        </pre>
      </PreviewSection>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        <PreviewSection title="Modèle">
          <p className="font-mono text-xs text-eldir-ink-2">
            {preset.model ?? 'défaut serveur'}
          </p>
        </PreviewSection>
        <PreviewSection title="Outils autorisés">
          {preset.allowed_tools && preset.allowed_tools.length > 0 ? (
            <div className="flex flex-wrap gap-1">
              {preset.allowed_tools.map((t) => (
                <span
                  key={t}
                  className="rounded-eldir border border-eldir-gray-3 bg-eldir-paper px-2 py-0.5 font-mono text-2xs text-eldir-ink-2"
                >
                  {t}
                </span>
              ))}
            </div>
          ) : (
            <p className="font-mono text-2xs text-eldir-gray">
              tous (pas de restriction)
            </p>
          )}
        </PreviewSection>
      </div>

      <PreviewSection title={`Skills (${preset.skills.length})`}>
        {preset.skills.length === 0 ? (
          <p className="font-mono text-2xs text-eldir-gray">aucun</p>
        ) : (
          <ul className="space-y-2">
            {preset.skills.map((s) => (
              <li
                key={s.name}
                className="rounded-eldir border border-eldir-gray-3 bg-eldir-paper p-3"
              >
                <div className="font-mono text-xs font-semibold text-eldir-ink">
                  {s.name}
                </div>
                {s.description && (
                  <div className="mt-0.5 text-xs text-eldir-ink-2">
                    {s.description}
                  </div>
                )}
              </li>
            ))}
          </ul>
        )}
      </PreviewSection>

      <PreviewSection title={`Sub-agents (${preset.sub_agents.length})`}>
        {preset.sub_agents.length === 0 ? (
          <p className="font-mono text-2xs text-eldir-gray">aucun</p>
        ) : (
          <ul className="space-y-2">
            {preset.sub_agents.map((a) => (
              <li
                key={a.name}
                className="rounded-eldir border border-eldir-gray-3 bg-eldir-paper p-3"
              >
                <div className="font-mono text-xs font-semibold text-eldir-ink">
                  {a.name}
                </div>
                {a.description && (
                  <div className="mt-0.5 text-xs text-eldir-ink-2">
                    {a.description}
                  </div>
                )}
                {a.allowed_tools && a.allowed_tools.length > 0 && (
                  <div className="mt-1 font-mono text-2xs text-eldir-gray">
                    tools: {a.allowed_tools.join(', ')}
                  </div>
                )}
              </li>
            ))}
          </ul>
        )}
      </PreviewSection>
    </article>
  );
}

function PreviewSection({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}): JSX.Element {
  return (
    <section>
      <div className="eldir-caps mb-2">{title}</div>
      {children}
    </section>
  );
}
