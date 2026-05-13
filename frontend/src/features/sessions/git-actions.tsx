/**
 * SessionGitActions — boutons Commit & Push / Open PR + dialogs.
 */

import { useState } from 'react';

import { ApiError } from '@/lib/api/client';
import {
  useCommitPush,
  useOpenPR,
  useSessionGitStatus,
} from '@/lib/api/queries';
import { cn } from '@/lib/utils';

export function SessionGitActions({
  sessionId,
}: {
  sessionId: string;
}): JSX.Element {
  const status = useSessionGitStatus(sessionId);
  const [openWhich, setOpenWhich] = useState<'commit' | 'pr' | null>(null);

  const dirty = Boolean(status.data?.has_changes);
  const totalChanges =
    (status.data?.modified ?? 0) +
    (status.data?.added ?? 0) +
    (status.data?.deleted ?? 0) +
    (status.data?.untracked ?? 0);

  return (
    <>
      <div className="hidden items-center gap-2 md:flex">
        {status.data && (
          <span
            className={cn(
              'font-mono text-2xs uppercase tracking-caps',
              dirty ? 'text-eldir-amber' : 'text-eldir-gray',
            )}
          >
            {dirty ? `${totalChanges} changes` : 'clean'}
          </span>
        )}
        <button
          type="button"
          onClick={() => setOpenWhich('commit')}
          disabled={!dirty}
          className="rounded-eldir border border-eldir-gray-3 bg-eldir-paper px-3 py-1.5 font-mono text-xs uppercase tracking-caps text-eldir-ink hover:bg-eldir-cream disabled:opacity-40"
        >
          commit & push
        </button>
        <button
          type="button"
          onClick={() => setOpenWhich('pr')}
          className="rounded-eldir border border-eldir-gray-3 bg-eldir-paper px-3 py-1.5 font-mono text-xs uppercase tracking-caps text-eldir-ink hover:bg-eldir-cream"
        >
          open pr
        </button>
      </div>

      {openWhich === 'commit' && (
        <CommitDialog
          sessionId={sessionId}
          branch={status.data?.branch}
          onClose={() => setOpenWhich(null)}
        />
      )}
      {openWhich === 'pr' && (
        <OpenPrDialog
          sessionId={sessionId}
          branch={status.data?.branch}
          onClose={() => setOpenWhich(null)}
        />
      )}
    </>
  );
}

function CommitDialog({
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
            className="w-full rounded-eldir border border-eldir-gray-3 bg-eldir-cream px-3 py-2 font-mono text-sm text-eldir-ink focus:border-eldir-orange focus:outline-none"
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

function OpenPrDialog({
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
            className="break-all rounded-eldir bg-eldir-orange px-3 py-2 text-center font-mono text-xs font-semibold uppercase tracking-caps text-white hover:bg-eldir-orange/90"
          >
            ouvrir sur le provider →
          </a>
          <button
            type="button"
            onClick={onClose}
            className="rounded-eldir border border-eldir-gray-3 px-3 py-2 font-mono text-xs uppercase tracking-caps text-eldir-ink hover:bg-eldir-cream"
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
            className="w-full rounded-eldir border border-eldir-gray-3 bg-eldir-cream px-3 py-2 font-mono text-sm text-eldir-ink focus:border-eldir-orange focus:outline-none"
          />
        </label>
        <label className="block">
          <span className="eldir-caps mb-1 block">Corps (optionnel, markdown)</span>
          <textarea
            value={body}
            onChange={(e) => setBody(e.target.value)}
            rows={5}
            maxLength={8000}
            className="w-full rounded-eldir border border-eldir-gray-3 bg-eldir-cream px-3 py-2 font-mono text-sm text-eldir-ink focus:border-eldir-orange focus:outline-none"
          />
        </label>
        <label className="block">
          <span className="eldir-caps mb-1 block">Base branch (optionnelle)</span>
          <input
            type="text"
            value={base}
            onChange={(e) => setBase(e.target.value)}
            placeholder="main"
            maxLength={120}
            className="w-full rounded-eldir border border-eldir-gray-3 bg-eldir-cream px-3 py-2 font-mono text-sm text-eldir-ink focus:border-eldir-orange focus:outline-none"
          />
        </label>

        {error && <ErrorBox text={error} />}

        <FormFooter
          onClose={onClose}
          submitting={openPr.isPending}
          label="open pr"
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
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-eldir-ink/60 p-4">
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
    <div className="rounded-eldir border border-eldir-red bg-eldir-red/10 px-3 py-2 font-mono text-xs text-eldir-red">
      {text}
    </div>
  );
}

function SuccessBox({ text }: { text: string }): JSX.Element {
  return (
    <div className="rounded-eldir border border-eldir-green bg-eldir-green/10 px-3 py-2 font-mono text-xs text-eldir-green">
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
        className="rounded-eldir border border-eldir-gray-3 px-4 py-2 font-mono text-xs uppercase tracking-caps text-eldir-ink hover:bg-eldir-cream"
      >
        annuler
      </button>
      <button
        type="submit"
        disabled={submitting}
        className="rounded-eldir bg-eldir-orange px-4 py-2 font-mono text-xs font-semibold uppercase tracking-caps text-white hover:bg-eldir-orange/90 disabled:opacity-50"
      >
        {submitting ? '…' : label}
      </button>
    </div>
  );
}
