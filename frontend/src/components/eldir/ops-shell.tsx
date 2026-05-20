/**
 * OpsShell - chrome interne de la page Ops (telemetry strip + contenu).
 *
 * La topbar globale (brand + nav + avatar) est fournie par `AuthedLayout` via
 * `AppTopbar`. OpsShell ne s'occupe plus que de la bande télémétrie et de
 * l'espace de contenu.
 */

import type { ReactNode } from 'react';

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
        <section
          className="grid gap-2.5 border-b border-eldir-gray-3 px-4 py-2.5"
          style={{
            gridTemplateColumns: `repeat(${telemetry.length}, minmax(0, 1fr))`,
          }}
        >
          {telemetry.map((t) => (
            <Tile
              key={t.label}
              label={t.label}
              value={t.value}
              {...(t.sub !== undefined ? { sub: t.sub } : {})}
              {...(t.spark ? { spark: t.spark, sparkWidth: 120, sparkHeight: 16 } : {})}
            />
          ))}
        </section>
      )}

      <div className="min-h-0 flex-1">{children}</div>
    </div>
  );
}
