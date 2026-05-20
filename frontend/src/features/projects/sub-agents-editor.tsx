/**
 * SubAgentsEditor - liste des sub-agents d'un projet + édition.
 *
 * Un sub-agent = un agent secondaire que Claude peut déléguer pour des
 * tâches spécifiques. Matérialisé en `.claude/agents/{name}.md` dans le
 * worktree.
 */

import { useState } from 'react';

import { ApiError } from '@/lib/api/client';
import {
  useCreateTemplateSubAgent,
  useDeleteTemplateSubAgent,
  useTemplateSubAgents,
  useUpdateTemplateSubAgent,
} from '@/lib/api/queries';
import type {
  TemplateSubAgent,
  TemplateSubAgentWrite,
} from '@/lib/api/queries';
import { cn } from '@/lib/utils';

interface SubAgentsEditorProps {
  projectId: string;
  toolOptions: readonly string[];
}

export function SubAgentsEditor({
  projectId,
  toolOptions,
}: SubAgentsEditorProps): JSX.Element {
  const agents = useTemplateSubAgents(projectId);
  const [editing, setEditing] = useState<TemplateSubAgent | 'new' | null>(null);

  return (
    <section className="rounded-eldir border border-eldir-gray-3 bg-eldir-cream p-5">
      <header className="mb-3 flex items-center justify-between">
        <div>
          <div className="eldir-caps">Sub-agents</div>
          <p className="mt-1 text-xs text-eldir-ink-2">
            Agents secondaires délégables - matérialisés dans{' '}
            <span className="font-mono">.claude/agents/</span>.
          </p>
        </div>
        <button
          type="button"
          onClick={() => setEditing('new')}
          className="rounded-eldir border border-eldir-gray-3 bg-eldir-paper px-3 py-1.5 font-mono text-xs uppercase tracking-caps text-eldir-ink hover:bg-eldir-cream-2"
        >
          + ajouter
        </button>
      </header>

      {agents.isPending && (
        <p className="font-mono text-xs text-eldir-gray">chargement…</p>
      )}
      {agents.data && agents.data.length === 0 && !agents.isPending && (
        <p className="font-mono text-xs text-eldir-gray">
          Aucun sub-agent. Exemples typiques : "test-runner" (Haiku),
          "doc-writer", "code-reviewer".
        </p>
      )}
      {agents.data && agents.data.length > 0 && (
        <ul className="divide-y divide-eldir-gray-3">
          {agents.data.map((a) => (
            <li key={a.id} className="flex items-center justify-between py-2">
              <div className="min-w-0">
                <div className="font-mono text-sm font-semibold text-eldir-ink">
                  {a.name}
                </div>
                {a.description && (
                  <div className="truncate text-xs text-eldir-gray">
                    {a.description}
                  </div>
                )}
                {a.allowed_tools && a.allowed_tools.length > 0 && (
                  <div className="mt-0.5 font-mono text-2xs text-eldir-gray">
                    tools: {a.allowed_tools.join(', ')}
                  </div>
                )}
              </div>
              <button
                type="button"
                onClick={() => setEditing(a)}
                className="rounded-eldir border border-eldir-gray-3 px-3 py-1.5 font-mono text-xs uppercase tracking-caps text-eldir-ink hover:bg-eldir-cream-2"
              >
                éditer
              </button>
            </li>
          ))}
        </ul>
      )}

      {editing && (
        <SubAgentDialog
          projectId={projectId}
          initial={editing === 'new' ? null : editing}
          toolOptions={toolOptions}
          onClose={() => setEditing(null)}
        />
      )}
    </section>
  );
}

