/**
 * LogsPanel — flux temps réel multi-sessions sur fond ink.
 * Cf. DA/d1.jsx · D1DeskHome (bloc logs).
 */

import { cn } from '@/lib/utils';

export type LogTone = 'orange' | 'gold' | 'amber' | 'green' | 'red' | 'gray' | 'cream';

const TONE_CLASS: Record<LogTone, string> = {
  orange: 'text-eldir-orange',
  gold: 'text-eldir-gold',
  amber: 'text-eldir-amber',
  green: 'text-eldir-green',
  red: 'text-eldir-red',
  gray: 'text-eldir-gray-2',
  cream: 'text-eldir-cream',
};

export interface LogLine {
  id: string;
  prefix: { tone: LogTone; text: string };
  kind?: { tone: LogTone; text: string };
  message: string;
  messageTone?: LogTone;
}

interface LogsPanelProps {
  title?: string;
  lines: readonly LogLine[];
  className?: string;
}

export function LogsPanel({
  title = '// stream · all sessions',
  lines,
  className,
}: LogsPanelProps): JSX.Element {
  return (
    <div
      className={cn(
        'overflow-hidden rounded-eldir bg-eldir-ink p-3 font-mono text-[11px] leading-relaxed text-eldir-cream',
        className,
      )}
    >
      <div className="mb-1.5 text-eldir-gray-2">{title}</div>
      {lines.map((l) => (
        <div key={l.id} className="whitespace-nowrap">
          <span className={TONE_CLASS[l.prefix.tone]}>{l.prefix.text}</span>{' '}
          {l.kind && (
            <>
              <span className={TONE_CLASS[l.kind.tone]}>{l.kind.text}</span>{' '}
            </>
          )}
          <span className={TONE_CLASS[l.messageTone ?? 'cream']}>{l.message}</span>
        </div>
      ))}
    </div>
  );
}
