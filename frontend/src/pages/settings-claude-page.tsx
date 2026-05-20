/**
 * SettingsClaudePage - gestion des credentials Claude post-install.
 * - Affiche les credentials existants (masqués).
 * - Permet de remplacer le token Pro/Max ou la clé API.
 * - Permet de supprimer un credential.
 */

import { useState } from 'react';

import { ApiError } from '@/lib/api/client';
import {
  useClaudeCredentials,
  useCreateClaudeCredential,
  useDeleteClaudeCredential,
} from '@/lib/api/queries';
import type { ClaudeCredentialKind, ClaudeCredentialRead } from '@/lib/types/api';
import { cn } from '@/lib/utils';

const KIND_LABEL: Record<ClaudeCredentialKind, string> = {
  oauth_token: 'Token Pro/Max',
  api_key: 'Clé API Console',
};

export function SettingsClaudePage(): JSX.Element {
  const credentials = useClaudeCredentials();
  const createMut = useCreateClaudeCredential();
  const deleteMut = useDeleteClaudeCredential();

  const items = credentials.data ?? [];

  return (
    <main className="mx-auto flex max-w-3xl flex-col gap-6 p-4 md:p-8">
      <header>
        <div className="eldir-caps">Settings · claude</div>
        <h1 className="mt-1 font-mono text-xl font-bold text-eldir-ink">
          Credentials Anthropic
        </h1>
        <p className="mt-2 text-sm text-eldir-ink-2">
          Eldir utilise <span className="font-mono">CLAUDE_CODE_OAUTH_TOKEN</span> en priorité
          (compte Pro/Max), avec <span className="font-mono">ANTHROPIC_API_KEY</span> en
          fallback. Les valeurs sont chiffrées en base.
        </p>
      </header>

      <section className="rounded-eldir border border-eldir-gray-3 bg-eldir-cream">
        <div className="border-b border-eldir-gray-3 px-4 py-3">
          <span className="eldir-caps">Actuels</span>
        </div>
        {items.length === 0 ? (
          <p className="px-4 py-6 font-mono text-xs text-eldir-gray">
            Aucun credential configuré.
          </p>
        ) : (
          <ul className="divide-y divide-eldir-gray-3">
            {items.map((c) => (
              <CredentialRow
                key={c.id}
                cred={c}
                onDelete={() => deleteMut.mutate(c.id)}
                deleting={deleteMut.isPending}
              />
            ))}
          </ul>
        )}
      </section>

      <CredentialForm
        kind="oauth_token"
        title="Mettre à jour le token Pro/Max"
        helper={
          <>
            Génère un nouveau token longue durée sur n'importe quelle machine avec :
            <pre className="my-2 rounded-eldir bg-eldir-ink p-3 font-mono text-xs text-eldir-cream">
              npx -y @anthropic-ai/claude-code setup-token
            </pre>
            Connecte-toi à ton compte Pro/Max, puis colle le token <span className="font-mono">sk-ant-oat…</span> ci-dessous.
          </>
        }
        submitting={createMut.isPending}
        onSubmit={(value, label) =>
          createMut.mutateAsync({ kind: 'oauth_token', value, label: label || null })
        }
      />

      <CredentialForm
        kind="api_key"
        title="Mettre à jour la clé API Console (fallback)"
        helper={
          <>
            Récupère ta clé API sur{' '}
            <a
              href="https://platform.claude.com"
              target="_blank"
              rel="noreferrer"
              className="text-eldir-orange underline"
            >
              platform.claude.com
            </a>
            . Format attendu : <span className="font-mono">sk-ant-api…</span>.
          </>
        }
        submitting={createMut.isPending}
        onSubmit={(value, label) =>
          createMut.mutateAsync({ kind: 'api_key', value, label: label || null })
        }
      />
    </main>
  );
}

function CredentialRow({
  cred,
  onDelete,
  deleting,
}: {
  cred: ClaudeCredentialRead;
  onDelete: () => void;
  deleting: boolean;
}): JSX.Element {
  return (
    <li className="flex items-center justify-between gap-3 px-4 py-3">
      <div>
        <div className="font-mono text-xs font-semibold text-eldir-ink">
          {KIND_LABEL[cred.kind]}
          {cred.label && <span className="ml-2 text-eldir-gray">· {cred.label}</span>}
        </div>
        <div className="mt-1 font-mono text-xs text-eldir-gray">
          {cred.masked_value}
        </div>
      </div>
      <button
        type="button"
        onClick={onDelete}
        disabled={deleting}
        className="rounded-eldir border border-eldir-gray-3 px-3 py-2 font-mono text-xs uppercase tracking-caps text-eldir-red hover:bg-eldir-red/10 disabled:opacity-50"
      >
        supprimer
      </button>
    </li>
  );
}

function CredentialForm({
  kind,
  title,
  helper,
  onSubmit,
  submitting,
}: {
  kind: ClaudeCredentialKind;
  title: string;
  helper: React.ReactNode;
  onSubmit: (value: string, label: string) => Promise<unknown>;
  submitting: boolean;
}): JSX.Element {
  const [value, setValue] = useState('');
  const [label, setLabel] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  const handle = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setSuccess(false);
    if (value.trim().length < 8) {
      setError('Valeur trop courte.');
      return;
    }
    try {
      await onSubmit(value.trim(), label.trim());
      setValue('');
      setLabel('');
      setSuccess(true);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Erreur lors de la sauvegarde.');
    }
  };

  return (
    <section className="rounded-eldir border border-eldir-gray-3 bg-eldir-cream p-4">
      <div className="eldir-caps">{KIND_LABEL[kind]}</div>
      <h2 className="mt-1 font-mono text-base font-semibold text-eldir-ink">{title}</h2>
      <div className="mt-2 text-sm text-eldir-ink-2">{helper}</div>

      <form onSubmit={handle} className="mt-4 flex flex-col gap-3">
        <label className="block">
          <span className="eldir-caps mb-1 block">Valeur</span>
          <input
            type="password"
            value={value}
            onChange={(e) => setValue(e.target.value)}
            placeholder={kind === 'oauth_token' ? 'sk-ant-oat…' : 'sk-ant-api…'}
            className="w-full rounded-eldir border border-eldir-gray-3 bg-eldir-paper px-3 py-2 font-mono text-sm text-eldir-ink focus:border-eldir-orange focus:outline-none"
          />
        </label>
        <label className="block">
          <span className="eldir-caps mb-1 block">Label (optionnel)</span>
          <input
            type="text"
            value={label}
            onChange={(e) => setLabel(e.target.value)}
            maxLength={120}
            className="w-full rounded-eldir border border-eldir-gray-3 bg-eldir-paper px-3 py-2 font-mono text-sm text-eldir-ink focus:border-eldir-orange focus:outline-none"
          />
        </label>
        {error && (
          <div className="rounded-eldir border border-eldir-red bg-eldir-red/10 px-3 py-2 font-mono text-xs text-eldir-red">
            {error}
          </div>
        )}
        {success && (
          <div className="rounded-eldir border border-eldir-green bg-eldir-green/10 px-3 py-2 font-mono text-xs text-eldir-green">
            Credential enregistré.
          </div>
        )}
        <button
          type="submit"
          disabled={submitting}
          className={cn(
            'self-start rounded-eldir bg-eldir-orange px-4 py-2 font-mono text-xs font-semibold uppercase tracking-caps text-white hover:bg-eldir-orange/90 disabled:opacity-50',
          )}
        >
          {submitting ? 'enregistrement…' : 'enregistrer'}
        </button>
      </form>
    </section>
  );
}
