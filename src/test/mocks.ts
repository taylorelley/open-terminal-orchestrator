import { vi } from 'vitest';
import type { Sandbox, Policy, User, Group } from '../types';

// eslint-disable-next-line @typescript-eslint/no-explicit-any
type ChainableQuery = Record<string, any>;

/**
 * Create a chainable mock that resolves to `{ data, error: null }`.
 * Every method returns the same chain so `.from().select().eq().order()` works.
 */
export function createQueryChain(
  tableData: Record<string, unknown[]>,
  table: string,
): ChainableQuery {
  const obj: ChainableQuery = {};
  const handler: ProxyHandler<ChainableQuery> = {
    get(_target, prop) {
      if (prop === 'then') {
        return (resolve: (v: unknown) => void) =>
          resolve({ data: tableData[table] ?? [], error: null });
      }
      if (typeof prop === 'string') {
        if (!obj[prop]) {
          obj[prop] = vi.fn(() => new Proxy({} as ChainableQuery, handler));
        }
        return obj[prop];
      }
      return undefined;
    },
  };
  return new Proxy(obj, handler);
}

/**
 * Build a `vi.fn()` that returns a chainable query per table name.
 */
export function createMockFrom(tableData: Record<string, unknown[]>) {
  return vi.fn((table: string) => createQueryChain(tableData, table));
}

// ---------------------------------------------------------------------------
// Factory helpers for test data
// ---------------------------------------------------------------------------

let idCounter = 0;
function nextId() {
  return `00000000-0000-0000-0000-${String(++idCounter).padStart(12, '0')}`;
}

export function makeSandbox(overrides: Partial<Sandbox> = {}): Sandbox {
  const id = nextId();
  return {
    id,
    name: `sg-test-${id.slice(-4)}`,
    user_id: null,
    state: 'ACTIVE',
    policy_id: null,
    internal_ip: '10.0.0.1',
    image_tag: 'oto-sandbox:slim',
    gpu_enabled: false,
    cpu_usage: 10,
    memory_usage: 256,
    disk_usage: 512,
    network_io: 100,
    created_at: '2026-03-01T00:00:00Z',
    last_active_at: '2026-03-28T12:00:00Z',
    suspended_at: null,
    destroyed_at: null,
    ...overrides,
  };
}

export function makePolicy(overrides: Partial<Policy> = {}): Policy {
  const id = nextId();
  return {
    id,
    name: `policy-${id.slice(-4)}`,
    tier: 'restricted',
    description: 'Test policy',
    current_version: '1.0.0',
    yaml: 'metadata:\n  name: test\n  tier: restricted\n  version: "1.0.0"\nnetwork:\n  default: deny\n',
    created_at: '2026-03-01T00:00:00Z',
    updated_at: '2026-03-28T12:00:00Z',
    ...overrides,
  };
}

export function makeUser(overrides: Partial<User> = {}): User {
  const id = nextId();
  return {
    id,
    owui_id: `owui-${id.slice(-4)}`,
    username: `user-${id.slice(-4)}`,
    email: `user-${id.slice(-4)}@test.local`,
    owui_role: 'user',
    group_id: null,
    synced_at: '2026-03-28T00:00:00Z',
    ...overrides,
  };
}

export function makeGroup(overrides: Partial<Group> = {}): Group {
  const id = nextId();
  return {
    id,
    name: `group-${id.slice(-4)}`,
    description: '',
    policy_id: null,
    created_at: '2026-03-01T00:00:00Z',
    updated_at: '2026-03-28T12:00:00Z',
    ...overrides,
  };
}
