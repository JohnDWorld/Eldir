/**
 * SessionPage - D1DeskSession portée.
 *
 * Layout desktop : sidebar sessions (200px) | chat (1fr) | logs+events live (1fr) | meta (240px)
 * Layout mobile  : tabs CHAT | LIVE | META, full-width.
 */

import { useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';

import { Avatar } from '@/components/eldir/avatar';
import { StatePill } from '@/components/eldir/state-pill';
import { DiffPanel } from '@/features/sessions/diff-panel';
import { SessionGitActions } from '@/features/sessions/git-actions';
import { useSessionStream } from '@/hooks/use-session-stream';
import {
  useDeleteSession,
  useProjects,
  useSendMessage,
  useSession,
  useSessionCostTotals,
  useSessionEvents,
  useSessions,
  useStopSession,
} from '@/lib/api/queries';
import type { SessionEvent, SessionEventRead } from '@/lib/types/api';
import { cn } from '@/lib/utils';

export function SessionPage(): JSX.Element {
  const { sessionId = '' } = useParams<{ sessionId: string }>();
  const session = useSession(sessionId);
  const sessions = useSessions();
  const projects = useProjects();
  const historical = useSessionEvents(sessionId);
  const costs = useSessionCostTotals(sessionId, Boolean(sessionId));
  const live = useSessionStream(sessionId, { enabled: Boolean(sessionId) });
  const sendMessage = useSendMessage(sessionId);
  const stopMut = useStopSession();
  const deleteMut = useDeleteSession();
  const navigate = useNavigate();
  const [rightTab, setRightTab] = useState<'live' | 'diff'>('live');
  // Le superviseur n'a ni repo ni worktree : pas de git, pas de diff.
  const isSupervisor = session.data?.is_system === true;

  const handleDelete = async () => {
    if (!sessionId) return;
    if (
      !confirm(
        'Supprimer cette session ? L\'historique et les events seront effacés.',
      )
    )
      return;
    try {
      await deleteMut.mutateAsync(sessionId);
      navigate('/');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Erreur suppression');
    }
  };

  const [input, setInput] = useState('');
  const [error, setError] = useState<string | null>(null);

  // Fusionne historique (DB) + live (WS). Le même event arrive d'abord
  // par WS (timestamp = moment du publish) puis par la requête /events
  // refetchée (timestamp = created_at SQL), les deux différant de quelques
  // ms. On dédupe par (type, payload) en n'écartant que les doublons
  // proches dans le temps (< 2s) pour ne pas écraser des events légitimes
  // qui répèteraient le même payload entre deux tours.
  const events = useMemo(() => {
    const seen: { fingerprint: string; ts: number }[] = [];
    const merged: NormalizedEvent[] = [];
    const consider = (item: NormalizedEvent) => {
      const fingerprint = `${item.type}|${JSON.stringify(item.data)}`;
      const ts = Date.parse(item.timestamp);
      const dup = seen.some(
        (s) => s.fingerprint === fingerprint && Math.abs(s.ts - ts) < 2000,
      );
      if (dup) return;
      seen.push({ fingerprint, ts });
      merged.push(item);
    };
    for (const e of historical.data ?? []) {
      consider({
        key: `db-${e.id}`,
        type: e.type,
        timestamp: e.created_at,
        data: e.payload,
      });
    }
    live.events.forEach((e, i) => {
      consider({
        key: `live-${i}-${e.timestamp}`,
        type: e.type,
        timestamp: e.timestamp,
        data: e.data,
      });
    });
    return merged;
  }, [historical.data, live.events]);

  const handleSend = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    const content = input.trim();
    if (!content) return;
    try {
      setInput('');
      await sendMessage.mutateAsync({ content });
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Erreur envoi message');
    }
  };

  if (session.isPending) {
    return (
      <main className="flex h-full items-center justify-center">
        <div className="eldir-caps animate-pulse">chargement de la session…</div>
      </main>
    );
  }
  if (session.isError || !session.data) {
    return (
      <main className="flex h-full items-center justify-center">
        <div className="font-mono text-xs text-eldir-red">
          {session.error?.message ?? 'session introuvable'}
        </div>
      </main>
    );
  }

  return (
    <div className="flex h-full flex-col bg-eldir-paper">
      {/* Topbar */}
      <header className="flex h-[42px] items-center gap-3.5 border-b border-eldir-gray-3 bg-eldir-cream-2 px-4">
        <a
          href="/"
          className="font-mono text-xs uppercase tracking-caps text-eldir-gray hover:text-eldir-ink"
        >
          ‹ OPS
        </a>
        <span className="font-mono text-xs font-semibold text-eldir-ink">
          / {session.data.id.slice(0, 8)}
        </span>
        <StatePill state={session.data.state} />
        <span className="hidden font-mono text-[11px] text-eldir-gray md:inline">
          {session.data.branch} · {session.data.model ?? 'default model'}
        </span>
        <div className="flex-1" />
        {!isSupervisor && <SessionGitActions sessionId={sessionId} />}
        <button
          type="button"
          onClick={() => stopMut.mutate(sessionId)}
          className="rounded-eldir border border-eldir-gray-3 bg-eldir-paper px-3 py-1.5 font-mono text-xs uppercase tracking-caps text-eldir-ink hover:bg-eldir-cream"
        >
          stop
        </button>
        <button
          type="button"
          onClick={handleDelete}
          disabled={deleteMut.isPending}
          className="rounded-eldir border border-eldir-gray-3 bg-eldir-paper px-3 py-1.5 font-mono text-xs uppercase tracking-caps text-eldir-red hover:bg-eldir-red/10 disabled:opacity-50"
        >
          {deleteMut.isPending ? 'suppr…' : 'supprimer'}
        </button>
        <Avatar size={24}>J</Avatar>
      </header>

      <div className="grid h-full min-h-0 grid-cols-1 md:grid-cols-[220px_1fr_320px]">
        {/* Sidebar sessions */}
        <aside className="hidden flex-col overflow-y-auto border-r border-eldir-gray-3 py-2.5 md:flex">
          <div className="px-3 pb-2 eldir-caps">Sessions</div>
          {(sessions.data ?? []).map((s) => {
            const project = projects.data?.find((p) => p.id === s.project_id);
            const label = s.is_system
              ? 'Eldir · superviseur'
              : (project?.name ?? 'projet inconnu');
            const active = s.id === sessionId;
            return (
              <a
                key={s.id}
                href={`/sessions/${s.id}`}
                className={cn(
                  'flex flex-col gap-0.5 border-l-2 px-3 py-2 font-mono text-xs',
                  active
                    ? 'border-l-eldir-orange bg-eldir-cream text-eldir-ink'
                    : 'border-l-transparent text-eldir-gray hover:bg-eldir-cream-2',
                )}
              >
                <div className="flex items-center gap-2">
                  <StatePill state={s.state} />
                  <span
                    className={cn(
                      'truncate font-semibold',
                      active ? 'text-eldir-ink' : 'text-eldir-ink-2',
                    )}
                  >
                    {label}
                  </span>
                </div>
                <span className="ml-5 truncate text-eldir-gray">
                  {s.id.slice(0, 8)}
                </span>
              </a>
            );
          })}
        </aside>

        {/* Chat */}
        <section className="flex min-h-0 min-w-0 flex-col overflow-hidden border-r border-eldir-gray-3">
          <ChatStream events={events} />
          {error && (
            <div className="border-t border-eldir-gray-3 px-4 py-2 font-mono text-xs text-eldir-red">
              {error}
            </div>
          )}
          <form
            onSubmit={handleSend}
            className="border-t border-eldir-gray-3 bg-eldir-paper p-3"
          >
            <div className="flex items-center gap-2 rounded-eldir border border-eldir-gray-3 bg-eldir-cream px-3 py-2">
              <span className="font-mono text-xs text-eldir-orange">›</span>
              <input
                type="text"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                placeholder="Reply, /command, ou @file…"
                disabled={sendMessage.isPending}
                className="flex-1 bg-transparent font-sans text-sm text-eldir-ink focus:outline-none disabled:opacity-50"
              />
              <span className="font-mono text-2xs text-eldir-gray">⌘↵</span>
            </div>
          </form>
        </section>

        {/* Right rail : Session meta (top) + Logs live stream (bottom) */}
        <aside className="hidden min-h-0 min-w-0 flex-col overflow-hidden border-l border-eldir-gray-3 md:flex">
          <div className="flex flex-col gap-3 border-b border-eldir-gray-3 bg-eldir-paper p-4">
            <div className="eldir-caps">Session meta</div>
            <Kv k="id" v={session.data.id.slice(0, 12)} />
            {(() => {
              const project = projects.data?.find(
                (p) => p.id === session.data.project_id,
              );
              return (
                <>
                  <Kv
                    k="project"
                    v={isSupervisor ? 'superviseur' : (project?.name ?? '-')}
                  />
                  <Kv k="repo" v={project?.repo_full_name ?? '-'} />
                </>
              );
            })()}
            <Kv k="branch" v={session.data.branch} />
            <Kv k="state" v={session.data.state} />
            <Kv k="model" v={session.data.model ?? '-'} />
            <Kv k="sdk_id" v={session.data.sdk_session_id?.slice(0, 12) ?? '-'} />
            <Kv k="created" v={new Date(session.data.created_at).toLocaleTimeString()} />
          </div>

          <SessionCostPanel
            inputTokens={costs.data?.input_tokens ?? 0}
            outputTokens={costs.data?.output_tokens ?? 0}
            cacheReadTokens={costs.data?.cache_read_tokens ?? 0}
            costUsd={costs.data?.cost_usd ?? 0}
            numTurns={costs.data?.num_turns ?? 0}
          />


          <div className="flex border-b border-eldir-gray-3 bg-eldir-cream-2">
            <RightTab
              label={`live · ${live.state}`}
              active={rightTab === 'live'}
              onClick={() => setRightTab('live')}
            />
            {!isSupervisor && (
              <RightTab
                label="diff"
                active={rightTab === 'diff'}
                onClick={() => setRightTab('diff')}
              />
            )}
          </div>

          {rightTab === 'live' || isSupervisor ? (
            <section className="flex min-h-0 flex-1 flex-col overflow-hidden bg-eldir-ink">
              <div className="flex-1 overflow-y-auto p-3 font-mono text-[11px] leading-relaxed text-eldir-cream">
                {events.map((e) => (
                  <LogLine key={e.key} event={e} />
                ))}
              </div>
            </section>
          ) : (
            <DiffPanel sessionId={sessionId} />
          )}
        </aside>
      </div>
    </div>
  );
}

