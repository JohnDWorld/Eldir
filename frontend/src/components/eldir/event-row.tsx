/**
 * EventRow - ligne du panneau "EVENTS" (rail de droite).
 * Cf. DA/d1.jsx · D1DeskHome.
 */

import { cn } from '@/lib/utils';

export interface EventEntry {
  time: string;
  source: string; // ex. "s1" ou "-"
  message: string;
}

export function EventRow({ entry }: { entry: EventEntry }): JSX.Element {
  const isSystem = entry.source === '-';
  return (
    <div
      className={cn(
        'flex gap-2 border-b border-dotted border-eldir-gray-3 py-1 font-mono text-[11px] leading-snug text-eldir-ink-2',
      )}
    >
      <span className="text-eldir-gray">{entry.time}</span>
      <span
        className={cn(
          'w-6 truncate',
          isSystem ? 'text-eldir-gray' : 'text-eldir-orange',
        )}
      >
        {entry.source}
      </span>
      <span className="flex-1 truncate">{entry.message}</span>
    </div>
  );
}
