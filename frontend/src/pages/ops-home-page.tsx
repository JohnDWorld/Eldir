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

import { formatAge, formatCost, formatTokens } from '@/lib/format';
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

  // Le nom court, pas le slug : « Creative-Strategist » se lit, pas
  // « johndworld-creative-strategist », qui se faisait tronquer au même
  // endroit sur deux cartes différentes.
  const projectNameById = useMemo(() => {
    const map = new Map<string, string>();
    for (const p of projects.data ?? []) map.set(p.id, p.name);
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
    // Ces deux-là appellent une action : elles se colorent dès qu'elles ne
    // sont pas à zéro, sinon « 1 en attente » pesait autant que « 2 projets ».
    {
      label: 'À toi',
      value: String(waitingInput),
      sub: 'en attente',
      ...(waitingInput > 0 ? { tone: 'attention' as const } : {}),
    },
    {
      label: 'Bloquées',
      value: String(blocked),
      sub: 'sessions',
      ...(blocked > 0 ? { tone: 'alerte' as const } : {}),
    },
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
      value: formatCost(spend7d),
      sub: '7 jours',
      ...(dailySpark.some((v) => v > 0) ? { spark: dailySpark } : {}),
    },
  ];

  // Par urgence, pas par date : sur un téléphone, les premières cartes
  // doivent être celles qui attendent quelque chose de John.
  const sortedUserSessions = useMemo(() => {
    const rang: Record<SessionState, number> = {
      waiting_input: 0,
      blocked: 1,
      tool_use: 2,
      thinking: 2,
      idle: 3,
    };
    return userSessions
      .slice()
      .sort(
        (a, b) =>
          rang[a.state] - rang[b.state] ||
          +new Date(b.created_at) - +new Date(a.created_at),
      );
  }, [userSessions]);

  const cards: SessionCardData[] = sortedUserSessions
    .map((s) => ({
      id: s.id.slice(0, 8),
      projectName:
        (s.project_id ? projectNameById.get(s.project_id) : 'Eldir') ?? 'Projet inconnu',
      state: s.state,
      summary: resumeLisible(s.summary),
      age: formatAge(s.created_at),
    }));

  return (
    <OpsShell telemetry={telemetry}>
      <div className="grid h-full min-h-0 min-w-0 grid-cols-1 md:grid-cols-[260px_1fr_320px]">
        {/* ── Projects rail ───────────────────────────────────── */}
        <aside className="flex min-w-0 flex-col overflow-y-auto border-eldir-gray-3 py-2.5 md:border-r">
          <div className="flex items-center justify-between px-3.5 py-1 pb-2">
            <h2 className="eldir-caps">
              Projets · {(projects.data ?? []).length}
            </h2>
            <Link
              to="/projects"
              className="inline-flex min-h-11 min-w-11 items-center justify-center rounded-eldir text-eldir-orange-text hover:bg-eldir-cream-2 md:min-h-8 md:min-w-8"
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
              <Link to="/projects" className="text-eldir-orange-text underline underline-offset-2">
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
              <span className="inline-flex min-w-0 items-center gap-1.5 truncate font-mono text-2xs uppercase tracking-caps text-eldir-orange-text">
                <Loader2 size={11} aria-hidden="true" className="shrink-0 animate-spin" />
                {activeSystemSessions.length} tâche
                {activeSystemSessions.length > 1 ? 's' : ''} système en cours
              </span>
              <Link
                to={`/sessions/${activeSystemSessions[0]!.id}`}
                className="inline-flex shrink-0 items-center font-mono text-2xs text-eldir-orange-text hover:underline"
              >
                voir
                <ChevronRight size={12} aria-hidden="true" />
              </Link>
            </div>
          )}
          <div className="mb-2.5 flex items-center justify-between">
            <h1 className="eldir-caps">Sessions en cours</h1>
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
                    <Link to="/projects" className="text-eldir-orange-text underline underline-offset-2">
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
                      className="absolute bottom-1 right-1 flex h-11 w-11 items-center justify-center rounded-eldir text-eldir-red-text transition-opacity hover:bg-eldir-red/10 focus-visible:opacity-100 disabled:opacity-45 md:bottom-2 md:right-2 md:h-8 md:w-8 md:min-h-0 md:min-w-0 md:opacity-0 md:group-hover:opacity-100"
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
            lines={sessionLogLines(sessions.data ?? [], projectNameById)}
          />
        </section>

        {/* ── Right rail : spend + events ─────────────────────── */}
        <aside className="hidden flex-col gap-3.5 overflow-y-auto border-l border-eldir-gray-3 px-3.5 py-2.5 md:flex">
          <div>
            <div className="mb-2 flex items-center justify-between">
              <h2 className="eldir-caps">Dépense · 7 jours</h2>
              <Link
                to="/costs"
                className="inline-flex items-center font-mono text-2xs text-eldir-orange-text hover:underline"
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
                <span>{formatCost(spend7d)} sur 7 jours</span>
                <span>{formatTokens(tokensSpark.reduce((a, b) => a + b, 0))} tokens</span>
              </div>
            </div>
          </div>
          <div>
            {/* Ce rail listait les mêmes sessions que les cartes, avec des
                horaires qui ne concordaient pas. Il montre maintenant ce
                qu'on ne voit nulle part ailleurs : les tâches internes
                d'Eldir, qui consomment des tokens sans apparaître dans la
                grille. */}
            <h2 className="eldir-caps mb-2">Tâches internes</h2>
            {systemSessions.length === 0 ? (
              <p className="font-sans text-xs text-eldir-gray">
                Aucune. Les générations de template et le superviseur
                apparaîtront ici.
              </p>
            ) : (
              <ul className="flex flex-col">
                {systemSessions.slice(0, 8).map((s) => (
                  <li key={s.id}>
                    <Link
                      to={`/sessions/${s.id}`}
                      className="flex items-center gap-2 border-b border-dotted border-eldir-gray-3 py-1.5 font-mono text-[11px] text-eldir-ink-2 hover:text-eldir-ink"
                    >
                      <StateDot state={s.state} size={6} decorative />
                      <span className="min-w-0 flex-1 truncate">
                        {s.system_kind === 'supervisor'
                          ? 'Eldir · superviseur'
                          : (s.summary ?? 'tâche interne')}
                      </span>
                      <span className="shrink-0 text-eldir-gray">
                        {formatAge(s.created_at)}
                      </span>
                    </Link>
                  </li>
                ))}
              </ul>
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
          <div className="inline-flex items-center gap-1 font-mono text-2xs font-semibold text-eldir-orange-text">
            {activeSessions}
            <StateDot state="thinking" size={6} />
          </div>
        )}
      </div>
    </Link>
  );
}

