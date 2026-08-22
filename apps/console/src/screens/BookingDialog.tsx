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
 */
import { useEffect, useMemo, useState } from 'react';
import { Button } from '@base-ui/design-system/Button';
import { Field, Input } from '@base-ui/design-system/Field';
import { Modal } from '@base-ui/design-system/Modal';
import {
  ApiError, balanceFor, type Balance, type Booking, type CatalogueService, createBooking,
  type CustomerHit, customerByPhone, earnSettings, type EarnSettings, editBookingNote,
  editBookingPayment, editBookingReward, editBookingServices, ensureCustomer, type FieldOffer, type FieldOperator,
  nearestSlot, type NoShowRisk, noShowRisk, offerFor, pointsByService, rescheduleBooking,
  sentenceFor, setServiceDuration, setServicePrice, suggestByPrefix,
} from '../api';
import { asLocal } from '../phone';
import { halalas, riyals } from '../money';
import { PAYMENT_LABEL, PAYMENT_ORDER, type PaymentStatus } from '../bookingPayment';

// THIS DIALOG USES THE DESIGN SYSTEM'S OWN PALETTE, NOT `--rj-*` — those custom properties are
// scoped to `.rj-grid` (Bookings.tsx's own bespoke identity), and this Modal portals outside it.
const PAYMENT_CLASS: Record<PaymentStatus, { active: string; idle: string }> = {
  none: { active: 'bg-text-secondary text-white', idle: 'bg-surface-2 text-text-secondary' },
  deposit: { active: 'bg-warning text-white', idle: 'bg-warning-soft text-warning-on-soft' },
  paid: { active: 'bg-success text-white', idle: 'bg-success-soft text-success-on-soft' },
};
import { digitsOnly } from '../digits';
import { newIdempotencyKey } from '../queue';
import { ServiceGrid } from '../ServiceGrid';
import type { Session } from '../session';

