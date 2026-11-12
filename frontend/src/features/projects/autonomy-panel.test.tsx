import { fireEvent, render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const mutateAsync = vi.fn();
const projets = vi.fn();

vi.mock('@/lib/api/queries', () => ({
  useProjects: () => ({ data: projets() }),
  useUpdateProjectAutonomy: () => ({ mutateAsync, isPending: false }),
}));

import { AutonomyPanel } from '@/features/projects/autonomy-panel';

const PROJET = {
  id: 'p1',
  name: 'demo',
  autonomous: false,
  deploy_command: null,
};

describe('AutonomyPanel', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    projets.mockReturnValue([PROJET]);
  });

  it('coche la case : le projet devient autonome', () => {
    render(<AutonomyPanel projectId="p1" />);

    fireEvent.click(screen.getByRole('checkbox', { name: /autonome/i }));

    expect(mutateAsync).toHaveBeenCalledWith({ autonomous: true });
  });

  it('enregistre la commande de déploiement sans espaces autour', () => {
    render(<AutonomyPanel projectId="p1" />);

    fireEvent.change(screen.getByLabelText(/commande de déploiement/i), {
      target: { value: '  ./deploy.sh  ' },
    });
    fireEvent.click(screen.getByRole('button', { name: /enregistrer/i }));

    expect(mutateAsync).toHaveBeenCalledWith({ deploy_command: './deploy.sh' });
  });

  it('montre l’état enregistré du projet', () => {
    projets.mockReturnValue([{ ...PROJET, autonomous: true, deploy_command: './d.sh' }]);

    render(<AutonomyPanel projectId="p1" />);

    expect(screen.getByRole('checkbox', { name: /autonome/i })).toBeChecked();
    expect(screen.getByLabelText(/commande de déploiement/i)).toHaveValue('./d.sh');
  });
});