function SubAgentDialog({
  projectId,
  initial,
  toolOptions,
  onClose,
}: {
  projectId: string;
  initial: TemplateSubAgent | null;
  toolOptions: readonly string[];
  onClose: () => void;
}): JSX.Element {
  const create = useCreateTemplateSubAgent(projectId);
  const update = useUpdateTemplateSubAgent(projectId);
  const del = useDeleteTemplateSubAgent(projectId);
  const [name, setName] = useState(initial?.name ?? '');
  const [description, setDescription] = useState(initial?.description ?? '');
  const [systemPrompt, setSystemPrompt] = useState(initial?.system_prompt ?? '');
  const [tools, setTools] = useState<Set<string>>(
    new Set(initial?.allowed_tools ?? []),
  );
  const [error, setError] = useState<string | null>(null);

  const toggleTool = (tool: string) => {
    setTools((prev) => {
      const next = new Set(prev);
      if (next.has(tool)) next.delete(tool);
      else next.add(tool);
      return next;
    });
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    const body: TemplateSubAgentWrite = {
      name: name.trim(),
      description: description.trim() || null,
      system_prompt: systemPrompt,
      allowed_tools: tools.size > 0 ? Array.from(tools) : null,
    };
    try {
      if (initial) {
        await update.mutateAsync({ id: initial.id, body });
      } else {
        await create.mutateAsync(body);
      }
      onClose();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Erreur lors de la sauvegarde.');
    }
  };

  const handleDelete = async () => {
    if (!initial) return;
    if (!confirm(`Supprimer le sub-agent "${initial.name}" ?`)) return;
    try {
      await del.mutateAsync(initial.id);
      onClose();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Erreur lors de la suppression.');
    }
  };

  const submitting = create.isPending || update.isPending;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-eldir-ink/60 p-4">
      <form
        onSubmit={handleSubmit}
        className="flex max-h-[85vh] w-full max-w-2xl flex-col rounded-eldir border border-eldir-gray-3 bg-eldir-paper"
      >
        <header className="flex items-center justify-between border-b border-eldir-gray-3 px-4 py-3">
          <div className="eldir-caps">
            {initial ? 'Éditer sub-agent' : 'Nouveau sub-agent'}
          </div>
          <button
            type="button"
            onClick={onClose}
            className="font-mono text-xs uppercase tracking-caps text-eldir-gray hover:text-eldir-ink"
          >
            fermer
          </button>
        </header>

        <div className="flex-1 overflow-y-auto p-4">
          <label className="mb-3 block">
            <span className="eldir-caps mb-1 block">Nom</span>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              maxLength={120}
              placeholder="ex: test-runner"
              className="w-full rounded-eldir border border-eldir-gray-3 bg-eldir-cream px-3 py-2 font-mono text-sm text-eldir-ink focus:border-eldir-orange focus:outline-none"
              required
            />
          </label>

          <label className="mb-3 block">
            <span className="eldir-caps mb-1 block">Description (optionnel)</span>
            <input
              type="text"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              maxLength={255}
              className="w-full rounded-eldir border border-eldir-gray-3 bg-eldir-cream px-3 py-2 font-mono text-sm text-eldir-ink focus:border-eldir-orange focus:outline-none"
            />
          </label>

          <label className="mb-3 block">
            <span className="eldir-caps mb-1 block">System prompt</span>
            <textarea
              value={systemPrompt}
              onChange={(e) => setSystemPrompt(e.target.value)}
              rows={8}
              required
              className="w-full rounded-eldir border border-eldir-gray-3 bg-eldir-cream px-3 py-2 font-mono text-xs text-eldir-ink focus:border-eldir-orange focus:outline-none"
            />
          </label>

          <div>
            <span className="eldir-caps mb-2 block">Outils autorisés (optionnel)</span>
            <div className="flex flex-wrap gap-2">
              {toolOptions.map((tool) => {
                const active = tools.has(tool);
                return (
                  <button
                    key={tool}
                    type="button"
                    onClick={() => toggleTool(tool)}
                    className={cn(
                      'rounded-eldir border px-3 py-1.5 font-mono text-xs uppercase tracking-caps transition-colors',
                      active
                        ? 'border-eldir-orange bg-eldir-orange/10 text-eldir-ink'
                        : 'border-eldir-gray-3 text-eldir-gray hover:text-eldir-ink',
                    )}
                  >
                    {tool}
                  </button>
                );
              })}
            </div>
          </div>

          {error && (
            <div className="mt-3 rounded-eldir border border-eldir-red bg-eldir-red/10 px-3 py-2 font-mono text-xs text-eldir-red">
              {error}
            </div>
          )}
        </div>

        <footer className="flex items-center justify-between gap-3 border-t border-eldir-gray-3 px-4 py-3">
          {initial ? (
            <button
              type="button"
              onClick={handleDelete}
              disabled={del.isPending}
              className="rounded-eldir border border-eldir-gray-3 px-3 py-2 font-mono text-xs uppercase tracking-caps text-eldir-red hover:bg-eldir-red/10 disabled:opacity-50"
            >
              {del.isPending ? 'suppr…' : 'supprimer'}
            </button>
          ) : (
            <span />
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
              type="submit"
              disabled={submitting || !name.trim() || !systemPrompt.trim()}
              className="rounded-eldir bg-eldir-orange px-4 py-2 font-mono text-xs font-semibold uppercase tracking-caps text-white hover:bg-eldir-orange/90 disabled:opacity-50"
            >
              {submitting ? 'enregistrement…' : 'enregistrer'}
            </button>
          </div>
        </footer>
      </form>
    </div>
  );
}
