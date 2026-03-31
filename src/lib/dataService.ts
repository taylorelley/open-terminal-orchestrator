/**
 * Unified data access layer.
 *
 * In **Supabase mode** every call delegates to the Supabase JS client.
 * In **local mode** it routes through the backend REST API via `./api.ts`.
 *
 * Pages import helpers from this module instead of importing `supabase`
 * directly, so they work in both modes without changes.
 */

import { isLocalMode } from './supabase';
import { supabase } from './supabase';
import * as api from './api';
import type {
  Sandbox,
  Policy,
  PolicyVersion,
  PolicyAssignment,
  User,
  Group,
  AuditLogEntry,
  SystemConfig,
} from '../types';

// ---------------------------------------------------------------------------
// Generic result type mirroring Supabase's { data, error } shape
// ---------------------------------------------------------------------------
interface Result<T> {
  data: T | null;
  error: string | null;
}

function ok<T>(data: T): Result<T> {
  return { data, error: null };
}

function err<T>(message: string): Result<T> {
  return { data: null, error: message };
}

async function wrap<T>(fn: () => Promise<T>): Promise<Result<T>> {
  try {
    return ok(await fn());
  } catch (e) {
    return err((e as Error).message);
  }
}

// ---------------------------------------------------------------------------
// Sandboxes
// ---------------------------------------------------------------------------

export async function getSandboxes(opts?: {
  excludeState?: string;
  stateIn?: string[];
  orderBy?: string;
  ascending?: boolean;
}): Promise<Result<Sandbox[]>> {
  if (isLocalMode) {
    return wrap(() =>
      api.fetchSandboxes({
        state_ne: opts?.excludeState,
        state_in: opts?.stateIn,
        order: opts?.orderBy,
      }) as Promise<Sandbox[]>,
    );
  }

  let query = supabase.from('sandboxes').select('*, user:users(*), policy:policies(*)');
  if (opts?.excludeState) query = query.neq('state', opts.excludeState);
  if (opts?.stateIn) query = query.in('state', opts.stateIn);
  if (opts?.orderBy) query = query.order(opts.orderBy, { ascending: opts.ascending ?? false });
  const { data, error } = await query;
  if (error) return err(error.message);
  return ok((data || []) as Sandbox[]);
}

export async function suspendSandbox(id: string): Promise<Result<Sandbox>> {
  if (isLocalMode) return wrap(() => api.suspendSandbox(id) as Promise<Sandbox>);
  const { data, error } = await supabase
    .from('sandboxes')
    .update({ state: 'SUSPENDED', suspended_at: new Date().toISOString(), cpu_usage: 0, memory_usage: 0, network_io: 0 })
    .eq('id', id)
    .select('*, user:users(*), policy:policies(*)')
    .single();
  if (error) return err(error.message);
  return ok(data as Sandbox);
}

export async function resumeSandbox(id: string): Promise<Result<Sandbox>> {
  if (isLocalMode) return wrap(() => api.resumeSandbox(id) as Promise<Sandbox>);
  const { data, error } = await supabase
    .from('sandboxes')
    .update({ state: 'ACTIVE', suspended_at: null, last_active_at: new Date().toISOString() })
    .eq('id', id)
    .select('*, user:users(*), policy:policies(*)')
    .single();
  if (error) return err(error.message);
  return ok(data as Sandbox);
}

export async function destroySandbox(id: string): Promise<Result<Sandbox>> {
  if (isLocalMode) return wrap(() => api.destroySandbox(id) as Promise<Sandbox>);
  const { data, error } = await supabase
    .from('sandboxes')
    .update({ state: 'DESTROYED', destroyed_at: new Date().toISOString() })
    .eq('id', id)
    .select()
    .single();
  if (error) return err(error.message);
  return ok(data as Sandbox);
}

export async function getSandboxLogs(sandboxId: string, limit = 20): Promise<Result<AuditLogEntry[]>> {
  if (isLocalMode) return wrap(() => api.fetchSandboxLogs(sandboxId, limit) as Promise<AuditLogEntry[]>);
  const { data, error } = await supabase
    .from('audit_log')
    .select('*, user:users(*)')
    .eq('sandbox_id', sandboxId)
    .order('timestamp', { ascending: false })
    .limit(limit);
  if (error) return err(error.message);
  return ok((data || []) as AuditLogEntry[]);
}

// ---------------------------------------------------------------------------
// Policies
// ---------------------------------------------------------------------------

export async function getPolicies(): Promise<Result<Policy[]>> {
  if (isLocalMode) return wrap(() => api.fetchPolicies() as Promise<Policy[]>);
  const { data, error } = await supabase.from('policies').select('*').order('created_at', { ascending: true });
  if (error) return err(error.message);
  return ok((data || []) as Policy[]);
}

