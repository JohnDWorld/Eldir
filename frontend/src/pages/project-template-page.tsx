/**
 * ProjectTemplatePage - éditeur du MissionTemplate d'un projet.
 *
 * Trois zones : config (system prompt + model + tools), skills (.claude/skills/),
 * sub-agents (.claude/agents/). Les skills/sub-agents sont matérialisés dans
 * le worktree à chaque création de session.
 */

import { useEffect, useMemo, useState } from 'react';
import { useParams } from 'react-router-dom';

import { ApiError } from '@/lib/api/client';
import {
  useProjectTemplate,
  useProjects,
  useUpsertProjectTemplate,
} from '@/lib/api/queries';
import { ApplyPresetDialog } from '@/features/projects/apply-preset-dialog';
import { GenerateTemplateDialog } from '@/features/projects/generate-template-dialog';
import { SkillsEditor } from '@/features/projects/skills-editor';
import { SubAgentsEditor } from '@/features/projects/sub-agents-editor';
import { TemplateHistory } from '@/features/projects/template-history';

const MODEL_OPTIONS: { value: string; label: string }[] = [
  { value: '', label: 'défaut serveur' },
  { value: 'claude-opus-4-7', label: 'Opus 4.7 (raisonnement long)' },
  { value: 'claude-sonnet-4-6', label: 'Sonnet 4.6 (équilibré)' },
  { value: 'claude-haiku-4-5-20251001', label: 'Haiku 4.5 (économe)' },
];

const TOOL_OPTIONS = [
  'Read',
  'Write',
  'Edit',
  'Bash',
  'Glob',
  'Grep',
  'NotebookEdit',
  'WebFetch',
  'WebSearch',
  'TodoWrite',
] as const;

