import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

vi.mock('../../lib/supabase', () => {
  const users = [
    { id: '1', owui_id: 'o1', username: 'alice', email: 'alice@test.com', owui_role: 'admin', group_id: '10', synced_at: '2026-03-28T00:00:00Z', group: { id: '10', name: 'Developers', description: 'Dev team', policy_id: null, policy: null } },
    { id: '2', owui_id: 'o2', username: 'bob', email: 'bob@test.com', owui_role: 'user', group_id: null, synced_at: '2026-03-28T00:00:00Z', group: null },
  ];

  const groups = [
    { id: '10', name: 'Developers', description: 'Dev team', policy_id: null, policy: null, created_at: '2026-03-01T00:00:00Z', updated_at: '2026-03-28T00:00:00Z' },
    { id: '11', name: 'Analysts', description: 'Analytics team', policy_id: null, policy: null, created_at: '2026-03-01T00:00:00Z', updated_at: '2026-03-28T00:00:00Z' },
  ];

  const policies = [
    { id: 'p1', name: 'Default Restricted', tier: 'restricted', description: '', current_version: '1.0.0', yaml: '', created_at: '2026-03-01T00:00:00Z', updated_at: '2026-03-28T00:00:00Z' },
  ];

  const sandboxes = [
    { id: 's1', name: 'sg-pool-abc1', state: 'ACTIVE', user_id: '1', policy_id: null, internal_ip: '10.0.0.1', image_tag: 'slim', gpu_enabled: false, cpu_usage: 10, memory_usage: 256, disk_usage: 512, network_io: 100, created_at: '2026-03-01T00:00:00Z', last_active_at: '2026-03-28T12:00:00Z', suspended_at: null, destroyed_at: null },
  ];

  const tableData: Record<string, unknown[]> = {
    users,
    groups,
    policies,
    sandboxes,
    policy_assignments: [],
  };

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  function makeChain(data: unknown[]): any {
    return {
      select: vi.fn(() => makeChain(data)),
      eq: vi.fn(() => makeChain(data)),
      neq: vi.fn(() => makeChain(data)),
      order: vi.fn(() => makeChain(data)),
      limit: vi.fn(() => makeChain(data)),
      insert: vi.fn(() => makeChain(data)),
      update: vi.fn(() => makeChain(data)),
      delete: vi.fn(() => makeChain(data)),
      in: vi.fn(() => makeChain(data)),
      then: (resolve: (v: unknown) => void) => resolve({ data, error: null }),
    };
  }

  return {
    supabase: {
      from: vi.fn((table: string) => makeChain(tableData[table] ?? [])),
      channel: vi.fn(() => ({ on: vi.fn().mockReturnThis(), subscribe: vi.fn(), unsubscribe: vi.fn() })),
      removeChannel: vi.fn(),
    },
  };
});

import UsersGroups from '../UsersGroups';

describe('UsersGroups page', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders users in the User Directory tab', async () => {
    render(<UsersGroups />);

    await waitFor(() => {
      expect(screen.getByText('alice')).toBeInTheDocument();
    });

    expect(screen.getByText('bob')).toBeInTheDocument();
  });

  it('renders tab navigation with User Directory and Groups', async () => {
    render(<UsersGroups />);

    await waitFor(() => {
      expect(screen.getByText('User Directory')).toBeInTheDocument();
    });

    expect(screen.getByText('Groups')).toBeInTheDocument();
    expect(screen.getByText('Role Mappings')).toBeInTheDocument();
  });

  it('filters users by search term', async () => {
    const user = userEvent.setup();
    render(<UsersGroups />);

    await waitFor(() => {
      expect(screen.getByText('alice')).toBeInTheDocument();
    });

    const searchInput = screen.getByPlaceholderText('Search users...');
    await user.type(searchInput, 'alice');

    expect(screen.getByText('alice')).toBeInTheDocument();
    expect(screen.queryByText('bob')).not.toBeInTheDocument();
  });

  it('switches to Groups tab and shows group cards', async () => {
    const user = userEvent.setup();
    render(<UsersGroups />);

    await waitFor(() => {
      expect(screen.getByText('User Directory')).toBeInTheDocument();
    });

    await user.click(screen.getByText('Groups'));

    await waitFor(() => {
      expect(screen.getByText('Developers')).toBeInTheDocument();
    });

    expect(screen.getByText('Analysts')).toBeInTheDocument();
  });
});
