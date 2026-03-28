import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { EmptyState, LoadingState } from '../EmptyState';

describe('EmptyState', () => {
  it('renders title and description', () => {
    render(
      <EmptyState
        icon={<span>icon</span>}
        title="No policies found"
        description="Create your first policy to get started."
      />,
    );
    expect(screen.getByText('No policies found')).toBeInTheDocument();
    expect(screen.getByText('Create your first policy to get started.')).toBeInTheDocument();
  });
});

describe('LoadingState', () => {
  it('renders loading placeholders', () => {
    const { container } = render(<LoadingState rows={3} />);
    const pulseElements = container.querySelectorAll('.animate-pulse');
    expect(pulseElements).toHaveLength(3);
  });
});
