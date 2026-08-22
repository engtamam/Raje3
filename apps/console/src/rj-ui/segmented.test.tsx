import { describe, expect, it, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { Segmented } from './Segmented';

const OPTIONS = [
  { value: 'all' as const, label: 'عملائي' },
  { value: 'overdue' as const, label: 'من تأخّر' },
];

describe('rj-ui Segmented', () => {
  it('renders every option and marks the active one', () => {
    render(<Segmented options={OPTIONS} value="all" onChange={vi.fn()} />);
    expect(screen.getByRole('radio', { name: 'عملائي' }).getAttribute('aria-checked')).toBe('true');
    expect(screen.getByRole('radio', { name: 'من تأخّر' }).getAttribute('aria-checked')).toBe('false');
  });

  it('calls onChange with the picked value', () => {
    const onChange = vi.fn();
    render(<Segmented options={OPTIONS} value="all" onChange={onChange} />);
    fireEvent.click(screen.getByText('من تأخّر'));
    expect(onChange).toHaveBeenCalledWith('overdue');
  });

  it('does nothing while disabled', () => {
    const onChange = vi.fn();
    render(<Segmented options={OPTIONS} value="all" onChange={onChange} disabled />);
    fireEvent.click(screen.getByText('من تأخّر'));
    expect(onChange).not.toHaveBeenCalled();
  });
});
