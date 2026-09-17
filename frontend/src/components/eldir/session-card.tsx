/**
 * SessionCard - carte session dans la grille Mission Control desktop.
 * L'état se lit sur la pastille. Plus de bordure gauche colorée de 3px :
 * elle doublait l'information et alourdissait la grille.
 */

import { Clock } from 'lucide-react';

import { StatePill } from '@/components/eldir/state-pill';
import type { SessionState } from '@/lib/constants';
import { cn } from '@/lib/utils';

export interface SessionCardData {
  id: string;
  projectSlug: string;
  state: SessionState;
  summary: string | null;
  duration: string;
}

interface SessionCardProps {
  data: SessionCardData;
  selected?: boolean;
  onClick?: () => void;
}

export function SessionCard({ data, selected, onClick }: SessionCardProps): JSX.Element {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        'w-full rounded-eldir border border-eldir-gray-3 bg-eldir-cream p-3 text-left transition-colors hover:border-eldir-gray-2 hover:bg-eldir-cream-2',
        selected && 'ring-1 ring-eldir-orange',
      )}
    >
      <div className="flex items-center justify-between gap-2">
        <span className="min-w-0 truncate font-mono text-xs font-semibold text-eldir-ink">
          {data.projectSlug} <span className="text-eldir-gray">/ {data.id}</span>
        </span>
        <span className="shrink-0">
          <StatePill state={data.state} />
        </span>
      </div>
      {data.summary && (
        <p className="mt-2 line-clamp-2 text-[11px] leading-relaxed text-eldir-ink-2">
          {data.summary}
        </p>
      )}
      <div className="mt-2.5 flex items-center gap-1 font-mono text-2xs text-eldir-gray">
        <Clock size={11} aria-hidden="true" />
        <span>{data.duration}</span>
      </div>
    </button>
  );
}
