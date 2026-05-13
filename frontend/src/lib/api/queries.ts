/**
 * TanStack Query — keys et hooks réutilisables.
 * Une seule source de vérité pour les `queryKey` (DRY).
 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { apiClient } from '@/lib/api/client';
import type {
  ClaudeCredentialCreate,
  ClaudeCredentialRead,
  CommitPushRequest,
  CommitPushResponse,
  GitCredentialCreate,
  GitCredentialRead,
  GitStatusResponse,
  HealthResponse,
  LoginResponse,
  OpenPullRequestRequest,
  OpenPullRequestResponse,
  ProjectCreateFromRepo,
  ProjectRead,
  RemoteRepo,
  SessionCreate,
  SessionEventRead,
  SessionMessageInput,
  SessionRead,
  SetupStatus,
  UserRead,
} from '@/lib/types/api';
import type { Provider } from '@/lib/constants';

export const queryKeys = {
  health: ['health'] as const,
  setupStatus: ['setup', 'status'] as const,
  me: ['auth', 'me'] as const,
  claudeCredentials: ['settings', 'claude-credentials'] as const,
  gitCredentials: ['settings', 'git-credentials'] as const,
  remoteRepos: (provider: Provider) => ['providers', provider, 'repos'] as const,
  projects: ['projects'] as const,
  project: (id: string) => ['projects', id] as const,
  sessions: ['sessions'] as const,
  session: (id: string) => ['sessions', id] as const,
  sessionEvents: (id: string) => ['sessions', id, 'events'] as const,
  sessionGitStatus: (id: string) => ['sessions', id, 'git-status'] as const,
};

export function useHealth() {
  return useQuery({
    queryKey: queryKeys.health,
    queryFn: ({ signal }) => apiClient.get<HealthResponse>('/health', { signal }),
    staleTime: 30_000,
  });
}

export function useSetupStatus() {
  return useQuery({
    queryKey: queryKeys.setupStatus,
    queryFn: ({ signal }) => apiClient.get<SetupStatus>('/setup/status', { signal }),
    staleTime: 10_000,
  });
}

export function useMe(enabled = true) {
  return useQuery({
    queryKey: queryKeys.me,
    queryFn: ({ signal }) => apiClient.get<UserRead>('/auth/me', { signal }),
    enabled,
    retry: false,
  });
}

export function useLogin() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: { email: string; password: string }) =>
      apiClient.post<LoginResponse, typeof body>('/auth/login', body),
    onSuccess: (data) => {
      qc.setQueryData(queryKeys.me, data.user);
    },
  });
}

export function useClaudeCredentials() {
  return useQuery({
    queryKey: queryKeys.claudeCredentials,
    queryFn: ({ signal }) =>
      apiClient.get<ClaudeCredentialRead[]>('/settings/claude-credentials', { signal }),
  });
}

export function useCreateClaudeCredential() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: ClaudeCredentialCreate) =>
      apiClient.post<ClaudeCredentialRead, ClaudeCredentialCreate>(
        '/settings/claude-credentials',
        body,
      ),
    onSuccess: () => qc.invalidateQueries({ queryKey: queryKeys.claudeCredentials }),
  });
}

export function useDeleteClaudeCredential() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) =>
      apiClient.delete<void>(`/settings/claude-credentials/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: queryKeys.claudeCredentials }),
  });
}

// ── Git credentials ───────────────────────────────────────────
export function useGitCredentials() {
  return useQuery({
    queryKey: queryKeys.gitCredentials,
    queryFn: ({ signal }) =>
      apiClient.get<GitCredentialRead[]>('/settings/git-credentials', { signal }),
  });
}

export function useUpsertGitCredential() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: GitCredentialCreate) =>
      apiClient.post<GitCredentialRead, GitCredentialCreate>(
        '/settings/git-credentials',
        body,
      ),
    onSuccess: () => qc.invalidateQueries({ queryKey: queryKeys.gitCredentials }),
  });
}

export function useDeleteGitCredential() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) =>
      apiClient.delete<void>(`/settings/git-credentials/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: queryKeys.gitCredentials }),
  });
}

// ── Remote repos (depuis le provider) ─────────────────────────
export function useRemoteRepos(provider: Provider, enabled = true) {
  return useQuery({
    queryKey: queryKeys.remoteRepos(provider),
    queryFn: ({ signal }) =>
      apiClient.get<RemoteRepo[]>(`/providers/${provider}/repos`, { signal }),
    enabled,
    staleTime: 60_000,
  });
}

// ── Projects ──────────────────────────────────────────────────
export function useProjects() {
  return useQuery({
    queryKey: queryKeys.projects,
    queryFn: ({ signal }) => apiClient.get<ProjectRead[]>('/projects', { signal }),
  });
}

export function useCreateProject() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: ProjectCreateFromRepo) =>
      apiClient.post<ProjectRead, ProjectCreateFromRepo>('/projects', body),
    onSuccess: () => qc.invalidateQueries({ queryKey: queryKeys.projects }),
  });
}

export function useCreateRemoteRepo() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: {
      provider: Provider;
      name: string;
      private: boolean;
      description?: string | null;
      create_project: boolean;
    }) =>
      apiClient.post<ProjectRead, typeof body>(
        `/providers/${body.provider}/repos`,
        body,
      ),
    onSuccess: (_data, vars) => {
      qc.invalidateQueries({ queryKey: queryKeys.remoteRepos(vars.provider) });
      qc.invalidateQueries({ queryKey: queryKeys.projects });
    },
  });
}

export function useDeleteProject() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => apiClient.delete<void>(`/projects/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: queryKeys.projects }),
  });
}

export function useSessions() {
  return useQuery({
    queryKey: queryKeys.sessions,
    queryFn: ({ signal }) => apiClient.get<SessionRead[]>('/sessions', { signal }),
  });
}

export function useSession(id: string, enabled = true) {
  return useQuery({
    queryKey: queryKeys.session(id),
    queryFn: ({ signal }) =>
      apiClient.get<SessionRead>(`/sessions/${id}`, { signal }),
    enabled,
  });
}

export function useSessionEvents(id: string, enabled = true) {
  return useQuery({
    queryKey: queryKeys.sessionEvents(id),
    queryFn: ({ signal }) =>
      apiClient.get<SessionEventRead[]>(`/sessions/${id}/events`, { signal }),
    enabled,
    staleTime: 0,
  });
}

export function useCreateSession() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: SessionCreate) =>
      apiClient.post<SessionRead, SessionCreate>('/sessions', body),
    onSuccess: () => qc.invalidateQueries({ queryKey: queryKeys.sessions }),
  });
}

export function useSendMessage(sessionId: string) {
  return useMutation({
    mutationFn: (body: SessionMessageInput) =>
      apiClient.post<{ status: string }, SessionMessageInput>(
        `/sessions/${sessionId}/messages`,
        body,
      ),
  });
}

export function useStopSession() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) =>
      apiClient.post<void>(`/sessions/${id}/stop`),
    onSuccess: (_data, id) => {
      qc.invalidateQueries({ queryKey: queryKeys.session(id) });
      qc.invalidateQueries({ queryKey: queryKeys.sessions });
    },
  });
}

export function useResumeSession() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) =>
      apiClient.post<SessionRead>(`/sessions/${id}/resume`),
    onSuccess: (_data, id) => {
      qc.invalidateQueries({ queryKey: queryKeys.session(id) });
    },
  });
}

// ── Git ops sur une session (chantier 5) ──────────────────────
export function useSessionGitStatus(sessionId: string, enabled = true) {
  return useQuery({
    queryKey: queryKeys.sessionGitStatus(sessionId),
    queryFn: ({ signal }) =>
      apiClient.get<GitStatusResponse>(
        `/sessions/${sessionId}/git-status`,
        { signal },
      ),
    enabled,
    refetchInterval: 5_000,
  });
}

export function useCommitPush(sessionId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: CommitPushRequest) =>
      apiClient.post<CommitPushResponse, CommitPushRequest>(
        `/sessions/${sessionId}/commit-push`,
        body,
      ),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.sessionGitStatus(sessionId) });
    },
  });
}

export function useOpenPR(sessionId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: OpenPullRequestRequest) =>
      apiClient.post<OpenPullRequestResponse, OpenPullRequestRequest>(
        `/sessions/${sessionId}/pull-request`,
        body,
      ),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.sessionGitStatus(sessionId) });
    },
  });
}