// ── helpers ─────────────────────────────────────────────────────
interface NormalizedEvent {
  key: string;
  type: SessionEvent['type'] | SessionEventRead['type'];
  timestamp: string;
  data: Record<string, unknown>;
}

function ChatStream({ events }: { events: NormalizedEvent[] }): JSX.Element {
  const scroll = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (scroll.current) {
      scroll.current.scrollTop = scroll.current.scrollHeight;
    }
  }, [events.length]);

  // Filtre : on affiche text + tool_use + stop + user_message.
  const visible = events.filter(
    (e) =>
      e.type === 'text' ||
      e.type === 'tool_use' ||
      e.type === 'stop' ||
      e.type === 'user_message',
  );

  return (
    <div
      ref={scroll}
      className="flex-1 space-y-3 overflow-y-auto bg-eldir-paper p-4"
    >
      {visible.length === 0 && (
        <p className="text-center font-mono text-xs text-eldir-gray">
          Pose ta première question à Claude…
        </p>
      )}
      {visible.map((e) => {
        if (e.type === 'user_message') {
          return (
            <UserBubble key={e.key}>{String(e.data.text ?? '')}</UserBubble>
          );
        }
        if (e.type === 'text') {
          return (
            <ClaudeBubble key={e.key}>
              {String(e.data.text ?? '')}
            </ClaudeBubble>
          );
        }
        if (e.type === 'tool_use') {
          return (
            <ToolRow
              key={e.key}
              name={String(e.data.tool_name ?? 'tool')}
              arg={firstStringArg(e.data.tool_input)}
            />
          );
        }
        return (
          <div
            key={e.key}
            className="text-center font-mono text-2xs uppercase tracking-caps text-eldir-gray"
          >
            - tour terminé -
          </div>
        );
      })}
    </div>
  );
}

