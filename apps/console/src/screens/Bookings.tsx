/**
 * Bookings grid (Stage 6 rebuilt + Stage 7, docs/خطة-تنفيذ-الحجوزات.md §6.1/§6.1.1,
 * docs/وصف-تطبيق-الحجوزات.md §6.1/§6.1.1). With Tamam's approval (2026-08-19) this screen alone
 * carries its own visual identity — it does not inherit `@base-ui/design-system` components or
 * colours, and borrows only the brand's own gold, so it stays راجِع rather than a foreign product.
 *
 * A REAL GRID: staff are columns, time is rows, bookings are cards positioned by their actual
 * minute — never a flat list. Empty cells are clickable to start a booking at that exact spot.
 * Drag-and-drop IS the reschedule act (`rescheduleBooking`), built with the grid rather than
 * bolted on later — no confirm dialog, a five-second undo bar instead. On touch
 * (`pointer: coarse`) a real drag fights scrolling, so a long-press opens a "move" mode completed
 * with one tap on the destination cell.
 */
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { ChevronLeft, ChevronRight, Plus, Search, X } from 'lucide-react';
import {
  attendBooking, type Booking, cancelBooking, type CatalogueService,
  fetchCatalogue, type FieldOperator, listBookings, listBookingStaff, noShowBooking,
  rescheduleBooking, sentenceFor,
} from '../api';
import type { ScopeBranch } from '../branch-scope';
import type { Session } from '../session';
import { BookingDialog } from './BookingDialog';

// ── display window and snap ─────────────────────────────────────────────────────────────────
const WINDOW_START = 8 * 60;    // 08:00 — a fixed, reasonable display window; real business
const WINDOW_END = 22 * 60;     // 22:00    hours are wired in later
const WINDOW_LEN = WINDOW_END - WINDOW_START;
const PX_PER_MIN = 1.15;
const SNAP_MINUTES = 15;        // same grain as the conflict lock (Tamam's decision, 2026-08-19)

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
function startOfWeek(date: string): string {
  // Sunday is the first day — same calendar convention the rest of the product uses.
  const [y, m, d] = date.split('-').map(Number);
  const dow = new Date(Date.UTC(y, m - 1, d)).getUTCDay();
  return addDays(date, -dow);
}
const WEEKDAYS = ['الأحد', 'الاثنين', 'الثلاثاء', 'الأربعاء', 'الخميس', 'الجمعة', 'السبت'];
const MONTHS = ['يناير', 'فبراير', 'مارس', 'أبريل', 'مايو', 'يونيو',
               'يوليو', 'أغسطس', 'سبتمبر', 'أكتوبر', 'نوفمبر', 'ديسمبر'];
function humanDate(date: string): string {
  const [y, m, d] = date.split('-').map(Number);
  const dt = new Date(Date.UTC(y, m - 1, d));
  return `${WEEKDAYS[dt.getUTCDay()]} ${d} ${MONTHS[m - 1]}`;
}
function shortDate(date: string): string {
  const [, m, d] = date.split('-').map(Number);
  return `${d} ${MONTHS[m - 1]}`;
}

/** Minutes since local midnight, for positioning a card on the axis. */
function minutesOf(epoch: number): number {
  const d = new Date(epoch * 1000);
  return d.getHours() * 60 + d.getMinutes();
}
function timeLabel(minutes: number): string {
  const h = Math.floor(minutes / 60);
  const m = minutes % 60;
  const h12 = h % 12 || 12;
  return `${h12}:${String(m).padStart(2, '0')} ${h >= 12 ? 'م' : 'ص'}`;
}
/** `date` at the given minute-of-day, in Riyadh — for building a new time on drop without
 *  disturbing the hour the person actually meant. */
function epochAt(date: string, minutes: number): number {
  const [y, m, d] = date.split('-').map(Number);
  const h = Math.floor(minutes / 60);
  const min = minutes % 60;
  return Math.floor(Date.parse(
    `${y}-${String(m).padStart(2, '0')}-${String(d).padStart(2, '0')}T${String(h).padStart(2, '0')}:${String(min).padStart(2, '0')}:00+03:00`,
  ) / 1000);
}
function dateKeyOf(epoch: number): string {
  const d = new Date(epoch * 1000);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
}

