/**
 * Backend REST API client used in local (non-Supabase) mode.
 *
 * Every function mirrors a Supabase query used by the frontend pages and
 * translates it into the corresponding backend endpoint call.
 */

import { API_BASE } from './config';

// ---------------------------------------------------------------------------
// Token management
// ---------------------------------------------------------------------------

const TOKEN_KEY = 'oto_local_token';

export function getLocalToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function setLocalToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token);
}

export function clearLocalToken(): void {
  localStorage.removeItem(TOKEN_KEY);
}

// ---------------------------------------------------------------------------
// Low-level fetch wrapper
// ---------------------------------------------------------------------------

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const token = getLocalToken();
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(init?.headers as Record<string, string> | undefined),
  };
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  const res = await fetch(`${API_BASE}${path}`, { ...init, headers });
  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(body.detail || body.error || res.statusText);
  }
  return res.json() as Promise<T>;
}

// ---------------------------------------------------------------------------
// Auth
// ---------------------------------------------------------------------------

export async function localSignUp(email: string, password: string) {
  return apiFetch<{ token: string; user: { id: string; email: string } }>(
    '/auth/local/signup',
    { method: 'POST', body: JSON.stringify({ email, password }) },
  );
}

export async function localSignIn(email: string, password: string) {
  return apiFetch<{ token: string; user: { id: string; email: string } }>(
    '/auth/local/login',
    { method: 'POST', body: JSON.stringify({ email, password }) },
  );
}

export async function localSession() {
  return apiFetch<{
    authenticated: boolean;
    method: string | null;
    sub?: string;
    email?: string;
    name?: string;
    groups?: string[];
  }>('/auth/local/session');
}

export async function authConfig() {
  return apiFetch<{ auth_method: string; oidc_configured: boolean }>('/auth/config');
}

// ---------------------------------------------------------------------------
// Sandboxes
// ---------------------------------------------------------------------------

interface PaginatedResponse<T> { items: T[]; total: number }

export async function fetchSandboxes(params?: { state_ne?: string; state_in?: string[]; order?: string; limit?: number }) {
  const q = new URLSearchParams();
  if (params?.state_ne) q.set('state_ne', params.state_ne);
  if (params?.state_in) q.set('state_in', params.state_in.join(','));
  if (params?.order) q.set('order', params.order);
  if (params?.limit) q.set('limit', String(params.limit));
  const qs = q.toString();
  const data = await apiFetch<PaginatedResponse<unknown>>(`/sandboxes${qs ? `?${qs}` : ''}`);
  return data.items;
}

export async function suspendSandbox(id: string) {
  return apiFetch<unknown>(`/sandboxes/${id}/suspend`, { method: 'POST' });
}

export async function resumeSandbox(id: string) {
  return apiFetch<unknown>(`/sandboxes/${id}/resume`, { method: 'POST' });
}

export async function destroySandbox(id: string) {
  return apiFetch<unknown>(`/sandboxes/${id}`, { method: 'DELETE' });
}

export async function fetchSandboxLogs(sandboxId: string, limit = 20) {
  const data = await apiFetch<PaginatedResponse<unknown>>(`/sandboxes/${sandboxId}/logs?limit=${limit}`);
  return data.items;
}

// ---------------------------------------------------------------------------
// Policies
// ---------------------------------------------------------------------------

export async function fetchPolicies() {
  return apiFetch<unknown[]>('/policies');
}

export async function createPolicy(body: Record<string, unknown>) {
  return apiFetch<unknown>('/policies', { method: 'POST', body: JSON.stringify(body) });
}

export async function updatePolicy(id: string, body: Record<string, unknown>) {
  return apiFetch<unknown>(`/policies/${id}`, { method: 'PUT', body: JSON.stringify(body) });
}

export async function deletePolicy(id: string) {
  return apiFetch<void>(`/policies/${id}`, { method: 'DELETE' });
}

export async function fetchPolicyVersions(policyId: string) {
  return apiFetch<unknown[]>(`/policies/${policyId}/versions`);
}

export async function fetchPolicyAssignments() {
  return apiFetch<unknown[]>('/policies/assignments');
}

export async function upsertPolicyAssignment(body: Record<string, unknown>) {
  return apiFetch<unknown>('/policies/assignments', { method: 'PUT', body: JSON.stringify(body) });
}

// ---------------------------------------------------------------------------
// Users & Groups
// ---------------------------------------------------------------------------

export async function fetchUsers() {
  return apiFetch<unknown[]>('/users');
}

export async function fetchGroups() {
  return apiFetch<unknown[]>('/groups');
}

export async function createGroup(body: Record<string, unknown>) {
  return apiFetch<unknown>('/groups', { method: 'POST', body: JSON.stringify(body) });
}

export async function updateGroup(id: string, body: Record<string, unknown>) {
  return apiFetch<unknown>(`/groups/${id}`, { method: 'PUT', body: JSON.stringify(body) });
}

export async function deleteGroup(id: string) {
  return apiFetch<void>(`/groups/${id}`, { method: 'DELETE' });
}

export async function updateGroupMembers(groupId: string, userIds: string[]) {
  return apiFetch<unknown[]>(`/groups/${groupId}/members`, {
    method: 'PUT',
    body: JSON.stringify({ user_ids: userIds }),
  });
}

// ---------------------------------------------------------------------------
// Audit Log
// ---------------------------------------------------------------------------

export async function fetchAuditLog(params: {
  category?: string;
  since?: string;
  limit?: number;
  sandbox_id?: string;
}) {
  const q = new URLSearchParams();
  if (params.category) q.set('category', params.category);
  if (params.since) q.set('since', params.since);
  if (params.limit) q.set('limit', String(params.limit));
  if (params.sandbox_id) q.set('sandbox_id', params.sandbox_id);
  const qs = q.toString();
  const data = await apiFetch<PaginatedResponse<unknown>>(`/audit${qs ? `?${qs}` : ''}`);
  return data;
}

// ---------------------------------------------------------------------------
// System Config
// ---------------------------------------------------------------------------

export async function fetchSystemConfig() {
  return apiFetch<unknown[]>('/config');
}

export async function upsertSystemConfig(key: string, value: unknown) {
  return apiFetch<unknown>(`/config/${key}`, {
    method: 'PUT',
    body: JSON.stringify({ value }),
  });
}

// ---------------------------------------------------------------------------
// Metrics
// ---------------------------------------------------------------------------

export async function fetchMetricsHistory(params: { metric_type?: string; since?: string; until?: string }) {
  const q = new URLSearchParams();
  if (params.metric_type) q.set('metric_type', params.metric_type);
  if (params.since) q.set('since', params.since);
  if (params.until) q.set('until', params.until);
  const qs = q.toString();
  return apiFetch<{ items: unknown[] }>(`/metrics/history${qs ? `?${qs}` : ''}`);
}

// ---------------------------------------------------------------------------
// Backup / Export
// ---------------------------------------------------------------------------

export async function createBackup() {
  return apiFetch<unknown>('/backup', { method: 'POST' });
}
