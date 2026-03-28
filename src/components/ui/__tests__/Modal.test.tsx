import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { Modal } from '../Modal';

describe('Modal', () => {
  it('renders title and children when open', () => {
    render(
      <Modal open={true} onClose={vi.fn()} title="Confirm Delete">
        <p>Are you sure?</p>
      </Modal>,
    );
    expect(screen.getByText('Confirm Delete')).toBeInTheDocument();
    expect(screen.getByText('Are you sure?')).toBeInTheDocument();
  });

  it('does not render when open is false', () => {
    render(
      <Modal open={false} onClose={vi.fn()} title="Hidden Modal">
        <p>Should not appear</p>
      </Modal>,
    );
    expect(screen.queryByText('Hidden Modal')).not.toBeInTheDocument();
    expect(screen.queryByText('Should not appear')).not.toBeInTheDocument();
  });

  it('renders action buttons when provided', () => {
    render(
      <Modal
        open={true}
        onClose={vi.fn()}
        title="With Actions"
        actions={<button>Save</button>}
      >
        <p>Content</p>
      </Modal>,
    );
    expect(screen.getByText('Save')).toBeInTheDocument();
  });
});
