/**
 * StatePill - dot + label pour annoncer l'état d'une session inline.
 */

import { StateDot } from '@/components/eldir/state-dot';
import { SESSION_STATE_LABEL, type SessionState } from '@/lib/constants';
import { cn } from '@/lib/utils';

export interface StatePillProps {
  state: SessionState;
  className?: string;
}

export function StatePill({ state, className }: StatePillProps): JSX.Element {
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1.5 font-mono text-[10px] uppercase tracking-caps text-eldir-gray',
        className,
      )}
    >
      <StateDot state={state} size={7} />
      {SESSION_STATE_LABEL[state]}
    </span>
  );
}
