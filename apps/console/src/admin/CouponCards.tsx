/**
 * Coupon cards — same idea as PlanCards.tsx. `billing.delete_coupon` was already a real button
 * (it takes no body at all, so the generic engine could already fire it). CouponEditDrawer now
 * handles both create_coupon and update_coupon — value, type, dates, and (billing-service v0.18.0's
 * plan_id field) which app it discounts, or "any app" when left unset.
 */
import { useState } from 'react';
import { Plus, Pencil } from 'lucide-react';
import { Badge } from '../rj-ui/Badge';
import { Card } from '../rj-ui/Card';
import { Button } from '../rj-ui/Button';
import { ConfirmDialog } from '../rj-ui/ConfirmDialog';
import { Modal } from '../rj-ui/Modal';
import { EmptyState } from '../rj-ui/EmptyState';
import { Field, Input, Select } from '../rj-ui/Field';
import { Toggle } from '../rj-ui/Toggle';
import { riyals, riyalsLabel, halalas } from '../money';
import type { AdminAction } from './catalog';
import { req, type AdminSession } from './api';
import { sentenceFor } from '../api';

interface Coupon {
  code: string; type: 'percent' | 'fixed' | 'trial'; value: number; currency?: string;
  status: 'active' | 'scheduled' | 'expired' | 'exhausted' | 'disabled';
  starts_at?: number; expires_at?: number; max_redemptions?: number; redeemed?: number;
  public?: boolean; note?: string; plan_id?: string;
}
interface PlanOption { id: string; name: string }

const STATUS_LABEL: Record<Coupon['status'], { label: string; tone: 'success' | 'warning' | 'neutral' | 'danger' }> = {
  active: { label: 'فعّال', tone: 'success' },
  scheduled: { label: 'مجدوَل', tone: 'warning' },
  expired: { label: 'منتهٍ', tone: 'neutral' },
  exhausted: { label: 'استُنفد', tone: 'neutral' },
  disabled: { label: 'مُعطَّل', tone: 'danger' },
};

function valueLine(c: Pick<Coupon, 'type' | 'value'>): string {
  if (c.type === 'percent') return `خصم ${c.value}%`;
  if (c.type === 'fixed') return `خصم ${riyalsLabel(c.value)}`;
  return 'تجربة مجانية';
}

// epoch seconds <-> an <input type="date"> value (YYYY-MM-DD, local midnight) — the only two
// places a date crosses this boundary, so the conversion lives here once.
function toDateInput(epoch?: number): string {
  if (!epoch) return '';
  return new Date(epoch * 1000).toISOString().slice(0, 10);
}
function fromDateInput(value: string): number | undefined {
  if (!value) return undefined;
  return Math.floor(new Date(`${value}T00:00:00`).getTime() / 1000);
}
function dateLine(epoch?: number): string {
  if (!epoch) return '—';
  // `-u-nu-latn` forces WESTERN digits — plain `ar-SA` renders Arabic-Indic numerals instead,
  // which every other date on this console deliberately avoids (Customer.tsx/Shop.tsx/Plans.tsx's
  // own `-u-nu-latn` dates) — found live from an admin screenshot of a coupon card.
  return new Date(epoch * 1000).toLocaleDateString('ar-SA-u-nu-latn');
}

export function CouponCards({ session, createAction, updateAction, deleteAction, coupons, plans, onReload }: {
  session: AdminSession; createAction?: AdminAction; updateAction?: AdminAction;
  deleteAction?: AdminAction; coupons: Coupon[]; plans: PlanOption[]; onReload: () => void;
}) {
  const [creating, setCreating] = useState(false);
  const planName = (id?: string) => plans.find((p) => p.id === id)?.name;

  return (
    <div className="flex flex-col gap-4">
      {createAction ? (
        <Button type="button" size="sm" className="flex w-fit items-center gap-2" onClick={() => setCreating(true)}>
          <Plus size={14} /> كوبون جديد
        </Button>
      ) : null}

      {coupons.length === 0 ? (
        <EmptyState title="لا كوبونات مُنشأة بعد" />
      ) : (
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {coupons.map((c) => (
            <CouponCard key={c.code} session={session} coupon={c} planName={planName(c.plan_id)}
                       updateAction={updateAction} deleteAction={deleteAction} plans={plans} onReload={onReload} />
          ))}
        </div>
      )}

      {createAction ? (
        <CouponEditDrawer session={session} action={createAction} mode="create" plans={plans}
                         open={creating} onClose={() => setCreating(false)}
                         onSaved={() => { setCreating(false); onReload(); }} />
      ) : null}
    </div>
  );
}

