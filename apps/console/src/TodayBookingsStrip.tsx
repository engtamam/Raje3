/**
 * Today's bookings strip — Stage 9 (docs/وصف-تطبيق-الحجوزات.md §6.3): "لا شاشة جديدة", a strip
 * ABOVE the existing field screen, so the operator taps "حضر" instead of hunting for the
 * customer she already knows is coming.
 *
 * ONE TAP IS THE VISIT. "حضر" here calls the same `attendBooking` the grid's own action sheet
 * calls — the booking->visit gateway (Stage 4) creates the Visit directly, so this is FASTER than
 * "opens the visit form pre-filled" would have been, not merely equivalent to it: nothing left to
 * confirm, because everything the visit needs (customer, services, operator) was already decided
 * when the booking was made.
 *
 * NOT THE GRID'S OWN VISUAL IDENTITY. This is a strip inside the ordinary field screen, which is
 * not the one screen carrying its own look (that treatment was approved as scoped to the
 * bookings grid alone) — so this renders in the console's standard palette.
 */
import { useEffect, useMemo, useState } from 'react';
import { Check } from 'lucide-react';
import {
  attendBooking, type Booking, type CatalogueService, listBookings, listBookingStaff,
  sentenceFor, type FieldOperator,
} from './api';
import type { Session } from './session';
import { useOperatorI18n } from './operator-i18n';
import { Card } from './rj-ui/Card';
import './today-bookings-strip-i18n';

export interface TodayBookingsStripProps {
  session: Session;
  branchId: string;
  services: CatalogueService[];
}

function todayLocal(): string {
  const now = new Date();
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')}`;
}
function timeOf(epoch: number, t: (key: string) => string): string {
  const d = new Date(epoch * 1000);
  const h = d.getHours();
  const h12 = h % 12 || 12;
  return `${h12}:${String(d.getMinutes()).padStart(2, '0')} ${h >= 12 ? t('todayBookings.pm') : t('todayBookings.am')}`;
}

export function TodayBookingsStrip({ session, branchId, services }: TodayBookingsStripProps) {
  const { t } = useOperatorI18n();
  // undefined = «not loaded yet» (nothing rendered); null = «the read failed» — distinct from an
  // ordinary empty day, because an empty strip on a failed read reads as «nobody is coming», and
  // an operator told that stops chasing the people who actually are.
  const [rows, setRows] = useState<Booking[] | null | undefined>(undefined);
  const [staff, setStaff] = useState<FieldOperator[] | null | undefined>(undefined);
  const [busy, setBusy] = useState('');
  const [note, setNote] = useState('');

  useEffect(() => {
    if (!branchId) { setRows(undefined); return; }
    listBookings(session, branchId, todayLocal())
      .then((r) => setRows(r.bookings.filter((b) => b.status === 'booked')))
      .catch(() => setRows(null));
    listBookingStaff(session).then(setStaff).catch(() => setStaff(null));
  }, [session, branchId]);

  const nameOf = useMemo(() => {
    const m = new Map((staff ?? []).map((o) => [o.id, o.name]));
    return (id: string) => m.get(id) || id;
  }, [staff]);
  const serviceNameOf = useMemo(() => {
    const m = new Map(services.map((s) => [s.id, s.name]));
    return (ids: string[]) => ids.map((id) => m.get(id) || id).join(t('todayBookings.listSeparator'));
  }, [services, t]);

  const sorted = useMemo(
    () => (rows ?? []).slice().sort((a, b) => a.starts_at - b.starts_at),
    [rows],
  );

  const attend = async (b: Booking) => {
    setBusy(b.id);
    try {
      await attendBooking(session, b.id);
      setRows((cur) => (cur ?? []).filter((x) => x.id !== b.id));
      setNote(t('todayBookings.attended'));
      window.setTimeout(() => setNote(''), 2500);
    } catch (e) {
      setNote(sentenceFor(e, t('todayBookings.attendFailed')));
      window.setTimeout(() => setNote(''), 4000);
    } finally {
      setBusy('');
    }
  };

  // A FAILED READ SAYS SO — an empty strip here reads as «nobody is coming today», which is a
  // different claim than «we could not check». Only THIS gets a visible line; a day that loaded
  // fine and genuinely has no bookings still renders nothing (see below).
  if (rows === null) {
    return (
      <p className="mb-3 text-sm text-danger">{t('todayBookings.readFailed')}</p>
    );
  }

  // NOTHING TODAY, NOTHING SHOWN — an empty strip above the field screen is a row of blank space
  // on the screen used a hundred times a day, for a day that genuinely has no bookings (or has not
  // loaded yet).
  if (!branchId || sorted.length === 0) return null;

  return (
    <div className="mb-3 flex flex-col gap-2">
      {note ? <p className="text-sm text-accent">{note}</p> : null}
      <div className="flex gap-2 overflow-x-auto pb-1">
        {sorted.map((b) => (
          <Card key={b.id}
              className="flex shrink-0 items-center gap-2 px-3 py-2">
            <div className="flex flex-col leading-tight">
              <span className="text-xs font-semibold tabular-nums">{timeOf(b.starts_at, t)}</span>
              <span className="text-xs text-text-secondary">
                {nameOf(b.operator_id)} · {serviceNameOf(b.service_ids) || '—'}
              </span>
            </div>
            <button
              type="button"
              disabled={busy === b.id}
              onClick={() => attend(b)}
              aria-label={t('todayBookings.attend')}
              className="grid h-9 w-9 shrink-0 place-items-center rounded-full bg-accent-soft text-accent-on-soft disabled:opacity-50"
            >
              <Check size={16} aria-hidden />
            </button>
          </Card>
        ))}
      </div>
    </div>
  );
}
