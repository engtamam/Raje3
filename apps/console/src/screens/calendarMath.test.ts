import { describe, expect, it } from 'vitest';
import { addDaysCal, addMonths, addYears, daysInMonth, monthGrid, startOfMonth, startOfYear } from './calendarMath';

describe('calendarMath — real calendar arithmetic, no manual day-drift', () => {
  it('addMonths crosses a year boundary correctly', () => {
    expect(addMonths('2026-12-15', 1)).toBe('2027-01-01');
    expect(addMonths('2026-01-15', -1)).toBe('2025-12-01');
  });

  it('addMonths lands on the 1st regardless of the day it started from', () => {
    expect(addMonths('2026-01-31', 1)).toBe('2026-02-01');
  });

  it('addYears keeps the month, changes only the year', () => {
    expect(addYears('2026-06-10', 1)).toBe('2027-06-01');
  });

  it('startOfMonth/startOfYear clamp to the 1st', () => {
    expect(startOfMonth('2026-08-16')).toBe('2026-08-01');
    expect(startOfYear('2026-08-16')).toBe('2026-01-01');
  });

  it('daysInMonth is correct across a leap and a non-leap February', () => {
    expect(daysInMonth(2024, 2)).toBe(29);   // leap
    expect(daysInMonth(2026, 2)).toBe(28);   // not leap
    expect(daysInMonth(2026, 4)).toBe(30);
  });

  it('addDaysCal crosses a month boundary without drifting', () => {
    expect(addDaysCal('2026-01-31', 1)).toBe('2026-02-01');
  });

  it('monthGrid is always a whole number of 7-day weeks, in-month days flagged correctly', () => {
    const cells = monthGrid('2026-08-01');
    expect(cells.length % 7).toBe(0);
    const inMonth = cells.filter((c) => c.inMonth);
    expect(inMonth.length).toBe(31);   // August has 31 days
    expect(inMonth[0]!.date).toBe('2026-08-01');
    expect(inMonth[inMonth.length - 1]!.date).toBe('2026-08-31');
  });

  it('monthGrid pads a February that needs only 4 weeks, or a month that needs 6', () => {
    const feb2026 = monthGrid('2026-02-01');   // 2026-02-01 is a Sunday, 28 days -> exactly 4 weeks
    expect(feb2026.length).toBe(28);
    expect(feb2026.every((c) => c.inMonth)).toBe(true);
  });
});
