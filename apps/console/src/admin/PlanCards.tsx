/**
 * Plan cards — replaces the raw generic table (English column names, unpacked JSON per cell) that
 * used to render `billing.list_plans`. Every limit/feature is translated to a readable Arabic
 * line instead of a technical key, and the price goes through `../money.ts` (the same rule
 * everywhere else in the product: halalas on the wire, riyals on the screen).
 *
 * VISUAL LANGUAGE MATCHES `KpiCard.tsx`, NOT INVENTED HERE: soft-tone icon badge, generous
 * padding, shadow-sm, a big tabular-nums number as the focal point — the same vocabulary the rest
 * of the admin panel already reads as "polished". The first pass of this file used plain text
 * rows and a raw period string leaked straight from the API ("billing_period", never translated)
 * — found live, both fixed here: boolean features get a check/x icon, gauges/counters a numeric
 * chip, and PERIOD_LABEL now covers both real values billing-service actually returns.
 *
 * The active/listed toggle calls `billing.plan_availability` directly — the ONE of the three plan
 * actions (`update_plan`/`plan_availability`) that becomes a real button here, because it is the
 * only one with a simple body param (active/listed, both booleans) a purpose-built card can fill
 * in itself — unlike the generic engine, which always sent an empty body (see AdminApps.tsx's own
 * older note). Full editing (`update_plan`) and creating a new plan (`create_plan`) still need a
 * real form — deferred to a later screen, same call as before, still correct.
 */
import { useState } from 'react';
import {
  Package, Check, X, Power, Pencil, Users, GitBranch, Plug, Sparkles, Gift,
  Megaphone, LineChart, MessageSquare, FileText,
} from 'lucide-react';
import { Badge } from '../rj-ui/Badge';
import { Button } from '../rj-ui/Button';
import { ConfirmDialog } from '../rj-ui/ConfirmDialog';
import { Drawer } from '../rj-ui/Drawer';
import { EmptyState } from '../rj-ui/EmptyState';
import { Field, Input, Select } from '../rj-ui/Field';
import { Toggle } from '../rj-ui/Toggle';
import { riyals, riyalsLabel, halalas } from '../money';
import type { AdminAction } from './catalog';
import { req, type AdminSession } from './api';

interface LimitEntry { kind: 'boolean' | 'gauge' | 'counter' | string; limit: number | 'unlimited'; period?: string }
interface Price { type: string; currency: string; interval: string; amount_minor: number }
interface Plan {
  id: string; name: string; active: boolean; listed: boolean;
  prices: Price[]; limits: Record<string, LimitEntry>; trial_days: number;
}

// technical key -> Arabic label + icon. An unknown key still renders (label = the raw key, a
// generic icon) — never hidden, never breaks the screen. Extend this the day billing-service adds
// a new limit; never guess ahead of it.
const LIMIT_META: Record<string, { label: string; icon: typeof Users }> = {
  'staff.seats': { label: 'مقاعد الموظفين', icon: Users },
  'branches': { label: 'الفروع', icon: GitBranch },
  'feature.base': { label: 'الميزات الأساسية', icon: Sparkles },
  'feature.bookings': { label: 'الحجوزات', icon: Gift },
  'feature.api': { label: 'واجهة API', icon: Plug },
  'feature.loyalty': { label: 'برنامج النقاط', icon: Gift },
  'feature.campaigns': { label: 'الحملات', icon: Megaphone },
  'feature.insights.engine': { label: 'محرّك التحليلات', icon: LineChart },
  'messages.monthly': { label: 'رسائل واتساب', icon: MessageSquare },
  'templates.custom': { label: 'القوالب المخصّصة', icon: FileText },
};

// "month" (a calendar month, regardless of billing interval — templates.custom's own reset clock)
// and "billing_period" (once per subscription cycle, whatever its interval is — messages.monthly's
// own) are the two real values billing-service returns; anything else still renders, verbatim,
// rather than being swallowed.
const PERIOD_LABEL: Record<string, string> = { month: 'شهرياً', billing_period: 'كل دورة فوترة' };

function amountLine(entry: LimitEntry): string {
  const amount = entry.limit === 'unlimited' ? 'غير محدود' : String(entry.limit);
  if (entry.kind === 'counter' && entry.period) {
    return `${amount} / ${PERIOD_LABEL[entry.period] ?? entry.period}`;
  }
  return amount;
}

const INTERVAL_LABEL: Record<string, string> = { month: 'شهرياً', year: 'سنوياً' };

export function PlanCards({ session, listAction, availabilityAction, updateAction, plans, onReload }: {
  session: AdminSession; listAction: AdminAction; availabilityAction?: AdminAction;
  updateAction?: AdminAction; plans: Plan[]; onReload: () => void;
}) {
  if (plans.length === 0) {
    return <EmptyState title="لا باقات مضبوطة بعد" />;
  }
  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3">
      {plans.map((p) => (
        <PlanCard key={p.id} session={session} plan={p} availabilityAction={availabilityAction}
                 updateAction={updateAction} onReload={onReload} />
      ))}
    </div>
  );
}