const STATUS_LABEL: Record<Booking['status'], string> = {
  booked: 'محجوز', attended: 'حضرت', no_show: 'لم تحضر', cancelled: 'ملغى',
};
const STATUS_VARS: Record<Booking['status'], { fg: string; bg: string }> = {
  booked: { fg: 'var(--rj-booked)', bg: 'var(--rj-booked-soft)' },
  attended: { fg: 'var(--rj-attended)', bg: 'var(--rj-attended-soft)' },
  no_show: { fg: 'var(--rj-noshow)', bg: 'var(--rj-noshow-soft)' },
  cancelled: { fg: 'var(--rj-cancelled)', bg: 'var(--rj-cancelled-soft)' },
};

export interface BookingsScreenProps {
  session: Session;
  branch: string;
  branches: ScopeBranch[];
  onBranch: (id: string) => void;
}

/** What is being dragged right now — the card and its original time/operator, for undo and drop. */
interface DragState {
  booking: Booking;
  fromMinutes: number;
  fromDate: string;
  fromOperator: string;
}

/** The mode a long-press opens on touch — the same act as a drag, with no real drag gesture. */
interface MovingState {
  booking: Booking;
}

/** The undo bar's own memory, five seconds long — never a confirm dialog (§6.1.1). */
interface UndoState {
  bookingId: string;
  previousStartsAt: number;
  previousOperatorId: string;
}

