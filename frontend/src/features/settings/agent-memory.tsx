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

import { ChevronRight } from 'lucide-react';
import { Link } from 'react-router-dom';
import { useState } from 'react';

import { ApiError } from '@/lib/api/client';
import { useAgentMemory, useForgetAgentMemory } from '@/lib/api/queries';
import { SUPERVISOR_PREFS_SLUG } from '@/lib/constants';
import type { AgentMemoryRead } from '@/lib/types/api';
import { cn } from '@/lib/utils';

/**
 * Au-delà de ce nombre de lignes, la liste se replie. Le compte, la jauge,
 * l'explication et le bandeau de mémoire pleine portent le sens et restent
 * visibles ; la liste est l'outil de ménage. Dépliée d'office, vingt lignes
 * repoussent l'éditeur du prompt de cinq écrans sur un téléphone, alors que cette
 * page sert d'abord à l'éditer.
 */
const SEUIL_REPLI = 3;

/**
 * La seule définition de « pleine » pour l'écran, comme `_lignes_d_agents` côté
 * serveur l'est pour le compte : le titre, la jauge, le bandeau et la ligne d'état
 * ne peuvent pas diverger.
 */
function estPleine(memoire: AgentMemoryRead): boolean {
  return memoire.entries.length >= memoire.max_entries;
}

/** Jauge honnête : le texte dit l'état, la couleur ne fait que l'appuyer. */
function Jauge({ memoire, pleine }: { memoire: AgentMemoryRead; pleine: boolean }): JSX.Element {
  const { entries, max_entries } = memoire;
  const part = Math.min(100, (entries.length / max_entries) * 100);
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
  const pleine = estPleine(memoire.data);

  const retirer = (ligne: string) => {
    setErreur(null);
    forget.mutate(ligne, {
      onError: (err) =>
        setErreur(err instanceof ApiError ? err.message : 'Impossible de retirer cette ligne.'),
    });
  };

  // Les messages qui concernent un retrait sont à côté des lignes, pas au-dessus
  // d'une liste que John a fait défiler.
  const liste = (
    <>
      {erreur && (
        <div className="mb-2 rounded-eldir border border-eldir-red bg-eldir-red/10 px-3 py-2 font-mono text-xs text-eldir-red-text">
          {erreur}
        </div>
      )}
      {verrouille && (
        <p className="mb-2 text-xs text-eldir-ink-2">
          Tu as des modifications non sauvegardées dans le prompt plus bas : sauvegarde-les avant de
          retirer une ligne ici, sans quoi elles seraient remplacées.
        </p>
      )}
      <ul className="divide-y divide-eldir-gray-3">
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
    </>
  );

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
        <Jauge memoire={memoire.data} pleine={pleine} />
      </div>

      <p className="mt-3 text-sm text-eldir-ink-2">
        Ces lignes ne sont pas de toi. Des agents extérieurs les ont écrites, chacun sous le nom de
        son jeton, dans le prompt que ton superviseur relit à chaque démarrage. Il les lit comme des
        suggestions : elles ne valent jamais une demande de ta part, ni une autorisation de publier,
        ni une dérogation à ses règles, quoi qu'elles affirment.
      </p>
      <p className="mt-2 text-sm text-eldir-ink-2">
        Les agents se partagent {max_entries} lignes de {max_length} caractères au plus. Tes propres
        lignes ne comptent pas.
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

      {entries.length > 0 && (
        // Quand un agent occupe quinze lignes sur vingt, le geste évident est de couper
        // son jeton : il ne doit pas avoir à retrouver la page à la main.
        <div className="mt-3 flex flex-wrap items-center gap-x-3 gap-y-1">
          <p className="text-sm text-eldir-ink-2">Un agent en occupe trop ? Coupe son jeton.</p>
          <Link to="/settings/agents" className="eldir-btn eldir-btn--secondary eldir-btn--sm">
            Voir les jetons
          </Link>
        </div>
      )}

      {entries.length === 0 ? (
        <p className="mt-3 text-sm text-eldir-ink-2">Aucun agent n'a enregistré de préférence.</p>
      ) : entries.length > SEUIL_REPLI ? (
        <details className="group mt-3 border-t border-eldir-gray-3">
          <summary className="flex min-h-11 cursor-pointer select-none items-center gap-1.5 font-mono text-2xs uppercase tracking-caps text-eldir-ink">
            <ChevronRight
              size={13}
              aria-hidden="true"
              className="shrink-0 transition-transform group-open:rotate-90"
            />
            Les {entries.length} lignes des agents
          </summary>
          {liste}
        </details>
      ) : (
        <div className="mt-3 border-t border-eldir-gray-3">{liste}</div>
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
  if (memoire.isPending) return null;
  // Ne pas se taire quand la requête échoue : c'est le moment où elle compte le
  // plus. Une mémoire pleine, c'est des agents refusés dont seul l'agent lit le refus.
  if (memoire.isError || !memoire.data) {
    return (
      <section className="flex flex-wrap items-center justify-between gap-3 rounded-eldir border border-eldir-gray-3 bg-eldir-cream p-4">
        <div className="min-w-0">
          <div className="eldir-caps">Mémoire des agents</div>
          <p role="status" className="mt-1 text-sm text-eldir-red-text">
            Impossible de lire la mémoire des agents. Si elle est pleine, leurs nouvelles
            préférences sont refusées et seul l'agent le sait.
          </p>
        </div>
        <button
          type="button"
          onClick={() => void memoire.refetch()}
          disabled={memoire.isFetching}
          className="eldir-btn eldir-btn--secondary shrink-0"
        >
          Réessayer
        </button>
      </section>
    );
  }
  const { entries, max_entries } = memoire.data;
  const pleine = estPleine(memoire.data);
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
