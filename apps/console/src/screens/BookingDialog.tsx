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
  ApiError, type Booking, type CatalogueService, createBooking, type CustomerHit,
  ensureCustomer, type FieldOperator, nearestSlot, type NoShowRisk, noShowRisk, sentenceFor,
  setServiceDuration, setServicePrice, suggestByPrefix,
} from '../api';
import { asLocal } from '../phone';
import { halalas, riyals } from '../money';
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
}

function timeOfEpoch(epoch: number): string {
  const d = new Date(epoch * 1000);
  return `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`;
}

export function BookingDialog(
  { session, branchId, date, initialOperatorId, initialStartsAt, initialCustomer,
   initialServiceIds, services, staff, onClose, onCreated }: BookingDialogProps,
) {
  const [phone, setPhone] = useState(initialCustomer?.phone ?? '');
  const [matches, setMatches] = useState<CustomerHit[] | null>([]);
  const [customer, setCustomer] = useState<CustomerHit | null>(initialCustomer ?? null);
  const [name, setName] = useState(initialCustomer?.name ?? '');
  const [chosen, setChosen] = useState<string[]>(initialServiceIds ?? []);
  const [operatorId, setOperatorId] = useState(initialOperatorId ?? '');
  const [day, setDay] = useState(date);
  const [time, setTime] = useState(initialStartsAt ? timeOfEpoch(initialStartsAt) : '');
  const [note, setNote] = useState('');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
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

  // FIXED FROM HERE, NOT SENT AWAY (Tamam, 2026-08-19) — "اضبطها من «خدماتي ومنتجاتي»" sent him
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

  // THE BOOKING'S OWN PRICE, NOT THE CATALOGUE'S (Tamam, 2026-08-19) — some appointments are
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

  const ready = Boolean((customer || phone.trim().length >= 3) && chosen.length > 0
    && !missingDuration && operatorId && starts_at > 0);

  // "أقرب فتحة" (§6.2) — the same availability derivation the grid's own conflict lock rests
  // on, from the moment a service and (optionally) an operator are chosen.
  const findNearest = async () => {
    if (chosen.length === 0 || missingDuration || finding) return;
    setFinding(true);
    setError('');
    const after = starts_at > 0 ? starts_at : Math.floor(Date.now() / 1000);
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

  const save = async () => {
    if (!ready || saving) return;
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
    <Modal open onClose={onClose} size="lg" title="حجز جديد"
          subtitle={`فرعك، ${date === day ? 'اليوم' : day}`}>
      <div className="flex flex-col gap-4">
        {/* ── العميل ───────────────────────────────────────────────────────────────────── */}
        <Field label="جوّال العميل" required htmlFor="bkg-phone">
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
        {(matches ?? []).length > 0 && !customer ? (
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
                twice, ask for a recorded deposit, or book as usual. Nothing here refuses anything. */}
            {risk?.risky ? (
              <p className="rounded-lg px-2.5 py-1.5 text-xs font-medium"
                style={{ background: '#FBEBE1', color: '#B15A2E' }}>
                غاب عن {risk.no_shows} من آخر {risk.considered} مواعيد
              </p>
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
          <ServiceGrid services={services} selected={chosen}
                      onToggle={(id) => setChosen((cur) => (
                        cur.includes(id) ? cur.filter((x) => x !== id) : [...cur, id]))} />
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

        {/* ── السعر — لهذا الحجز وحده، ما لم يُحفظ صراحةً (Tamam, 2026-08-19) ───────────── */}
        {chosen.length > 0 ? (
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

        {/* ── الموظف ───────────────────────────────────────────────────────────────────── */}
        <Field label="الموظف" required htmlFor="bkg-op">
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
          <Field label="الوقت" required htmlFor="bkg-time">
            <Input id="bkg-time" type="time" value={time} dir="ltr"
                  onChange={(e) => setTime(e.target.value)} />
          </Field>
        </div>
        {/* "أقرب فتحة" (§6.2) — the same availability derivation the grid's own lock rests on. */}
        <Button variant="ghost" disabled={chosen.length === 0 || missingDuration || finding}
               onClick={findNearest}>
          {finding ? 'يبحث…' : 'أقرب فتحة'}
        </Button>

        <Field label="ملاحظة (اختياري)" htmlFor="bkg-note">
          <Input id="bkg-note" value={note} onChange={(e) => setNote(e.target.value)} />
        </Field>

        {error ? <p className="text-sm text-danger">{error}</p> : null}

        <div className="flex items-center justify-end gap-2 border-t border-border-subtle pt-3">
          <Button variant="ghost" onClick={onClose}>إلغاء</Button>
          <Button disabled={!ready || saving} onClick={save}>
            {saving ? 'جارٍ الحجز…' : 'احجز'}
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
