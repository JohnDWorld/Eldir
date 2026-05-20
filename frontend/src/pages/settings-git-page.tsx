/**
 * SettingsGitPage - gestion des PAT GitHub/Forgejo.
 */

import { useEffect, useState } from 'react';

import { ApiError } from '@/lib/api/client';
import {
  useDeleteGitCredential,
  useGitCredentials,
  useGitHubOauthConfig,
  useGitHubOauthStart,
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

  // Bandeau retour OAuth (?github=connected | error)
  const [oauthBanner, setOauthBanner] = useState<
    { kind: 'success' | 'error'; message: string } | null
  >(null);
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const status = params.get('github');
    if (!status) return;
    if (status === 'connected') {
      setOauthBanner({ kind: 'success', message: 'GitHub connecté avec succès.' });
    } else if (status === 'error') {
      setOauthBanner({
        kind: 'error',
        message: `Échec OAuth GitHub : ${params.get('reason') ?? 'inconnu'}.`,
      });
    }
    // Nettoie l'URL pour ne pas re-trigger au refresh
    params.delete('github');
    params.delete('reason');
    const newSearch = params.toString();
    const url = window.location.pathname + (newSearch ? `?${newSearch}` : '');
    window.history.replaceState(null, '', url);
  }, []);

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

      {oauthBanner && (
        <div
          className={
            oauthBanner.kind === 'success'
              ? 'rounded-eldir border border-eldir-green bg-eldir-green/10 px-4 py-3 font-mono text-xs text-eldir-green'
              : 'rounded-eldir border border-eldir-red bg-eldir-red/10 px-4 py-3 font-mono text-xs text-eldir-red'
          }
        >
          {oauthBanner.message}
        </div>
      )}

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

      <GitHubOauthSection />
      <CredentialForm provider="github" />
      <CredentialForm provider="forgejo" />
    </main>
  );
}

function GitHubOauthSection(): JSX.Element | null {
  const config = useGitHubOauthConfig();
  const start = useGitHubOauthStart();
  const [error, setError] = useState<string | null>(null);

  if (config.isPending) return null;
  if (!config.data?.enabled) {
    return (
      <section className="rounded-eldir border border-dashed border-eldir-gray-3 bg-eldir-paper p-4">
        <div className="eldir-caps">Connect with GitHub</div>
        <p className="mt-2 text-sm text-eldir-ink-2">
          OAuth GitHub n'est pas configuré sur ce serveur Eldir. Pour l'activer,
          crée une{' '}
          <a
            href="https://github.com/settings/applications/new"
            target="_blank"
            rel="noreferrer"
            className="text-eldir-orange underline"
          >
            OAuth App GitHub
          </a>{' '}
          et renseigne <span className="font-mono">GITHUB_OAUTH_CLIENT_ID</span> et{' '}
          <span className="font-mono">GITHUB_OAUTH_CLIENT_SECRET</span> dans l'env
          du backend. En attendant, utilise un PAT ci-dessous.
        </p>
      </section>
    );
  }

  const handleConnect = async () => {
    setError(null);
    try {
      const res = await start.mutateAsync();
      window.location.href = res.authorize_url;
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Erreur lors du démarrage OAuth.');
    }
  };

  return (
    <section className="rounded-eldir border border-eldir-gray-3 bg-eldir-cream p-4">
      <div className="eldir-caps">Connect with GitHub</div>
      <h2 className="mt-1 font-mono text-base font-semibold text-eldir-ink">
        Connexion OAuth GitHub
      </h2>
      <p className="mt-2 text-sm text-eldir-ink-2">
        Autorise Eldir à accéder à tes repos. Le token (scopes :{' '}
        <span className="font-mono">repo</span>,{' '}
        <span className="font-mono">read:user</span>) est chiffré (Fernet) avant
        d'être persisté. Remplace tout PAT GitHub précédemment configuré.
      </p>
      {error && (
        <div className="mt-3 rounded-eldir border border-eldir-red bg-eldir-red/10 px-3 py-2 font-mono text-xs text-eldir-red">
          {error}
        </div>
      )}
      <button
        type="button"
        onClick={handleConnect}
        disabled={start.isPending}
        className="mt-4 inline-flex items-center gap-2 rounded-eldir bg-eldir-ink px-4 py-2 font-mono text-xs font-semibold uppercase tracking-caps text-eldir-paper hover:bg-eldir-ink-2 disabled:opacity-50"
      >
        <svg
          xmlns="http://www.w3.org/2000/svg"
          viewBox="0 0 16 16"
          width="14"
          height="14"
          fill="currentColor"
          aria-hidden="true"
        >
          <path d="M8 0C3.58 0 0 3.58 0 8a8 8 0 0 0 5.47 7.59c.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.01 8.01 0 0 0 16 8c0-4.42-3.58-8-8-8Z" />
        </svg>
        {start.isPending ? 'redirection…' : 'Se connecter avec GitHub'}
      </button>
    </section>
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
