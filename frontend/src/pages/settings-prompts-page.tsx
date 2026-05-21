/**
 * SettingsPromptsPage - édition des prompts système qu'Eldir envoie à
 * Claude pour ses opérations internes (génération de template, etc.).
 *
 * Cf. Principe directeur #5 : l'utilisateur reste maître. Chaque prompt
 * automatique d'Eldir doit être visible et modifiable.
 */

import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';

import {
  useResetSystemPrompt,
  useSystemPrompts,
  useUpsertSystemPrompt,
} from '@/lib/api/queries';
import type { SystemPromptRead } from '@/lib/types/api';
import { cn } from '@/lib/utils';

export function SettingsPromptsPage(): JSX.Element {
  const prompts = useSystemPrompts();
  const [selectedSlug, setSelectedSlug] = useState<string | null>(null);

  useEffect(() => {
    if (selectedSlug === null && prompts.data && prompts.data.length > 0) {
      setSelectedSlug(prompts.data[0]?.slug ?? null);
    }
  }, [prompts.data, selectedSlug]);

  const selected = prompts.data?.find((p) => p.slug === selectedSlug) ?? null;

  return (
    <main className="mx-auto flex max-w-6xl flex-col gap-4 p-4 md:p-8">
      <header>
        <Link
          to="/settings"
          className="font-mono text-2xs uppercase tracking-caps text-eldir-gray hover:text-eldir-orange"
        >
          ← settings
        </Link>
        <div className="eldir-caps mt-2">Prompts système</div>
        <h1 className="mt-1 font-mono text-xl font-bold text-eldir-ink">
          Prompts Eldir
        </h1>
        <p className="mt-2 max-w-3xl text-sm text-eldir-ink-2">
          Eldir utilise Claude pour certaines opérations internes (génération
          d'un Mission Template depuis un repo cloné, par exemple). Tu peux
          modifier ces prompts ici. Reset au défaut possible à tout moment.
        </p>
      </header>

      {prompts.isPending && (
        <p className="font-mono text-sm text-eldir-gray">Chargement…</p>
      )}
      {prompts.isError && (
        <p className="font-mono text-sm text-eldir-red">
          Impossible de charger les prompts.
        </p>
      )}

      {prompts.data && prompts.data.length === 0 && (
        <p className="font-mono text-sm text-eldir-gray">
          Aucun prompt système défini pour le moment.
        </p>
      )}

      {prompts.data && prompts.data.length > 0 && (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-[260px_1fr]">
          {/* Liste à gauche */}
          <aside className="flex flex-col gap-1 rounded-eldir border border-eldir-gray-3 bg-eldir-cream p-2">
            {prompts.data.map((p) => (
              <button
                key={p.slug}
                type="button"
                onClick={() => setSelectedSlug(p.slug)}
                className={cn(
                  'rounded-eldir px-3 py-2 text-left transition-colors',
                  selectedSlug === p.slug
                    ? 'bg-eldir-orange/10 ring-1 ring-eldir-orange'
                    : 'hover:bg-eldir-cream-2',
                )}
              >
                <div className="flex items-center gap-2">
                  <span className="font-mono text-xs font-semibold text-eldir-ink">
                    {p.title}
                  </span>
                  {p.is_overridden && (
                    <span className="rounded-eldir bg-eldir-orange/20 px-1.5 py-0.5 font-mono text-2xs uppercase tracking-caps text-eldir-orange">
                      édité
                    </span>
                  )}
                </div>
                <div className="mt-0.5 font-mono text-2xs text-eldir-gray">
                  {p.slug}
                </div>
              </button>
            ))}
          </aside>

          {/* Éditeur à droite */}
          <section className="min-w-0">
            {selected ? (
              <PromptEditor key={selected.slug} prompt={selected} />
            ) : (
              <p className="font-mono text-sm text-eldir-gray">
                Sélectionne un prompt à gauche.
              </p>
            )}
          </section>
        </div>
      )}
    </main>
  );
}

function PromptEditor({ prompt }: { prompt: SystemPromptRead }): JSX.Element {
  const [content, setContent] = useState(prompt.content);
  const upsert = useUpsertSystemPrompt(prompt.slug);
  const reset = useResetSystemPrompt(prompt.slug);
  const [status, setStatus] = useState<string | null>(null);

  useEffect(() => {
    setContent(prompt.content);
  }, [prompt.slug, prompt.content]);

  const dirty = content !== prompt.content;
  const matchesDefault = content === prompt.default_content;

  const onSave = async () => {
    setStatus(null);
    try {
      await upsert.mutateAsync({ content });
      setStatus('Sauvegardé.');
    } catch {
      setStatus('Erreur lors de la sauvegarde.');
    }
  };

  const onReset = async () => {
    if (
      !confirm(
        `Restaurer le défaut Eldir pour "${prompt.title}" ? Tes modifications seront perdues.`,
      )
    ) {
      return;
    }
    setStatus(null);
    try {
      const reverted = await reset.mutateAsync();
      setContent(reverted.content);
      setStatus('Défaut restauré.');
    } catch {
      setStatus('Erreur lors du reset.');
    }
  };

  return (
    <div className="flex flex-col gap-3">
      <header className="rounded-eldir border border-eldir-gray-3 bg-eldir-paper p-3">
        <div className="flex items-start justify-between gap-3">
          <div>
            <div className="font-mono text-sm font-semibold text-eldir-ink">
              {prompt.title}
            </div>
            {prompt.description && (
              <p className="mt-1 text-xs text-eldir-ink-2">
                {prompt.description}
              </p>
            )}
            <div className="mt-2 font-mono text-2xs text-eldir-gray">
              slug : <code>{prompt.slug}</code>
            </div>
          </div>
          <div className="flex flex-col items-end gap-1 font-mono text-2xs">
            <span
              className={cn(
                'rounded-eldir px-2 py-0.5 uppercase tracking-caps',
                prompt.is_overridden
                  ? 'bg-eldir-orange/20 text-eldir-orange'
                  : 'bg-eldir-gray-3 text-eldir-gray',
              )}
            >
              {prompt.is_overridden ? 'édité' : 'défaut Eldir'}
            </span>
          </div>
        </div>
      </header>

      <textarea
        value={content}
        onChange={(e) => setContent(e.target.value)}
        spellCheck={false}
        className="min-h-[400px] w-full resize-y rounded-eldir border border-eldir-gray-3 bg-eldir-paper p-3 font-mono text-xs text-eldir-ink focus:border-eldir-orange focus:outline-none focus:ring-1 focus:ring-eldir-orange"
      />

      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="font-mono text-2xs text-eldir-gray">
          {content.length} caractères
          {dirty && ' · modifications non sauvegardées'}
          {!dirty && matchesDefault && prompt.is_overridden && ' · ⚠ identique au défaut'}
        </div>
        <div className="flex gap-2">
          <button
            type="button"
            onClick={onReset}
            disabled={reset.isPending || !prompt.is_overridden}
            className="rounded-eldir border border-eldir-gray-3 bg-eldir-paper px-3 py-1.5 font-mono text-xs uppercase tracking-caps text-eldir-ink hover:bg-eldir-cream-2 disabled:opacity-40"
          >
            {reset.isPending ? 'reset…' : 'restaurer le défaut'}
          </button>
          <button
            type="button"
            onClick={onSave}
            disabled={upsert.isPending || !dirty}
            className="rounded-eldir bg-eldir-orange px-3 py-1.5 font-mono text-xs font-semibold uppercase tracking-caps text-white hover:bg-eldir-orange/90 disabled:opacity-50"
          >
            {upsert.isPending ? 'sauvegarde…' : 'sauvegarder'}
          </button>
        </div>
      </div>

      {status && (
        <p className="font-mono text-2xs text-eldir-gray">{status}</p>
      )}
    </div>
  );
}