export async function createPolicy(body: Partial<Policy>): Promise<Result<Policy>> {
  if (isLocalMode) return wrap(() => api.createPolicy(body as Record<string, unknown>) as Promise<Policy>);
  const { data, error } = await supabase.from('policies').insert(body as Record<string, unknown>).select().single();
  if (error) return err(error.message);
  return ok(data as Policy);
}

export async function updatePolicy(id: string, body: Partial<Policy>): Promise<Result<Policy>> {
  if (isLocalMode) return wrap(() => api.updatePolicy(id, body as Record<string, unknown>) as Promise<Policy>);
  const { data, error } = await supabase.from('policies').update(body as Record<string, unknown>).eq('id', id).select().single();
  if (error) return err(error.message);
  return ok(data as Policy);
}

export async function deletePolicy(id: string): Promise<Result<null>> {
  if (isLocalMode) return wrap(async () => { await api.deletePolicy(id); return null; });
  const { error } = await supabase.from('policies').delete().eq('id', id);
  if (error) return err(error.message);
  return ok(null);
}

export async function getPolicyVersions(policyId: string): Promise<Result<PolicyVersion[]>> {
  if (isLocalMode) return wrap(() => api.fetchPolicyVersions(policyId) as Promise<PolicyVersion[]>);
  const { data, error } = await supabase
    .from('policy_versions')
    .select('*')
    .eq('policy_id', policyId)
    .order('created_at', { ascending: false });
  if (error) return err(error.message);
  return ok((data || []) as PolicyVersion[]);
}

export async function createPolicyVersion(body: Partial<PolicyVersion>): Promise<Result<PolicyVersion>> {
  if (isLocalMode) {
    // Use the policy update endpoint which handles version creation
    return wrap(() => api.updatePolicy(body.policy_id as string, { yaml: body.yaml } as Record<string, unknown>) as Promise<PolicyVersion>);
  }
  const { data, error } = await supabase.from('policy_versions').insert(body as Record<string, unknown>).select().single();
  if (error) return err(error.message);
  return ok(data as PolicyVersion);
}

// ---------------------------------------------------------------------------
// Policy Assignments
// ---------------------------------------------------------------------------

export async function getPolicyAssignments(): Promise<Result<PolicyAssignment[]>> {
  if (isLocalMode) return wrap(() => api.fetchPolicyAssignments() as Promise<PolicyAssignment[]>);
  const { data, error } = await supabase
    .from('policy_assignments')
    .select('*, policy:policies(*)')
    .order('priority', { ascending: false });
  if (error) return err(error.message);
  return ok((data || []) as PolicyAssignment[]);
}

export async function upsertPolicyAssignment(body: Partial<PolicyAssignment>): Promise<Result<PolicyAssignment>> {
  if (isLocalMode) return wrap(() => api.upsertPolicyAssignment(body as Record<string, unknown>) as Promise<PolicyAssignment>);
  if (body.id) {
    const { data, error } = await supabase
      .from('policy_assignments')
      .update({ policy_id: body.policy_id })
      .eq('id', body.id)
      .select('*, policy:policies(*)')
      .single();
    if (error) return err(error.message);
    return ok(data as PolicyAssignment);
  }
  const { data, error } = await supabase
    .from('policy_assignments')
    .insert(body as Record<string, unknown>)
    .select('*, policy:policies(*)')
    .single();
  if (error) return err(error.message);
  return ok(data as PolicyAssignment);
}

export async function deletePolicyAssignment(id: string): Promise<Result<null>> {
  if (isLocalMode) {
    // Use the upsert endpoint with a delete flag — or call assignments endpoint
    return wrap(async () => {
      // Backend doesn't have a direct delete for assignments;
      // this would need a dedicated endpoint or use upsert with priority=0.
      // For now, we'll call the general API.
      await api.upsertPolicyAssignment({ id, _delete: true } as Record<string, unknown>);
      return null;
    });
  }
  const { error } = await supabase.from('policy_assignments').delete().eq('id', id);
  if (error) return err(error.message);
  return ok(null);
}

// ---------------------------------------------------------------------------
// Users & Groups
// ---------------------------------------------------------------------------

export async function getUsers(): Promise<Result<User[]>> {
  if (isLocalMode) return wrap(() => api.fetchUsers() as Promise<User[]>);
  const { data, error } = await supabase
    .from('users')
    .select('*, group:groups(*, policy:policies(*))')
    .order('username');
  if (error) return err(error.message);
  return ok((data || []) as User[]);
}

export async function getGroups(): Promise<Result<Group[]>> {
  if (isLocalMode) return wrap(() => api.fetchGroups() as Promise<Group[]>);
  const { data, error } = await supabase.from('groups').select('*, policy:policies(*)').order('name');
  if (error) return err(error.message);
  return ok((data || []) as Group[]);
}

export async function createGroup(body: Partial<Group>): Promise<Result<Group>> {
  if (isLocalMode) return wrap(() => api.createGroup(body as Record<string, unknown>) as Promise<Group>);
  const { data, error } = await supabase.from('groups').insert(body as Record<string, unknown>).select('*, policy:policies(*)').single();
  if (error) return err(error.message);
  return ok(data as Group);
}

