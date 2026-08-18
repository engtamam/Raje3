/**
 * الحجوزات — Stage 6 (docs/خطة-تنفيذ-الحجوزات.md §6): the catalogue link, the booking dialog,
 * and the day's grid, READ-ONLY in its layout. Drag-and-drop and live colouring while dragging
 * are Stage 7's, on the exact same routes this screen already calls.
 *
 * ONE BRANCH, ALWAYS. Unlike a dashboard that can sum several branches into one number, a day's
 * appointments belong to exactly one place — so this screen, alone among the rail's sections,
 * needs the shell's shared branch scope to resolve to a SINGLE id before it can ask anything.
 * A single-branch shop never sees a chooser (`branches.length === 1` picks it silently); a
 * multi-branch one not yet narrowed sees the same «اختر فرعاً» prompt «محلّي» already uses —
 * the SAME choice the rail holds, never a private one (see Local.tsx's own comment on this).
 */
import { useCallback, useEffect, useMemo, useState } from 'react';
import { Badge } from '@base-ui/design-system/Badge';
import { Button } from '@base-ui/design-system/Button';
import { EmptyState } from '@base-ui/design-system/EmptyState';
import { Skeleton } from '@base-ui/design-system/Skeleton';
import { ChevronLeft, ChevronRight, Plus } from 'lucide-react';
import {
  ApiError, attendBooking, cancelBooking, listBookings, noShowBooking, sentenceFor,
  type Booking, type CatalogueService, type FieldOperator, fetchCatalogue, listBookingStaff,
} from '../api';
import type { ScopeBranch } from '../branch-scope';
import type { Session } from '../session';
import { BookingDialog } from './BookingDialog';

/** «اليوم» بتوقيت المحل، لا بتوقيت الجهاز المتصفَّح منه — والفارق حقيقي عابر منتصف الليل. */
function todayLocal(): string {
  const now = new Date();
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')}`;
}

function addDays(date: string, delta: number): string {
  const [y, m, d] = date.split('-').map(Number);
  const dt = new Date(Date.UTC(y, m - 1, d));
  dt.setUTCDate(dt.getUTCDate() + delta);
  return `${dt.getUTCFullYear()}-${String(dt.getUTCMonth() + 1).padStart(2, '0')}-${String(dt.getUTCDate()).padStart(2, '0')}`;
}

const WEEKDAYS = ['الأحد', 'الاثنين', 'الثلاثاء', 'الأربعاء', 'الخميس', 'الجمعة', 'السبت'];
const MONTHS = ['يناير', 'فبراير', 'مارس', 'أبريل', 'مايو', 'يونيو',
               'يوليو', 'أغسطس', 'سبتمبر', 'أكتوبر', 'نوفمبر', 'ديسمبر'];

function humanDate(date: string): string {
  const [y, m, d] = date.split('-').map(Number);
  const dt = new Date(Date.UTC(y, m - 1, d));
  return `${WEEKDAYS[dt.getUTCDay()]} ${d} ${MONTHS[m - 1]}`;
}

function timeOf(epoch: number): string {
  const d = new Date(epoch * 1000);
  const h = d.getHours();
  const h12 = h % 12 || 12;
  return `${h12}:${String(d.getMinutes()).padStart(2, '0')} ${h >= 12 ? 'م' : 'ص'}`;
}

const STATUS_LABEL: Record<Booking['status'], string> = {
  booked: 'محجوز', attended: 'حضرت', no_show: 'لم تحضر', cancelled: 'ملغى',
};
const STATUS_TONE: Record<Booking['status'], 'accent' | 'success' | 'warning' | 'neutral'> = {
  booked: 'accent', attended: 'success', no_show: 'warning', cancelled: 'neutral',
};

export interface BookingsScreenProps {
  session: Session;
  branch: string;
  branches: ScopeBranch[];
  onBranch: (id: string) => void;
}

