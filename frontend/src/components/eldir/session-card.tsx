/**
 * SessionCard - carte session dans la grille Mission Control desktop.
 * Bordure gauche colorée selon l'état (cf. DA/d1.jsx · D1DeskHome).
 */

import { StatePill } from '@/components/eldir/state-pill';
import type { SessionState } from '@/lib/constants';
import { cn } from '@/lib/utils';

const STATE_BORDER: Record<SessionState, string> = {
  idle: 'border-l-eldir-gray-2',
  thinking: 'border-l-eldir-orange',
  tool_use: 'border-l-eldir-gold',
  waiting_input: 'border-l-eldir-amber',
  blocked: 'border-l-eldir-red',
};

export interface SessionCardData {
  id: string;
  projectSlug: string;
  state: SessionState;
  summary: string | null;
  duration: string;
  tokens: string;
  cost: string;
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
        'w-full rounded-eldir border border-eldir-gray-3 border-l-[3px] bg-eldir-cream p-3 text-left transition-colors hover:bg-eldir-cream-2',
        STATE_BORDER[data.state],
        selected && 'ring-1 ring-eldir-orange',
      )}
    >
      <div className="flex items-center justify-between">
        <span className="font-mono text-xs font-semibold text-eldir-ink">
          {data.projectSlug} <span className="text-eldir-gray">/ {data.id}</span>
        </span>
        <StatePill state={data.state} />
      </div>
      {data.summary && (
        <p className="mt-2 line-clamp-2 text-[11px] leading-relaxed text-eldir-ink-2">
          {data.summary}
        </p>
      )}
      <div className="mt-2.5 flex gap-2.5 font-mono text-2xs text-eldir-gray">
        <span>⏱ {data.duration}</span>
        <span>◊ {data.tokens}</span>
        <span>{data.cost}</span>
      </div>
    </button>
  );
}
