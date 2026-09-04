/**
 * BottomNav - navigation principale sur mobile.
 *
 * La topbar masque ses onglets sous `md` (place insuffisante) : sans cette
 * barre, un téléphone n'avait plus aucun accès à Projects, Costs ou Settings.
 * Posée en frère de l'Outlet dans le flux, pas en `fixed` : elle prend sa
 * place, donc rien à compenser en padding et aucun recouvrement du champ de
 * saisie du chat.
 */

import { NavLink, useLocation } from 'react-router-dom';

import { isNavItemActive, NAV_ITEMS } from '@/lib/nav';
import { cn } from '@/lib/utils';

export function BottomNav(): JSX.Element {
  const { pathname } = useLocation();
  return (
    <nav
      className="flex shrink-0 border-t border-eldir-gray-3 bg-eldir-cream-2 pb-[env(safe-area-inset-bottom)] md:hidden"
      aria-label="Navigation principale"
    >
      {NAV_ITEMS.map((item) => {
        const active = isNavItemActive(item, pathname);
        return (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.to === '/'}
            aria-current={active ? 'page' : undefined}
            className={cn(
              // 44px minimum de hauteur : cf. design system, tap targets.
              'flex min-h-11 flex-1 flex-col items-center justify-center gap-0.5 py-1.5 font-mono text-2xs uppercase tracking-caps transition-colors',
              active
                ? 'border-t-2 border-eldir-orange text-eldir-ink'
                : 'border-t-2 border-transparent text-eldir-gray',
            )}
          >
            <span aria-hidden className="text-sm leading-none">
              {item.glyph}
            </span>
            {item.label}
          </NavLink>
        );
      })}
    </nav>
  );
}
