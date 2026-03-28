import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { Badge } from '../Badge';

describe('Badge', () => {
  it('renders children text', () => {
    render(<Badge>Active</Badge>);
    expect(screen.getByText('Active')).toBeInTheDocument();
  });

  it('renders with state variant and applies correct styling', () => {
    const { container } = render(
      <Badge variant="state" value="ACTIVE">
        ACTIVE
      </Badge>,
    );
    const badge = container.querySelector('span');
    expect(badge).toHaveClass('bg-emerald-100');
  });

  it('renders with tier variant', () => {
    const { container } = render(
      <Badge variant="tier" value="restricted">
        Restricted
      </Badge>,
    );
    const badge = container.querySelector('span');
    expect(badge).toHaveClass('bg-amber-100');
  });
});