function PlanCard({ session, plan, availabilityAction, updateAction, onReload }: {
  session: AdminSession; plan: Plan; availabilityAction?: AdminAction; updateAction?: AdminAction;
  onReload: () => void;
}) {
  const [busy, setBusy] = useState(false);
  const [armActive, setArmActive] = useState(false);
  const [editing, setEditing] = useState(false);
  const price = plan.prices[0];
  const limitEntries = Object.entries(plan.limits);
  const booleans = limitEntries.filter(([, e]) => e.kind === 'boolean');
  const counted = limitEntries.filter(([, e]) => e.kind !== 'boolean');

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
    <section className={[
      'flex flex-col gap-4 rounded-card border p-5 shadow-sm transition-opacity',
      plan.active ? 'border-border-subtle bg-surface-1' : 'border-border-subtle bg-surface-1 opacity-70',
    ].join(' ')}>
      <div className="flex items-start justify-between gap-3">
        <span className="inline-flex w-fit rounded-lg bg-accent-soft p-2 text-accent-on-soft">
          <Package size={20} />
        </span>
        <div className="flex flex-col items-end gap-1">
          <Badge tone={plan.active ? 'success' : 'neutral'}>{plan.active ? 'نشطة' : 'متوقفة'}</Badge>
          {!plan.listed ? <Badge tone="warning">مخفية عن القائمة</Badge> : null}
        </div>
      </div>

      <div>
        <h3 className="text-lg font-semibold text-text-primary">{plan.name}</h3>
        <p className="mt-1 tabular-nums tracking-tight">
          <span className="text-3xl font-semibold">{price ? riyalsLabel(price.amount_minor) : '—'}</span>
          {price ? <span className="text-sm font-medium text-text-secondary"> / {INTERVAL_LABEL[price.interval] ?? price.interval}</span> : null}
        </p>
        {plan.trial_days > 0 ? (
          <p className="mt-0.5 text-xs text-text-muted">تجربة مجانية {plan.trial_days} يوماً</p>
        ) : null}
      </div>

      {booleans.length > 0 ? (
        <div className="grid grid-cols-1 gap-1.5 sm:grid-cols-2">
          {booleans.map(([key, entry]) => {
            const meta = LIMIT_META[key];
            const Icon = meta?.icon ?? Sparkles;
            const on = Boolean(entry.limit);
            return (
              <div key={key} className={`flex items-center gap-2 text-sm ${on ? 'text-text-primary' : 'text-text-muted'}`}>
                {on ? <Check size={15} className="shrink-0 text-success" /> : <X size={15} className="shrink-0 text-text-muted" />}
                <Icon size={14} className="shrink-0" />
                <span>{meta?.label ?? key}</span>
              </div>
            );
          })}
        </div>
      ) : null}

      {counted.length > 0 ? (
        <ul className="flex flex-col gap-1.5 border-t border-border-subtle pt-3 text-sm">
          {counted.map(([key, entry]) => {
            const meta = LIMIT_META[key];
            return (
              <li key={key} className="flex items-center justify-between gap-2">
                <span className="flex items-center gap-2 text-text-secondary">
                  {meta ? <meta.icon size={14} className="shrink-0" /> : null}
                  {meta?.label ?? key}
                </span>
                <span className="font-medium tabular-nums">{amountLine(entry)}</span>
              </li>
            );
          })}
        </ul>
      ) : null}

      <div className="flex gap-2">
        {updateAction ? (
          <Button type="button" size="sm" variant="outline"
                  className="flex flex-1 items-center justify-center gap-2"
                  onClick={() => setEditing(true)}>
            <Pencil size={14} /> تعديل
          </Button>
        ) : null}
        {availabilityAction ? (
          <Button type="button" size="sm" variant="outline" disabled={busy}
                  className="flex flex-1 items-center justify-center gap-2"
                  onClick={() => setArmActive(true)}>
            <Power size={14} /> {plan.active ? 'إيقاف' : 'تفعيل'}
          </Button>
        ) : null}
      </div>

      <ConfirmDialog open={armActive} onClose={() => setArmActive(false)} onConfirm={toggleActive}
                    busy={busy} danger={plan.active}
                    title={plan.active ? `إيقاف "${plan.name}"؟` : `تفعيل "${plan.name}"؟`}
                    body={plan.active
                      ? 'لا أحد جديد يقدر يشترك فيها — المشتركون الحاليون ما يتأثرون.'
                      : 'تصير متاحة للاشتراك من جديد.'} />

      {updateAction ? (
        <PlanEditDrawer session={session} plan={plan} updateAction={updateAction} open={editing}
                       onClose={() => setEditing(false)}
                       onSaved={() => { setEditing(false); onReload(); }} />
      ) : null}
    </section>
  );
}

