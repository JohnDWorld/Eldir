/**
 * Tile - telemetry tile (cockpit). Label caps + valeur tabular-nums + sub or sparkline.
 * Cf. DA/d1.jsx · Tile + telemetry strip.
 */

import type { ReactNode } from 'react';

import { Spark } from '@/components/eldir/spark';
import { cn } from '@/lib/utils';

/**
 * `alerte` : la tuile appelle une action (une session attend une réponse, une
 * autre est bloquée). Sans ça, « 1 en attente » avait exactement le même poids
 * que « 2 projets clonés », et l'oeil ne trouvait pas l'urgence.
 */
export type TileTone = 'neutre' | 'attention' | 'alerte';

interface TileProps {
  label: string;
  value: ReactNode;
  tone?: TileTone;
  sub?: ReactNode;
  spark?: readonly number[];
  sparkWidth?: number;
  sparkHeight?: number;
  className?: string;
}

export function Tile({
  label,
  value,
  tone = 'neutre',
  sub,
  spark,
  sparkWidth = 70,
  sparkHeight = 14,
  className,
}: TileProps): JSX.Element {
  return (
    <div
      className={cn(
        // `min-w-0` + `overflow-hidden` : dans une grille, un enfant garde
        // sinon la largeur de son contenu et pousse la page en scroll
        // horizontal. La valeur est tronquée, jamais coupée à cheval.
        'min-w-0 overflow-hidden rounded-eldir border px-2.5 py-2',
        tone === 'alerte'
          ? 'border-eldir-red/50 bg-eldir-red/5'
          : tone === 'attention'
            ? 'border-eldir-amber/50 bg-eldir-amber/5'
            : 'border-eldir-gray-3 bg-eldir-cream',
        className,
      )}
    >
      <div className="truncate font-mono text-2xs font-semibold uppercase tracking-caps text-eldir-gray">
        {label}
      </div>
      <div
        className={cn(
          'mt-1 truncate text-lg font-bold leading-tight tabular-nums md:mt-1.5 md:text-[22px]',
          tone === 'alerte'
            ? 'text-eldir-red-text'
            : tone === 'attention'
              ? 'text-eldir-amber-text'
              : 'text-eldir-ink',
        )}
      >
        {value}
      </div>
      {spark ? (
        <div className="mt-1">
          <Spark
            data={spark}
            width={sparkWidth}
            height={sparkHeight}
            fill="hsl(var(--eldir-orange) / 0.12)"
          />
        </div>
      ) : sub !== undefined ? (
        <div className="mt-1 break-words font-mono text-2xs leading-tight text-eldir-gray">
          {sub}
        </div>
      ) : null}
    </div>
  );
}