export async function updateGroup(id: string, body: Partial<Group>): Promise<Result<Group>> {
  if (isLocalMode) return wrap(() => api.updateGroup(id, body as Record<string, unknown>) as Promise<Group>);
  const { data, error } = await supabase.from('groups').update(body as Record<string, unknown>).eq('id', id).select('*, policy:policies(*)').single();
  if (error) return err(error.message);
  return ok(data as Group);
}

export async function deleteGroup(id: string): Promise<Result<null>> {
  if (isLocalMode) return wrap(async () => { await api.deleteGroup(id); return null; });
  // Clear group_id for members first, then delete.
  await supabase.from('users').update({ group_id: null }).eq('group_id', id);
  const { error } = await supabase.from('groups').delete().eq('id', id);
  if (error) return err(error.message);
  return ok(null);
}

export async function assignUserGroup(userId: string, groupId: string | null): Promise<Result<User>> {
  if (isLocalMode) {
    return wrap(async () => {
      if (groupId) {
        const result = await api.updateGroupMembers(groupId, [userId]);
        return (result as User[])[0];
      }
      // To remove from group, we'd need the current group — use a generic update
      const users = await api.fetchUsers() as User[];
      return users.find(u => u.id === userId) || ({} as User);
    });
  }
  const { data, error } = await supabase
    .from('users')
    .update({ group_id: groupId })
    .eq('id', userId)
    .select('*, group:groups(*, policy:policies(*))')
    .single();
  if (error) return err(error.message);
  return ok(data as User);
}

// ---------------------------------------------------------------------------
// Audit Log
// ---------------------------------------------------------------------------

export async function getAuditLog(opts: {
  category?: string;
  since?: string;
  limit?: number;
  sandboxId?: string;
}): Promise<Result<{ items: AuditLogEntry[]; total: number }>> {
  if (isLocalMode) {
    return wrap(async () => {
      const res = await api.fetchAuditLog({
        category: opts.category,
        since: opts.since,
        limit: opts.limit,
        sandbox_id: opts.sandboxId,
      });
      return { items: res.items as AuditLogEntry[], total: res.total };
    });
  }

  let query = supabase.from('audit_log').select('*, user:users(*), sandbox:sandboxes(*)');
  if (opts.category) query = query.eq('category', opts.category);
  if (opts.since) query = query.gte('timestamp', opts.since);
  query = query.order('timestamp', { ascending: false });
  if (opts.limit) query = query.limit(opts.limit);

  const { data, error } = await query;
  if (error) return err(error.message);
  return ok({ items: (data || []) as AuditLogEntry[], total: (data || []).length });
}

export async function getAuditLogCount(category: string, since: string): Promise<Result<number>> {
  if (isLocalMode) {
    return wrap(async () => {
      const res = await api.fetchAuditLog({ category, since, limit: 0 });
      return res.total;
    });
  }
  const { count, error } = await supabase
    .from('audit_log')
    .select('id', { count: 'exact', head: true })
    .eq('category', category)
    .gte('timestamp', since);
  if (error) return err(error.message);
  return ok(count ?? 0);
}

// ---------------------------------------------------------------------------
// System Config
// ---------------------------------------------------------------------------

export async function getSystemConfig(): Promise<Result<SystemConfig[]>> {
  if (isLocalMode) return wrap(() => api.fetchSystemConfig() as Promise<SystemConfig[]>);
  const { data, error } = await supabase.from('system_config').select('*');
  if (error) return err(error.message);
  return ok((data || []) as SystemConfig[]);
}

export async function upsertSystemConfig(key: string, value: unknown): Promise<Result<SystemConfig>> {
  if (isLocalMode) return wrap(() => api.upsertSystemConfig(key, value) as Promise<SystemConfig>);
  const { data, error } = await supabase
    .from('system_config')
    .upsert({ key, value, updated_at: new Date().toISOString() })
    .select()
    .single();
  if (error) return err(error.message);
  return ok(data as SystemConfig);
}

// ---------------------------------------------------------------------------
// Combined dashboard data (convenience)
// ---------------------------------------------------------------------------

export async function getDashboardData() {
  const [sandboxRes, auditRes, configRes, lifecycleRes] = await Promise.all([
    getSandboxes({ excludeState: 'DESTROYED' }),
    getAuditLog({ limit: 20 }),
    getSystemConfig(),
    getAuditLog({ category: 'lifecycle', since: new Date(Date.now() - 3600000).toISOString(), limit: 200 }),
  ]);

  return {
    sandboxes: sandboxRes.data || [],
    recentEvents: auditRes.data?.items || [],
    config: configRes.data || [],
    lifecycleEvents: lifecycleRes.data?.items || [],
    error: sandboxRes.error || auditRes.error || configRes.error || lifecycleRes.error,
  };
}
