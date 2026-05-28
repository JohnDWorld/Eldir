/**
 * SettingsOllamaPage - état Ollama + playground de transformations
 * locales (Phase 6 - mode données sensibles).
 *
 * Le serveur Ollama est configuré côté backend via OLLAMA_BASE_URL.
 * Cette page lit le status, liste les modèles dispos et permet de
 * tester mask/anonymize/summarize sur du texte arbitraire.
 */

import { useState } from 'react';
import { Link } from 'react-router-dom';

import { ApiError } from '@/lib/api/client';
import {
  useOllamaSettings,
  useOllamaStatus,
  useOllamaTransform,
  useUpdateOllamaSettings,
} from '@/lib/api/queries';
import type { OllamaTransformMode } from '@/lib/types/api';
import { cn } from '@/lib/utils';

const MODE_OPTIONS: ReadonlyArray<{
  value: OllamaTransformMode;
  label: string;
  description: string;
}> = [
  {
    value: 'mask',
    label: 'Masquer secrets',
    description:
      'Remplace tokens, clés d\'API, mots de passe, emails, etc. par des placeholders.',
  },
  {
    value: 'anonymize',
    label: 'Anonymiser PII',
    description:
      'Remplace noms, identifiants, entreprises, adresses par des génériques cohérents.',
  },
  {
    value: 'summarize',
    label: 'Résumer',
    description:
      'Produit un résumé court (10 lignes max) d\'un fichier de code ou de doc.',
  },
];

