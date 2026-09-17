/**
 * BackLink - retour vers la page parente, au-dessus d'un titre.
 *
 * Remplace les surtitres (« Settings · claude ») qui servaient de repère sans
 * être cliquables : ici le repère ramène vraiment quelque part.
 */

import { ChevronLeft } from 'lucide-react';
import { Link } from 'react-router-dom';

export function BackLink({ to, label }: { to: string; label: string }): JSX.Element {
  return (
    <Link
      to={to}
      className="-ml-1 inline-flex min-h-11 items-center gap-0.5 pr-2 font-mono text-2xs uppercase tracking-caps text-eldir-gray hover:text-eldir-orange md:min-h-8"
    >
      <ChevronLeft size={13} aria-hidden="true" />
      {label}
    </Link>
  );
}
