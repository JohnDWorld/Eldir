/**
 * TanStack Query - keys et hooks réutilisables.
 * Une seule source de vérité pour les `queryKey` (DRY).
 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { apiClient } from '@/lib/api/client';
import type {
  ClaudeCredentialCreate,
  ClaudeCredentialRead,
  CommitPushRequest,
  CommitPushResponse,
  CostDashboard,
  CostTotalsRead,
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
  SystemPromptRead,
  SystemPromptWrite,
  OllamaSettingsRead,
  OllamaSettingsWrite,
  OllamaStatus,
  OllamaTransformRequest,
  OllamaTransformResponse,
  UserRead,
} from '@/lib/types/api';
import type { Provider } from '@/lib/constants';

export const queryKeys = {
  health: ['health'] as const,
  setupStatus: ['setup', 'status'] as const,
  me: ['auth', 'me'] as const,
  claudeCredentials: ['settings', 'claude-credentials'] as const,
  gitCredentials: ['settings', 'git-credentials'] as const,
  githubOauthConfig: ['auth', 'github-oauth', 'config'] as const,
  remoteRepos: (provider: Provider) => ['providers', provider, 'repos'] as const,
  projects: ['projects'] as const,
  project: (id: string) => ['projects', id] as const,
  sessions: ['sessions'] as const,
  session: (id: string) => ['sessions', id] as const,
  sessionEvents: (id: string) => ['sessions', id, 'events'] as const,
  sessionGitStatus: (id: string) => ['sessions', id, 'git-status'] as const,
  sessionDiff: (id: string) => ['sessions', id, 'diff'] as const,
  sessionDiffFile: (id: string, path: string) =>
    ['sessions', id, 'diff', 'file', path] as const,
  projectTemplate: (projectId: string) =>
    ['projects', projectId, 'template'] as const,
  projectTemplateSkills: (projectId: string) =>
    ['projects', projectId, 'template', 'skills'] as const,
  projectTemplateSubAgents: (projectId: string) =>
    ['projects', projectId, 'template', 'sub-agents'] as const,
  templatePresets: ['templates', 'presets'] as const,
  templatePreset: (slug: string) => ['templates', 'presets', slug] as const,
  templateVersions: (projectId: string) =>
    ['projects', projectId, 'template', 'versions'] as const,
  costsDashboard: ['costs', 'dashboard'] as const,
  costsSession: (id: string) => ['costs', 'sessions', id] as const,
  systemPrompts: ['system-prompts'] as const,
  systemPrompt: (slug: string) => ['system-prompts', slug] as const,
  ollamaStatus: ['ollama', 'status'] as const,
  ollamaSettings: ['ollama', 'settings'] as const,
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

// ── GitHub OAuth ───────────────────────────────────────────────
export type GitHubOauthConfig = { enabled: boolean; client_id: string | null };
export type GitHubOauthStartResponse = { authorize_url: string };

export function useGitHubOauthConfig() {
  return useQuery({
    queryKey: queryKeys.githubOauthConfig,
    queryFn: ({ signal }) =>
      apiClient.get<GitHubOauthConfig>('/auth/github/oauth/config', { signal }),
    staleTime: 60_000,
  });
}

export function useGitHubOauthStart() {
  return useMutation({
    mutationFn: () =>
      apiClient.post<GitHubOauthStartResponse, Record<string, never>>(
        '/auth/github/oauth/start',
        {},
      ),
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

export type ProjectSyncResult = {
  fetched: boolean;
  fast_forwarded: boolean;
  ahead: number;
  behind: number;
  branch: string;
  has_local_changes: boolean;
  message: string | null;
};

export function useSyncProject() {
  return useMutation({
    mutationFn: (projectId: string) =>
      apiClient.post<ProjectSyncResult, Record<string, never>>(
        `/projects/${projectId}/sync`,
        {},
      ),
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
    // Refetch régulier pour pouvoir détecter les transitions d'état
    // côté frontend (cf. use-session-notifier) sans WS global.
    refetchInterval: 5_000,
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

/**
 * Démarre (ou reprend) la session superviseur et la renvoie. Idempotent :
 * appelable à chaque ouverture de la page Eldir.
 */
export function useEnsureSupervisor() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () =>
      apiClient.post<SessionRead, Record<string, never>>(
        '/supervisor/session',
        {},
      ),
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

export function useDeleteSession() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => apiClient.delete<void>(`/sessions/${id}`),
    onSuccess: (_data, id) => {
      qc.removeQueries({ queryKey: queryKeys.session(id) });
      qc.removeQueries({ queryKey: queryKeys.sessionEvents(id) });
      qc.invalidateQueries({ queryKey: queryKeys.sessions });
    },
  });
}

