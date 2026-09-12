import { describe, expect, it, vi } from 'vitest';
import { render, screen, fireEvent, within } from '@testing-library/react';
import { HourRangePicker } from './HourRangePicker';

describe('rj-ui HourRangePicker', () => {
  it('shows the two hours as western-digit 00:00-shaped buttons', () => {
    render(<HourRangePicker startHour={8} endHour={20} onChange={vi.fn()} fromLabel="من" toLabel="إلى" />);
    const buttons = screen.getAllByRole('button', { name: /من|إلى/ });
    expect(within(buttons[0]).getByText('08:00')).toBeTruthy();
    expect(within(buttons[1]).getByText('20:00')).toBeTruthy();
  });

  it('the end hour list runs through 24 (midnight), the start hour list never reaches it', () => {
    const onChange = vi.fn();
    render(<HourRangePicker startHour={0} endHour={24} onChange={onChange} fromLabel="من" toLabel="إلى" />);
    const [startBtn, endBtn] = screen.getAllByRole('button', { name: /من|إلى/ });
    fireEvent.click(startBtn);
    // THE START LIST STOPS AT 23:00 — its last option (23rd down from 00:00) still reads 23:00,
    // never a wrapped "24".
    const startLastOption = screen.getAllByRole('option').at(-1)!;
    fireEvent.click(startLastOption);
    expect(onChange).toHaveBeenLastCalledWith(23, 24);
    fireEvent.click(endBtn);
    // THE END LIST RUNS ONE HOUR FURTHER — its last option is the true end of the day
    // (`startHour` is the original, un-rewired prop here — this is a static render).
    const endLastOption = screen.getAllByRole('option').at(-1)!;
    fireEvent.click(endLastOption);
    expect(onChange).toHaveBeenLastCalledWith(0, 24);
  });

  it('calls onChange with the new start, keeping the end untouched, and closes the list', () => {
    const onChange = vi.fn();
    render(<HourRangePicker startHour={8} endHour={20} onChange={onChange} fromLabel="من" toLabel="إلى" />);
    const [startBtn] = screen.getAllByRole('button', { name: /من|إلى/ });
    fireEvent.click(startBtn);
    fireEvent.click(screen.getByRole('option', { name: '10:00' }));
    expect(onChange).toHaveBeenCalledWith(10, 20);
    expect(screen.queryByRole('listbox')).toBeNull();
  });

  it('calls onChange with the new end, keeping the start untouched', () => {
    const onChange = vi.fn();
    render(<HourRangePicker startHour={8} endHour={20} onChange={onChange} fromLabel="من" toLabel="إلى" />);
    const [, endBtn] = screen.getAllByRole('button', { name: /من|إلى/ });
    fireEvent.click(endBtn);
    fireEvent.click(screen.getByRole('option', { name: '18:00' }));
    expect(onChange).toHaveBeenCalledWith(8, 18);
  });
});
