/**
 * Plan cards — replaces the raw generic table (English column names, unpacked JSON per cell) that
 * used to render `billing.list_plans`. Every limit/feature is translated to a readable Arabic
 * line instead of a technical key, and the price goes through `../money.ts` (the same rule
 * everywhere else in the product: halalas on the wire, riyals on the screen).
 *
 * The active/listed toggle calls `billing.plan_availability` directly — the ONE of the three plan
 * actions (`update_plan`/`plan_availability`) that becomes a real button here, because it is the
 * only one with a simple body param (active/listed, both booleans) a purpose-built card can fill
 * in itself — unlike the generic engine, which always sent an empty body (see AdminApps.tsx's own
 * older note). Full editing (`update_plan`) and creating a new plan (`create_plan`) still need a
 * real form — deferred to a later screen, same call as before, still correct.
 */
import { useState } from 'react';
import { Badge } from '../rj-ui/Badge';
import { Button } from '../rj-ui/Button';
import { ConfirmDialog } from '../rj-ui/ConfirmDialog';
import { EmptyState } from '../rj-ui/EmptyState';
import { riyalsLabel } from '../money';
import type { AdminAction } from './catalog';
import { req, type AdminSession } from './api';

interface LimitEntry { kind: 'boolean' | 'gauge' | 'counter' | string; limit: number | 'unlimited'; period?: string }
interface Price { type: string; currency: string; interval: string; amount_minor: number }
interface Plan {
  id: string; name: string; active: boolean; listed: boolean;
  prices: Price[]; limits: Record<string, LimitEntry>; trial_days: number;
}

// technical key -> Arabic label. An unknown key renders as-is (never hidden, never breaks the
// screen) — extend this the day billing-service adds a new limit, never guess ahead of it.
const LIMIT_LABELS: Record<string, string> = {
  'staff.seats': 'مقاعد الموظفين',
  'branches': 'الفروع',
  'feature.base': 'الميزات الأساسية',
  'feature.bookings': 'الحجوزات',
  'feature.api': 'واجهة API',
  'feature.loyalty': 'برنامج النقاط',
  'feature.campaigns': 'الحملات',
  'feature.insights.engine': 'محرّك التحليلات',
  'messages.monthly': 'رسائل واتساب الشهرية',
  'templates.custom': 'القوالب المخصّصة',
};

function limitLine(entry: LimitEntry): string {
  if (entry.kind === 'boolean') return entry.limit ? 'متاحة' : 'غير متاحة';
  const amount = entry.limit === 'unlimited' ? 'غير محدود' : String(entry.limit);
  if (entry.kind === 'counter' && entry.period) return `${amount} / ${entry.period === 'month' ? 'شهرياً' : entry.period}`;
  return amount;
}

const INTERVAL_LABEL: Record<string, string> = { month: 'شهرياً', year: 'سنوياً' };

export function PlanCards({ session, listAction, availabilityAction, plans, onReload }: {
  session: AdminSession; listAction: AdminAction; availabilityAction?: AdminAction;
  plans: Plan[]; onReload: () => void;
}) {
  if (plans.length === 0) {
    return <EmptyState title="لا باقات مضبوطة بعد" />;
  }
  return (
    <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
      {plans.map((p) => (
        <PlanCard key={p.id} session={session} plan={p} availabilityAction={availabilityAction} onReload={onReload} />
      ))}
    </div>
  );
}

function PlanCard({ session, plan, availabilityAction, onReload }: {
  session: AdminSession; plan: Plan; availabilityAction?: AdminAction; onReload: () => void;
}) {
  const [busy, setBusy] = useState(false);
  const [armActive, setArmActive] = useState(false);
  const price = plan.prices[0];

  async function toggleActive() {
    if (!availabilityAction) return;
    setBusy(true);
    try {
      await req(availabilityAction.path.replace('{plan_id}', encodeURIComponent(plan.id)),
                'POST', { active: !plan.active }, session.access_token);
      onReload();
    } finally {
      setBusy(false);
      setArmActive(false);
    }
  }

  return (
    <section className="flex flex-col gap-3 rounded-card border border-border-subtle bg-surface-1 p-4">
      <div className="flex items-start justify-between gap-2">
        <h3 className="text-lg font-semibold">{plan.name}</h3>
        <div className="flex flex-col items-end gap-1">
          <Badge tone={plan.active ? 'success' : 'neutral'}>{plan.active ? 'نشطة' : 'متوقفة'}</Badge>
          {!plan.listed ? <Badge tone="warning">مخفية عن القائمة</Badge> : null}
        </div>
      </div>

      <p className="text-2xl font-bold">
        {price ? riyalsLabel(price.amount_minor) : '—'}
        {price ? <span className="text-sm font-normal text-text-secondary"> / {INTERVAL_LABEL[price.interval] ?? price.interval}</span> : null}
      </p>

      {plan.trial_days > 0 ? (
        <p className="text-label text-text-secondary">تجربة مجانية {plan.trial_days} يوماً</p>
      ) : null}

      <ul className="flex flex-col gap-1 text-sm">
        {Object.entries(plan.limits).map(([key, entry]) => (
          <li key={key} className="flex items-center justify-between gap-2">
            <span className="text-text-secondary">{LIMIT_LABELS[key] ?? key}</span>
            <span className="font-medium">{limitLine(entry)}</span>
          </li>
        ))}
      </ul>

      {availabilityAction ? (
        <Button type="button" size="sm" variant="outline" disabled={busy}
                onClick={() => setArmActive(true)}>
          {plan.active ? 'إيقاف الباقة' : 'تفعيل الباقة'}
        </Button>
      ) : null}

      <ConfirmDialog open={armActive} onClose={() => setArmActive(false)} onConfirm={toggleActive}
                    busy={busy} danger={plan.active}
                    title={plan.active ? `إيقاف "${plan.name}"؟` : `تفعيل "${plan.name}"؟`}
                    body={plan.active
                      ? 'لا أحد جديد يقدر يشترك فيها — المشتركون الحاليون ما يتأثرون.'
                      : 'تصير متاحة للاشتراك من جديد.'} />
    </section>
  );
}
