/**
 * SettingsPage - hub d'entrée pour les sous-sections de réglages.
 *
 * Une liste, pas une grille de cartes : quatre destinations et un
 * interrupteur, on les parcourt de haut en bas. Chaque ligne dit ce qu'elle
 * règle, sans surtitre au-dessus du titre.
 */

import {
  Bell,
  Check,
  ChevronRight,
  FileText,
  KeyRound,
  ShieldCheck,
} from 'lucide-react';
import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';

import { GitMark } from '@/components/eldir/git-mark';
import {
  getNotificationPermission,
  requestNotificationPermission,
  type NotificationPermissionState,
} from '@/hooks/use-session-notifier';

interface SettingsRowProps {
  to: string;
  title: string;
  description: string;
  icon: JSX.Element;
}

function RowIcon({ children }: { children: JSX.Element }): JSX.Element {
  return (
    <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-eldir border border-eldir-gray-3 bg-eldir-paper text-eldir-ink">
      {children}
    </span>
  );
}

function SettingsRow({ to, title, description, icon }: SettingsRowProps): JSX.Element {
  return (
    <li>
      <Link
        to={to}
        className="group flex items-center gap-4 px-4 py-4 transition-colors hover:bg-eldir-cream-2"
      >
        <RowIcon>{icon}</RowIcon>
        <span className="min-w-0 flex-1">
          <span className="block font-sans text-sm font-semibold text-eldir-ink">
            {title}
          </span>
          <span className="mt-0.5 block font-sans text-sm text-eldir-ink-2">
            {description}
          </span>
        </span>
        <ChevronRight
          size={16}
          aria-hidden="true"
          className="shrink-0 text-eldir-gray transition-colors group-hover:text-eldir-orange"
        />
      </Link>
    </li>
  );
}

export function SettingsPage(): JSX.Element {
  return (
    <main className="mx-auto flex max-w-3xl flex-col gap-6 p-4 md:p-8">
      <header>
        <h1 className="eldir-title">Paramètres</h1>
        <p className="eldir-lede">
          Tokens, credentials, prompts et intégrations utilisés par Eldir.
        </p>
      </header>

      <ul className="divide-y divide-eldir-gray-3 overflow-hidden rounded-eldir border border-eldir-gray-3 bg-eldir-cream">
        <SettingsRow
          to="/settings/claude"
          title="Credentials Claude"
          description="Token OAuth Pro/Max ou clé API Anthropic. L'OAuth est utilisé en priorité s'il est présent."
          icon={<KeyRound size={17} aria-hidden="true" />}
        />
        <SettingsRow
          to="/settings/git"
          title="Credentials Git"
          description="GitHub (OAuth ou PAT) et Forgejo, pour cloner, créer des repos et ouvrir des PR."
          icon={<GitMark provider="github" size={17} className="text-current" />}
        />
        <SettingsRow
          to="/settings/prompts"
          title="Prompts Eldir"
          description="Les prompts qu'Eldir envoie à Claude pour ses tâches internes, comme la génération de template. Réinitialisables."
          icon={<FileText size={17} aria-hidden="true" />}
        />
        <SettingsRow
          to="/settings/ollama"
          title="Données sensibles"
          description="Masquage de secrets et anonymisation faits localement par Ollama, avant tout appel à Claude."
          icon={<ShieldCheck size={17} aria-hidden="true" />}
        />
        <NotificationsRow />
      </ul>
    </main>
  );
}

function NotificationsRow(): JSX.Element {
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
      setStatus('Notifications refusées. Pour les réactiver, passe par les réglages du site dans ton navigateur.');
    } else if (result === 'unsupported') {
      setStatus('Ce navigateur ne gère pas les notifications.');
    }
  };

  return (
    <li className="flex flex-wrap items-center gap-4 px-4 py-4">
      <RowIcon>
        <Bell size={17} aria-hidden="true" />
      </RowIcon>
      <div className="min-w-0 flex-1 basis-48">
        <div className="font-sans text-sm font-semibold text-eldir-ink">
          Notifications de fin de tour
        </div>
        <p className="mt-0.5 font-sans text-sm text-eldir-ink-2">
          Être prévenu quand un tour Claude se termine pendant que tu es
          ailleurs : autre onglet, écran verrouillé, PWA en arrière-plan.
        </p>
        {status && (
          <p role="status" className="mt-2 font-sans text-xs text-eldir-ink-2">
            {status}
          </p>
        )}
      </div>
      <div className="shrink-0">
        {permission === 'granted' && (
          <span className="inline-flex items-center gap-1 font-mono text-2xs uppercase tracking-caps text-eldir-green">
            <Check size={12} strokeWidth={2.5} aria-hidden="true" />
            activées
          </span>
        )}
        {permission === 'denied' && (
          <span className="font-mono text-2xs uppercase tracking-caps text-eldir-red">
            refusées
          </span>
        )}
        {permission === 'unsupported' && (
          <span className="font-mono text-2xs uppercase tracking-caps text-eldir-gray">
            non gérées
          </span>
        )}
        {permission === 'default' && (
          <button
            type="button"
            onClick={handleEnable}
            className="eldir-btn eldir-btn--secondary eldir-btn--sm"
          >
            activer
          </button>
        )}
      </div>
    </li>
  );
}
