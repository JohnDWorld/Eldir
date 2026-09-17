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
        'inline-flex shrink-0 items-center gap-1.5 whitespace-nowrap font-mono text-[10px] uppercase leading-[1.35] tracking-caps text-eldir-gray',
        className,
      )}
    >
      <StateDot state={state} size={7} decorative />
      {SESSION_STATE_LABEL[state]}
    </span>
  );
}
