/**
 * RemotePanel - brancher le projet sur la machine où il tourne.
 *
 * Adresse, utilisateur, et c'est tout : Eldir génère sa clé, la dépose et
 * vérifie. Le mot de passe n'est demandé que si la clé ne passe pas encore,
 * ne sert qu'à cette requête, et n'est ni stocké ni renvoyé.
 */

import { useEffect, useState } from 'react';

import { ApiError } from '@/lib/api/client';
import {
  useConnectRemote,
  useDisconnectRemote,
  useRemoteAccess,
} from '@/lib/api/queries';

interface RemotePanelProps {
  projectId: string;
}

export function RemotePanel({ projectId }: RemotePanelProps): JSX.Element {
  const remote = useRemoteAccess(projectId);
  const connect = useConnectRemote(projectId);
  const disconnect = useDisconnectRemote(projectId);

  const [host, setHost] = useState('');
  const [user, setUser] = useState('');
  const [port, setPort] = useState('22');
  const [password, setPassword] = useState('');
  const [needsPassword, setNeedsPassword] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const data = remote.data;
  const connected = data?.connected === true;

  useEffect(() => {
    if (!data?.configured) return;
    setHost((prev) => prev || (data.host ?? ''));
    setUser((prev) => prev || (data.user ?? ''));
    setPort((prev) => (prev === '22' ? String(data.port) : prev));
  }, [data]);

  const submit = async () => {
    setError(null);
    try {
      const state = await connect.mutateAsync({
        host: host.trim(),
        user: user.trim(),
        port: Number(port) || 22,
        password: password || null,
      });
      // Le mot de passe a servi (ou n'a pas servi) : dans les deux cas il ne
      // reste pas dans un champ de formulaire.
      setPassword('');
      setNeedsPassword(state.connected !== true);
    } catch (err) {
      setPassword('');
      setError(
        err instanceof ApiError ? err.message : 'Connexion impossible.',
      );
      setNeedsPassword(true);
    }
  };

  const remove = async () => {
    if (
      !window.confirm(
        'Retirer la clé Eldir de cette machine et oublier la connexion ?',
      )
    )
      return;
    setError(null);
    try {
      await disconnect.mutateAsync();
      setNeedsPassword(false);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Erreur à la révocation.');
    }
  };

  const champ =
    'h-11 w-full min-w-0 rounded-eldir border border-eldir-gray-3 bg-eldir-paper px-3 font-mono text-xs text-eldir-ink focus:border-eldir-orange focus:outline-none';

  return (
    <div className="rounded-eldir border border-eldir-gray-3 bg-eldir-paper p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="eldir-caps">Machine du projet</div>
        <span
          className={
            'rounded-eldir border px-2 py-1 font-mono text-2xs uppercase tracking-caps ' +
            (connected
              ? 'border-eldir-green bg-eldir-green/10 text-eldir-green'
              : data?.configured
                ? 'border-eldir-gold bg-eldir-gold/10 text-eldir-ink'
                : 'border-eldir-gray-3 text-eldir-gray')
          }
        >
          {connected
            ? 'connectée'
            : data?.configured
              ? 'à vérifier'
              : 'non connectée'}
        </span>
      </div>

      <p className="mt-2 text-xs text-eldir-ink-2">
        Eldir génère une clé dédiée à ce projet et la dépose sur la machine. Le
        mot de passe n&apos;est demandé que pour cette première fois : il ne
        sera ni stocké ni journalisé. Les sessions de ce projet pourront
        ensuite s&apos;y connecter, et seulement là.
      </p>

      <div className="mt-3 grid gap-2 sm:grid-cols-[2fr_1fr]">
        <label className="block">
          <span className="eldir-caps mb-1 block">Adresse</span>
          <input
            value={host}
            onChange={(e) => setHost(e.target.value)}
            spellCheck={false}
            autoCapitalize="none"
            autoCorrect="off"
            placeholder="192.0.2.10 ou serveur.exemple.fr"
            className={champ}
          />
        </label>
        <label className="block">
          <span className="eldir-caps mb-1 block">Port</span>
          <input
            value={port}
            onChange={(e) => setPort(e.target.value)}
            inputMode="numeric"
            className={champ}
          />
        </label>
        <label className="block sm:col-span-2">
          <span className="eldir-caps mb-1 block">Utilisateur</span>
          <input
            value={user}
            onChange={(e) => setUser(e.target.value)}
            spellCheck={false}
            autoCapitalize="none"
            autoCorrect="off"
            autoComplete="username"
            placeholder="deploy"
            className={champ}
          />
        </label>
        {needsPassword && !connected && (
          <label className="block sm:col-span-2">
            <span className="eldir-caps mb-1 block">
              Mot de passe (une seule fois)
            </span>
            <input
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              type="password"
              autoComplete="off"
              className={champ}
            />
          </label>
        )}
      </div>

      {data?.detail && !error && (
        <div className="mt-3 rounded-eldir border border-eldir-gold bg-eldir-gold/10 px-3 py-2 font-mono text-2xs text-eldir-ink">
          {data.detail}
        </div>
      )}

      {error && (
        <div className="mt-3 rounded-eldir border border-eldir-red bg-eldir-red/10 px-3 py-2 font-mono text-2xs text-eldir-red">
          {error}
        </div>
      )}

      {connected && data?.alias && (
        <p className="mt-3 font-mono text-2xs text-eldir-gray">
          Alias <code className="text-eldir-ink">{data.alias}</code>, accessible
          aux sessions via{' '}
          <code className="text-eldir-ink">$ELDIR_REMOTE_HOST</code>. La clé est
          retirée de la machine si tu supprimes le projet.
        </p>
      )}

      <div className="mt-3 flex flex-wrap items-center gap-2">
        <button
          type="button"
          onClick={submit}
          disabled={!host.trim() || !user.trim() || connect.isPending}
          className="min-h-11 rounded-eldir bg-eldir-orange px-4 py-2 font-mono text-xs font-semibold uppercase tracking-caps text-white hover:bg-eldir-orange/90 disabled:opacity-40"
        >
          {connect.isPending
            ? 'connexion…'
            : connected
              ? 'revérifier'
              : 'connecter au serveur'}
        </button>
        {data?.configured && (
          <button
            type="button"
            onClick={remove}
            disabled={disconnect.isPending}
            className="min-h-11 rounded-eldir border border-eldir-gray-3 px-4 py-2 font-mono text-xs uppercase tracking-caps text-eldir-gray hover:text-eldir-ink disabled:opacity-40"
          >
            {disconnect.isPending ? 'révocation…' : 'déconnecter'}
          </button>
        )}
      </div>
    </div>
  );
}