// ── Session diff ─────────────────────────────────────────────
export type SessionDiffFile = {
  path: string;
  status: string;
  additions: number;
  deletions: number;
};

export type SessionDiffSummary = {
  base_ref: string;
  head_branch: string;
  files: SessionDiffFile[];
};

export type SessionDiffFilePatch = {
  path: string;
  base_ref: string;
  patch: string;
};

export function useSessionDiff(sessionId: string, enabled = true) {
  return useQuery({
    queryKey: queryKeys.sessionDiff(sessionId),
    queryFn: ({ signal }) =>
      apiClient.get<SessionDiffSummary>(`/sessions/${sessionId}/diff`, {
        signal,
      }),
    enabled: enabled && Boolean(sessionId),
    staleTime: 5_000,
  });
}

export function useSessionDiffFile(
  sessionId: string,
  path: string | null,
) {
  return useQuery({
    queryKey: queryKeys.sessionDiffFile(sessionId, path ?? ''),
    queryFn: ({ signal }) =>
      apiClient.get<SessionDiffFilePatch>(
        `/sessions/${sessionId}/diff/file?path=${encodeURIComponent(path!)}`,
        { signal },
      ),
    enabled: Boolean(sessionId && path),
    staleTime: 5_000,
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

// ── Mission Templates (Phase 4) ───────────────────────────────
export type TemplateSkill = {
  id: string;
  template_id: string;
  name: string;
  description: string | null;
  content: string;
  created_at: string;
  updated_at: string;
};

export type TemplateSubAgent = {
  id: string;
  template_id: string;
  name: string;
  description: string | null;
  system_prompt: string;
  allowed_tools: string[] | null;
  created_at: string;
  updated_at: string;
};

export type MissionTemplate = {
  id: string;
  project_id: string;
  system_prompt: string | null;
  model: string | null;
  allowed_tools: string[] | null;
  source_preset: string | null;
  skills: TemplateSkill[];
  sub_agents: TemplateSubAgent[];
  created_at: string;
  updated_at: string;
};

export type MissionTemplateWrite = {
  system_prompt: string | null;
  model: string | null;
  allowed_tools: string[] | null;
};

export type TemplateSkillWrite = {
  name: string;
  description: string | null;
  content: string;
};

export type TemplateSubAgentWrite = {
  name: string;
  description: string | null;
  system_prompt: string;
  allowed_tools: string[] | null;
};

export function useProjectTemplate(projectId: string) {
  return useQuery({
    queryKey: queryKeys.projectTemplate(projectId),
    queryFn: ({ signal }) =>
      apiClient.get<MissionTemplate | null>(
        `/projects/${projectId}/template`,
        { signal },
      ),
    enabled: Boolean(projectId),
  });
}

export function useUpsertProjectTemplate(projectId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: MissionTemplateWrite) =>
      apiClient.put<MissionTemplate, MissionTemplateWrite>(
        `/projects/${projectId}/template`,
        body,
      ),
    onSuccess: (data) => {
      qc.setQueryData(queryKeys.projectTemplate(projectId), data);
    },
  });
}

export function useDeleteProjectTemplate(projectId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => apiClient.delete<void>(`/projects/${projectId}/template`),
    onSuccess: () => {
      qc.setQueryData(queryKeys.projectTemplate(projectId), null);
    },
  });
}

export function useTemplateSkills(projectId: string) {
  return useQuery({
    queryKey: queryKeys.projectTemplateSkills(projectId),
    queryFn: ({ signal }) =>
      apiClient.get<TemplateSkill[]>(
        `/projects/${projectId}/template/skills`,
        { signal },
      ),
    enabled: Boolean(projectId),
  });
}

export function useCreateTemplateSkill(projectId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: TemplateSkillWrite) =>
      apiClient.post<TemplateSkill, TemplateSkillWrite>(
        `/projects/${projectId}/template/skills`,
        body,
      ),
    onSuccess: () => {
      qc.invalidateQueries({
        queryKey: queryKeys.projectTemplateSkills(projectId),
      });
      qc.invalidateQueries({
        queryKey: queryKeys.projectTemplate(projectId),
      });
    },
  });
}

export function useUpdateTemplateSkill(projectId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, body }: { id: string; body: TemplateSkillWrite }) =>
      apiClient.put<TemplateSkill, TemplateSkillWrite>(
        `/projects/${projectId}/template/skills/${id}`,
        body,
      ),
    onSuccess: () => {
      qc.invalidateQueries({
        queryKey: queryKeys.projectTemplateSkills(projectId),
      });
      qc.invalidateQueries({
        queryKey: queryKeys.projectTemplate(projectId),
      });
    },
  });
}

