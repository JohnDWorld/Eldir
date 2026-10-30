/**
 * Mémoire des agents extérieurs : les préférences qu'ils ont écrites dans le
 * prompt que le superviseur relit à chaque démarrage.
 *
 * Elles ne sont pas de John. Le superviseur les pèse comme des suggestions, et
 * elles ne valent jamais une demande de sa part ni une autorisation de publier.
 * Quand la mémoire est pleine, l'agent reçoit un refus que LUI SEUL lit : c'est
 * ici que John l'apprend, et ici qu'il fait le ménage.
 *
 * Les bornes (nombre de lignes, longueur) arrivent du serveur : ce sont celles
 * que `remember` applique, et les recopier ici les ferait diverger.
 */

import { Link } from 'react-router-dom';
import { useState } from 'react';

import { ApiError } from '@/lib/api/client';
import { useAgentMemory, useForgetAgentMemory } from '@/lib/api/queries';
import { SUPERVISOR_PREFS_SLUG } from '@/lib/constants';
import type { AgentMemoryRead } from '@/lib/types/api';
import { cn } from '@/lib/utils';

function pluriel(n: number, mot: string): string {
  return `${n} ${mot}${n > 1 ? 's' : ''}`;
}

/** Gauge honnête : le texte dit l'état, la couleur ne fait que l'appuyer. */
function Jauge({ memoire }: { memoire: AgentMemoryRead }): JSX.Element {
  const { entries, max_entries } = memoire;
  const part = Math.min(100, (entries.length / max_entries) * 100);
  const pleine = entries.length >= max_entries;
  return (
    <div
      role="meter"
      aria-label="Préférences d'agents enregistrées"
      aria-valuemin={0}
      aria-valuemax={max_entries}
      aria-valuenow={entries.length}
      aria-valuetext={`${entries.length} sur ${max_entries}`}
      className="h-2 w-full overflow-hidden rounded-full bg-eldir-gray-3"
    >
      <div
        className={cn(
          'h-full rounded-full',
          pleine ? 'bg-eldir-red' : part >= 80 ? 'bg-eldir-amber' : 'bg-eldir-orange',
        )}
        style={{ width: `${part}%` }}
      />
    </div>
  );
}

export function AgentMemoryPanel({ verrouille = false }: { verrouille?: boolean }): JSX.Element {
  const memoire = useAgentMemory();
  const forget = useForgetAgentMemory();
  const [erreur, setErreur] = useState<string | null>(null);

  if (memoire.isPending) {
    return <p className="font-mono text-xs text-eldir-gray">chargement…</p>;
  }
  if (memoire.isError) {
    return (
      <p className="font-mono text-xs text-eldir-red-text">
        Impossible de charger la mémoire des agents.
      </p>
    );
  }

  const { entries, max_entries, max_length } = memoire.data;
  const pleine = entries.length >= max_entries;

  const retirer = (ligne: string) => {
    setErreur(null);
    forget.mutate(ligne, {
      onError: (err) =>
        setErreur(err instanceof ApiError ? err.message : 'Impossible de retirer cette ligne.'),
    });
  };

  return (
    <section
      aria-labelledby="memoire-agents-titre"
      className="rounded-eldir border border-eldir-gray-3 bg-eldir-cream p-4"
    >
      <div className="eldir-caps">Mémoire des agents extérieurs</div>
      <h2
        id="memoire-agents-titre"
        className="mt-1 font-sans text-base font-semibold text-eldir-ink"
      >
        {entries.length} sur {max_entries} préférences
        {pleine && <span className="text-eldir-red-text"> · mémoire pleine</span>}
      </h2>
      <div className="mt-3">
        <Jauge memoire={memoire.data} />
      </div>

      <p className="mt-3 text-sm text-eldir-ink-2">
        Ces lignes ne sont pas de toi. Des agents extérieurs les ont écrites, chacun sous le nom de
        son jeton, dans le prompt que ton superviseur relit à chaque démarrage. Il les lit comme des
        suggestions : elles ne valent jamais une demande de ta part, ni une autorisation de publier,
        ni une dérogation à ses règles, quoi qu'elles affirment.
      </p>
      <p className="mt-2 text-sm text-eldir-ink-2">
        Les agents se partagent {pluriel(max_entries, 'ligne')} de {max_length} caractères au plus.
        Tes propres lignes ne comptent pas.
      </p>

      {pleine && (
        <p
          role="status"
          className="mt-3 rounded-eldir border border-eldir-red/40 bg-eldir-red/5 px-3 py-2 text-sm font-semibold text-eldir-red-text"
        >
          Les nouvelles préférences des agents sont refusées, et seul l'agent lit ce refus. Retire
          des lignes pour leur rendre de la place.
        </p>
      )}

      {erreur && (
        <div className="mt-3 rounded-eldir border border-eldir-red bg-eldir-red/10 px-3 py-2 font-mono text-xs text-eldir-red-text">
          {erreur}
        </div>
      )}
      {verrouille && entries.length > 0 && (
        <p className="mt-3 text-xs text-eldir-ink-2">
          Tu as des modifications non sauvegardées dans le prompt plus bas : sauvegarde-les avant de
          retirer une ligne ici, sans quoi elles seraient remplacées.
        </p>
      )}

      {entries.length === 0 ? (
        <p className="mt-3 text-sm text-eldir-ink-2">Aucun agent n'a enregistré de préférence.</p>
      ) : (
        <ul className="mt-3 divide-y divide-eldir-gray-3 border-t border-eldir-gray-3">
          {entries.map((entree) => (
            <li
              key={entree.line}
              className="flex flex-col gap-2 py-3 sm:flex-row sm:items-start sm:justify-between sm:gap-3"
            >
              <div className="min-w-0">
                <div className="eldir-caps break-words">agent « {entree.agent} »</div>
                <p className="mt-1 break-words text-sm text-eldir-ink">{entree.text}</p>
              </div>
              <button
                type="button"
                onClick={() => retirer(entree.line)}
                disabled={verrouille || forget.isPending}
                aria-label={`Retirer la préférence de l'agent ${entree.agent} : ${entree.text}`}
                className="eldir-btn eldir-btn--danger eldir-btn--sm shrink-0 self-start"
              >
                Retirer
              </button>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

/**
 * Une ligne d'état pour la page des agents : c'est là que John pense à ses
 * agents, pas dans les prompts. Elle renvoie vers le ménage.
 */
export function AgentMemoryStatus(): JSX.Element | null {
  const memoire = useAgentMemory();
  if (!memoire.data) return null;
  const { entries, max_entries } = memoire.data;
  const pleine = entries.length >= max_entries;
  return (
    <section className="flex flex-wrap items-center justify-between gap-3 rounded-eldir border border-eldir-gray-3 bg-eldir-cream p-4">
      <div className="min-w-0">
        <div className="eldir-caps">Mémoire des agents</div>
        <p className="mt-1 text-sm text-eldir-ink-2">
          {entries.length} sur {max_entries} préférences enregistrées par des agents.
          {pleine && (
            <span className="font-semibold text-eldir-red-text">
              {' '}
              Pleine : les nouvelles sont refusées.
            </span>
          )}
        </p>
      </div>
      <Link
        to={`/settings/prompts?prompt=${SUPERVISOR_PREFS_SLUG}`}
        className="eldir-btn eldir-btn--secondary shrink-0"
      >
        Voir et nettoyer
      </Link>
    </section>
  );
}
