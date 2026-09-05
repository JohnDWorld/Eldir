/**
 * Navigation principale - source unique pour la topbar (desktop) et le menu
 * du profil (mobile). Cf. AGENTS.md §DRY.
 */

import {
  Activity,
  Flame,
  FolderGit2,
  Settings,
  Wallet,
  type LucideIcon,
} from 'lucide-react';

export interface NavItem {
  to: string;
  label: string;
  icon: LucideIcon;
  /** Si fourni, l'onglet est actif quand le pathname commence par cette valeur. */
  matchPrefix?: string;
}

export const NAV_ITEMS: readonly NavItem[] = [
  { to: '/', label: 'Ops', icon: Activity },
  { to: '/supervisor', label: 'Eldir', icon: Flame, matchPrefix: '/supervisor' },
  { to: '/projects', label: 'Projects', icon: FolderGit2, matchPrefix: '/projects' },
  { to: '/costs', label: 'Costs', icon: Wallet, matchPrefix: '/costs' },
  { to: '/settings', label: 'Settings', icon: Settings, matchPrefix: '/settings' },
];

export function isNavItemActive(item: NavItem, pathname: string): boolean {
  if (pathname === item.to) return true;
  return item.matchPrefix !== undefined && pathname.startsWith(item.matchPrefix);
}

/** Libellé de la page courante, affiché dans la topbar mobile. */
export function currentNavLabel(pathname: string): string | null {
  return NAV_ITEMS.find((item) => isNavItemActive(item, pathname))?.label ?? null;
}
