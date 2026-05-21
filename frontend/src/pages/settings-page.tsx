/**
 * SettingsPage - hub d'entrée pour les sous-sections de réglages.
 * Liste les cartes credentials + prompts + permet d'activer les notifs.
 */

import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';

import { GitMark } from '@/components/eldir/git-mark';
import {
  getNotificationPermission,
  requestNotificationPermission,
  type NotificationPermissionState,
} from '@/hooks/use-session-notifier';

interface SettingsCardProps {
  to: string;
  caps: string;
  title: string;
  description: string;
  icon: JSX.Element;
}

function SettingsCard({ to, caps, title, description, icon }: SettingsCardProps): JSX.Element {
  return (
    <Link
      to={to}
      className="group flex items-start gap-4 rounded-eldir border border-eldir-gray-3 bg-eldir-cream p-5 transition-colors hover:border-eldir-orange hover:bg-eldir-cream-2"
    >
      <div className="mt-1 rounded-eldir border border-eldir-gray-3 bg-eldir-paper p-2.5 text-eldir-ink">
        {icon}
      </div>
      <div className="min-w-0 flex-1">
        <div className="eldir-caps">{caps}</div>
        <h2 className="mt-1 font-mono text-base font-semibold text-eldir-ink">
          {title}
        </h2>
        <p className="mt-1 text-sm text-eldir-ink-2">{description}</p>
      </div>
      <span className="self-center font-mono text-xs uppercase tracking-caps text-eldir-gray group-hover:text-eldir-orange">
        →
      </span>
    </Link>
  );
}

export function SettingsPage(): JSX.Element {
  return (
    <main className="mx-auto flex max-w-3xl flex-col gap-6 p-4 md:p-8">
      <header>
        <div className="eldir-caps">Settings</div>
        <h1 className="mt-1 font-mono text-xl font-bold text-eldir-ink">
          Paramètres
        </h1>
        <p className="mt-2 text-sm text-eldir-ink-2">
          Tokens, credentials, prompts et intégrations utilisés par Eldir.
        </p>
      </header>

      <div className="flex flex-col gap-4">
        <SettingsCard
          to="/settings/claude"
          caps="Claude · API"
          title="Credentials Claude"
          description="Token OAuth Pro/Max et/ou clé API Anthropic. Eldir privilégie l'OAuth si présent."
          icon={
            <svg
              xmlns="http://www.w3.org/2000/svg"
              viewBox="0 0 24 24"
              width="20"
              height="20"
              fill="currentColor"
              aria-hidden="true"
            >
              <path d="M12 2 2 20h20L12 2Zm0 5.84L18.53 18H5.47L12 7.84Z" />
            </svg>
          }
        />
        <SettingsCard
          to="/settings/git"
          caps="Git providers"
          title="Credentials Git"
          description="Connexion GitHub (OAuth ou PAT) et Forgejo. Utilisés pour cloner, créer des repos et ouvrir des PR."
          icon={<GitMark provider="github" size={20} className="text-current" />}
        />
        <SettingsCard
          to="/settings/prompts"
          caps="Prompts · système"
          title="Prompts Eldir"
          description="Édite les prompts qu'Eldir envoie à Claude pour ses opérations internes (génération de template, etc.). Reset au défaut possible à tout moment."
          icon={
            <svg
              xmlns="http://www.w3.org/2000/svg"
              viewBox="0 0 24 24"
              width="20"
              height="20"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
              aria-hidden="true"
            >
              <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
              <polyline points="14 2 14 8 20 8" />
              <line x1="9" y1="13" x2="15" y2="13" />
              <line x1="9" y1="17" x2="15" y2="17" />
            </svg>
          }
        />
        <SettingsCard
          to="/settings/ollama"
          caps="Ollama · local"
          title="Pré-traitement données sensibles"
          description="Masquage de secrets, anonymisation et résumés faits localement via Ollama avant tout appel à Claude. Tes données sensibles ne traversent jamais Internet."
          icon={
            <svg
              xmlns="http://www.w3.org/2000/svg"
              viewBox="0 0 24 24"
              width="20"
              height="20"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
              aria-hidden="true"
            >
              <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
            </svg>
          }
        />
        <NotificationsCard />
      </div>
    </main>
  );
}

function NotificationsCard(): JSX.Element {
  const [permission, setPermission] = useState<NotificationPermissionState>(
    'default',
  );
  const [status, setStatus] = useState<string | null>(null);

  useEffect(() => {
    setPermission(getNotificationPermission());
  }, []);

  const handleEnable = async () => {
    setStatus(null);
    const result = await requestNotificationPermission();
    setPermission(result);
    if (result === 'granted') {
      setStatus('Notifications activées. Eldir te préviendra quand un tour Claude se termine en arrière-plan.');
    } else if (result === 'denied') {
      setStatus('Tu as refusé les notifications. Tu peux les réactiver via les paramètres de ton navigateur.');
    } else if (result === 'unsupported') {
      setStatus('Ton navigateur ne supporte pas l\'API Notification.');
    }
  };

  return (
    <div className="flex items-start gap-4 rounded-eldir border border-eldir-gray-3 bg-eldir-cream p-5">
      <div className="mt-1 rounded-eldir border border-eldir-gray-3 bg-eldir-paper p-2.5 text-eldir-ink">
        <svg
          xmlns="http://www.w3.org/2000/svg"
          viewBox="0 0 24 24"
          width="20"
          height="20"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
          aria-hidden="true"
        >
          <path d="M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9" />
          <path d="M10.3 21a1.94 1.94 0 0 0 3.4 0" />
        </svg>
      </div>
      <div className="min-w-0 flex-1">
        <div className="eldir-caps">Notifications · push</div>
        <h2 className="mt-1 font-mono text-base font-semibold text-eldir-ink">
          Notifs de fin de tour
        </h2>
        <p className="mt-1 text-sm text-eldir-ink-2">
          Active les notifs natives pour être prévenu quand un tour Claude
          termine pendant que tu es ailleurs (autre onglet, écran verrouillé,
          PWA en arrière-plan).
        </p>
        {status && (
          <p className="mt-2 font-mono text-2xs text-eldir-ink-2">{status}</p>
        )}
      </div>
      <div className="self-center">
        {permission === 'granted' && (
          <span className="rounded-eldir bg-eldir-orange/20 px-3 py-1.5 font-mono text-2xs uppercase tracking-caps text-eldir-orange">
            ✓ activées
          </span>
        )}
        {permission === 'denied' && (
          <span className="rounded-eldir bg-eldir-red/10 px-3 py-1.5 font-mono text-2xs uppercase tracking-caps text-eldir-red">
            refusées
          </span>
        )}
        {(permission === 'default' || permission === 'unsupported') && (
          <button
            type="button"
            onClick={handleEnable}
            disabled={permission === 'unsupported'}
            className="rounded-eldir bg-eldir-orange px-3 py-1.5 font-mono text-xs font-semibold uppercase tracking-caps text-white hover:bg-eldir-orange/90 disabled:opacity-50"
          >
            activer
          </button>
        )}
      </div>
    </div>
  );
}
