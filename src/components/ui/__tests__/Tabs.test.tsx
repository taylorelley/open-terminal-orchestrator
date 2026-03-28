import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { Tabs } from '../Tabs';

const tabs = [
  { id: 'library', label: 'Library', count: 3 },
  { id: 'assignments', label: 'Assignments' },
];

describe('Tabs', () => {
  it('renders tab labels', () => {
    render(<Tabs tabs={tabs} activeTab="library" onChange={vi.fn()} />);
    expect(screen.getByText('Library')).toBeInTheDocument();
    expect(screen.getByText('Assignments')).toBeInTheDocument();
  });

  it('calls onChange when a tab is clicked', async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(<Tabs tabs={tabs} activeTab="library" onChange={onChange} />);

    await user.click(screen.getByText('Assignments'));
    expect(onChange).toHaveBeenCalledWith('assignments');
  });
});
