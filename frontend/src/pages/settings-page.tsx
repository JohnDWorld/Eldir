/**
 * SettingsPage - hub d'entrée pour les sous-sections de réglages.
 * Liste deux cartes : credentials Claude, credentials Git.
 */

import { Link } from 'react-router-dom';

import { GitMark } from '@/components/eldir/git-mark';

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
          Tokens, credentials et intégrations utilisés par Eldir.
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
      </div>
    </main>
  );
}
