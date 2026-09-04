/**
 * AppTopbar - barre supérieure persistante pour tout l'app authentifié.
 *
 * Brand + onglets navigables (NavLink) + avatar. Le rail Telemetry vit dans
 * `OpsShell`, lui-même côté contenu et donc ré-utilisable sur d'autres pages
 * sans imposer la barre.
 */

import type { ReactNode } from 'react';
import { NavLink, useLocation } from 'react-router-dom';

import { Avatar } from '@/components/eldir/avatar';
import { useSessions } from '@/lib/api/queries';
import type { SessionState } from '@/lib/constants';
import { APP_NAME } from '@/lib/constants';
import { cn } from '@/lib/utils';

const ACTIVE_STATES: ReadonlySet<SessionState> = new Set([
  'thinking',
  'tool_use',
  'waiting_input',
  'blocked',
]);

interface TopNavItem {
  to: string;
  label: string;
  /** Si fourni, l'onglet est actif quand le pathname commence par cette valeur. */
  matchPrefix?: string;
}

const NAV_ITEMS: readonly TopNavItem[] = [
  { to: '/', label: 'Ops' },
  { to: '/supervisor', label: 'Eldir', matchPrefix: '/supervisor' },
  { to: '/projects', label: 'Projects', matchPrefix: '/projects' },
  { to: '/costs', label: 'Costs', matchPrefix: '/costs' },
  { to: '/settings', label: 'Settings', matchPrefix: '/settings' },
];

interface AppTopbarProps {
  rightInfo?: ReactNode;
}

export function AppTopbar({ rightInfo }: AppTopbarProps): JSX.Element {
  const { pathname } = useLocation();
  const sessions = useSessions();
  const activeCount = (sessions.data ?? []).filter((s) =>
    ACTIVE_STATES.has(s.state),
  ).length;
  return (
    <header className="flex h-[42px] items-center gap-3.5 border-b border-eldir-gray-3 bg-eldir-cream-2 px-4">
      <NavLink
        to="/"
        end
        className="font-mono text-[13px] font-bold tracking-wider text-eldir-ink"
      >
        {APP_NAME.toUpperCase()}
        <span className="text-eldir-orange">·</span>CTL
      </NavLink>
      <nav className="hidden gap-0.5 md:flex">
        {NAV_ITEMS.map((item) => {
          const isExact = pathname === item.to;
          const isPrefixed =
            item.matchPrefix !== undefined && pathname.startsWith(item.matchPrefix);
          const active = isExact || isPrefixed;
          return (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.to === '/'}
              className={cn(
                '-mb-px px-3.5 py-2.5 font-mono text-[11px] font-semibold uppercase tracking-caps transition-colors',
                active
                  ? 'border-b-2 border-eldir-orange text-eldir-ink'
                  : 'border-b-2 border-transparent text-eldir-gray hover:text-eldir-ink',
              )}
            >
              {item.label}
            </NavLink>
          );
        })}
      </nav>
      <div className="flex-1" />
      {activeCount > 0 && (
        <NavLink
          to="/"
          end
          className="hidden items-center gap-1.5 rounded-eldir border border-eldir-orange/60 bg-eldir-orange/10 px-2 py-1 font-mono text-2xs uppercase tracking-caps text-eldir-ink hover:bg-eldir-orange/20 md:inline-flex"
          aria-label={`${activeCount} session(s) active(s)`}
        >
          <span className="relative inline-flex h-1.5 w-1.5">
            <span className="absolute inset-0 animate-ping rounded-full bg-eldir-orange opacity-75" />
            <span className="relative inline-flex h-1.5 w-1.5 rounded-full bg-eldir-orange" />
          </span>
          {activeCount} actif{activeCount > 1 ? 's' : ''}
        </NavLink>
      )}
      {rightInfo && (
        <div className="hidden font-mono text-[11px] text-eldir-gray md:block">
          {rightInfo}
        </div>
      )}
      <Avatar size={24}>J</Avatar>
    </header>
  );
}
