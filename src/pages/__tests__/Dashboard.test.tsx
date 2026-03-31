import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';

vi.mock('recharts', () => ({
  ResponsiveContainer: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  AreaChart: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  Area: () => <div />,
  XAxis: () => <div />,
  YAxis: () => <div />,
  Tooltip: () => <div />,
}));

vi.mock('../../lib/supabase', () => {
  const sandboxes = [
    { id: '1', name: 'sg-pool-abc1', state: 'ACTIVE', user_id: '1', policy_id: null, internal_ip: '10.0.0.1', image_tag: 'slim', gpu_enabled: false, cpu_usage: 25, memory_usage: 512, disk_usage: 200, network_io: 50, created_at: '2026-03-01T00:00:00Z', last_active_at: '2026-03-28T12:00:00Z', suspended_at: null, destroyed_at: null, user: { username: 'alice' }, policy: { name: 'Default', tier: 'restricted' } },
    { id: '2', name: 'sg-pool-def2', state: 'READY', user_id: null, policy_id: null, internal_ip: '10.0.0.2', image_tag: 'slim', gpu_enabled: false, cpu_usage: 0, memory_usage: 64, disk_usage: 100, network_io: 0, created_at: '2026-03-01T00:00:00Z', last_active_at: '2026-03-28T12:00:00Z', suspended_at: null, destroyed_at: null },
    { id: '3', name: 'sg-pool-ghi3', state: 'SUSPENDED', user_id: null, policy_id: null, internal_ip: '10.0.0.3', image_tag: 'slim', gpu_enabled: false, cpu_usage: 0, memory_usage: 0, disk_usage: 100, network_io: 0, created_at: '2026-03-01T00:00:00Z', last_active_at: '2026-03-28T10:00:00Z', suspended_at: '2026-03-28T11:00:00Z', destroyed_at: null },
  ];

  const auditEntries = [
    { id: 'a1', event_type: 'allow', category: 'enforcement', timestamp: new Date().toISOString(), details: { destination: 'api.openai.com' }, source_ip: '10.0.0.1', user: { username: 'alice' } },
    { id: 'a2', event_type: 'deny', category: 'enforcement', timestamp: new Date().toISOString(), details: { destination: 'evil.com' }, source_ip: '10.0.0.1', user: { username: 'bob' } },
  ];

  const systemConfig = [
    { key: 'pool', value: { max_active: 10, warmup_size: 2 } },
    { key: 'lifecycle', value: { idle_timeout: '30m' } },
  ];

  const lifecycleEntries = [
    { details: { warmup_time_ms: 3000 } },
    { details: { warmup_time_ms: 3400 } },
  ];

  const tableData: Record<string, unknown[]> = {
    sandboxes,
    audit_log: auditEntries,
    system_config: systemConfig,
  };

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  function makeChain(data: unknown[]): any {
    return {
      select: vi.fn(() => makeChain(data)),
      eq: vi.fn((_col: string, val: string) => {
        if (val === 'created') return makeChain(lifecycleEntries);
        return makeChain(data);
      }),
      neq: vi.fn(() => makeChain(data)),
      in: vi.fn(() => makeChain(data)),
      gte: vi.fn(() => makeChain(data)),
      order: vi.fn(() => makeChain(data)),
      limit: vi.fn(() => makeChain(data)),
      then: (resolve: (v: unknown) => void) => resolve({ data, error: null }),
    };
  }

  return {
    isLocalMode: false,
    supabase: {
      from: vi.fn((table: string) => makeChain(tableData[table] ?? [])),
      channel: vi.fn(() => ({ on: vi.fn().mockReturnThis(), subscribe: vi.fn(), unsubscribe: vi.fn() })),
      removeChannel: vi.fn(),
    },
  };
});

import Dashboard from '../Dashboard';

describe('Dashboard page', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders stat cards after loading', async () => {
    render(<Dashboard />);

    await waitFor(() => {
      expect(screen.getAllByText('Active Sandboxes').length).toBeGreaterThanOrEqual(1);
    });

    expect(screen.getByText('Suspended')).toBeInTheDocument();
    expect(screen.getByText('Pool Ready')).toBeInTheDocument();
    expect(screen.getByText('Enforcement (24h)')).toBeInTheDocument();
    expect(screen.getByText('Avg Startup')).toBeInTheDocument();
  });

  it('renders the resource utilization chart section', async () => {
    render(<Dashboard />);

    await waitFor(() => {
      expect(screen.getByText('Resource Utilization (24h)')).toBeInTheDocument();
    });
  });

  it('renders the recent activity section', async () => {
    render(<Dashboard />);

    await waitFor(() => {
      expect(screen.getByText('Recent Activity')).toBeInTheDocument();
    });
  });

  it('renders the active sandboxes table', async () => {
    render(<Dashboard />);

    await waitFor(() => {
      expect(screen.getByText('sg-pool-abc1')).toBeInTheDocument();
    });
  });
});
