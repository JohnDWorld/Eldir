/**
 * Tile - telemetry tile (cockpit). Label caps + valeur tabular-nums + sub or sparkline.
 * Cf. DA/d1.jsx · Tile + telemetry strip.
 */

import type { ReactNode } from 'react';

import { Spark } from '@/components/eldir/spark';
import { cn } from '@/lib/utils';

interface TileProps {
  label: string;
  value: ReactNode;
  sub?: ReactNode;
  spark?: readonly number[];
  sparkWidth?: number;
  sparkHeight?: number;
  className?: string;
}

export function Tile({
  label,
  value,
  sub,
  spark,
  sparkWidth = 70,
  sparkHeight = 14,
  className,
}: TileProps): JSX.Element {
  return (
    <div
      className={cn(
        'rounded-eldir border border-eldir-gray-3 bg-eldir-cream px-2.5 py-2',
        className,
      )}
    >
      <div className="font-mono text-2xs font-semibold uppercase tracking-caps text-eldir-gray">
        {label}
      </div>
      <div className="mt-1.5 text-[22px] font-bold leading-tight tabular-nums text-eldir-ink">
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
        <div className="mt-1 font-mono text-2xs text-eldir-gray">{sub}</div>
      ) : null}
    </div>
  );
}
