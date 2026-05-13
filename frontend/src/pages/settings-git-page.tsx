/**
 * SettingsGitPage — gestion des PAT GitHub/Forgejo.
 */

import { useState } from 'react';

import { ApiError } from '@/lib/api/client';
import {
  useDeleteGitCredential,
  useGitCredentials,
  useUpsertGitCredential,
} from '@/lib/api/queries';
import type { Provider } from '@/lib/constants';
import type { GitCredentialRead } from '@/lib/types/api';

const PROVIDER_LABEL: Record<Provider, string> = {
  github: 'GitHub',
  forgejo: 'Forgejo',
};

const HELPERS: Record<Provider, JSX.Element> = {
  github: (
    <>
      Génère un <span className="font-mono">Personal Access Token</span> sur{' '}
      <a
        href="https://github.com/settings/tokens?type=beta"
        target="_blank"
        rel="noreferrer"
        className="text-eldir-orange underline"
      >
        github.com/settings/tokens
      </a>
      . Scopes requis : <span className="font-mono">repo</span>,{' '}
      <span className="font-mono">read:user</span>.
    </>
  ),
  forgejo: (
    <>
      Génère un Personal Access Token depuis ton instance Forgejo (Settings → Applications → Generate New Token).
      Renseigne aussi l'URL de l'instance (ex. <span className="font-mono">https://forgejo.example.com</span>).
    </>
  ),
};

export function SettingsGitPage(): JSX.Element {
  const credentials = useGitCredentials();
  const deleteMut = useDeleteGitCredential();

  return (
    <main className="mx-auto flex max-w-3xl flex-col gap-6 p-4 md:p-8">
      <header>
        <div className="eldir-caps">Settings · git</div>
        <h1 className="mt-1 font-mono text-xl font-bold text-eldir-ink">
          Credentials Git providers
        </h1>
        <p className="mt-2 text-sm text-eldir-ink-2">
          Eldir utilise ces tokens pour lister tes repos, en cloner, en créer et
          publier des pull requests. Stockage chiffré (Fernet) en base.
        </p>
      </header>

      <section className="rounded-eldir border border-eldir-gray-3 bg-eldir-cream">
        <div className="border-b border-eldir-gray-3 px-4 py-3">
          <span className="eldir-caps">Actuels</span>
        </div>
        {credentials.isPending ? (
          <p className="px-4 py-6 font-mono text-xs text-eldir-gray">chargement…</p>
        ) : (credentials.data ?? []).length === 0 ? (
          <p className="px-4 py-6 font-mono text-xs text-eldir-gray">
            Aucun credential configuré.
          </p>
        ) : (
          <ul className="divide-y divide-eldir-gray-3">
            {(credentials.data ?? []).map((c) => (
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

      <CredentialForm provider="github" />
      <CredentialForm provider="forgejo" />
    </main>
  );
}

function CredentialRow({
  cred,
  onDelete,
  deleting,
}: {
  cred: GitCredentialRead;
  onDelete: () => void;
  deleting: boolean;
}): JSX.Element {
  return (
    <li className="flex items-center justify-between gap-3 px-4 py-3">
      <div>
        <div className="font-mono text-xs font-semibold text-eldir-ink">
          {PROVIDER_LABEL[cred.provider]}
          {cred.label && <span className="ml-2 text-eldir-gray">· {cred.label}</span>}
        </div>
        <div className="mt-1 font-mono text-xs text-eldir-gray">
          {cred.masked_token}
          {cred.base_url && <span className="ml-2">{cred.base_url}</span>}
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

function CredentialForm({ provider }: { provider: Provider }): JSX.Element {
  const upsert = useUpsertGitCredential();
  const [token, setToken] = useState('');
  const [label, setLabel] = useState('');
  const [baseUrl, setBaseUrl] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  const handle = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setSuccess(false);
    if (token.trim().length < 8) {
      setError('Token trop court.');
      return;
    }
    if (provider === 'forgejo' && !baseUrl.trim()) {
      setError("L'URL de l'instance Forgejo est requise.");
      return;
    }
    try {
      await upsert.mutateAsync({
        provider,
        token: token.trim(),
        label: label.trim() || null,
        base_url: baseUrl.trim() || null,
      });
      setToken('');
      setLabel('');
      setBaseUrl('');
      setSuccess(true);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Erreur lors de la sauvegarde.');
    }
  };

  return (
    <section className="rounded-eldir border border-eldir-gray-3 bg-eldir-cream p-4">
      <div className="eldir-caps">{PROVIDER_LABEL[provider]}</div>
      <h2 className="mt-1 font-mono text-base font-semibold text-eldir-ink">
        Configurer un PAT {PROVIDER_LABEL[provider]}
      </h2>
      <div className="mt-2 text-sm text-eldir-ink-2">{HELPERS[provider]}</div>

      <form onSubmit={handle} className="mt-4 flex flex-col gap-3">
        {provider === 'forgejo' && (
          <label className="block">
            <span className="eldir-caps mb-1 block">URL de l'instance</span>
            <input
              type="url"
              value={baseUrl}
              onChange={(e) => setBaseUrl(e.target.value)}
              placeholder="https://forgejo.example.com"
              className="w-full rounded-eldir border border-eldir-gray-3 bg-eldir-paper px-3 py-2 font-mono text-sm text-eldir-ink focus:border-eldir-orange focus:outline-none"
            />
          </label>
        )}
        <label className="block">
          <span className="eldir-caps mb-1 block">Token</span>
          <input
            type="password"
            value={token}
            onChange={(e) => setToken(e.target.value)}
            placeholder={provider === 'github' ? 'ghp_… ou github_pat_…' : 'token Forgejo'}
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
            Token enregistré.
          </div>
        )}
        <button
          type="submit"
          disabled={upsert.isPending}
          className="self-start rounded-eldir bg-eldir-orange px-4 py-2 font-mono text-xs font-semibold uppercase tracking-caps text-white hover:bg-eldir-orange/90 disabled:opacity-50"
        >
          {upsert.isPending ? 'enregistrement…' : 'enregistrer'}
        </button>
      </form>
    </section>
  );
}
