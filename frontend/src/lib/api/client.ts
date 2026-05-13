/**
 * Client API centralisé — JAMAIS appeler `fetch()` directement dans un composant.
 * Cf. AGENTS.md §TypeScript.
 */

import { API_BASE_URL } from '@/lib/constants';
import type { ErrorResponse } from '@/lib/types/api';

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly details: Record<string, unknown>;

  constructor(status: number, payload: ErrorResponse) {
    super(payload.message);
    this.name = 'ApiError';
    this.status = status;
    this.code = payload.code;
    this.details = payload.details;
  }
}

let authToken: string | null = null;

export function setAuthToken(token: string | null): void {
  authToken = token;
}

export function getAuthToken(): string | null {
  return authToken;
}

export interface RequestOptions {
  signal?: AbortSignal;
  headers?: Record<string, string>;
}

async function request<TResponse, TBody = unknown>(
  method: string,
  path: string,
  body?: TBody,
  options: RequestOptions = {},
): Promise<TResponse> {
  const headers: Record<string, string> = {
    Accept: 'application/json',
    ...(options.headers ?? {}),
  };
  if (body !== undefined) {
    headers['Content-Type'] = 'application/json';
  }
  if (authToken) {
    headers['Authorization'] = `Bearer ${authToken}`;
  }

  const response = await fetch(`${API_BASE_URL}${path}`, {
    method,
    headers,
    body: body === undefined ? null : JSON.stringify(body),
    signal: options.signal ?? null,
    credentials: 'include',
  });

  if (response.status === 204) {
    return undefined as TResponse;
  }

  const contentType = response.headers.get('content-type') ?? '';
  const isJson = contentType.includes('application/json');
  const payload: unknown = isJson ? await response.json() : await response.text();

  if (!response.ok) {
    const errorPayload: ErrorResponse =
      isJson && typeof payload === 'object' && payload !== null
        ? (payload as ErrorResponse)
        : { code: 'http_error', message: String(payload), details: {} };
    throw new ApiError(response.status, errorPayload);
  }

  return payload as TResponse;
}

export const apiClient = {
  get: <T>(path: string, options?: RequestOptions): Promise<T> =>
    request<T>('GET', path, undefined, options),
  post: <T, B = unknown>(path: string, body?: B, options?: RequestOptions): Promise<T> =>
    request<T, B>('POST', path, body, options),
  patch: <T, B = unknown>(path: string, body?: B, options?: RequestOptions): Promise<T> =>
    request<T, B>('PATCH', path, body, options),
  delete: <T>(path: string, options?: RequestOptions): Promise<T> =>
    request<T>('DELETE', path, undefined, options),
};
