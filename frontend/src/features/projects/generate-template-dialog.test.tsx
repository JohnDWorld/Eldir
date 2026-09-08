import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const mutateAsync = vi.fn();
const statusData = vi.fn();

vi.mock('@/lib/api/queries', () => ({
  useStartTemplateGeneration: () => ({ mutateAsync, isPending: false }),
  useApplyInlinePreset: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useTemplateGenerationStatus: (_projectId: string, sessionId: string | null) => ({
    data: sessionId === null ? undefined : statusData(sessionId),
  }),
}));

vi.mock('@/features/projects/apply-preset-dialog', () => ({
  PresetPreview: () => <div>aperçu du preset</div>,
}));

import { GenerateTemplateDialog } from '@/features/projects/generate-template-dialog';

const PRESET = {
  slug: 'demo',
  title: 'Demo',
  description: '',
  tags: [],
  system_prompt: '',
  model: null,
  allowed_tools: null,
  skills: [],
  sub_agents: [],
};

function renderDialog(): void {
  render(
    <MemoryRouter>
      <GenerateTemplateDialog projectId="p1" projectName="demo" onClose={vi.fn()} />
    </MemoryRouter>,
  );
}

describe('GenerateTemplateDialog', () => {
  beforeEach(() => {
    localStorage.clear();
    vi.clearAllMocks();
  });

  it('reprend une génération mémorisée au lieu d’en relancer une', async () => {
    localStorage.setItem(
      'eldir.template-generation.p1',
      JSON.stringify({ sessionId: 's1', at: Date.now() }),
    );
    statusData.mockReturnValue({ status: 'done', preset: PRESET, detail: null });

    renderDialog();

    expect(await screen.findByText('aperçu du preset')).toBeInTheDocument();
    expect(mutateAsync).not.toHaveBeenCalled();
  });

  it('ignore une génération mémorisée trop vieille', () => {
    localStorage.setItem(
      'eldir.template-generation.p1',
      JSON.stringify({ sessionId: 's1', at: Date.now() - 25 * 60 * 60 * 1000 }),
    );

    renderDialog();

    expect(screen.getByText(/générer/i)).toBeInTheDocument();
    expect(localStorage.getItem('eldir.template-generation.p1')).toBeNull();
  });
});
