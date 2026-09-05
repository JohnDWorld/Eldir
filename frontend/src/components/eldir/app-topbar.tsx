/**
 * AppTopbar - barre supérieure persistante pour tout l'app authentifié.
 *
 * Desktop : brand + onglets + télémétrie + avatar.
 * Mobile  : brand + libellé de la page courante + bouton menu (ProfileMenu),
 * parce que cinq onglets ne tiennent pas sous 375px. La navigation reste donc
 * atteignable partout, sans barre du bas qui mange la hauteur utile.
 */

import type { ReactNode } from 'react';
import { NavLink, useLocation } from 'react-router-dom';

import { ProfileMenu } from '@/components/eldir/profile-menu';
import { useSessions } from '@/lib/api/queries';
import type { SessionState } from '@/lib/constants';
import { APP_NAME } from '@/lib/constants';
import { currentNavLabel, isNavItemActive, NAV_ITEMS } from '@/lib/nav';
import { cn } from '@/lib/utils';

const ACTIVE_STATES: ReadonlySet<SessionState> = new Set([
  'thinking',
  'tool_use',
  'waiting_input',
  'blocked',
]);

interface AppTopbarProps {
  rightInfo?: ReactNode;
}

export function AppTopbar({ rightInfo }: AppTopbarProps): JSX.Element {
  const { pathname } = useLocation();
  const sessions = useSessions();
  const activeCount = (sessions.data ?? []).filter((s) =>
    ACTIVE_STATES.has(s.state),
  ).length;
  const pageLabel = currentNavLabel(pathname);

  return (
    <header className="flex h-12 shrink-0 items-center gap-2 border-b border-eldir-gray-3 bg-eldir-cream-2 px-3 md:h-[42px] md:gap-3.5 md:px-4">
      <NavLink
        to="/"
        end
        className="shrink-0 font-mono text-[13px] font-bold tracking-wider text-eldir-ink"
      >
        {APP_NAME.toUpperCase()}
        <span className="text-eldir-orange">·</span>CTL
      </NavLink>

      {/* Mobile : le fil d'ariane remplace les onglets absents. */}
      {pageLabel && (
        <span className="min-w-0 truncate font-mono text-[11px] uppercase tracking-caps text-eldir-gray md:hidden">
          / {pageLabel}
        </span>
      )}

      <nav className="hidden gap-0.5 md:flex" aria-label="Navigation principale">
        {NAV_ITEMS.map((item) => {
          const active = isNavItemActive(item, pathname);
          return (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.to === '/'}
              aria-current={active ? 'page' : undefined}
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
          className="inline-flex shrink-0 items-center gap-1.5 rounded-eldir border border-eldir-orange/60 bg-eldir-orange/10 px-2 py-1 font-mono text-2xs uppercase tracking-caps text-eldir-ink hover:bg-eldir-orange/20"
          aria-label={`${activeCount} session(s) active(s)`}
        >
          <span className="relative inline-flex h-1.5 w-1.5">
            <span className="absolute inset-0 animate-ping rounded-full bg-eldir-orange opacity-75" />
            <span className="relative inline-flex h-1.5 w-1.5 rounded-full bg-eldir-orange" />
          </span>
          {activeCount}
          <span className="hidden sm:inline">actif{activeCount > 1 ? 's' : ''}</span>
        </NavLink>
      )}

      {rightInfo && (
        <div className="hidden font-mono text-[11px] text-eldir-gray md:block">
          {rightInfo}
        </div>
      )}

      <ProfileMenu pathname={pathname} />
    </header>
  );
}
