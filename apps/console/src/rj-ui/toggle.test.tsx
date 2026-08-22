import { describe, expect, it, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { Toggle } from './Toggle';

describe('rj-ui Toggle', () => {
  it('reflects the checked state via aria-checked', () => {
    render(<Toggle checked onChange={vi.fn()} testId="t1" />);
    expect(screen.getByTestId('t1').getAttribute('aria-checked')).toBe('true');
  });

  it('calls onChange with the flipped value on click', () => {
    const onChange = vi.fn();
    render(<Toggle checked={false} onChange={onChange} testId="t2" />);
    fireEvent.click(screen.getByTestId('t2'));
    expect(onChange).toHaveBeenCalledWith(true);
  });

  it('does nothing while disabled', () => {
    const onChange = vi.fn();
    render(<Toggle checked={false} onChange={onChange} disabled testId="t3" />);
    fireEvent.click(screen.getByTestId('t3'));
    expect(onChange).not.toHaveBeenCalled();
  });

  it('renders a clickable label pairing when given one, and none when not', () => {
    render(<Toggle checked onChange={vi.fn()} label="أكّد الزيارة تلقائياً" testId="t4" />);
    expect(screen.getByText('أكّد الزيارة تلقائياً')).toBeTruthy();

    render(<Toggle checked onChange={vi.fn()} testId="t5" />);
    expect(screen.getByTestId('t5').closest('label')).toBeNull();
  });
});
