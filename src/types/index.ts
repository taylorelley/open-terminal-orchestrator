export type PolicyTier = 'restricted' | 'standard' | 'elevated';
export type SandboxState = 'POOL' | 'WARMING' | 'READY' | 'ACTIVE' | 'SUSPENDED' | 'DESTROYED';
export type OwuiRole = 'admin' | 'user' | 'pending';
export type AuditCategory = 'enforcement' | 'lifecycle' | 'admin';
export type EnforcementEventType = 'allow' | 'deny' | 'route';
export type LifecycleEventType = 'created' | 'assigned' | 'suspended' | 'resumed' | 'destroyed';
export type AdminEventType = 'policy_change' | 'config_change';
export type PolicyAssignmentEntity = 'user' | 'group' | 'role';

export interface Policy {
  id: string;
  name: string;
  tier: PolicyTier;
  description: string;
  current_version: string;
  yaml: string;
  created_at: string;
  updated_at: string;
}

export interface PolicyVersion {
  id: string;
  policy_id: string;
  version: string;
  yaml: string;
  changelog: string;
  created_by: string | null;
  created_at: string;
}

export interface Group {
  id: string;
  name: string;
  description: string;
  policy_id: string | null;
  created_at: string;
  updated_at: string;
  policy?: Policy | null;
}

export interface User {
  id: string;
  owui_id: string;
  username: string;
  email: string;
  owui_role: OwuiRole;
  group_id: string | null;
  synced_at: string;
  group?: Group | null;
}

export interface Sandbox {
  id: string;
  name: string;
  user_id: string | null;
  state: SandboxState;
  policy_id: string | null;
  internal_ip: string;
  image_tag: string;
  gpu_enabled: boolean;
  cpu_usage: number;
  memory_usage: number;
  disk_usage: number;
  network_io: number;
  created_at: string;
  last_active_at: string;
  suspended_at: string | null;
  destroyed_at: string | null;
  user?: User | null;
  policy?: Policy | null;
}

export interface PolicyAssignment {
  id: string;
  entity_type: PolicyAssignmentEntity;
  entity_id: string;
  policy_id: string;
  priority: number;
  created_by: string | null;
  created_at: string;
  policy?: Policy | null;
}

export interface AuditLogEntry {
  id: string;
  timestamp: string;
  event_type: string;
  category: AuditCategory;
  user_id: string | null;
  sandbox_id: string | null;
  details: Record<string, unknown>;
  source_ip: string;
  user?: User | null;
  sandbox?: Sandbox | null;
}

export interface SystemConfig {
  key: string;
  value: Record<string, unknown>;
  updated_at: string;
  updated_by: string | null;
}
