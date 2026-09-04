import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { useState } from 'react';
import { BrowserRouter, Route, Routes } from 'react-router-dom';

import { AuthedLayout } from '@/features/auth/authed-layout';
import { CostsPage } from '@/pages/costs-page';
import { LoginPage } from '@/pages/login-page';
import { NotFoundPage } from '@/pages/not-found-page';
import { OpsHomePage } from '@/pages/ops-home-page';
import { ProjectsPage } from '@/pages/projects-page';
import { ProjectTemplatePage } from '@/pages/project-template-page';
import { SessionPage } from '@/pages/session-page';
import { SettingsClaudePage } from '@/pages/settings-claude-page';
import { SettingsGitPage } from '@/pages/settings-git-page';
import { SettingsOllamaPage } from '@/pages/settings-ollama-page';
import { SettingsPage } from '@/pages/settings-page';
import { SettingsPromptsPage } from '@/pages/settings-prompts-page';
import { SupervisorPage } from '@/pages/supervisor-page';
import { SetupPendingPage } from '@/pages/setup-pending-page';
import { useRegisterSw } from '@/pwa/use-register-sw';

export function App(): JSX.Element {
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            staleTime: 30_000,
            refetchOnWindowFocus: false,
            retry: 1,
          },
        },
      }),
  );

  useRegisterSw();

  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/setup-pending" element={<SetupPendingPage />} />
          <Route element={<AuthedLayout />}>
            <Route path="/" element={<OpsHomePage />} />
            <Route path="/supervisor" element={<SupervisorPage />} />
            <Route path="/projects" element={<ProjectsPage />} />
            <Route
              path="/projects/:projectId/template"
              element={<ProjectTemplatePage />}
            />
            <Route path="/sessions/:sessionId" element={<SessionPage />} />
            <Route path="/costs" element={<CostsPage />} />
            <Route path="/settings" element={<SettingsPage />} />
            <Route path="/settings/claude" element={<SettingsClaudePage />} />
            <Route path="/settings/git" element={<SettingsGitPage />} />
            <Route path="/settings/prompts" element={<SettingsPromptsPage />} />
            <Route path="/settings/ollama" element={<SettingsOllamaPage />} />
          </Route>
          <Route path="*" element={<NotFoundPage />} />
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  );
}