function CouponCard({ session, coupon, planName, updateAction, deleteAction, plans, onReload }: {
  session: AdminSession; coupon: Coupon; planName?: string;
  updateAction?: AdminAction; deleteAction?: AdminAction; plans: PlanOption[]; onReload: () => void;
}) {
  const [busy, setBusy] = useState(false);
  const [armDelete, setArmDelete] = useState(false);
  const [editing, setEditing] = useState(false);
  const status = STATUS_LABEL[coupon.status];

  async function doDelete() {
    if (!deleteAction) return;
    setBusy(true);
    try {
      await req(deleteAction.path.replace('{code}', encodeURIComponent(coupon.code)),
                'DELETE', undefined, session.access_token);
      onReload();
    } finally {
      setBusy(false);
      setArmDelete(false);
    }
  }

  return (
    <Card className="flex flex-col gap-3 p-4">
      <div className="flex items-start justify-between gap-2">
        <h3 dir="ltr" className="text-lg font-semibold">{coupon.code}</h3>
        <Badge tone={status.tone}>{status.label}</Badge>
      </div>

      <p className="text-xl font-bold">{valueLine(coupon)}</p>

      <ul className="flex flex-col gap-1 text-sm">
        <li className="flex items-center justify-between gap-2">
          <span className="text-text-secondary">التطبيق</span>
          <span className="font-medium">{coupon.plan_id ? (planName ?? coupon.plan_id) : 'أي تطبيق'}</span>
        </li>
        <li className="flex items-center justify-between gap-2">
          <span className="text-text-secondary">الاستخدام</span>
          <span className="font-medium">
            {coupon.redeemed ?? 0} / {coupon.max_redemptions ? coupon.max_redemptions : 'غير محدود'}
          </span>
        </li>
        <li className="flex items-center justify-between gap-2">
          <span className="text-text-secondary">البداية</span>
          <span className="font-medium">{dateLine(coupon.starts_at)}</span>
        </li>
        <li className="flex items-center justify-between gap-2">
          <span className="text-text-secondary">الانتهاء</span>
          <span className="font-medium">{dateLine(coupon.expires_at)}</span>
        </li>
        <li className="flex items-center justify-between gap-2">
          <span className="text-text-secondary">ظاهر للعملاء</span>
          <span className="font-medium">{coupon.public ? 'نعم' : 'لا'}</span>
        </li>
      </ul>

      {coupon.note ? <p className="text-label text-text-secondary">{coupon.note}</p> : null}

      <div className="flex gap-2">
        {updateAction ? (
          <Button type="button" size="sm" variant="outline" className="flex flex-1 items-center justify-center gap-2"
                  disabled={busy} onClick={() => setEditing(true)}>
            <Pencil size={14} /> تعديل
          </Button>
        ) : null}
        {deleteAction ? (
          <Button type="button" size="sm" variant="outline" className="flex-1 text-danger" disabled={busy}
                  onClick={() => setArmDelete(true)}>
            حذف
          </Button>
        ) : null}
      </div>

      <ConfirmDialog open={armDelete} onClose={() => setArmDelete(false)} onConfirm={doDelete}
                    busy={busy} danger title={`حذف "${coupon.code}"؟`}
                    body="لا رجعة — سجل الاستخدام السابق يبقى، لكن الكود ما يشتغل بعدها." />

      {updateAction ? (
        <CouponEditDrawer session={session} action={updateAction} mode="edit" coupon={coupon} plans={plans}
                         open={editing} onClose={() => setEditing(false)}
                         onSaved={() => { setEditing(false); onReload(); }} />
      ) : null}
    </Card>
  );
}

/** Shared by "كوبون جديد" (create_coupon, POST) and a card's own "تعديل" (update_coupon, PATCH,
 *  {code} in the path). `plan_id` empty means "any app" — the coupon's existing, backward-
 *  compatible default; a real selection scopes it, enforced server-side per base-services' own
 *  confirmed contract (COUPON_PLAN_MISMATCH). */
