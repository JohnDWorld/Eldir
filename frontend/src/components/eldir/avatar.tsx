/**
 * Avatar - pastille texte (initiales). Pas de chargement d'image - image vivra
 * plus tard derrière `<img>` dans la version finale.
 */

import { cn } from '@/lib/utils';

interface AvatarProps {
  children: string;
  size?: number;
  bg?: string;
  fg?: string;
  className?: string;
}

export function Avatar({
  children,
  size = 22,
  bg = 'hsl(var(--eldir-ink))',
  fg = 'hsl(var(--eldir-cream))',
  className,
}: AvatarProps): JSX.Element {
  return (
    <span
      style={{ width: size, height: size, background: bg, color: fg }}
      className={cn(
        'inline-flex shrink-0 items-center justify-center rounded-full font-sans text-[10px] font-semibold leading-none',
        className,
      )}
    >
      {children}
    </span>
  );
}
