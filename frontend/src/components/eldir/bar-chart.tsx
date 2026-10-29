/**
 * BarChart - barres depuis zéro, pour les séries par jour.
 *
 * Remplace la sparkline sur la page Coûts. Deux raisons : `Spark` est
 * normalisée entre son minimum et son maximum, donc une dépense qui passe de
 * 0,26 à 0,62 $ remplissait toute la hauteur comme si elle avait explosé ; et
 * elle était rendue sur 16 px de haut quelle que soit la hauteur demandée, ce
 * qui donnait un trait écrasé au milieu d'un cadre vide.
 *
 * Ici la base est à zéro, donc la hauteur d'une barre est proportionnelle à
 * la valeur, et chaque barre porte son jour et sa valeur.
 */

import { cn } from '@/lib/utils';

export interface BarPoint {
  /** Clé stable (la date ISO du jour). */
  key: string;
  /** Libellé sous la barre : « 23 oct ». */
  label: string;
  value: number;
  /** Valeur affichée au-dessus de la barre. */
  display: string;
}

interface BarChartProps {
  points: readonly BarPoint[];
  /** Décrit la série pour un lecteur d'écran. */
  caption: string;
  className?: string;
}

export function BarChart({ points, caption, className }: BarChartProps): JSX.Element {
  const max = Math.max(...points.map((p) => p.value), 0);

  return (
    <figure className={cn('m-0', className)}>
      <figcaption className="sr-only">{caption}</figcaption>
      <div className="flex h-32 items-stretch gap-1.5" role="list">
        {points.map((point) => {
          // 2 % minimum : un jour à zéro doit rester visible comme un jour
          // compté, et non disparaître du graphique.
          const hauteur = max > 0 ? Math.max((point.value / max) * 100, 2) : 2;
          const vide = point.value === 0;
          return (
            <div
              key={point.key}
              role="listitem"
              aria-label={`${point.label} : ${point.display}`}
              className="flex min-w-0 flex-1 flex-col justify-end gap-1.5"
            >
              <div
                className={cn(
                  'truncate text-center font-mono text-2xs tabular-nums',
                  vide ? 'text-eldir-gray' : 'font-semibold text-eldir-ink',
                )}
              >
                {point.display}
              </div>
              <div
                style={{ height: `${hauteur}%` }}
                className={cn(
                  'rounded-sm',
                  vide ? 'bg-eldir-gray-3' : 'bg-eldir-orange/70',
                )}
              />
            </div>
          );
        })}
      </div>
      <div className="mt-2 flex gap-1.5 border-t border-eldir-gray-3 pt-2">
        {points.map((point) => (
          <div
            key={point.key}
            className="min-w-0 flex-1 truncate text-center font-mono text-2xs text-eldir-gray"
          >
            {point.label}
          </div>
        ))}
      </div>
    </figure>
  );
}
