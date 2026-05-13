import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { useState } from 'react';
import { BrowserRouter, Route, Routes } from 'react-router-dom';

import { RequireAuth } from '@/features/auth/require-auth';
import { LoginPage } from '@/pages/login-page';
import { NotFoundPage } from '@/pages/not-found-page';
import { OpsHomePage } from '@/pages/ops-home-page';
import { ProjectsPage } from '@/pages/projects-page';
import { SessionPage } from '@/pages/session-page';
import { SettingsClaudePage } from '@/pages/settings-claude-page';
import { SettingsGitPage } from '@/pages/settings-git-page';
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
          <Route
            path="/"
            element={
              <RequireAuth>
                <OpsHomePage />
              </RequireAuth>
            }
          />
          <Route
            path="/projects"
            element={
              <RequireAuth>
                <ProjectsPage />
              </RequireAuth>
            }
          />
          <Route
            path="/sessions/:sessionId"
            element={
              <RequireAuth>
                <SessionPage />
              </RequireAuth>
            }
          />
          <Route
            path="/settings/claude"
            element={
              <RequireAuth>
                <SettingsClaudePage />
              </RequireAuth>
            }
          />
          <Route
            path="/settings/git"
            element={
              <RequireAuth>
                <SettingsGitPage />
              </RequireAuth>
            }
          />
          <Route path="*" element={<NotFoundPage />} />
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  );
}
