import { describe, expect, it, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { HourRangePicker } from './HourRangePicker';

describe('rj-ui HourRangePicker', () => {
  it('shows the two hours as western-digit 00:00-shaped options', () => {
    render(<HourRangePicker startHour={8} endHour={20} onChange={vi.fn()} fromLabel="من" toLabel="إلى" />);
    const selects = screen.getAllByRole('combobox') as HTMLSelectElement[];
    expect(selects[0].value).toBe('8');
    expect(selects[1].value).toBe('20');
    expect(screen.getAllByText('08:00').length).toBeGreaterThan(0);
  });

  it('the end hour options run through 24 (midnight), the start hour options never reach it', () => {
    render(<HourRangePicker startHour={0} endHour={24} onChange={vi.fn()} fromLabel="من" toLabel="إلى" />);
    const [start, end] = screen.getAllByRole('combobox') as HTMLSelectElement[];
    const startValues = Array.from(start.options).map((o) => o.value);
    const endValues = Array.from(end.options).map((o) => o.value);
    expect(startValues).not.toContain('24');
    expect(endValues).toContain('24');
  });

  it('calls onChange with the new start, keeping the end untouched', () => {
    const onChange = vi.fn();
    render(<HourRangePicker startHour={8} endHour={20} onChange={onChange} fromLabel="من" toLabel="إلى" />);
    const [start] = screen.getAllByRole('combobox');
    fireEvent.change(start, { target: { value: '10' } });
    expect(onChange).toHaveBeenCalledWith(10, 20);
  });

  it('calls onChange with the new end, keeping the start untouched', () => {
    const onChange = vi.fn();
    render(<HourRangePicker startHour={8} endHour={20} onChange={onChange} fromLabel="من" toLabel="إلى" />);
    const [, end] = screen.getAllByRole('combobox');
    fireEvent.change(end, { target: { value: '18' } });
    expect(onChange).toHaveBeenCalledWith(8, 18);
  });
});
