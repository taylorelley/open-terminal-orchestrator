import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { SlidePanel } from '../SlidePanel';

describe('SlidePanel', () => {
  it('renders title and children when open', () => {
    render(
      <SlidePanel open={true} onClose={vi.fn()} title="Panel Title">
        <p>Panel content</p>
      </SlidePanel>,
    );
    expect(screen.getByText('Panel Title')).toBeInTheDocument();
    expect(screen.getByText('Panel content')).toBeInTheDocument();
  });

  it('does not render content when open is false', () => {
    render(
      <SlidePanel open={false} onClose={vi.fn()} title="Hidden Panel">
        <p>Hidden content</p>
      </SlidePanel>,
    );
    expect(screen.queryByText('Hidden Panel')).not.toBeInTheDocument();
    expect(screen.queryByText('Hidden content')).not.toBeInTheDocument();
  });
});
