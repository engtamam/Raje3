/**
 * Bookings grid (Stage 6 rebuilt + Stage 7, docs/خطة-تنفيذ-الحجوزات.md §6.1/§6.1.1,
 * docs/وصف-تطبيق-الحجوزات.md §6.1/§6.1.1). This screen alone
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
import {
  Calendar, Check, ChevronLeft, ChevronRight, Clock, Filter, GripVertical, LayoutGrid, List,
  Pencil, Phone, Plus, Settings, Trash2, User, X,
} from 'lucide-react';
import {
  attendBooking, type Booking, bookingsForCustomer, cancelBooking, type CatalogueService,
  customerRecord, type CustomerHit, type DayHours, fetchCatalogue, type FieldOperator,
  listBookings, listBookingStaff, noShowBooking, rescheduleBooking, sentenceFor, suggestByPrefix,
  type VisitRecord, type WeeklyHours, workingHours,
} from '../api';
import { asLocal } from '../phone';
import { digitsOnly } from '../digits';
import type { ScopeBranch } from '../branch-scope';
import { riyals } from '../money';
import { PAYMENT_COLOR, PAYMENT_LABEL, PAYMENT_ORDER, type PaymentStatus } from '../bookingPayment';
import { FilterMenu } from '../rj-ui/FilterMenu';
import type { Session } from '../session';
import { BookingDialog } from './BookingDialog';
import { WorkingHoursDialog } from './WorkingHoursDialog';

// ── display window and snap ─────────────────────────────────────────────────────────────────
// WINDOW_START/WINDOW_END are no longer fixed constants — computed below from the shop's own
// real working hours. The honest default while they load, or for a shop
// that never configured them, stays 08:00–22:00 — the exact fixed window this used to be.
const DEFAULT_WINDOW_START = 8 * 60;
const DEFAULT_WINDOW_END = 22 * 60;
const PX_PER_MIN = 1.85;
const SNAP_MINUTES = 15;        // same grain as the conflict lock

/** `date.weekday()`'s own numbering (0=Monday..6=Sunday) — the same one the server's
 *  `availability.Schedule` uses, from a `YYYY-MM-DD` string with no timezone ambiguity. */
