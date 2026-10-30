/**
 * AgentTokensPanel - créer et couper les jetons des agents extérieurs.
 *
 * Un jeton qu'on ne peut pas révoquer est un jeton qu'on ne peut pas émettre :
 * « Révoquer » est donc sur chaque ligne active, visible, pas dans un menu.
 *
 * Le clair n'est rendu qu'une fois, à la création, et Eldir ne le conserve pas.
 * L'écran le dit AVANT de le montrer (dans le formulaire, puis au-dessus du
 * jeton), et ne le réaffiche jamais : le clair vit dans l'état du composant,
 * jamais dans la liste (qui ne le reçoit pas) ni dans le cache des requêtes.
 */

import { useState } from 'react';

import { ApiError } from '@/lib/api/client';
import { useAgentTokens, useCreateAgentToken, useRevokeAgentToken } from '@/lib/api/queries';
import { formatAge, formatDateTime } from '@/lib/format';
import type { AgentTokenCreated, AgentTokenRead } from '@/lib/types/api';
import { cn } from '@/lib/utils';

// Borne du libellé côté serveur (`agent_token_service`), répétée ici pour que le
// champ cesse d'accepter des caractères plutôt que d'échouer à l'envoi.
const LIBELLE_MAX = 80;

type Copie = 'ok' | 'impossible' | null;

export function AgentTokensPanel(): JSX.Element {
  const [revele, setRevele] = useState<AgentTokenCreated | null>(null);

  return (
    <>
      <FormulaireJeton bloque={revele !== null} onCree={setRevele} />
      {/* Sous le formulaire, pas au-dessus : sur un téléphone, un bloc inséré au-dessus
          du bouton qu'on vient d'appuyer sortirait de l'écran, et le jeton passerait inaperçu. */}
      {revele && <JetonRevele jeton={revele} onClose={() => setRevele(null)} />}
      <ListeJetons />
    </>
  );
}

function FormulaireJeton({
  bloque,
  onCree,
}: {
  bloque: boolean;
  onCree: (jeton: AgentTokenCreated) => void;
}): JSX.Element {
  const create = useCreateAgentToken();
  const [libelle, setLibelle] = useState('');
  const [erreur, setErreur] = useState<string | null>(null);

  const handle = async (e: React.FormEvent) => {
    e.preventDefault();
    setErreur(null);
    const nom = libelle.trim();
    if (!nom) {
      setErreur('Donne un nom à cet agent.');
      return;
    }
    try {
      const cree = await create.mutateAsync({ label: nom });
      // Le clair ne reste pas dans le cache des mutations (cf. `gcTime: 0` du hook).
      create.reset();
      setLibelle('');
      onCree(cree);
    } catch (err) {
      setErreur(err instanceof ApiError ? err.message : 'Création impossible.');
    }
  };

  return (
    <section className="rounded-eldir border border-eldir-gray-3 bg-eldir-cream p-4">
      <div className="eldir-caps">Nouveau jeton</div>
      <h2 className="mt-1 font-sans text-base font-semibold text-eldir-ink">Brancher un agent</h2>
      <p className="mt-2 text-sm text-eldir-ink-2">
        Le jeton ne sera montré qu'une seule fois, juste après sa création. Eldir ne le conserve pas
        : si tu le perds, il faudra en créer un autre et révoquer celui-ci.
      </p>

      <form onSubmit={handle} className="mt-4 flex flex-col gap-3">
        <label className="block">
          <span className="eldir-caps mb-1 block">Nom de l'agent</span>
          <input
            type="text"
            value={libelle}
            onChange={(e) => setLibelle(e.target.value)}
            maxLength={LIBELLE_MAX}
            placeholder="ex. assistant de bureau"
            className="w-full rounded-eldir border border-eldir-gray-3 bg-eldir-paper px-3 py-2 font-mono text-sm text-eldir-ink focus:border-eldir-orange"
          />
          <span className="mt-1 block text-xs text-eldir-ink-2">
            Ce nom signe ce que l'agent écrit dans les préférences du superviseur, et dit dans ton
            historique lequel a parlé.
          </span>
        </label>
        {erreur && (
          <div className="rounded-eldir border border-eldir-red bg-eldir-red/10 px-3 py-2 font-mono text-xs text-eldir-red-text">
            {erreur}
          </div>
        )}
        {bloque && (
          <p className="text-xs text-eldir-ink-2">
            Ferme le jeton affiché ci-dessous avant d'en créer un autre : il ne pourrait plus être
            relu.
          </p>
        )}
        <button
          type="submit"
          disabled={create.isPending || bloque}
          className="eldir-btn eldir-btn--primary self-start"
        >
          {create.isPending ? 'création…' : 'Créer un jeton'}
        </button>
      </form>
    </section>
  );
}

/**
 * Le seul endroit où le clair s'affiche. L'avertissement vient AVANT le jeton
 * dans le document, pour qu'on le lise (et que le lecteur d'écran le lise)
 * avant de voir la valeur.
 */
