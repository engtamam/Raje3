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
import { ChevronLeft, ChevronRight, Filter, GripVertical, Plus, X } from 'lucide-react';
import {
  attendBooking, type Booking, cancelBooking, type CatalogueService, type CustomerHit,
  fetchCatalogue, type FieldOperator, listBookings, listBookingStaff, noShowBooking,
  rescheduleBooking, sentenceFor,
} from '../api';
import type { ScopeBranch } from '../branch-scope';
import { riyals } from '../money';
import { PAYMENT_COLOR, PAYMENT_LABEL, PAYMENT_ORDER, type PaymentStatus } from '../bookingPayment';
import type { Session } from '../session';
import { BookingDialog } from './BookingDialog';

// ── display window and snap ─────────────────────────────────────────────────────────────────
const WINDOW_START = 8 * 60;    // 08:00 — a fixed, reasonable display window; real business
const WINDOW_END = 22 * 60;     // 22:00    hours are wired in later
const WINDOW_LEN = WINDOW_END - WINDOW_START;
const PX_PER_MIN = 1.6;
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
  booked: 'محجوز', attended: 'حضر', no_show: 'لم يحضر', cancelled: 'ملغى',
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
  // undefined = «not loaded yet» (skeleton); null = «the read failed» (retry). Collapsing them to
  // one value made a failed read indistinguishable from one still in flight — the retry sentence
  // written below was unreachable.
  const [rows, setRows] = useState<Booking[] | null | undefined>(undefined);
  // null = «the read failed», not «this shop has none» — a failed staff read must not render as
  // «لا موظفون نشِطون», which reads as a fact about the shop instead of a fact about the network.
  const [services, setServices] = useState<CatalogueService[] | null | undefined>(undefined);
  const [staff, setStaff] = useState<FieldOperator[] | null | undefined>(undefined);
  const [note, setNote] = useState<string | null>(null);
  const [undo, setUndo] = useState<UndoState | null>(null);
  // FILTERS, NOT SEARCH — a shop reads this grid a hundred times a day; typing a name is a
  // request nobody asked to make when the same narrowing is three taps away as a chip.
  const [filterService, setFilterService] = useState('');   // '' = every service
  const [filterPayment, setFilterPayment] = useState<'any' | PaymentStatus>('any');
  const [filtersOpen, setFiltersOpen] = useState(false);
  // "البحث بالجوال" كان هنا — عُطِّل مؤقتاً (لا يعمل: مساره في search-service لم يُبنَ بعد،
  // مُشخَّصٌ ومُصحَّحٌ في platform/ بانتظار إصدارٍ حقيقي منك). يعود حين يعمل فعلاً.

  const [dialog, setDialog] = useState<{
    operatorId?: string; startsAt?: number; customer?: CustomerHit; serviceIds?: string[];
    /** Set from "تعديل" on an existing card — the same dialog, in edit mode. */
    editing?: Booking; editingLabel?: string;
  } | 'closed'>('closed');
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
    setRows(undefined);
    Promise.all(daysToLoad.map((d) => listBookings(session, activeBranch, d)))
      .then((answers) => setRows(answers.flatMap((a) => a.bookings)))
      .catch(() => setRows(null));
  }, [session, activeBranch, daysToLoad]);

  useEffect(() => { load(); }, [load]);

  useEffect(() => {
    fetchCatalogue(session).then((r) => setServices(r.services)).catch(() => setServices(null));
    listBookingStaff(session).then(setStaff).catch(() => setStaff(null));
  }, [session]);

  // THIS BRANCH'S TEAM ONLY. `listBookingStaff` returns every branch the caller may see;
  // unbranched operators stay visible everywhere, the same rule operations' own staff route uses.
  const staffHere = useMemo(
    () => (staff ?? []).filter((o) => !o.branch_id || o.branch_id === activeBranch),
    [staff, activeBranch],
  );
  useEffect(() => {
    if (!weekStaffId && staffHere.length > 0) setWeekStaffId(staffHere[0].id);
  }, [staffHere, weekStaffId]);

  const nameOf = useMemo(() => {
    const m = new Map(staffHere.map((o) => [o.id, o.name]));
    return (id: string) => m.get(id) || id;
  }, [staffHere]);
  const serviceNamesOf = useMemo(() => {
    const m = new Map((services ?? []).map((s) => [s.id, s.name]));
    return (ids: string[]) => ids.map((id) => m.get(id) || id);
  }, [services]);
  const serviceNameOf = useMemo(
    () => (ids: string[]) => serviceNamesOf(ids).join('، '),
    [serviceNamesOf],
  );

  const visible = useMemo(() => {
    return (rows ?? []).filter((b) => {
      if (filterService && !b.service_ids.includes(filterService)) return false;
      if (filterPayment !== 'any' && b.payment_status !== filterPayment) return false;
      return true;
    });
  }, [rows, filterService, filterPayment]);

  const activeFilterCount = (filterService ? 1 : 0) + (filterPayment !== 'any' ? 1 : 0);

  // ── columns: staff in day view, days in week view ───────────────────────────────────────────
  const columns = view === 'day'
    ? staffHere.map((o) => ({ key: o.id, label: o.name, date }))
    // DAY NUMBER ONLY, NO MONTH — a week column is a fraction of the grid's own width, and the
    // range header above already states the month ("16 أغسطس – 22 أغسطس"). Repeating it in seven
    // narrow columns was what forced "الأحد 16 أغسط…" to truncate before the day number even
    // finished rendering — the one number the column actually needs to say.
    : daysToLoad.map((d) => ({ key: d, label: `${WEEKDAYS[new Date(`${d}T00:00:00Z`).getUTCDay()]} ${Number(d.split('-')[2])}`, date: d }));

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

  // ── OVERLAPPING CARDS SIT SIDE BY SIDE, NEVER STACKED — one operator double-booked (or two
  // appointments fifteen minutes apart) used to render as two cards at the SAME left/right edges,
  // one hiding the other completely with no sign a second booking existed at all. Classic
  // interval-graph colouring, per column: sweep bookings in start order, group into clusters that
  // actually overlap in time, and within a cluster assign each card the first lane whose previous
  // occupant has already ended — the same layout a real calendar draws.
  const overlapLayout = useMemo(() => {
    const layout = new Map<string, { lane: number; lanes: number }>();
    for (const cards of cardsByColumn.values()) {
      const sorted = [...cards].sort((a, b) => a.starts_at - b.starts_at);
      let cluster: Booking[] = [];
      let clusterEnd = -Infinity;
      const flush = () => {
        if (cluster.length === 0) return;
        const laneEnds: number[] = [];
        for (const b of cluster) {
          const start = minutesOf(b.starts_at);
          const end = start + b.duration_minutes;
          let lane = laneEnds.findIndex((t) => t <= start);
          if (lane === -1) { lane = laneEnds.length; laneEnds.push(end); }
          else laneEnds[lane] = end;
          layout.set(b.id, { lane, lanes: 0 });   // lanes filled in once the cluster is known
        }
        for (const b of cluster) layout.get(b.id)!.lanes = laneEnds.length;
        cluster = [];
      };
      for (const b of sorted) {
        const start = minutesOf(b.starts_at);
        if (start >= clusterEnd) flush();
        cluster.push(b);
        clusterEnd = Math.max(clusterEnd, start + b.duration_minutes);
      }
      flush();
    }
    return layout;
  }, [cardsByColumn]);

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
          {branches.length === 0 ? 'لا فروع بعد' : 'اختر فرعاً لعرض جدوله'}
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

            {/* FILTERS, NOT A SEARCH BOX — narrowing the grid is a tap on what it already shows
                (a service, a deposit state), never typing a query for something read a hundred
                times a day.

                TWO LAYOUTS, ONE STATE. On a phone the header is already three rows deep before
                the grid starts, so the controls fold into one chip — a tap most of the time, two
                on the day filtering actually touches. On anything wider there is room to just
                SHOW the two controls inline, which is the one-tap version this was always meant
                to be; the chip below only exists for the width that cannot afford it. */}
            {/* البحث بالجوال مُعطَّل مؤقتاً — الاقتراح يتكئ على search-service، ومساره الداخلي
                لهذا الاستدعاء بالذات لم يُبنَ بعد (مُشخَّصٌ ومُصحَّحٌ في platform/، بانتظار
                إصدارٍ حقيقي منك قبل أن يعمل). عرضه هنا كان يريه حقلاً لا يجيب أبداً. */}
            <div className="hidden items-center gap-2 sm:flex">
              <select value={filterService} onChange={(e) => setFilterService(e.target.value)}
                     className="h-9 rounded-full px-3 text-xs font-medium shadow-sm outline-none"
                     style={{ background: 'var(--rj-surface)', color: 'var(--rj-ink)' }}>
                <option value="">كل الخدمات</option>
                {(services ?? []).map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
              </select>
              <div className="flex overflow-hidden rounded-full shadow-sm" style={{ border: '1px solid var(--rj-line)' }}>
                <button type="button" onClick={() => setFilterPayment('any')}
                       className="h-9 px-3 text-xs font-medium"
                       style={filterPayment === 'any'
                         ? { background: 'var(--rj-ink)', color: 'var(--rj-bg)' }
                         : { background: 'var(--rj-surface)', color: 'var(--rj-ink-soft)' }}>
                  الكل
                </button>
                {PAYMENT_ORDER.map((v) => (
                  <button key={v} type="button" onClick={() => setFilterPayment(v)}
                         className="h-9 px-3 text-xs font-medium"
                         style={v === filterPayment
                           ? { background: PAYMENT_COLOR[v].fg, color: 'var(--rj-bg)' }
                           : { background: PAYMENT_COLOR[v].bg, color: PAYMENT_COLOR[v].fg }}>
                    {PAYMENT_LABEL[v]}
                  </button>
                ))}
              </div>
              {activeFilterCount ? (
                <button type="button" onClick={() => { setFilterService(''); setFilterPayment('any'); }}
                       aria-label="إزالة كل الفلاتر"
                       className="grid h-9 w-9 place-items-center rounded-full shadow-sm"
                       style={{ background: 'var(--rj-surface)', color: 'var(--rj-ink-soft)' }}>
                  <X size={14} aria-hidden />
                </button>
              ) : null}
            </div>

            {/* THE MOBILE-ONLY FALLBACK — same state, folded behind one chip. */}
            <div className="relative sm:hidden">
              <button type="button" onClick={() => setFiltersOpen((v) => !v)}
                     aria-expanded={filtersOpen}
                     className="flex h-9 items-center gap-1.5 rounded-full px-3 text-sm font-medium shadow-sm"
                     style={{
                       background: activeFilterCount ? 'var(--rj-gold-soft)' : 'var(--rj-surface)',
                       color: activeFilterCount ? 'var(--rj-gold-deep)' : 'var(--rj-ink)',
                     }}>
                <Filter size={14} aria-hidden />
                فلاتر
                {activeFilterCount ? (
                  <span className="grid h-4 w-4 place-items-center rounded-full text-[10px] font-bold"
                       style={{ background: 'var(--rj-gold)', color: 'var(--rj-ink)' }}>
                    {activeFilterCount}
                  </span>
                ) : null}
              </button>

              {filtersOpen ? (
                <>
                <button type="button" aria-label="إغلاق الفلاتر" onClick={() => setFiltersOpen(false)}
                       className="fixed inset-0 z-10 cursor-default" />
                <div className="absolute inset-inline-end-0 top-11 z-20 flex w-64 flex-col gap-3 rounded-2xl p-4 shadow-lg"
                    style={{ background: 'var(--rj-surface)', border: '1px solid var(--rj-line)' }}>
                  <div className="flex flex-col gap-1.5">
                    <span className="text-xs font-semibold" style={{ color: 'var(--rj-ink-soft)' }}>الخدمة</span>
                    <select value={filterService} onChange={(e) => setFilterService(e.target.value)}
                           className="h-9 rounded-xl px-2 text-sm outline-none"
                           style={{ background: 'var(--rj-bg)', border: '1px solid var(--rj-line)' }}>
                      <option value="">كل الخدمات</option>
                      {(services ?? []).map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
                    </select>
                  </div>
                  <div className="flex flex-col gap-1.5">
                    <span className="text-xs font-semibold" style={{ color: 'var(--rj-ink-soft)' }}>الدفع</span>
                    <div className="flex gap-1.5">
                      <button type="button" onClick={() => setFilterPayment('any')}
                             className="flex-1 rounded-full py-1.5 text-xs font-medium"
                             style={filterPayment === 'any'
                               ? { background: 'var(--rj-ink)', color: 'var(--rj-bg)' }
                               : { background: 'var(--rj-bg)', color: 'var(--rj-ink-soft)',
                                  border: '1px solid var(--rj-line)' }}>
                        الكل
                      </button>
                      {PAYMENT_ORDER.map((v) => (
                        <button key={v} type="button" onClick={() => setFilterPayment(v)}
                               className="flex-1 rounded-full py-1.5 text-xs font-medium"
                               style={v === filterPayment
                                 ? { background: PAYMENT_COLOR[v].fg, color: 'var(--rj-bg)' }
                                 : { background: PAYMENT_COLOR[v].bg, color: PAYMENT_COLOR[v].fg }}>
                          {PAYMENT_LABEL[v]}
                        </button>
                      ))}
                    </div>
                  </div>
                  {activeFilterCount ? (
                    <button type="button" onClick={() => { setFilterService(''); setFilterPayment('any'); }}
                           className="text-xs font-medium underline" style={{ color: 'var(--rj-gold-deep)' }}>
                      إزالة كل الفلاتر
                    </button>
                  ) : null}
                </div>
                </>
              ) : null}
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
        {rows === undefined ? (
          <div className="grid place-items-center py-24 text-sm" style={{ color: 'var(--rj-ink-soft)' }}>
            يُحمَّل الجدول…
          </div>
        ) : rows === null ? (
          <div className="grid place-items-center gap-2 py-24 text-center">
            <p className="text-base font-medium">تعذّر قراءة الحجوزات</p>
            <button type="button" onClick={load} className="text-sm font-medium underline"
                   style={{ color: 'var(--rj-gold-deep)' }}>حاول مجدداً</button>
          </div>
        ) : view === 'day' && staff === null ? (
          <div className="grid place-items-center gap-2 py-24 text-center">
            <p className="text-base font-medium">تعذّرت قراءة فريق العمل</p>
            <button type="button" onClick={() => listBookingStaff(session).then(setStaff).catch(() => setStaff(null))}
                   className="text-sm font-medium underline" style={{ color: 'var(--rj-gold-deep)' }}>
              حاول مجدداً
            </button>
          </div>
        ) : columns.length === 0 ? (
          <div className="grid place-items-center py-24 text-sm" style={{ color: 'var(--rj-ink-soft)' }}>
            لا موظفون نشِطون في هذا الفرع بعد.
          </div>
        ) : (
          <div data-testid="rj-grid"
              className={view === 'week' ? 'rounded-[28px] p-2 shadow-sm' : 'overflow-x-auto rounded-[28px] p-2 shadow-sm'}
              style={{ background: 'var(--rj-surface)' }}>
            {/* WEEK NEVER SCROLLS TO BE SEEN WHOLE — its seven columns are the fixed, known set the
                view exists to show side by side, so they take `1fr` each and share the container's
                own width exactly, however wide that is. DAY KEEPS A FLOOR — one column per staff
                member, whose names must stay readable, and a branch with many of them is the one
                case scrolling is the honest answer rather than crushed, truncated columns. */}
            <div className="grid" style={{ gridTemplateColumns: view === 'week'
              ? `58px repeat(${columns.length}, 1fr)`
              : `64px repeat(${columns.length}, minmax(140px, 1fr))` }}>
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
                {/* THE LABEL NAMES THE HOUR ROW, SO IT SITS IN THE MIDDLE OF IT — not on the line
                    between one hour and the next, which read as belonging to neither cell (and,
                    at the very first line, sat half off the top of the grid entirely). One label
                    per hour BAND (`WINDOW_LEN / 60` bands, not `+ 1` boundary ticks), centred on
                    its own band's own height. */}
                {Array.from({ length: WINDOW_LEN / 60 }, (_, i) => WINDOW_START + i * 60).map((m) => (
                  <div key={m}
                      className="absolute inset-inline-end-2.5 -translate-y-1/2 whitespace-nowrap text-xs font-bold tabular-nums"
                      style={{ top: (m - WINDOW_START) * PX_PER_MIN + (60 * PX_PER_MIN) / 2, color: 'var(--rj-ink)' }}>
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
                    {/* QUARTER-HOUR LINES, FAINTER THAN THE HOUR — every cell is already
                        clickable at 15-minute precision (SNAP_MINUTES), this is what makes that
                        structure visible instead of guessed. Four real sections per hour, each
                        its own tap target, matching the grain the click math already snaps to. */}
                    {Array.from({ length: WINDOW_LEN / 15 }, (_, i) => WINDOW_START + i * 15).map((m) => (
                      <div key={m} className="absolute inset-x-0 border-t"
                          style={{
                            top: (m - WINDOW_START) * PX_PER_MIN,
                            borderColor: m % 60 === 0 ? 'var(--rj-line)' : 'var(--rj-line)',
                            opacity: m % 60 === 0 ? 1 : 0.4,
                          }} />
                    ))}

                    {/* THE PREVIEW SAYS WHERE IT WILL LAND, NOT JUST THAT IT MOVED — a dashed box
                        with no time on it left him guessing whether the snap actually caught the
                        quarter-hour line it looked close to. A solid top edge marks the exact
                        head of the block (the moment it starts, which is the one edge dragging
                        actually decides — the tail just follows from the service's own duration),
                        and the time itself sits pinned to that edge, updating on every snap tick
                        rather than only once the card is dropped. */}
                    {isDragTarget && drag ? (
                      <div className="pointer-events-none absolute inset-inline-2 overflow-visible rounded-xl border-2 border-dashed transition-[top] duration-100"
                          style={{
                            top: (dragOver.minutes - WINDOW_START) * PX_PER_MIN,
                            height: drag.booking.duration_minutes * PX_PER_MIN,
                            background: dragOver.valid ? 'var(--rj-valid-soft)' : 'var(--rj-invalid-soft)',
                            borderColor: dragOver.valid ? 'var(--rj-valid)' : 'var(--rj-invalid)',
                            borderTopWidth: 3, borderTopStyle: 'solid',
                          }}>
                        <span
                          className="absolute inset-inline-start-1 -top-2.5 whitespace-nowrap rounded-full px-2 py-0.5 text-[10px] font-bold shadow-sm"
                          style={{
                            background: dragOver.valid ? 'var(--rj-valid)' : 'var(--rj-invalid)',
                            color: 'var(--rj-bg)',
                          }}>
                          {timeLabel(dragOver.minutes)}
                        </span>
                      </div>
                    ) : null}

                    {cards.map((b) => {
                      const top = (minutesOf(b.starts_at) - WINDOW_START) * PX_PER_MIN;
                      const height = Math.max(28, b.duration_minutes * PX_PER_MIN);
                      const isBeingMoved = moving?.booking.id === b.id;
                      const tone = STATUS_VARS[b.status];
                      // ONE OF SEVERAL OVERLAPPING CARDS SHRINKS TO ITS OWN LANE, WITH A HAIRLINE
                      // GAP FROM ITS NEIGHBOURS — a card alone in its slot still takes the full
                      // column, exactly as before.
                      const { lane, lanes } = overlapLayout.get(b.id) ?? { lane: 0, lanes: 1 };
                      const laneWidth = 100 / lanes;
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
                          className={`rj-card-settle absolute cursor-grab overflow-hidden rounded-xl px-2.5 py-1.5 text-start shadow-sm transition-shadow active:cursor-grabbing ${drag?.booking.id === b.id ? 'rj-card-dragging' : ''} ${isBeingMoved ? 'ring-2 ring-offset-1' : ''}`}
                          style={{
                            top: top + 1, height: Math.max(26, height - 2),
                            insetInlineStart: `calc(${lane * laneWidth}% + ${lane ? 3 : 4}px)`,
                            width: `calc(${laneWidth}% - ${lanes > 1 ? 6 : 8}px)`,
                            background: tone.bg, color: tone.fg,
                            opacity: drag?.booking.id === b.id ? 0.4 : 1,
                            zIndex: lane + 1,
                            ...(isBeingMoved ? { '--tw-ring-color': 'var(--rj-gold)' } as React.CSSProperties : {}),
                          }}
                        >
                          {/* THE ONLY VISIBLE SIGN A CARD DRAGS AT ALL, otherwise the sole cue was
                              a cursor style — invisible on touch and easy to miss with a mouse
                              that never happened to hover. Booked-only, matching `draggable`
                              itself: a card that cannot be dragged must not offer a handle for it. */}
                          {b.status === 'booked' ? (
                            <GripVertical size={11} aria-hidden
                                         className="absolute inset-inline-start-1 top-1/2 -translate-y-1/2 opacity-40" />
                          ) : null}
                          {/* A DOT, NOT A CHIP — one glance at the grid should tell "عربون" from
                              "مدفوع" without opening the card; a full badge would fight the
                              service tags for the same few pixels a short card has. */}
                          {/* `?? 'none'` — a rolling deploy can serve this exact response from an
                              older bookings pod that predates payment_status entirely; reading a
                              missing key as "بدون عربون" is the right default and never crashes
                              the whole grid over one field one pod has not caught up on yet. */}
                          {(b.payment_status ?? 'none') !== 'none' ? (
                            <span aria-hidden
                                 title={b.payment_status === 'deposit' && b.deposit_amount_minor
                                   ? `${PAYMENT_LABEL.deposit} — ${riyals(b.deposit_amount_minor)} ريال`
                                   : PAYMENT_LABEL[b.payment_status ?? 'none']}
                                 className="absolute inset-inline-end-1.5 top-1.5 h-2 w-2 rounded-full"
                                 style={{ background: PAYMENT_COLOR[b.payment_status ?? 'none'].fg }} />
                          ) : null}
                          {/* A STAR BESIDE THE DOT — a customer waiting on a reward is a different
                              fact from a customer who paid a deposit, and a shop that sells both
                              needs to tell them apart at a glance, not just know "something's
                              flagged". Still present on an attended booking means the spend
                              failed or needed an approval attend() could not give (see the
                              field's own note) — the same glance now reads "still owed". */}
                          {b.intended_reward_id ? (
                            <span aria-hidden title="جائزة بانتظار الاستبدال عند الحضور"
                                 className="absolute inset-inline-end-4 top-1 text-[10px] leading-none">
                              ⭐
                            </span>
                          ) : null}
                          {height < 30 ? (
                            // A very short card (a quick service) has no room for two lines — one
                            // combined line beats a time with no service name at all.
                            <div className={`truncate text-[11px] font-semibold leading-tight ${b.status === 'booked' ? 'ps-3' : ''}`}>
                              {timeLabel(minutesOf(b.starts_at))} · {serviceNameOf(b.service_ids) || '—'}
                            </div>
                          ) : (
                            <div className={b.status === 'booked' ? 'ps-3' : ''}>
                              <div className="truncate text-xs font-semibold leading-tight">
                                {timeLabel(minutesOf(b.starts_at))}
                              </div>
                              {/* TAGS, NOT A SENTENCE — a comma-joined line read as a description
                                  of the appointment; each service is its own fact, and a shop
                                  reading the grid needs to pick them out at a glance, not parse a
                                  clause. Wraps onto a second line inside the card rather than
                                  truncating the services that did not fit the first one. */}
                              <div className="mt-0.5 flex flex-wrap gap-1 overflow-hidden" style={{ maxHeight: height - 20 }}>
                                {serviceNamesOf(b.service_ids).length > 0
                                  ? serviceNamesOf(b.service_ids).map((name) => (
                                      <span key={name}
                                           className="truncate rounded-full px-1.5 py-px text-[10px] leading-tight"
                                           style={{ background: 'rgb(0 0 0 / 0.08)', maxWidth: '100%' }}>
                                        {name}
                                      </span>
                                    ))
                                  : <span className="text-[11px] opacity-80">—</span>}
                              </div>
                            </div>
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

      {/* AN ICON ALONE, NOT A LABELLED PILL — the wide "حجز جديد" button sat over the grid's own
          content, on the one screen where every extra pixel is a slot he could otherwise see.
          `+` reads the same act at a fifth of the width; `aria-label` carries the words a sighted
          tap never needed. */}
      <button
        type="button"
        onClick={() => setDialog({})}
        aria-label="حجز جديد"
        title="حجز جديد"
        className="fixed bottom-6 inset-inline-end-6 z-20 grid h-14 w-14 place-items-center rounded-full shadow-lg transition-transform active:scale-95"
        style={{ background: 'var(--rj-gold)', color: 'var(--rj-ink)' }}
      >
        <Plus size={24} aria-hidden />
      </button>

      {dialog !== 'closed' ? (
        <BookingDialog
          session={session}
          branchId={activeBranch}
          date={dialog.startsAt ? dateKeyOf(dialog.startsAt) : date}
          initialOperatorId={dialog.operatorId}
          initialStartsAt={dialog.startsAt}
          initialCustomer={dialog.customer}
          initialServiceIds={dialog.serviceIds}
          services={services ?? []}
          staff={staffHere}
          editingBooking={dialog.editing}
          editingCustomerLabel={dialog.editingLabel}
          onClose={() => setDialog('closed')}
          onCreated={(b) => {
            const wasEditing = Boolean(dialog.editing);
            setDialog('closed');
            setRows((cur) => (wasEditing
              ? (cur ?? []).map((x) => (x.id === b.id ? b : x))
              : [...(cur ?? []), b]));
            say(wasEditing ? 'حُفظ التعديل ✓' : 'تم الحجز ✓');
          }}
        />
      ) : null}

      {openBooking ? (
        <BookingActions
          booking={openBooking}
          customerLabel={serviceNameOf(openBooking.service_ids)}
          operatorLabel={nameOf(openBooking.operator_id)}
          services={services ?? []}
          onClose={() => setOpenBooking(null)}
          onChanged={(b) => {
            setRows((cur) => (cur ?? []).map((x) => (x.id === b.id ? b : x)));
            // Attending stays open — BookingActions shows its own follow-up view (§2.7); cancel
            // and no-show have nothing further to say, so the sheet closes right away.
            if (b.status !== 'attended') setOpenBooking(null);
          }}
          onBookNext={(b) => {
            setOpenBooking(null);
            const cycleDays = Math.max(
              0, ...b.service_ids.map((id) => (services ?? []).find((s) => s.id === id)?.cycle_days ?? 0));
            setDialog({
              operatorId: b.operator_id,
              startsAt: b.starts_at + cycleDays * 86400,
              // Only the id is known here — a closed Booking carries no phone number, and the
              // dialog never reads `.phone` once `customer` is already set (it saves by id).
              customer: { id: b.customer_id, phone: '' },
              serviceIds: b.service_ids,
            });
          }}
          onEdit={(b) => {
            setOpenBooking(null);
            setDialog({ editing: b, editingLabel: serviceNameOf(b.service_ids) });
          }}
          session={session}
          say={say}
        />
      ) : null}
    </main>
  );
}


/** A small action sheet opened by tapping a card — attend / no-show / cancel, in the grid's own
 *  visual identity. Closing a booking as attended offers "احجزي الجلسة القادمة" (§2.7) when the
 *  service has a real cycle — the sleeping field `cycle_days` already in the catalogue, used for
 *  its own purpose rather than reinvented. */
function BookingActions({ booking, customerLabel, operatorLabel, services, onClose, onChanged,
                         onBookNext, onEdit, session, say }: {
  booking: Booking; customerLabel: string; operatorLabel: string; services: CatalogueService[];
  onClose: () => void; onChanged: (b: Booking) => void; onBookNext: (b: Booking) => void;
  onEdit: (b: Booking) => void; session: Session; say: (t: string) => void;
}) {
  const [busy, setBusy] = useState(false);
  const [attended, setAttended] = useState<Booking | null>(null);
  const act = async (fn: (s: Session, id: string) => Promise<Booking>, doneMsg: string) => {
    setBusy(true);
    try {
      const updated = await fn(session, booking.id);
      onChanged(updated);
      if (updated.status === 'attended') setAttended(updated);
      say(doneMsg);
    } catch (e) {
      say(sentenceFor(e, 'تعذّر تنفيذ الإجراء.'));
    } finally {
      setBusy(false);
    }
  };
  const cycleDays = Math.max(
    0, ...booking.service_ids.map((id) => services.find((s) => s.id === id)?.cycle_days ?? 0));

  if (attended) {
    return (
      <div className="rj-grid fixed inset-0 z-40 flex items-end justify-center sm:items-center"
          onClick={onClose}>
        <div className="absolute inset-0" style={{ background: 'rgba(32,26,21,0.35)' }} />
        <div onClick={(e) => e.stopPropagation()}
            className="relative w-full max-w-sm rounded-t-[28px] p-5 shadow-lg sm:rounded-[28px]"
            style={{ background: 'var(--rj-surface)' }}>
          <p className="mb-3 text-base font-semibold">سُجّل الحضور ✓</p>
          {cycleDays > 0 ? (
            <button type="button" onClick={() => onBookNext(attended)}
                   className="w-full rounded-2xl py-3 text-sm font-semibold"
                   style={{ background: 'var(--rj-gold-soft)', color: 'var(--rj-gold-deep)' }}>
              احجز الجلسة القادمة — بعد {cycleDays} يوماً
            </button>
          ) : null}
          <button type="button" onClick={onClose}
                 className="mt-2 w-full rounded-2xl py-3 text-sm font-medium"
                 style={{ color: 'var(--rj-ink-soft)' }}>
            إغلاق
          </button>
        </div>
      </div>
    );
  }
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
            <button type="button" onClick={() => onEdit(booking)}
                   className="rounded-2xl py-3 text-sm font-semibold"
                   style={{ background: 'var(--rj-line)', color: 'var(--rj-ink)' }}>
              تعديل الحجز — الخدمات، الموعد، الملاحظة
            </button>
            <button type="button" disabled={busy} onClick={() => act(attendBooking, 'سُجّل الحضور ✓')}
                   className="rounded-2xl py-3 text-sm font-semibold"
                   style={{ background: 'var(--rj-attended-soft)', color: 'var(--rj-attended)' }}>
              حضر
            </button>
            <button type="button" disabled={busy}
                   onClick={() => act((s, id) => noShowBooking(s, id), 'سُجّل عدم الحضور')}
                   className="rounded-2xl py-3 text-sm font-semibold"
                   style={{ background: 'var(--rj-noshow-soft)', color: 'var(--rj-noshow)' }}>
              لم يحضر
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
