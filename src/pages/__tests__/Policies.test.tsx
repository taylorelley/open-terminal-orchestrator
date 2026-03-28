import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

vi.mock('../../lib/supabase', () => {
  const policies = [
    { id: '1', name: 'Default Restricted', tier: 'restricted', description: '', current_version: '1.0.0', yaml: '', created_at: '2026-03-01T00:00:00Z', updated_at: '2026-03-28T12:00:00Z' },
    { id: '2', name: 'Developer Elevated', tier: 'elevated', description: '', current_version: '1.0.0', yaml: '', created_at: '2026-03-01T00:00:00Z', updated_at: '2026-03-28T12:00:00Z' },
  ];
  const tableData: Record<string, unknown[]> = {
    policies,
    policy_assignments: [],
    users: [{ id: '10', owui_id: 'o1', username: 'testuser', email: 't@t.com', owui_role: 'user', group_id: null, synced_at: '2026-03-28T00:00:00Z' }],
    groups: [{ id: '20', name: 'g1', description: '', policy_id: null, created_at: '2026-03-01T00:00:00Z', updated_at: '2026-03-28T00:00:00Z' }],
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

import Policies from '../Policies';

describe('Policies page', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    global.fetch = vi.fn(() =>
      Promise.resolve({
        ok: true,
        json: () => Promise.resolve({ valid: true, errors: [] }),
      }),
    ) as unknown as typeof fetch;
  });

  it('renders the policy list after loading', async () => {
    render(<Policies />);

    await waitFor(() => {
      expect(screen.getByText('Default Restricted')).toBeInTheDocument();
    });

    expect(screen.getByText('Developer Elevated')).toBeInTheDocument();
  });

  it('renders tab navigation with Library tab', async () => {
    render(<Policies />);

    await waitFor(() => {
      expect(screen.getByText(/library/i)).toBeInTheDocument();
    });
  });

  it('renders search input', async () => {
    render(<Policies />);

    await waitFor(() => {
      expect(screen.getByPlaceholderText(/search/i)).toBeInTheDocument();
    });
  });

  it('filters policies by search term', async () => {
    const user = userEvent.setup();
    render(<Policies />);

    await waitFor(() => {
      expect(screen.getByText('Default Restricted')).toBeInTheDocument();
    });

    const searchInput = screen.getByPlaceholderText(/search/i);
    await user.type(searchInput, 'Developer');

    expect(screen.getByText('Developer Elevated')).toBeInTheDocument();
    expect(screen.queryByText('Default Restricted')).not.toBeInTheDocument();
  });
});