export function BookingsScreen({ session, branch, branches, onBranch }: BookingsScreenProps) {
  // ONE BRANCH IS NO CHOICE (canSwitch's own rule, mirrored) — a single-branch shop is never
  // asked to pick the branch it already only has.
  const activeBranch = branch || (branches.length === 1 ? branches[0].id : '');

  const [date, setDate] = useState(todayLocal);
  const [rows, setRows] = useState<Booking[] | null>(null);
  const [failed, setFailed] = useState(false);
  const [services, setServices] = useState<CatalogueService[]>([]);
  const [staff, setStaff] = useState<FieldOperator[]>([]);
  const [creating, setCreating] = useState(false);
  const [note, setNote] = useState<string | null>(null);
  const [acting, setActing] = useState('');

  const load = useCallback(() => {
    if (!activeBranch) return;
    setRows(null);
    setFailed(false);
    listBookings(session, activeBranch, date)
      .then((r) => setRows(r.bookings))
      .catch(() => { setRows(null); setFailed(true); });
  }, [session, activeBranch, date]);

  useEffect(() => { load(); }, [load]);

  // THE CATALOGUE AND THE TEAM, ONCE — the same two reads the visit screen makes, reused rather
  // than re-fetched by the dialog every time it opens.
  useEffect(() => {
    fetchCatalogue(session).then((r) => setServices(r.services)).catch(() => setServices([]));
    listBookingStaff(session).then(setStaff).catch(() => setStaff([]));
  }, [session]);

  // THIS BRANCH'S TEAM ONLY. `listBookingStaff` returns every branch this caller may see —
  // operations scopes it to the READER, not to one branch — so a chain with several branches
  // would otherwise offer a Riyadh operator on a Jeddah booking. Unbranched operators stay
  // visible everywhere, the same rule operations' own staff route documents.
  const staffHere = useMemo(
    () => staff.filter((o) => !o.branch_id || o.branch_id === activeBranch),
    [staff, activeBranch],
  );
  const nameOf = useMemo(() => {
    const m = new Map(staff.map((o) => [o.id, o.name]));
    return (id: string) => m.get(id) || id;
  }, [staff]);
  const serviceNameOf = useMemo(() => {
    const m = new Map(services.map((s) => [s.id, s.name]));
    return (ids: string[]) => ids.map((id) => m.get(id) || id).join('، ');
  }, [services]);

  const sorted = useMemo(
    () => (rows ?? []).slice().sort((a, b) => a.starts_at - b.starts_at),
    [rows],
  );

  const say = (text: string) => { setNote(text); window.setTimeout(() => setNote(null), 3000); };

  const act = useCallback(async (
    booking: Booking, fn: (s: Session, id: string) => Promise<Booking>, doneMsg: string,
  ) => {
    setActing(booking.id);
    try {
      const updated = await fn(session, booking.id);
      setRows((cur) => (cur ?? []).map((b) => (b.id === updated.id ? updated : b)));
      say(doneMsg);
    } catch (e) {
      say(sentenceFor(e, 'تعذّر تنفيذ الإجراء.'));
    } finally {
      setActing('');
    }
  }, [session]);

  // ── لا فرع مُختار بعد ─────────────────────────────────────────────────────────────────────
  if (!activeBranch) {
    if (branches.length === 0) {
      return <div className="p-4"><EmptyState title="لا فروع بعد" description="أضف فرعاً من «حسابي»." /></div>;
    }
    return (
      <div className="flex flex-col items-center gap-3 p-4">
        <EmptyState title="اختر فرعاً" description="الحجوزات تُعرض لفرعٍ واحد في كل مرة." />
        <div className="flex flex-wrap items-center justify-center gap-2">
          {branches.map((b) => (
            <button
              key={b.id}
              type="button"
              onClick={() => onBranch(b.id)}
              className="rounded-full bg-surface-2 px-3 py-1 text-sm text-text-secondary"
            >
              {b.name || b.id}
            </button>
          ))}
        </div>
      </div>
    );
  }

  return (
    <main className="bg-surface-0 text-text-primary">
      <div className="mx-auto flex max-w-3xl flex-col gap-4 p-4">
        {/* ── شريط التاريخ ───────────────────────────────────────────────────────────────── */}
        <div className="flex items-center justify-between gap-2">
          <button
            type="button"
            onClick={() => setDate((d) => addDays(d, -1))}
            aria-label="اليوم السابق"
            className="grid h-10 w-10 place-items-center rounded-xl bg-surface-1 shadow-sm"
          >
            <ChevronRight size={18} aria-hidden />
          </button>
          <div className="flex flex-col items-center">
            <span className="text-lg font-semibold">{humanDate(date)}</span>
            {date !== todayLocal() ? (
              <button type="button" onClick={() => setDate(todayLocal())}
                     className="text-xs text-accent">
                اليوم
              </button>
            ) : null}
          </div>
          <button
            type="button"
            onClick={() => setDate((d) => addDays(d, 1))}
            aria-label="اليوم التالي"
            className="grid h-10 w-10 place-items-center rounded-xl bg-surface-1 shadow-sm"
          >
            <ChevronLeft size={18} aria-hidden />
          </button>
        </div>

        {branches.length > 1 ? (
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-xs text-text-secondary">الفرع:</span>
            {branches.map((b) => (
              <button
                key={b.id}
                type="button"
                onClick={() => onBranch(b.id)}
                className={`rounded-full px-3 py-1 text-xs ${b.id === activeBranch
                  ? 'bg-accent text-white' : 'bg-surface-2 text-text-secondary'}`}
              >
                {b.name || b.id}
              </button>
            ))}
          </div>
        ) : null}

        {note ? (
          <div className="rounded-xl bg-accent-soft px-3 py-2 text-sm text-accent-on-soft">
            {note}
          </div>
        ) : null}

        {/* ── الجدول ─────────────────────────────────────────────────────────────────────── */}
        {rows === null && !failed ? (
          <div className="flex flex-col gap-2">
            <Skeleton height={64} /><Skeleton height={64} /><Skeleton height={64} />
          </div>
        ) : failed ? (
          <EmptyState title="تعذّر قراءة الحجوزات" description="حاول بعد قليل." />
        ) : sorted.length === 0 ? (
          <EmptyState title="لا حجوزات هذا اليوم" description="اضغط «حجز جديد» لإضافة أول حجز." />
        ) : (
          <ul className="flex flex-col gap-2">
            {sorted.map((b) => (
              <li key={b.id}
                 className="flex flex-col gap-2 rounded-2xl bg-surface-1 p-3 shadow-sm sm:flex-row sm:items-center sm:justify-between">
                <div className="flex flex-col gap-0.5">
                  <div className="flex items-center gap-2">
                    <span dir="ltr" className="tabular-nums text-lg font-semibold">
                      {timeOf(b.starts_at)}
                    </span>
                    <Badge tone={STATUS_TONE[b.status]}>{STATUS_LABEL[b.status]}</Badge>
                  </div>
                  <span className="text-sm text-text-secondary">
                    {serviceNameOf(b.service_ids) || '—'} · {nameOf(b.operator_id)}
                  </span>
                  {b.note ? <span className="text-xs text-text-secondary">{b.note}</span> : null}
                </div>

                {b.status === 'booked' ? (
                  <div className="flex shrink-0 flex-wrap gap-2">
                    <Button
                      variant="ghost"
                      disabled={acting === b.id}
                      onClick={() => act(b, attendBooking, 'سُجّل الحضور ✓')}
                    >
                      حضرت
                    </Button>
                    <Button
                      variant="ghost"
                      disabled={acting === b.id}
                      onClick={() => act(b, (s, id) => noShowBooking(s, id), 'سُجّل عدم الحضور')}
                    >
                      لم تحضر
                    </Button>
                    <Button
                      variant="ghost"
                      disabled={acting === b.id}
                      onClick={() => act(b, (s, id) => cancelBooking(s, id), 'أُلغي الحجز')}
                    >
                      إلغاء
                    </Button>
                  </div>
                ) : null}
              </li>
            ))}
          </ul>
        )}

        <button
          type="button"
          onClick={() => setCreating(true)}
          className="fixed bottom-6 inset-inline-end-6 flex h-14 items-center gap-2 rounded-full bg-accent px-5 text-base font-bold text-white shadow-lg active:scale-[0.98]"
        >
          <Plus size={20} aria-hidden />
          حجز جديد
        </button>
      </div>

      {creating ? (
        <BookingDialog
          session={session}
          branchId={activeBranch}
          date={date}
          services={services}
          staff={staffHere}
          onClose={() => setCreating(false)}
          onCreated={(b) => {
            setCreating(false);
            setRows((cur) => [...(cur ?? []), b]);
            say('تم الحجز ✓');
          }}
        />
      ) : null}
    </main>
  );
}
