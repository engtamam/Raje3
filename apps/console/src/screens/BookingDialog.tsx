/**
 * Booking dialog — creates a new booking (docs/خطة-تنفيذ-الحجوزات.md §6).
 *
 * THE CUSTOMER STEP REUSES THE SAME RESOLVE-OR-CREATE ACT `VisitIn` MAKES (§6.2 of the decisions
 * doc: "the same backend act… never reimplemented"): `ensureCustomer` calls
 * `/api/v1/field/customers/ensure`, which is `Operations.record_visit`'s own customer resolution,
 * exposed without a visit riding along. Search-while-typing is the SAME `/customers/suggest` the
 * keypad already uses.
 *
 * THE SERVICE GRID IS THE SAME COMPONENT, SHARED DATA, NEVER SHARED UI (§6.1 of the decisions
 * doc): `ServiceGrid` renders the same tiles the visit screen does because it is the same
 * catalogue — this dialog's own frame, order and controls are entirely its own.
 *
 * THE ORDER IS SERVICE → STAFF → ONE MERGED TIME PICKER → CONFIRM, not a stack of independent
 * fields with a search button bolted on afterward. Every professional booking product converges
 * on this shape (Fresha, Vagaro, Calendly, Acuity — the research behind the smart-scheduling
 * rebuild) for the same reason: eligibility narrows BEFORE a time is shown, never as a validation
 * error after one is picked, and there is exactly one merged "when" step rather than a date box, a
 * time box and a separate "أقرب موعد" button that only ever fills those same two boxes.
 */
import { useCallback, useEffect, useMemo, useState } from 'react';
import { Button } from '../rj-ui/Button';
import { Field, Input, Select } from '../rj-ui/Field';
import { Modal } from '../rj-ui/Modal';
import { Segmented } from '../rj-ui/Segmented';
import { Badge } from '../rj-ui/Badge';
import { ChevronLeft, ChevronRight } from 'lucide-react';
import {
  ApiError, balanceFor, type Balance, type Booking, type CatalogueService, createBooking,
  type CustomerHit, customerByPhone, earnSettings, type EarnSettings, editBookingNote,
  editBookingPayment, editBookingReward, editBookingServices, ensureCustomer, type FieldOffer, type FieldOperator,
  nearestSlot, nearestSlotsAny, type NoShowRisk, noShowRisk, offerFor, pointsByService, rescheduleBooking,
  sentenceFor, setServiceDuration, setServicePrice, suggestByPrefix, type WeeklyHours,
} from '../api';
import { action, type Catalog } from '../catalog';
import { asLocal } from '../phone';
import { halalas, riyals } from '../money';
import { PAYMENT_ORDER, paymentLabel, type PaymentStatus } from '../bookingPayment';
import { digitsOnly } from '../digits';
import { newIdempotencyKey } from '../queue';
import { ServiceGrid } from '../ServiceGrid';
import { pyWeekday } from './Bookings';
import type { Session } from '../session';
import { useOperatorI18n, tf } from '../operator-i18n';
import './booking-dialog-i18n';

export interface BookingDialogProps {
  session: Session;
  catalog: Catalog;
  branchId: string;
  /** The grid's own day, prefilled — he is already looking at it. */
  date: string;
  /** Set when opened from a click on an empty grid cell — the exact operator and time already
   *  chosen, so the dialog opens with nothing left to pick but the customer and the services. */
  initialOperatorId?: string;
  initialStartsAt?: number;
  /** Set by "احجزي الجلسة القادمة" (§2.7) — she is already a known customer, and asking her
   *  phone again for someone standing at the counter a moment ago would be a step backwards. */
  initialCustomer?: CustomerHit;
  initialServiceIds?: string[];
  services: CatalogueService[];
  staff: FieldOperator[];
  /** The shop's own weekly working hours, handed down by the grid that already read them — used
   *  for exactly one sentence: whether «أقرب وقت فاضي» is late because the shop is CLOSED right
   *  now, or merely because it is busy. */
  weekly?: WeeklyHours;
  onClose: () => void;
  /** `referralNotice`, WHEN GIVEN, IS A ONE-LINE TOAST TEXT — this dialog closes the moment a
   *  booking is created (`onClose` runs immediately in every caller), so any referral-code
   *  feedback has to travel out with the booking itself rather than render inline here, where
   *  nobody would ever see it. */
  onCreated: (booking: Booking, referralNotice?: string) => void;
  /** Set when opened from an existing card's action sheet ("تعديل") rather than an empty cell —
   *  the customer is already fixed (no PATCH route changes who a booking is for), so that whole
   *  step is skipped; services, operator, time and note stay editable and are written back with
   *  the same PATCH acts the grid's own drag-and-drop and «خدماتي ومنتجاتي» already use, never a
   *  second booking created beside the first. */
  editingBooking?: Booking;
  editingCustomerLabel?: string;
}

function timeOfEpoch(epoch: number): string {
  const d = new Date(epoch * 1000);
  return `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`;
}

function dayOfEpoch(epoch: number): string {
  const d = new Date(epoch * 1000);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
}

/** Real "today," by the browser's own clock — never the grid's `date` prop, which is whatever
 *  day the grid happened to be showing when this dialog was opened. */
function todayStr(): string {
  const n = new Date();
  return `${n.getFullYear()}-${String(n.getMonth() + 1).padStart(2, '0')}-${String(n.getDate()).padStart(2, '0')}`;
}

function addDays(dateStr: string, delta: number): string {
  const d = new Date(`${dateStr}T00:00:00Z`);
  d.setUTCDate(d.getUTCDate() + delta);
  return `${d.getUTCFullYear()}-${String(d.getUTCMonth() + 1).padStart(2, '0')}-${String(d.getUTCDate()).padStart(2, '0')}`;
}

function humanDay(dateStr: string, t: (key: string) => string): string {
  if (dateStr === todayStr()) return t('bookingDialog.today');
  if (dateStr === addDays(todayStr(), 1)) return t('bookingDialog.tomorrow');
  const d = new Date(`${dateStr}T00:00:00Z`);
  return tf(t, 'bookingDialog.weekdayAndDate', { weekday: t(`bookingDialog.weekday.${d.getUTCDay()}`), day: d.getUTCDate() });
}

