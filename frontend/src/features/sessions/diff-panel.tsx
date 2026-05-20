/**
 * DiffPanel - liste les fichiers modifiés par une session depuis sa base, et
 * affiche le patch unifié du fichier sélectionné.
 *
 * Calcule le diff côté backend via /sessions/{id}/diff puis /diff/file?path=…
 * La base est le merge-base entre HEAD et origin/<default_branch>, donc on
 * voit exactement ce que la session a ajouté, sans les commits arrivés sur
 * main depuis.
 */

import { useState } from 'react';

import { useSessionDiff, useSessionDiffFile } from '@/lib/api/queries';
import type { SessionDiffFile } from '@/lib/api/queries';
import { cn } from '@/lib/utils';

interface DiffPanelProps {
  sessionId: string;
}

const STATUS_LABEL: Record<string, string> = {
  A: 'add',
  M: 'mod',
  D: 'del',
  R: 'ren',
  C: 'cpy',
  T: 'typ',
  U: 'unm',
};

const STATUS_COLOR: Record<string, string> = {
  A: 'text-eldir-green',
  M: 'text-eldir-orange',
  D: 'text-eldir-red',
  R: 'text-eldir-gold',
  C: 'text-eldir-gold',
};

export function DiffPanel({ sessionId }: DiffPanelProps): JSX.Element {
  const diff = useSessionDiff(sessionId);
  const [selected, setSelected] = useState<string | null>(null);

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <header className="flex items-center justify-between border-b border-eldir-gray-3 bg-eldir-paper px-3 py-2">
        <span className="eldir-caps">Diff</span>
        <button
          type="button"
          onClick={() => diff.refetch()}
          disabled={diff.isFetching}
          className="font-mono text-2xs uppercase tracking-caps text-eldir-gray hover:text-eldir-ink disabled:opacity-50"
        >
          {diff.isFetching ? 'maj…' : '↻'}
        </button>
      </header>

      {diff.isPending && (
        <p className="px-3 py-4 font-mono text-2xs text-eldir-gray">chargement…</p>
      )}
      {diff.isError && (
        <p className="px-3 py-4 font-mono text-2xs text-eldir-red">
          {diff.error.message}
        </p>
      )}
      {diff.data && diff.data.files.length === 0 && (
        <p className="px-3 py-4 font-mono text-2xs text-eldir-gray">
          Aucun changement depuis la base ({diff.data.base_ref.slice(0, 8)}).
        </p>
      )}

      {diff.data && diff.data.files.length > 0 && (
        <>
          <ul className="max-h-[35%] min-h-[80px] overflow-y-auto border-b border-eldir-gray-3">
            {diff.data.files.map((f) => (
              <FileRow
                key={f.path}
                file={f}
                selected={selected === f.path}
                onClick={() => setSelected(f.path)}
              />
            ))}
          </ul>
          <div className="min-h-0 flex-1">
            {selected ? (
              <PatchView sessionId={sessionId} path={selected} />
            ) : (
              <p className="px-3 py-4 font-mono text-2xs text-eldir-gray">
                Sélectionne un fichier pour voir le patch.
              </p>
            )}
          </div>
        </>
      )}
    </div>
  );
}

function FileRow({
  file,
  selected,
  onClick,
}: {
  file: SessionDiffFile;
  selected: boolean;
  onClick: () => void;
}): JSX.Element {
  const statusColor = STATUS_COLOR[file.status] ?? 'text-eldir-gray';
  return (
    <li>
      <button
        type="button"
        onClick={onClick}
        className={cn(
          'flex w-full items-center gap-2 px-3 py-1.5 text-left font-mono text-2xs hover:bg-eldir-cream-2',
          selected && 'bg-eldir-cream text-eldir-ink',
        )}
      >
        <span className={cn('w-7 shrink-0 uppercase', statusColor)}>
          {STATUS_LABEL[file.status] ?? file.status}
        </span>
        <span className="min-w-0 flex-1 truncate text-eldir-ink-2">
          {file.path}
        </span>
        <span className="shrink-0 font-mono text-2xs">
          {file.additions > 0 && (
            <span className="text-eldir-green">+{file.additions}</span>
          )}
          {file.additions > 0 && file.deletions > 0 && ' '}
          {file.deletions > 0 && (
            <span className="text-eldir-red">-{file.deletions}</span>
          )}
        </span>
      </button>
    </li>
  );
}

function PatchView({
  sessionId,
  path,
}: {
  sessionId: string;
  path: string;
}): JSX.Element {
  const patch = useSessionDiffFile(sessionId, path);
  return (
    <div className="h-full min-w-0 overflow-y-auto bg-eldir-ink font-mono text-[11px] leading-relaxed text-eldir-cream">
      {patch.isPending && (
        <p className="px-3 py-3 text-eldir-gray-2">chargement…</p>
      )}
      {patch.isError && (
        <p className="px-3 py-3 text-eldir-red">{patch.error.message}</p>
      )}
      {patch.data && (
        <pre className="whitespace-pre-wrap break-words px-3 py-2">
          {patch.data.patch
            ? colorize(patch.data.patch)
            : 'aucun diff (fichier binaire ou identique)'}
        </pre>
      )}
    </div>
  );
}

/**
 * Coloration minimale du patch unifié : lignes `+` / `-` / `@@`.
 * Volontairement basique : pas de coloration syntaxique (Phase 5+).
 */
function colorize(patch: string): JSX.Element[] {
  return patch.split('\n').map((line, idx) => {
    let cls = '';
    if (line.startsWith('+++') || line.startsWith('---')) {
      cls = 'text-eldir-gray-2';
    } else if (line.startsWith('+')) {
      cls = 'text-eldir-green';
    } else if (line.startsWith('-')) {
      cls = 'text-eldir-red';
    } else if (line.startsWith('@@')) {
      cls = 'text-eldir-orange';
    } else if (line.startsWith('diff ')) {
      cls = 'text-eldir-gold';
    }
    return (
      <div key={idx} className={cls}>
        {line || ' '}
      </div>
    );
  });
}