function JetonRevele({
  jeton,
  onClose,
}: {
  jeton: AgentTokenCreated;
  onClose: () => void;
}): JSX.Element {
  const [copie, setCopie] = useState<Copie>(null);

  const copier = async () => {
    try {
      await navigator.clipboard.writeText(jeton.token);
      setCopie('ok');
    } catch {
      // Hors contexte sécurisé (Eldir servi en http sur un réseau local),
      // `navigator.clipboard` n'existe pas : le jeton reste sélectionnable.
      setCopie('impossible');
    }
  };

  return (
    <section
      role="status"
      aria-labelledby="jeton-cree-titre"
      className="rounded-eldir border border-eldir-orange bg-eldir-cream p-4"
    >
      <div className="eldir-caps">Jeton créé</div>
      <h2
        id="jeton-cree-titre"
        className="mt-1 break-words font-sans text-base font-semibold text-eldir-ink"
      >
        {jeton.label}
      </h2>
      <p className="mt-2 rounded-eldir border border-eldir-amber/40 bg-eldir-amber/10 px-3 py-2 text-sm font-semibold text-eldir-amber-text">
        Copie-le maintenant : il ne sera plus affiché. Eldir ne le conserve pas.
      </p>
      <code className="mt-3 block select-all break-all rounded-eldir bg-eldir-console p-3 font-mono text-xs text-eldir-console-fg">
        {jeton.token}
      </code>
      <div className="mt-3 flex flex-wrap items-center gap-2">
        <button type="button" onClick={copier} className="eldir-btn eldir-btn--secondary">
          Copier
        </button>
        <button type="button" onClick={onClose} className="eldir-btn eldir-btn--primary">
          J'ai copié le jeton
        </button>
        {copie === 'ok' && (
          <span className="font-mono text-2xs uppercase tracking-caps text-eldir-green-text">
            copié
          </span>
        )}
        {copie === 'impossible' && (
          <span className="text-xs text-eldir-red-text">
            Copie impossible ici : sélectionne le jeton à la main.
          </span>
        )}
      </div>
    </section>
  );
}

function ListeJetons(): JSX.Element {
  const jetons = useAgentTokens();
  const revoke = useRevokeAgentToken();
  const [erreur, setErreur] = useState<string | null>(null);

  const revoquer = (jeton: AgentTokenRead) => {
    if (
      !confirm(
        `Révoquer « ${jeton.label} » ? L'agent sera coupé à sa prochaine requête, et ce jeton ne pourra pas être rétabli.`,
      )
    ) {
      return;
    }
    setErreur(null);
    revoke.mutate(jeton.id, {
      onError: (err) => setErreur(err instanceof ApiError ? err.message : 'Révocation impossible.'),
    });
  };

  const items = jetons.data ?? [];

  return (
    <section className="rounded-eldir border border-eldir-gray-3 bg-eldir-cream">
      <div className="border-b border-eldir-gray-3 px-4 py-3">
        <span className="eldir-caps">Jetons émis</span>
      </div>
      {erreur && (
        <div className="m-4 rounded-eldir border border-eldir-red bg-eldir-red/10 px-3 py-2 font-mono text-xs text-eldir-red-text">
          {erreur}
        </div>
      )}
      {jetons.isPending && (
        <p className="px-4 py-6 font-mono text-xs text-eldir-gray">chargement…</p>
      )}
      {jetons.isError && (
        <p className="px-4 py-6 font-mono text-xs text-eldir-red-text">
          Impossible de charger les jetons.
        </p>
      )}
      {jetons.data && items.length === 0 && (
        <p className="px-4 py-6 text-sm text-eldir-ink-2">
          Aucun jeton : aucun agent extérieur ne peut piloter Eldir.
        </p>
      )}
      {items.length > 0 && (
        <ul className="divide-y divide-eldir-gray-3">
          {items.map((jeton) => (
            <LigneJeton
              key={jeton.id}
              jeton={jeton}
              onRevoke={() => revoquer(jeton)}
              enCours={revoke.isPending && revoke.variables === jeton.id}
            />
          ))}
        </ul>
      )}
    </section>
  );
}

function LigneJeton({
  jeton,
  onRevoke,
  enCours,
}: {
  jeton: AgentTokenRead;
  onRevoke: () => void;
  enCours: boolean;
}): JSX.Element {
  const revoque = jeton.revoked_at !== null;
  return (
    <li className="flex flex-col gap-2 px-4 py-3 sm:flex-row sm:items-center sm:justify-between sm:gap-3">
      <div className="min-w-0">
        <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
          <span
            className={cn(
              'break-words font-sans text-sm font-semibold',
              revoque ? 'text-eldir-gray line-through' : 'text-eldir-ink',
            )}
          >
            {jeton.label}
          </span>
          <span
            className={cn(
              'font-mono text-2xs uppercase tracking-caps',
              revoque ? 'text-eldir-red-text' : 'text-eldir-green-text',
            )}
          >
            {revoque ? 'révoqué' : 'actif'}
          </span>
        </div>
        <div className="mt-1 font-mono text-2xs text-eldir-gray">
          créé le {formatDateTime(jeton.created_at)}
          {' · '}
          {jeton.revoked_at !== null ? (
            <>révoqué le {formatDateTime(jeton.revoked_at)}</>
          ) : jeton.last_used_at !== null ? (
            <span title={formatDateTime(jeton.last_used_at)}>
              dernier usage {formatAge(jeton.last_used_at)}
            </span>
          ) : (
            <>jamais utilisé</>
          )}
        </div>
      </div>
      {!revoque && (
        <button
          type="button"
          onClick={onRevoke}
          disabled={enCours}
          aria-label={`Révoquer le jeton ${jeton.label}`}
          className="eldir-btn eldir-btn--danger eldir-btn--sm shrink-0 self-start sm:self-auto"
        >
          {enCours ? 'révocation…' : 'Révoquer'}
        </button>
      )}
    </li>
  );
}
