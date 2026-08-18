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
  ensureCustomer, type FieldOperator, sentenceFor, suggestByPrefix,
} from '../api';
import { asLocal } from '../phone';
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
  { session, branchId, date, initialOperatorId, initialStartsAt, services, staff, onClose,
   onCreated }: BookingDialogProps,
) {
  const [phone, setPhone] = useState('');
  const [matches, setMatches] = useState<CustomerHit[]>([]);
  const [customer, setCustomer] = useState<CustomerHit | null>(null);
  const [name, setName] = useState('');
  const [chosen, setChosen] = useState<string[]>([]);
  const [operatorId, setOperatorId] = useState(initialOperatorId ?? '');
  const [day, setDay] = useState(date);
  const [time, setTime] = useState(initialStartsAt ? timeOfEpoch(initialStartsAt) : '');
  const [note, setNote] = useState('');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
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
        .catch(() => { if (!stale) setMatches([]); });
    }, 180);
    return () => { stale = true; window.clearTimeout(id); };
  }, [phone, session]);

  const durationTotal = useMemo(() => {
    const byId = new Map(services.map((s) => [s.id, s.duration_minutes ?? 0]));
    return chosen.reduce((sum, id) => sum + (byId.get(id) ?? 0), 0);
  }, [chosen, services]);
  // A SELECTED SERVICE WITH NO DURATION SET REFUSES THE SAVE, NEVER GUESSES — the same rule the
  // server itself enforces; said here too so he learns it before the round trip, not after.
  const missingDuration = chosen.some((id) => {
    const s = services.find((x) => x.id === id);
    return s && !s.duration_minutes;
  });

  const starts_at = (() => {
    if (!day || !time) return 0;
    const at = Date.parse(`${day}T${time}:00+03:00`);
    return Number.isNaN(at) ? 0 : Math.floor(at / 1000);
  })();

  const ready = Boolean((customer || phone.trim().length >= 3) && chosen.length > 0
    && !missingDuration && operatorId && starts_at > 0);

  const save = async () => {
    if (!ready || saving) return;
    setSaving(true);
    setError('');
    try {
      // THE CUSTOMER, RESOLVED-OR-CREATED HERE, AT THE MOMENT HE COMMITS — not while he types,
      // which would create a row for every phone he tries and abandons.
      const c = customer ?? (await ensureCustomer(session, phone, name)).customer;
      const booking = await createBooking(session, {
        branch_id: branchId, operator_id: operatorId, customer_id: c.id, service_ids: chosen,
        starts_at, note: note.trim() || undefined, idempotency_key: idempotencyKey,
      });
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
        {/* ── العميلة ─────────────────────────────────────────────────────────────────── */}
        <Field label="جوّال العميلة" required htmlFor="bkg-phone">
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
        {matches.length > 0 && !customer ? (
          <div className="flex flex-col gap-1">
            {matches.slice(0, 4).map((m) => (
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
          <p className="text-sm text-success">✓ عميلة معروفة{customer.name ? ` — ${customer.name}` : ''}</p>
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
              <p className="mt-1 text-sm text-danger">
                إحدى الخدمات المختارة بلا مدة مضبوطة — اضبطها من «خدماتي».
              </p>
            ) : (
              <p className="mt-1 text-sm text-text-secondary">المدة الإجمالية: {durationTotal} دقيقة</p>
            )
          ) : null}
        </div>

        {/* ── الموظفة ─────────────────────────────────────────────────────────────────── */}
        <Field label="الموظفة" required htmlFor="bkg-op">
          <select
            id="bkg-op"
            value={operatorId}
            onChange={(e) => setOperatorId(e.target.value)}
            className="h-11 w-full rounded-xl bg-surface-1 px-3 shadow-sm"
          >
            <option value="">اختاري…</option>
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

        <Field label="ملاحظة (اختياري)" htmlFor="bkg-note">
          <Input id="bkg-note" value={note} onChange={(e) => setNote(e.target.value)} />
        </Field>

        {error ? <p className="text-sm text-danger">{error}</p> : null}

        <div className="flex items-center justify-end gap-2 border-t border-border-subtle pt-3">
          <Button variant="ghost" onClick={onClose}>إلغاء</Button>
          <Button disabled={!ready || saving} onClick={save}>
            {saving ? 'جارٍ الحجز…' : 'احجزي'}
          </Button>
        </div>
      </div>
    </Modal>
  );
}