export interface BookingDialogProps {
  session: Session;
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
  onClose: () => void;
  onCreated: (booking: Booking) => void;
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

export function BookingDialog(
  { session, branchId, date, initialOperatorId, initialStartsAt, initialCustomer,
   initialServiceIds, services, staff, onClose, onCreated,
   editingBooking, editingCustomerLabel }: BookingDialogProps,
) {
  const editing = editingBooking ?? null;
  const [phone, setPhone] = useState(initialCustomer?.phone ?? '');
  const [matches, setMatches] = useState<CustomerHit[] | null>([]);
  const [customer, setCustomer] = useState<CustomerHit | null>(initialCustomer ?? null);
  const [name, setName] = useState(initialCustomer?.name ?? '');
  const [chosen, setChosen] = useState<string[]>(editing?.service_ids ?? initialServiceIds ?? []);
  const [operatorId, setOperatorId] = useState(editing?.operator_id ?? initialOperatorId ?? '');
  const [day, setDay] = useState(editing ? dayOfEpoch(editing.starts_at) : date);
  const [time, setTime] = useState(
    editing ? timeOfEpoch(editing.starts_at) : (initialStartsAt ? timeOfEpoch(initialStartsAt) : ''),
  );
  const [note, setNote] = useState(editing?.note ?? '');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  // A PRESS THAT TEACHES, NOT ONE THAT REFUSES SILENTLY — «احجز» is always
  // clickable; a press while something required is still empty marks EXACTLY that field red,
  // right under it, instead of sitting disabled with no way to tell why. Stays false until the
  // first press, so an empty fresh dialog never opens already covered in red ink.
  const [attempted, setAttempted] = useState(false);
  const [risk, setRisk] = useState<NoShowRisk | null>(null);
  const [finding, setFinding] = useState(false);
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
  const [earn, setEarn] = useState<EarnSettings | null>(null);
  const [offer, setOffer] = useState<FieldOffer | null>(null);
  const [balance, setBalance] = useState<Balance | null>(null);

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
    () => chosen.reduce((sum, id) => sum + durationOf(id), 0),
    [chosen, services, localDurations],
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
    () => chosen.reduce((sum, id) => sum + (services.find((s) => s.id === id)?.price_minor ?? 0), 0),
    [chosen, services],
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

  const starts_at = (() => {
    if (!day || !time) return 0;
    const at = Date.parse(`${day}T${time}:00+03:00`);
    return Number.isNaN(at) ? 0 : Math.floor(at / 1000);
  })();

  const phoneMissing = !editing && !customer && phone.trim().length < 3;
  const servicesMissing = chosen.length === 0;
  const operatorMissing = !operatorId;
  const timeMissing = starts_at <= 0;
  const ready = Boolean(!phoneMissing && !servicesMissing && !missingDuration
    && !operatorMissing && !timeMissing && !depositAmountMissing);

  // "أقرب موعد" (§6.2) — the same availability derivation the grid's own conflict lock rests
  // on, from the moment a service and (optionally) an operator are chosen.
  const findNearest = async () => {
    if (chosen.length === 0 || missingDuration || finding) return;
    setFinding(true);
    setError('');
    // NEVER BEFORE NOW — a day/time already typed can sit in the past (the
    // date default is today, and an empty time field reads as 00:00 the moment ANY digit lands
    // in it before the rest is typed), and searching from there could hand back a slot that has
    // already passed. `now` always wins over an earlier `starts_at`; a LATER one he already
    // chose is respected exactly as before.
    const now = Math.floor(Date.now() / 1000);
    const after = starts_at > now ? starts_at : now;
    try {
      const staffToTry = operatorId ? [operatorId] : staff.map((o) => o.id);
      // THE EARLIEST SLOT, AND WHO OWNS IT — a search across several staff must know which one
      // produced the winning answer, not merely the winning TIME.
      let best: { operatorId: string; startsAt: number } | null = null;
      for (const opId of staffToTry) {
        // eslint-disable-next-line no-await-in-loop
        const r = await nearestSlot(session, branchId, opId, chosen, after);
        if (r.starts_at !== null && (best === null || r.starts_at < best.startsAt)) {
          best = { operatorId: opId, startsAt: r.starts_at };
        }
      }
      if (best === null) { setError('لا فتحة قريبة خلال أسبوعين.'); return; }
      const d = new Date(best.startsAt * 1000);
      setDay(`${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`);
      setTime(`${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`);
      if (!operatorId) setOperatorId(best.operatorId);
    } catch (e) {
      setError(sentenceFor(e, 'تعذّر البحث عن فتحة.'));
    } finally {
      setFinding(false);
    }
  };

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
      const servicesChanged = chosen.length !== editing.service_ids.length
        || chosen.some((id) => !editing.service_ids.includes(id));
      if (servicesChanged) booking = await editBookingServices(session, editing.id, chosen);
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
      setError(sentenceFor(e, 'تعذّر حفظ التعديل.'));
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
      if (!c) {
        const ensured = await ensureCustomer(session, phone, name);
        // A REFUSAL RETURNED, NOT THROWN — the route answers 200 with `customer: null` on
        // failure (`reason` is author-written, safe to show), so this is checked explicitly
        // rather than relying on the catch block below to ever see it.
        if (!ensured.customer) { setError(ensured.reason || 'تعذّر الحجز.'); return; }
        c = ensured.customer;
      }
      const booking = await createBooking(session, {
        branch_id: branchId, operator_id: operatorId, customer_id: c.id, service_ids: chosen,
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
      onCreated(booking);
    } catch (e) {
      const status = e instanceof ApiError ? e.status : (e as { status?: number })?.status;
      setError(status === 402
        ? sentenceFor(e, 'الحجوزات ليست في اشتراكك.')
        : sentenceFor(e, 'تعذّر الحجز.'));
    } finally {
      setSaving(false);
    }
  };

  return (
    <Modal open onClose={onClose} size="lg" title={editing ? 'تعديل الحجز' : 'حجز جديد'}
          subtitle={`فرعك، ${date === day ? 'اليوم' : day}`}>
      <div className="flex flex-col gap-4">
        {/* ── العميل — ثابتٌ في التعديل، لا PATCH يغيّره ─────────────────────────────────── */}
        {editing ? (
          <p className="text-sm text-text-secondary">
            العميل: <span className="font-semibold text-text-primary">{editingCustomerLabel || '—'}</span>
          </p>
        ) : (
        <Field label="جوّال العميل" required htmlFor="bkg-phone"
              error={attempted && phoneMissing ? 'الجوال مطلوب' : undefined}>
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
            <p className="text-sm text-success">✓ عميل معروف{customer.name ? ` — ${customer.name}` : ''}</p>
            {/* A NUMBER, NEVER A VERDICT (§2.6) — the staff member reads it and decides: confirm
                twice, ask for a recorded deposit, or book as usual. Nothing here refuses anything.
                MADE TO BE UNDERSTOOD, NOT JUST NOTICED — the screen must be clear, not just a
                badge whose meaning is unknown — the sentence names the actual percentage against
                the shop's own configured cutoff, and offers the one action §5.3 names for this
                exact number: "قرار طلب العربون ممن تكرّر منه", one tap away instead of a
                separate trip to the payment section below. */}
            {risk?.risky ? (
              <div className="flex flex-col gap-1.5 rounded-xl bg-warning-soft p-3">
                <p className="text-sm font-semibold text-warning-on-soft">
                  ⚠️ نسبة عدم حضوره مرتفعة: غاب عن {risk.no_shows} من آخر {risk.considered} موعداً
                  ({Math.round((risk.no_shows / risk.considered) * 100)}٪، والحد {risk.threshold_percent}٪)
                </p>
                <p className="text-xs text-warning-on-soft">
                  يُنصح بطلب عربون لتأكيد هذا الحجز — القرار لك، والنظام لا يفرضه.
                </p>
                {paymentStatus !== 'deposit' ? (
                  <button type="button" onClick={() => setPaymentStatus('deposit')}
                         className="self-start rounded-full bg-warning px-3 py-1 text-xs font-bold text-white">
                    فعّل العربون الآن
                  </button>
                ) : null}
              </div>
            ) : null}
          </div>
        ) : phone.length >= 3 ? (
          <Field label="اسمها (اختياري)" htmlFor="bkg-name">
            <Input id="bkg-name" value={name} onChange={(e) => setName(e.target.value)} />
          </Field>
        ) : null}

        {/* ── الخدمات ─────────────────────────────────────────────────────────────────── */}
        <div>
          <h3 className="mb-2 text-sm text-text-secondary">الخدمات</h3>
          {attempted && servicesMissing ? (
            <p className="mb-2 text-sm text-danger">اختر خدمة واحدة على الأقل</p>
          ) : null}
          <ServiceGrid services={services} selected={chosen}
                      onToggle={(id) => setChosen((cur) => (
                        cur.includes(id) ? cur.filter((x) => x !== id) : [...cur, id]))}
                      offered={new Set(offer?.service_ids ?? [])}
                      redeemable={new Set(
                        (balance?.rewards ?? []).map((r) => r.service_id ?? '').filter(Boolean),
                      )}
                      points={pointsByService(earn, services.map((s) => s.id))} />
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
              <p className="mt-1 text-sm text-text-secondary">المدة الإجمالية: {durationTotal} دقيقة</p>
            )
          ) : null}
        </div>

        {/* ── السعر — لهذا الحجز وحده، ما لم يُحفظ صراحةً ───────────── */}
        {/* لا PATCH يكتب السعر بعد الحجز — يبقى كما كان، يُضبط من جديد فقط. */}
        {!editing && chosen.length > 0 ? (
          <Field label="السعر (اختياري، ريال)" htmlFor="bkg-price">
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
                احفظه كسعر ثابت لهذه الخدمة (لكل الحجوزات القادمة)
              </label>
            ) : null}
          </Field>
        ) : null}

        {/* ── حالة الدفع — ثلاث حالات بلون كل واحدة، تُغيَّر في أي وقت من عمر الحجز ─────────── */}
        <Field label="حالة الدفع" htmlFor="bkg-payment">
          <div id="bkg-payment" className="flex gap-1.5">
            {PAYMENT_ORDER.map((s) => (
              <button key={s} type="button" onClick={() => setPaymentStatus(s)}
                     className={`flex-1 rounded-xl py-2 text-sm font-semibold transition-colors ${
                       s === paymentStatus ? PAYMENT_CLASS[s].active : PAYMENT_CLASS[s].idle}`}>
                {PAYMENT_LABEL[s]}
              </button>
            ))}
          </div>
        </Field>
        {/* «مدفوع» يتّكئ على حقل السعر أعلاه؛ «عربون» وحده يحتاج رقماً — إجباري، لا يُخمَّن. */}
        {paymentStatus === 'deposit' ? (
          <Field label="مبلغ العربون (ريال)" required htmlFor="bkg-deposit"
                error={attempted && depositAmountMissing ? 'مبلغ العربون مطلوب' : undefined}>
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

        {/* ── نيّة استبدال — تُختار الآن، تُصرف عند «حضر» فقط ──────────── */}
        {(balance?.rewards ?? []).length > 0 ? (
          <Field label="جائزة يريد استبدالها (اختياري)" htmlFor="bkg-reward"
                hint="لا تُخصم نقاطه الآن — تُصرف تلقائياً عند تسجيل حضوره.">
            <select
              id="bkg-reward"
              value={intendedRewardId}
              onChange={(e) => setIntendedRewardId(e.target.value)}
              className="h-11 w-full rounded-xl bg-surface-1 px-3 shadow-sm"
            >
              <option value="">بدون</option>
              {(balance?.rewards ?? []).map((r) => (
                <option key={r.id} value={r.id}>
                  {r.name} ({r.cost}){r.needs_approval ? ' — تحتاج موافقة مشرف' : ''}
                </option>
              ))}
            </select>
          </Field>
        ) : null}

        {/* ── الموظف ───────────────────────────────────────────────────────────────────── */}
        <Field label="الموظف" required htmlFor="bkg-op"
              error={attempted && operatorMissing ? 'اختر موظفاً' : undefined}>
          <select
            id="bkg-op"
            value={operatorId}
            onChange={(e) => setOperatorId(e.target.value)}
            className="h-11 w-full rounded-xl bg-surface-1 px-3 shadow-sm"
          >
            <option value="">اختر…</option>
            {staff.map((o) => <option key={o.id} value={o.id}>{o.name}</option>)}
          </select>
        </Field>

        {/* ── الوقت ───────────────────────────────────────────────────────────────────── */}
        <div className="grid grid-cols-2 gap-3">
          <Field label="اليوم" required htmlFor="bkg-day">
            <Input id="bkg-day" type="date" value={day} dir="ltr"
                  onChange={(e) => setDay(e.target.value)} />
          </Field>
          <Field label="الوقت" required htmlFor="bkg-time"
                error={attempted && timeMissing ? 'الوقت مطلوب' : undefined}>
            <Input id="bkg-time" type="time" value={time} dir="ltr"
                  onChange={(e) => setTime(e.target.value)} />
          </Field>
        </div>
        {/* "أقرب موعد" (§6.2) — the same availability derivation the grid's own lock rests on. */}
        <Button variant="ghost" disabled={chosen.length === 0 || missingDuration || finding}
               onClick={findNearest}>
          {finding ? 'يبحث…' : 'أقرب موعد'}
        </Button>

        <Field label="ملاحظة (اختياري)" htmlFor="bkg-note">
          <Input id="bkg-note" value={note} onChange={(e) => setNote(e.target.value)} />
        </Field>

        {error ? <p className="text-sm text-danger">{error}</p> : null}

        <div className="flex items-center justify-end gap-2 border-t border-border-subtle pt-3">
          <Button variant="ghost" onClick={onClose}>إلغاء</Button>
          <Button disabled={saving} onClick={save}>
            {saving ? 'جارٍ الحفظ…' : editing ? 'حفظ التعديل' : 'احجز'}
          </Button>
        </div>
      </div>
    </Modal>
  );
}

