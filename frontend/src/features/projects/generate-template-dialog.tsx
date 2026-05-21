/**
 * GenerateTemplateDialog - lance une session système qui analyse le repo
 * et génère un Mission Template via Claude. L'utilisateur peut ensuite
 * reviewer / éditer le preset avant de l'appliquer.
 *
 * 3 étapes :
 *  1. `choose-model` : sélection du modèle (Haiku par défaut)
 *  2. `generating`   : spinner + lien vers la session live
 *  3. `review`       : preview du preset + boutons Apply / Annuler
 */

import { useState } from 'react';
import { Link } from 'react-router-dom';

import { PresetPreview } from '@/features/projects/apply-preset-dialog';
import { ApiError } from '@/lib/api/client';
import {
  useApplyInlinePreset,
  useGenerateTemplate,
} from '@/lib/api/queries';
import type { TemplatePresetDetail } from '@/lib/api/queries';
import { cn } from '@/lib/utils';

interface GenerateTemplateDialogProps {
  projectId: string;
  projectName: string;
  onClose: () => void;
  onApplied?: () => void;
}

type Step = 'choose-model' | 'generating' | 'review' | 'error';

const MODEL_OPTIONS: ReadonlyArray<{
  value: string;
  label: string;
  hint: string;
}> = [
  {
    value: 'claude-haiku-4-5-20251001',
    label: 'Haiku 4.5',
    hint: 'Recommandé · rapide & économique · suffisant pour l\'analyse',
  },
  {
    value: 'claude-sonnet-4-6',
    label: 'Sonnet 4.6',
    hint: 'Plus précis sur les repos très atypiques',
  },
  {
    value: 'claude-opus-4-7',
    label: 'Opus 4.7',
    hint: 'Le plus puissant · pour gros monorepos complexes',
  },
];

