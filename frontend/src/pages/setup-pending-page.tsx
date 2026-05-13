/**
 * SetupPendingPage — affichée quand le bootstrap n'a pas encore été fait.
 * Eldir attend que l'administrateur lance `scripts/install-eldir.sh`.
 */

import { useSetupStatus } from '@/lib/api/queries';

export function SetupPendingPage(): JSX.Element {
  const status = useSetupStatus();

  return (
    <main className="flex h-full items-center justify-center bg-eldir-paper p-4">
      <div className="w-full max-w-xl rounded-eldir border border-eldir-gray-3 bg-eldir-cream p-6 md:p-10">
        <div className="eldir-caps mb-2">Eldir · installation</div>
        <h1 className="font-mono text-2xl font-bold text-eldir-ink">
          Cette instance n'est pas encore configurée
        </h1>
        <p className="mt-4 text-sm text-eldir-ink-2">
          Pour terminer l'installation, exécute le script d'install à la racine du repo
          sur la machine hôte :
        </p>
        <pre className="mt-3 overflow-x-auto rounded-eldir bg-eldir-ink p-4 font-mono text-xs text-eldir-cream">
          {'./scripts/install-eldir.sh'}
        </pre>
        <p className="mt-4 text-sm text-eldir-ink-2">
          Il créera l'administrateur, te connectera à ton compte Claude Pro/Max (ou
          configurera une clé API Console) et persistera les credentials chiffrés en
          base. Cette page se mettra à jour automatiquement une fois l'installation
          complétée.
        </p>
        <div className="mt-6 flex items-center gap-3 font-mono text-xs text-eldir-gray">
          <span>version :</span>
          <span className="text-eldir-ink">{status.data?.eldir_version ?? '…'}</span>
          <span>·</span>
          <button
            type="button"
            onClick={() => status.refetch()}
            className="text-eldir-orange hover:underline"
          >
            re-vérifier
          </button>
        </div>
      </div>
    </main>
  );
}
