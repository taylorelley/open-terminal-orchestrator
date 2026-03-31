import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

// jsdom does not provide IntersectionObserver
globalThis.IntersectionObserver = vi.fn().mockImplementation(() => ({
  observe: vi.fn(),
  unobserve: vi.fn(),
  disconnect: vi.fn(),
}));

vi.mock('../../lib/supabase', () => {
  const auditEntries = [
    { id: 'e1', event_type: 'allow', category: 'enforcement', timestamp: new Date().toISOString(), details: { destination: 'api.openai.com', method: 'GET', rule: 'allow-api' }, source_ip: '10.0.0.1', user: { username: 'alice' }, sandbox: { name: 'sg-pool-abc1' } },
    { id: 'e2', event_type: 'deny', category: 'enforcement', timestamp: new Date().toISOString(), details: { destination: 'evil.com', method: 'POST', rule: 'deny-all' }, source_ip: '10.0.0.2', user: { username: 'bob' }, sandbox: { name: 'sg-pool-def2' } },
  ];

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  function makeChain(data: unknown[], count?: number): any {
    return {
      select: vi.fn((_sel?: string, opts?: { count?: string; head?: boolean }) => {
        if (opts?.head) return makeChain([], 5);
        return makeChain(data);
      }),
      eq: vi.fn(() => makeChain(data, count)),
      neq: vi.fn(() => makeChain(data, count)),
      gte: vi.fn(() => makeChain(data, count)),
      order: vi.fn(() => makeChain(data, count)),
      limit: vi.fn(() => makeChain(data, count)),
      then: (resolve: (v: unknown) => void) => resolve({ data, error: null, count: count ?? null }),
    };
  }

  return {
    isLocalMode: false,
    supabase: {
      from: vi.fn(() => makeChain(auditEntries)),
      channel: vi.fn(() => ({ on: vi.fn().mockReturnThis(), subscribe: vi.fn(), unsubscribe: vi.fn() })),
      removeChannel: vi.fn(),
    },
  };
});

vi.mock('../../hooks/useSupabaseQuery', () => ({
  useSupabaseRealtime: vi.fn(() => ({ status: 'SUBSCRIBED' })),
}));

vi.mock('../../hooks/useFilterPresets', () => ({
  useFilterPresets: vi.fn(() => ({
    presets: [],
    savePreset: vi.fn(),
    deletePreset: vi.fn(),
  })),
}));

import AuditLog from '../AuditLog';

describe('AuditLog page', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders tab navigation with enforcement, lifecycle, and admin tabs', async () => {
    render(<AuditLog />);

    await waitFor(() => {
      expect(screen.getByText('Enforcement Events')).toBeInTheDocument();
    });

    expect(screen.getByText('Lifecycle Events')).toBeInTheDocument();
    expect(screen.getByText('Admin Actions')).toBeInTheDocument();
  });

  it('renders the search input', async () => {
    render(<AuditLog />);

    await waitFor(() => {
      expect(screen.getByPlaceholderText('Search events...')).toBeInTheDocument();
    });
  });

  it('renders audit entries after loading', async () => {
    render(<AuditLog />);

    await waitFor(() => {
      expect(screen.getByText('allow')).toBeInTheDocument();
    });

    expect(screen.getByText('deny')).toBeInTheDocument();
  });

  it('filters entries by search term', async () => {
    const user = userEvent.setup();
    render(<AuditLog />);

    await waitFor(() => {
      expect(screen.getByText('allow')).toBeInTheDocument();
    });

    const searchInput = screen.getByPlaceholderText('Search events...');
    await user.type(searchInput, 'alice');

    expect(screen.getByText('allow')).toBeInTheDocument();
    expect(screen.queryByText('deny')).not.toBeInTheDocument();
  });
});
