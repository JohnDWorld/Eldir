/**
 * NewRepoDialog — créer un nouveau repo distant (GitHub/Forgejo) puis
 * optionnellement le cloner en projet Eldir.
 */

import { useState } from 'react';

import { GitMark } from '@/components/eldir/git-mark';
import { ApiError } from '@/lib/api/client';
import { useCreateRemoteRepo } from '@/lib/api/queries';
import type { Provider } from '@/lib/constants';
import { PROVIDERS } from '@/lib/constants';
import { cn } from '@/lib/utils';

export function NewRepoDialog({ onClose }: { onClose: () => void }): JSX.Element {
  const [provider, setProvider] = useState<Provider>('github');
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [isPrivate, setIsPrivate] = useState(true);
  const [createProject, setCreateProject] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const create = useCreateRemoteRepo();

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    if (name.trim().length < 1) {
      setError('Le nom est requis.');
      return;
    }
    try {
      await create.mutateAsync({
        provider,
        name: name.trim(),
        private: isPrivate,
        description: description.trim() || null,
        create_project: createProject,
      });
      onClose();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Erreur création repo');
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-eldir-ink/60 p-4">
      <div className="w-full max-w-lg rounded-eldir border border-eldir-gray-3 bg-eldir-paper">
        <header className="flex items-center justify-between border-b border-eldir-gray-3 px-4 py-3">
          <div className="eldir-caps">Nouveau repo distant</div>
          <button
            type="button"
            onClick={onClose}
            className="font-mono text-xs uppercase tracking-caps text-eldir-gray hover:text-eldir-ink"
          >
            fermer
          </button>
        </header>

        <form onSubmit={submit} className="flex flex-col gap-3 p-4">
          <div className="flex gap-2">
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

          <label className="block">
            <span className="eldir-caps mb-1 block">Nom du repo</span>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="mon-nouveau-repo"
              required
              maxLength={100}
              className="w-full rounded-eldir border border-eldir-gray-3 bg-eldir-cream px-3 py-2 font-mono text-sm text-eldir-ink focus:border-eldir-orange focus:outline-none"
            />
          </label>

          <label className="block">
            <span className="eldir-caps mb-1 block">Description (optionnelle)</span>
            <input
              type="text"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              maxLength={512}
              className="w-full rounded-eldir border border-eldir-gray-3 bg-eldir-cream px-3 py-2 font-mono text-sm text-eldir-ink focus:border-eldir-orange focus:outline-none"
            />
          </label>

          <label className="flex items-center gap-2 font-mono text-xs text-eldir-ink">
            <input
              type="checkbox"
              checked={isPrivate}
              onChange={(e) => setIsPrivate(e.target.checked)}
            />
            Repo privé
          </label>

          <label className="flex items-center gap-2 font-mono text-xs text-eldir-ink">
            <input
              type="checkbox"
              checked={createProject}
              onChange={(e) => setCreateProject(e.target.checked)}
            />
            Cloner immédiatement comme projet Eldir
          </label>

          {error && (
            <div className="rounded-eldir border border-eldir-red bg-eldir-red/10 px-3 py-2 font-mono text-xs text-eldir-red">
              {error}
            </div>
          )}

          <div className="flex justify-end gap-2">
            <button
              type="button"
              onClick={onClose}
              className="rounded-eldir border border-eldir-gray-3 px-4 py-2 font-mono text-xs uppercase tracking-caps text-eldir-ink hover:bg-eldir-cream"
            >
              annuler
            </button>
            <button
              type="submit"
              disabled={create.isPending}
              className="rounded-eldir bg-eldir-orange px-4 py-2 font-mono text-xs font-semibold uppercase tracking-caps text-white hover:bg-eldir-orange/90 disabled:opacity-50"
            >
              {create.isPending ? 'création…' : 'créer'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
