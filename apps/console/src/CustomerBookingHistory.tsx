/**
 * "Their upcoming and past appointments, and their attendance rate" — the customer-page section
 * the bookings plan named from the start and never got built (see the bookings app's own
 * description doc, §3). Mounted straight into the customer screen's own overview, same
 * precedent as `TodayBookingsStrip` inside Visit.tsx: no entitlement check of its own — a shop
 * that never bought bookings gets `bookings: []` or a failed read either way, and both render
 * nothing. The licence gate lives once, in `bookings.read`'s own capability check on the server.
 */
import { useEffect, useState } from 'react';
import { bookingsForCustomer, type Booking } from './api';
import type { Session } from './session';
import { useOperatorI18n, tf } from './operator-i18n';
import './screens/bookings-i18n';
import './customer-booking-history-i18n';

function fmtDate(epoch: number): string {
  const d = new Date(epoch * 1000);
  return `${d.getDate()}/${d.getMonth() + 1}`;
}
function fmtTime(epoch: number, t: (key: string) => string): string {
  const d = new Date(epoch * 1000);
  const h = d.getHours();
  const h12 = h % 12 || 12;
  return `${h12}:${String(d.getMinutes()).padStart(2, '0')} ${h >= 12 ? t('bookings.pm') : t('bookings.am')}`;
}

const STATUS_KEY: Record<Booking['status'], string> = {
  booked: 'bookings.status.booked', attended: 'bookings.status.attended',
  no_show: 'bookings.status.noShow', cancelled: 'bookings.status.cancelled',
};
const STATUS_CLASS: Record<Booking['status'], string> = {
  booked: 'text-accent', attended: 'text-success', no_show: 'text-danger',
  cancelled: 'text-text-muted',
};

export function CustomerBookingHistory({ session, customerId }: {
  session: Session; customerId: string;
}) {
  const { t } = useOperatorI18n();
  // undefined = still loading (renders nothing meanwhile, no skeleton worth the flash for a
  // section that may end up empty anyway); null = the read failed OR this shop has no bookings
  // app — both render the same nothing, on purpose (see the module doc above).
  const [rows, setRows] = useState<Booking[] | null | undefined>(undefined);

  useEffect(() => {
    let stale = false;
    bookingsForCustomer(session, customerId)
      .then((r) => { if (!stale) setRows(r.bookings); })
      .catch(() => { if (!stale) setRows(null); });
    return () => { stale = true; };
  }, [session, customerId]);

  if (!rows || rows.length === 0) return null;

  const now = Math.floor(Date.now() / 1000);
  const upcoming = rows
    .filter((b) => b.status === 'booked' && b.starts_at >= now)
    .sort((a, b) => a.starts_at - b.starts_at);
  const past = rows
    .filter((b) => !(b.status === 'booked' && b.starts_at >= now))
    .sort((a, b) => b.starts_at - a.starts_at);
  // ATTENDANCE RATE — from CLOSED appointments only (attended/no-show); booked and cancelled
  // are not an attendance outcome.
  const closed = rows.filter((b) => b.status === 'attended' || b.status === 'no_show');
  const rate = closed.length > 0
    ? Math.round((closed.filter((b) => b.status === 'attended').length / closed.length) * 100)
    : null;

  return (
    <div className="rounded-card bg-surface-1 p-4">
      <div className="mb-3 flex items-center justify-between">
        <h3 className="text-sm font-semibold text-text-primary">{t('customerBookingHistory.title')}</h3>
        {rate !== null ? (
          <span className="text-xs text-text-secondary">{tf(t, 'customerBookingHistory.attendanceRate', { rate })}</span>
        ) : null}
      </div>
      {upcoming.length > 0 ? (
        <div className="mb-3 flex flex-col gap-1">
          <p className="text-xs font-semibold text-text-secondary">{t('customerBookingHistory.upcoming')}</p>
          {upcoming.map((b) => (
            <div key={b.id} className="flex items-center justify-between rounded-xl bg-surface-2 px-3 py-2 text-sm">
              <span>{fmtDate(b.starts_at)} — {fmtTime(b.starts_at, t)}</span>
              <span className={STATUS_CLASS[b.status]}>{t(STATUS_KEY[b.status])}</span>
            </div>
          ))}
        </div>
      ) : null}
      {past.length > 0 ? (
        <div className="flex flex-col gap-1">
          <p className="text-xs font-semibold text-text-secondary">{t('customerBookingHistory.past')}</p>
          {past.slice(0, 10).map((b) => (
            <div key={b.id} className="flex items-center justify-between rounded-xl px-3 py-1.5 text-sm">
              <span className="text-text-secondary">{fmtDate(b.starts_at)}</span>
              <span className={STATUS_CLASS[b.status]}>{t(STATUS_KEY[b.status])}</span>
            </div>
          ))}
        </div>
      ) : null}
    </div>
  );
}
