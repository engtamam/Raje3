/**
 * Real calendar math for the month/year views (docs/خطة-تصميم-تقويم-الحجوزات.md §2) — "the
 * existing `addDays`/ما يعادلها بمنطق شهر/سنة حقيقي". `Bookings.tsx`'s own `addDays` stays
 * untouched (day/week nav is not to be touched at all); this is a SEPARATE, additive set of
 * helpers for the two new views and the nav unit they add, all in UTC-anchored `Date` objects so
 * a month boundary (28/29/30/31 days) or a year boundary never drifts the way manual
 * day-arithmetic would.
 *
 * Every date here is `YYYY-MM-DD`, the shop's own business-day string — the same shape
 * `day_bucket()` produces server-side and every other date helper in this screen already uses.
 */

function parts(date: string): [number, number, number] {
  const [y, m, d] = date.split('-').map(Number);
  return [y, m, d];
}
function fmt(dt: Date): string {
  return `${dt.getUTCFullYear()}-${String(dt.getUTCMonth() + 1).padStart(2, '0')}-${String(dt.getUTCDate()).padStart(2, '0')}`;
}

/** Same day, `delta` days later (or earlier) — a local copy of `Bookings.tsx`'s own `addDays`,
 *  kept separate on purpose (see file header). */
export function addDaysCal(date: string, delta: number): string {
  const [y, m, d] = parts(date);
  const dt = new Date(Date.UTC(y, m - 1, d));
  dt.setUTCDate(dt.getUTCDate() + delta);
  return fmt(dt);
}

/** The first of `date`'s own month. */
export function startOfMonth(date: string): string {
  const [y, m] = parts(date);
  return `${y}-${String(m).padStart(2, '0')}-01`;
}

/** `date`'s own month, `delta` months later (or earlier) — clamped to the 1st, since a month
 *  view only ever cares which month it is, never which day within it. */
export function addMonths(date: string, delta: number): string {
  const [y, m] = parts(date);
  const dt = new Date(Date.UTC(y, m - 1 + delta, 1));
  return fmt(dt);
}

/** January 1st of `date`'s own year. */
export function startOfYear(date: string): string {
  const [y] = parts(date);
  return `${y}-01-01`;
}

/** `date`'s own year, `delta` years later (or earlier). */
export function addYears(date: string, delta: number): string {
  const [y, m] = parts(date);
  const dt = new Date(Date.UTC(y + delta, m - 1, 1));
  return fmt(dt);
}

/** How many days `y`-`m` (1-based month) has — the one fact manual day-arithmetic gets wrong at
 *  a month boundary. */
export function daysInMonth(y: number, m: number): number {
  return new Date(Date.UTC(y, m, 0)).getUTCDate();
}

/** `date.weekday()`'s own numbering is Monday-first; the calendar GRID is Sunday-first (same
 *  convention `Bookings.tsx`'s own `startOfWeek` already uses) — plain `Date#getUTCDay()`. */
function dow(date: string): number {
  const [y, m, d] = parts(date);
  return new Date(Date.UTC(y, m - 1, d)).getUTCDay();
}

export interface MonthCell {
  date: string;
  day: number;
  inMonth: boolean;
}

/** A full 7×5-or-6 grid for `monthStart` (the 1st of the month) — leading days from the previous
 *  month and trailing days from the next fill out whole weeks, so the grid is always a clean
 *  rectangle, `inMonth: false` marking the padding on either side. */
export function monthGrid(monthStart: string): MonthCell[] {
  const [y, m] = parts(monthStart);
  const leading = dow(monthStart);
  const total = daysInMonth(y, m);
  const rows = Math.ceil((leading + total) / 7);
  const gridStart = addDaysCal(monthStart, -leading);
  return Array.from({ length: rows * 7 }, (_, i) => {
    const date = addDaysCal(gridStart, i);
    return { date, day: Number(date.split('-')[2]), inMonth: date.slice(0, 7) === monthStart.slice(0, 7) };
  });
}
