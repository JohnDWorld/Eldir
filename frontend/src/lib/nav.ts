/**
 * Navigation principale - source unique pour la topbar (desktop) et la
 * barre du bas (mobile). Cf. AGENTS.md §DRY.
 */

export interface NavItem {
  to: string;
  label: string;
  /** Pictogramme de la barre du bas (mobile). */
  glyph: string;
  /** Si fourni, l'onglet est actif quand le pathname commence par cette valeur. */
  matchPrefix?: string;
}

export const NAV_ITEMS: readonly NavItem[] = [
  { to: '/', label: 'Ops', glyph: '◆' },
  { to: '/supervisor', label: 'Eldir', glyph: '✦', matchPrefix: '/supervisor' },
  { to: '/projects', label: 'Projects', glyph: '❯', matchPrefix: '/projects' },
  { to: '/costs', label: 'Costs', glyph: '$', matchPrefix: '/costs' },
  { to: '/settings', label: 'Settings', glyph: '⚙', matchPrefix: '/settings' },
];

export function isNavItemActive(item: NavItem, pathname: string): boolean {
  if (pathname === item.to) return true;
  return item.matchPrefix !== undefined && pathname.startsWith(item.matchPrefix);
}