interface Slot { operatorId: string; startsAt: number }

const SLOTS_PER_DAY = 6;

export function BookingDialog(
  { session, catalog, branchId, date, initialOperatorId, initialStartsAt, initialCustomer,
   initialServiceIds, services, staff, weekly, onClose, onCreated,
   editingBooking, editingCustomerLabel }: BookingDialogProps,
) {
  const { t } = useOperatorI18n();
  const editing = editingBooking ?? null;
  const [phone, setPhone] = useState(initialCustomer?.phone ?? '');
  const [matches, setMatches] = useState<CustomerHit[] | null>([]);
  const [customer, setCustomer] = useState<CustomerHit | null>(initialCustomer ?? null);
  const [name, setName] = useState(initialCustomer?.name ?? '');
  // A NEW CUSTOMER'S REFERRAL CODE — the only moment this dialog ever has to collect one
  // (`ensureCustomer`'s own docstring: this IS the real "new customer" moment for a booking).
  // Never shown once `customer` is set — a returning customer typing one in would be refused by
  // the engine itself anyway (see `core/referral_redemption.py`'s own new-customer check).
  const [referralCode, setReferralCode] = useState('');
  const [chosen, setChosen] = useState<string[]>(editing?.service_ids ?? initialServiceIds ?? []);
  /** HOW MANY OF EACH — "2× غسيل خارجي", like the same thing recorded as a visit. Absent for an
   *  id in `chosen` means one, same default the server side already carries. Seeded from the
   *  booking being edited, when there is one. */
  const [quantities, setQuantities] = useState<Record<string, number>>(editing?.quantities ?? {});
  const toggleService = useCallback((id: string) => {
    setChosen((cur) => (cur.includes(id) ? cur.filter((x) => x !== id) : [...cur, id]));
    // DESELECTING FORGETS THE COUNT TOO — same rule Visit.tsx's own `toggle` follows.
    setQuantities((cur) => {
      if (!(id in cur)) return cur;
      const next = { ...cur };
      delete next[id];
      return next;
    });
  }, []);
  const changeQuantity = useCallback((id: string, quantity: number) => {
    setQuantities((cur) => ({ ...cur, [id]: quantity }));
  }, []);
  const [operatorId, setOperatorId] = useState(editing?.operator_id ?? initialOperatorId ?? '');
  const [day, setDay] = useState(editing ? dayOfEpoch(editing.starts_at) : date);
  const [time, setTime] = useState(
    editing ? timeOfEpoch(editing.starts_at) : (initialStartsAt ? timeOfEpoch(initialStartsAt) : ''),
  );
  const [manualEntry, setManualEntry] = useState(false);
  const [note, setNote] = useState(editing?.note ?? '');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  // A PRESS THAT TEACHES, NOT ONE THAT REFUSES SILENTLY — «احجز» is always
  // clickable; a press while something required is still empty marks EXACTLY that field red,
  // right under it, instead of sitting disabled with no way to tell why. Stays false until the
  // first press, so an empty fresh dialog never opens already covered in red ink.
  const [attempted, setAttempted] = useState(false);
  const [risk, setRisk] = useState<NoShowRisk | null>(null);
  // MINTED ONCE, PER OPEN OF THIS DIALOG — a double-press of «احجز» carries the same key and
  // returns the same booking rather than creating a second one, exactly as the visit screen's
  // own save does.
  const [idempotencyKey] = useState(newIdempotencyKey);

  useEffect(() => {
    if (phone.length < 3) { setMatches([]); return; }
    let stale = false;
    const id = window.setTimeout(() => {
      suggestByPrefix(session, phone)
        .then((rows) => { if (!stale) setMatches(rows); })
        .catch(() => { if (!stale) setMatches(null); });
    }, 180);
    return () => { stale = true; window.clearTimeout(id); };
  }, [phone, session]);

  // A NUMBER BESIDE HER NAME, THE MOMENT SHE IS IDENTIFIED (§2.6) — never a verdict, never a
  // refusal; the staff member reads it and decides. Silent on failure, same as everything else
  // in this dialog that is not the save itself.
  useEffect(() => {
    if (!customer) { setRisk(null); return; }
    let stale = false;
    noShowRisk(session, customer.id).then((r) => { if (!stale) setRisk(r); }).catch(() => {});
    return () => { stale = true; };
  }, [customer, session]);

  // THE SAME GRID VISIT.TSX DRAWS, NOT A PLAINER ONE — «ServiceGrid» always
  // took `offered`/`redeemable`/`points`, and this dialog never passed them, so a customer with a
  // live offer or a redeemable reward saw neither of those things while booking his OWN next visit
  // — only while being checked in for the one he was already standing at the counter for. Same
  // resolution path Visit.tsx uses: the phone answers a `subject_ref`, and that pseudonym is what
  // offers and balances are actually keyed on (operations never learns a name from either read).
  const [earn, setEarn] = useState<EarnSettings | null | undefined>(undefined);
  const [offer, setOffer] = useState<FieldOffer | null | undefined>(undefined);
  const [balance, setBalance] = useState<Balance | null | undefined>(undefined);

  useEffect(() => {
    earnSettings(session).then(setEarn).catch(() => setEarn(null));
  }, [session]);

  useEffect(() => {
    if (!customer) { setOffer(null); setBalance(null); return; }
    let stale = false;
    customerByPhone(session, customer.phone)
      .then(async (r) => {
        const ref = r.customer?.subject_ref ?? '';
        if (stale || !ref) return;
        const [o, b] = await Promise.allSettled([offerFor(session, ref), balanceFor(session, ref)]);
        if (stale) return;
        setOffer(o.status === 'fulfilled' ? o.value : null);
        setBalance(b.status === 'fulfilled' ? b.value : null);
      })
      .catch(() => { if (!stale) { setOffer(null); setBalance(null); } });
    return () => { stale = true; };
  }, [customer, session]);

  // FIXED FROM HERE, NOT SENT AWAY — "اضبطها من «خدماتي ومنتجاتي»" sent him
  // to a whole other screen to answer a question this one already had open. A patch made from
  // here updates the SAME `operations.update_service` row Services.tsx's own edit row writes; this
  // overlay is only local memory of what was just saved, so the dialog reflects it without a
  // refetch of the whole catalogue.
  const [localDurations, setLocalDurations] = useState<Record<string, number>>({});
  const durationOf = (id: string): number =>
    localDurations[id] ?? services.find((s) => s.id === id)?.duration_minutes ?? 0;

  const durationTotal = useMemo(
    () => chosen.reduce((sum, id) => sum + durationOf(id) * Math.max(1, quantities[id] ?? 1), 0),
    [chosen, services, localDurations, quantities],
  );
  // A SELECTED SERVICE WITH NO DURATION SET REFUSES THE SAVE, NEVER GUESSES — the same rule the
  // server itself enforces; said here too so he learns it before the round trip, not after.
  const missingIds = chosen.filter((id) => !durationOf(id));
  const missingDuration = missingIds.length > 0;

  // THE BOOKING'S OWN PRICE, NOT THE CATALOGUE'S — some appointments are
  // negotiated at the counter, and that number must never leak onto every future booking of the
  // same service. Suggested from the catalogue's own sum, freely editable, saved back to the
  // catalogue ONLY when he explicitly ticks the box below — two different acts, never implied by
  // each other.
  const catalogPriceMinor = useMemo(
    () => chosen.reduce((sum, id) => sum
      + (services.find((s) => s.id === id)?.price_minor ?? 0) * Math.max(1, quantities[id] ?? 1), 0),
    [chosen, services, quantities],
  );
  const [priceText, setPriceText] = useState('');
  const [priceTouched, setPriceTouched] = useState(false);
  const [saveToCatalog, setSaveToCatalog] = useState(false);
  const [paymentStatus, setPaymentStatus] = useState<PaymentStatus>(editing?.payment_status ?? 'none');
  // required only for «عربون»; «مدفوع» reads the
  // price field above instead, so it needs no number of its own.
  const [depositAmountText, setDepositAmountText] = useState(
    editing?.deposit_amount_minor ? riyals(editing.deposit_amount_minor) : '',
  );
  const depositAmountMinor = depositAmountText.trim() ? halalas(depositAmountText) : null;
  const depositAmountMissing = paymentStatus === 'deposit'
    && (depositAmountMinor === null || depositAmountMinor <= 0);
  // نيّة استبدال، لا استبدال فوري — يُختار هنا، يُصرف فعلياً فقط عند
  // «حضر» (attend()), أبداً عند الحجز نفسه: نقاطه ما تُخصم لزيارة لسه ما صارت.
  const [intendedRewardId, setIntendedRewardId] = useState(editing?.intended_reward_id ?? '');
  const priceMinor = priceText.trim() ? halalas(priceText) : (catalogPriceMinor || null);
  // ONLY WHEN ONE SERVICE IS CHOSEN — a total across several services has no single catalogue row
  // to write back to, so the checkbox that would do it is not offered at all rather than guessing
  // which service the negotiated price was actually for.
  const singleServiceId = chosen.length === 1 ? chosen[0] : null;

  // SUGGESTS, NEVER OVERWRITES. The moment he types his own number the catalogue's total stops
  // following his selection — the same "his edit wins" rule the rest of this dialog already
  // follows for name/time/operator.
  useEffect(() => {
    if (!priceTouched) setPriceText(catalogPriceMinor ? riyals(catalogPriceMinor) : '');
  }, [catalogPriceMinor, priceTouched]);

  // THE DETAILS SECTION (price/payment/deposit/reward) OPENS ON ITS OWN whenever it actually has
  // something that needs his attention — a real payment status already chosen (e.g. the risk
  // note's one-tap «فعّل العربون الآن»), or a required field left empty after a press. Otherwise
  // it stays folded: a shop that never touches payment on a booking never sees it at all.
  const [detailsOpen, setDetailsOpen] = useState(false);
  const detailsForcedOpen = paymentStatus !== 'none' || (attempted && depositAmountMissing);

  const starts_at = (() => {
    if (!day || !time) return 0;
    const at = Date.parse(`${day}T${time}:00+03:00`);
    return Number.isNaN(at) ? 0 : Math.floor(at / 1000);
  })();

  const phoneMissing = !editing && !customer && phone.trim().length < 3;
  const servicesMissing = chosen.length === 0;
  const operatorMissing = !operatorId;
  const timeMissing = starts_at <= 0;

  // WHO CAN ACTUALLY DO EVERY CHOSEN SERVICE, TOGETHER — one booking is one operator covering the
  // whole basket (the server's own `_refuse_if_ineligible` refuses anybody else), so this is the
  // real set the dropdown may offer, not a hint layered on top of it.
  //
  // A SERVICE WITH NO RESTRICTION (`eligible_staff_ids` empty/absent) resolves to every FIELD-ROLE
  // operator — NOT every active operator regardless of role any more (assignment-mode redesign
  // phase 2, matched here to operations' own service-eligibility route: this used to return
  // `staff` unfiltered, which let the dropdown OFFER a manager for an unrestricted service the
  // server would then refuse at save time with a less specific sentence than this screen could
  // have given up front).
  const fieldStaffIds = useMemo(
    () => new Set(staff.filter((o) => o.role === 'operator').map((o) => o.id)), [staff]);
  const eligibleStaff = useMemo(() => {
    const perService = chosen.map((id) => {
      const ids = services.find((s) => s.id === id)?.eligible_staff_ids;
      return ids && ids.length > 0 ? new Set(ids) : fieldStaffIds;
    });
    if (perService.length === 0) return staff;
    return staff.filter((o) => perService.every((set) => set.has(o.id)));
  }, [chosen, services, staff, fieldStaffIds]);
  // ANY NAMED SERVICE KEEPS THE MANUAL PICKER — a basket mixing a "named" haircut with an "auto"
  // express service still lets him choose explicitly, exactly as today; only a basket where EVERY
  // chosen service is "auto" hides the dropdown, since there is then no service left that ever
  // asks "which operator" on its own. No separate "mixed basket" refusal needed: the eligibility
  // intersection above already narrows correctly either way.
  const anyNamed = chosen.some((id) => services.find((s) => s.id === id)?.assignment_mode === 'named');
  // A CHOSEN OPERATOR WHO NO LONGER QUALIFIES (a service was added after he was picked) IS DROPPED
  // rather than silently kept — sending him would just be refused server-side a moment later, with
  // a less specific sentence than this one.
  const operatorIneligible = Boolean(operatorId) && !eligibleStaff.some((o) => o.id === operatorId);
  // NO SINGLE OPERATOR COVERS THIS COMBINATION — a real state, not an error in the data. Splitting
  // such a basket across several people ("موظف لكل خدمة معاً في نفس الحجز") is not something the
  // server can do today (`create()` books the whole basket under one operator id) — so the honest
  // move here is to say so plainly and let him book the services one at a time, rather than
  // offering a control that promises a split booking nothing behind it can perform.
  const noCommonOperator = chosen.length > 1 && eligibleStaff.length === 0;
  const ready = Boolean(!phoneMissing && !servicesMissing && !missingDuration
    && !operatorMissing && !operatorIneligible && !noCommonOperator && !timeMissing
    && !depositAmountMissing);
  // ONE CAPABILITY BEHIND EVERY WRITE THIS DIALOG MAKES — create, reschedule, edit-services,
  // edit-note, edit-payment and edit-reward all enforce the SAME backend capability
  // (`bookings.write`, services/bookings/app/api/v1/bookings.py's `_WRITE`), so any one declared
  // catalogue id stands for all of them; there is no finer-grained id to ask for.
  const canWrite = Boolean(action(catalog, 'bookings.create'));

  // ── THE MERGED TIME PICKER ────────────────────────────────────────────────────────────────
  //
  // ONE STEP, NOT A DATE BOX + A TIME BOX + A SEPARATE "أقرب موعد" BUTTON. Every real slot for
  // the day on screen is fetched and shown as a tap-once chip; picking one sets both the time AND
  // (when the operator step is «أي متاح») the operator who actually owns it — the exact "who
  // for, and with whom" question that a bare time input never answered.
  //
  // ONE SERVER CALL, NOT A LOOP OF THEM (Phase 0, services/bookings/app/core/assignment.py) —
  // this used to walk `cursor` forward itself, calling the single-operator `/nearest` endpoint
  // once per candidate per round (up to SLOTS_PER_DAY × eligibleStaff.length round trips for one
  // chip row). The merge now happens server-side in `nearest-any`; this effect only asks once.
  const [slots, setSlots] = useState<Slot[] | null>(null);   // null = loading
  const [slotsError, setSlotsError] = useState('');
  const [jumping, setJumping] = useState(false);

  useEffect(() => {
    let stale = false;
    async function run() {
      if (chosen.length === 0 || missingDuration || !day || noCommonOperator) {
        if (!stale) setSlots([]);
        return;
      }
      setSlots(null);
      setSlotsError('');
      const dayStartEpoch = Math.floor(Date.parse(`${day}T00:00:00+03:00`) / 1000);
      const dayEndEpoch = dayStartEpoch + 24 * 3600;
      // ALWAYS FROM RIGHT NOW WHEN THE DAY ON SCREEN IS TODAY — never from a pre-filled or
      // previously-picked time, the exact bug this dialog once had (§ findNearest's own history).
      const after = day === todayStr() ? Math.floor(Date.now() / 1000) : dayStartEpoch;
      const candidates = operatorId ? [operatorId] : eligibleStaff.map((o) => o.id);
      if (candidates.length === 0) { if (!stale) setSlots([]); return; }
      try {
        const r = await nearestSlotsAny(
          session, branchId, candidates, chosen, after, dayEndEpoch, SLOTS_PER_DAY, editing?.id,
          quantities);
        if (!stale) {
          setSlots(r.slots.map((s) => ({ operatorId: s.operator_id, startsAt: s.starts_at })));
        }
      } catch (e) {
        if (!stale) { setSlots([]); setSlotsError(sentenceFor(e, t('bookingDialog.slotsSearchError'))); }
      }
    }
    run();
    return () => { stale = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [chosen, quantities, operatorId, day, missingDuration, durationTotal, noCommonOperator]);

  function pickSlot(s: Slot) {
    setOperatorId(s.operatorId);
    setTime(timeOfEpoch(s.startsAt));
    setManualEntry(false);
  }

  // «المحل مغلق الآن» EXPLAINED, NOT LEFT AS A CONFUSING TIME — reported directly: the earliest
  // real slot on a currently-closed day IS the top of the next working window (the algorithm is
  // correct), but a bare "09:00" with no context reads as a bug rather than a fact.
  //
  // AND ONLY WHEN THE SHOP IS ACTUALLY CLOSED. This used to be "today, and the first slot is more
  // than five minutes away" — which is equally true of a shop that is wide open and simply booked
  // solid until the evening, so a busy Tuesday afternoon was told, in the product's own voice,
  // that the shop was closed (seen on a real recording at three in the afternoon, hours inside the
  // working day). The shop's own hours are the only thing that can answer this, so they are what
  // answers it: closed today, or now sitting before opening or after closing.
  const shopClosedNow = (() => {
    if (day !== todayStr() || !weekly) return false;
    const today = weekly[String(pyWeekday(day))];
    if (!today) return false;
    if (today.closed) return true;
    const n = new Date();
    const minuteOfDay = n.getHours() * 60 + n.getMinutes();
    return minuteOfDay < today.start_minute || minuteOfDay >= today.end_minute;
  })();
  const firstSlotIsShopOpening = shopClosedNow && (slots ?? []).length > 0
    && (slots as Slot[])[0].startsAt - Math.floor(Date.now() / 1000) > 5 * 60;

  // "أقرب يوم فيه موعد" — for when the day on screen has nothing at all (closed, or fully
  // booked): the same whole-horizon search the old «أقرب موعد» button always did, just jumping
  // the day switcher to the day it actually found instead of only filling two fields.
  async function jumpToNearestDay() {
    if (chosen.length === 0 || missingDuration || jumping) return;
    setJumping(true);
    setSlotsError('');
    try {
      const after = Math.floor(Date.now() / 1000);
      const candidates = operatorId ? [operatorId] : eligibleStaff.map((o) => o.id);
      let best: Slot | null = null;
      for (const opId of candidates) {
        // eslint-disable-next-line no-await-in-loop
        const r = await nearestSlot(session, branchId, opId, chosen, after, editing?.id, quantities);
        if (r.starts_at !== null && (best === null || r.starts_at < best.startsAt)) {
          best = { operatorId: opId, startsAt: r.starts_at };
        }
      }
      if (best === null) { setSlotsError(t('bookingDialog.noNearSlot')); return; }
      setDay(dayOfEpoch(best.startsAt));
      setTime(timeOfEpoch(best.startsAt));
      if (!operatorId) setOperatorId(best.operatorId);
    } catch (e) {
      setSlotsError(sentenceFor(e, t('bookingDialog.slotSearchError')));
    } finally {
      setJumping(false);
    }
  }

  // AN EDIT IS THREE INDEPENDENT PATCHES, NOT A NEW BOOKING — services, the slot (operator+time
  // together, since reschedule is the one act that moves both), and the note, each sent only
  // when it actually changed. A partial failure still leaves the earlier PATCHes standing rather
  // than rolling back, exactly like every other multi-step save in this app.
  const saveEdit = async () => {
    if (!editing) return;
    setSaving(true);
    setError('');
    try {
      let booking = editing;
      const editingQuantities = editing.quantities ?? {};
      const quantitiesChanged = Object.keys(quantities).length !== Object.keys(editingQuantities).length
        || Object.entries(quantities).some(([id, q]) => editingQuantities[id] !== q);
      const servicesChanged = chosen.length !== editing.service_ids.length
        || chosen.some((id) => !editing.service_ids.includes(id))
        || quantitiesChanged;
      if (servicesChanged) {
        booking = await editBookingServices(session, editing.id, chosen, quantities);
      }
      if (operatorId !== editing.operator_id || starts_at !== editing.starts_at) {
        booking = await rescheduleBooking(session, editing.id, starts_at, operatorId);
      }
      if (note !== (editing.note ?? '')) booking = await editBookingNote(session, editing.id, note);
      if (paymentStatus !== editing.payment_status
          || (paymentStatus === 'deposit' && depositAmountMinor !== editing.deposit_amount_minor)) {
        booking = await editBookingPayment(
          session, editing.id, paymentStatus, depositAmountMinor ?? undefined);
      }
      if ((intendedRewardId || null) !== editing.intended_reward_id) {
        booking = await editBookingReward(session, editing.id, intendedRewardId || null);
      }
      onCreated(booking);
    } catch (e) {
      setError(sentenceFor(e, t('bookingDialog.saveEditError')));
    } finally {
      setSaving(false);
    }
  };

  const save = async () => {
    if (saving) return;
    if (!ready) { setAttempted(true); return; }
    if (editing) { await saveEdit(); return; }
    setSaving(true);
    setError('');
    try {
      // THE CUSTOMER, RESOLVED-OR-CREATED HERE, AT THE MOMENT HE COMMITS — not while he types,
      // which would create a row for every phone he tries and abandons.
      let c = customer;
      let referralNotice: string | undefined;
      if (!c) {
        const ensured = await ensureCustomer(session, phone, name, referralCode.trim());
        // A REFUSAL RETURNED, NOT THROWN — the route answers 200 with `customer: null` on
        // failure (`reason` is author-written, safe to show), so this is checked explicitly
        // rather than relying on the catch block below to ever see it.
        if (!ensured.customer) { setError(ensured.reason || t('bookingDialog.bookingError')); return; }
        c = ensured.customer;
        // NEVER BLOCKS THE BOOKING EITHER WAY — a rejected code is only ever a notice, surfaced
        // by the caller (this dialog closes immediately below); the booking is real regardless.
        if (ensured.referral_registration) {
          referralNotice = ensured.referral_registration.ok
            ? t('bookingDialog.referralRegistered')
            : tf(t, 'bookingDialog.referralRejected',
                { reason: ensured.referral_registration.message || '' });
        }
      }
      const booking = await createBooking(session, {
        branch_id: branchId, operator_id: operatorId, customer_id: c.id, service_ids: chosen,
        quantities: Object.keys(quantities).length > 0 ? quantities : undefined,
        starts_at, note: note.trim() || undefined, idempotency_key: idempotencyKey,
        // undefined WHEN IT MATCHES THE CATALOGUE — a booking at the ordinary price carries no
        // override at all, rather than a redundant copy of a number that can change under it.
        price_override_minor: priceMinor !== null && priceMinor !== catalogPriceMinor
          ? priceMinor : undefined,
        payment_status: paymentStatus,
        deposit_amount_minor: paymentStatus === 'deposit' ? depositAmountMinor ?? undefined : undefined,
        intended_reward_id: intendedRewardId || undefined,
      });
      // A SEPARATE WRITE, AFTER THE BOOKING ITSELF SUCCEEDED — ticking the box changes what every
      // FUTURE booking of this service defaults to; it must never block or unwind the one he is
      // making right now. Silent on failure, like every other secondary save in this dialog: the
      // booking is real either way, and he can fix the catalogue price from «خدماتي ومنتجاتي» if
      // this one quietly did not take.
      if (saveToCatalog && singleServiceId && priceMinor !== null) {
        setServicePrice(session, singleServiceId, priceMinor).catch(() => {});
      }
      onCreated(booking, referralNotice);
    } catch (e) {
      const status = e instanceof ApiError ? e.status : (e as { status?: number })?.status;
      setError(status === 402
        ? sentenceFor(e, t('bookingDialog.notSubscribed'))
        : sentenceFor(e, t('bookingDialog.bookingError')));
    } finally {
      setSaving(false);
    }
  };

  return (
    <Modal open onClose={onClose} title={editing ? t('bookingDialog.title.edit') : t('bookingDialog.title.create')}
          subtitle={tf(t, 'bookingDialog.subtitle', { day: humanDay(day, t) })} size="lg">
      <div className="flex flex-col gap-4">
        {/* ── customer — fixed once editing, no PATCH ever changes who a booking is for ──────── */}
        {editing ? (
          <p className="text-sm text-text-secondary">
            {t('bookingDialog.customerLabel')} <span className="font-semibold text-text-primary">{editingCustomerLabel || '—'}</span>
          </p>
        ) : (
        <Field label={t('bookingDialog.phoneLabel')} required htmlFor="bkg-phone"
              error={attempted && phoneMissing ? t('bookingDialog.phoneRequired') : undefined}>
          <Input
            id="bkg-phone"
            value={phone}
            dir="ltr"
            inputMode="tel"
            placeholder="05…"
            onChange={(e) => {
              setPhone(digitsOnly(e.target.value).slice(0, 10));
              setCustomer(null);
            }}
          />
        </Field>
        )}
        {!editing && (matches ?? []).length > 0 && !customer ? (
          <div className="flex flex-col gap-1">
            {(matches ?? []).slice(0, 4).map((m) => (
              <button
                key={m.id}
                type="button"
                onClick={() => { setCustomer(m); setPhone(m.phone); setName(m.name ?? ''); }}
                className="flex items-center justify-between rounded-xl bg-surface-1 px-3 py-2 text-start shadow-sm"
              >
                <span dir="ltr" className="tabular-nums">{asLocal(m.phone)}</span>
                <span className="text-text-secondary">{m.name || '—'}</span>
              </button>
            ))}
          </div>
        ) : null}
        {customer ? (
          <div className="flex flex-col gap-1">
            <p className="flex items-center gap-1.5 text-sm">
              <Badge tone="success">{t('bookingDialog.knownCustomer')}</Badge>
              {customer.name ? <span>{customer.name}</span> : null}
            </p>
            {/* A NUMBER, NEVER A VERDICT (§2.6) — the staff member reads it and decides: confirm
                twice, ask for a recorded deposit, or book as usual. Nothing here refuses anything.
                MADE TO BE UNDERSTOOD, NOT JUST NOTICED — the screen must be clear, not just a
                badge whose meaning is unknown — the sentence names the actual percentage against
                the shop's own configured cutoff, and offers the one action §5.3 names for this
                exact number: request a deposit from a repeat no-show, one tap away instead of a
                separate trip to the payment section below. */}
            {risk?.risky ? (
              <div className="flex flex-col gap-1.5 rounded-xl bg-warning-soft p-3">
                <p className="text-sm font-semibold text-warning-on-soft">
                  {tf(t, 'bookingDialog.riskWarning', {
                    noShows: risk.no_shows, considered: risk.considered,
                    pct: Math.round((risk.no_shows / risk.considered) * 100), threshold: risk.threshold_percent,
                  })}
                </p>
                <p className="text-xs text-warning-on-soft">
                  {t('bookingDialog.riskAdvice')}
                </p>
                {paymentStatus !== 'deposit' ? (
                  <button type="button" onClick={() => setPaymentStatus('deposit')}
                         className="self-start rounded-full bg-warning px-3 py-1 text-xs font-bold text-white">
                    {t('bookingDialog.enableDepositNow')}
                  </button>
                ) : null}
              </div>
            ) : null}
          </div>
        ) : phone.length >= 3 ? (
          <>
            <Field label={t('bookingDialog.nameLabel')} htmlFor="bkg-name">
              <Input id="bkg-name" value={name} onChange={(e) => setName(e.target.value)} />
            </Field>
            {/* THE ONLY MOMENT THIS CUSTOMER EVER TYPES ONE IN — `ensureCustomer`'s own docstring:
                by the time a booking is attended, the customer already exists, so this is the
                real "new customer" door for a referral code, not the attendance step. */}
            <Field label={t('bookingDialog.referralCodeLabel')} htmlFor="bkg-referral">
              <Input id="bkg-referral" value={referralCode} dir="ltr"
                onChange={(e) => setReferralCode(e.target.value.toUpperCase())} />
            </Field>
          </>
        ) : null}

        {/* ── services ────────────────────────────────────────────────────────────────── */}
        <div>
          <h3 className="mb-2 text-sm text-text-secondary">{t('bookingDialog.servicesHeading')}</h3>
          {attempted && servicesMissing ? (
            <p className="mb-2 text-sm text-danger">{t('bookingDialog.servicesRequired')}</p>
          ) : null}
          {/* A FAILED READ, NAMED — earn/offer/balance used to fail into `null` from the same
              starting `null` a load-in-progress uses, so a customer with a live offer or reward
              points would silently look like one with none at all: the grid rendered clean, the
              save still worked, and nobody was ever told his points or offer could not be read. */}
          {customer && (earn === null || offer === null || balance === null) ? (
            <p className="mb-2 text-xs text-danger">
              {t('bookingDialog.perksReadError')}
            </p>
          ) : null}
          <ServiceGrid session={session} services={services} selected={chosen}
                      onToggle={toggleService}
                      offered={new Set(offer?.service_ids ?? [])}
                      redeemable={new Set(
                        (balance?.rewards ?? []).map((r) => r.service_id ?? '').filter(Boolean),
                      )}
                      points={pointsByService(earn ?? null, services.map((s) => s.id))}
                      quantities={quantities}
                      onQuantityChange={changeQuantity} />
          {chosen.length > 0 ? (
            missingDuration ? (
              <div className="mt-1 flex flex-col gap-1.5">
                {missingIds.map((id) => (
                  <MissingDurationFix
                    key={id}
                    session={session}
                    serviceId={id}
                    serviceName={services.find((s) => s.id === id)?.name ?? id}
                    onSet={(minutes) => setLocalDurations((cur) => ({ ...cur, [id]: minutes }))}
                  />
                ))}
              </div>
            ) : (
              <p className="mt-1 text-sm text-text-secondary">{tf(t, 'bookingDialog.totalDuration', { n: durationTotal })}</p>
            )
          ) : null}
        </div>

        {/* ── staff — before time, not after: "anyone available" is the first, default option ──
            Same list a shop that never customized anything sees — it only narrows once a chosen
            service is actually restricted to specific staff (§3 of the smart-scheduling plan:
            simple by default, deep when needed).

            Hidden entirely when every chosen service is "auto" (`assignment_mode`, phase 3) — no
            remaining service ever asks "with whom" at all, so the question itself drops instead of
            showing a single meaningless option. `operatorId` stays empty the whole time (exactly
            today's "anyone available" behaviour), and the slot picker below fills it in the moment
            a chip is actually chosen — the customer never asks, but real assignment still happens
            as usual. */}
        {anyNamed ? (
          <Field label={t('bookingDialog.staffLabel')} required htmlFor="bkg-op"
                error={attempted && (operatorMissing || operatorIneligible) ? t('bookingDialog.staffRequired') : undefined}>
            <Select
              id="bkg-op"
              value={operatorIneligible ? '' : operatorId}
              onChange={(e) => setOperatorId(e.target.value)}
            >
              <option value="">{t('bookingDialog.anyAvailable')}</option>
              {eligibleStaff.map((o) => <option key={o.id} value={o.id}>{o.name}</option>)}
            </Select>
          </Field>
        ) : null}

        {/* No single staff member covers all chosen services together — a real state, not a data error. */}
        {noCommonOperator ? (
          <p className="text-sm text-danger">
            {t('bookingDialog.noCommonOperator')}
          </p>
        ) : null}

        {/* ── time — one merged slot picker, not two raw fields and a separate button ────────
            Every chip is a real, actually-open slot; tapping it fills the time (and the staff
            member, if "anyone available") directly. */}
        <div>
          <div className="mb-2 flex items-center justify-between gap-2">
            <h3 className="text-sm text-text-secondary">{t('bookingDialog.timeHeading')}</h3>
            {!editing ? (
              <div className="flex items-center gap-1">
                <button type="button" aria-label={t('bookingDialog.prevDay')} disabled={day <= todayStr()}
                       onClick={() => { setDay(addDays(day, -1)); setTime(''); }}
                       className="grid size-8 place-items-center rounded-full text-text-secondary disabled:opacity-30">
                  <ChevronRight size={16} aria-hidden />
                </button>
                <span className="min-w-16 text-center text-sm font-medium">{humanDay(day, t)}</span>
                <button type="button" aria-label={t('bookingDialog.nextDay')}
                       onClick={() => { setDay(addDays(day, 1)); setTime(''); }}
                       className="grid size-8 place-items-center rounded-full text-text-secondary">
                  <ChevronLeft size={16} aria-hidden />
                </button>
              </div>
            ) : null}
          </div>

          {firstSlotIsShopOpening ? (
            <p className="mb-2 text-xs text-text-secondary">
              {t('bookingDialog.shopClosedNote')}
            </p>
          ) : null}

          {chosen.length === 0 || missingDuration || noCommonOperator ? null
            : slots === null ? (
              <p className="text-sm text-text-secondary">{t('bookingDialog.searchingSlots')}</p>
            ) : slots.length === 0 ? (
              <div className="flex flex-col gap-2">
                <p className="text-sm text-text-secondary">{t('bookingDialog.noSlotsToday')}</p>
                <Button type="button" variant="ghost" disabled={jumping} onClick={jumpToNearestDay}
                       className="self-start">
                  {jumping ? t('bookingDialog.jumping') : t('bookingDialog.nearestDay')}
                </Button>
              </div>
            ) : (
              <div className="flex flex-wrap gap-2">
                {slots.map((s, i) => {
                  const picked = time === timeOfEpoch(s.startsAt) && operatorId === s.operatorId;
                  const opName = !operatorId
                    ? staff.find((o) => o.id === s.operatorId)?.name : undefined;
                  return (
                    <button
                      // INDEXED, NOT JUST operatorId+startsAt — a stalled search floor (a mocked
                      // or otherwise unmoving `nearestSlot` answer) can legitimately repeat the
                      // same slot several times in a row; the index keeps React's list identity
                      // correct even then, never a silently-dropped duplicate.
                      key={`${s.operatorId}-${s.startsAt}-${i}`}
                      type="button"
                      onClick={() => pickSlot(s)}
                      className={`rounded-full px-3 py-2 text-sm font-medium transition-colors ${
                        picked ? 'bg-accent text-accent-contrast' : 'border border-border-subtle bg-surface-1 text-text-primary hover:bg-surface-3'
                      }`}
                    >
                      {timeOfEpoch(s.startsAt)}{opName ? tf(t, 'bookingDialog.withOperator', { name: opName }) : ''}
                    </button>
                  );
                })}
              </div>
            )}
          {slotsError ? <p className="mt-1 text-sm text-danger">{slotsError}</p> : null}
          {attempted && timeMissing ? <p className="mt-1 text-sm text-danger">{t('bookingDialog.timeRequired')}</p> : null}

          {/* The manual fallback path — folded by default: editing a past-dated booking, or any
              exception the chip strip doesn't cover. */}
          <button type="button" className="mt-2 text-xs text-text-secondary underline underline-offset-2"
                 onClick={() => setManualEntry((v) => !v)}>
            {manualEntry ? t('bookingDialog.hideManual') : t('bookingDialog.showManual')}
          </button>
          {manualEntry ? (
            <div className="mt-2 grid grid-cols-2 gap-3">
              <Field label={t('bookingDialog.dayLabel')} htmlFor="bkg-day">
                <Input id="bkg-day" type="date" value={day} dir="ltr"
                      onChange={(e) => setDay(e.target.value)} />
              </Field>
              <Field label={t('bookingDialog.timeHeading')} htmlFor="bkg-time">
                <Input id="bkg-time" type="time" value={time} dir="ltr"
                      onChange={(e) => setTime(e.target.value)} />
              </Field>
            </div>
          ) : null}
        </div>

        {/* ── extra details — folded, opens automatically only when it genuinely needs attention ── */}
        <details open={detailsOpen || detailsForcedOpen}
                 onToggle={(e) => setDetailsOpen(e.currentTarget.open)}
                 className="rounded-card border border-border-subtle">
          <summary className="cursor-pointer select-none px-3 py-2 text-sm font-medium text-text-secondary">
            {t('bookingDialog.paymentDetails')}
          </summary>
          <div className="flex flex-col gap-3 border-t border-border-subtle p-3">
            {/* ── price — for this booking alone, unless explicitly saved ───────────── */}
            {!editing && chosen.length > 0 ? (
              <Field label={t('bookingDialog.priceLabel')} htmlFor="bkg-price">
                <Input
                  id="bkg-price"
                  value={priceText}
                  dir="ltr"
                  inputMode="decimal"
                  placeholder="—"
                  onChange={(e) => { setPriceText(e.target.value); setPriceTouched(true); }}
                />
                {singleServiceId ? (
                  <label className="mt-1.5 flex items-center gap-2 text-sm text-text-secondary">
                    <input type="checkbox" checked={saveToCatalog}
                          onChange={(e) => setSaveToCatalog(e.target.checked)} />
                    {t('bookingDialog.saveAsCatalogPrice')}
                  </label>
                ) : null}
              </Field>
            ) : null}

            {/* ── payment status — three exclusive states, the ready-made Segmented gauge ────── */}
            <Field label={t('bookingDialog.paymentStatusLabel')}>
              <Segmented
                ariaLabel={t('bookingDialog.paymentStatusLabel')}
                value={paymentStatus}
                onChange={setPaymentStatus}
                options={PAYMENT_ORDER.map((s) => ({ value: s, label: paymentLabel(s, t) }))}
                className="w-full [&>button]:flex-1"
              />
            </Field>
            {/* "paid" leans on the price field above; "deposit" alone needs its own number — required, never guessed. */}
            {paymentStatus === 'deposit' ? (
              <Field label={t('bookingDialog.depositAmountLabel')} required htmlFor="bkg-deposit"
                    error={attempted && depositAmountMissing ? t('bookingDialog.depositRequired') : undefined}>
                <Input
                  id="bkg-deposit"
                  value={depositAmountText}
                  dir="ltr"
                  inputMode="decimal"
                  placeholder="0"
                  onChange={(e) => setDepositAmountText(e.target.value)}
                />
              </Field>
            ) : null}

            {/* ── redemption intent — chosen now, spent only on "attended" ──────────── */}
            {(balance?.rewards ?? []).length > 0 ? (
              <Field label={t('bookingDialog.rewardLabel')} htmlFor="bkg-reward"
                    hint={t('bookingDialog.rewardHint')}>
                <Select
                  id="bkg-reward"
                  value={intendedRewardId}
                  onChange={(e) => setIntendedRewardId(e.target.value)}
                >
                  <option value="">{t('bookingDialog.noneOption')}</option>
                  {(balance?.rewards ?? []).map((r) => (
                    <option key={r.id} value={r.id}>
                      {tf(t, 'bookingDialog.rewardOption', { name: r.name, cost: r.cost })}
                    </option>
                  ))}
                </Select>
              </Field>
            ) : null}
          </div>
        </details>

        <Field label={t('bookingDialog.noteLabel')} htmlFor="bkg-note">
          <Input id="bkg-note" value={note} onChange={(e) => setNote(e.target.value)} />
        </Field>

        {error ? <p className="text-sm text-danger">{error}</p> : null}

        <div className="flex items-center justify-end gap-2 border-t border-border-subtle pt-3">
          <Button variant="ghost" onClick={onClose}>{t('bookingDialog.cancel')}</Button>
          {canWrite ? (
            <Button disabled={saving} onClick={save} className="shadow-glow">
              {saving ? t('bookingDialog.saving') : editing ? t('bookingDialog.saveEdit') : t('bookingDialog.bookNow')}
            </Button>
          ) : null}
        </div>
      </div>
    </Modal>
  );
}

/** ONE ROW, THE SAME ACT "My Services & Products" OFFERS — a number and a save, right where the
 *  refusal was noticed, so fixing it costs one tap and a keystroke instead of a whole other screen. */
function MissingDurationFix({
  session, serviceId, serviceName, onSet,
}: {
  session: Session;
  serviceId: string;
  serviceName: string;
  onSet: (minutes: number) => void;
}) {
  const { t } = useOperatorI18n();
  const [minutes, setMinutes] = useState('');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  const save = async () => {
    const n = Number(minutes);
    if (!minutes.trim() || !Number.isFinite(n) || n <= 0) {
      setError(t('bookingDialog.enterPositiveNumber'));
      return;
    }
    setSaving(true);
    setError('');
    try {
      await setServiceDuration(session, serviceId, n);
      onSet(n);
    } catch (e) {
      setError(sentenceFor(e, t('bookingDialog.saveFailedGeneric')));
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="flex items-center gap-2 rounded-xl bg-danger/5 p-2">
      <span className="flex-1 truncate text-sm text-danger">{tf(t, 'bookingDialog.noDurationSet', { name: serviceName })}</span>
      <Input
        value={minutes}
        onChange={(e) => setMinutes(e.target.value.replace(/[^\d]/g, ''))}
        dir="ltr"
        inputMode="numeric"
        placeholder="15"
        aria-label={tf(t, 'bookingDialog.durationAriaLabel', { name: serviceName })}
        className="w-16 text-center"
      />
      <Button type="button" disabled={saving} onClick={save}>
        {saving ? t('bookingDialog.savingDots') : t('bookingDialog.save')}
      </Button>
      {error ? <span className="text-xs text-danger">{error}</span> : null}
    </div>
  );
}
