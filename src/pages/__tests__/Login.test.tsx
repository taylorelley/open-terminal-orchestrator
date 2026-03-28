import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';

const mockNavigate = vi.fn();

vi.mock('react-router-dom', () => ({
  useNavigate: () => mockNavigate,
  useSearchParams: () => [new URLSearchParams(), vi.fn()],
}));

vi.mock('../../contexts/AuthContext', () => ({
  useAuth: () => ({
    signIn: vi.fn(() => Promise.resolve({ error: null })),
    signUp: vi.fn(() => Promise.resolve({ error: null })),
    signInWithOIDC: vi.fn(),
    authMethod: 'local',
    oidcConfigured: false,
  }),
}));

import Login from '../Login';

describe('Login page', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders the ShellGuard title', () => {
    render(<Login />);

    expect(screen.getByText('ShellGuard')).toBeInTheDocument();
    expect(screen.getByText('Terminal Orchestration Console')).toBeInTheDocument();
  });

  it('renders email and password inputs', () => {
    render(<Login />);

    expect(screen.getByPlaceholderText('admin@example.com')).toBeInTheDocument();
    expect(screen.getByPlaceholderText('Enter password')).toBeInTheDocument();
  });

  it('renders the Sign In button', () => {
    render(<Login />);

    expect(screen.getByText('Sign In')).toBeInTheDocument();
  });

  it('renders the sign-up toggle link', () => {
    render(<Login />);

    expect(screen.getByText('Need an account? Create one')).toBeInTheDocument();
  });
});
