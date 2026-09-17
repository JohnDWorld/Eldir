/**
 * OpsHomePage - D1 Mission Control desktop, branchée sur les vraies données.
 *
 * Layout (≥ md): 260px (projects) | 1fr (sessions + logs) | 320px (spend + events)
 * Layout (< md): stack verticale.
 *
 * Phase 1: les telemetry (tokens/spend) et la spend 7-day restent en mocks
 * tant que SessionCost n'est pas alimenté par l'OTel SDK.
 */

import { ChevronRight, Loader2, Plus, Trash2 } from 'lucide-react';
import { useMemo, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';

import { EventRow } from '@/components/eldir/event-row';
import { GitMark } from '@/components/eldir/git-mark';
import { LogsPanel, type LogLine, type LogTone } from '@/components/eldir/logs-panel';
import { OpsShell, type TelemetryItem } from '@/components/eldir/ops-shell';
import { SessionCard, type SessionCardData } from '@/components/eldir/session-card';
import { Spark } from '@/components/eldir/spark';
import { StateDot } from '@/components/eldir/state-dot';
import { NewSessionDialog } from '@/features/sessions/new-session-dialog';
import {
  useCostsDashboard,
  useDeleteSession,
  useProjects,
  useSessions,
} from '@/lib/api/queries';
import type { ProjectRead, SessionRead } from '@/lib/types/api';
import type { SessionState } from '@/lib/constants';
import { SESSION_STATE_LABEL } from '@/lib/constants';
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
  const costs = useCostsDashboard();
  const deleteSession = useDeleteSession();
  const [addOpen, setAddOpen] = useState(false);

  const handleDelete = (sessionId: string, label: string) => {
    if (!confirm(`Supprimer la session ${label} ? L'historique sera effacé.`)) {
      return;
    }
    deleteSession.mutate(sessionId);
  };

  // Les sessions système (ex. génération de template) restent comptées
  // dans les COÛTS (cf. principe : pas de "faux-coût"), mais on ne les
  // affiche pas dans la grille Live Sessions principale pour ne pas
  // polluer la vue ops. Filtrage uniquement visuel.
  const userSessions = useMemo(
    () => (sessions.data ?? []).filter((s) => !s.is_system),
    [sessions.data],
  );
  const systemSessions = useMemo(
    () => (sessions.data ?? []).filter((s) => s.is_system),
    [sessions.data],
  );
  const activeSessions = useMemo(
    () => userSessions.filter((s) => ACTIVE_STATES.has(s.state)),
    [userSessions],
  );
  const activeSystemSessions = useMemo(
    () => systemSessions.filter((s) => ACTIVE_STATES.has(s.state)),
    [systemSessions],
  );
  const waitingInput = useMemo(
    () => userSessions.filter((s) => s.state === 'waiting_input').length,
    [userSessions],
  );
  const blocked = useMemo(
    () => userSessions.filter((s) => s.state === 'blocked').length,
    [userSessions],
  );

  const projectSlugById = useMemo(() => {
    const map = new Map<string, string>();
    for (const p of projects.data ?? []) map.set(p.id, p.slug);
    return map;
  }, [projects.data]);

  const projectSessionCount = useMemo(() => {
    const map = new Map<string, number>();
    for (const s of activeSessions) {
      // project_id est null pour le superviseur, déjà exclu d'activeSessions.
      if (!s.project_id) continue;
      map.set(s.project_id, (map.get(s.project_id) ?? 0) + 1);
    }
    return map;
  }, [activeSessions]);

  const tokensToday =
    (costs.data?.today.input_tokens ?? 0) +
    (costs.data?.today.output_tokens ?? 0);
  const spend7d = costs.data?.last_7_days.cost_usd ?? 0;
  const dailySpark = (costs.data?.daily ?? []).map((d) => d.cost_usd);
  const tokensSpark = (costs.data?.daily ?? []).map(
    (d) => d.input_tokens + d.output_tokens,
  );

  const telemetry: readonly TelemetryItem[] = [
    { label: 'Actives', value: String(activeSessions.length), sub: 'sessions' },
    { label: 'Projets', value: String((projects.data ?? []).length), sub: 'clonés' },
    { label: 'À toi', value: String(waitingInput), sub: 'en attente' },
    { label: 'Bloquées', value: String(blocked), sub: 'sessions' },
    {
      label: 'Tokens',
      value: formatTokens(tokensToday),
      sub: 'aujourd’hui',
      // Une courbe à plat sur des zéros est de la décoration : on ne la
      // dessine que s'il y a quelque chose à montrer.
      ...(tokensSpark.some((v) => v > 0) ? { spark: tokensSpark } : {}),
    },
    {
      label: 'Dépense',
      value: spend7d > 0 ? `$${spend7d.toFixed(2)}` : '$0.00',
      sub: '7 jours',
      ...(dailySpark.some((v) => v > 0) ? { spark: dailySpark } : {}),
    },
  ];

  const sortedUserSessions = useMemo(
    () =>
      userSessions
        .slice()
        .sort((a, b) => +new Date(b.created_at) - +new Date(a.created_at)),
    [userSessions],
  );

  const recentEvents = (sessions.data ?? [])
    .slice()
    .sort((a, b) => +new Date(b.created_at) - +new Date(a.created_at))
    .slice(0, 8)
    .map((s) => ({
      time: new Date(s.created_at).toLocaleTimeString('fr-FR', {
        hour: '2-digit',
        minute: '2-digit',
      }),
      source: s.is_system ? '-' : s.id.slice(0, 2),
      message: `${
        s.system_kind === 'supervisor'
          ? 'eldir'
          : s.project_id
            ? (projectSlugById.get(s.project_id) ?? 'projet')
            : 'système'
      } · ${SESSION_STATE_LABEL[s.state]}`,
    }));

  const cards: SessionCardData[] = sortedUserSessions
    .map((s) => ({
      id: s.id.slice(0, 8),
      projectSlug:
        (s.project_id ? projectSlugById.get(s.project_id) : 'eldir') ?? 'inconnu',
      state: s.state,
      summary: s.summary ?? null,
      duration: durationSince(s.created_at),
    }));

  return (
    <OpsShell telemetry={telemetry}>
      <div className="grid h-full min-h-0 min-w-0 grid-cols-1 md:grid-cols-[260px_1fr_320px]">
        {/* ── Projects rail ───────────────────────────────────── */}
        <aside className="flex min-w-0 flex-col overflow-y-auto border-eldir-gray-3 py-2.5 md:border-r">
          <div className="flex items-center justify-between px-3.5 py-1 pb-2">
            <span className="eldir-caps">
              Projets · {(projects.data ?? []).length}
            </span>
            <Link
              to="/projects"
              className="inline-flex min-h-11 min-w-11 items-center justify-center rounded-eldir text-eldir-orange hover:bg-eldir-cream-2 md:min-h-8 md:min-w-8"
              aria-label="Gérer les projets"
              title="Gérer les projets"
            >
              <Plus size={14} aria-hidden="true" />
            </Link>
          </div>
          {(projects.data ?? []).map((p) => (
            <ProjectRailRow
              key={p.id}
              project={p}
              activeSessions={projectSessionCount.get(p.id) ?? 0}
            />
          ))}
          {projects.isPending &&
            [0, 1].map((i) => (
              <div key={i} className="flex items-center gap-2 px-3.5 py-2.5">
                <span className="eldir-skeleton h-3 w-3" />
                <span className="flex flex-1 flex-col gap-1.5">
                  <span className="eldir-skeleton h-3 w-3/5" />
                  <span className="eldir-skeleton h-2.5 w-2/5" />
                </span>
              </div>
            ))}
          {!projects.isPending && (projects.data ?? []).length === 0 && (
            <p className="px-3.5 py-3 font-sans text-xs text-eldir-gray">
              Aucun projet.{' '}
              <Link to="/projects" className="text-eldir-orange underline underline-offset-2">
                Ajoute un repo
              </Link>{' '}
              pour lancer une session dessus.
            </p>
          )}
        </aside>

        {/* ── Sessions grid ──────────────────────────────────── */}
        <section className="flex min-h-0 min-w-0 flex-col overflow-y-auto p-3.5">
          {activeSystemSessions.length > 0 && (
            <div className="mb-2.5 flex items-center justify-between gap-2 rounded-eldir border border-eldir-orange/40 bg-eldir-orange/5 px-3 py-1.5">
              <span className="inline-flex min-w-0 items-center gap-1.5 truncate font-mono text-2xs uppercase tracking-caps text-eldir-orange">
                <Loader2 size={11} aria-hidden="true" className="shrink-0 animate-spin" />
                {activeSystemSessions.length} tâche
                {activeSystemSessions.length > 1 ? 's' : ''} système en cours
              </span>
              <Link
                to={`/sessions/${activeSystemSessions[0]!.id}`}
                className="inline-flex shrink-0 items-center font-mono text-2xs text-eldir-orange hover:underline"
              >
                voir
                <ChevronRight size={12} aria-hidden="true" />
              </Link>
            </div>
          )}
          <div className="mb-2.5 flex items-center justify-between">
            <span className="eldir-caps">Sessions en cours</span>
            {/* Quand la liste est vide, l'état vide porte déjà l'action :
                deux boutons identiques côte à côte, c'était un de trop. */}
            {cards.length > 0 && (
              <button
                type="button"
                onClick={() => setAddOpen(true)}
                className="eldir-btn eldir-btn--primary eldir-btn--sm"
              >
                <Plus size={14} aria-hidden="true" />
                nouvelle session
              </button>
            )}
          </div>
          {cards.length === 0 ? (
            <div className="flex flex-col items-center gap-3 rounded-eldir border border-dashed border-eldir-gray-3 bg-eldir-cream px-4 py-10 text-center">
              <h2 className="font-sans text-base font-semibold text-eldir-ink">
                Aucune session en cours
              </h2>
              <p className="max-w-md font-sans text-sm text-eldir-ink-2">
                {(projects.data ?? []).length === 0 ? (
                  <>
                    Commence par{' '}
                    <Link to="/projects" className="text-eldir-orange underline underline-offset-2">
                      ajouter un repo
                    </Link>
                    , puis lance une session dessus.
                  </>
                ) : (
                  <>
                    Une session, c&apos;est un agent Claude qui travaille sur une
                    copie isolée d&apos;un de tes repos. Tu peux aussi passer par
                    Eldir, qui dispatche pour toi.
                  </>
                )}
              </p>
              {(projects.data ?? []).length > 0 && (
                <div className="flex flex-wrap justify-center gap-2">
                  <button
                    type="button"
                    onClick={() => setAddOpen(true)}
                    className="eldir-btn eldir-btn--primary"
                  >
                    <Plus size={14} aria-hidden="true" />
                    nouvelle session
                  </button>
                  <Link to="/supervisor" className="eldir-btn eldir-btn--secondary">
                    parler à eldir
                  </Link>
                </div>
              )}
            </div>
          ) : (
            <div className="grid grid-cols-1 gap-2.5 md:grid-cols-2">
              {cards.map((card, idx) => {
                const sessionId = sortedUserSessions[idx]!.id;
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
                      // Visible en permanence sous `md` : il n'y a pas de
                      // survol au doigt, le bouton était inatteignable.
                      className="absolute bottom-1 right-1 flex h-11 w-11 items-center justify-center rounded-eldir text-eldir-red transition-opacity hover:bg-eldir-red/10 focus-visible:opacity-100 disabled:opacity-45 md:bottom-2 md:right-2 md:h-8 md:w-8 md:min-h-0 md:min-w-0 md:opacity-0 md:group-hover:opacity-100"
                    >
                      <Trash2 size={14} aria-hidden="true" />
                    </button>
                  </div>
                );
              })}
            </div>
          )}
          <LogsPanel
            className="mt-3.5 max-h-[160px]"
            title={`// flux · ${activeSessions.length} active${activeSessions.length > 1 ? 's' : ''}`}
            lines={sessionLogLines(sessions.data ?? [], projectSlugById)}
          />
        </section>

        {/* ── Right rail : spend + events ─────────────────────── */}
        <aside className="hidden flex-col gap-3.5 overflow-y-auto border-l border-eldir-gray-3 px-3.5 py-2.5 md:flex">
          <div>
            <div className="mb-2 flex items-center justify-between">
              <span className="eldir-caps">Dépense · 7 jours</span>
              <Link
                to="/costs"
                className="inline-flex items-center font-mono text-2xs text-eldir-orange hover:underline"
              >
                détails
                <ChevronRight size={12} aria-hidden="true" />
              </Link>
            </div>
            <div className="rounded-eldir border border-eldir-gray-3 bg-eldir-cream py-2.5">
              {dailySpark.length > 0 ? (
                <Spark
                  data={dailySpark}
                  width={290}
                  height={56}
                  fill="hsl(var(--eldir-orange) / 0.12)"
                  className="px-2.5"
                />
              ) : (
                <div className="px-2.5 py-3 font-mono text-2xs text-eldir-gray">
                  Aucun coût encore enregistré.
                </div>
              )}
              <div className="flex justify-between px-2.5 pt-1 font-mono text-2xs text-eldir-gray">
                <span>${spend7d.toFixed(2)} sur 7 jours</span>
                <span>{formatTokens(tokensSpark.reduce((a, b) => a + b, 0))} tokens</span>
              </div>
            </div>
          </div>
          <div>
            {/* Ce panneau affichait des événements inventés (« forgejo
                webhook · push », « test passed ») présentés comme réels. Il
                montre maintenant les dernières sessions, qui existent. */}
            <div className="eldir-caps mb-2">Dernières sessions</div>
            {recentEvents.length === 0 ? (
              <p className="font-sans text-xs text-eldir-gray">
                Rien encore. Les sessions apparaîtront ici dès la première.
              </p>
            ) : (
              <div>
                {recentEvents.map((e) => (
                  <EventRow key={`${e.time}-${e.source}-${e.message}`} entry={e} />
                ))}
              </div>
            )}
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
    <Link
      to={`/projects/${project.id}/template`}
      title={`Configurer ${project.name}`}
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
    </Link>
  );
}

function formatTokens(n: number): string {
  if (n === 0) return '0';
  if (n < 1_000) return String(n);
  if (n < 1_000_000) return `${(n / 1_000).toFixed(1)}k`;
  return `${(n / 1_000_000).toFixed(2)}M`;
}

function durationSince(iso: string): string {
  const ms = Date.now() - +new Date(iso);
  const m = Math.floor(ms / 60_000);
  if (m < 60) return `${String(Math.floor(m / 60)).padStart(2, '0')}:${String(m % 60).padStart(2, '0')}`;
  const h = Math.floor(m / 60);
  const rem = m % 60;
  return `${String(h).padStart(2, '0')}:${String(rem).padStart(2, '0')}`;
}

function sessionLogLines(
  sessions: readonly SessionRead[],
  slugById: ReadonlyMap<string, string>,
): readonly LogLine[] {
  if (sessions.length === 0) {
    return [
      {
        id: 'vide',
        prefix: { tone: 'gray', text: '--' },
        message: 'aucune session pour le moment',
        messageTone: 'gray',
      },
    ];
  }
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
      message:
        s.summary?.slice(0, 80) ??
        (s.project_id ? (slugById.get(s.project_id) ?? '') : 'eldir'),
      messageTone: 'cream',
    };
  });
}
