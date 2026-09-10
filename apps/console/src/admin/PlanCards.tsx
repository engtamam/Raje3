/**
 * Plan cards — replaces the raw generic table (English column names, unpacked JSON per cell) that
 * used to render `billing.list_plans`. Every limit/feature is translated to a readable Arabic
 * line instead of a technical key, and the price goes through `../money.ts` (the same rule
 * everywhere else in the product: halalas on the wire, riyals on the screen).
 *
 * SAME WORDING AS THE SHOP-OWNER-FACING «الاشتراك» SCREEN, ON PURPOSE. `LIMIT_WORDS` and
 * `REQUIRES_ANY_LABELS` are `Plans.tsx`'s own maps, exported from there and imported here rather
 * than re-typed — a raw key that gets a sentence on one screen and stays raw jargon on its sibling
 * is a drift bug waiting to happen the day someone edits only one of the two files. This file adds
 * only what an ADMIN needs beyond that: the icon per key (the shop-owner screen has no room for
 * one), and a slightly more technical fallback for a key `Plans.tsx` deliberately never prints
 * (`plan.requires_any`'s own value shape is a list, never a number — see that file's own note).
 *
 * OWNER'S OWN COMPLAINT, VERBATIM (screenshot reviewed live): every button — تعديل/إيقاف/إخفاء/
 * إظهار — was the same flat grey in every state, so a destructive action (إيقاف: stops new
 * subscriptions) read exactly like a neutral one (تعديل) or a reversible, low-stakes one (إخفاء/
 * إظهار: only changes what the store lists, existing subscribers untouched). Colour now follows
 * what each button's own `onClick` actually does, matching this session's own rule everywhere
 * else (`Plans.tsx`'s own note on its danger cancel button): a fast signal a glance reads, and a
 * destructive action wearing a neutral action's colour is a colour saying nothing.
 *
 * VISUAL LANGUAGE MATCHES `Wallet.tsx` (المحفظتي), the owner's own named quality bar this session
 * — tinted panels, real icon circles, colour-coded state, generous spacing — not `KpiCard.tsx`
 * alone as the very first pass here used. That first pass used plain text rows and a raw period
 * string leaked straight from the API ("billing_period", never translated) — found live, both
 * fixed here: boolean features get a check/x icon, gauges/counters a numeric chip, and
 * PERIOD_LABEL now covers both real values billing-service actually returns.
 *
 * TWO SEPARATE TOGGLES, ONE ROUTE. `active` (can anyone subscribe at all) and `listed` (does the
 * store show it) both call `billing.plan_availability` directly — the ONE of the three app
 * actions (`update_plan`/`plan_availability`) that becomes a real button here, because it is the
 * only one with simple body params (active/listed, both booleans) a purpose-built card can fill
 * in itself — unlike the generic engine, which always sent an empty body (see AdminApps.tsx's own
 * older note). They used to be a SINGLE button that only ever sent `active` — found live, by a
 * full pipeline audit that went looking for a show/hide control and discovered `listed` had never
 * actually been wired to anything in this file, despite the server route always having accepted
 * it. Full editing (`update_plan`) and creating a new app (`create_plan`) still need a real form
 * — deferred to a later screen, same call as before, still correct.
 */
