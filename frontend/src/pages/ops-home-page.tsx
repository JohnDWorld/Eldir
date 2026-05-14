/**
 * OpsHomePage — D1 Mission Control desktop, branchée sur les vraies données.
 *
 * Layout (≥ md): 260px (projects) | 1fr (sessions + logs) | 320px (spend + events)
 * Layout (< md): stack verticale.
 *
 * Phase 1: les telemetry (tokens/spend) et la spend 7-day restent en mocks
 * tant que SessionCost n'est pas alimenté par l'OTel SDK.
 */

import { useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';

import { EventRow } from '@/components/eldir/event-row';
import { GitMark } from '@/components/eldir/git-mark';
import { LogsPanel, type LogLine, type LogTone } from '@/components/eldir/logs-panel';
import { OpsShell, type TelemetryItem } from '@/components/eldir/ops-shell';
import { SessionCard, type SessionCardData } from '@/components/eldir/session-card';
import { Spark } from '@/components/eldir/spark';
import { StateDot } from '@/components/eldir/state-dot';
import { NewSessionDialog } from '@/features/sessions/new-session-dialog';
import {
  MOCK_EVENTS,
  MOCK_LOG_LINES,
  MOCK_SPEND_7D,
  MOCK_TOKENS_TODAY,
} from '@/features/sessions/mock-data';
import { useDeleteSession, useProjects, useSessions } from '@/lib/api/queries';
import type { ProjectRead, SessionRead } from '@/lib/types/api';
import type { SessionState } from '@/lib/constants';
import { cn } from '@/lib/utils';

const ACTIVE_STATES: ReadonlySet<SessionState> = new Set([
  'thinking',
  'tool_use',
  'waiting_input',
  'blocked',
]);

export function OpsHomePage(): JSX.Element {
  const navigate = useNavigate();
  const projects = useProjects();
  const sessions = useSessions();
  const deleteSession = useDeleteSession();
  const [addOpen, setAddOpen] = useState(false);

  const handleDelete = (sessionId: string, label: string) => {
    if (!confirm(`Supprimer la session ${label} ? L'historique sera effacé.`)) {
      return;
    }
    deleteSession.mutate(sessionId);
  };

  const activeSessions = useMemo(
    () => (sessions.data ?? []).filter((s) => ACTIVE_STATES.has(s.state)),
    [sessions.data],
  );
  const waitingInput = useMemo(
    () => (sessions.data ?? []).filter((s) => s.state === 'waiting_input').length,
    [sessions.data],
  );
  const blocked = useMemo(
    () => (sessions.data ?? []).filter((s) => s.state === 'blocked').length,
    [sessions.data],
  );

  const projectSlugById = useMemo(() => {
    const map = new Map<string, string>();
    for (const p of projects.data ?? []) map.set(p.id, p.slug);
    return map;
  }, [projects.data]);

  const projectSessionCount = useMemo(() => {
    const map = new Map<string, number>();
    for (const s of activeSessions) {
      map.set(s.project_id, (map.get(s.project_id) ?? 0) + 1);
    }
    return map;
  }, [activeSessions]);

  const telemetry: readonly TelemetryItem[] = [
    { label: 'Active', value: String(activeSessions.length), sub: 'sessions' },
    { label: 'Projects', value: String((projects.data ?? []).length), sub: 'cloned' },
    { label: 'Input', value: String(waitingInput), sub: 'awaiting you' },
    { label: 'Blocked', value: String(blocked), sub: '—' },
    // Tokens et Spend restent en mock jusqu'à intégration OTel (Phase 5).
    { label: 'Tokens', value: '—', sub: 'today', spark: MOCK_TOKENS_TODAY },
    { label: 'Spend', value: '—', sub: '$8 cap', spark: MOCK_SPEND_7D },
  ];

  const cards: SessionCardData[] = (sessions.data ?? [])
    .slice()
    .sort((a, b) => +new Date(b.created_at) - +new Date(a.created_at))
    .map((s) => ({
      id: s.id.slice(0, 8),
      projectSlug: projectSlugById.get(s.project_id) ?? 'unknown',
      state: s.state,
      summary: s.summary ?? null,
      duration: durationSince(s.created_at),
      tokens: '—',
      cost: '—',
    }));

  return (
    <OpsShell telemetry={telemetry}>
      <div className="grid h-full min-h-0 grid-cols-1 md:grid-cols-[260px_1fr_320px]">
        {/* ── Projects rail ───────────────────────────────────── */}
        <aside className="flex flex-col overflow-y-auto border-eldir-gray-3 py-2.5 md:border-r">
          <div className="flex items-center justify-between px-3.5 py-1 pb-2">
            <span className="eldir-caps">
              Projects · {(projects.data ?? []).length}
            </span>
            <a
              href="/projects"
              className="font-mono text-xs font-semibold text-eldir-orange"
              aria-label="manage projects"
            >
              +
            </a>
          </div>
          {(projects.data ?? []).map((p) => (
            <ProjectRailRow
              key={p.id}
              project={p}
              activeSessions={projectSessionCount.get(p.id) ?? 0}
            />
          ))}
          {(projects.data ?? []).length === 0 && (
            <p className="px-3.5 py-3 font-mono text-2xs text-eldir-gray">
              Aucun projet. <a href="/projects" className="text-eldir-orange">ajoute-en</a>.
            </p>
          )}
        </aside>

        {/* ── Sessions grid ──────────────────────────────────── */}
        <section className="flex min-h-0 flex-col overflow-y-auto p-3.5">
          <div className="mb-2.5 flex items-center justify-between">
            <span className="eldir-caps">Live sessions</span>
            <button
              type="button"
              onClick={() => setAddOpen(true)}
              className="rounded-eldir bg-eldir-orange px-3 py-1.5 font-mono text-xs font-semibold uppercase tracking-caps text-white hover:bg-eldir-orange/90"
            >
              + new session
            </button>
          </div>
          {cards.length === 0 ? (
            <p className="rounded-eldir border border-dashed border-eldir-gray-3 bg-eldir-cream py-6 text-center font-mono text-xs text-eldir-gray">
              Aucune session. Clique "+ NEW SESSION" pour démarrer.
            </p>
          ) : (
            <div className="grid grid-cols-1 gap-2.5 md:grid-cols-2">
              {cards.map((card, idx) => {
                const sessionId = sessions.data![idx]!.id;
                return (
                  <div key={card.id} className="group relative">
                    <SessionCard
                      data={card}
                      onClick={() => navigate(`/sessions/${sessionId}`)}
                    />
                    <button
                      type="button"
                      onClick={(e) => {
                        e.stopPropagation();
                        handleDelete(sessionId, card.id);
                      }}
                      disabled={deleteSession.isPending}
                      aria-label="Supprimer la session"
                      title="Supprimer la session"
                      className="absolute right-2 top-2 rounded-eldir border border-eldir-gray-3 bg-eldir-paper px-2 py-1 font-mono text-2xs uppercase tracking-caps text-eldir-red opacity-0 transition-opacity hover:bg-eldir-red/10 focus:opacity-100 group-hover:opacity-100 disabled:opacity-50"
                    >
                      ✕
                    </button>
                  </div>
                );
              })}
            </div>
          )}
          <LogsPanel
            className="mt-3.5 max-h-[160px]"
            title={`// stream · ${activeSessions.length} active`}
            lines={fakeLogLines(sessions.data ?? [], projectSlugById)}
          />
        </section>

        {/* ── Right rail : spend + events ─────────────────────── */}
        <aside className="hidden flex-col gap-3.5 overflow-y-auto border-l border-eldir-gray-3 px-3.5 py-2.5 md:flex">
          <div>
            <div className="eldir-caps mb-2">Spend · 7-day</div>
            <div className="rounded-eldir border border-eldir-gray-3 bg-eldir-cream py-2.5">
              <Spark
                data={MOCK_SPEND_7D}
                width={290}
                height={56}
                fill="hsl(var(--eldir-orange) / 0.12)"
                className="px-2.5"
              />
              <div className="flex justify-between px-2.5 pt-1 font-mono text-2xs text-eldir-gray">
                <span>Phase 5 — OTel</span>
                <span>—</span>
              </div>
            </div>
          </div>
          <div>
            <div className="eldir-caps mb-2">Events</div>
            <div>
              {MOCK_EVENTS.map((e) => (
                <EventRow key={`${e.time}-${e.source}-${e.message}`} entry={e} />
              ))}
            </div>
          </div>
        </aside>
      </div>

      {addOpen && <NewSessionDialog onClose={() => setAddOpen(false)} />}
    </OpsShell>
  );
}

function ProjectRailRow({
  project,
  activeSessions,
}: {
  project: ProjectRead;
  activeSessions: number;
}): JSX.Element {
  return (
    <a
      href={`/projects`}
      className={cn(
        'flex items-center gap-2 border-l-2 px-3.5 py-2.5 text-left transition-colors',
        'border-l-transparent hover:bg-eldir-cream-2',
      )}
    >
      <GitMark
        provider={project.provider}
        size={11}
        className="text-eldir-gray"
      />
      <div className="min-w-0 flex-1">
        <div className="font-mono text-xs font-semibold text-eldir-ink">
          {project.name}
        </div>
        <div className="mt-0.5 truncate font-mono text-2xs text-eldir-gray">
          {project.default_branch}
        </div>
      </div>
      <div className="text-right">
        {activeSessions > 0 && (
          <div className="inline-flex items-center gap-1 font-mono text-2xs font-semibold text-eldir-orange">
            {activeSessions}
            <StateDot state="thinking" size={6} />
          </div>
        )}
      </div>
    </a>
  );
}

function durationSince(iso: string): string {
  const ms = Date.now() - +new Date(iso);
  const m = Math.floor(ms / 60_000);
  if (m < 60) return `${String(Math.floor(m / 60)).padStart(2, '0')}:${String(m % 60).padStart(2, '0')}`;
  const h = Math.floor(m / 60);
  const rem = m % 60;
  return `${String(h).padStart(2, '0')}:${String(rem).padStart(2, '0')}`;
}

function fakeLogLines(
  sessions: readonly SessionRead[],
  slugById: ReadonlyMap<string, string>,
): readonly LogLine[] {
  if (sessions.length === 0) return MOCK_LOG_LINES;
  return sessions.slice(0, 5).map((s) => {
    const tone: LogTone =
      s.state === 'thinking'
        ? 'orange'
        : s.state === 'tool_use'
        ? 'gold'
        : s.state === 'waiting_input'
        ? 'amber'
        : s.state === 'blocked'
        ? 'red'
        : 'gray';
    return {
      id: s.id,
      prefix: { tone, text: s.id.slice(0, 4) },
      kind: { tone: 'gray', text: s.state },
      message: s.summary?.slice(0, 80) ?? (slugById.get(s.project_id) ?? ''),
      messageTone: 'cream',
    };
  });
}
