/**
 * SessionPage - D1DeskSession portée.
 *
 * Layout desktop : sidebar sessions (200px) | chat (1fr) | logs+events live (1fr) | meta (240px)
 * Layout mobile  : tabs CHAT | LIVE | META, full-width.
 */

import {
  ChevronLeft,
  Lock,
  LockOpen,
  SendHorizontal,
  TriangleAlert,
  Wrench,
} from 'lucide-react';
import { useEffect, useMemo, useRef, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';

import { formatCost, formatDateTime, formatTokens } from '@/lib/format';
import { Avatar } from '@/components/eldir/avatar';
import { StatePill } from '@/components/eldir/state-pill';
import {
  MESSAGE_ORIGIN_AGENT_PREFIX,
  MESSAGE_ORIGIN_ELDIR,
  MESSAGE_ORIGIN_USER,
  SESSION_STATE_LABEL,
} from '@/lib/constants';
import { DiffPanel } from '@/features/sessions/diff-panel';
import { CommitDialog, OpenPrDialog } from '@/features/sessions/git-actions';
import { SessionActions } from '@/features/sessions/session-actions';
import { messagesEnAttente } from '@/features/sessions/pending-messages';
import { useSessionStream } from '@/hooks/use-session-stream';
import {
  useDeleteSession,
  useSetPublishPermission,
  useProjects,
  useSendMessage,
  useSession,
  useSessionCostTotals,
  useSessionEvents,
  useSessionGitStatus,
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
  const publishPermission = useSetPublishPermission(sessionId);
  const gitStatus = useSessionGitStatus(sessionId);
  const changeCount =
    (gitStatus.data?.modified ?? 0) +
    (gitStatus.data?.added ?? 0) +
    (gitStatus.data?.deleted ?? 0) +
    (gitStatus.data?.untracked ?? 0);
  const navigate = useNavigate();
  const [rightTab, setRightTab] = useState<'live' | 'diff'>('live');
  const [gitDialog, setGitDialog] = useState<'commit' | 'pr' | null>(null);
  // Sous `md`, les trois colonnes ne tiennent pas : on n'en montre qu'une,
  // choisie ici. Le rail réutilise `rightTab`, donc on le synchronise.
  const [mobileTab, setMobileTab] = useState<'chat' | 'diff' | 'live'>('chat');
  const selectMobileTab = (tab: 'chat' | 'diff' | 'live') => {
    setMobileTab(tab);
    if (tab !== 'chat') setRightTab(tab);
  };
  // Les sessions système (superviseur, générateur de template) n'exposent ni
  // git ni diff. Seul le superviseur porte le nom « Eldir ».
  const isSystem = session.data?.is_system === true;
  const isSupervisor = session.data?.system_kind === 'supervisor';

  const handleDelete = async () => {
    if (!sessionId) return;
    if (!confirm("Supprimer cette session ? L'historique et les events seront effacés.")) return;
    try {
      await deleteMut.mutateAsync(sessionId);
      navigate('/');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Erreur suppression');
    }
  };

  const [input, setInput] = useState('');
  // Ce que John a envoyé et que le fil ne porte pas encore. Un tableau de
  // textes et pas un compteur : on les affiche, on ne les dénombre pas.
  const [envoyes, setEnvoyes] = useState<string[]>([]);
  const composer = useRef<HTMLTextAreaElement>(null);
  useEffect(() => {
    const el = composer.current;
    if (!el) return;
    // `auto` d'abord, sinon la hauteur ne redescend jamais quand on efface.
    el.style.height = 'auto';
    el.style.height = `${el.scrollHeight}px`;
  }, [input]);
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
      const dup = seen.some((s) => s.fingerprint === fingerprint && Math.abs(s.ts - ts) < 2000);
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

  const enAttente = useMemo(
    () => messagesEnAttente(envoyes, events),
    [envoyes, events],
  );

  const handleSend = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    const content = input.trim();
    if (!content) return;
    setInput('');
    setEnvoyes((liste) => [...liste, content]);
    try {
      await sendMessage.mutateAsync({ content });
    } catch (err) {
      // Le message n'est pas parti : on le rend à John au lieu de le perdre.
      // Sans ça, un réseau coupé effaçait un paragraphe tapé au pouce.
      setEnvoyes((liste) => {
        const i = liste.lastIndexOf(content);
        return i === -1 ? liste : [...liste.slice(0, i), ...liste.slice(i + 1)];
      });
      setInput((current) => (current.length === 0 ? content : current));
      setError(
        err instanceof Error
          ? `Message non envoyé : ${err.message}`
          : 'Message non envoyé.',
      );
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
      <main className="flex h-full flex-col items-center justify-center gap-3 p-6 text-center">
        <p className="font-sans text-sm text-eldir-red-text">
          {session.error?.message ?? 'Cette session est introuvable.'}
        </p>
        <Link to="/" className="eldir-btn eldir-btn--secondary eldir-btn--sm">
          <ChevronLeft size={14} aria-hidden="true" />
          retour au pilotage
        </Link>
      </main>
    );
  }

  return (
    <div className="flex h-full flex-col bg-eldir-paper">
      {/* Topbar */}
      <header className="flex h-12 shrink-0 items-center gap-2 border-b border-eldir-gray-3 bg-eldir-cream-2 px-3 md:h-[42px] md:gap-3.5 md:px-4">
        <Link
          to="/"
          aria-label="Retour au pilotage"
          className="-ml-2 inline-flex min-h-11 min-w-11 shrink-0 items-center justify-center gap-0.5 rounded-eldir font-mono text-xs uppercase tracking-caps text-eldir-gray hover:text-eldir-ink sm:min-w-0 sm:px-1 md:min-h-0"
        >
          <ChevronLeft size={14} aria-hidden="true" />
          <span className="hidden sm:inline">pilotage</span>
        </Link>
        {/* Le titre de l'écran, c'est le projet sur lequel l'agent travaille.
            L'identifiant de session ne disait rien à personne. */}
        <h1 className="min-w-0 truncate font-sans text-sm font-semibold text-eldir-ink">
          {isSupervisor
            ? 'Eldir'
            : (projects.data?.find((p) => p.id === session.data?.project_id)?.name ??
              'Session')}
        </h1>
        <StatePill state={session.data.state} />
        <span className="hidden min-w-0 truncate font-mono text-[11px] text-eldir-gray lg:inline">
          {session.data.branch}
        </span>
        <div className="flex-1" />
        {!isSystem && (
          <>
            {gitStatus.data?.has_changes && (
              <span
                className="font-mono text-2xs uppercase tracking-caps text-eldir-amber-text"
                title="Modifications non commitées dans le worktree"
              >
                {changeCount} modif{changeCount > 1 ? 's' : ''}
              </span>
            )}
            <span
              className={cn(
                'inline-flex items-center gap-1 font-mono text-2xs uppercase tracking-caps',
                session.data.publish_allowed ? 'text-eldir-gold-text' : 'text-eldir-gray',
              )}
              title={
                session.data.publish_allowed
                  ? 'L’agent peut commiter, pousser et ouvrir une PR lui-même.'
                  : 'Les commandes git de l’agent sont refusées. Toi, tu publies quand tu veux.'
              }
            >
              {session.data.publish_allowed ? (
                <LockOpen size={11} aria-hidden="true" />
              ) : (
                <Lock size={11} aria-hidden="true" />
              )}
              <span className="hidden sm:inline">
                {session.data.publish_allowed ? 'agent : publie' : 'agent : ne publie pas'}
              </span>
            </span>
          </>
        )}
        <SessionActions
          isSystem={isSystem}
          publishAllowed={session.data.publish_allowed}
          publishPending={publishPermission.isPending}
          onTogglePublish={(allowed) => publishPermission.mutate(allowed)}
          hasChanges={Boolean(gitStatus.data?.has_changes)}
          onCommit={() => setGitDialog('commit')}
          onOpenPr={() => setGitDialog('pr')}
          onStop={() => stopMut.mutate(sessionId)}
          onDelete={handleDelete}
          deletePending={deleteMut.isPending}
        />
      </header>

      {gitDialog === 'commit' && (
        <CommitDialog
          sessionId={sessionId}
          branch={gitStatus.data?.branch}
          onClose={() => setGitDialog(null)}
        />
      )}
      {gitDialog === 'pr' && (
        <OpenPrDialog
          sessionId={sessionId}
          branch={gitStatus.data?.branch}
          onClose={() => setGitDialog(null)}
        />
      )}

      {/* Sélecteur de panneau, mobile uniquement */}
      <div className="flex shrink-0 border-b border-eldir-gray-3 bg-eldir-cream-2 md:hidden">
        {(['chat', 'diff', 'live'] as const).map((tab) => (
          <button
            key={tab}
            type="button"
            onClick={() => selectMobileTab(tab)}
            className={cn(
              'min-h-11 flex-1 px-3 font-mono text-2xs uppercase tracking-caps transition-colors',
              mobileTab === tab
                ? 'border-b-2 border-eldir-orange bg-eldir-paper text-eldir-ink'
                : 'border-b-2 border-transparent text-eldir-gray',
            )}
          >
            {MOBILE_TAB_LABEL[tab]}
          </button>
        ))}
      </div>

      <div className="grid min-h-0 min-w-0 flex-1 grid-cols-1 md:grid-cols-[220px_1fr_320px]">
        {/* Sidebar sessions */}
        <aside className="hidden flex-col overflow-y-auto border-r border-eldir-gray-3 py-2.5 md:flex">
          <div className="eldir-caps px-3 pb-2">Sessions</div>
          {(sessions.data ?? [])
            .filter(
              // Les générateurs de template sont des sessions jetables gardées
              // pour l'audit des coûts : hors de la navigation, sauf celle
              // qu'on regarde.
              (s) => !s.is_system || s.system_kind === 'supervisor' || s.id === sessionId,
            )
            .map((s) => {
              const project = projects.data?.find((p) => p.id === s.project_id);
              const label =
                s.system_kind === 'supervisor'
                  ? 'Eldir · superviseur'
                  : s.is_system
                    ? `système · ${SYSTEM_KIND_LABEL[s.system_kind ?? ''] ?? 'tâche interne'}`
                    : (project?.name ?? 'projet inconnu');
              const active = s.id === sessionId;
              return (
                <Link
                  key={s.id}
                  to={`/sessions/${s.id}`}
                  aria-current={active ? 'page' : undefined}
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
                  <span className="ml-5 truncate text-eldir-gray">{s.id.slice(0, 8)}</span>
                </Link>
              );
            })}
        </aside>

        {/* Chat */}
        <section
          className={cn(
            'min-h-0 min-w-0 flex-col overflow-hidden border-r border-eldir-gray-3 md:flex',
            mobileTab === 'chat' ? 'flex' : 'hidden',
          )}
        >
          <ChatStream events={events} />
          {enAttente.length > 0 && (
            <ul className="shrink-0 space-y-1 border-t border-eldir-gray-3 px-4 py-2">
              {enAttente.map((texte, i) => (
                <li
                  key={`${texte}-${i}`}
                  className="ml-auto max-w-[85%] rounded-eldir bg-eldir-cream-2 px-3 py-2 text-sm text-eldir-gray"
                >
                  <span className="whitespace-pre-wrap break-words">{texte}</span>
                  <span className="eldir-caps ml-2 whitespace-nowrap">en attente</span>
                </li>
              ))}
            </ul>
          )}
          {error && (
            <div className="border-t border-eldir-gray-3 px-4 py-2 font-mono text-xs text-eldir-red-text">
              {error}
            </div>
          )}
          <form onSubmit={handleSend} className="border-t border-eldir-gray-3 bg-eldir-paper p-3">
            {/* Pas de padding vertical sur la ligne : la zone de saisie et le
                bouton font tous les deux 44px, donc ils s'alignent d'eux-mêmes
                sur une ligne. Sinon le bouton, plus haut que le texte, créait
                un vide au-dessus qui ressemblait à un saut de ligne. */}
            <div className="flex items-end gap-2 rounded-eldir border border-eldir-gray-3 bg-eldir-cream px-3">
              <span className="self-start py-3 font-mono text-xs leading-5 text-eldir-orange-text">
                ›
              </span>
              <textarea
                ref={composer}
                rows={1}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => {
                  // Entrée seule insère une ligne (indispensable au clavier
                  // tactile), ⌘/Ctrl + Entrée envoie, comme l'annonce le
                  // raccourci affiché.
                  if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) {
                    e.preventDefault();
                    void handleSend(e);
                  }
                }}
                placeholder={isSupervisor ? 'Écris à Eldir…' : 'Écris à Claude…'}
                aria-label="Message"
                className="max-h-40 min-h-11 min-w-0 flex-1 resize-none overflow-y-auto bg-transparent py-3 font-sans text-sm leading-5 text-eldir-ink"
              />
              <button
                type="submit"
                disabled={input.trim().length === 0}
                aria-label="Envoyer le message"
                title="Envoyer (⌘ ou Ctrl + Entrée)"
                className="flex h-11 w-11 shrink-0 items-center justify-center rounded-eldir bg-eldir-orange font-mono text-sm text-eldir-on-orange transition-colors hover:bg-eldir-orange/90 disabled:opacity-40"
              >
                <SendHorizontal size={16} aria-hidden="true" />
              </button>
            </div>
            <p className="mt-1.5 hidden font-mono text-2xs text-eldir-gray md:block">
              Entrée pour une nouvelle ligne · ⌘/Ctrl + Entrée pour envoyer
            </p>
          </form>
        </section>

        {/* Right rail : Session meta (top) + Logs live stream (bottom) */}
        <aside
          className={cn(
            'min-h-0 min-w-0 flex-col overflow-hidden border-l border-eldir-gray-3 md:flex',
            mobileTab === 'chat' ? 'hidden' : 'flex',
          )}
        >
          <div className="flex flex-col gap-3 border-b border-eldir-gray-3 bg-eldir-paper p-4">
            <div className="eldir-caps">Détails</div>
            <Kv k="id" v={session.data.id.slice(0, 12)} />
            {(() => {
              const project = projects.data?.find((p) => p.id === session.data.project_id);
              return (
                <>
                  <Kv k="projet" v={isSupervisor ? 'superviseur' : (project?.name ?? '-')} />
                  <Kv k="repo" v={project?.repo_full_name ?? '-'} />
                </>
              );
            })()}
            <Kv k="branche" v={session.data.branch} />
            <Kv k="état" v={SESSION_STATE_LABEL[session.data.state]} />
            <Kv k="modèle" v={session.data.model ?? '-'} />
            <Kv k="créée" v={formatDateTime(session.data.created_at)} />
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
              label={`direct · ${CONNECTION_LABEL[live.state] ?? live.state}`}
              active={rightTab === 'live'}
              onClick={() => setRightTab('live')}
            />
            {!isSystem && (
              <RightTab
                label="diff"
                active={rightTab === 'diff'}
                onClick={() => setRightTab('diff')}
              />
            )}
          </div>

          {rightTab === 'live' || isSystem ? (
            <section className="flex min-h-0 flex-1 flex-col overflow-hidden bg-eldir-console">
              <div className="flex-1 overflow-y-auto p-3 font-mono text-[11px] leading-relaxed text-eldir-console-fg">
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
const MOBILE_TAB_LABEL = { chat: 'fil', diff: 'diff', live: 'direct' } as const;

const CONNECTION_LABEL: Record<string, string> = {
  idle: 'inactif',
  connecting: 'connexion…',
  open: 'connecté',
  closed: 'coupé',
};

const SYSTEM_KIND_LABEL: Record<string, string> = {
  template_generator: 'génération de template',
  supervisor: 'superviseur',
};

interface NormalizedEvent {
  key: string;
  type: SessionEvent['type'] | SessionEventRead['type'];
  timestamp: string;
  data: Record<string, unknown>;
}

/**
 * Qui a écrit ce message, d'après son `origin` : `null` pour John, sinon le libellé
 * de l'encart qui le dit. Seuls un `origin` absent (event écrit avant l'ajout du
 * champ) et `user` sont John. Une origine qu'on ne reconnaît pas n'est pas lui non
 * plus : l'afficher comme sa bulle serait mentir sur qui a demandé quoi.
 *
 * Le libellé d'un agent arrive déjà sur une seule ligne (cf. `origine_de_dispatch`
 * côté backend) : il n'y a rien à nettoyer ici.
 */
function auteurDuMessage(origin: unknown): string | null {
  if (origin === undefined || origin === MESSAGE_ORIGIN_USER) return null;
  if (origin === MESSAGE_ORIGIN_ELDIR) return 'Eldir · automatique';
  if (typeof origin !== 'string') return 'origine inconnue';
  if (origin.startsWith(MESSAGE_ORIGIN_AGENT_PREFIX)) {
    const nom = origin.slice(MESSAGE_ORIGIN_AGENT_PREFIX.length);
    return nom ? `agent « ${nom} »` : 'agent sans nom';
  }
  return `origine « ${origin} »`;
}

export function ChatStream({ events }: { events: NormalizedEvent[] }): JSX.Element {
  const scroll = useRef<HTMLDivElement>(null);
  // Suit le bas du fil seulement si John y était déjà. Sinon, remonter lire
  // une réponse pendant que l'agent travaille le ramenait en bas à chaque
  // outil lancé.
  const stuckToBottom = useRef(true);
  useEffect(() => {
    const el = scroll.current;
    if (el && stuckToBottom.current) el.scrollTop = el.scrollHeight;
  }, [events.length]);

  // Les erreurs étaient filtrées : un tour qui plantait ne laissait aucune
  // trace dans le fil, la session repassait « au repos », et on pouvait croire
  // le travail terminé. Elles s'affichent maintenant comme le reste.
  const visible = events
    .filter(
      (e) =>
        e.type === 'text' ||
        e.type === 'tool_use' ||
        e.type === 'stop' ||
        e.type === 'error' ||
        e.type === 'user_message',
    )
    .filter((e, i, all) => !(e.type === 'stop' && all[i - 1]?.type === 'stop'));

  return (
    <div
      ref={scroll}
      onScroll={(e) => {
        const el = e.currentTarget;
        stuckToBottom.current = el.scrollHeight - el.scrollTop - el.clientHeight < 80;
      }}
      role="log"
      aria-live="polite"
      className="min-w-0 flex-1 space-y-3 overflow-y-auto bg-eldir-paper p-4"
    >
      {visible.length === 0 && (
        <p className="mx-auto max-w-sm pt-8 text-center font-sans text-sm text-eldir-gray">
          Rien pour l&apos;instant. Écris une consigne en bas : l&apos;agent
          lit le repo, travaille, et te rend un compte rendu à la fin du tour.
        </p>
      )}
      {visible.map((e) => {
        if (e.type === 'user_message') {
          // Eldir parle aussi dans le fil : consigne dispatchée par le
          // superviseur ou par un agent extérieur, ping de fin de tour. L'afficher
          // comme un message de John ferait croire qu'il l'a écrit.
          const auteur = auteurDuMessage(e.data.origin);
          const texte = String(e.data.text ?? '');
          if (auteur === null) return <UserBubble key={e.key}>{texte}</UserBubble>;
          return (
            <EldirNotice key={e.key} auteur={auteur}>
              {texte}
            </EldirNotice>
          );
        }
        if (e.type === 'text') {
          return <ClaudeBubble key={e.key}>{String(e.data.text ?? '')}</ClaudeBubble>;
        }
        if (e.type === 'error') {
          return (
            <TurnError key={e.key}>
              {String(e.data.message ?? 'Erreur inconnue.')}
            </TurnError>
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
        // `turn_complete` = Claude a fini de répondre ; sans raison = la
        // session elle-même a été arrêtée. Deux faits différents.
        return (
          <div
            key={e.key}
            className="flex items-center gap-3 font-mono text-2xs uppercase tracking-caps text-eldir-gray"
          >
            <span className="h-px flex-1 bg-eldir-gray-3" />
            {e.data.reason === 'turn_complete' ? 'tour terminé' : 'session arrêtée'}
            <span className="h-px flex-1 bg-eldir-gray-3" />
          </div>
        );
      })}
    </div>
  );
}

/** Un tour qui a échoué. Visible dans le fil, pas seulement dans la console. */
function TurnError({ children }: { children: React.ReactNode }): JSX.Element {
  return (
    <div
      role="alert"
      className="rounded-eldir border border-eldir-red/50 bg-eldir-red/5 px-3 py-2"
    >
      <div className="eldir-caps mb-1 flex items-center gap-1.5 text-eldir-red-text">
        <TriangleAlert size={12} aria-hidden="true" />
        Tour interrompu
      </div>
      <div className="whitespace-pre-wrap break-words font-sans text-sm text-eldir-ink-2">
        {children}
      </div>
      <p className="mt-1.5 font-sans text-xs text-eldir-gray">
        Le travail déjà fait reste dans le worktree. Relance une consigne pour
        reprendre là où l’agent s’est arrêté.
      </p>
    </div>
  );
}

function EldirNotice({
  auteur,
  children,
}: {
  auteur: string;
  children: React.ReactNode;
}): JSX.Element {
  return (
    <div className="rounded-eldir border border-eldir-orange/35 bg-eldir-orange/5 px-3 py-2">
      <div className="eldir-caps mb-1 break-words text-eldir-orange-text">{auteur}</div>
      <div className="whitespace-pre-wrap break-words font-sans text-sm text-eldir-ink-2">
        {children}
      </div>
    </div>
  );
}

function UserBubble({ children }: { children: React.ReactNode }): JSX.Element {
  return (
    <div className="flex justify-end">
      <div className="max-w-[90%] whitespace-pre-wrap break-words rounded-[10px_2px_10px_10px] border border-eldir-orange/30 bg-eldir-orange/10 px-3 py-2 font-sans text-sm text-eldir-ink">
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

/**
 * Texte d'agent : prose et blocs de code séparés. Un agent de code répond avec
 * des extraits, du JSON, des diffs ; en police proportionnelle et sans
 * alignement, c'était illisible. Pas de moteur Markdown complet : les blocs
 * ``` suffisent à rendre la réponse lisible, sans dépendance de plus.
 */
function RichText({ text }: { text: string }): JSX.Element {
  // Une clôture ``` n'ouvre un bloc qu'en début de ligne. Au milieu d'une
  // ligne (dans une chaîne JSON, par exemple), c'est du texte : la découper
  // là produisait des blocs de code au hasard.
  const blocks: { code: boolean; lines: string[] }[] = [];
  let current: { code: boolean; lines: string[] } = { code: false, lines: [] };
  for (const line of text.split('\n')) {
    if (/^\s*```/.test(line)) {
      blocks.push(current);
      current = { code: !current.code, lines: [] };
      continue;
    }
    current.lines.push(line);
  }
  blocks.push(current);

  return (
    <>
      {blocks.map((block, i) => {
        const body = block.lines.join('\n');
        if (block.code) {
          return (
            <pre
              key={i}
              className="my-2 overflow-x-auto rounded-eldir bg-eldir-console px-3 py-2 font-mono text-xs leading-relaxed text-eldir-console-fg"
            >
              {body}
            </pre>
          );
        }
        const prose = body.replace(/^\n+|\n+$/g, '');
        return prose.trim().length > 0 ? (
          <span key={i} className="block whitespace-pre-wrap break-words">
            {prose}
          </span>
        ) : null;
      })}
    </>
  );
}

function ClaudeBubble({ children }: { children: string }): JSX.Element {
  return (
    <div className="flex max-w-[90%] min-w-0 gap-2">
      <Avatar bg="hsl(var(--eldir-orange))" fg="hsl(var(--eldir-on-orange))" size={20}>
        C
      </Avatar>
      <div className="min-w-0 rounded-[2px_10px_10px_10px] border border-eldir-gray-3 bg-eldir-cream px-3 py-2 font-sans text-sm leading-relaxed text-eldir-ink">
        <RichText text={children} />
      </div>
    </div>
  );
}

function ToolRow({ name, arg }: { name: string; arg: string }): JSX.Element {
  return (
    <div className="flex min-w-0 max-w-full items-center gap-2 rounded-eldir border border-dashed border-eldir-gray-2 px-2.5 py-1.5 font-mono text-2xs text-eldir-gray">
      <Wrench size={11} aria-hidden="true" className="shrink-0 text-eldir-gold-text" />
      <span className="shrink-0 text-eldir-ink">{name}</span>
      {arg && <span className="min-w-0 flex-1 truncate opacity-70">({arg})</span>}
    </div>
  );
}

function LogLine({ event }: { event: NormalizedEvent }): JSX.Element {
  const time = new Date(event.timestamp).toLocaleTimeString('fr-FR', {
    hour12: false,
  });
  // Console sombre : accents clairs.
  const tone: Record<string, string> = {
    text: 'text-eldir-console-fg',
    tool_use: 'text-eldir-gold',
    tool_result: 'text-eldir-console-fg/55',
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
    <div className="flex min-w-0 gap-2">
      <span className="shrink-0 text-eldir-console-fg/55">{time}</span>
      <span className={cn('w-20 shrink-0', tone[event.type] ?? 'text-eldir-console-fg')}>
        {event.type}
      </span>
      <span className="min-w-0 flex-1 truncate text-eldir-console-fg">{summary}</span>
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
  const cacheRatio =
    totalBillable + cacheReadTokens > 0
      ? Math.round((cacheReadTokens / (totalBillable + cacheReadTokens)) * 100)
      : 0;
  return (
    <div
      className={cn(
        'flex flex-col gap-2 border-b p-4',
        overBudget ? 'border-eldir-red/50 bg-eldir-red/5' : 'border-eldir-gray-3 bg-eldir-paper',
      )}
    >
      <div className="flex items-center justify-between">
        <span className="eldir-caps">Coût · session</span>
        {overBudget && (
          <span className="font-mono text-2xs font-semibold uppercase tracking-caps text-eldir-red-text">
            budget dépassé
          </span>
        )}
      </div>
      <div className="flex items-baseline gap-2">
        <span className="font-mono text-base font-bold text-eldir-ink">
          {formatCost(costUsd)}
        </span>
        <span className="font-mono text-2xs text-eldir-gray">
          {numTurns} tour{numTurns > 1 ? 's' : ''}
        </span>
      </div>
      <Kv k="entrée" v={formatTokens(inputTokens)} />
      <Kv k="sortie" v={formatTokens(outputTokens)} />
      <Kv k="cache lu" v={`${formatTokens(cacheReadTokens)} (${cacheRatio}%)`} />
    </div>
  );
}

function Kv({ k, v }: { k: string; v: string }): JSX.Element {
  return (
    <div className="flex justify-between gap-2 border-b border-dotted border-eldir-gray-3 pb-1 font-mono text-xs">
      <span className="shrink-0 text-eldir-gray">{k}</span>
      <span className="min-w-0 truncate text-eldir-ink" title={v}>
        {v}
      </span>
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