function UserBubble({ children }: { children: React.ReactNode }): JSX.Element {
  return (
    <div className="flex justify-end">
      <div className="max-w-[90%] whitespace-pre-wrap rounded-[10px_2px_10px_10px] border border-eldir-orange/30 bg-eldir-orange/10 px-3 py-2 font-sans text-sm text-eldir-ink">
        {children}
      </div>
    </div>
  );
}

function firstStringArg(input: unknown): string {
  if (input && typeof input === 'object') {
    for (const v of Object.values(input)) {
      if (typeof v === 'string') return v;
    }
  }
  return '';
}

function ClaudeBubble({ children }: { children: React.ReactNode }): JSX.Element {
  return (
    <div className="flex max-w-[90%] gap-2">
      <Avatar bg="hsl(var(--eldir-orange))" fg="#fff" size={20}>
        C
      </Avatar>
      <div className="whitespace-pre-wrap rounded-[2px_10px_10px_10px] border border-eldir-gray-3 bg-eldir-cream px-3 py-2 font-sans text-sm text-eldir-ink">
        {children}
      </div>
    </div>
  );
}

function ToolRow({ name, arg }: { name: string; arg: string }): JSX.Element {
  return (
    <div className="flex min-w-0 max-w-full items-center gap-2 rounded-eldir border border-dashed border-eldir-gray-2 px-2.5 py-1.5 font-mono text-2xs text-eldir-gray">
      <span className="shrink-0 text-eldir-gold">◇</span>
      <span className="shrink-0 text-eldir-ink">{name}</span>
      {arg && (
        <span className="min-w-0 flex-1 truncate opacity-70">({arg})</span>
      )}
    </div>
  );
}