function CouponEditDrawer({ session, action, mode, coupon, plans, open, onClose, onSaved }: {
  session: AdminSession; action: AdminAction; mode: 'create' | 'edit'; coupon?: Coupon;
  plans: PlanOption[]; open: boolean; onClose: () => void; onSaved: () => void;
}) {
  const [code, setCode] = useState(coupon?.code ?? '');
  const [type, setType] = useState<Coupon['type']>(coupon?.type ?? 'percent');
  const [valueText, setValueText] = useState(
    coupon ? (coupon.type === 'fixed' ? riyals(coupon.value) : String(coupon.value)) : '');
  const [planId, setPlanId] = useState(coupon?.plan_id ?? '');
  const [startsAt, setStartsAt] = useState(toDateInput(coupon?.starts_at));
  const [expiresAt, setExpiresAt] = useState(toDateInput(coupon?.expires_at));
  const [maxRedemptions, setMaxRedemptions] = useState(String(coupon?.max_redemptions ?? 0));
  const [isPublic, setIsPublic] = useState(coupon?.public ?? false);
  const [note, setNote] = useState(coupon?.note ?? '');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  async function save() {
    if (mode === 'create' && !code.trim()) { setError('أدخل كود الكوبون.'); return; }
    const rawValue = type === 'fixed' ? halalas(valueText) : Number(valueText);
    if (rawValue === null || Number.isNaN(rawValue) || rawValue < 0) { setError('قيمة غير صحيحة.'); return; }
    if (type === 'percent' && rawValue > 100) { setError('النسبة أقصاها 100%.'); return; }
    const redemptions = Number(maxRedemptions);
    if (!Number.isInteger(redemptions) || redemptions < 0) { setError('عدد استخدامات غير صحيح.'); return; }

    setBusy(true);
    setError('');
    try {
      const body: Record<string, unknown> = {
        type, value: rawValue, plan_id: planId || '',
        starts_at: fromDateInput(startsAt) ?? null, expires_at: fromDateInput(expiresAt) ?? null,
        max_redemptions: redemptions, public: isPublic, note,
      };
      if (mode === 'create') body.code = code.trim().toUpperCase();
      const path = mode === 'edit' && coupon
        ? action.path.replace('{code}', encodeURIComponent(coupon.code)) : action.path;
      await req(path, mode === 'edit' ? 'PATCH' : 'POST', body, session.access_token);
      onSaved();
    } catch (err) {
      setError(sentenceFor(err, 'تعذّر حفظ القسيمة.'));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Modal open={open} onClose={onClose} title={mode === 'create' ? 'كوبون جديد' : `تعديل "${coupon?.code}"`}
           footer={
             <>
               <Button type="button" variant="ghost" onClick={onClose}>إلغاء</Button>
               <Button type="button" disabled={busy} onClick={save}>{busy ? 'جارٍ الحفظ…' : 'حفظ'}</Button>
             </>
           }>
      <div className="flex flex-col gap-4">
        {mode === 'create' ? (
          <Field label="الكود" htmlFor="coupon-code" hint="بالإنجليزية، بدون مسافات">
            <Input id="coupon-code" dir="ltr" value={code} onChange={(e) => setCode(e.target.value)} />
          </Field>
        ) : null}

        <div className="grid grid-cols-2 gap-3">
          <Field label="النوع" htmlFor="coupon-type">
            <Select id="coupon-type" value={type} onChange={(e) => setType(e.target.value as Coupon['type'])}>
              <option value="percent">نسبة مئوية</option>
              <option value="fixed">مبلغ ثابت</option>
              <option value="trial">تجربة مجانية</option>
            </Select>
          </Field>
          <Field label={type === 'percent' ? 'النسبة (%)' : type === 'fixed' ? 'المبلغ (ريال)' : 'أيام التجربة'}
                htmlFor="coupon-value">
            <Input id="coupon-value" dir="ltr" value={valueText} onChange={(e) => setValueText(e.target.value)} />
          </Field>
        </div>

        <Field label="التطبيق" htmlFor="coupon-plan" hint="اتركها فارغة ليطبَّق الخصم على أي تطبيق">
          <Select id="coupon-plan" value={planId} onChange={(e) => setPlanId(e.target.value)}>
            <option value="">— أي تطبيق —</option>
            {plans.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
          </Select>
        </Field>

        <div className="grid grid-cols-2 gap-3">
          <Field label="تاريخ البداية" htmlFor="coupon-starts">
            <Input id="coupon-starts" type="date" dir="ltr" value={startsAt}
                  onChange={(e) => setStartsAt(e.target.value)} />
          </Field>
          <Field label="تاريخ الانتهاء" htmlFor="coupon-expires">
            <Input id="coupon-expires" type="date" dir="ltr" value={expiresAt}
                  onChange={(e) => setExpiresAt(e.target.value)} />
          </Field>
        </div>

        <Field label="حد الاستخدام" htmlFor="coupon-max" hint="0 = بلا حد">
          <Input id="coupon-max" dir="ltr" inputMode="numeric" value={maxRedemptions}
                onChange={(e) => setMaxRedemptions(e.target.value)} />
        </Field>

        <div className="flex items-center justify-between">
          <span className="text-sm">إظهار للعملاء (عرض عام)</span>
          <Toggle checked={isPublic} onChange={setIsPublic} ariaLabel="إظهار للعملاء" />
        </div>

        <Field label="ملاحظة" htmlFor="coupon-note" hint="للمشغّلين فقط، لا يراها العميل">
          <Input id="coupon-note" value={note} onChange={(e) => setNote(e.target.value)} />
        </Field>

        {error ? <p role="alert" className="text-danger text-sm">{error}</p> : null}
      </div>
    </Modal>
  );
}
