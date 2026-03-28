import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

vi.mock('../../lib/supabase', () => {
  const configData = [
    { key: 'general', value: { instance_name: 'ShellGuard Production', base_url: 'http://shellguard:8080', openshell_gateway: '', owui_endpoint: '', byoc_image: '' } },
    { key: 'pool', value: { warmup_size: 2, max_sandboxes: 20, max_active: 10 } },
    { key: 'lifecycle', value: { idle_timeout: '30m', suspend_timeout: '24h', startup_timeout: '120s', resume_timeout: '30s' } },
    { key: 'auth', value: { method: 'local', oidc_issuer: '', oidc_client_id: '', oidc_client_secret: '', oidc_redirect_uri: '' } },
    { key: 'integrations', value: { litellm_url: '', prometheus_enabled: true, webhook_url: '', syslog_enabled: false } },
  ];

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  function makeChain(data: unknown[]): any {
    return {
      select: vi.fn(() => makeChain(data)),
      eq: vi.fn(() => makeChain(data)),
      neq: vi.fn(() => makeChain(data)),
      order: vi.fn(() => makeChain(data)),
      limit: vi.fn(() => makeChain(data)),
      upsert: vi.fn(() => makeChain(data)),
      in: vi.fn(() => makeChain(data)),
      then: (resolve: (v: unknown) => void) => resolve({ data, error: null }),
    };
  }

  return {
    supabase: {
      from: vi.fn((table: string) => makeChain(table === 'system_config' ? configData : [])),
      channel: vi.fn(() => ({ on: vi.fn().mockReturnThis(), subscribe: vi.fn(), unsubscribe: vi.fn() })),
      removeChannel: vi.fn(),
    },
  };
});

import Settings from '../Settings';

describe('Settings page', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders tab navigation', async () => {
    render(<Settings />);

    await waitFor(() => {
      expect(screen.getByText('General')).toBeInTheDocument();
    });

    expect(screen.getByText('Pool & Lifecycle')).toBeInTheDocument();
    expect(screen.getByText('Authentication')).toBeInTheDocument();
    expect(screen.getByText('Integrations')).toBeInTheDocument();
    expect(screen.getByText('Backup & Export')).toBeInTheDocument();
  });

  it('renders Instance Configuration under General tab', async () => {
    render(<Settings />);

    await waitFor(() => {
      expect(screen.getByText('Instance Configuration')).toBeInTheDocument();
    });
  });

  it('switches to Pool & Lifecycle tab', async () => {
    const user = userEvent.setup();
    render(<Settings />);

    await waitFor(() => {
      expect(screen.getByText('General')).toBeInTheDocument();
    });

    await user.click(screen.getByText('Pool & Lifecycle'));

    await waitFor(() => {
      expect(screen.getByText('Pool Settings')).toBeInTheDocument();
    });

    expect(screen.getByText('Lifecycle Timeouts')).toBeInTheDocument();
  });

  it('switches to Backup & Export tab', async () => {
    const user = userEvent.setup();
    render(<Settings />);

    await waitFor(() => {
      expect(screen.getByText('General')).toBeInTheDocument();
    });

    await user.click(screen.getByText('Backup & Export'));

    await waitFor(() => {
      expect(screen.getByText('Full Backup')).toBeInTheDocument();
    });

    expect(screen.getByText('Export Individual')).toBeInTheDocument();
  });
});
