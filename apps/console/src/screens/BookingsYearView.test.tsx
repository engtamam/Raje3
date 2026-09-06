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

const { BookingsYearView } = await import('./BookingsYearView');

const t = (key: string) => key;
const session = {} as never;

function open(overrides: Partial<Parameters<typeof BookingsYearView>[0]> = {}) {
  return render(createElement(BookingsYearView, {
    session, branchId: 'b1', date: '2026-08-16', today: '2026-08-02', t,
    onSelectDay: () => {}, onSelectMonth: () => {}, ...overrides,
  }));
}

describe('BookingsYearView — 12 mini-months in one fetch', () => {
  it('fetches counts exactly once for the whole year, never per month', async () => {
    open();
    await waitFor(() => expect(asked.length).toBe(1));
    expect(asked[0]!.fn).toBe('fetchBookingCounts');
    expect(asked[0]!.args[2]).toBe('2026-01-01');   // range starts at Jan 1st of that year
  });

  it('draws 12 mini-calendars, one per month of the year', async () => {
    open();
    await waitFor(() => screen.getByTestId('rj-year-grid'));
    for (let m = 1; m <= 12; m += 1) {
      const monthStart = `2026-${String(m).padStart(2, '0')}-01`;
      expect(screen.getByTestId(`rj-year-month-${monthStart}`)).toBeTruthy();
    }
  });

  it('clicking a month label calls onSelectMonth with that month\'s own start date', async () => {
    const onSelectMonth = vi.fn();
    open({ onSelectMonth });
    await waitFor(() => screen.getByTestId('rj-year-month-2026-03-01'));
    fireEvent.click(screen.getByTestId('rj-year-month-2026-03-01'));
    expect(onSelectMonth).toHaveBeenCalledWith('2026-03-01');
  });

  it('clicking a day inside a mini-month calls onSelectDay with that exact date', async () => {
    const onSelectDay = vi.fn();
    open({ onSelectDay });
    await waitFor(() => screen.getByTestId('rj-year-day-2026-03-10'));
    fireEvent.click(screen.getByTestId('rj-year-day-2026-03-10'));
    expect(onSelectDay).toHaveBeenCalledWith('2026-03-10');
  });
});
