/**
 * Coupon cards — same idea as PlanCards.tsx. `billing.delete_coupon` becomes a real button here
 * (it takes no body at all, so the generic engine could already fire it — this just puts it next
 * to the rest of the card instead of a raw table row). `update_coupon`/`create_coupon` (editing
 * value, type, dates) need a real form — deferred, same as the plan screen.
 */
import { useState } from 'react';
import { Badge } from '../rj-ui/Badge';
import { Button } from '../rj-ui/Button';
import { ConfirmDialog } from '../rj-ui/ConfirmDialog';
import { EmptyState } from '../rj-ui/EmptyState';
import { riyalsLabel } from '../money';
import type { AdminAction } from './catalog';
import { req, type AdminSession } from './api';

interface Coupon {
  code: string; type: 'percent' | 'fixed' | 'trial'; value: number; currency?: string;
  status: 'active' | 'scheduled' | 'expired' | 'exhausted' | 'disabled';
  starts_at?: number; expires_at?: number; max_redemptions?: number; redeemed?: number;
  public?: boolean; note?: string;
}

const STATUS_LABEL: Record<Coupon['status'], { label: string; tone: 'success' | 'warning' | 'neutral' | 'danger' }> = {
  active: { label: 'فعّال', tone: 'success' },
  scheduled: { label: 'مجدوَل', tone: 'warning' },
  expired: { label: 'منتهٍ', tone: 'neutral' },
  exhausted: { label: 'استُنفد', tone: 'neutral' },
  disabled: { label: 'مُعطَّل', tone: 'danger' },
};

function valueLine(c: Coupon): string {
  if (c.type === 'percent') return `خصم ${c.value}%`;
  if (c.type === 'fixed') return `خصم ${riyalsLabel(c.value)}`;
  return 'تجربة مجانية';
}

function dateLine(epoch?: number): string {
  if (!epoch) return '—';
  return new Date(epoch * 1000).toLocaleDateString('ar-SA');
}

export function CouponCards({ session, deleteAction, coupons, onReload }: {
  session: AdminSession; deleteAction?: AdminAction; coupons: Coupon[]; onReload: () => void;
}) {
  if (coupons.length === 0) {
    return <EmptyState title="لا كوبونات مُنشأة بعد" />;
  }
  return (
    <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
      {coupons.map((c) => (
        <CouponCard key={c.code} session={session} coupon={c} deleteAction={deleteAction} onReload={onReload} />
      ))}
    </div>
  );
}

function CouponCard({ session, coupon, deleteAction, onReload }: {
  session: AdminSession; coupon: Coupon; deleteAction?: AdminAction; onReload: () => void;
}) {
  const [busy, setBusy] = useState(false);
  const [armDelete, setArmDelete] = useState(false);
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
    <section className="flex flex-col gap-3 rounded-card border border-border-subtle bg-surface-1 p-4">
      <div className="flex items-start justify-between gap-2">
        <h3 dir="ltr" className="text-lg font-semibold">{coupon.code}</h3>
        <Badge tone={status.tone}>{status.label}</Badge>
      </div>

      <p className="text-xl font-bold">{valueLine(coupon)}</p>

      <ul className="flex flex-col gap-1 text-sm">
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

      {deleteAction ? (
        <Button type="button" size="sm" variant="outline" className="text-danger" disabled={busy}
                onClick={() => setArmDelete(true)}>
          حذف الكوبون
        </Button>
      ) : null}

      <ConfirmDialog open={armDelete} onClose={() => setArmDelete(false)} onConfirm={doDelete}
                    busy={busy} danger title={`حذف "${coupon.code}"؟`}
                    body="لا رجعة — سجل الاستخدام السابق يبقى، لكن الكود ما يشتغل بعدها." />
    </section>
  );
}
