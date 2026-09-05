/**
 * OpsShell - chrome interne de la page Ops (telemetry strip + contenu).
 *
 * La topbar globale (brand + nav + avatar) est fournie par `AuthedLayout` via
 * `AppTopbar`. OpsShell ne s'occupe plus que de la bande télémétrie et de
 * l'espace de contenu.
 */

import type { CSSProperties, ReactNode } from 'react';

import { Tile } from '@/components/eldir/tile';

interface OpsShellProps {
  telemetry?: readonly TelemetryItem[];
  children: ReactNode;
}

export interface TelemetryItem {
  label: string;
  value: ReactNode;
  sub?: ReactNode;
  spark?: readonly number[];
}

export function OpsShell({ telemetry, children }: OpsShellProps): JSX.Element {
  return (
    <div className="flex h-full flex-col">
      {telemetry && telemetry.length > 0 && (
        // Six tuiles sur une ligne de 375px donnent 49px chacune : les
        // chiffres débordaient de leur cadre. Sur mobile on passe donc en
        // trois colonnes qui se replient, la ligne unique reprend à `md`.
        <section
          className="grid grid-cols-3 gap-2 border-b border-eldir-gray-3 px-3 py-2.5 md:gap-2.5 md:px-4 md:[grid-template-columns:repeat(var(--tiles),minmax(0,1fr))]"
          style={{ '--tiles': telemetry.length } as CSSProperties}
        >
          {telemetry.map((t) => (
            <Tile
              key={t.label}
              label={t.label}
              value={t.value}
              {...(t.sub !== undefined ? { sub: t.sub } : {})}
              {...(t.spark ? { spark: t.spark } : {})}
            />
          ))}
        </section>
      )}

      <div className="min-h-0 flex-1">{children}</div>
    </div>
  );
}
