import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { StatCard } from '../StatCard';

describe('StatCard', () => {
  it('renders label and value', () => {
    render(
      <StatCard label="Active Sandboxes" value={42} icon={<span>icon</span>} />,
    );
    expect(screen.getByText('Active Sandboxes')).toBeInTheDocument();
    expect(screen.getByText('42')).toBeInTheDocument();
  });

  it('renders subtitle when provided', () => {
    render(
      <StatCard
        label="Total Users"
        value={100}
        subtitle="across all groups"
        icon={<span>icon</span>}
      />,
    );
    expect(screen.getByText('across all groups')).toBeInTheDocument();
  });
});