/** `billing.update_plan` PATCH — name, the first price's amount, trial days, and every EXISTING
 *  limit's value (booleans as a toggle, numbers as a field with an "unlimited" override). Adding
 *  a brand-new limit key or a second price/interval still needs a schema-aware form — out of
 *  scope here, same as create_plan; this edits what a plan already has, thoroughly, not what it
 *  could have. */
function PlanEditDrawer({ session, plan, updateAction, open, onClose, onSaved }: {
  session: AdminSession; plan: Plan; updateAction: AdminAction;
  open: boolean; onClose: () => void; onSaved: () => void;
}) {
  const [name, setName] = useState(plan.name);
  const [priceText, setPriceText] = useState(plan.prices[0] ? riyals(plan.prices[0].amount_minor) : '0');
  const [interval, setInterval_] = useState(plan.prices[0]?.interval ?? 'month');
  const [trialDays, setTrialDays] = useState(String(plan.trial_days));
  const [limits, setLimits] = useState<Record<string, LimitEntry>>(() => structuredClone(plan.limits));
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  function setLimitValue(key: string, patch: Partial<LimitEntry>) {
    setLimits((prev) => ({ ...prev, [key]: { ...prev[key], ...patch } }));
  }

  async function save() {
    const amount = halalas(priceText);
    if (amount === null || amount < 0) { setError('سعر غير صحيح.'); return; }
    const days = Number(trialDays);
    if (!Number.isInteger(days) || days < 0) { setError('عدد أيام التجربة غير صحيح.'); return; }

    setBusy(true);
    setError('');
    try {
      await req(updateAction.path.replace('{plan_id}', encodeURIComponent(plan.id)), 'PATCH', {
        name,
        prices: [{ ...plan.prices[0], amount_minor: amount, interval }],
        limits,
        trial_days: days,
      }, session.access_token);
      onSaved();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'تعذّر الحفظ.');
    } finally {
      setBusy(false);
    }
  }

  return (
    <Drawer open={open} onClose={onClose} title={`تعديل "${plan.name}"`}
           footer={
             <>
               <Button type="button" variant="ghost" onClick={onClose}>إلغاء</Button>
               <Button type="button" disabled={busy} onClick={save}>
                 {busy ? 'جارٍ الحفظ…' : 'حفظ'}
               </Button>
             </>
           }>
      <div className="flex flex-col gap-4">
        <Field label="الاسم" htmlFor="plan-name">
          <Input id="plan-name" value={name} onChange={(e) => setName(e.target.value)} />
        </Field>

        <div className="grid grid-cols-2 gap-3">
          <Field label="السعر (ريال)" htmlFor="plan-price">
            <Input id="plan-price" dir="ltr" value={priceText} onChange={(e) => setPriceText(e.target.value)} />
          </Field>
          <Field label="الدورة" htmlFor="plan-interval">
            <Select id="plan-interval" value={interval} onChange={(e) => setInterval_(e.target.value)}>
              <option value="month">شهرياً</option>
              <option value="year">سنوياً</option>
            </Select>
          </Field>
        </div>

        <Field label="أيام التجربة المجانية" htmlFor="plan-trial">
          <Input id="plan-trial" dir="ltr" inputMode="numeric" value={trialDays}
                onChange={(e) => setTrialDays(e.target.value)} />
        </Field>

        {Object.keys(limits).length > 0 ? (
          <div className="flex flex-col gap-3 border-t border-border-subtle pt-4">
            <h4 className="text-sm font-semibold text-text-secondary">الحدود والميزات</h4>
            {Object.entries(limits).map(([key, entry]) => (
              <div key={key} className="flex items-center justify-between gap-3">
                <span className="text-sm">{LIMIT_META[key]?.label ?? key}</span>
                {entry.kind === 'boolean' ? (
                  <Toggle checked={Boolean(entry.limit)}
                         onChange={(v) => setLimitValue(key, { limit: v ? 1 : 0 })}
                         ariaLabel={LIMIT_META[key]?.label ?? key} />
                ) : (
                  <div className="flex items-center gap-2">
                    <Input dir="ltr" inputMode="numeric" className="w-20"
                          disabled={entry.limit === 'unlimited'}
                          value={entry.limit === 'unlimited' ? '' : String(entry.limit)}
                          onChange={(e) => setLimitValue(key, { limit: Number(e.target.value) || 0 })} />
                    <label className="flex items-center gap-1.5 text-xs text-text-secondary">
                      <input type="checkbox" checked={entry.limit === 'unlimited'}
                            onChange={(e) => setLimitValue(key, { limit: e.target.checked ? 'unlimited' : 0 })} />
                      غير محدود
                    </label>
                  </div>
                )}
              </div>
            ))}
          </div>
        ) : null}

        {error ? <p role="alert" className="text-danger text-sm">{error}</p> : null}
      </div>
    </Drawer>
  );
}