export function ProjectTemplatePage(): JSX.Element {
  const { projectId = '' } = useParams<{ projectId: string }>();
  const projects = useProjects();
  const template = useProjectTemplate(projectId);
  const upsert = useUpsertProjectTemplate(projectId);

  const project = projects.data?.find((p) => p.id === projectId);
  const [systemPrompt, setSystemPrompt] = useState('');
  const [model, setModel] = useState<string>('');
  const [allowedTools, setAllowedTools] = useState<Set<string>>(new Set());
  const [feedback, setFeedback] = useState<
    { kind: 'success' | 'error'; text: string } | null
  >(null);
  const [presetOpen, setPresetOpen] = useState(false);
  const [generateOpen, setGenerateOpen] = useState(false);

  // Hydrate quand on charge le template.
  useEffect(() => {
    if (!template.data) {
      setSystemPrompt('');
      setModel('');
      setAllowedTools(new Set());
      return;
    }
    setSystemPrompt(template.data.system_prompt ?? '');
    setModel(template.data.model ?? '');
    setAllowedTools(new Set(template.data.allowed_tools ?? []));
  }, [template.data]);

  const toggleTool = (tool: string) => {
    setAllowedTools((prev) => {
      const next = new Set(prev);
      if (next.has(tool)) next.delete(tool);
      else next.add(tool);
      return next;
    });
  };

  const handleSave = async () => {
    setFeedback(null);
    try {
      await upsert.mutateAsync({
        system_prompt: systemPrompt.trim() || null,
        model: model || null,
        allowed_tools: allowedTools.size > 0 ? Array.from(allowedTools) : null,
      });
      setFeedback({ kind: 'success', text: 'Template enregistré.' });
    } catch (err) {
      setFeedback({
        kind: 'error',
        text: err instanceof ApiError ? err.message : 'Erreur lors de la sauvegarde.',
      });
    }
  };

  const toolsHelper = useMemo(
    () =>
      allowedTools.size === 0
        ? 'Aucun outil sélectionné ⇒ tous les outils built-in autorisés.'
        : `${allowedTools.size} outil(s) autorisé(s). Les autres seront bloqués.`,
    [allowedTools],
  );

  if (!projectId) return <main className="p-6">Projet inconnu.</main>;

  return (
    <main className="mx-auto flex max-w-4xl flex-col gap-6 p-4 md:p-8">
      <header className="flex items-start justify-between gap-3">
        <div>
          <div className="eldir-caps">Projects · template</div>
          <h1 className="mt-1 font-mono text-xl font-bold text-eldir-ink">
            Template du projet {project?.name ?? '…'}
          </h1>
          <p className="mt-2 text-sm text-eldir-ink-2">
            Applique automatiquement system prompt, modèle, outils, skills et
            sub-agents à chaque nouvelle session de ce projet. Les changements
            n'affectent pas les sessions déjà ouvertes.
          </p>
          {template.data?.source_preset && (
            <p className="mt-2 font-mono text-2xs uppercase tracking-caps text-eldir-gold">
              basé sur le preset · {template.data.source_preset}
            </p>
          )}
        </div>
        <div className="flex gap-2">
          <button
            type="button"
            onClick={() => setGenerateOpen(true)}
            className="rounded-eldir bg-eldir-orange px-4 py-2 font-mono text-xs font-semibold uppercase tracking-caps text-white hover:bg-eldir-orange/90"
            title="Lance Claude pour analyser le repo et proposer un template clé en main"
          >
            ✨ générer avec claude
          </button>
          <button
            type="button"
            onClick={() => setPresetOpen(true)}
            className="rounded-eldir border border-eldir-gray-3 bg-eldir-paper px-4 py-2 font-mono text-xs font-semibold uppercase tracking-caps text-eldir-ink hover:bg-eldir-cream-2"
          >
            appliquer un preset
          </button>
        </div>
      </header>

      {/* Config principale */}
      <section className="rounded-eldir border border-eldir-gray-3 bg-eldir-cream p-5">
        <div className="eldir-caps mb-4">Config</div>
        <div className="flex flex-col gap-4">
          <label className="block">
            <span className="eldir-caps mb-1 block">System prompt</span>
            <textarea
              value={systemPrompt}
              onChange={(e) => setSystemPrompt(e.target.value)}
              rows={8}
              placeholder="Ex: 'Tu es l'agent maintainer du repo X. Convention : conventional commits, branches feature/. Stack: …'"
              className="w-full rounded-eldir border border-eldir-gray-3 bg-eldir-paper px-3 py-2 font-mono text-sm text-eldir-ink focus:border-eldir-orange focus:outline-none"
            />
            <p className="mt-1 font-mono text-2xs text-eldir-gray">
              Surcharge le system prompt par défaut. Laisse vide pour utiliser le défaut.
            </p>
          </label>

          <label className="block">
            <span className="eldir-caps mb-1 block">Modèle</span>
            <select
              value={model}
              onChange={(e) => setModel(e.target.value)}
              className="rounded-eldir border border-eldir-gray-3 bg-eldir-paper px-3 py-2 font-mono text-sm text-eldir-ink focus:border-eldir-orange focus:outline-none"
            >
              {MODEL_OPTIONS.map((o) => (
                <option key={o.value} value={o.value}>
                  {o.label}
                </option>
              ))}
            </select>
          </label>

          <div>
            <span className="eldir-caps mb-2 block">Outils autorisés</span>
            <div className="flex flex-wrap gap-2">
              {TOOL_OPTIONS.map((tool) => {
                const active = allowedTools.has(tool);
                return (
                  <button
                    key={tool}
                    type="button"
                    onClick={() => toggleTool(tool)}
                    className={
                      'rounded-eldir border px-3 py-1.5 font-mono text-xs uppercase tracking-caps transition-colors ' +
                      (active
                        ? 'border-eldir-orange bg-eldir-orange/10 text-eldir-ink'
                        : 'border-eldir-gray-3 text-eldir-gray hover:text-eldir-ink')
                    }
                  >
                    {tool}
                  </button>
                );
              })}
            </div>
            <p className="mt-2 font-mono text-2xs text-eldir-gray">{toolsHelper}</p>
          </div>
        </div>

        {feedback && (
          <div
            className={
              'mt-4 rounded-eldir border px-3 py-2 font-mono text-xs ' +
              (feedback.kind === 'success'
                ? 'border-eldir-green bg-eldir-green/10 text-eldir-green'
                : 'border-eldir-red bg-eldir-red/10 text-eldir-red')
            }
          >
            {feedback.text}
          </div>
        )}

        <div className="mt-4 flex justify-end">
          <button
            type="button"
            onClick={handleSave}
            disabled={upsert.isPending}
            className="rounded-eldir bg-eldir-orange px-4 py-2 font-mono text-xs font-semibold uppercase tracking-caps text-white hover:bg-eldir-orange/90 disabled:opacity-50"
          >
            {upsert.isPending ? 'enregistrement…' : 'enregistrer'}
          </button>
        </div>
      </section>

      <SkillsEditor projectId={projectId} />
      <SubAgentsEditor projectId={projectId} toolOptions={TOOL_OPTIONS} />
      <TemplateHistory projectId={projectId} />

      {presetOpen && (
        <ApplyPresetDialog
          projectId={projectId}
          onClose={() => setPresetOpen(false)}
        />
      )}
      {generateOpen && (
        <GenerateTemplateDialog
          projectId={projectId}
          projectName={project?.name ?? 'projet'}
          onClose={() => setGenerateOpen(false)}
        />
      )}
    </main>
  );
}