export function BookingsScreen({ session, branch, branches, onBranch }: BookingsScreenProps) {
  const activeBranch = branch || (branches.length === 1 ? branches[0].id : '');

  const [view, setView] = useState<'day' | 'week'>('day');
  const [date, setDate] = useState(todayLocal);
  const [weekStaffId, setWeekStaffId] = useState('');
  const [rows, setRows] = useState<Booking[] | null>(null);
  const [failed, setFailed] = useState(false);
  const [services, setServices] = useState<CatalogueService[]>([]);
  const [staff, setStaff] = useState<FieldOperator[]>([]);
  const [note, setNote] = useState<string | null>(null);
  const [undo, setUndo] = useState<UndoState | null>(null);
  const [search, setSearch] = useState('');

  const [dialog, setDialog] = useState<{ operatorId?: string; startsAt?: number } | 'closed'>('closed');
  const [openBooking, setOpenBooking] = useState<Booking | null>(null);
  const [drag, setDrag] = useState<DragState | null>(null);
  const [dragOver, setDragOver] = useState<{ column: string; minutes: number; valid: boolean } | null>(null);
  const [moving, setMoving] = useState<MovingState | null>(null);
  const longPress = useRef<number | null>(null);

  const say = useCallback((text: string) => {
    setNote(text);
    window.setTimeout(() => setNote((n) => (n === text ? null : n)), 3000);
  }, []);

  // ── the read: one day, or the whole week, depending on the view ────────────────────────────
  const daysToLoad = useMemo(() => {
    if (view === 'day') return [date];
    const start = startOfWeek(date);
    return Array.from({ length: 7 }, (_, i) => addDays(start, i));
  }, [view, date]);

  const load = useCallback(() => {
    if (!activeBranch) return;
    setRows(null);
    setFailed(false);
    Promise.all(daysToLoad.map((d) => listBookings(session, activeBranch, d)))
      .then((answers) => setRows(answers.flatMap((a) => a.bookings)))
      .catch(() => { setRows(null); setFailed(true); });
  }, [session, activeBranch, daysToLoad]);

  useEffect(() => { load(); }, [load]);

  useEffect(() => {
    fetchCatalogue(session).then((r) => setServices(r.services)).catch(() => setServices([]));
    listBookingStaff(session).then(setStaff).catch(() => setStaff([]));
  }, [session]);

  // THIS BRANCH'S TEAM ONLY. `listBookingStaff` returns every branch the caller may see;
  // unbranched operators stay visible everywhere, the same rule operations' own staff route uses.
  const staffHere = useMemo(
    () => staff.filter((o) => !o.branch_id || o.branch_id === activeBranch),
    [staff, activeBranch],
  );
  useEffect(() => {
    if (!weekStaffId && staffHere.length > 0) setWeekStaffId(staffHere[0].id);
  }, [staffHere, weekStaffId]);

  const nameOf = useMemo(() => {
    const m = new Map(staffHere.map((o) => [o.id, o.name]));
    return (id: string) => m.get(id) || id;
  }, [staffHere]);
  const serviceNameOf = useMemo(() => {
    const m = new Map(services.map((s) => [s.id, s.name]));
    return (ids: string[]) => ids.map((id) => m.get(id) || id).join('، ');
  }, [services]);

  const visible = useMemo(() => {
    const q = search.trim();
    if (!q) return rows ?? [];
    return (rows ?? []).filter((b) =>
      serviceNameOf(b.service_ids).includes(q) || nameOf(b.operator_id).includes(q)
      || b.note.includes(q));
  }, [rows, search, serviceNameOf, nameOf]);

  // ── columns: staff in day view, days in week view ───────────────────────────────────────────
  const columns = view === 'day'
    ? staffHere.map((o) => ({ key: o.id, label: o.name, date }))
    : daysToLoad.map((d) => ({ key: d, label: `${WEEKDAYS[new Date(`${d}T00:00:00Z`).getUTCDay()]} ${shortDate(d)}`, date: d }));

  const cardsByColumn = useMemo(() => {
    const map = new Map<string, Booking[]>();
    for (const b of visible) {
      if (b.status === 'cancelled') continue;
      const key = view === 'day' ? b.operator_id : dateKeyOf(b.starts_at);
      if (view === 'week' && b.operator_id !== weekStaffId) continue;
      if (!map.has(key)) map.set(key, []);
      map.get(key)!.push(b);
    }
    return map;
  }, [visible, view, weekStaffId]);

  // ── local conflict check — for the drag colour ONLY; the real check always lives in the
  // backend claim lane, never here.
  const conflicts = useCallback((columnKey: string, minutes: number, durationMinutes: number,
                                 excludeId: string): boolean => {
    const operatorId = view === 'day' ? columnKey : weekStaffId;
    const dayDate = view === 'day' ? date : columnKey;
    const end = minutes + durationMinutes;
    return (rows ?? []).some((b) => {
      if (b.id === excludeId || b.status === 'cancelled' || b.operator_id !== operatorId) return false;
      if (dateKeyOf(b.starts_at) !== dayDate) return false;
      const bStart = minutesOf(b.starts_at);
      const bEnd = bStart + b.duration_minutes;
      return minutes < bEnd && bStart < end;
    });
  }, [rows, view, weekStaffId, date]);

  // ── the drop: the same act as "reschedule", no confirm, a five-second undo bar instead ─────
  const commitMove = useCallback(async (booking: Booking, columnKey: string, minutes: number) => {
    const snapped = Math.round(minutes / SNAP_MINUTES) * SNAP_MINUTES;
    const dayDate = view === 'day' ? date : columnKey;
    const newOperator = view === 'day' ? columnKey : booking.operator_id;
    const startsAt = epochAt(dayDate, snapped);
    if (startsAt === booking.starts_at && newOperator === booking.operator_id) return;

    const previous = { bookingId: booking.id, previousStartsAt: booking.starts_at,
                       previousOperatorId: booking.operator_id };
    // Optimistic, corrected immediately if the server refuses — the real lock is decided there.
    setRows((cur) => (cur ?? []).map((b) => (b.id === booking.id
      ? { ...b, starts_at: startsAt, operator_id: newOperator } : b)));
    try {
      const updated = await rescheduleBooking(session, booking.id, startsAt,
        newOperator !== booking.operator_id ? newOperator : undefined);
      setRows((cur) => (cur ?? []).map((b) => (b.id === updated.id ? updated : b)));
      setUndo(previous);
      window.setTimeout(() => setUndo((u) => (u?.bookingId === previous.bookingId ? null : u)), 5000);
    } catch (e) {
      setRows((cur) => (cur ?? []).map((b) => (b.id === booking.id ? booking : b)));
      say(sentenceFor(e, 'تعذّر نقل الموعد.'));
    }
  }, [session, view, date, say]);

  const undoMove = useCallback(async () => {
    if (!undo) return;
    const { bookingId, previousStartsAt, previousOperatorId } = undo;
    setUndo(null);
    try {
      const updated = await rescheduleBooking(session, bookingId, previousStartsAt, previousOperatorId);
      setRows((cur) => (cur ?? []).map((b) => (b.id === updated.id ? updated : b)));
      say('تراجعنا عن النقل ✓');
    } catch (e) {
      say(sentenceFor(e, 'تعذّر التراجع.'));
    }
  }, [session, undo, say]);

  // ── the long-press on touch — the drag's stand-in, no fragile drag simulation (§6.1.1) ─────
  const onCardPointerDown = (booking: Booking, coarse: boolean) => {
    if (!coarse || booking.status !== 'booked') return;
    longPress.current = window.setTimeout(() => setMoving({ booking }), 450);
  };
  const cancelLongPress = () => {
    if (longPress.current) { window.clearTimeout(longPress.current); longPress.current = null; }
  };

  if (!activeBranch) {
    return (
      <div className="rj-grid flex min-h-dvh flex-col items-center justify-center gap-4 p-6">
        <p className="text-lg font-medium">
          {branches.length === 0 ? 'لا فروع بعد' : 'اختاري فرعاً لعرض جدوله'}
        </p>
        <div className="flex flex-wrap items-center justify-center gap-2">
          {branches.map((b) => (
            <button key={b.id} type="button" onClick={() => onBranch(b.id)}
                   className="rounded-full px-4 py-2 text-sm shadow-sm"
                   style={{ background: 'var(--rj-surface)', color: 'var(--rj-ink)' }}>
              {b.name || b.id}
            </button>
          ))}
        </div>
      </div>
    );
  }

  return (
    <main className="rj-grid min-h-dvh">
      {/* ── header: date, branch, search, day/week ───────────────────────────────────────── */}
      <header className="sticky top-0 z-20 border-b px-4 py-4 backdrop-blur-sm sm:px-6"
             style={{ borderColor: 'var(--rj-line)', background: 'color-mix(in srgb, var(--rj-bg) 92%, transparent)' }}>
        <div className="mx-auto flex max-w-[1400px] flex-col gap-3">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex items-center gap-3">
              <button type="button" onClick={() => setDate((d) => addDays(d, view === 'day' ? -1 : -7))}
                     aria-label="السابق"
                     className="grid h-9 w-9 place-items-center rounded-full shadow-sm transition-transform active:scale-90"
                     style={{ background: 'var(--rj-surface)' }}>
                <ChevronRight size={16} aria-hidden />
              </button>
              <div className="flex flex-col items-center leading-tight">
                <h1 className="text-xl font-semibold tracking-tight">
                  {view === 'day' ? humanDate(date)
                    : `${shortDate(startOfWeek(date))} – ${shortDate(addDays(startOfWeek(date), 6))}`}
                </h1>
                {date !== todayLocal() ? (
                  <button type="button" onClick={() => setDate(todayLocal())}
                         className="text-xs font-medium" style={{ color: 'var(--rj-gold-deep)' }}>
                    العودة لليوم
                  </button>
                ) : null}
              </div>
              <button type="button" onClick={() => setDate((d) => addDays(d, view === 'day' ? 1 : 7))}
                     aria-label="التالي"
                     className="grid h-9 w-9 place-items-center rounded-full shadow-sm transition-transform active:scale-90"
                     style={{ background: 'var(--rj-surface)' }}>
                <ChevronLeft size={16} aria-hidden />
              </button>
            </div>

            <div className="flex items-center gap-1 rounded-full p-1 shadow-sm" style={{ background: 'var(--rj-surface)' }}>
              {(['day', 'week'] as const).map((v) => (
                <button key={v} type="button" onClick={() => setView(v)}
                       className="rounded-full px-4 py-1.5 text-sm font-medium transition-colors"
                       style={v === view
                         ? { background: 'var(--rj-ink)', color: 'var(--rj-bg)' }
                         : { color: 'var(--rj-ink-soft)' }}>
                  {v === 'day' ? 'اليوم' : 'الأسبوع'}
                </button>
              ))}
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-3">
            {branches.length > 1 ? (
              <div className="flex flex-wrap items-center gap-1.5">
                {branches.map((b) => (
                  <button key={b.id} type="button" onClick={() => onBranch(b.id)}
                         className="rounded-full px-3 py-1 text-xs font-medium transition-colors"
                         style={b.id === activeBranch
                           ? { background: 'var(--rj-gold-soft)', color: 'var(--rj-gold-deep)' }
                           : { color: 'var(--rj-ink-soft)' }}>
                    {b.name || b.id}
                  </button>
                ))}
              </div>
            ) : null}

            {view === 'week' && staffHere.length > 1 ? (
              <select value={weekStaffId} onChange={(e) => setWeekStaffId(e.target.value)}
                     className="rounded-full px-3 py-1 text-xs font-medium shadow-sm"
                     style={{ background: 'var(--rj-surface)' }}>
                {staffHere.map((o) => <option key={o.id} value={o.id}>{o.name}</option>)}
              </select>
            ) : null}

            {/* Near-zero-friction search — filters the cards already on screen, no new request. */}
            <div className="relative flex-1 sm:max-w-[220px]">
              <Search size={14} aria-hidden
                     className="pointer-events-none absolute inset-inline-start-3 top-1/2 -translate-y-1/2"
                     style={{ color: 'var(--rj-ink-soft)' }} />
              <input
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="بحثٌ سريع: خدمة، موظفة، ملاحظة…"
                aria-label="بحث في الحجوزات"
                className="h-9 w-full rounded-full py-1.5 ps-9 pe-3 text-sm shadow-sm outline-none"
                style={{ background: 'var(--rj-surface)' }}
              />
            </div>
          </div>
        </div>
      </header>

      {note ? (
        <div className="fixed inset-x-0 top-20 z-30 mx-auto w-fit rounded-full px-4 py-2 text-sm font-medium shadow-lg"
            style={{ background: 'var(--rj-ink)', color: 'var(--rj-bg)' }}>
          {note}
        </div>
      ) : null}

      {/* ── body ───────────────────────────────────────────────────────────────────────────── */}
      <div className="mx-auto max-w-[1400px] px-4 pb-28 pt-4 sm:px-6">
        {rows === null && !failed ? (
          <div className="grid place-items-center py-24 text-sm" style={{ color: 'var(--rj-ink-soft)' }}>
            يُحمَّل الجدول…
          </div>
        ) : failed ? (
          <div className="grid place-items-center gap-2 py-24 text-center">
            <p className="text-base font-medium">تعذّر قراءة الحجوزات</p>
            <button type="button" onClick={load} className="text-sm font-medium underline"
                   style={{ color: 'var(--rj-gold-deep)' }}>حاول مجدداً</button>
          </div>
        ) : columns.length === 0 ? (
          <div className="grid place-items-center py-24 text-sm" style={{ color: 'var(--rj-ink-soft)' }}>
            لا موظفاتٌ نشِطاتٌ في هذا الفرع بعد.
          </div>
        ) : (
          <div className="overflow-x-auto rounded-[28px] shadow-sm" style={{ background: 'var(--rj-surface)' }}>
            <div className="grid" style={{ gridTemplateColumns: `56px repeat(${columns.length}, minmax(168px, 1fr))` }}>
              <div className="sticky top-0 z-10" style={{ background: 'var(--rj-surface)' }} />
              {columns.map((col) => (
                <div key={col.key}
                    className="sticky top-0 z-10 truncate border-b border-s px-3 py-3 text-center text-sm font-semibold"
                    style={{ borderColor: 'var(--rj-line)', background: 'var(--rj-surface)' }}>
                  {col.label}
                </div>
              ))}

              {/* time axis */}
              <div className="relative" style={{ height: WINDOW_LEN * PX_PER_MIN }}>
                {Array.from({ length: WINDOW_LEN / 60 + 1 }, (_, i) => WINDOW_START + i * 60).map((m) => (
                  <div key={m} className="absolute inset-inline-end-2 -translate-y-1/2 text-[11px] font-medium tabular-nums"
                      style={{ top: (m - WINDOW_START) * PX_PER_MIN, color: 'var(--rj-ink-soft)' }}>
                    {timeLabel(m)}
                  </div>
                ))}
              </div>

              {columns.map((col) => {
                const cards = cardsByColumn.get(col.key) ?? [];
                const isDragTarget = dragOver?.column === col.key;
                return (
                  <div
                    key={col.key}
                    className="relative border-s"
                    style={{ borderColor: 'var(--rj-line)', height: WINDOW_LEN * PX_PER_MIN }}
                    onDragOver={(e) => {
                      if (!drag) return;
                      e.preventDefault();
                      const rect = e.currentTarget.getBoundingClientRect();
                      const raw = WINDOW_START + (e.clientY - rect.top) / PX_PER_MIN;
                      const snapped = Math.round(Math.max(WINDOW_START, Math.min(WINDOW_END, raw)) / SNAP_MINUTES) * SNAP_MINUTES;
                      const valid = !conflicts(col.key, snapped, drag.booking.duration_minutes, drag.booking.id);
                      setDragOver({ column: col.key, minutes: snapped, valid });
                    }}
                    onDragLeave={(e) => {
                      if (e.currentTarget === e.target) setDragOver((d) => (d?.column === col.key ? null : d));
                    }}
                    onDrop={(e) => {
                      e.preventDefault();
                      if (drag && dragOver?.column === col.key) commitMove(drag.booking, col.key, dragOver.minutes);
                      setDrag(null); setDragOver(null);
                    }}
                    onClick={(e) => {
                      if (moving) {
                        const rect = e.currentTarget.getBoundingClientRect();
                        const raw = WINDOW_START + (e.clientY - rect.top) / PX_PER_MIN;
                        const snapped = Math.round(raw / SNAP_MINUTES) * SNAP_MINUTES;
                        commitMove(moving.booking, col.key, snapped);
                        setMoving(null);
                        return;
                      }
                      if (e.target !== e.currentTarget) return;
                      const rect = e.currentTarget.getBoundingClientRect();
                      const raw = WINDOW_START + (e.clientY - rect.top) / PX_PER_MIN;
                      const snapped = Math.round(raw / SNAP_MINUTES) * SNAP_MINUTES;
                      setDialog({ operatorId: view === 'day' ? col.key : weekStaffId,
                                 startsAt: epochAt(col.date, snapped) });
                    }}
                  >
                    {/* hour lines — for reading the grid, not decoration */}
                    {Array.from({ length: WINDOW_LEN / 60 }, (_, i) => WINDOW_START + i * 60).map((m) => (
                      <div key={m} className="absolute inset-x-0 border-t"
                          style={{ top: (m - WINDOW_START) * PX_PER_MIN, borderColor: 'var(--rj-line)' }} />
                    ))}

                    {/* drop preview — valid or refused, coloured BEFORE the drop itself (§6.1.1) */}
                    {isDragTarget && drag ? (
                      <div className="pointer-events-none absolute inset-inline-2 rounded-xl border-2 border-dashed"
                          style={{
                            top: (dragOver.minutes - WINDOW_START) * PX_PER_MIN,
                            height: drag.booking.duration_minutes * PX_PER_MIN,
                            background: dragOver.valid ? 'var(--rj-valid-soft)' : 'var(--rj-invalid-soft)',
                            borderColor: dragOver.valid ? 'var(--rj-valid)' : 'var(--rj-invalid)',
                          }} />
                    ) : null}

                    {cards.map((b) => {
                      const top = (minutesOf(b.starts_at) - WINDOW_START) * PX_PER_MIN;
                      const height = Math.max(28, b.duration_minutes * PX_PER_MIN);
                      const isBeingMoved = moving?.booking.id === b.id;
                      const tone = STATUS_VARS[b.status];
                      return (
                        <div
                          key={b.id}
                          draggable={b.status === 'booked'}
                          onDragStart={() => setDrag({
                            booking: b, fromMinutes: minutesOf(b.starts_at),
                            fromDate: dateKeyOf(b.starts_at), fromOperator: b.operator_id,
                          })}
                          onDragEnd={() => { setDrag(null); setDragOver(null); }}
                          onPointerDown={(e) => onCardPointerDown(b, e.pointerType === 'touch')}
                          onPointerUp={cancelLongPress}
                          onPointerLeave={cancelLongPress}
                          onClick={(e) => { e.stopPropagation(); if (!moving) setOpenBooking(b); }}
                          className={`rj-card-settle absolute inset-inline-1 cursor-grab overflow-hidden rounded-xl px-2.5 py-1.5 text-start shadow-sm transition-shadow active:cursor-grabbing ${drag?.booking.id === b.id ? 'rj-card-dragging' : ''} ${isBeingMoved ? 'ring-2 ring-offset-1' : ''}`}
                          style={{
                            top, height, background: tone.bg, color: tone.fg,
                            opacity: drag?.booking.id === b.id ? 0.4 : 1,
                            ...(isBeingMoved ? { '--tw-ring-color': 'var(--rj-gold)' } as React.CSSProperties : {}),
                          }}
                        >
                          {height < 30 ? (
                            // A very short card (a quick service) has no room for two lines — one
                            // combined line beats a time with no service name at all.
                            <div className="truncate text-[11px] font-semibold leading-tight">
                              {timeLabel(minutesOf(b.starts_at))} · {serviceNameOf(b.service_ids) || '—'}
                            </div>
                          ) : (
                            <>
                              <div className="truncate text-xs font-semibold leading-tight">
                                {timeLabel(minutesOf(b.starts_at))}
                              </div>
                              <div className="truncate text-[11px] leading-tight opacity-80">
                                {serviceNameOf(b.service_ids) || '—'}
                              </div>
                            </>
                          )}
                        </div>
                      );
                    })}
                  </div>
                );
              })}
            </div>
          </div>
        )}
      </div>

      {/* undo bar — five seconds, never a confirm dialog (§6.1.1) */}
      {undo ? (
        <div className="fixed inset-x-0 bottom-24 z-30 mx-auto flex w-fit items-center gap-3 rounded-full px-4 py-2.5 shadow-lg sm:bottom-6 sm:inset-inline-end-6 sm:inset-inline-start-auto"
            style={{ background: 'var(--rj-ink)', color: 'var(--rj-bg)' }}>
          <span className="text-sm">نُقل الموعد</span>
          <button type="button" onClick={undoMove} className="text-sm font-semibold"
                 style={{ color: 'var(--rj-gold)' }}>تراجع</button>
        </div>
      ) : null}

      {/* touch "move" mode — cancelled by tapping outside any card */}
      {moving ? (
        <div className="fixed inset-x-0 top-20 z-30 mx-auto flex w-fit items-center gap-3 rounded-full px-4 py-2 shadow-lg"
            style={{ background: 'var(--rj-gold)', color: 'var(--rj-ink)' }}>
          <span className="text-sm font-medium">انقري على الخانة الجديدة</span>
          <button type="button" onClick={() => setMoving(null)} aria-label="إلغاء النقل">
            <X size={16} aria-hidden />
          </button>
        </div>
      ) : null}

      <button
        type="button"
        onClick={() => setDialog({})}
        className="fixed bottom-6 inset-inline-end-6 z-20 flex h-14 items-center gap-2 rounded-full px-5 text-base font-semibold shadow-lg transition-transform active:scale-95"
        style={{ background: 'var(--rj-gold)', color: 'var(--rj-ink)' }}
      >
        <Plus size={20} aria-hidden />
        حجز جديد
      </button>

      {dialog !== 'closed' ? (
        <BookingDialog
          session={session}
          branchId={activeBranch}
          date={dialog.startsAt ? dateKeyOf(dialog.startsAt) : date}
          initialOperatorId={dialog.operatorId}
          initialStartsAt={dialog.startsAt}
          services={services}
          staff={staffHere}
          onClose={() => setDialog('closed')}
          onCreated={(b) => {
            setDialog('closed');
            setRows((cur) => [...(cur ?? []), b]);
            say('تم الحجز ✓');
          }}
        />
      ) : null}

      {openBooking ? (
        <BookingActions
          booking={openBooking}
          customerLabel={serviceNameOf(openBooking.service_ids)}
          operatorLabel={nameOf(openBooking.operator_id)}
          onClose={() => setOpenBooking(null)}
          onChanged={(b) => {
            setRows((cur) => (cur ?? []).map((x) => (x.id === b.id ? b : x)));
            setOpenBooking(null);
          }}
          session={session}
          say={say}
        />
      ) : null}
    </main>
  );
}