/**
 * Le compte rendu d'un agent est un bloc `FAIT: / FICHIERS: / RESTE: / PRET:`.
 * Tel quel sur deux lignes de carte, il se coupait en plein chemin de fichier
 * et ne disait rien. On garde la ligne qui porte le sens : le blocage s'il y
 * en a un, sinon ce qui a été fait.
 */
function resumeLisible(summary: string | null): string | null {
  if (!summary) return null;
  const lignes = summary
    .split('\n')
    .map((l) => l.trim())
    .filter(Boolean);
  const prefixe = (p: string) => lignes.find((l) => l.toUpperCase().startsWith(p));
  // Le blocage d'abord (c'est le problème), puis ce qui a été fait. `RESTE:`
  // en dernier : « RESTE: rien » est vrai mais ne dit rien.
  const retenue =
    prefixe('BLOCAGE:') ?? prefixe('FAIT:') ?? prefixe('RESTE:') ?? lignes[0];
  if (!retenue) return null;
  return retenue.replace(/^(BLOCAGE|RESTE|FAIT|FICHIERS|PRET)\s*:\s*/i, '');
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
      kind: { tone: 'gray', text: SESSION_STATE_LABEL[s.state] },
      message:
        resumeLisible(s.summary)?.slice(0, 80) ??
        (s.project_id ? (slugById.get(s.project_id) ?? '') : 'eldir'),
      messageTone: 'cream',
    };
  });
}