export function useDeleteTemplateSkill(projectId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) =>
      apiClient.delete<void>(`/projects/${projectId}/template/skills/${id}`),
    onSuccess: () => {
      qc.invalidateQueries({
        queryKey: queryKeys.projectTemplateSkills(projectId),
      });
      qc.invalidateQueries({
        queryKey: queryKeys.projectTemplate(projectId),
      });
    },
  });
}

export function useTemplateSubAgents(projectId: string) {
  return useQuery({
    queryKey: queryKeys.projectTemplateSubAgents(projectId),
    queryFn: ({ signal }) =>
      apiClient.get<TemplateSubAgent[]>(
        `/projects/${projectId}/template/sub-agents`,
        { signal },
      ),
    enabled: Boolean(projectId),
  });
}

export function useCreateTemplateSubAgent(projectId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: TemplateSubAgentWrite) =>
      apiClient.post<TemplateSubAgent, TemplateSubAgentWrite>(
        `/projects/${projectId}/template/sub-agents`,
        body,
      ),
    onSuccess: () => {
      qc.invalidateQueries({
        queryKey: queryKeys.projectTemplateSubAgents(projectId),
      });
      qc.invalidateQueries({
        queryKey: queryKeys.projectTemplate(projectId),
      });
    },
  });
}

export function useUpdateTemplateSubAgent(projectId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      id,
      body,
    }: {
      id: string;
      body: TemplateSubAgentWrite;
    }) =>
      apiClient.put<TemplateSubAgent, TemplateSubAgentWrite>(
        `/projects/${projectId}/template/sub-agents/${id}`,
        body,
      ),
    onSuccess: () => {
      qc.invalidateQueries({
        queryKey: queryKeys.projectTemplateSubAgents(projectId),
      });
      qc.invalidateQueries({
        queryKey: queryKeys.projectTemplate(projectId),
      });
    },
  });
}

export function useDeleteTemplateSubAgent(projectId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) =>
      apiClient.delete<void>(
        `/projects/${projectId}/template/sub-agents/${id}`,
      ),
    onSuccess: () => {
      qc.invalidateQueries({
        queryKey: queryKeys.projectTemplateSubAgents(projectId),
      });
      qc.invalidateQueries({
        queryKey: queryKeys.projectTemplate(projectId),
      });
    },
  });
}

// ── Template presets (Chantier 5) ─────────────────────────────
export type TemplatePresetSummary = {
  slug: string;
  title: string;
  description: string;
  tags: string[];
  model: string | null;
  skill_count: number;
  sub_agent_count: number;
};

export type TemplatePresetSkill = {
  name: string;
  description: string | null;
  content: string;
};

export type TemplatePresetSubAgent = {
  name: string;
  description: string | null;
  system_prompt: string;
  allowed_tools: string[] | null;
};

export type TemplatePresetDetail = {
  slug: string;
  title: string;
  description: string;
  tags: string[];
  system_prompt: string;
  model: string | null;
  allowed_tools: string[] | null;
  skills: TemplatePresetSkill[];
  sub_agents: TemplatePresetSubAgent[];
};

export type TemplateGenerateResponse = {
  preset: TemplatePresetDetail;
  session_id: string;
};

export function useTemplatePresets() {
  return useQuery({
    queryKey: queryKeys.templatePresets,
    queryFn: ({ signal }) =>
      apiClient.get<TemplatePresetSummary[]>('/templates/presets', { signal }),
    staleTime: 5 * 60_000,
  });
}

export function useTemplatePreset(slug: string | null) {
  return useQuery({
    queryKey: slug ? queryKeys.templatePreset(slug) : ['templates', 'presets', 'none'],
    queryFn: ({ signal }) =>
      apiClient.get<TemplatePresetDetail>(`/templates/presets/${slug!}`, {
        signal,
      }),
    enabled: Boolean(slug),
    staleTime: 5 * 60_000,
  });
}

export type TemplateVersion = {
  id: string;
  template_id: string;
  version_index: number;
  note: string | null;
  snapshot: Record<string, unknown>;
  created_at: string;
  updated_at: string;
};

export function useTemplateVersions(projectId: string) {
  return useQuery({
    queryKey: queryKeys.templateVersions(projectId),
    queryFn: ({ signal }) =>
      apiClient.get<TemplateVersion[]>(
        `/projects/${projectId}/template/versions`,
        { signal },
      ),
    enabled: Boolean(projectId),
  });
}

export function useRestoreTemplateVersion(projectId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      versionId,
      note,
    }: {
      versionId: string;
      note?: string | null;
    }) =>
      apiClient.post<MissionTemplate, { note: string | null }>(
        `/projects/${projectId}/template/versions/${versionId}/restore`,
        { note: note ?? null },
      ),
    onSuccess: (data) => {
      qc.setQueryData(queryKeys.projectTemplate(projectId), data);
      qc.invalidateQueries({
        queryKey: queryKeys.templateVersions(projectId),
      });
      qc.invalidateQueries({
        queryKey: queryKeys.projectTemplateSkills(projectId),
      });
      qc.invalidateQueries({
        queryKey: queryKeys.projectTemplateSubAgents(projectId),
      });
    },
  });
}

