/**
 * AutonomyPanel - ce que le superviseur peut faire seul sur ce projet.
 *
 * Décoché (le défaut), il ouvre les PR et John merge. Coché, il merge quand la
 * CI est verte et lance la commande de déploiement déclarée ici, et seulement
 * celle-là.
 */

import { useEffect, useState } from 'react';

import { ApiError } from '@/lib/api/client';
import { useProjects, useUpdateProjectAutonomy } from '@/lib/api/queries';
import type { ProjectAutonomyUpdate } from '@/lib/types/api';

interface AutonomyPanelProps {
  projectId: string;
}

export function AutonomyPanel({ projectId }: AutonomyPanelProps): JSX.Element {
  const projects = useProjects();
  const update = useUpdateProjectAutonomy(projectId);
  const project = projects.data?.find((p) => p.id === projectId);
  const saved = project?.deploy_command ?? '';
  const [command, setCommand] = useState(saved);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setCommand(saved);
  }, [saved]);

  const save = async (body: ProjectAutonomyUpdate) => {
    setError(null);
    try {
      await update.mutateAsync(body);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Enregistrement impossible.');
    }
  };

  const autonomous = project?.autonomous === true;

  return (
    <div className="rounded-eldir border border-eldir-gray-3 bg-eldir-paper p-4">
      <div className="eldir-caps">Autonomie</div>

      <label className="mt-3 flex items-start gap-2">
        <input
          type="checkbox"
          checked={autonomous}
          disabled={!project || update.isPending}
          onChange={(e) => void save({ autonomous: e.target.checked })}
          className="mt-0.5"
        />
        <span className="text-xs text-eldir-ink">
          Autonome : le superviseur peut merger et déployer seul
        </span>
      </label>

      <p className="mt-2 text-xs text-eldir-ink-2">
        Décoché, il ouvre les PR et c&apos;est toi qui merges. Coché, il merge
        quand la CI est verte, puis lance la commande ci-dessous si le
        changement doit partir en production.
      </p>

      <label className="mt-3 block">
        <span className="eldir-caps mb-1 block">Commande de déploiement</span>
        <input
          value={command}
          onChange={(e) => setCommand(e.target.value)}
          spellCheck={false}
          autoCapitalize="none"
          autoCorrect="off"
          placeholder="cd /srv/projet && ./deploy.sh"
          className="eldir-field min-w-0 bg-eldir-cream font-mono text-xs"
        />
      </label>
      <p className="mt-1 font-mono text-2xs text-eldir-gray">
        Lancée par la machine du projet ci-dessus. Vide si la forge déploie au
        merge.
      </p>

      {error && (
        <div className="mt-3 rounded-eldir border border-eldir-red bg-eldir-red/10 px-3 py-2 font-mono text-2xs text-eldir-red-text">
          {error}
        </div>
      )}

      <div className="mt-3">
        <button
          type="button"
          onClick={() => void save({ deploy_command: command.trim() })}
          disabled={!project || command.trim() === saved || update.isPending}
          className="eldir-btn eldir-btn--secondary"
        >
          {update.isPending ? 'enregistrement…' : 'enregistrer la commande'}
        </button>
      </div>
    </div>
  );
}
