/**
 * ToolchainPanel - les outils que le repo a besoin d'avoir sur le serveur.
 *
 * Le conteneur n'embarque que git, node, python et le CLI Claude : un agent
 * sur un repo Flutter ne peut pas lancer `flutter analyze`. Le projet déclare
 * ici les commandes qui installent ce qu'il lui faut, et on les lance à la
 * demande. Jamais automatiquement : ça coûte du disque et du temps, donc ça
 * se décide et ça s'affiche.
 */

import { useState } from 'react';

import { ApiError } from '@/lib/api/client';
import {
  useDeleteToolchain,
  useInstallToolchain,
  useToolchain,
} from '@/lib/api/queries';

interface ToolchainPanelProps {
  projectId: string;
  /** Commandes du formulaire, pour prévenir si elles ne sont pas enregistrées. */
  draftCommands: string[];
  /**
   * Commandes réellement enregistrées, lues depuis le template lui-même.
   * Surtout pas depuis `GET /toolchain` : ce cache n'est pas rafraîchi par
   * l'enregistrement du template, et le bouton « installer » restait grisé
   * alors que les commandes étaient bien en base.
   */
  savedCommands: string[];
}

function formatSize(bytes: number | null): string {
  if (bytes === null) return 'taille inconnue';
  const gb = bytes / 1024 ** 3;
  if (gb >= 1) return `${gb.toFixed(1)} Go`;
  return `${Math.max(1, Math.round(bytes / 1024 ** 2))} Mo`;
}

export function ToolchainPanel({
  projectId,
  draftCommands,
  savedCommands,
}: ToolchainPanelProps): JSX.Element {
  const toolchain = useToolchain(projectId);
  const install = useInstallToolchain(projectId);
  const remove = useDeleteToolchain(projectId);
  const [error, setError] = useState<string | null>(null);
  const [logOpen, setLogOpen] = useState(false);

  const data = toolchain.data;
  const saved = savedCommands;
  const unsaved =
    JSON.stringify(draftCommands) !== JSON.stringify(saved) &&
    !(draftCommands.length === 0 && saved.length === 0);
  const installing = data?.status === 'installing';

  const run = async (action: 'install' | 'remove') => {
    setError(null);
    try {
      if (action === 'install') await install.mutateAsync();
      else await remove.mutateAsync();
      await toolchain.refetch();
    } catch (err) {
      setError(
        err instanceof ApiError ? err.message : 'Erreur sur le toolchain.',
      );
    }
  };

  return (
    <div className="rounded-eldir border border-eldir-gray-3 bg-eldir-paper p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="eldir-caps">Toolchain du repo</div>
        <StatusPill status={data?.status ?? 'absent'} />
      </div>

      <p className="mt-2 text-xs text-eldir-ink-2">
        Ces commandes tournent sur le serveur, une seule fois, dans un dossier
        propre au projet. Les sessions le retrouvent dans{' '}
        <code className="font-mono text-eldir-ink">$ELDIR_TOOLCHAIN</code>, et{' '}
        <code className="font-mono text-eldir-ink">$ELDIR_TOOLCHAIN/bin</code>{' '}
        est en tête de leur PATH. Une installation à la fois sur le serveur.
      </p>

      {saved.length === 0 && !installing ? (
        <p className="mt-3 font-mono text-2xs text-eldir-gray">
          Aucune commande déclarée. Ajoute-les au-dessus (une par ligne),
          enregistre, puis installe.
        </p>
      ) : (
        <div className="mt-3 flex flex-col gap-2">
          {data?.status === 'installed' && (
            <div className="font-mono text-2xs text-eldir-gray">
              {formatSize(data.size_bytes)} sur disque
              {data.installed_at
                ? ` · installé le ${new Date(data.installed_at).toLocaleString()}`
                : ''}
            </div>
          )}
          {data?.stale && data.status !== 'installing' && (
            <div className="rounded-eldir border border-eldir-gold bg-eldir-gold/10 px-3 py-2 font-mono text-2xs text-eldir-ink">
              Les commandes enregistrées ont changé depuis l&apos;installation.
              Réinstalle pour que le serveur corresponde à ce qui est déclaré.
            </div>
          )}
          {data?.detail && (
            <div className="rounded-eldir border border-eldir-red bg-eldir-red/10 px-3 py-2 font-mono text-2xs text-eldir-red">
              {data.detail}
            </div>
          )}
        </div>
      )}

      {unsaved && (
        <div className="mt-3 rounded-eldir border border-eldir-gold bg-eldir-gold/10 px-3 py-2 font-mono text-2xs text-eldir-ink">
          Les commandes affichées ne sont pas encore enregistrées. Clique sur
          « enregistrer » avant d&apos;installer.
        </div>
      )}

      {error && (
        <div className="mt-3 rounded-eldir border border-eldir-red bg-eldir-red/10 px-3 py-2 font-mono text-2xs text-eldir-red">
          {error}
        </div>
      )}

      <div className="mt-3 flex flex-wrap items-center gap-2">
        <button
          type="button"
          onClick={() => run('install')}
          disabled={installing || saved.length === 0 || install.isPending}
          className="min-h-11 rounded-eldir bg-eldir-orange px-4 py-2 font-mono text-xs font-semibold uppercase tracking-caps text-white hover:bg-eldir-orange/90 disabled:opacity-40"
        >
          {installing
            ? 'installation…'
            : data?.status === 'installed'
              ? 'réinstaller'
              : 'installer'}
        </button>
        {data && data.status !== 'absent' && (
          <button
            type="button"
            onClick={() => {
              if (confirm('Supprimer le toolchain et rendre le disque ?')) {
                void run('remove');
              }
            }}
            disabled={installing || remove.isPending}
            className="min-h-11 rounded-eldir border border-eldir-gray-3 px-3 py-2 font-mono text-xs uppercase tracking-caps text-eldir-red hover:bg-eldir-red/10 disabled:opacity-40"
          >
            supprimer
          </button>
        )}
        {data?.log && (
          <button
            type="button"
            onClick={() => setLogOpen((v) => !v)}
            className="min-h-11 font-mono text-2xs uppercase tracking-caps text-eldir-orange hover:underline"
          >
            {logOpen ? 'masquer le log' : 'voir le log'}
          </button>
        )}
      </div>

      {logOpen && data?.log && (
        <pre className="mt-3 max-h-64 overflow-auto rounded-eldir bg-eldir-ink p-3 font-mono text-2xs leading-relaxed text-eldir-cream">
          {data.log}
        </pre>
      )}
    </div>
  );
}

function StatusPill({ status }: { status: string }): JSX.Element {
  const styles: Record<string, string> = {
    absent: 'border-eldir-gray-3 text-eldir-gray',
    installing: 'border-eldir-orange text-eldir-orange animate-pulse',
    installed: 'border-eldir-green text-eldir-green',
    error: 'border-eldir-red text-eldir-red',
  };
  const labels: Record<string, string> = {
    absent: 'non installé',
    installing: 'installation',
    installed: 'installé',
    error: 'échec',
  };
  return (
    <span
      className={`rounded-eldir border px-2 py-1 font-mono text-2xs uppercase tracking-caps ${
        styles[status] ?? styles.absent
      }`}
    >
      {labels[status] ?? status}
    </span>
  );
}
