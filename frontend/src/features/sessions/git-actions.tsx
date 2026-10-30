/**
 * Dialogues git d'une session : commit (et push), ouverture de PR.
 *
 * Les boutons qui les ouvraient vivaient ici ; ils sont maintenant dans
 * `SessionActions`, le menu de l'en-tête. Ce fichier ne porte plus que les
 * formulaires.
 */

import { useState } from 'react';

import { ApiError } from '@/lib/api/client';
import { useCommitPush, useOpenPR } from '@/lib/api/queries';

export function CommitDialog({
  sessionId,
  branch,
  onClose,
}: {
  sessionId: string;
  branch: string | undefined;
  onClose: () => void;
}): JSX.Element {
  const commit = useCommitPush(sessionId);
  const [message, setMessage] = useState('');
  const [push, setPush] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<string | null>(null);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    if (message.trim().length < 1) {
      setError('Message requis.');
      return;
    }
    try {
      const r = await commit.mutateAsync({ message: message.trim(), push });
      setResult(
        push
          ? `Commit ${r.sha.slice(0, 7)} poussé sur ${r.branch}`
          : `Commit ${r.sha.slice(0, 7)} créé (non poussé)`,
      );
      setMessage('');
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Erreur commit/push');
    }
  };

  return (
    <DialogShell title="Commit & Push" onClose={onClose}>
      <form onSubmit={submit} className="flex flex-col gap-3 p-4">
        <div className="font-mono text-xs text-eldir-gray">
          branche : <span className="text-eldir-ink">{branch ?? '?'}</span>
        </div>
        <label className="block">
          <span className="eldir-caps mb-1 block">Message de commit</span>
          <textarea
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            rows={4}
            required
            maxLength={1000}
            placeholder="feat(sessions): add per-session ring buffer"
            className="eldir-field bg-eldir-cream"
          />
        </label>
        <label className="flex items-center gap-2 font-mono text-xs text-eldir-ink">
          <input
            type="checkbox"
            checked={push}
            onChange={(e) => setPush(e.target.checked)}
          />
          Pousser après le commit
        </label>

        {error && <ErrorBox text={error} />}
        {result && <SuccessBox text={result} />}

        <FormFooter
          onClose={onClose}
          submitting={commit.isPending}
          label={push ? 'commit & push' : 'commit'}
        />
      </form>
    </DialogShell>
  );
}

export function OpenPrDialog({
  sessionId,
  branch,
  onClose,
}: {
  sessionId: string;
  branch: string | undefined;
  onClose: () => void;
}): JSX.Element {
  const openPr = useOpenPR(sessionId);
  const [title, setTitle] = useState('');
  const [body, setBody] = useState('');
  const [base, setBase] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [created, setCreated] = useState<{ url: string; n: number } | null>(null);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    if (title.trim().length < 1) {
      setError('Titre requis.');
      return;
    }
    try {
      const r = await openPr.mutateAsync({
        title: title.trim(),
        body: body.trim() || null,
        base: base.trim() || null,
      });
      setCreated({ url: r.pr_url, n: r.pr_number });
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Erreur création PR");
    }
  };

  if (created) {
    return (
      <DialogShell title="Pull request créée" onClose={onClose}>
        <div className="flex flex-col gap-3 p-4">
          <div className="font-mono text-xs text-eldir-gray">
            #{created.n} ouverte avec succès
          </div>
          <a
            href={created.url}
            target="_blank"
            rel="noreferrer"
            className="eldir-btn eldir-btn--primary"
          >
            ouvrir la PR
          </a>
          <button
            type="button"
            onClick={onClose}
            className="eldir-btn eldir-btn--secondary eldir-btn--sm"
          >
            fermer
          </button>
        </div>
      </DialogShell>
    );
  }

  return (
    <DialogShell title="Ouvrir une pull request" onClose={onClose}>
      <form onSubmit={submit} className="flex flex-col gap-3 p-4">
        <div className="font-mono text-xs text-eldir-gray">
          de <span className="text-eldir-ink">{branch ?? '?'}</span> vers{' '}
          <span className="text-eldir-ink">{base || 'main (défaut)'}</span>
        </div>
        <label className="block">
          <span className="eldir-caps mb-1 block">Titre</span>
          <input
            type="text"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            required
            maxLength={255}
            className="eldir-field bg-eldir-cream"
          />
        </label>
        <label className="block">
          <span className="eldir-caps mb-1 block">Corps (optionnel, markdown)</span>
          <textarea
            value={body}
            onChange={(e) => setBody(e.target.value)}
            rows={5}
            maxLength={8000}
            className="eldir-field bg-eldir-cream"
          />
        </label>
        <label className="block">
          <span className="eldir-caps mb-1 block">Branche de base (optionnelle)</span>
          <input
            type="text"
            value={base}
            onChange={(e) => setBase(e.target.value)}
            placeholder="main"
            maxLength={120}
            className="eldir-field bg-eldir-cream"
          />
        </label>

        {error && <ErrorBox text={error} />}

        <FormFooter
          onClose={onClose}
          submitting={openPr.isPending}
          label="ouvrir la pr"
        />
      </form>
    </DialogShell>
  );
}

// ── primitives partagées ─────────────────────────────────────────
function DialogShell({
  title,
  onClose,
  children,
}: {
  title: string;
  onClose: () => void;
  children: React.ReactNode;
}): JSX.Element {
  return (
    <div className="eldir-overlay">
      <div className="w-full max-w-lg rounded-eldir border border-eldir-gray-3 bg-eldir-paper">
        <header className="flex items-center justify-between border-b border-eldir-gray-3 px-4 py-3">
          <div className="eldir-caps">{title}</div>
          <button
            type="button"
            onClick={onClose}
            className="font-mono text-xs uppercase tracking-caps text-eldir-gray hover:text-eldir-ink"
          >
            fermer
          </button>
        </header>
        {children}
      </div>
    </div>
  );
}

function ErrorBox({ text }: { text: string }): JSX.Element {
  return (
    <div className="rounded-eldir border border-eldir-red bg-eldir-red/10 px-3 py-2 font-mono text-xs text-eldir-red-text">
      {text}
    </div>
  );
}

function SuccessBox({ text }: { text: string }): JSX.Element {
  return (
    <div className="rounded-eldir border border-eldir-green bg-eldir-green/10 px-3 py-2 font-mono text-xs text-eldir-green-text">
      {text}
    </div>
  );
}

function FormFooter({
  onClose,
  submitting,
  label,
}: {
  onClose: () => void;
  submitting: boolean;
  label: string;
}): JSX.Element {
  return (
    <div className="flex justify-end gap-2">
      <button
        type="button"
        onClick={onClose}
        className="eldir-btn eldir-btn--secondary"
      >
        annuler
      </button>
      <button
        type="submit"
        disabled={submitting}
        className="eldir-btn eldir-btn--primary"
      >
        {submitting ? '…' : label}
      </button>
    </div>
  );
}
