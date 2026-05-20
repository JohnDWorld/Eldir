/**
 * SkillsEditor - liste des skills d'un projet + édition inline.
 *
 * Un skill = un fichier markdown matérialisé en `.claude/skills/{name}/SKILL.md`
 * dans le worktree de chaque nouvelle session.
 */

import { useState } from 'react';

import { ApiError } from '@/lib/api/client';
import {
  useCreateTemplateSkill,
  useDeleteTemplateSkill,
  useTemplateSkills,
  useUpdateTemplateSkill,
} from '@/lib/api/queries';
import type { TemplateSkill, TemplateSkillWrite } from '@/lib/api/queries';

interface SkillsEditorProps {
  projectId: string;
}

export function SkillsEditor({ projectId }: SkillsEditorProps): JSX.Element {
  const skills = useTemplateSkills(projectId);
  const [editing, setEditing] = useState<TemplateSkill | 'new' | null>(null);

  return (
    <section className="rounded-eldir border border-eldir-gray-3 bg-eldir-cream p-5">
      <header className="mb-3 flex items-center justify-between">
        <div>
          <div className="eldir-caps">Skills</div>
          <p className="mt-1 text-xs text-eldir-ink-2">
            Matérialisés dans <span className="font-mono">.claude/skills/</span>{' '}
            de chaque nouvelle session.
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

      {skills.isPending && (
        <p className="font-mono text-xs text-eldir-gray">chargement…</p>
      )}
      {skills.data && skills.data.length === 0 && !skills.isPending && (
        <p className="font-mono text-xs text-eldir-gray">
          Aucun skill. Ajoute-en un - par exemple "exécuter-tests" avec les
          commandes locales pour lancer tes tests.
        </p>
      )}
      {skills.data && skills.data.length > 0 && (
        <ul className="divide-y divide-eldir-gray-3">
          {skills.data.map((s) => (
            <li key={s.id} className="flex items-center justify-between py-2">
              <div className="min-w-0">
                <div className="font-mono text-sm font-semibold text-eldir-ink">
                  {s.name}
                </div>
                {s.description && (
                  <div className="truncate text-xs text-eldir-gray">
                    {s.description}
                  </div>
                )}
              </div>
              <button
                type="button"
                onClick={() => setEditing(s)}
                className="rounded-eldir border border-eldir-gray-3 px-3 py-1.5 font-mono text-xs uppercase tracking-caps text-eldir-ink hover:bg-eldir-cream-2"
              >
                éditer
              </button>
            </li>
          ))}
        </ul>
      )}

      {editing && (
        <SkillDialog
          projectId={projectId}
          initial={editing === 'new' ? null : editing}
          onClose={() => setEditing(null)}
        />
      )}
    </section>
  );
}

function SkillDialog({
  projectId,
  initial,
  onClose,
}: {
  projectId: string;
  initial: TemplateSkill | null;
  onClose: () => void;
}): JSX.Element {
  const create = useCreateTemplateSkill(projectId);
  const update = useUpdateTemplateSkill(projectId);
  const del = useDeleteTemplateSkill(projectId);
  const [name, setName] = useState(initial?.name ?? '');
  const [description, setDescription] = useState(initial?.description ?? '');
  const [content, setContent] = useState(initial?.content ?? '');
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    const body: TemplateSkillWrite = {
      name: name.trim(),
      description: description.trim() || null,
      content,
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
    if (!confirm(`Supprimer le skill "${initial.name}" ?`)) return;
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
          <div className="eldir-caps">{initial ? 'Éditer skill' : 'Nouveau skill'}</div>
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
              placeholder="ex: run-tests"
              className="w-full rounded-eldir border border-eldir-gray-3 bg-eldir-cream px-3 py-2 font-mono text-sm text-eldir-ink focus:border-eldir-orange focus:outline-none"
              required
            />
            <p className="mt-1 font-mono text-2xs text-eldir-gray">
              Lettres, chiffres, tirets et underscores uniquement.
            </p>
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

          <label className="block">
            <span className="eldir-caps mb-1 block">Contenu (markdown)</span>
            <textarea
              value={content}
              onChange={(e) => setContent(e.target.value)}
              rows={14}
              required
              className="w-full rounded-eldir border border-eldir-gray-3 bg-eldir-cream px-3 py-2 font-mono text-xs text-eldir-ink focus:border-eldir-orange focus:outline-none"
            />
          </label>

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
              disabled={submitting || !name.trim() || !content.trim()}
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