import { useState } from 'react';
import {
  Package, Check, X, Power, Pencil, Users, GitBranch, Plug,
  MessageSquare, FileText, Eye, EyeOff, CheckCircle2, PauseCircle,
  Boxes, Layers,
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
import { sentenceFor } from '../api';
import { LIMIT_WORDS, REQUIRES_ANY_LABELS, isStandalone, kindOf, appKey } from '../screens/Plans';
import { APP_ROWS } from '../apps';
import { appIcon, toneClasses } from '../rj-ui/AppFeatureList';

interface LimitEntry { kind: 'boolean' | 'gauge' | 'counter' | string; limit: number | 'unlimited'; period?: string }
interface Price { type: string; currency: string; interval: string; amount_minor: number }
interface Plan {
  id: string; name: string; active: boolean; listed: boolean;
  prices: Price[]; limits: Record<string, LimitEntry>; trial_days: number;
}

// The icon for a NON-APP limit (a seat, a branch, the message meter) — the small remainder that
// has no row in `apps.ts` to read from. A `feature.*` key is never listed here on purpose: its
// icon comes from `APP_ROWS` below, the same single source every other screen already reads, so
// an app never wears a different icon on this screen than on Plans.tsx/Locked.tsx.
const LIMIT_ICON: Record<string, typeof Users> = {
  'staff.seats': Users,
  branches: GitBranch,
  'feature.api': Plug,
  'messages.monthly': MessageSquare,
  'templates.custom': FileText,
  'plan.standalone': Boxes,
};

// technical key -> Arabic label (from `Plans.tsx`'s own `LIMIT_WORDS`) + icon. A key with no
// sentence there falls back to `REQUIRES_ANY_LABELS` (for `plan.requires_any` itself, which
// `Plans.tsx` deliberately never prints as a line) and finally to the raw key — never hidden,
// never breaking the screen, but the raw-key fallback should now be dead code in practice.
function limitLabel(key: string): string {
  return LIMIT_WORDS[key]?.label ?? REQUIRES_ANY_LABELS[key] ?? key;
}
function limitIcon(key: string): typeof Users {
  // A `feature.*` key IS an app, and `apps.ts` already names its icon — reading it here instead
  // of a second hardcoded map is the whole point of this screen's redesign (see the header note).
  const row = APP_ROWS.find((a) => a.key === key);
  if (row) return appIcon(row.icon) as typeof Users;
  return LIMIT_ICON[key] ?? Boxes;
}

// "month" (a calendar month, regardless of billing interval — templates.custom's own reset clock)
// and "billing_period" (once per subscription cycle, whatever its interval is — messages.monthly's
// own) are the two real values billing-service returns; anything else still renders, verbatim,
// rather than being swallowed.
const PERIOD_LABEL: Record<string, string> = { month: 'شهرياً', billing_period: 'كل دورة فوترة' };

// NEVER EDITABLE, ANYWHERE THIS FORM RENDERS A LIMIT — `messages.monthly` is not a sold ceiling,
// it is billing's own protection meter (deploy/seed/plans.json's own header: "measured, never
// sold... it catches our own runaway loop before the owner's bill does"), and its value is always
// the WORD "unlimited", never a number the base plan actually enforces. The generic editor below
// treated every counter/gauge key alike — a number field plus an "unlimited" checkbox — which let
// this ONE key be typed into as a real number with no code anywhere refusing it. Two real risks,
// traced end to end: reminders' own send path (services/reminders/app/core/quota.py::consume)
// never refuses a send for this key regardless of what billing answers, so a typed number would
// not even stop a single message — but billing-service would still start metering against it, and
// plans.json's own `"overage": "allow_and_bill"` on this key means a shop could be charged an
// overage fee for a ceiling that never actually limited anything it paid for. Removed from the
// editable list entirely rather than merely defaulted — a control that exists "but nobody presses
// it" is one press away from both of those, and Meta's own real ceiling (250/2,000 customers a
// day) is the only number that should ever gate a send; see reminders/core/ceiling.py, which reads
// it live and is untouched by this.
const NEVER_EDITABLE = new Set(['messages.monthly']);

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
    return <EmptyState title="لا تطبيقات مضبوطة بعد" />;
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
  // A SEPARATE ARM/CONFIRM FROM `armActive` — `active` (can anybody subscribe at all) and
  // `listed` (does the store show it) are two different questions with two different answers on
  // the SAME plan on purpose (an unlisted-but-active plan is a negotiated one nobody browses to;
  // a listed-but-inactive one is "قريباً" — visible, not yet buyable). Conflating them into one
  // button was the actual bug a full pipeline audit found: the only toggle this card ever had
  // sent `{ active: !plan.active }` and never touched `listed` at all, so there was no real
  // show/hide control despite the server route (`billing.plan_availability`) accepting both.
  const [armListed, setArmListed] = useState(false);
  const [editing, setEditing] = useState(false);
  const price = plan.prices[0];
  const limitEntries = Object.entries(plan.limits);
  const booleans = limitEntries.filter(([, e]) => e.kind === 'boolean');
  const counted = limitEntries.filter(([, e]) => e.kind !== 'boolean');
  const kind = kindOf(plan as never);
  const standalone = isStandalone(plan as never);
  // THE CARD'S OWN FACE — a capacity row (مقاعد إضافية/فرع إضافي) is not "an app" the same way
  // التقييم is, and a standalone app (بوت خدمة العملاء الذكي) is sold on its own, unlike every
  // other app which needs الأساس underneath it. Both facts are read straight off the plan's own
  // limits (`kindOf`/`isStandalone`, `Plans.tsx`'s own logic, imported rather than re-derived),
  // never off its name — and both get their own icon/tone rather than sharing the generic Package
  // every card used to wear regardless of what it actually sold.
  // THE SAME AppRow apps.ts's OWN icon/tone — a capacity row (no app of its own) still gets
  // `Boxes`, but a real app (base included) reads its icon/colour from the one registry every
  // other screen already reads, instead of the plain grey `Package` this card used to fall back
  // to for anything it could not otherwise name.
  const matchedApp = kind === 'capacity' ? undefined
    : kind === 'base' ? APP_ROWS.find((a) => a.id === 'base')
    : APP_ROWS.find((a) => a.key === appKey(plan as never));
  const CardIcon = kind === 'capacity' ? Boxes : matchedApp ? appIcon(matchedApp.icon) : Package;

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

  async function toggleListed() {
    if (!availabilityAction) return;
    setBusy(true);
    try {
      await req(availabilityAction.path.replace('{plan_id}', encodeURIComponent(plan.id)),
                'POST', { listed: !plan.listed }, session.access_token);
      onReload();
    } finally {
      setBusy(false);
      setArmListed(false);
    }
  }

  return (
    <section className={[
      'flex flex-col gap-4 rounded-card border p-5 shadow-sm transition-opacity',
      // A TINTED PANEL WHEN STOPPED, NOT JUST DIMMED — `opacity-70` alone made a stopped app look
      // like a loading card, not a deliberately-off one. `Wallet.tsx`/`KpiCard.tsx`'s own
      // "colour the whole shape, not just a chip" rule, applied here: a neutral, muted panel for
      // "stopped", the ordinary surface for "running".
      plan.active
        ? 'border-border-subtle bg-surface-1'
        : 'border-border-subtle bg-surface-2/60 opacity-90',
    ].join(' ')}>
      <div className="flex items-start justify-between gap-3">
        <span className={[
          'inline-flex w-fit rounded-lg p-2',
          plan.active ? toneClasses(matchedApp?.tone ?? 'accent') : 'bg-surface-2 text-text-secondary',
        ].join(' ')}>
          <CardIcon size={20} />
        </span>
        <div className="flex flex-col items-end gap-1">
          <Badge tone={plan.active ? 'success' : 'neutral'}>
            {plan.active ? <CheckCircle2 size={12} /> : <PauseCircle size={12} />}
            {plan.active ? 'نشطة' : 'متوقفة'}
          </Badge>
          {!plan.listed ? (
            <Badge tone="warning"><EyeOff size={12} /> مخفية عن القائمة</Badge>
          ) : null}
          {kind === 'capacity' ? (
            <Badge tone="info">إضافة سعة</Badge>
          ) : standalone ? (
            <Badge tone="accent"><Boxes size={12} /> تُشترى وحدها</Badge>
          ) : null}
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
            const Icon = limitIcon(key);
            const on = Boolean(entry.limit);
            return (
              <div key={key} className={`flex items-center gap-2 text-sm ${on ? 'text-text-primary' : 'text-text-muted'}`}>
                {on ? <Check size={15} className="shrink-0 text-success" /> : <X size={15} className="shrink-0 text-text-muted" />}
                <Icon size={14} className="shrink-0" />
                <span>{limitLabel(key)}</span>
              </div>
            );
          })}
        </div>
      ) : null}

      {counted.length > 0 ? (
        <ul className="flex flex-col gap-1.5 border-t border-border-subtle pt-3 text-sm">
          {counted.map(([key, entry]) => {
            const Icon = limitIcon(key);
            return (
              <li key={key} className="flex items-center justify-between gap-2">
                <span className="flex items-center gap-2 text-text-secondary">
                  <Icon size={14} className="shrink-0" />
                  {limitLabel(key)}
                </span>
                <span className="font-medium tabular-nums">{amountLine(entry)}</span>
              </li>
            );
          })}
        </ul>
      ) : null}

      {/* mt-auto PINS THIS ROW TO THE CARD'S BOTTOM EDGE. A grid row's cards already stretch to
          the same height (CSS Grid's own default), but each card's own content was top-aligned —
          so a short card (few limits) put its buttons right under its price, while its neighbour
          with more limits pushed its buttons much lower, and the row read as inconsistent even
          though every card was the same height. Reported live from a screenshot. */}
      <div className="mt-auto flex gap-2">
        {updateAction ? (
          <Button type="button" size="sm" variant="outline"
                  className="flex flex-1 items-center justify-center gap-2"
                  onClick={() => setEditing(true)}>
            <Pencil size={14} /> تعديل
          </Button>
        ) : null}
        {availabilityAction ? (
          // DANGER WHEN THIS PRESS WOULD STOP NEW SUBSCRIPTIONS, A CALM TONE WHEN IT WOULD RESUME
          // THEM — read straight off `plan.active`, the same fact the confirm dialog below already
          // states in words. The owner's own complaint, verbatim: this button and «تعديل» used to
          // be the identical flat grey, so a press that quietly turns off sales read as harmless as
          // a press that opens an edit form.
          <Button type="button" size="sm" disabled={busy}
                  variant={plan.active ? 'danger' : undefined}
                  className={plan.active
                    ? 'flex flex-1 items-center justify-center gap-2'
                    : 'flex flex-1 items-center justify-center gap-2 bg-success-soft text-success-on-soft hover:opacity-90'}
                  onClick={() => setArmActive(true)}>
            <Power size={14} /> {plan.active ? 'إيقاف' : 'تفعيل'}
          </Button>
        ) : null}
        {availabilityAction ? (
          // ITS OWN, DISTINCT, LESS ALARMING TONE — show/hide only changes what the STORE lists;
          // existing subscribers are never touched (see the ConfirmDialog body below, and the
          // entitlement-resolver trace in the comment further down). A warning-soft tint says
          // "worth a second look" without borrowing إيقاف's red, which means "this costs someone
          // something" — hiding a plan costs nobody anything already bought.
          <Button type="button" size="sm" disabled={busy}
                  className="flex flex-1 items-center justify-center gap-2 bg-warning-soft text-warning-on-soft hover:opacity-90"
                  onClick={() => setArmListed(true)}>
            {plan.listed ? <EyeOff size={14} /> : <Eye size={14} />} {plan.listed ? 'إخفاء' : 'إظهار'}
          </Button>
        ) : null}
      </div>

      <ConfirmDialog open={armActive} onClose={() => setArmActive(false)} onConfirm={toggleActive}
                    busy={busy} danger={plan.active}
                    title={plan.active ? `إيقاف "${plan.name}"؟` : `تفعيل "${plan.name}"؟`}
                    body={plan.active
                      ? 'لا أحد جديد يقدر يشترك فيها — المشتركون الحاليون ما يتأثرون.'
                      : 'تصير متاحة للاشتراك من جديد.'} />

      {/* SAME "existing subscribers never move" GUARANTEE AS `active` ABOVE — confirmed by tracing
          the real entitlement check (billing-service's entitlement_resolver.resolve()) all the
          way through: it reads only actual subscription rows, never `plan.listed`. Hiding a plan
          from the store cannot touch anyone already on it. */}
      <ConfirmDialog open={armListed} onClose={() => setArmListed(false)} onConfirm={toggleListed}
                    busy={busy} danger={plan.listed}
                    title={plan.listed ? `إخفاء "${plan.name}" عن المتجر؟` : `إظهار "${plan.name}" في المتجر؟`}
                    body={plan.listed
                      ? 'يختفي من متجر التطبيقات لمن لم يشترك بعد — المشتركون الحاليون ما يتأثرون، وتقدر تُظهرها من جديد وقت ما تبي.'
                      : 'يصير مرئياً في متجر التطبيقات ويقدر أي محل يشتريه.'} />

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
 *  scope here, same as create_plan; this edits what an app already has, thoroughly, not what it
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
      setError(sentenceFor(err, 'تعذّر حفظ التطبيق.'));
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
            {/* رسائل واتساب — NOT A ROW HERE AT ALL, on purpose. See NEVER_EDITABLE's own note:
                there is nothing to toggle or type, so a fixed sentence replaces the control
                rather than a disabled one sitting where an editable field used to be. */}
            {limits['messages.monthly'] ? (
              <div className="flex items-center justify-between gap-3">
                <span className="flex items-center gap-2 text-sm text-text-secondary">
                  <MessageSquare size={14} className="shrink-0" /> رسائل واتساب
                </span>
                {/* THE REAL STORED VALUE, NOT AN ASSUMPTION — this key is meant to always read
                    "unlimited" (see NEVER_EDITABLE's own note), but a fixed sentence that claimed
                    so regardless of what billing actually holds would hide the one case worth
                    surfacing: a row that somehow already carries a real number. */}
                <span className="text-xs text-text-muted">
                  {limits['messages.monthly'].limit === 'unlimited'
                    ? 'غير محدودة دائماً — واتساب تتحكم بالسقف الفعلي'
                    : `${amountLine(limits['messages.monthly'])} — يجب أن تكون غير محدودة، راجع الإعداد`}
                </span>
              </div>
            ) : null}
            {Object.entries(limits).filter(([key]) => !NEVER_EDITABLE.has(key)).map(([key, entry]) => (
              <div key={key} className="flex items-center justify-between gap-3">
                <span className="text-sm">{limitLabel(key)}</span>
                {entry.kind === 'boolean' ? (
                  <Toggle checked={Boolean(entry.limit)}
                         onChange={(v) => setLimitValue(key, { limit: v ? 1 : 0 })}
                         ariaLabel={limitLabel(key)} />
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
