import { Link } from 'react-router-dom';

export function NotFoundPage(): JSX.Element {
  return (
    <main className="flex h-full flex-col items-center justify-center gap-4 p-6 text-center">
      <h1 className="font-mono text-2xl font-bold">404</h1>
      <p className="font-mono text-sm text-eldir-gray">
        cette route n'existe pas (encore).
      </p>
      <Link
        to="/"
        className="rounded-eldir border border-eldir-gray-3 bg-eldir-cream px-4 py-2 font-mono text-xs uppercase tracking-caps text-eldir-ink hover:bg-eldir-cream-2"
      >
        ← retour à OPS
      </Link>
    </main>
  );
}
