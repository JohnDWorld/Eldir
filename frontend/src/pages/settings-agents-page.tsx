/**
 * SettingsAgentsPage - les jetons qui laissent un agent extérieur piloter Eldir.
 *
 * Page mince : tout le geste (créer, voir une fois, couper) vit dans
 * `AgentTokensPanel`.
 */

import { BackLink } from '@/components/eldir/back-link';
import { AgentMemoryStatus } from '@/features/settings/agent-memory';
import { AgentTokensPanel } from '@/features/settings/agent-tokens';

export function SettingsAgentsPage(): JSX.Element {
  return (
    <main className="mx-auto flex max-w-3xl flex-col gap-6 p-4 md:p-8">
      <header>
        <BackLink to="/settings" label="réglages" />
        <h1 className="eldir-title mt-1">Agents extérieurs</h1>
        <p className="eldir-lede">
          Un agent extérieur se branche sur Eldir en MCP, à l'adresse{' '}
          <span className="font-mono">/api/mcp/</span> de ton instance, avec un jeton émis ici. Il
          dispose des cinq outils du superviseur : lister tes projets et tes sessions, leur confier
          une consigne, autoriser une session à publier, et enregistrer une préférence.{' '}
          <strong className="font-semibold">
            Autoriser à publier en fait partie : un jeton peut donc pousser sur tes dépôts.
          </strong>{' '}
          Ne donne un jeton qu'à un agent dont tu maîtrises le cerveau, et coupe-le dès qu'il ne
          sert plus.
        </p>
      </header>

      <AgentTokensPanel />
      <AgentMemoryStatus />
    </main>
  );
}