function LogLine({ event }: { event: NormalizedEvent }): JSX.Element {
  const time = new Date(event.timestamp).toLocaleTimeString('fr-FR', {
    hour12: false,
  });
  const tone: Record<string, string> = {
    text: 'text-eldir-cream',
    tool_use: 'text-eldir-gold',
    tool_result: 'text-eldir-gray-2',
    state: 'text-eldir-orange',
    stop: 'text-eldir-amber',
    error: 'text-eldir-red',
  };
  const summary =
    event.type === 'text'
      ? String(event.data.text ?? '').slice(0, 120)
      : event.type === 'tool_use'
      ? String(event.data.tool_name ?? '')
      : event.type === 'state'
      ? String(event.data.state ?? event.data.sdk_session_id ?? '')
      : event.type === 'error'
      ? String(event.data.message ?? '')
      : '';
  return (
    <div className="flex gap-2">
      <span className="text-eldir-gray">{time}</span>
      <span className={cn('w-20 shrink-0', tone[event.type] ?? 'text-eldir-cream')}>
        {event.type}
      </span>
      <span className="flex-1 truncate text-eldir-cream">{summary}</span>
    </div>
  );
}

// Phase 5 : seuil d'alerte (jamais bloquant - cf. Principes directeurs #5).
const SESSION_TOKEN_BUDGET = 1_000_000;

function SessionCostPanel({
  inputTokens,
  outputTokens,
  cacheReadTokens,
  costUsd,
  numTurns,
}: {
  inputTokens: number;
  outputTokens: number;
  cacheReadTokens: number;
  costUsd: number;
  numTurns: number;
}): JSX.Element {
  const totalBillable = inputTokens + outputTokens;
  const overBudget = totalBillable > SESSION_TOKEN_BUDGET;
  const cacheRatio = totalBillable + cacheReadTokens > 0
    ? Math.round((cacheReadTokens / (totalBillable + cacheReadTokens)) * 100)
    : 0;
  return (
    <div
      className={cn(
        'flex flex-col gap-2 border-b p-4',
        overBudget
          ? 'border-eldir-red/50 bg-eldir-red/5'
          : 'border-eldir-gray-3 bg-eldir-paper',
      )}
    >
      <div className="flex items-center justify-between">
        <span className="eldir-caps">Cost · session</span>
        {overBudget && (
          <span className="font-mono text-2xs font-semibold uppercase tracking-caps text-eldir-red">
            budget dépassé
          </span>
        )}
      </div>
      <div className="flex items-baseline gap-2">
        <span className="font-mono text-base font-bold text-eldir-ink">
          ${costUsd.toFixed(4)}
        </span>
        <span className="font-mono text-2xs text-eldir-gray">
          {numTurns} tour{numTurns > 1 ? 's' : ''}
        </span>
      </div>
      <Kv k="input" v={formatTokens(inputTokens)} />
      <Kv k="output" v={formatTokens(outputTokens)} />
      <Kv k="cache read" v={`${formatTokens(cacheReadTokens)} (${cacheRatio}%)`} />
    </div>
  );
}

function formatTokens(n: number): string {
  if (n === 0) return '0';
  if (n < 1_000) return String(n);
  if (n < 1_000_000) return `${(n / 1_000).toFixed(1)}k`;
  return `${(n / 1_000_000).toFixed(2)}M`;
}

function Kv({ k, v }: { k: string; v: string }): JSX.Element {
  return (
    <div className="flex justify-between gap-2 border-b border-dotted border-eldir-gray-3 pb-1 font-mono text-xs">
      <span className="text-eldir-gray">{k}</span>
      <span className="truncate text-eldir-ink">{v}</span>
    </div>
  );
}

function RightTab({
  label,
  active,
  onClick,
}: {
  label: string;
  active: boolean;
  onClick: () => void;
}): JSX.Element {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        'flex-1 px-3 py-2 font-mono text-2xs uppercase tracking-caps transition-colors',
        active
          ? 'border-b-2 border-eldir-orange bg-eldir-paper text-eldir-ink'
          : 'border-b-2 border-transparent text-eldir-gray hover:text-eldir-ink',
      )}
    >
      {label}
    </button>
  );
}