function pyWeekday(dateStr: string): number {
  const jsDay = new Date(`${dateStr}T00:00:00Z`).getUTCDay();   // 0=Sunday..6=Saturday
  return (jsDay + 6) % 7;
}

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
// A YEAR SHOWN ONLY WHEN IT ISN'T THIS ONE. Every date on this screen used to render month+day
// alone — harmless for the day/week grid, which can never leave the current year, but the
// customer-history list can genuinely span years (a booking from last summer, one for next), and
// "23 أغسطس" said nothing about which year it was. Appending the year always would clutter every
// ordinary date with a number that is almost always obvious; appending it only when it differs is
// the same rule a calendar app follows.
function withYear(y: number, rendered: string): string {
  return y === new Date().getFullYear() ? rendered : `${rendered} ${y}`;
}
function humanDate(date: string): string {
  const [y, m, d] = date.split('-').map(Number);
  const dt = new Date(Date.UTC(y, m - 1, d));
  return withYear(y, `${WEEKDAYS[dt.getUTCDay()]} ${d} ${MONTHS[m - 1]}`);
}
function shortDate(date: string): string {
  const [y, m, d] = date.split('-').map(Number);
  return withYear(y, `${d} ${MONTHS[m - 1]}`);
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
  // A SEPARATE AXIS FROM `view` ON PURPOSE — `view` decides WHAT DATA is loaded (one day vs a
  // week of seven), `layout` decides only HOW it is drawn. Neither filters, search, the picked
  // date, nor `view` itself resets when this changes — the same data, read a different way, is
  // the whole point of a second layout (Pencil & Paper / Mobiscroll's own scheduler-switching
  // guidance: a view switch that silently drops the filter or the date is the #1 complaint about
  // multi-view schedulers). `grid` stays the field default; `list` is the scan-and-search shape.
  const [layout, setLayout] = useState<'grid' | 'list'>('grid');
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
  // أوقات الدوام — سياسة واحدة للمنشأة كلها. `undefined` = لسه ما وصلت، تُعامل
  // كنافذة ٨-٢٢ الافتراضية القديمة ريثما تصل، عشان الشبكة ما تومض فاضية أول ما تُفتح الشاشة.
  const [weekly, setWeekly] = useState<WeeklyHours | undefined>(undefined);
  const [hoursDialogOpen, setHoursDialogOpen] = useState(false);
  useEffect(() => {
    workingHours(session).then((r) => setWeekly(r.weekly)).catch(() => setWeekly(undefined));
  }, [session]);
  /** ذاك اليوم بالضبط — مفتوح بوقته المضبوط، أو الافتراضي ريثما تصل الإعدادات. */
  const dayEntry = (dateStr: string): DayHours => {
    const entry = weekly?.[String(pyWeekday(dateStr))];
    return entry ?? { closed: false, start_minute: DEFAULT_WINDOW_START, end_minute: DEFAULT_WINDOW_END };
  };
  const [note, setNote] = useState<string | null>(null);
  const [undo, setUndo] = useState<UndoState | null>(null);
  // A CARD GROWS LOUDER, NOTHING EVER POPS UP — the operator must be able to close it out
  // without being interrupted by it. `now` ticks once a minute — a card whose whole appointment window has already
  // passed and is still «booked» is unclosed, and it reads that way from a glance the moment
  // this re-renders, with no polling loop or alert of its own.
  const [now, setNow] = useState(() => Math.floor(Date.now() / 1000));
  useEffect(() => {
    const id = window.setInterval(() => setNow(Math.floor(Date.now() / 1000)), 60_000);
    return () => window.clearInterval(id);
  }, []);
  // A COUNT, NOT A BOOLEAN — dismissing hides the banner only until a genuinely NEW overdue
  // booking appears (the count grows past what he last dismissed); a booking closing and
  // another going overdue later at the same total count stays quiet, same as any dismissal.
  const [overdueDismissedAt, setOverdueDismissedAt] = useState(0);
  useEffect(() => { setOverdueDismissedAt(0); }, [date]);
  // FILTERS, NOT SEARCH — a shop reads this grid a hundred times a day; typing a name is a
  // request nobody asked to make when the same narrowing is three taps away as a chip.
  const [filterServices, setFilterServices] = useState<string[]>([]);   // [] = every service
  const [filterPayment, setFilterPayment] = useState<'any' | PaymentStatus>('any');
  const [filtersOpen, setFiltersOpen] = useState(false);
  // البحث بالبادئة — عاد بعد إصدار المنصة v0.16.24 (2026-08-19)، الذي حمل المسار الداخلي
  // /internal/search/suggest الذي كان ناقصاً منذ يوم بُنيت هذه الميزة.
  const [phoneQuery, setPhoneQuery] = useState('');
  const [phoneMatches, setPhoneMatches] = useState<CustomerHit[] | null>([]);
  const [filterCustomer, setFilterCustomer] = useState<CustomerHit | null>(null);

  useEffect(() => {
    if (filterCustomer || phoneQuery.length < 3) { setPhoneMatches([]); return; }
    let stale = false;
    const id = window.setTimeout(() => {
      suggestByPrefix(session, phoneQuery).then((rows) => { if (!stale) setPhoneMatches(rows); })
        .catch(() => { if (!stale) setPhoneMatches(null); });
    }, 180);
    return () => { stale = true; window.clearTimeout(id); };
  }, [phoneQuery, filterCustomer, session]);

  // PICKING A CUSTOMER BY PHONE ANSWERS A DIFFERENT QUESTION THAN THE GRID DOES. A receptionist
  // typing a number is not narrowing today's board — she has someone in front of her asking
  // "متى موعدي الجاي؟", and the answer is every appointment ahead of him, on any date, at any
  // branch, not just what happens to be loaded for the day or week currently on screen. So this
  // switches to the list layout on its own and reads `bookings.for-customer` — a real, already-
  // built, cross-date, cross-branch endpoint (`bookings_for_customer` in operations.py: "a
  // customer's OWN history is his across every branch he was ever served at") that nothing in
  // the console had ever called before this.
  //
  // undefined = reading; null = the read failed; an array = his whole history, exactly as the
  // endpoint returns it (newest-first, any status) — ONE fetch, and «القادمة»/«السابقة» below are
  // two ways of slicing the same answer rather than two reads.
  const [customerAll, setCustomerAll] = useState<Booking[] | null | undefined>(undefined);
  // A WALK-IN NEVER TOUCHES `bookings` AT ALL (verified against services/operations directly,
  // not assumed) — the two services share no table, and the only link runs one way, from a
  // booking's own `visit_id` once it is attended. "متى آخر مرة جاء؟" needs BOTH: every booking he
  // ever had here AND every walk-in visit that was never a booking at all — from
  // `GET /field/customers/{id}`, verified against the real route (not the `/customers/{id}` a
  // first pass mis-read) and its own 38 passing unit tests before building on it.
  const [customerVisits, setCustomerVisits] = useState<VisitRecord[] | null | undefined>(undefined);
  // DEFAULTS TO WHAT'S COMING, NEVER TO HIS PAST — a receptionist reaches for this to answer
  // "متى موعدي الجاي؟", not to audit him. Past appointments are one tap away, never open by
  // default: an option he reaches for stays out of his way until he actually wants it.
  const [customerHistoryMode, setCustomerHistoryMode] = useState<'upcoming' | 'past'>('upcoming');
  useEffect(() => {
    setCustomerHistoryMode('upcoming');
    if (!filterCustomer) { setCustomerAll(undefined); setCustomerVisits(undefined); return; }
    setLayout('list');
    setCustomerAll(undefined);
    setCustomerVisits(undefined);
    let stale = false;
    bookingsForCustomer(session, filterCustomer.id)
      .then((r) => { if (!stale) setCustomerAll(r.bookings); })
      .catch(() => { if (!stale) setCustomerAll(null); });
    // ITS OWN FAILURE, SEPARATE FROM THE BOOKINGS READ — a walk-in service outage must not blank
    // out his real upcoming/past bookings, which came back fine from a different service.
    customerRecord(session, filterCustomer.id)
      .then((r) => { if (!stale) setCustomerVisits(r.visits); })
      .catch(() => { if (!stale) setCustomerVisits(null); });
    return () => { stale = true; };
  }, [filterCustomer, session]);

  const customerDisplayed = useMemo(() => {
    if (!customerAll) return customerAll;
    const todayStart = epochAt(todayLocal(), 0);
    if (customerHistoryMode === 'upcoming') {
      // BOOKED ONLY, TODAY ONWARD — a cancelled booking with a future timestamp is not an
      // appointment to confirm at the counter, so it is filtered out rather than trusted at
      // face value. Soonest first: the one he is actually about to ask you to confirm.
      return customerAll.filter((b) => b.status === 'booked' && b.starts_at >= todayStart)
        .sort((a, b) => a.starts_at - b.starts_at);
    }
    // PAST, EVERY STATUS — "آخر موعد لك كان..." is a fact about what actually happened, and a
    // no-show or a cancellation is still part of that answer, not a reason to hide the row. The
    // endpoint already sorts newest-first, so no re-sort is needed here — only the slice.
    return customerAll.filter((b) => b.starts_at < todayStart);
  }, [customerAll, customerHistoryMode]);

  // THE MERGED PAST — bookings that already happened AND walk-in visits, one timeline, newest
  // first. Nothing here is invented: a visit stays a visit (no status pill — it was never
  // scheduled, so there is no "attended/no-show" to say about it), a booking stays a booking.
  // `null` only once BOTH reads have failed; one failing while the other succeeded is still a
  // real, partial answer worth showing rather than discarding.
  const pastEntries = useMemo(() => {
    if (customerHistoryMode !== 'past') return undefined;
    if (customerDisplayed === null && customerVisits === null) return null;
    if (customerDisplayed === undefined || customerVisits === undefined) return undefined;
    const fromBookings = (customerDisplayed ?? [])
      .map((b) => ({ kind: 'booking' as const, time: b.starts_at, booking: b }));
    const fromVisits = (customerVisits ?? [])
      .map((v) => ({ kind: 'visit' as const, time: v.occurred_at, visit: v }));
    return [...fromBookings, ...fromVisits].sort((a, b) => b.time - a.time);
  }, [customerHistoryMode, customerDisplayed, customerVisits]);

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
  // THE SAME NUMBER THE DIALOG ITSELF SHOWS — the booking's own override when it was negotiated,
  // otherwise the catalogue's sum for whatever services it holds. `null` when neither says
  // anything (no override, and no service on the card carries a price) — the card then shows no
  // number rather than a confident-looking "0".
  const priceMinorOf = useMemo(() => {
    const m = new Map((services ?? []).map((s) => [s.id, s.price_minor ?? 0]));
    return (b: Booking): number | null => {
      if (b.price_override_minor !== null && b.price_override_minor !== undefined) {
        return b.price_override_minor;
      }
      const sum = b.service_ids.reduce((total, id) => total + (m.get(id) ?? 0), 0);
      return sum > 0 ? sum : null;
    };
  }, [services]);

  const visible = useMemo(() => {
    return (rows ?? []).filter((b) => {
      if (filterServices.length && !b.service_ids.some((id) => filterServices.includes(id))) return false;
      if (filterPayment !== 'any' && b.payment_status !== filterPayment) return false;
      if (filterCustomer && b.customer_id !== filterCustomer.id) return false;
      return true;
    });
  }, [rows, filterServices, filterPayment, filterCustomer]);

  const activeFilterCount =
    filterServices.length + (filterPayment !== 'any' ? 1 : 0) + (filterCustomer ? 1 : 0);

  // MINUTES PAST THE WHOLE APPOINTMENT WINDOW, NOT PAST ITS START — a booking still inside its
  // own duration is simply happening, not overdue. 0 (or negative) means "not overdue yet".
  const overdueMinutes = (b: Booking): number => {
    if (b.status !== 'booked') return 0;
    const pastBy = now - (b.starts_at + b.duration_minutes * 60);
    return pastBy > 0 ? Math.floor(pastBy / 60) : 0;
  };
  const overdueBookings = useMemo(
    () => (rows ?? []).filter((b) => overdueMinutes(b) > 0)
      .sort((a, b2) => a.starts_at - b2.starts_at),
    [rows, now],
  );

  // ── columns: staff in day view, days in week view ───────────────────────────────────────────
  const columns = view === 'day'
    ? staffHere.map((o) => ({ key: o.id, label: o.name, date }))
    // DAY NUMBER ONLY, NO MONTH — a week column is a fraction of the grid's own width, and the
    // range header above already states the month ("16 أغسطس – 22 أغسطس"). Repeating it in seven
    // narrow columns was what forced "الأحد 16 أغسط…" to truncate before the day number even
    // finished rendering — the one number the column actually needs to say.
    : daysToLoad.map((d) => ({ key: d, label: `${WEEKDAYS[new Date(`${d}T00:00:00Z`).getUTCDay()]} ${Number(d.split('-')[2])}`, date: d }));

  // النافذة الرأسية — يوم واحد: دوامه هو بالضبط. أسبوع: محور مشترك واحد (أوسع دوام بين كل أيامه)،
  // لأن مقياساً مختلفاً لكل عمود يخلي نفس الموضع الرأسي يعني وقتاً مختلفاً من عمود لعمود، وهذا
  // تشويش أسوأ من الحل نفسه. الأيام المغلقة داخل هذا المحور المشترك تُعتَّم
  // بصرياً بدل ما تُقصَّر — أضيق نافذة ممكنة أعوج من قراءة صحيحة.
  const isDayClosed = view === 'day' && dayEntry(date).closed;
  const { WINDOW_START, WINDOW_END } = useMemo(() => {
    if (view === 'day') {
      const e = dayEntry(date);
      return e.closed
        ? { WINDOW_START: DEFAULT_WINDOW_START, WINDOW_END: DEFAULT_WINDOW_END }
        : { WINDOW_START: e.start_minute, WINDOW_END: e.end_minute };
    }
    const open = daysToLoad.map(dayEntry).filter((e) => !e.closed);
    if (open.length === 0) return { WINDOW_START: DEFAULT_WINDOW_START, WINDOW_END: DEFAULT_WINDOW_END };
    return {
      WINDOW_START: Math.min(...open.map((e) => e.start_minute)),
      WINDOW_END: Math.max(...open.map((e) => e.end_minute)),
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [view, date, daysToLoad, weekly]);
  const WINDOW_LEN = WINDOW_END - WINDOW_START;

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
                         className="text-xs font-medium" style={{ color: 'var(--rj-accent-deep)' }}>
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
          </div>

          {/* اليوم/الأسبوع وزر الإعدادات على نفس خط الفلاتر — صف تحكّم
              واحد بدل صفّين، بدل ما يتفرّق التحكّم بالعرض عن التحكّم بالمحتوى. */}
          <div className="flex flex-wrap items-center gap-3">
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

            {/* GRID vs LIST — a separate control from يوم/أسبوع above, because it changes only
                how the same read is drawn. Icon-only (كالإعدادات بجانبه) fits the toolbar's own
                width budget; each carries its own aria-label and title for the first-time case
                an icon alone does not explain itself. */}
            <div className="flex items-center gap-1 rounded-full p-1 shadow-sm" style={{ background: 'var(--rj-surface)' }}>
              {([
                { id: 'grid' as const, icon: LayoutGrid, label: 'عرض الشبكة' },
                { id: 'list' as const, icon: List, label: 'عرض القائمة' },
              ]).map(({ id, icon: Icon, label }) => (
                <button key={id} type="button" onClick={() => setLayout(id)}
                       aria-label={label} title={label}
                       className="grid h-7 w-9 place-items-center rounded-full transition-colors"
                       style={id === layout
                         ? { background: 'var(--rj-ink)', color: 'var(--rj-bg)' }
                         : { color: 'var(--rj-ink-soft)' }}>
                  <Icon size={15} aria-hidden />
                </button>
              ))}
            </div>

            <button type="button" onClick={() => setHoursDialogOpen(true)}
                   aria-label="أوقات الدوام" title="أوقات الدوام"
                   className="grid h-9 w-9 place-items-center rounded-full shadow-sm transition-transform active:scale-90"
                   style={{ background: 'var(--rj-surface)' }}>
              <Settings size={16} aria-hidden />
            </button>

            {branches.length > 1 ? (
              <div className="flex flex-wrap items-center gap-1.5">
                {branches.map((b) => (
                  <button key={b.id} type="button" onClick={() => onBranch(b.id)}
                         className="rounded-full px-3 py-1 text-xs font-medium transition-colors"
                         style={b.id === activeBranch
                           ? { background: 'var(--rj-accent-soft)', color: 'var(--rj-accent-deep)' }
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
            <div className="hidden items-center gap-2 sm:flex">
              <PhoneLookup phoneQuery={phoneQuery} setPhoneQuery={setPhoneQuery}
                          phoneMatches={phoneMatches} filterCustomer={filterCustomer}
                          setFilterCustomer={setFilterCustomer} />
              <FilterMenu label="الخدمة" options={(services ?? []).map((s) => ({ value: s.id, label: s.name }))}
                         selected={filterServices} onChange={setFilterServices} />
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
                <button type="button" onClick={() => { setFilterServices([]); setFilterPayment('any'); setFilterCustomer(null); setPhoneQuery(''); }}
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
                       background: activeFilterCount ? 'var(--rj-accent-soft)' : 'var(--rj-surface)',
                       color: activeFilterCount ? 'var(--rj-accent-deep)' : 'var(--rj-ink)',
                     }}>
                <Filter size={14} aria-hidden />
                فلاتر
                {activeFilterCount ? (
                  <span className="grid h-4 w-4 place-items-center rounded-full text-[10px] font-bold"
                       style={{ background: 'var(--rj-accent)', color: 'var(--rj-ink)' }}>
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
                    <span className="text-xs font-semibold" style={{ color: 'var(--rj-ink-soft)' }}>جوّال العميل</span>
                    <PhoneLookup phoneQuery={phoneQuery} setPhoneQuery={setPhoneQuery}
                                phoneMatches={phoneMatches} filterCustomer={filterCustomer}
                                setFilterCustomer={setFilterCustomer} full />
                  </div>
                  <div className="flex flex-col gap-1.5">
                    <span className="text-xs font-semibold" style={{ color: 'var(--rj-ink-soft)' }}>الخدمة</span>
                    <FilterMenu label="الخدمة" options={(services ?? []).map((s) => ({ value: s.id, label: s.name }))}
                               selected={filterServices} onChange={setFilterServices} className="w-full" />
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
                    <button type="button" onClick={() => { setFilterServices([]); setFilterPayment('any'); setFilterCustomer(null); setPhoneQuery(''); }}
                           className="text-xs font-medium underline" style={{ color: 'var(--rj-accent-deep)' }}>
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

      {/* ONE BANNER, ONCE — never a popup, never repeats itself while he keeps this screen open.
          A tap either opens the earliest overdue card directly or folds the banner away; either
          way it does not reappear this session unless the list of overdue bookings actually
          changes (a fresh minute tick that finds a NEW one un-dismisses it, since that is a
          genuinely new fact, not the same nag repeating). */}
      {overdueBookings.length > overdueDismissedAt ? (
        <div className="mx-auto flex max-w-[1400px] items-center gap-3 px-4 pt-3 sm:px-6">
          <div className="flex flex-1 items-center gap-2 rounded-2xl px-4 py-2.5 text-sm font-medium shadow-sm"
              style={{ background: 'var(--rj-noshow-soft)', color: 'var(--rj-noshow)' }}>
            <span className="flex-1">
              {overdueBookings.length === 1
                ? 'حجزٌ واحد فات وقته ولم يُغلق بعد.'
                : `${overdueBookings.length} حجوزات فات وقتها ولم تُغلق بعد.`}
            </span>
            <button type="button" onClick={() => setOpenBooking(overdueBookings[0])}
                   className="rounded-full px-3 py-1 text-xs font-semibold shadow-sm"
                   style={{ background: 'var(--rj-noshow)', color: 'var(--rj-bg)' }}>
              افتح الأقدم
            </button>
            <button type="button" aria-label="إخفاء" onClick={() => setOverdueDismissedAt(overdueBookings.length)}
                   className="grid h-6 w-6 shrink-0 place-items-center rounded-full">
              <X size={13} aria-hidden />
            </button>
          </div>
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
                   style={{ color: 'var(--rj-accent-deep)' }}>حاول مجدداً</button>
          </div>
        ) : layout === 'list' && filterCustomer ? (
          // A CUSTOMER PICKED BY PHONE ANSWERS "متى موعده الجاي؟" — every booked appointment
          // ahead of him, any date, any branch, not the day or week currently loaded. Its own
          // loading/failed states, separate from the grid's — a different read (`for-customer`,
          // not `listBookings`), so it can be in flight or fail independently of it.
          customerAll === undefined ? (
            <div className="grid place-items-center py-24 text-sm" style={{ color: 'var(--rj-ink-soft)' }}>
              يُحمَّل سجل العميل…
            </div>
          ) : customerAll === null ? (
            <div className="grid place-items-center gap-2 py-24 text-center">
              <p className="text-base font-medium">تعذّرت قراءة مواعيد العميل</p>
              <button type="button" onClick={() => setFilterCustomer({ ...filterCustomer })}
                     className="text-sm font-medium underline" style={{ color: 'var(--rj-accent-deep)' }}>
                حاول مجدداً
              </button>
            </div>
          ) : (
            <div className="flex flex-col gap-3">
              {/* AN OPTION HE REACHES FOR, NOT ONE ALREADY OPEN IN HIS FACE — «القادمة» stays the
                  default every time a new customer is picked; «السابقة» is one tap away for
                  "آخر موعد لك كان؟", shown newest-first once he asks for it. */}
              <div className="flex items-center gap-1 self-start rounded-full p-1 shadow-sm" style={{ background: 'var(--rj-surface)' }}>
                {([
                  { id: 'upcoming' as const, label: 'القادمة' },
                  { id: 'past' as const, label: 'السابقة' },
                ]).map(({ id, label }) => (
                  <button key={id} type="button" onClick={() => setCustomerHistoryMode(id)}
                         className="rounded-full px-3 py-1 text-xs font-medium transition-colors"
                         style={id === customerHistoryMode
                           ? { background: 'var(--rj-ink)', color: 'var(--rj-bg)' }
                           : { color: 'var(--rj-ink-soft)' }}>
                    {label}
                  </button>
                ))}
              </div>
              {customerHistoryMode === 'upcoming' ? (
                <BookingsList rows={customerDisplayed ?? []} nameOf={nameOf} serviceNameOf={serviceNameOf}
                             priceMinorOf={priceMinorOf} onOpen={setOpenBooking}
                             emptyMessage={`ما عند ${filterCustomer.name || asLocal(filterCustomer.phone)} أي موعد قادم.`} />
              ) : pastEntries === undefined ? (
                <div className="grid place-items-center py-24 text-sm" style={{ color: 'var(--rj-ink-soft)' }}>
                  يُحمَّل سجل زياراته…
                </div>
              ) : pastEntries === null ? (
                <div className="grid place-items-center gap-2 py-24 text-center">
                  <p className="text-base font-medium">تعذّرت قراءة سجله بالكامل</p>
                  <button type="button" onClick={() => setFilterCustomer({ ...filterCustomer })}
                         className="text-sm font-medium underline" style={{ color: 'var(--rj-accent-deep)' }}>
                    حاول مجدداً
                  </button>
                </div>
              ) : (
                <CustomerHistoryList entries={pastEntries} nameOf={nameOf} serviceNameOf={serviceNameOf}
                             priceMinorOf={priceMinorOf} onOpenBooking={setOpenBooking}
                             emptyMessage={`ما عند ${filterCustomer.name || asLocal(filterCustomer.phone)} مواعيد أو زيارات سابقة.`} />
              )}
            </div>
          )
        ) : layout === 'list' ? (
          // A FLAT LIST NEEDS NONE OF THE GRID'S OWN GEOMETRY — no staff-as-columns, no working
          // hours, no "المحل مغلق" (a closed day simply has no rows, and an empty list already
          // says so). It reads straight off `visible` — the SAME filtered array the grid draws
          // from, so nothing here can disagree with the grid about which bookings match.
          <BookingsList rows={visible} nameOf={nameOf} serviceNameOf={serviceNameOf}
                       priceMinorOf={priceMinorOf} onOpen={setOpenBooking} />
        ) : view === 'day' && staff === null ? (
          <div className="grid place-items-center gap-2 py-24 text-center">
            <p className="text-base font-medium">تعذّرت قراءة فريق العمل</p>
            <button type="button" onClick={() => listBookingStaff(session).then(setStaff).catch(() => setStaff(null))}
                   className="text-sm font-medium underline" style={{ color: 'var(--rj-accent-deep)' }}>
              حاول مجدداً
            </button>
          </div>
        ) : columns.length === 0 ? (
          <div className="grid place-items-center py-24 text-sm" style={{ color: 'var(--rj-ink-soft)' }}>
            لا موظفون نشِطون في هذا الفرع بعد.
          </div>
        ) : isDayClosed ? (
          <div className="grid place-items-center gap-2 py-24 text-center text-sm" style={{ color: 'var(--rj-ink-soft)' }}>
            <p className="text-base font-semibold" style={{ color: 'var(--rj-ink)' }}>المحل مغلق هذا اليوم</p>
            <p>يمكنك ضبط أوقات الدوام من الزر أعلى الشاشة.</p>
          </div>
        ) : (
          <div data-testid="rj-grid"
              className={view === 'week' ? 'rj-card rounded-[28px] p-2' : 'rj-card overflow-x-auto rounded-[28px] p-2'}
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
                  >
                    {/* أيام مغلقة أو خارج دوامها ضمن المحور المشترك — تُعتَّم لا تُقصَّر، عشان
                        نفس الموضع الرأسي يبقى يعني نفس الوقت في كل الأعمدة. */}
                    {view === 'week' ? (() => {
                      const e = dayEntry(col.date);
                      if (e.closed) {
                        return (
                          <div className="pointer-events-none absolute inset-0"
                              style={{ background: 'rgba(19,18,38,0.06)' }} />
                        );
                      }
                      return (
                        <>
                          {e.start_minute > WINDOW_START ? (
                            <div className="pointer-events-none absolute inset-x-0 top-0"
                                style={{ height: (e.start_minute - WINDOW_START) * PX_PER_MIN,
                                        background: 'rgba(19,18,38,0.06)' }} />
                          ) : null}
                          {e.end_minute < WINDOW_END ? (
                            <div className="pointer-events-none absolute inset-x-0 bottom-0"
                                style={{ height: (WINDOW_END - e.end_minute) * PX_PER_MIN,
                                        background: 'rgba(19,18,38,0.06)' }} />
                          ) : null}
                        </>
                      );
                    })() : null}
                    {/* REAL CELLS NOW, NOT JUST LINES — each quarter-hour used to be a zero-height
                        border with no way to tell it was clickable except by clicking it. A cell
                        that only reveals itself on contact is not an affordance; it is a guess
                        that happened to be right. Every band now lights up and names its own time
                        on hover — the same "this is pressable" cue a button gives, at the exact
                        grain SNAP_MINUTES already snaps every drop to. The click itself moved
                        here too, off the column's own onClick: a cell knows its own minute
                        precisely, so this is a snap to what was actually pressed, not pixel math
                        against the pointer's Y. */}
                    {Array.from({ length: WINDOW_LEN / 15 }, (_, i) => WINDOW_START + i * 15).map((m) => (
                      <button
                        key={m}
                        type="button"
                        tabIndex={-1}
                        className="group absolute inset-x-0 cursor-pointer border-t text-start transition-colors duration-100 hover:bg-[var(--rj-accent-soft)]"
                        style={{
                          top: (m - WINDOW_START) * PX_PER_MIN,
                          height: 15 * PX_PER_MIN,
                          borderColor: m % 60 === 0
                            ? 'var(--rj-line)'
                            : 'color-mix(in srgb, var(--rj-line) 40%, transparent)',
                        }}
                        onClick={() => {
                          if (moving) { commitMove(moving.booking, col.key, m); setMoving(null); return; }
                          setDialog({ operatorId: view === 'day' ? col.key : weekStaffId,
                                     startsAt: epochAt(col.date, m) });
                        }}
                      >
                        <span
                          className="pointer-events-none absolute inset-inline-end-1.5 top-1/2 hidden -translate-y-1/2 whitespace-nowrap rounded-full px-1.5 py-0.5 text-[9px] font-bold shadow-sm group-hover:block"
                          style={{ background: 'var(--rj-accent-deep)', color: '#ffffff' }}>
                          {timeLabel(m)}
                        </span>
                      </button>
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
                      // LOUDER THE LONGER IT WAITS, NEVER A POPUP — a hairline past the window,
                      // a solid ring past the half-hour, matching the no-show colour on purpose:
                      // an unclosed card is exactly the outcome that colour already means.
                      const overdue = overdueMinutes(b);
                      const overdueRing = overdue > 60 ? '3px' : overdue > 30 ? '2px' : overdue > 0 ? '1px' : '0px';
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
                          className={`rj-card rj-card-settle absolute cursor-grab overflow-hidden rounded-xl px-2.5 py-1.5 text-start transition-shadow active:cursor-grabbing ${drag?.booking.id === b.id ? 'rj-card-dragging' : ''} ${isBeingMoved ? 'ring-2 ring-offset-1' : ''}`}
                          style={{
                            // A REAL GAP, NOT A HAIRLINE — 1-2px read as touching when cards
                            // stack with no visible margin between them. 4px top and bottom is a real breath between cards.
                            top: top + 4, height: Math.max(26, height - 8),
                            insetInlineStart: `calc(${lane * laneWidth}% + ${lane ? 3 : 4}px)`,
                            width: `calc(${laneWidth}% - ${lanes > 1 ? 6 : 8}px)`,
                            background: tone.bg, color: tone.fg,
                            // A SOLID STRIPE, NOT JUST A TINTED BOX — a flat wash of the status
                            // colour was the whole card, which reads as one undifferentiated
                            // block of colour rather than a card WITH a status. A 3px solid edge
                            // in the same colour gives the eye one strong anchor to scan a whole
                            // week of these by, while the tint underneath stays soft enough that
                            // service-name text over it never fights for contrast.
                            borderInlineStart: `3px solid ${tone.fg}`,
                            opacity: drag?.booking.id === b.id ? 0.4 : 1,
                            zIndex: lane + 1,
                            boxShadow: overdue > 0
                              ? `0 0 0 ${overdueRing} var(--rj-noshow)` : undefined,
                            ...(isBeingMoved ? { '--tw-ring-color': 'var(--rj-accent)' } as React.CSSProperties : {}),
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
                          {(() => {
                            // `?? 'none'` — a rolling deploy can serve this exact response from an
                            // older bookings pod that predates payment_status entirely; reading a
                            // missing key as "بدون عربون" is the right default and never crashes
                            // the whole grid over one field one pod has not caught up on yet.
                            const pay = b.payment_status ?? 'none';
                            const price = priceMinorOf(b);
                            // THE NUMBER ITSELF, NOT JUST A DOT'S COLOUR — a tooltip on a 2px dot
                            // never shows on a touch device at all, so the amount itself has to be printed for it to be
                            // legible. عربون shows what was actually taken;
                            // مدفوع shows the booking's own price, when there is one to show.
                            const payLabel = pay === 'deposit' && b.deposit_amount_minor
                              ? `عربون ${riyals(b.deposit_amount_minor)}`
                              : pay === 'paid' && price !== null
                                ? `مدفوع ${riyals(price)}`
                                : pay !== 'none' ? PAYMENT_LABEL[pay] : null;
                            const payPill = payLabel ? (
                              <span
                                className="shrink-0 truncate rounded-full px-1.5 py-px text-[10px] font-bold leading-tight"
                                style={{ background: PAYMENT_COLOR[pay].bg, color: PAYMENT_COLOR[pay].fg }}>
                                {payLabel}
                              </span>
                            ) : null;
                            // A STAR BESIDE THE PILL — a customer waiting on a reward is a
                            // different fact from one who paid a deposit. Still present on an
                            // attended booking means the spend failed or needed an approval
                            // attend() could not give (see the field's own note) — the same
                            // glance now reads "still owed".
                            const rewardPill = b.intended_reward_id ? (
                              <span aria-hidden title="جائزة بانتظار الاستبدال عند الحضور"
                                   className="text-[10px] leading-none">⭐</span>
                            ) : null;
                            // THE NUMBER ALONE, NOT THE LABEL — a week column is narrow at every
                            // lane count, and truncating "عربون 50" left "عربون…" with the
                            // amount itself cut off, which read as broken rather than merely
                            // compact. The colour
                            // already carries "عربون vs مدفوع" (same PAYMENT_COLOR the filter
                            // chips use); the digits are the one fact a dot's tooltip could never
                            // show on a touch device, so they are what survives the squeeze.
                            const payShort = pay === 'deposit' && b.deposit_amount_minor
                              ? riyals(b.deposit_amount_minor)
                              : pay === 'paid' && price !== null ? riyals(price)
                              : pay !== 'none' ? PAYMENT_LABEL[pay] : null;
                            // FULL LABEL WHEN THERE IS ROOM, THE NUMBER ALONE WHEN THERE IS NOT
                            // — a single-lane day-view card has plenty of width even at this
                            // height (a quick 15-minute service); only week view or a shared
                            // lane is actually this tight.
                            const cramped = view === 'week' || lanes > 1;
                            const payPillShort = (cramped ? payShort : payLabel) ? (
                              <span
                                className="shrink-0 rounded-full px-1.5 py-px text-[10px] font-bold leading-tight"
                                style={{ background: PAYMENT_COLOR[pay].bg, color: PAYMENT_COLOR[pay].fg }}
                                title={cramped ? (payLabel ?? undefined) : undefined}>
                                {cramped ? payShort : payLabel}
                              </span>
                            ) : null;

                            if (height < 30) {
                              // A very short card (a quick service) has no room for a whole pill
                              // ROW, but the payment fact still belongs on it. THE TIME NEVER
                              // TRUNCATES (`shrink-0` of its own, split out of the service name)
                              // — a narrow week column used to squeeze "10:00" itself down to a
                              // stray "…00" beside a pill that then read as disconnected from
                              // anything. The
                              // service name is what gives way now, and the pill shows the
                              // number ALONE (`payPillShort`) rather than a label that truncates
                              // mid-word.
                              return (
                                <div className={`flex items-center gap-1 text-[11px] font-semibold leading-tight ${b.status === 'booked' ? 'ps-3' : ''}`}>
                                  <span className="shrink-0">{timeLabel(minutesOf(b.starts_at))}</span>
                                  <span className="min-w-0 flex-1 truncate">
                                    · {serviceNameOf(b.service_ids) || '—'}
                                  </span>
                                  {payPillShort}
                                  {rewardPill}
                                </div>
                              );
                            }
                            return (
                              <div className={b.status === 'booked' ? 'ps-3' : ''}>
                                <div className="truncate text-xs font-semibold leading-tight">
                                  {timeLabel(minutesOf(b.starts_at))}
                                </div>
                                {/* TAGS, NOT A SENTENCE — a comma-joined line read as a
                                    description of the appointment; each service is its own fact,
                                    and a shop reading the grid needs to pick them out at a
                                    glance, not parse a clause. The payment pill and the reward
                                    star ride the SAME wrapping row, at its end — one place the
                                    eye already goes for every fact about this card, not a
                                    separate corner badge nobody was told to look at. */}
                                <div className="mt-0.5 flex flex-wrap items-center gap-1 overflow-hidden" style={{ maxHeight: height - 20 }}>
                                  {/* TINTED TO THE CARD'S OWN STATUS, NOT A FLAT GREY — a
                                      black-at-8% chip reads as murky on a violet/teal/red tint
                                      instead of on the white it was designed for, which is
                                      exactly the "cheap sticker" look reported directly. Blending
                                      the tone's own colour into white keeps every chip on a card
                                      visibly part of the same card, whatever its status is. */}
                                  {serviceNamesOf(b.service_ids).length > 0
                                    ? serviceNamesOf(b.service_ids).map((name) => (
                                        <span key={name}
                                             className="truncate rounded-full px-1.5 py-px text-[10px] font-medium leading-tight"
                                             style={{
                                               background: `color-mix(in srgb, ${tone.fg} 16%, white)`,
                                               color: tone.fg,
                                               maxWidth: '100%',
                                             }}>
                                          {name}
                                        </span>
                                      ))
                                    : <span className="text-[11px] opacity-80">—</span>}
                                  {payPill}
                                  {rewardPill}
                                </div>
                              </div>
                            );
                          })()}
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
                 style={{ color: 'var(--rj-accent)' }}>تراجع</button>
        </div>
      ) : null}

      {/* touch "move" mode — cancelled by tapping outside any card */}
      {moving ? (
        <div className="fixed inset-x-0 top-20 z-30 mx-auto flex w-fit items-center gap-3 rounded-full px-4 py-2 shadow-lg"
            style={{ background: 'var(--rj-accent)', color: 'var(--rj-ink)' }}>
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
        style={{ background: 'var(--rj-accent)', color: 'var(--rj-ink)' }}
      >
        <Plus size={24} aria-hidden />
      </button>

      {hoursDialogOpen ? (
        <WorkingHoursDialog
          session={session}
          weekly={weekly ?? {}}
          onClose={() => setHoursDialogOpen(false)}
          onSaved={setWeekly}
        />
      ) : null}

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


/** THE COUNTER'S OWN QUESTION, ANSWERED IN ONE FIELD. A customer standing there and asking about
 *  his own appointment gives a phone number, not a query — so this narrows the grid to exactly
 *  his card(s) rather than filtering a list he was never browsing. Once matched, the customer's
 *  own name (and visit count, when the read carries one) shows beside the field, because the
 *  phone number alone does not answer "who is this" the way his name does. */
function PhoneLookup({
  phoneQuery, setPhoneQuery, phoneMatches, filterCustomer, setFilterCustomer, full,
}: {
  phoneQuery: string;
  setPhoneQuery: (v: string) => void;
  phoneMatches: CustomerHit[] | null;
  filterCustomer: CustomerHit | null;
  setFilterCustomer: (c: CustomerHit | null) => void;
  /** The popover's own column layout needs the full width; the inline header row keeps it compact. */
  full?: boolean;
}) {
  if (filterCustomer) {
    return (
      <div className="flex h-9 items-center gap-1.5 rounded-full ps-3 pe-1 text-xs font-medium shadow-sm"
          style={{ background: 'var(--rj-accent-soft)', color: 'var(--rj-accent-deep)' }}>
        <Phone size={12} aria-hidden />
        <span className="truncate">{filterCustomer.name || asLocal(filterCustomer.phone)}</span>
        {typeof filterCustomer.visits === 'number' ? (
          <span className="opacity-70">· {filterCustomer.visits} زيارة</span>
        ) : null}
        <button type="button" aria-label="إلغاء" onClick={() => { setFilterCustomer(null); setPhoneQuery(''); }}
               className="grid h-6 w-6 shrink-0 place-items-center rounded-full"
               style={{ color: 'var(--rj-accent-deep)' }}>
          <X size={12} aria-hidden />
        </button>
      </div>
    );
  }
  return (
    <div className={`relative ${full ? '' : 'w-40'}`}>
      <Phone size={13} aria-hidden
            className="pointer-events-none absolute inset-inline-start-3 top-1/2 -translate-y-1/2"
            style={{ color: 'var(--rj-ink-soft)' }} />
      <input
        value={phoneQuery}
        onChange={(e) => setPhoneQuery(digitsOnly(e.target.value).slice(0, 10))}
        placeholder="جوّال العميل"
        aria-label="ابحث عن حجز عميل بجواله"
        className="h-9 w-full rounded-full py-1.5 ps-9 pe-3 text-xs font-medium shadow-sm outline-none"
        style={{ background: 'var(--rj-surface)', color: 'var(--rj-ink)' }}
      />
      {(phoneMatches ?? []).length > 0 ? (
        <div className="absolute inset-inline-start-0 top-11 z-30 flex w-56 flex-col gap-1 rounded-2xl p-2 shadow-lg"
            style={{ background: 'var(--rj-surface)', border: '1px solid var(--rj-line)' }}>
          {(phoneMatches ?? []).slice(0, 5).map((c) => (
            <button key={c.id} type="button" onClick={() => setFilterCustomer(c)}
                   className="flex items-center justify-between rounded-xl px-2.5 py-1.5 text-start text-sm hover:opacity-80">
              <span dir="ltr" className="tabular-nums">{asLocal(c.phone)}</span>
              <span className="truncate ps-2 text-xs" style={{ color: 'var(--rj-ink-soft)' }}>{c.name || ''}</span>
            </button>
          ))}
        </div>
      ) : null}
    </div>
  );
}

/** THE SCAN-AND-SEARCH SHAPE — one column of time-ordered rows instead of a spatial grid.
 *  Tapping a row opens the SAME `BookingActions` sheet a grid card opens (`onOpen` is just
 *  `setOpenBooking`), so this needed no new action logic at all, only a new way to reach it.
 *  No customer name/phone on the row yet — `Booking` carries only `customer_id`, and there is no
 *  batch id→name resolver in this screen's API surface the way `operations.customers_by_refs`
 *  exists elsewhere; showing a raw id would be worse than not showing one. The phone-lookup
 *  filter chip above the toolbar still narrows this list to one customer's bookings by name —
 *  what is missing here is a name on every OTHER row, a real but separate piece of work. */
function BookingsList({ rows, nameOf, serviceNameOf, priceMinorOf, onOpen, emptyMessage, order = 'asc' }: {
  rows: Booking[];
  nameOf: (id: string) => string;
  serviceNameOf: (ids: string[]) => string;
  priceMinorOf: (b: Booking) => number | null;
  onOpen: (b: Booking) => void;
  /** «لا حجوزات تطابق هذا العرض» is the right sentence for a filtered grid view; a customer's own
   *  upcoming list has a truer one to say when it's empty («ما عنده أي موعد قادم»), so the caller
   *  may override it rather than every empty state reading the same regardless of why. */
  emptyMessage?: string;
  /** `asc` (soonest first) for anything upcoming — the grid, a customer's coming appointments.
   *  `desc` (most recent first) for a customer's PAST ones — "آخر موعد لك كان؟" wants the most
   *  recent past visit at the top, not buried under his oldest one. */
  order?: 'asc' | 'desc';
}) {
  const sorted = useMemo(
    () => [...rows].sort((a, b) => (order === 'desc' ? b.starts_at - a.starts_at : a.starts_at - b.starts_at)),
    [rows, order],
  );

  if (sorted.length === 0) {
    return (
      <div className="grid place-items-center py-24 text-sm" style={{ color: 'var(--rj-ink-soft)' }}>
        {emptyMessage ?? 'لا حجوزات تطابق هذا العرض.'}
      </div>
    );
  }

  let lastDate = '';
  const today = todayLocal();
  return (
    <div data-testid="rj-list" className="rj-card overflow-hidden rounded-[28px]" style={{ background: 'var(--rj-surface)' }}>
      <ul>
        {sorted.map((b) => {
          const dateKey = dateKeyOf(b.starts_at);
          const showDateHeader = dateKey !== lastDate;
          lastDate = dateKey;
          const isToday = dateKey === today;
          const tone = STATUS_VARS[b.status];
          const pay = b.payment_status ?? 'none';
          const price = priceMinorOf(b);
          const payLabel = pay === 'deposit' && b.deposit_amount_minor
            ? `عربون ${riyals(b.deposit_amount_minor)}`
            : pay === 'paid' && price !== null ? `مدفوع ${riyals(price)}`
              : pay !== 'none' ? PAYMENT_LABEL[pay] : null;
          return (
            <li key={b.id}>
              {/* A DAY HEADER ONLY WHEN THE DATE ACTUALLY CHANGES — a single day's list never
                  shows one at all; a week's list gets exactly seven, at the point they occur in
                  time order, never a fixed row per day regardless of whether it holds anything.
                  TODAY GETS THE ACCENT, EVERY OTHER DAY STAYS NEUTRAL — a list spanning many
                  dates (a customer's own history, a week flattened) is read fastest when "is this
                  today?" costs nothing to notice. */}
              {showDateHeader ? (
                <div className="sticky top-0 border-b px-4 pb-1.5 pt-3 text-xs font-semibold"
                    style={isToday
                      ? { borderColor: 'var(--rj-accent-soft)', background: 'var(--rj-accent-soft)', color: 'var(--rj-accent-deep)' }
                      : { borderColor: 'var(--rj-line)', background: 'color-mix(in srgb, var(--rj-surface) 92%, transparent)', color: 'var(--rj-ink-soft)' }}>
                  {isToday ? `اليوم — ${humanDate(dateKey)}` : humanDate(dateKey)}
                </div>
              ) : null}
              {/* AND THE DATE ITSELF, ON EVERY ROW — not only in the header. The header sits
                  `sticky top-0` inside this list's own scroll, but the PAGE (not this box) is
                  what actually scrolls a long customer history, so a header can end up well out
                  of view while its rows are still on screen. A row must never depend on
                  remembering what it scrolled past. */}
              <button type="button" onClick={() => onOpen(b)}
                     className="flex w-full items-center gap-3 border-b px-4 py-3 text-start transition-colors last:border-b-0 hover:brightness-[0.98]"
                     style={{
                       borderColor: 'var(--rj-line)',
                       background: isToday ? 'color-mix(in srgb, var(--rj-accent-soft) 45%, transparent)' : undefined,
                     }}>
                <span className="w-14 shrink-0 text-[11px] font-semibold" style={{ color: isToday ? 'var(--rj-accent-deep)' : 'var(--rj-ink-soft)' }}>
                  {isToday ? 'اليوم' : shortDate(dateKey)}
                </span>
                <span dir="ltr" className="w-14 shrink-0 text-sm font-semibold tabular-nums">{timeLabel(minutesOf(b.starts_at))}</span>
                <span className="min-w-0 flex-1 truncate text-sm">{serviceNameOf(b.service_ids) || '—'}</span>
                <span className="hidden shrink-0 text-xs sm:block" style={{ color: 'var(--rj-ink-soft)' }}>{nameOf(b.operator_id)}</span>
                {payLabel ? (
                  <span className="hidden shrink-0 rounded-full px-2 py-0.5 text-[10px] font-bold sm:inline-block"
                       style={{ background: PAYMENT_COLOR[pay].bg, color: PAYMENT_COLOR[pay].fg }}>
                    {payLabel}
                  </span>
                ) : null}
                <span className="shrink-0 rounded-full px-2 py-0.5 text-[10px] font-bold"
                     style={{ background: tone.bg, color: tone.fg }}>
                  {STATUS_LABEL[b.status]}
                </span>
              </button>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

type PastEntry =
  | { kind: 'booking'; time: number; booking: Booking }
  | { kind: 'visit'; time: number; visit: VisitRecord };

/** THE MERGED TIMELINE — every booking he ever had AND every walk-in visit that was never one,
 *  in one list, because "متى آخر مرة جاء؟" is a question about the customer, not about which of
 *  two services happened to record the answer. A visit row carries no status pill — it was never
 *  scheduled, so there is nothing to say about whether it was "attended"; it simply happened,
 *  which is the entire fact a walk-in visit is. Only booking rows open the action sheet — a
 *  walk-in visit has no booking behind it to act on. */
function CustomerHistoryList({ entries, nameOf, serviceNameOf, priceMinorOf, onOpenBooking, emptyMessage }: {
  entries: PastEntry[];
  nameOf: (id: string) => string;
  serviceNameOf: (ids: string[]) => string;
  priceMinorOf: (b: Booking) => number | null;
  onOpenBooking: (b: Booking) => void;
  emptyMessage?: string;
}) {
  if (entries.length === 0) {
    return (
      <div className="grid place-items-center py-24 text-sm" style={{ color: 'var(--rj-ink-soft)' }}>
        {emptyMessage ?? 'لا شيء هنا.'}
      </div>
    );
  }

  let lastDate = '';
  const today = todayLocal();
  return (
    <div data-testid="rj-history" className="rj-card overflow-hidden rounded-[28px]" style={{ background: 'var(--rj-surface)' }}>
      <ul>
        {entries.map((e) => {
          const dateKey = dateKeyOf(e.time);
          const showDateHeader = dateKey !== lastDate;
          lastDate = dateKey;
          const isToday = dateKey === today;
          const key = e.kind === 'booking' ? e.booking.id : e.visit.id;
          return (
            <li key={key}>
              {showDateHeader ? (
                <div className="sticky top-0 border-b px-4 pb-1.5 pt-3 text-xs font-semibold"
                    style={isToday
                      ? { borderColor: 'var(--rj-accent-soft)', background: 'var(--rj-accent-soft)', color: 'var(--rj-accent-deep)' }
                      : { borderColor: 'var(--rj-line)', background: 'color-mix(in srgb, var(--rj-surface) 92%, transparent)', color: 'var(--rj-ink-soft)' }}>
                  {isToday ? `اليوم — ${humanDate(dateKey)}` : humanDate(dateKey)}
                </div>
              ) : null}
              {e.kind === 'visit' ? (
                // NOT A BUTTON — there is no action sheet behind a walk-in, on purpose.
                <div className="flex w-full items-center gap-3 border-b px-4 py-3 last:border-b-0"
                    style={{ borderColor: 'var(--rj-line)', background: isToday ? 'color-mix(in srgb, var(--rj-accent-soft) 45%, transparent)' : undefined }}>
                  <span className="w-14 shrink-0 text-[11px] font-semibold" style={{ color: isToday ? 'var(--rj-accent-deep)' : 'var(--rj-ink-soft)' }}>
                    {isToday ? 'اليوم' : shortDate(dateKey)}
                  </span>
                  <span dir="ltr" className="w-14 shrink-0 text-sm font-semibold tabular-nums">{timeLabel(minutesOf(e.time))}</span>
                  <span className="min-w-0 flex-1 truncate text-sm">{e.visit.services || e.visit.custom_service || '—'}</span>
                  <span className="shrink-0 rounded-full px-2 py-0.5 text-[10px] font-bold"
                       style={{ background: 'var(--rj-cancelled-soft)', color: 'var(--rj-ink-soft)' }}>
                    زيارة
                  </span>
                </div>
              ) : (() => {
                const b = e.booking;
                const tone = STATUS_VARS[b.status];
                const pay = b.payment_status ?? 'none';
                const price = priceMinorOf(b);
                const payLabel = pay === 'deposit' && b.deposit_amount_minor
                  ? `عربون ${riyals(b.deposit_amount_minor)}`
                  : pay === 'paid' && price !== null ? `مدفوع ${riyals(price)}`
                    : pay !== 'none' ? PAYMENT_LABEL[pay] : null;
                return (
                  <button type="button" onClick={() => onOpenBooking(b)}
                         className="flex w-full items-center gap-3 border-b px-4 py-3 text-start transition-colors last:border-b-0 hover:brightness-[0.98]"
                         style={{ borderColor: 'var(--rj-line)', background: isToday ? 'color-mix(in srgb, var(--rj-accent-soft) 45%, transparent)' : undefined }}>
                    <span className="w-14 shrink-0 text-[11px] font-semibold" style={{ color: isToday ? 'var(--rj-accent-deep)' : 'var(--rj-ink-soft)' }}>
                      {isToday ? 'اليوم' : shortDate(dateKey)}
                    </span>
                    <span dir="ltr" className="w-14 shrink-0 text-sm font-semibold tabular-nums">{timeLabel(minutesOf(b.starts_at))}</span>
                    <span className="min-w-0 flex-1 truncate text-sm">{serviceNameOf(b.service_ids) || '—'}</span>
                    <span className="hidden shrink-0 text-xs sm:block" style={{ color: 'var(--rj-ink-soft)' }}>{nameOf(b.operator_id)}</span>
                    {payLabel ? (
                      <span className="hidden shrink-0 rounded-full px-2 py-0.5 text-[10px] font-bold sm:inline-block"
                           style={{ background: PAYMENT_COLOR[pay].bg, color: PAYMENT_COLOR[pay].fg }}>
                        {payLabel}
                      </span>
                    ) : null}
                    <span className="shrink-0 rounded-full px-2 py-0.5 text-[10px] font-bold"
                         style={{ background: tone.bg, color: tone.fg }}>
                      {STATUS_LABEL[b.status]}
                    </span>
                  </button>
                );
              })()}
            </li>
          );
        })}
      </ul>
    </div>
  );
}

/** A small action sheet opened by tapping a card — attend / no-show / cancel, in the grid's own
 *  visual identity. Closing a booking as attended offers "احجزي الجلسة القادمة" (§2.7) when the
 *  service has a real cycle — the sleeping field `cycle_days` already in the catalogue, used for
 *  its own purpose rather than reinvented. */
function BookingActions({ booking, operatorLabel, services, onClose, onChanged,
                         onBookNext, onEdit, session, say }: {
  booking: Booking; operatorLabel: string; services: CatalogueService[];
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
  // THE SAME NUMBER THE CARD AND THE DIALOG ITSELF SHOW — the booking's own override when it
  // was negotiated, otherwise the catalogue's sum for whatever services it holds.
  const priceMinor = booking.price_override_minor ?? (() => {
    const sum = booking.service_ids.reduce(
      (total, id) => total + (services.find((s) => s.id === id)?.price_minor ?? 0), 0);
    return sum > 0 ? sum : null;
  })();
  const pay = booking.payment_status ?? 'none';
  const serviceNames = booking.service_ids.map((id) => services.find((s) => s.id === id)?.name ?? id);

  if (attended) {
    return (
      <div className="rj-grid fixed inset-0 z-40 flex items-end justify-center sm:items-center"
          onClick={onClose}>
        <div className="absolute inset-0" style={{ background: 'rgba(19,18,38,0.35)' }} />
        <div onClick={(e) => e.stopPropagation()}
            className="relative w-full max-w-sm rounded-t-[28px] p-5 sm:rounded-[28px]"
            style={{ background: 'var(--rj-surface)', boxShadow: 'var(--rj-shadow-lift)' }}>
          <p className="mb-3 text-base font-semibold">سُجّل الحضور ✓</p>
          {cycleDays > 0 ? (
            <button type="button" onClick={() => onBookNext(attended)}
                   className="w-full rounded-2xl py-3 text-sm font-semibold"
                   style={{ background: 'var(--rj-accent-soft)', color: 'var(--rj-accent-deep)' }}>
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
      <div className="absolute inset-0" style={{ background: 'rgba(19,18,38,0.35)' }} />
      <div onClick={(e) => e.stopPropagation()}
          className="relative w-full max-w-sm rounded-t-[28px] p-5 sm:rounded-[28px]"
          style={{ background: 'var(--rj-surface)', boxShadow: 'var(--rj-shadow-lift)' }}>
        {/* التفاصيل أولاً — كل ما يحتاجه قبل يقرر، لا بعد ما يضغط: تُعرض الخدمات والوقت
            وغيرها من التفاصيل قبل أي إجراء. */}
        <div className="mb-4 flex items-start justify-between gap-3">
          <div className="flex flex-col gap-2">
            <div className="flex flex-wrap gap-1">
              {serviceNames.map((name, i) => (
                <span key={`${name}-${i}`}
                     className="truncate rounded-full px-2 py-0.5 text-xs font-semibold"
                     style={{ background: 'var(--rj-line)', color: 'var(--rj-ink)' }}>
                  {name}
                </span>
              ))}
            </div>
            <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-sm" style={{ color: 'var(--rj-ink-soft)' }}>
              <span className="flex items-center gap-1">
                <Calendar size={13} aria-hidden />
                {humanDate(dateKeyOf(booking.starts_at))}
              </span>
              <span className="flex items-center gap-1">
                <Clock size={13} aria-hidden />
                {timeLabel(minutesOf(booking.starts_at))} · {booking.duration_minutes} د
              </span>
              <span className="flex items-center gap-1">
                <User size={13} aria-hidden />
                {operatorLabel}
              </span>
            </div>
            {pay !== 'none' || priceMinor !== null || booking.intended_reward_id ? (
              <div className="flex flex-wrap items-center gap-1.5">
                {pay !== 'none' ? (
                  <span className="rounded-full px-2 py-0.5 text-xs font-bold"
                       style={{ background: PAYMENT_COLOR[pay].bg, color: PAYMENT_COLOR[pay].fg }}>
                    {pay === 'deposit' && booking.deposit_amount_minor
                      ? `عربون ${riyals(booking.deposit_amount_minor)} ريال`
                      : PAYMENT_LABEL[pay]}
                  </span>
                ) : null}
                {priceMinor !== null ? (
                  <span className="rounded-full px-2 py-0.5 text-xs font-semibold"
                       style={{ background: 'var(--rj-line)', color: 'var(--rj-ink)' }}>
                    السعر: {riyals(priceMinor)} ريال
                  </span>
                ) : null}
                {booking.intended_reward_id ? (
                  <span className="text-sm" title="جائزة بانتظار الاستبدال عند الحضور">⭐</span>
                ) : null}
              </div>
            ) : null}
            {booking.note ? <p className="text-xs" style={{ color: 'var(--rj-ink-soft)' }}>{booking.note}</p> : null}
          </div>
          <button type="button" onClick={onClose} aria-label="إغلاق" className="shrink-0"><X size={18} aria-hidden /></button>
        </div>
        {booking.status === 'booked' ? (
          // أيقونات فقط، صف واحد — التفاصيل أعلاه هي ما يقرأه، هذا فقط ما يضغطه.
          <div className="flex items-center justify-center gap-3">
            <button type="button" onClick={() => onEdit(booking)} aria-label="تعديل الحجز" title="تعديل الحجز"
                   className="grid h-12 w-12 place-items-center rounded-full"
                   style={{ background: 'var(--rj-line)', color: 'var(--rj-ink)' }}>
              <Pencil size={18} aria-hidden />
            </button>
            <button type="button" disabled={busy} onClick={() => act(attendBooking, 'سُجّل الحضور ✓')}
                   aria-label="حضر" title="حضر"
                   className="grid h-12 w-12 place-items-center rounded-full"
                   style={{ background: 'var(--rj-attended-soft)', color: 'var(--rj-attended)' }}>
              <Check size={20} aria-hidden />
            </button>
            <button type="button" disabled={busy}
                   onClick={() => act((s, id) => noShowBooking(s, id), 'سُجّل عدم الحضور')}
                   aria-label="لم يحضر" title="لم يحضر"
                   className="grid h-12 w-12 place-items-center rounded-full"
                   style={{ background: 'var(--rj-noshow-soft)', color: 'var(--rj-noshow)' }}>
              <X size={20} aria-hidden />
            </button>
            <button type="button" disabled={busy}
                   onClick={() => act((s, id) => cancelBooking(s, id), 'أُلغي الحجز')}
                   aria-label="إلغاء الحجز" title="إلغاء الحجز"
                   className="grid h-12 w-12 place-items-center rounded-full"
                   style={{ background: 'var(--rj-cancelled-soft)', color: 'var(--rj-cancelled)' }}>
              <Trash2 size={18} aria-hidden />
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