export function SettingsOllamaPage(): JSX.Element {
  const status = useOllamaStatus();
  const transform = useOllamaTransform();
  const exposeSettings = useOllamaSettings();
  const updateExpose = useUpdateOllamaSettings();
  const [mode, setMode] = useState<OllamaTransformMode>('mask');
  const [input, setInput] = useState('');
  const [output, setOutput] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const run = async () => {
    setError(null);
    setOutput(null);
    if (!input.trim()) {
      setError('Saisis du texte à transformer.');
      return;
    }
    try {
      const result = await transform.mutateAsync({ text: input, mode });
      setOutput(result.text);
    } catch (err) {
      setError(
        err instanceof ApiError ? err.message : 'Erreur lors de la transformation.',
      );
    }
  };

  return (
    <main className="mx-auto flex max-w-4xl flex-col gap-6 p-4 md:p-8">
      <header>
        <Link
          to="/settings"
          className="font-mono text-2xs uppercase tracking-caps text-eldir-gray hover:text-eldir-orange"
        >
          ← settings
        </Link>
        <div className="eldir-caps mt-2">Ollama · données sensibles</div>
        <h1 className="mt-1 font-mono text-xl font-bold text-eldir-ink">
          Pré-traitement local via Ollama
        </h1>
        <p className="mt-2 max-w-3xl text-sm text-eldir-ink-2">
          Ollama tourne sur ton réseau et permet de masquer / anonymiser /
          résumer du texte <strong>localement</strong> avant de l'envoyer à
          Claude. Tes données sensibles ne traversent jamais Internet.
        </p>
      </header>

      <section className="rounded-eldir border border-eldir-gray-3 bg-eldir-cream p-5">
        <div className="eldir-caps mb-3">Statut</div>
        {status.isPending && (
          <p className="font-mono text-sm text-eldir-gray">chargement…</p>
        )}
        {status.data && (
          <div className="flex flex-col gap-2 font-mono text-xs">
            <Kv k="enabled" v={status.data.enabled ? '✓ oui' : '✗ non configuré'} />
            {status.data.enabled && (
              <>
                <Kv k="base_url" v={status.data.base_url ?? '-'} />
                <Kv
                  k="reachable"
                  v={
                    status.data.reachable
                      ? '✓ accessible'
                      : `✗ inaccessible${status.data.error ? ` (${status.data.error})` : ''}`
                  }
                />
                <Kv k="default_model" v={status.data.default_model} />
                <Kv
                  k="models"
                  v={
                    status.data.available_models.length === 0
                      ? 'aucun'
                      : status.data.available_models
                          .map((m) => m.name)
                          .join(', ')
                  }
                />
              </>
            )}
          </div>
        )}
        {!status.isPending && status.data && !status.data.enabled && (
          <div className="mt-3 rounded-eldir border border-eldir-orange/40 bg-eldir-orange/5 p-3 text-xs text-eldir-ink-2">
            <strong>Pas encore configuré.</strong> Définis{' '}
            <code>OLLAMA_BASE_URL</code> dans <code>backend/.env</code> (ex.{' '}
            <code>http://host.docker.internal:11434</code>) puis redémarre le
            backend.
            <div className="mt-2">
              <a
                href="https://github.com/JohnDWorld/Eldir/blob/main/docs/ollama-integration.md"
                target="_blank"
                rel="noopener noreferrer"
                className="text-eldir-orange hover:underline"
              >
                voir la doc d'installation →
              </a>
            </div>
          </div>
        )}
      </section>

      <section className="rounded-eldir border border-eldir-gray-3 bg-eldir-cream p-5">
        <div className="eldir-caps mb-3">Exposer Ollama aux sessions Claude</div>
        <p className="mb-3 text-sm text-eldir-ink-2">
          Quand activé, chaque nouvelle session Claude reçoit automatiquement
          un sub-agent <code>mask-data</code> qu'elle peut invoquer pour
          masquer / anonymiser / résumer du texte sensible <strong>en local</strong>{' '}
          avant tout appel à Anthropic.
        </p>
        <p className="mb-4 font-mono text-2xs text-eldir-gray">
          Garde-fous : le sub-agent n'est PAS injecté si Ollama n'est pas
          configuré ou pas joignable, même si cette option est activée. C'est
          Claude qui décide d'invoquer le sub-agent (vue Option A+C du
          ROADMAP — auto-routing en V3).
        </p>
        {exposeSettings.isPending && (
          <p className="font-mono text-2xs text-eldir-gray">chargement…</p>
        )}
        {exposeSettings.data && (
          <label className="flex items-center justify-between gap-3 rounded-eldir border border-eldir-gray-3 bg-eldir-paper px-3 py-2.5">
            <div>
              <div className="font-mono text-xs font-semibold uppercase tracking-caps text-eldir-ink">
                Sub-agent <code>mask-data</code>
              </div>
              <div className="mt-0.5 font-mono text-2xs text-eldir-gray">
                {!status.data?.enabled
                  ? '⚠ Ollama non configuré côté backend.'
                  : !status.data?.reachable
                    ? '⚠ Ollama configuré mais injoignable.'
                    : exposeSettings.data.expose_to_sessions
                      ? '✓ Actif - injecté dans chaque nouvelle session.'
                      : 'Désactivé - playground manuel uniquement.'}
              </div>
            </div>
            <input
              type="checkbox"
              checked={exposeSettings.data.expose_to_sessions}
              disabled={
                updateExpose.isPending ||
                !status.data?.enabled ||
                !status.data?.reachable
              }
              onChange={(e) =>
                updateExpose.mutate({ expose_to_sessions: e.target.checked })
              }
              className="h-5 w-5 accent-eldir-orange disabled:cursor-not-allowed disabled:opacity-40"
            />
          </label>
        )}
      </section>

      {status.data?.reachable && (
        <section className="rounded-eldir border border-eldir-gray-3 bg-eldir-cream p-5">
          <div className="eldir-caps mb-3">Playground</div>

          <div className="mb-3 flex flex-wrap gap-2">
            {MODE_OPTIONS.map((opt) => (
              <button
                key={opt.value}
                type="button"
                onClick={() => setMode(opt.value)}
                className={cn(
                  'rounded-eldir border px-3 py-1.5 font-mono text-xs uppercase tracking-caps transition-colors',
                  mode === opt.value
                    ? 'border-eldir-orange bg-eldir-orange/10 text-eldir-ink'
                    : 'border-eldir-gray-3 text-eldir-gray hover:text-eldir-ink',
                )}
              >
                {opt.label}
              </button>
            ))}
          </div>
          <p className="mb-3 font-mono text-2xs text-eldir-gray">
            {MODE_OPTIONS.find((m) => m.value === mode)?.description}
          </p>

          <label className="block">
            <span className="eldir-caps mb-1 block">Texte d'entrée</span>
            <textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              rows={8}
              placeholder="Colle ici un fichier .env, un log, un fragment de code…"
              className="w-full rounded-eldir border border-eldir-gray-3 bg-eldir-paper px-3 py-2 font-mono text-xs text-eldir-ink focus:border-eldir-orange focus:outline-none"
            />
          </label>

          <div className="mt-3 flex justify-end">
            <button
              type="button"
              onClick={run}
              disabled={transform.isPending}
              className="rounded-eldir bg-eldir-orange px-4 py-2 font-mono text-xs font-semibold uppercase tracking-caps text-white hover:bg-eldir-orange/90 disabled:opacity-50"
            >
              {transform.isPending ? 'traitement local…' : 'lancer'}
            </button>
          </div>

          {error && (
            <p className="mt-3 font-mono text-xs text-eldir-red">{error}</p>
          )}

          {output !== null && (
            <div className="mt-4">
              <span className="eldir-caps mb-1 block">Résultat</span>
              <pre className="whitespace-pre-wrap break-words rounded-eldir border border-eldir-gray-3 bg-eldir-paper p-3 font-mono text-xs text-eldir-ink">
                {output}
              </pre>
              <p className="mt-2 font-mono text-2xs text-eldir-gray">
                ℹ️ Cette transformation a été faite par Ollama en local.
                Anthropic n'a reçu aucune de ces données.
              </p>
            </div>
          )}
        </section>
      )}
    </main>
  );
}

function Kv({ k, v }: { k: string; v: string }): JSX.Element {
  return (
    <div className="flex justify-between gap-2 border-b border-dotted border-eldir-gray-3 pb-1">
      <span className="text-eldir-gray">{k}</span>
      <span className="truncate text-eldir-ink">{v}</span>
    </div>
  );
}
