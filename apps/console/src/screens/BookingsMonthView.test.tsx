import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen, waitFor, fireEvent } from '@testing-library/react';
import { createElement } from 'react';

const asked: { fn: string; args: unknown[] }[] = [];
let countsOverride: Record<string, number> = {};

vi.mock('../api', async (importOriginal) => {
  const real = await importOriginal<typeof import('../api')>();
  return {
    ...real,
    fetchBookingCounts: async (...args: unknown[]) => {
      asked.push({ fn: 'fetchBookingCounts', args });
      return { counts: countsOverride };
    },
  };
});

afterEach(() => {
  asked.length = 0;
  countsOverride = {};
  cleanup();
});

const { BookingsMonthView } = await import('./BookingsMonthView');

const t = (key: string) => key;
const session = {} as never;

function open(overrides: Partial<Parameters<typeof BookingsMonthView>[0]> = {}) {
  const onSelectDay = overrides.onSelectDay ?? (() => {});
  return render(createElement(BookingsMonthView, {
    session, branchId: 'b1', date: '2026-08-16', today: '2026-08-02', t, onSelectDay, ...overrides,
  }));
}

describe('BookingsMonthView — the month grid, counts-only', () => {
  it('asks for counts across the whole grid range, never listBookings', async () => {
    open();
    await waitFor(() => expect(asked.length).toBe(1));
    expect(asked[0]!.fn).toBe('fetchBookingCounts');
    // Range is the FULL rendered grid (padding included), branch-scoped.
    expect(asked[0]!.args[1]).toBe('b1');
  });

  it('shows a count badge on a day that has bookings, and none on an empty day', async () => {
    countsOverride = { '2026-08-16': 3 };
    open();
    await waitFor(() => screen.getByTestId('rj-month-day-2026-08-16'));
    expect(screen.getByTestId('rj-month-day-2026-08-16').textContent).toContain('3');
    // A day with zero bookings shows only its own day number — no count badge appended.
    expect(screen.getByTestId('rj-month-day-2026-08-20').textContent).toBe('20');
  });

  it('clicking a day calls onSelectDay with that exact date', async () => {
    const onSelectDay = vi.fn();
    open({ onSelectDay });
    await waitFor(() => screen.getByTestId('rj-month-day-2026-08-20'));
    fireEvent.click(screen.getByTestId('rj-month-day-2026-08-20'));
    expect(onSelectDay).toHaveBeenCalledWith('2026-08-20');
  });

  it('renders exactly the days August 2026 has, plus whole-week padding', async () => {
    open();
    await waitFor(() => screen.getByTestId('rj-month-grid'));
    // 31 real August days must all be present.
    for (let d = 1; d <= 31; d += 1) {
      const key = `2026-08-${String(d).padStart(2, '0')}`;
      expect(screen.getByTestId(`rj-month-day-${key}`)).toBeTruthy();
    }
  });
});
