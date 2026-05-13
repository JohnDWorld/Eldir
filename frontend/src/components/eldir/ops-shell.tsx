/**
 * OpsShell — chrome desktop Mission Control : topbar + telemetry strip.
 * Contenu principal injecté en `children`.
 *
 * Mobile-first: en < md, on retombe sur une stack verticale ; les rails
 * latéraux du contenu seront gérés par les pages à l'aide de `OpsLayout`.
 */

import type { ReactNode } from 'react';

import { Avatar } from '@/components/eldir/avatar';
import { Tile } from '@/components/eldir/tile';
import { APP_NAME } from '@/lib/constants';
import { cn } from '@/lib/utils';

interface TopTab {
  key: string;
  label: string;
  active?: boolean;
}

interface OpsShellProps {
  tabs: readonly TopTab[];
  rightInfo?: ReactNode;
  telemetry?: readonly TelemetryItem[];
  children: ReactNode;
}

export interface TelemetryItem {
  label: string;
  value: ReactNode;
  sub?: ReactNode;
  spark?: readonly number[];
}

export function OpsShell({
  tabs,
  rightInfo,
  telemetry,
  children,
}: OpsShellProps): JSX.Element {
  return (
    <div className="flex h-full flex-col bg-eldir-paper">
      {/* Topbar */}
      <header className="flex h-[42px] items-center gap-3.5 border-b border-eldir-gray-3 bg-eldir-cream-2 px-4">
        <span className="font-mono text-[13px] font-bold tracking-wider">
          {APP_NAME.toUpperCase()}
          <span className="text-eldir-orange">·</span>CTL
        </span>
        <nav className="hidden gap-0.5 md:flex">
          {tabs.map((t) => (
            <span
              key={t.key}
              className={cn(
                '-mb-px px-3.5 py-2.5 font-mono text-[11px] font-semibold uppercase tracking-caps',
                t.active
                  ? 'border-b-2 border-eldir-orange text-eldir-ink'
                  : 'border-b-2 border-transparent text-eldir-gray',
              )}
            >
              {t.label}
            </span>
          ))}
        </nav>
        <div className="flex-1" />
        {rightInfo && (
          <div className="hidden font-mono text-[11px] text-eldir-gray md:block">
            {rightInfo}
          </div>
        )}
        <Avatar size={24}>J</Avatar>
      </header>

      {/* Telemetry strip */}
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
