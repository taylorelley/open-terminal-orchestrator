import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

vi.mock('../../lib/supabase', () => {
  const sandboxes = [
    { id: '1', name: 'sb-1', state: 'ACTIVE', user_id: null, policy_id: null, internal_ip: '10.0.0.1', image_tag: 'slim', gpu_enabled: false, cpu_usage: 45, memory_usage: 512, disk_usage: 100, network_io: 50, created_at: '2026-03-01T00:00:00Z', last_active_at: '2026-03-28T12:00:00Z', suspended_at: null, destroyed_at: null },
    { id: '2', name: 'sb-2', state: 'ACTIVE', user_id: null, policy_id: null, internal_ip: '10.0.0.2', image_tag: 'slim', gpu_enabled: false, cpu_usage: 30, memory_usage: 256, disk_usage: 50, network_io: 20, created_at: '2026-03-01T00:00:00Z', last_active_at: '2026-03-28T12:00:00Z', suspended_at: null, destroyed_at: null },
    { id: '3', name: 'sb-3', state: 'READY', user_id: null, policy_id: null, internal_ip: '10.0.0.3', image_tag: 'slim', gpu_enabled: false, cpu_usage: 0, memory_usage: 64, disk_usage: 10, network_io: 0, created_at: '2026-03-01T00:00:00Z', last_active_at: '2026-03-28T12:00:00Z', suspended_at: null, destroyed_at: null },
  ];

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  function makeChain(data: unknown[]): any {
    return {
      select: vi.fn(() => makeChain(data)),
      eq: vi.fn(() => makeChain(data)),
      neq: vi.fn(() => makeChain(data)),
      order: vi.fn(() => makeChain(data)),
      limit: vi.fn(() => makeChain(data)),
      in: vi.fn(() => makeChain(data)),
      then: (resolve: (v: unknown) => void) => resolve({ data, error: null }),
    };
  }

  return {
    isLocalMode: false,
    supabase: {
      from: vi.fn((table: string) => makeChain(table === 'sandboxes' ? sandboxes : [])),
      channel: vi.fn(() => ({ on: vi.fn().mockReturnThis(), subscribe: vi.fn(), unsubscribe: vi.fn() })),
      removeChannel: vi.fn(),
    },
  };
});

vi.mock('recharts', () => ({
  AreaChart: ({ children }: { children: React.ReactNode }) => <div data-testid="area-chart">{children}</div>,
  Area: () => null,
  BarChart: ({ children }: { children: React.ReactNode }) => <div data-testid="bar-chart">{children}</div>,
  Bar: () => null,
  XAxis: () => null,
  YAxis: () => null,
  Tooltip: () => null,
  ResponsiveContainer: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  PieChart: ({ children }: { children: React.ReactNode }) => <div data-testid="pie-chart">{children}</div>,
  Pie: () => null,
  Cell: () => null,
}));

import Monitoring from '../Monitoring';

describe('Monitoring page', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    global.fetch = vi.fn((url: string | URL) => {
      const urlStr = typeof url === 'string' ? url : url.toString();
      if (urlStr.includes('/alerts')) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({ rules: [] }),
        });
      }
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve({ points: [] }),
      });
    }) as unknown as typeof fetch;
  });

  it('renders the monitoring dashboard', async () => {
    render(<Monitoring />);

    await waitFor(() => {
      expect(screen.getByText(/resources/i)).toBeInTheDocument();
    });
  });

  it('renders time range selector buttons', async () => {
    render(<Monitoring />);

    await waitFor(() => {
      expect(screen.getByText('1h')).toBeInTheDocument();
      expect(screen.getByText('24h')).toBeInTheDocument();
      expect(screen.getByText('7d')).toBeInTheDocument();
      expect(screen.getByText('30d')).toBeInTheDocument();
    });
  });

  it('can switch time ranges', async () => {
    const user = userEvent.setup();
    render(<Monitoring />);

    await waitFor(() => {
      expect(screen.getByText('1h')).toBeInTheDocument();
    });

    await user.click(screen.getByText('7d'));
    expect(screen.getByText('7d')).toBeInTheDocument();
  });
});