/** A small action sheet opened by tapping a card — attend / no-show / cancel, in the grid's own
 *  visual identity. */
function BookingActions({ booking, customerLabel, operatorLabel, onClose, onChanged, session, say }: {
  booking: Booking; customerLabel: string; operatorLabel: string; onClose: () => void;
  onChanged: (b: Booking) => void; session: Session; say: (t: string) => void;
}) {
  const [busy, setBusy] = useState(false);
  const act = async (fn: (s: Session, id: string) => Promise<Booking>, doneMsg: string) => {
    setBusy(true);
    try {
      onChanged(await fn(session, booking.id));
      say(doneMsg);
    } catch (e) {
      say(sentenceFor(e, 'تعذّر تنفيذ الإجراء.'));
    } finally {
      setBusy(false);
    }
  };
  return (
    <div className="rj-grid fixed inset-0 z-40 flex items-end justify-center sm:items-center"
        onClick={onClose}>
      <div className="absolute inset-0" style={{ background: 'rgba(32,26,21,0.35)' }} />
      <div onClick={(e) => e.stopPropagation()}
          className="relative w-full max-w-sm rounded-t-[28px] p-5 shadow-lg sm:rounded-[28px]"
          style={{ background: 'var(--rj-surface)' }}>
        <div className="mb-4 flex items-start justify-between gap-3">
          <div>
            <p className="text-base font-semibold">{customerLabel || 'حجز'}</p>
            <p className="text-sm" style={{ color: 'var(--rj-ink-soft)' }}>{operatorLabel}</p>
            {booking.note ? <p className="mt-1 text-xs" style={{ color: 'var(--rj-ink-soft)' }}>{booking.note}</p> : null}
          </div>
          <button type="button" onClick={onClose} aria-label="إغلاق"><X size={18} aria-hidden /></button>
        </div>
        {booking.status === 'booked' ? (
          <div className="flex flex-col gap-2">
            <button type="button" disabled={busy} onClick={() => act(attendBooking, 'سُجّل الحضور ✓')}
                   className="rounded-2xl py-3 text-sm font-semibold"
                   style={{ background: 'var(--rj-attended-soft)', color: 'var(--rj-attended)' }}>
              حضرت
            </button>
            <button type="button" disabled={busy}
                   onClick={() => act((s, id) => noShowBooking(s, id), 'سُجّل عدم الحضور')}
                   className="rounded-2xl py-3 text-sm font-semibold"
                   style={{ background: 'var(--rj-noshow-soft)', color: 'var(--rj-noshow)' }}>
              لم تحضر
            </button>
            <button type="button" disabled={busy}
                   onClick={() => act((s, id) => cancelBooking(s, id), 'أُلغي الحجز')}
                   className="rounded-2xl py-3 text-sm font-semibold"
                   style={{ background: 'var(--rj-cancelled-soft)', color: 'var(--rj-cancelled)' }}>
              إلغاء الحجز
            </button>
          </div>
        ) : (
          <p className="rounded-2xl py-3 text-center text-sm" style={{ background: 'var(--rj-line)', color: 'var(--rj-ink-soft)' }}>
            {STATUS_LABEL[booking.status]} — لا أفعالٌ إضافية
          </p>
        )}
      </div>
    </div>
  );
}
