/**
 * Month view (see the calendar design doc, §2) — a 7×5/6 grid, each day cell showing the day
 * number and a real booking-COUNT indicator, never details. Fed only by `/bookings/counts`
 * (`fetchBookingCounts`) — the SAME lesson the backend side of this plan already paid for on the
 * affiliate side of this codebase: a screen that only needs a number per day must never pull a
 * hydrated row per booking to get it.
 *
 * VISUAL LANGUAGE MATCHES THIS SESSION'S OWN PREMIUM CARD (`PackagesTab.tsx`, `Services.tsx`'s
 * grid): `rounded-2xl`, a real hover lift (`hover:-translate-y-0.5` + a deeper shadow) on a
 * clickable day, and a leading info-gradient strip on today's own cell — informational (which day
 * is today), not a call to action, so it stays on the `info` semantic token, never `accent`.
 *
 * Does NOT touch day/week's own grid, state, or visual identity — a sibling component, not a
 * variant of it.
 */
import { useEffect, useMemo, useState } from 'react';
import { fetchBookingCounts } from '../api';
import type { Session } from '../session';
import { monthGrid, startOfMonth } from './calendarMath';

type T = (key: string) => string;

export interface BookingsMonthViewProps {
  session: Session;
  branchId: string;
  /** Any date within the month to show — only its year/month matter. */
  date: string;
  today: string;
  t: T;
  onSelectDay: (date: string) => void;
}

const weekdayLabel = (t: T, dow: number) => t(`bookings.weekday.${dow}`);

export function BookingsMonthView({ session, branchId, date, today, t, onSelectDay }: BookingsMonthViewProps) {
  const monthStart = startOfMonth(date);
  const cells = useMemo(() => monthGrid(monthStart), [monthStart]);
  const rangeStart = cells[0]?.date ?? monthStart;
  const rangeEnd = cells[cells.length - 1]?.date ?? monthStart;

  // undefined = loading, null = failed, {} (or filled) = answered — same three-state convention
  // `rows`/`staff` already use elsewhere in this screen.
  const [counts, setCounts] = useState<Record<string, number> | null | undefined>(undefined);

  useEffect(() => {
    if (!branchId) return;
    setCounts(undefined);
    fetchBookingCounts(session, branchId, rangeStart, rangeEnd)
      .then((r) => setCounts(r.counts))
      .catch(() => setCounts(null));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [session, branchId, rangeStart, rangeEnd]);

  return (
    <div data-testid="rj-month-grid" className="rj-card overflow-hidden rounded-[28px] p-2" style={{ background: 'var(--rj-surface)' }}>
      <div className="grid grid-cols-7 gap-1">
        {Array.from({ length: 7 }, (_, dow) => (
          <div key={dow} className="px-1 py-2 text-center text-xs font-semibold" style={{ color: 'var(--rj-ink-soft)' }}>
            {weekdayLabel(t, dow)}
          </div>
        ))}
        {cells.map((cell) => {
          const isToday = cell.date === today;
          const count = counts == null ? null : (counts[cell.date] ?? 0);
          return (
            <button key={cell.date} type="button" onClick={() => onSelectDay(cell.date)}
                   data-testid={`rj-month-day-${cell.date}`}
                   className={[
                     'group relative flex h-16 flex-col items-center justify-center gap-1 overflow-hidden rounded-2xl',
                     'border transition-all duration-200 hover:-translate-y-0.5 hover:shadow-lg hover:shadow-black/5',
                     cell.inMonth ? 'border-border-subtle bg-surface-1 hover:bg-surface-2' : 'border-transparent opacity-40',
                   ].join(' ')}>
              {isToday ? (
                <span aria-hidden
                     className="pointer-events-none absolute inset-x-0 top-0 h-full bg-gradient-to-b from-info/[0.14] to-transparent" />
              ) : null}
              <span className="relative text-sm font-semibold" style={isToday ? { color: 'var(--rj-info-deep)' } : undefined}>
                {cell.day}
              </span>
              {count === null ? null : count > 0 ? (
                // TINTED, NOT FLAT GREY — this number is not a decoration on the cell, it is the
                // one fact this whole view exists to show: "something is booked here". A neutral
                // the flat neutral surface token badge said the same nothing whether a day held one booking or
                // twenty, no different from the cell's own background; the accent tint (the same
                // one this session's other screens use for "there is real activity here") makes a
                // day WITH bookings visibly distinct from an empty one at a glance, before the
                // digit is even read.
                <span className="relative rounded-full bg-accent-soft px-1.5 py-0.5 text-[10px] font-bold text-accent-on-soft">
                  {count}
                </span>
              ) : (
                <span className="relative h-3" aria-hidden />
              )}
            </button>
          );
        })}
      </div>
    </div>
  );
}
