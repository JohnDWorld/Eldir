/**
 * Types API - façade DRY.
 *
 * Source de vérité : `api-generated.ts` (généré depuis OpenAPI via
 * `scripts/gen-types.sh`). Tant que le pipeline n'a pas tourné au moins
 * une fois, on conserve ici un miroir manuel en fallback.
 *
 * À TERME : ce fichier ne contiendra plus que des `export type` pointant
 * vers `api-generated.ts`. Voir [shared/README.md](../../../../shared/README.md).
 */

import type { Provider, SessionState } from '@/lib/constants';

export interface HealthResponse {
  status: string;
  app_name: string;
  version: string;
  env: string;
}

export interface ErrorResponse {
  code: string;
  message: string;
  details: Record<string, unknown>;
}

export interface TokenResponse {
  access_token: string;
  token_type: 'bearer';
  expires_in: number;
}

export interface UserRead {
  id: string;
  email: string;
  display_name: string | null;
  is_active: boolean;
  is_admin: boolean;
  created_at: string;
  updated_at: string;
}

export interface ProjectRead {
  id: string;
  name: string;
  slug: string;
  provider: Provider;
  repo_full_name: string;
  default_branch: string;
  workspace_path: string | null;
  created_at: string;
  updated_at: string;
}

export interface ProjectSummary {
  id: string;
  name: string;
  slug: string;
  provider: Provider;
  branch: string;
  active_sessions: number;
  last_activity_at: string | null;
}

export interface SessionRead {
  id: string;
  /** null pour la session superviseur (aucun repo rattaché). */
  project_id: string | null;
  user_id: string;
  sdk_session_id: string | null;
  branch: string;
  worktree_path: string | null;
  state: SessionState;
  summary: string | null;
  model: string | null;
  is_system: boolean;
  system_kind: string | null;
  created_at: string;
  updated_at: string;
}

export interface SessionSummary {
  id: string;
  project_slug: string;
  state: SessionState;
  summary: string | null;
  duration_seconds: number;
  input_tokens: number;
  output_tokens: number;
  cost_usd: number;
}

export type SessionEventType =
  | 'text'
  | 'tool_use'
  | 'tool_result'
  | 'state'
  | 'stop'
  | 'error'
  | 'user_message'
  | 'usage';

export interface SessionEvent {
  type: SessionEventType;
  session_id: string;
  timestamp: string;
  data: Record<string, unknown>;
}

export interface SessionEventRead {
  id: string;
  session_id: string;
  type: SessionEventType;
  payload: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface SessionCreate {
  project_id: string;
  system_prompt?: string | null;
  model?: string | null;
}

export interface SessionMessageInput {
  content: string;
}

// ── Git ops sur une session (chantier 5) ───────────────────────
export interface GitStatusResponse {
  branch: string;
  has_changes: boolean;
  modified: number;
  added: number;
  deleted: number;
  untracked: number;
}

export interface CommitPushRequest {
  message: string;
  push?: boolean;
}

export interface CommitPushResponse {
  branch: string;
  sha: string;
  pushed: boolean;
}

export interface OpenPullRequestRequest {
  title: string;
  body?: string | null;
  base?: string | null;
}

export interface OpenPullRequestResponse {
  pr_number: number;
  pr_url: string;
  head: string;
  base: string;
  title: string;
}

// ── Setup / auth ───────────────────────────────────────────────
export interface SetupStatus {
  needs_bootstrap: boolean;
  bootstrap_completed: boolean;
  has_admin: boolean;
  has_claude_credentials: boolean;
  eldir_version: string;
}

export interface LoginResponse extends TokenResponse {
  user: UserRead;
}

// ── Claude credentials ─────────────────────────────────────────
export type ClaudeCredentialKind = 'oauth_token' | 'api_key';

export interface ClaudeCredentialRead {
  id: string;
  kind: ClaudeCredentialKind;
  label: string | null;
  is_active: boolean;
  last_validated_at: string | null;
  masked_value: string;
  created_at: string;
  updated_at: string;
}

export interface ClaudeCredentialCreate {
  kind: ClaudeCredentialKind;
  value: string;
  label?: string | null;
}

// ── Git credentials ────────────────────────────────────────────
export interface GitCredentialRead {
  id: string;
  provider: Provider;
  base_url: string | null;
  label: string | null;
  masked_token: string;
  created_at: string;
  updated_at: string;
}

export interface GitCredentialCreate {
  provider: Provider;
  token: string;
  base_url?: string | null;
  label?: string | null;
}

// ── Remote repos (providers/{name}/repos) ──────────────────────
export interface RemoteRepo {
  full_name: string;
  default_branch: string;
  clone_url: string;
  description: string | null;
  is_private: boolean;
}

export interface ProjectCreateFromRepo {
  provider: Provider;
  repo_full_name: string;
  display_name?: string | null;
}

export interface RemoteRepoCreate {
  provider: Provider;
  name: string;
  private: boolean;
  description?: string | null;
  create_project: boolean;
}

// ── Ollama (Phase 6 - mode données sensibles) ──────────────────
export interface OllamaModelInfo {
  name: string;
  size_bytes: number;
  modified_at: string | null;
}

export interface OllamaStatus {
  enabled: boolean;
  base_url: string | null;
  reachable: boolean;
  error: string | null;
  default_model: string;
  available_models: OllamaModelInfo[];
}

export type OllamaTransformMode = 'mask' | 'anonymize' | 'summarize';

export interface OllamaTransformRequest {
  text: string;
  mode: OllamaTransformMode;
  model?: string | null;
}

export interface OllamaTransformResponse {
  text: string;
  mode: string;
  model_used: string;
}

export interface OllamaSettingsRead {
  expose_to_sessions: boolean;
}

export interface OllamaSettingsWrite {
  expose_to_sessions: boolean;
}

// ── System prompts (Settings > Prompts) ────────────────────────
export interface SystemPromptRead {
  slug: string;
  title: string;
  description: string;
  content: string;
  is_overridden: boolean;
  default_content: string;
}

export interface SystemPromptWrite {
  content: string;
}

// ── Costs (Phase 5 - Optimisation tokens) ──────────────────────
export interface CostTotalsRead {
  input_tokens: number;
  output_tokens: number;
  cache_read_tokens: number;
  cache_write_tokens: number;
  cost_usd: number;
  num_turns: number;
}

export interface DailyCostRead {
  day: string; // ISO date (YYYY-MM-DD)
  input_tokens: number;
  output_tokens: number;
  cache_read_tokens: number;
  cache_write_tokens: number;
  cost_usd: number;
}

export interface ProjectCostRead {
  project_id: string;
  project_name: string | null;
  input_tokens: number;
  output_tokens: number;
  cost_usd: number;
}

export interface CostDashboard {
  today: CostTotalsRead;
  last_7_days: CostTotalsRead;
  last_30_days: CostTotalsRead;
  daily: DailyCostRead[];
  by_project: ProjectCostRead[];
}
