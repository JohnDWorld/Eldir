/**
 * AppTopbar — barre supérieure persistante pour tout l'app authentifié.
 *
 * Brand + onglets navigables (NavLink) + avatar. Le rail Telemetry vit dans
 * `OpsShell`, lui-même côté contenu et donc ré-utilisable sur d'autres pages
 * sans imposer la barre.
 */

import type { ReactNode } from 'react';
import { NavLink, useLocation } from 'react-router-dom';

import { Avatar } from '@/components/eldir/avatar';
import { APP_NAME } from '@/lib/constants';
import { cn } from '@/lib/utils';

interface TopNavItem {
  to: string;
  label: string;
  /** Si fourni, l'onglet est actif quand le pathname commence par cette valeur. */
  matchPrefix?: string;
}

const NAV_ITEMS: readonly TopNavItem[] = [
  { to: '/', label: 'Ops' },
  { to: '/projects', label: 'Projects', matchPrefix: '/projects' },
  { to: '/settings', label: 'Settings', matchPrefix: '/settings' },
];

interface AppTopbarProps {
  rightInfo?: ReactNode;
}

export function AppTopbar({ rightInfo }: AppTopbarProps): JSX.Element {
  const { pathname } = useLocation();
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
      {rightInfo && (
        <div className="hidden font-mono text-[11px] text-eldir-gray md:block">
          {rightInfo}
        </div>
      )}
      <Avatar size={24}>J</Avatar>
    </header>
  );
}
