/**
 * StateDot - pastille animée par état de session.
 * Cf. DA/shared.jsx · STATES + DA/tokens.css · .dot.*
 */

import { SESSION_STATE_LABEL, type SessionState } from '@/lib/constants';
import { cn } from '@/lib/utils';

const SIZE_CLASSES: Record<6 | 7 | 8 | 9 | 10, string> = {
  6: 'h-1.5 w-1.5',
  7: 'h-[7px] w-[7px]',
  8: 'h-2 w-2',
  9: 'h-[9px] w-[9px]',
  10: 'h-2.5 w-2.5',
};

const STATE_CLASS: Record<SessionState, string> = {
  idle: 'eldir-dot--idle',
  thinking: 'eldir-dot--thinking',
  tool_use: 'eldir-dot--tool',
  waiting_input: 'eldir-dot--input',
  blocked: 'eldir-dot--blocked',
};

export interface StateDotProps {
  state: SessionState;
  size?: 6 | 7 | 8 | 9 | 10;
  className?: string;
  /**
   * Pastille purement visuelle quand le libellé est déjà écrit à côté
   * (StatePill). Sinon un lecteur d'écran annonçait l'état deux fois.
   */
  decorative?: boolean;
}

export function StateDot({
  state,
  size = 8,
  className,
  decorative = false,
}: StateDotProps): JSX.Element {
  return (
    <span
      {...(decorative
        ? { 'aria-hidden': true }
        : { role: 'img', 'aria-label': `état : ${SESSION_STATE_LABEL[state]}` })}
      className={cn('eldir-dot', SIZE_CLASSES[size], STATE_CLASS[state], className)}
    />
  );
}
