import { ChevronLeft } from 'lucide-react';
import { Link } from 'react-router-dom';

export function NotFoundPage(): JSX.Element {
  return (
    <main className="flex h-full flex-col items-center justify-center gap-4 p-6 text-center">
      <h1 className="eldir-title">Cette page n&apos;existe pas</h1>
      <p className="max-w-sm font-sans text-sm text-eldir-ink-2">
        Le lien est peut-être ancien, ou la session a été supprimée.
      </p>
      <Link
        to="/"
        className="eldir-btn eldir-btn--secondary"
      >
        <ChevronLeft size={14} aria-hidden="true" />
        retour à ops
      </Link>
    </main>
  );
}