export function GenerateTemplateDialog({
  projectId,
  projectName,
  onClose,
  onApplied,
}: GenerateTemplateDialogProps): JSX.Element {
  const [step, setStep] = useState<Step>('choose-model');
  const [model, setModel] = useState<string>('claude-haiku-4-5-20251001');
  const [preset, setPreset] = useState<TemplatePresetDetail | null>(null);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [overwrite, setOverwrite] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const generate = useGenerateTemplate(projectId);
  const apply = useApplyInlinePreset(projectId);

  const launch = async () => {
    setError(null);
    setStep('generating');
    try {
      const result = await generate.mutateAsync({ model });
      setPreset(result.preset);
      setSessionId(result.session_id);
      setStep('review');
    } catch (err) {
      setError(
        err instanceof ApiError
          ? err.message
          : 'Erreur pendant la génération.',
      );
      setStep('error');
    }
  };

  const handleApply = async () => {
    if (!preset) return;
    setError(null);
    try {
      await apply.mutateAsync({ preset, overwrite });
      onApplied?.();
      onClose();
    } catch (err) {
      setError(
        err instanceof ApiError ? err.message : 'Erreur lors de l\'application.',
      );
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-eldir-ink/60 p-4">
      <div className="flex max-h-[90vh] w-full max-w-4xl flex-col rounded-eldir border border-eldir-gray-3 bg-eldir-paper">
        <header className="flex items-center justify-between border-b border-eldir-gray-3 px-4 py-3">
          <div>
            <div className="eldir-caps">Générer un template avec Claude</div>
            <div className="mt-1 font-mono text-2xs text-eldir-gray">
              Projet : <span className="text-eldir-ink">{projectName}</span>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            disabled={step === 'generating'}
            className="font-mono text-xs uppercase tracking-caps text-eldir-gray hover:text-eldir-ink disabled:opacity-40"
          >
            {step === 'generating' ? '...' : 'fermer'}
          </button>
        </header>

        {step === 'choose-model' && (
          <ChooseModelStep
            model={model}
            onSelectModel={setModel}
            onLaunch={launch}
            onCancel={onClose}
          />
        )}

        {step === 'generating' && (
          <GeneratingStep sessionId={sessionId} />
        )}

        {step === 'review' && preset && (
          <ReviewStep
            preset={preset}
            sessionId={sessionId}
            overwrite={overwrite}
            onOverwriteChange={setOverwrite}
            applying={apply.isPending}
            error={error}
            onCancel={onClose}
            onApply={handleApply}
          />
        )}

        {step === 'error' && (
          <ErrorStep
            error={error ?? 'Erreur inconnue.'}
            onRetry={() => setStep('choose-model')}
            onClose={onClose}
          />
        )}
      </div>
    </div>
  );
}

function ChooseModelStep({
  model,
  onSelectModel,
  onLaunch,
  onCancel,
}: {
  model: string;
  onSelectModel: (m: string) => void;
  onLaunch: () => void;
  onCancel: () => void;
}): JSX.Element {
  return (
    <>
      <div className="flex flex-col gap-4 overflow-y-auto px-4 py-5">
        <p className="text-sm text-eldir-ink-2">
          Eldir va lancer une session Claude en lecture seule sur ton repo pour
          en extraire un Mission Template (système prompt, skills, sub-agents).
          Tu pourras tout reviewer et éditer avant d'appliquer.
        </p>
        <div className="rounded-eldir border border-eldir-orange/30 bg-eldir-orange/5 p-3 text-xs text-eldir-ink-2">
          <strong className="font-semibold text-eldir-orange">
            💡 Haiku suffit largement.
          </strong>{' '}
          Eldir embarque ses propres instructions pour le générateur (cf.
          Settings &gt; Prompts &gt; Génération de Mission Template), donc même
          le modèle le plus économique fait le travail. Choisis Sonnet ou Opus
          uniquement si ton repo a une structure très atypique.
        </div>

        <div className="eldir-caps">Modèle</div>
        <div className="flex flex-col gap-2">
          {MODEL_OPTIONS.map((opt) => (
            <label
              key={opt.value}
              className={cn(
                'flex cursor-pointer items-start gap-3 rounded-eldir border p-3 transition-colors',
                model === opt.value
                  ? 'border-eldir-orange bg-eldir-orange/5'
                  : 'border-eldir-gray-3 hover:bg-eldir-cream-2',
              )}
            >
              <input
                type="radio"
                name="model"
                value={opt.value}
                checked={model === opt.value}
                onChange={() => onSelectModel(opt.value)}
                className="mt-0.5 h-4 w-4 accent-eldir-orange"
              />
              <div>
                <div className="font-mono text-sm font-semibold text-eldir-ink">
                  {opt.label}
                </div>
                <div className="mt-0.5 text-xs text-eldir-ink-2">
                  {opt.hint}
                </div>
              </div>
            </label>
          ))}
        </div>

        <div className="rounded-eldir border border-eldir-gray-3 bg-eldir-cream p-3 text-2xs text-eldir-ink-2">
          ℹ️ Le coût de cette opération apparaîtra dans le dashboard Costs comme
          n'importe quelle autre session. Aucun coût caché.
        </div>
      </div>

      <footer className="flex justify-end gap-2 border-t border-eldir-gray-3 px-4 py-3">
        <button
          type="button"
          onClick={onCancel}
          className="rounded-eldir border border-eldir-gray-3 px-3 py-2 font-mono text-xs uppercase tracking-caps text-eldir-gray hover:text-eldir-ink"
        >
          annuler
        </button>
        <button
          type="button"
          onClick={onLaunch}
          className="rounded-eldir bg-eldir-orange px-4 py-2 font-mono text-xs font-semibold uppercase tracking-caps text-white hover:bg-eldir-orange/90"
        >
          analyser le repo
        </button>
      </footer>
    </>
  );
}

function GeneratingStep({
  sessionId,
}: {
  sessionId: string | null;
}): JSX.Element {
  return (
    <div className="flex flex-col items-center gap-5 px-4 py-12">
      <div className="h-12 w-12 animate-spin rounded-full border-2 border-eldir-gray-3 border-t-eldir-orange" />
      <div className="text-center">
        <div className="font-mono text-sm font-semibold text-eldir-ink">
          Claude analyse ton repo…
        </div>
        <p className="mt-1 text-xs text-eldir-ink-2">
          Lecture des fichiers de configuration, détection de la stack et
          construction du template. Compte 30s à 2min selon la taille du repo.
        </p>
      </div>
      {sessionId && (
        <Link
          to={`/sessions/${sessionId}`}
          target="_blank"
          rel="noopener noreferrer"
          className="font-mono text-2xs uppercase tracking-caps text-eldir-orange hover:underline"
        >
          voir la session live →
        </Link>
      )}
    </div>
  );
}

function ReviewStep({
  preset,
  sessionId,
  overwrite,
  onOverwriteChange,
  applying,
  error,
  onCancel,
  onApply,
}: {
  preset: TemplatePresetDetail;
  sessionId: string | null;
  overwrite: boolean;
  onOverwriteChange: (v: boolean) => void;
  applying: boolean;
  error: string | null;
  onCancel: () => void;
  onApply: () => void;
}): JSX.Element {
  return (
    <>
      <div className="overflow-y-auto bg-eldir-cream">
        <div className="border-b border-eldir-gray-3 bg-eldir-orange/5 px-5 py-3">
          <div className="flex items-center justify-between gap-3">
            <div className="font-mono text-xs text-eldir-ink">
              ✨ Preset généré. Relis-le, ajuste si nécessaire, puis applique.
            </div>
            {sessionId && (
              <Link
                to={`/sessions/${sessionId}`}
                target="_blank"
                rel="noopener noreferrer"
                className="font-mono text-2xs uppercase tracking-caps text-eldir-orange hover:underline"
              >
                voir la session →
              </Link>
            )}
          </div>
        </div>
        <PresetPreview preset={preset} />
      </div>

      <footer className="flex flex-col gap-3 border-t border-eldir-gray-3 px-4 py-3 md:flex-row md:items-center md:justify-between">
        <label className="flex items-center gap-2 font-mono text-xs text-eldir-ink-2">
          <input
            type="checkbox"
            checked={overwrite}
            onChange={(e) => onOverwriteChange(e.target.checked)}
            className="h-4 w-4 accent-eldir-orange"
          />
          <span>Écraser le template existant (sinon : merge)</span>
        </label>
        {error && (
          <span className="font-mono text-xs text-eldir-red">{error}</span>
        )}
        <div className="flex gap-2">
          <button
            type="button"
            onClick={onCancel}
            className="rounded-eldir border border-eldir-gray-3 px-3 py-2 font-mono text-xs uppercase tracking-caps text-eldir-gray hover:text-eldir-ink"
          >
            annuler
          </button>
          <button
            type="button"
            onClick={onApply}
            disabled={applying}
            className="rounded-eldir bg-eldir-orange px-4 py-2 font-mono text-xs font-semibold uppercase tracking-caps text-white hover:bg-eldir-orange/90 disabled:opacity-50"
          >
            {applying ? 'application…' : 'appliquer ce template'}
          </button>
        </div>
      </footer>
    </>
  );
}

function ErrorStep({
  error,
  onRetry,
  onClose,
}: {
  error: string;
  onRetry: () => void;
  onClose: () => void;
}): JSX.Element {
  return (
    <>
      <div className="flex flex-col gap-4 px-4 py-6">
        <div className="rounded-eldir border border-eldir-red/40 bg-eldir-red/5 p-3 text-sm text-eldir-red">
          {error}
        </div>
        <p className="text-xs text-eldir-ink-2">
          Tu peux réessayer (le coût du tour précédent reste comptabilisé dans
          Costs, c'est attendu) ou abandonner et configurer le template à la
          main depuis l'éditeur.
        </p>
      </div>
      <footer className="flex justify-end gap-2 border-t border-eldir-gray-3 px-4 py-3">
        <button
          type="button"
          onClick={onClose}
          className="rounded-eldir border border-eldir-gray-3 px-3 py-2 font-mono text-xs uppercase tracking-caps text-eldir-gray hover:text-eldir-ink"
        >
          fermer
        </button>
        <button
          type="button"
          onClick={onRetry}
          className="rounded-eldir bg-eldir-orange px-4 py-2 font-mono text-xs font-semibold uppercase tracking-caps text-white hover:bg-eldir-orange/90"
        >
          réessayer
        </button>
      </footer>
    </>
  );
}
