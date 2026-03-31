import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

vi.mock('../../lib/supabase', () => {
  const sandboxData = [
    { id: '1', name: 'sg-pool-abc1', state: 'ACTIVE', user_id: '1', policy_id: null, internal_ip: '10.0.0.1', image_tag: 'slim', gpu_enabled: false, cpu_usage: 10, memory_usage: 256, disk_usage: 512, network_io: 100, created_at: '2026-03-01T00:00:00Z', last_active_at: '2026-03-28T12:00:00Z', suspended_at: null, destroyed_at: null },
    { id: '2', name: 'sg-pool-def2', state: 'READY', user_id: null, policy_id: null, internal_ip: '10.0.0.2', image_tag: 'slim', gpu_enabled: false, cpu_usage: 0, memory_usage: 64, disk_usage: 100, network_io: 0, created_at: '2026-03-01T00:00:00Z', last_active_at: '2026-03-28T12:00:00Z', suspended_at: null, destroyed_at: null },
    { id: '3', name: 'sg-pool-ghi3', state: 'SUSPENDED', user_id: null, policy_id: null, internal_ip: '10.0.0.3', image_tag: 'slim', gpu_enabled: false, cpu_usage: 0, memory_usage: 0, disk_usage: 100, network_io: 0, created_at: '2026-03-01T00:00:00Z', last_active_at: '2026-03-28T10:00:00Z', suspended_at: '2026-03-28T11:00:00Z', destroyed_at: null },
  ];

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  function makeChain(data: unknown[]): any {
    return {
      select: vi.fn(() => makeChain(data)),
      eq: vi.fn(() => makeChain(data)),
      neq: vi.fn(() => makeChain(data)),
      order: vi.fn(() => makeChain(data)),
      limit: vi.fn(() => makeChain(data)),
      update: vi.fn(() => makeChain(data)),
      in: vi.fn(() => makeChain(data)),
      then: (resolve: (v: unknown) => void) => resolve({ data, error: null }),
    };
  }

  return {
    isLocalMode: false,
    supabase: {
      from: vi.fn((table: string) => makeChain(table === 'sandboxes' ? sandboxData : [])),
      channel: vi.fn(() => ({ on: vi.fn().mockReturnThis(), subscribe: vi.fn(), unsubscribe: vi.fn() })),
      removeChannel: vi.fn(),
    },
  };
});

vi.mock('../../components/TerminalEmbed', () => ({
  TerminalEmbed: () => <div data-testid="terminal-embed">Terminal</div>,
}));

import Sandboxes from '../Sandboxes';

describe('Sandboxes page', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders the sandbox list after loading', async () => {
    render(<Sandboxes />);

    await waitFor(() => {
      expect(screen.getByText('sg-pool-abc1')).toBeInTheDocument();
    });

    expect(screen.getByText('sg-pool-def2')).toBeInTheDocument();
  });

  it('renders search input', async () => {
    render(<Sandboxes />);

    await waitFor(() => {
      expect(screen.getByPlaceholderText(/search/i)).toBeInTheDocument();
    });
  });

  it('filters sandboxes by search term', async () => {
    const user = userEvent.setup();
    render(<Sandboxes />);

    await waitFor(() => {
      expect(screen.getByText('sg-pool-abc1')).toBeInTheDocument();
    });

    const searchInput = screen.getByPlaceholderText(/search/i);
    await user.type(searchInput, 'abc1');

    expect(screen.getByText('sg-pool-abc1')).toBeInTheDocument();
    expect(screen.queryByText('sg-pool-def2')).not.toBeInTheDocument();
  });

  it('displays tab navigation', async () => {
    render(<Sandboxes />);

    await waitFor(() => {
      // The Sandboxes page has tab buttons — check for at least one tab label
      expect(screen.getByText('Suspended')).toBeInTheDocument();
    });
  });
});
