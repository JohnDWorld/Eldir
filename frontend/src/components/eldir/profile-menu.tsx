/**
 * ProfileMenu - menu du profil, ancré sur l'avatar.
 *
 * Sur mobile, la topbar n'a pas la place d'afficher les onglets : ce menu
 * porte toute la navigation. Sur desktop, les onglets restent dans la barre
 * et le menu se limite au compte.
 *
 * Radix DropdownMenu apporte gratuitement le piège de focus, la fermeture au
 * clic extérieur et à Échap, et les rôles ARIA.
 */

import * as DropdownMenu from '@radix-ui/react-dropdown-menu';
import { LogOut, Menu } from 'lucide-react';
import { useNavigate } from 'react-router-dom';

import { Avatar } from '@/components/eldir/avatar';
import { useAuthStore } from '@/lib/store/auth';
import { isNavItemActive, NAV_ITEMS } from '@/lib/nav';
import { cn } from '@/lib/utils';

interface ProfileMenuProps {
  pathname: string;
  initial?: string;
}

export function ProfileMenu({
  pathname,
  initial = 'J',
}: ProfileMenuProps): JSX.Element {
  const logout = useAuthStore((s) => s.logout);
  const navigate = useNavigate();

  return (
    <DropdownMenu.Root>
      <DropdownMenu.Trigger asChild>
        <button
          type="button"
          aria-label="Menu du compte et navigation"
          className="flex min-h-11 min-w-11 items-center justify-center gap-1 rounded-eldir text-eldir-gray transition-colors hover:text-eldir-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-eldir-orange"
        >
          <Menu aria-hidden className="h-4 w-4 md:hidden" strokeWidth={2} />
          <Avatar size={26}>{initial}</Avatar>
        </button>
      </DropdownMenu.Trigger>

      <DropdownMenu.Portal>
        <DropdownMenu.Content
          align="end"
          sideOffset={8}
          className="z-50 w-56 overflow-hidden rounded-eldir border border-eldir-gray-3 bg-eldir-paper shadow-lg"
        >
          <div className="border-b border-eldir-gray-3 px-3 py-2 font-mono text-2xs uppercase tracking-caps text-eldir-gray">
            Navigation
          </div>

          {NAV_ITEMS.map((item) => {
            const active = isNavItemActive(item, pathname);
            const Icon = item.icon;
            return (
              <DropdownMenu.Item
                key={item.to}
                onSelect={() => navigate(item.to)}
                className={cn(
                  'flex min-h-11 cursor-pointer select-none items-center gap-2.5 px-3 font-sans text-sm outline-none transition-colors data-[highlighted]:bg-eldir-cream md:hidden',
                  active
                    ? 'font-semibold text-eldir-ink'
                    : 'text-eldir-ink-2',
                )}
              >
                <Icon
                  aria-hidden
                  strokeWidth={1.75}
                  className={cn(
                    'h-4 w-4 shrink-0',
                    active ? 'text-eldir-orange' : 'text-eldir-gray',
                  )}
                />
                {item.label}
                {active && (
                  <span
                    aria-hidden
                    className="ml-auto h-1.5 w-1.5 rounded-full bg-eldir-orange"
                  />
                )}
              </DropdownMenu.Item>
            );
          })}

          <DropdownMenu.Separator className="h-px bg-eldir-gray-3 md:hidden" />

          <DropdownMenu.Item
            onSelect={() => {
              logout();
              navigate('/login');
            }}
            className="flex min-h-11 cursor-pointer select-none items-center gap-2.5 px-3 font-sans text-sm text-eldir-red outline-none transition-colors data-[highlighted]:bg-eldir-red/10"
          >
            <LogOut aria-hidden strokeWidth={1.75} className="h-4 w-4 shrink-0" />
            Se déconnecter
          </DropdownMenu.Item>
        </DropdownMenu.Content>
      </DropdownMenu.Portal>
    </DropdownMenu.Root>
  );
}
