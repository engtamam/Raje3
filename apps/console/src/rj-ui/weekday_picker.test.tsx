import { describe, expect, it, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { WeekdayPicker } from './WeekdayPicker';

const OPTIONS = [
  { value: 5, label: 'السبت' }, { value: 6, label: 'الأحد' }, { value: 0, label: 'الاثنين' },
  { value: 1, label: 'الثلاثاء' }, { value: 2, label: 'الأربعاء' }, { value: 3, label: 'الخميس' },
  { value: 4, label: 'الجمعة' },
];

describe('rj-ui WeekdayPicker', () => {
  it('marks the selected days pressed, and the rest not', () => {
    render(<WeekdayPicker options={OPTIONS} selected={[4, 5]} onChange={vi.fn()} />);
    expect(screen.getByText('الجمعة').getAttribute('aria-pressed')).toBe('true');
    expect(screen.getByText('السبت').getAttribute('aria-pressed')).toBe('true');
    expect(screen.getByText('الأحد').getAttribute('aria-pressed')).toBe('false');
  });

  it('adds a day when an unselected chip is pressed', () => {
    const onChange = vi.fn();
    render(<WeekdayPicker options={OPTIONS} selected={[4]} onChange={onChange} />);
    fireEvent.click(screen.getByText('السبت'));
    expect(onChange).toHaveBeenCalledWith([4, 5]);
  });

  it('removes a day when an already-selected chip is pressed', () => {
    const onChange = vi.fn();
    render(<WeekdayPicker options={OPTIONS} selected={[4, 5]} onChange={onChange} />);
    fireEvent.click(screen.getByText('الجمعة'));
    expect(onChange).toHaveBeenCalledWith([5]);
  });
});