/** ONE ROW, THE SAME ACT «خدماتي ومنتجاتي» OFFERS — a number and a save, right where the refusal
 *  was noticed, so fixing it costs one tap and a keystroke instead of a whole other screen. */
function MissingDurationFix({
  session, serviceId, serviceName, onSet,
}: {
  session: Session;
  serviceId: string;
  serviceName: string;
  onSet: (minutes: number) => void;
}) {
  const [minutes, setMinutes] = useState('');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  const save = async () => {
    const n = Number(minutes);
    if (!minutes.trim() || !Number.isFinite(n) || n <= 0) {
      setError('اكتب رقماً أكبر من صفر.');
      return;
    }
    setSaving(true);
    setError('');
    try {
      await setServiceDuration(session, serviceId, n);
      onSet(n);
    } catch (e) {
      setError(sentenceFor(e, 'تعذّر الحفظ.'));
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="flex items-center gap-2 rounded-xl bg-danger/5 p-2">
      <span className="flex-1 truncate text-sm text-danger">{serviceName} — بلا مدة مضبوطة</span>
      <Input
        value={minutes}
        onChange={(e) => setMinutes(e.target.value.replace(/[^\d]/g, ''))}
        dir="ltr"
        inputMode="numeric"
        placeholder="15"
        aria-label={`مدة ${serviceName} بالدقائق`}
        className="w-16 text-center"
      />
      <Button type="button" disabled={saving} onClick={save}>
        {saving ? '...' : 'حفظ'}
      </Button>
      {error ? <span className="text-xs text-danger">{error}</span> : null}
    </div>
  );
}
