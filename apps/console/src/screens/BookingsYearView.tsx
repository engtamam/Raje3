/**
 * Year view (docs/خطة-تصميم-تقويم-الحجوزات.md §2) — 12 mini-months, same idea as
 * `BookingsMonthView` at a smaller scale ("زي لقطة المنافس الأولى: 12 تقويماً صغيراً بنقاط"):
 * density DOTS, not numbers — a whole year of numbers in a grid this small is noise, a dot per
 * booked day is the same "something happened here" signal the competitor screenshot showed.
 *
 * ONE FETCH FOR THE WHOLE YEAR, not 12 — `/bookings/counts` is a single cheap index count
 * regardless of range (docs/خطة-تصميم-تقويم-الحجوزات.md §1's whole point), so there is no reason
 * to split it into 12 network round trips just because the screen happens to draw 12 grids.
 *
 * Clicking a day jumps straight to day view; clicking a month's own label switches to month view
 * for that month — two different targets, both reachable from the same mini-calendar.
 */
import { useEffect, useMemo, useState } from 'react';
import { fetchBookingCounts } from '../api';
import type { Session } from '../session';
import { monthGrid, startOfYear, addMonths } from './calendarMath';

type T = (key: string) => string;

export interface BookingsYearViewProps {
  session: Session;
  branchId: string;
  /** Any date within the year to show — only its year matters. */
  date: string;
  today: string;
  t: T;
  onSelectDay: (date: string) => void;
  onSelectMonth: (monthStart: string) => void;
}

const weekdayLetter = (t: T, dow: number) => t(`bookings.weekday.${dow}`).slice(0, 1);
const monthLabel = (t: T, m: number) => t(`bookings.month.${m}`);

export function BookingsYearView({
  session, branchId, date, today, t, onSelectDay, onSelectMonth,
}: BookingsYearViewProps) {
  const yearStart = startOfYear(date);
  const months = useMemo(
    () => Array.from({ length: 12 }, (_, m) => addMonths(yearStart, m)),
    [yearStart],
  );
  const lastMonthCells = useMemo(() => monthGrid(months[11]), [months]);
  const rangeStart = months[0];
  const rangeEnd = lastMonthCells[lastMonthCells.length - 1]?.date ?? months[11];

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
    <div data-testid="rj-year-grid" className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
      {months.map((monthStart, mi) => {
        const cells = monthGrid(monthStart);
        return (
          <div key={monthStart}
              className="group relative flex flex-col gap-2 overflow-hidden rounded-2xl border border-border-subtle bg-surface-1 p-3
                        transition-all duration-200 hover:-translate-y-0.5 hover:shadow-lg hover:shadow-black/5">
            <button type="button" onClick={() => onSelectMonth(monthStart)}
                   data-testid={`rj-year-month-${monthStart}`}
                   className="relative text-start text-sm font-semibold hover:underline"
                   style={{ color: 'var(--rj-ink)' }}>
              {monthLabel(t, mi)}
            </button>
            <div className="relative grid grid-cols-7 gap-0.5">
              {Array.from({ length: 7 }, (_, dow) => (
                <div key={dow} className="text-center text-[9px] font-medium" style={{ color: 'var(--rj-ink-soft)' }}>
                  {weekdayLetter(t, dow)}
                </div>
              ))}
              {cells.map((cell) => {
                const isToday = cell.date === today;
                const count = counts == null ? 0 : (counts[cell.date] ?? 0);
                return (
                  <button key={cell.date} type="button" onClick={() => onSelectDay(cell.date)}
                         data-testid={`rj-year-day-${cell.date}`}
                         className={[
                           'relative flex h-6 flex-col items-center justify-center rounded-md text-[9px] transition-colors',
                           cell.inMonth ? 'hover:bg-surface-2' : 'opacity-30',
                         ].join(' ')}
                         style={isToday ? { background: 'var(--rj-info-soft)', color: 'var(--rj-info-deep)', fontWeight: 700 } : undefined}>
                    {cell.day}
                    {/* THE SAME SIGNAL THE MONTH VIEW GIVES ITS OWN COUNT BADGE, AT DOT SCALE —
                        a neutral `bg-surface-3` dot said nothing more than "not empty", the exact
                        same tone the grid lines around it already carry; the accent dot ties this
                        density map to the one other place in this feature that answers "did
                        anything happen here", so the two screens read as one system rather than
                        two different colour choices for the same fact. */}
                    {count > 0 ? (
                      <span aria-hidden className="absolute bottom-0.5 h-1 w-1 rounded-full bg-accent" />
                    ) : null}
                  </button>
                );
              })}
            </div>
          </div>
        );
      })}
    </div>
  );
}
