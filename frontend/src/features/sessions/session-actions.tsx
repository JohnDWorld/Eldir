/**
 * SessionActions - ce qu'on peut faire d'une session, dans un seul menu.
 *
 * Avant, six contrôles s'alignaient dans l'en-tête (publication, modifs,
 * commit & push, ouvrir une PR, arrêter, supprimer), tous du même poids. Sur
 * un téléphone ils prenaient trois lignes, soit près de 180 px avant le
 * premier message : l'écran le plus consulté d'Eldir s'ouvrait sur sa barre
 * d'outils plutôt que sur la conversation.
 *
 * Ces actions servent une fois par session, à la fin. Elles vivent donc dans
 * un menu, et l'en-tête ne garde que ce qui se lit en continu : l'état de la
 * session, le nombre de modifications, et si l'agent a le droit de publier.
 *
 * L'autorisation de publier ne contraint que l'agent : le backend ne la lit
 * que pour le hook qui refuse ses commandes git. John, lui, commite et pousse
 * quand il veut, c'est tout l'intérêt de la relecture humaine. Les deux
 * actions ne sont donc jamais grisées pour lui.
 */

import * as DropdownMenu from '@radix-ui/react-dropdown-menu';
import {
  GitCommitHorizontal,
  GitPullRequest,
  Lock,
  LockOpen,
  MoreHorizontal,
  Square,
  Trash2,
} from 'lucide-react';
import { cn } from '@/lib/utils';

interface SessionActionsProps {
  /** Session système : ni git, ni publication. */
  isSystem: boolean;
  publishAllowed: boolean;
  publishPending: boolean;
  onTogglePublish: (allowed: boolean) => void;
  hasChanges: boolean;
  onCommit: () => void;
  onOpenPr: () => void;
  onStop: () => void;
  onDelete: () => void;
  deletePending: boolean;
}

const ITEM =
  'flex min-h-11 w-full cursor-pointer select-none items-center gap-2.5 px-3 font-sans text-sm outline-none transition-colors data-[highlighted]:bg-eldir-cream data-[disabled]:cursor-not-allowed data-[disabled]:opacity-45';

export function SessionActions({
  isSystem,
  publishAllowed,
  publishPending,
  onTogglePublish,
  hasChanges,
  onCommit,
  onOpenPr,
  onStop,
  onDelete,
  deletePending,
}: SessionActionsProps): JSX.Element {
  return (
    <DropdownMenu.Root>
      <DropdownMenu.Trigger asChild>
        <button
          type="button"
          aria-label="Actions de la session"
          className="flex min-h-11 min-w-11 items-center justify-center rounded-eldir text-eldir-gray transition-colors hover:bg-eldir-cream hover:text-eldir-ink md:min-h-9 md:min-w-9"
        >
          <MoreHorizontal size={18} aria-hidden="true" />
        </button>
      </DropdownMenu.Trigger>

      <DropdownMenu.Portal>
        <DropdownMenu.Content
          align="end"
          sideOffset={8}
          className="z-50 w-72 overflow-hidden rounded-eldir border border-eldir-gray-3 bg-eldir-paper shadow-lg"
        >
          {!isSystem && (
            <>
              <DropdownMenu.Item
                onSelect={() => onTogglePublish(!publishAllowed)}
                disabled={publishPending}
                className={cn(ITEM, 'text-eldir-ink-2')}
              >
                {publishAllowed ? (
                  <LockOpen size={16} aria-hidden="true" className="shrink-0 text-eldir-gold-text" />
                ) : (
                  <Lock size={16} aria-hidden="true" className="shrink-0 text-eldir-gray" />
                )}
                <span className="min-w-0">
                  {publishAllowed
                    ? 'Retirer le droit de publier à l’agent'
                    : 'Laisser l’agent publier'}
                  <span className="mt-0.5 block font-sans text-xs text-eldir-gray">
                    {publishAllowed
                      ? 'L’agent peut commiter, pousser et ouvrir une PR lui-même.'
                      : 'Les commandes git de l’agent sont refusées. Toi, tu publies quand tu veux.'}
                  </span>
                </span>
              </DropdownMenu.Item>

              <DropdownMenu.Separator className="h-px bg-eldir-gray-3" />

              <DropdownMenu.Item
                onSelect={onCommit}
                disabled={!hasChanges}
                className={cn(ITEM, 'text-eldir-ink-2')}
              >
                <GitCommitHorizontal size={16} aria-hidden="true" className="shrink-0" />
                <span className="min-w-0">
                  Commiter et pousser
                  {!hasChanges && (
                    <span className="mt-0.5 block font-sans text-xs text-eldir-gray">
                      Rien à commiter, le worktree est propre.
                    </span>
                  )}
                </span>
              </DropdownMenu.Item>

              <DropdownMenu.Item onSelect={onOpenPr} className={cn(ITEM, 'text-eldir-ink-2')}>
                <GitPullRequest size={16} aria-hidden="true" className="shrink-0" />
                <span className="min-w-0">Ouvrir une pull request</span>
              </DropdownMenu.Item>

              <DropdownMenu.Separator className="h-px bg-eldir-gray-3" />
            </>
          )}

          <DropdownMenu.Item onSelect={onStop} className={cn(ITEM, 'text-eldir-ink-2')}>
            <Square size={16} aria-hidden="true" className="shrink-0" />
            <span className="min-w-0">
              Arrêter la session
              <span className="mt-0.5 block font-sans text-xs text-eldir-gray">
                Libère un emplacement. Elle reste reprenable.
              </span>
            </span>
          </DropdownMenu.Item>

          <DropdownMenu.Item
            onSelect={onDelete}
            disabled={deletePending}
            className={cn(ITEM, 'text-eldir-red-text data-[highlighted]:bg-eldir-red/10')}
          >
            <Trash2 size={16} aria-hidden="true" className="shrink-0" />
            <span className="min-w-0">
              Supprimer la session
              <span className="mt-0.5 block font-sans text-xs text-eldir-red-text/80">
                Efface le fil et les events. Irréversible.
              </span>
            </span>
          </DropdownMenu.Item>
        </DropdownMenu.Content>
      </DropdownMenu.Portal>
    </DropdownMenu.Root>
  );
}