export function useApplyTemplatePreset(projectId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: { slug: string; overwrite: boolean }) =>
      apiClient.post<MissionTemplate, { slug: string; overwrite: boolean }>(
        `/projects/${projectId}/template/apply-preset`,
        body,
      ),
    onSuccess: (data) => {
      qc.setQueryData(queryKeys.projectTemplate(projectId), data);
      qc.invalidateQueries({
        queryKey: queryKeys.projectTemplateSkills(projectId),
      });
      qc.invalidateQueries({
        queryKey: queryKeys.projectTemplateSubAgents(projectId),
      });
    },
  });
}

export function useApplyInlinePreset(projectId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: { preset: TemplatePresetDetail; overwrite: boolean }) =>
      apiClient.post<
        MissionTemplate,
        { preset: TemplatePresetDetail; overwrite: boolean }
      >(`/projects/${projectId}/template/apply-inline`, body),
    onSuccess: (data) => {
      qc.setQueryData(queryKeys.projectTemplate(projectId), data);
      qc.invalidateQueries({
        queryKey: queryKeys.projectTemplateSkills(projectId),
      });
      qc.invalidateQueries({
        queryKey: queryKeys.projectTemplateSubAgents(projectId),
      });
    },
  });
}

export function useGenerateTemplate(projectId: string) {
  return useMutation({
    mutationFn: (body: { model?: string | null }) =>
      apiClient.post<TemplateGenerateResponse, { model?: string | null }>(
        `/projects/${projectId}/template/generate`,
        body,
      ),
  });
}

// ── Costs (Phase 5) ────────────────────────────────────────────
export function useCostsDashboard() {
  return useQuery({
    queryKey: queryKeys.costsDashboard,
    queryFn: () => apiClient.get<CostDashboard>('/costs/dashboard'),
    refetchInterval: 30_000,
  });
}

export function useSessionCostTotals(sessionId: string, enabled = true) {
  return useQuery({
    queryKey: queryKeys.costsSession(sessionId),
    queryFn: () =>
      apiClient.get<CostTotalsRead>(`/costs/sessions/${sessionId}`),
    enabled,
    refetchInterval: 15_000,
  });
}

// ── System prompts (Settings > Prompts) ────────────────────────
export function useSystemPrompts() {
  return useQuery({
    queryKey: queryKeys.systemPrompts,
    queryFn: () => apiClient.get<SystemPromptRead[]>('/system-prompts'),
  });
}

export function useSystemPrompt(slug: string, enabled = true) {
  return useQuery({
    queryKey: queryKeys.systemPrompt(slug),
    queryFn: () =>
      apiClient.get<SystemPromptRead>(`/system-prompts/${slug}`),
    enabled,
  });
}

export function useUpsertSystemPrompt(slug: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: SystemPromptWrite) =>
      apiClient.put<SystemPromptRead, SystemPromptWrite>(
        `/system-prompts/${slug}`,
        body,
      ),
    onSuccess: (data) => {
      qc.setQueryData(queryKeys.systemPrompt(slug), data);
      qc.invalidateQueries({ queryKey: queryKeys.systemPrompts });
    },
  });
}

export function useResetSystemPrompt(slug: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () =>
      apiClient.post<SystemPromptRead>(`/system-prompts/${slug}/reset`),
    onSuccess: (data) => {
      qc.setQueryData(queryKeys.systemPrompt(slug), data);
      qc.invalidateQueries({ queryKey: queryKeys.systemPrompts });
    },
  });
}

// ── Ollama (Phase 6) ───────────────────────────────────────────
export function useOllamaStatus() {
  return useQuery({
    queryKey: queryKeys.ollamaStatus,
    queryFn: () => apiClient.get<OllamaStatus>('/ollama/status'),
    refetchInterval: 30_000,
  });
}

export function useOllamaTransform() {
  return useMutation({
    mutationFn: (body: OllamaTransformRequest) =>
      apiClient.post<OllamaTransformResponse, OllamaTransformRequest>(
        '/ollama/transform',
        body,
      ),
  });
}

export function useOllamaSettings() {
  return useQuery({
    queryKey: queryKeys.ollamaSettings,
    queryFn: () => apiClient.get<OllamaSettingsRead>('/ollama/settings'),
  });
}

export function useUpdateOllamaSettings() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: OllamaSettingsWrite) =>
      apiClient.put<OllamaSettingsRead, OllamaSettingsWrite>(
        '/ollama/settings',
        body,
      ),
    onSuccess: (data) => {
      qc.setQueryData(queryKeys.ollamaSettings, data);
    },
  });
}
