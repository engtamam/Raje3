/**
 * The real billing types and pure logic every screen shares — extracted from the old شاشة
 * الاشتراك screen (`screens/Plans.tsx`, deleted 2026-09-16 once its last real consumer,
 * «حسابي»'s own billing tab, was replaced by `BillingStatusPane.tsx` and every app-purchase
 * surface had already moved to the launcher, [[task-app-store-redesign-7-phases]]). This file is
 * NOT a screen — no JSX component here renders a page. It is the one place `Plan`/`Subscription`
 * mean the same thing to `admin/PlanCards.tsx`, `subscribeFlow.ts`, the launcher's
 * `useAppBilling.ts`/`AppLauncher.tsx`, and `screens/Locked.tsx`, so none of them can drift into
 * re-deriving what a plan's own `limits` mean.
 *
 * `CapacityAddonCard` IS THE ONE EXCEPTION — a real component, because the seat/branch stepper
 * itself is still exactly the UI the launcher's own capacity shelf reuses (`AppLauncher.tsx`'s
 * `CapacityTile`); it never had a second, "new" version to replace it with, so it stays real code
 * living beside the types it reads instead of being invented twice.
 */
import { Minus, Plus } from 'lucide-react';
import { Card } from './rj-ui/Card';
import { Button } from './rj-ui/Button';
import { isDenied, isReady, type Loading } from './loading';
import { APP_ROWS, type Owned } from './apps';
import { riyals } from './money';
import { useOperatorI18n, tf, translate } from './operator-i18n';
import './billing-shared-i18n';

type Translator = (key: string) => string;

interface Price {
  type?: string; currency?: string; interval?: string; amount_minor?: number; includes_tax?: boolean;
  /** billing-service v0.19.24 — present ONLY on a plan that opted into the percent-of-price AI-
   *  credit allowance (today, only بوت خدمة العملاء الذكي). Halalas, same unit as `amount_minor`,
   *  computed live off the CURRENT operator-set percent — never stored, never a value this screen
   *  could go stale on. Absent means "this plan carries no such allowance", never zero. */
  included_credit_minor?: number;
}
/** `limit` is a NUMBER OR THE WORD `unlimited` — billing's own sentinel, which its merge treats as
 *  beating every arithmetic. We used to seed -1 for the same idea; billing read that as a plain
 *  number and SUMMED it, so a base-shaped row plus a capacity pack came out at 9 seats instead of
 *  no limit, and two base-shaped rows summed to -2 messages — which refuses every send. */
interface Limit { kind?: string; limit?: number | string; period?: string; overage?: string }
export interface Plan {
  id: string;
  name: string;
  active?: boolean;
  listed?: boolean;
  prices?: Price[];
  limits?: Record<string, Limit>;
  /** Non-zero means this plan is entered free, no charge at signup at all — the same field
   *  `subscription.checkout_link` (services/operations) reads server-side to decide whether a
   *  plan even needs a pay-link. Read here for the identical reason: a trial/free plan goes
   *  through the plain `subscription.activate` call, never a pay-link it does not need. */
  trial_days?: number;
}
/** Free forever, or a trial that owes nothing today — the one shape `subscription.activate` still
 *  handles directly, no pay-link needed at all (billing-service creates it straight away). Mirrors
 *  `may_subscribe`'s own `paid` computation (services/operations/app/core/subscribe.py) so every
 *  caller here — `subscribeFlow.ts`'s single locked-card buy, `useAppBilling.ts`'s launcher tile
 *  and cart — takes the exact same branch the server will. */
export function needsNoPayment(plan: Plan): boolean {
  const priceMinor = plan.prices?.[0]?.amount_minor ?? 0;
  return priceMinor === 0 || (plan.trial_days ?? 0) > 0;
}

export interface Subscription {
  id: string; plan_id?: string; plan_name?: string; status?: string;
  /** How many units of a CAPACITY row this one subscription holds — Odoo-style per-seat licensing,
   *  not one row per unit. Defaults to 1 server-side; absent entirely on rows minted before this
   *  existed, so `?? 1` at every read site, never a bare `sub.quantity`. */
  quantity?: number;
  /** Seconds on the wire — the model's own real field name is `current_period_end`. */
  current_period_end?: number;
  /** True once he has asked to leave — the subscription still serves him until the date above,
   *  and nothing charges again after it. */
  cancel_at_period_end?: boolean;
  /** A SCHEDULED DOWNGRADE (v0.16.33) - set the moment billing.change_plan schedules
   *  one, cleared the moment run_cycle adopts it at renewal or billing.cancel_scheduled_change
   *  undoes it. Empty string, never absent, when nothing is scheduled - the server's own
   *  sentinel, not ours. */
  pending_plan_id?: string;
}

/**
 * One sentence per limit key, and an app says only what we can say plainly.
 *
 * `gauge` counts things that exist at once (seats, branches); `counter` counts events inside a
 * period; `boolean` is a capability that is on or off. The renderer below reads `kind` rather than
 * guessing from the key, so a new gauge needs a sentence here and nothing else.
 */
export const LIMIT_KEYS: Record<string, { label: string; unit?: string }> = {
  'staff.seats': { label: 'plans.limit.staffSeats.label', unit: 'plans.limit.staffSeats.unit' },
  branches: { label: 'plans.limit.branches.label', unit: 'plans.limit.branches.unit' },
  'messages.monthly': { label: 'plans.limit.messagesMonthly.label', unit: 'plans.limit.messagesMonthly.unit' },
  'templates.custom': { label: 'plans.limit.templatesCustom.label', unit: 'plans.limit.templatesCustom.unit' },
  'feature.loyalty': { label: 'plans.limit.loyalty.label' },
  'feature.campaigns': { label: 'plans.limit.campaigns.label' },
  'feature.insights.engine': { label: 'plans.limit.insightsEngine.label' },
  'feature.api': { label: 'plans.limit.api.label' },
  'feature.bookings': { label: 'plans.limit.bookings.label' },
  'feature.rating': { label: 'plans.limit.rating.label' },
  'feature.whatsapp': { label: 'plans.limit.whatsapp.label' },
  'feature.partner_loyalty': { label: 'plans.limit.coupons.label' },
  'feature.mobile_requests': { label: 'plans.limit.mobileRequests.label' },
  'feature.mutual_benefit': { label: 'plans.limit.mutualBenefit.label' },
  'feature.mobile_ai_assistant': { label: 'plans.limit.mobileAiAssistant.label' },
  'feature.coworking': { label: 'plans.limit.coworking.label' },
  // Phase 0 only (services/referrals) — no screen calls this yet; `listed: false` on its plan
  // row keeps the card itself from ever reaching a real customer (see deploy/seed/plans.json).
  'feature.referrals': { label: 'plans.limit.referrals.label' },
  // Backend-only pass, no console/mobile screen yet -- `listed: false` on its plan row, same
  // posture as `feature.whatsapp_delivery_orders` above.
  'feature.customer_service': { label: 'plans.limit.customerService.label' },
  // Phase 0 only, same posture as `feature.referrals` above -- `listed: false` on its plan row
  // (deploy/seed/plans.json) keeps the card from ever reaching a real customer.
  'feature.whatsapp_delivery_orders': { label: 'plans.limit.whatsappDeliveryOrders.label' },
  'plan.standalone': { label: 'plans.limit.standalone.label' },
  // `plan.requires_any` NEVER ACTUALLY PRINTS via `planLines` (its value is a list, never a
  // positive `limit`) — the entry exists only so `ci/check_entitlements.py` finds the wording it
  // demands for every sold limit.
  'plan.requires_any': { label: 'plans.limit.requiresAny.label' },
  'feature.contacts': { label: 'plans.limit.contacts.label' },
  'feature.visit': { label: 'plans.limit.visit.label' },
};

function monthly(p: Plan): Price | undefined {
  return p.prices?.find((x) => x.interval === 'month') ?? p.prices?.[0];
}

/**
 * The readable lines for one app — kept for `admin/DiscountRuleCards.tsx`-style callers and its
 * own test (`billing_shared_rating_wording.test.ts`); no live screen renders it directly any more
 * since `AppCard`'s own JSX (the old شاشة الاشتراك) was retired with that screen.
 */
export function planLines(p: Plan, t: Translator = (k) => translate('ar', k)): string[] {
  const out: string[] = [];
  for (const [key, lim] of Object.entries(p.limits ?? {})) {
    const words = LIMIT_KEYS[key];
    if (!words) continue;
    const label = t(words.label);
    const raw = lim.limit ?? 0;
    const unlimited = raw === 'unlimited' || (typeof raw === 'number' && raw < 0);
    const n = typeof raw === 'number' ? raw : 0;
    if (lim.kind === 'boolean') {
      if (unlimited || n > 0) out.push(label);
      continue;
    }
    if (unlimited) out.push(tf(t, 'plans.limit.unlimited', { label }));
    else if (n > 0) out.push(tf(t, 'plans.limit.withCount', { label, n }));
  }
  return out;
}

export type Kind = 'app' | 'capacity';

/** Read straight off the SAME field operations' own `may_add`/`is_standalone` reads
 * (deploy/seed/plans.json's `plan.standalone`) — never a name or an id. THE ONE APP SOLD WITHOUT
 * الأساس UNDERNEATH IT: a plan carrying this may be bought even when a base concept existed. */
export function isStandalone(plan: Plan): boolean {
  const raw = plan.limits?.['plan.standalone']?.limit;
  return typeof raw === 'string' ? raw.toLowerCase() === 'unlimited' : Number(raw ?? 0) !== 0;
}

/** Short, readable names for the small set of keys `requiresAny` is likely to name — same list,
 * same wording spirit, as `_REQUIRES_ANY_LABELS` in services/operations/app/core/subscribe.py. */
export const REQUIRES_ANY_KEYS: Record<string, string> = {
  'feature.visit': 'plans.requiresAny.visit',
  'feature.bookings': 'plans.requiresAny.bookings',
  'feature.contacts': 'plans.requiresAny.contacts',
  'feature.mobile_requests': 'plans.requiresAny.mobileRequests',
  'feature.whatsapp_delivery_orders': 'plans.requiresAny.whatsappDeliveryOrders',
};

/** The OTHER feature keys this plan's own row says at least one of must already be held —
 * `services/operations/app/core/subscribe.py::requires_any` reads the SAME field, off the same
 * shape, purchase-time. */
export function requiresAny(plan: Plan): string[] {
  const raw = (plan.limits?.['plan.requires_any'] as unknown as { list?: unknown })?.list;
  return Array.isArray(raw) ? raw.filter((k): k is string => typeof k === 'string' && Boolean(k)) : [];
}

/** The sentence for a locked/disabled buy state when this shop holds none of `requiresAny`'s
 * keys yet — empty when the plan declares no dependency, when the read has not settled or could
 * not be asked, or when he is DENIED the read entirely, so the card never flashes a lock it
 * cannot yet justify. */
export function missingRequirement(
  plan: Plan, owned: Loading<Owned>, t: Translator = (k) => translate('ar', k),
): string {
  const need = requiresAny(plan);
  if (!need.length) return '';
  if (isDenied(owned) || !isReady(owned) || !owned.checked) return '';
  if (need.some((k) => owned.keys.includes(k))) return '';
  const names = need.map((k) => (REQUIRES_ANY_KEYS[k] ? t(REQUIRES_ANY_KEYS[k]) : k)).join(` ${t('plans.or')} `);
  return tf(t, 'plans.missingRequirement', { names });
}

/** WHAT KIND OF THING IS THIS ROW — read off its limits, never off its name. An app turns a
 *  feature on; capacity carries only seats/branches. */
export function kindOf(plan: Plan): Kind {
  const limits = plan.limits ?? {};
  const on = Object.keys(limits)
    .filter((k) => k.startsWith('feature.') && (limits[k]?.limit ?? 0) !== 0);
  return on.length ? 'app' : 'capacity';
}

/** The one feature an app row turns on, for asking `owned` about it. */
export function appKey(plan: Plan): string {
  const limits = plan.limits ?? {};
  const on = Object.keys(limits).filter(
    (k) => k.startsWith('feature.') && (limits[k]?.limit ?? 0) !== 0);
  return on[0] ?? '';
}

/** THE REAL APP NAME — never the billing plan's own `name`. A plan row's `name` is stored data
 *  (billing-service, keyed by its original slug — «كوبونات» for «تحالف استراتيجي», by deliberate
 *  choice: renaming the STORED row is a data migration, not a copy edit — see apps.ts's own
 *  `AppRow` entry for «coupons»). Every surface a shop actually reads (the launcher tile, the
 *  discount chip, the cart, an auto-added-dependency notice) must show the SAME name, so this is
 *  the one lookup all of them share — found live as a real bug: the cart showed «كوبونات» beside
 *  a tile reading «تحالف استراتيجي» for the identical app. */
export function appDisplayName(plan: Plan): string {
  const key = appKey(plan);
  return APP_ROWS.find((a) => a.key === key)?.name ?? plan.name;
}

/**
 * MAY THIS PRESS BUY ANYTHING? (د-15)
 *
 * Three separate facts. `gatewayEnabled` answers «is there a gateway key on the server»;
 * `canMint` answers «can this browser hand back a card token». Merging them into one condition is
 * how a paid row got drawn live with no way to ever actually charge it.
 */
export function canBuy(
  { hasAction, gatewayEnabled, canMint }:
  { hasAction: boolean; gatewayEnabled: boolean; canMint: boolean },
): boolean {
  return hasAction && gatewayEnabled && canMint;
}

/** The server's own sentence when billing was ASKED and could not answer — empty otherwise. */
export function unreadSentence(answer: Owned | null | undefined): string {
  return answer && !answer.checked ? answer.message : '';
}

/** A day an owner can plan around: western digits and a Gregorian month, like every other date
 *  in this product. Seconds on the wire — the subscription's `current_period_end`. */
function renewalDay(epoch: number | null | undefined): string {
  return epoch
    ? new Date(epoch * 1000).toLocaleDateString('ar-SA-u-nu-latn-ca-gregory',
                                                { day: 'numeric', month: 'long' })
    : '';
}

/** How many DIFFERENT days this shop is charged on — each owned app's. Counted off days rather
 *  than timestamps: two subscriptions bought hours apart on the same date are one billing day to
 *  the person paying. An unread billing (`checked` false) counts nothing — it has no dates. */
export function distinctRenewalDays(answer: Owned | null | undefined): Set<string> {
  if (!answer?.checked) return new Set();
  const days = new Set<string>();
  for (const a of answer.apps) if (a.owned && a.renews_at) days.add(renewalDay(a.renews_at));
  const base = renewalDay(answer.base?.renews_at);
  if (base) days.add(base);
  return days;
}

/** The word for ONE of whatever this capacity row grants («مقعد»/«فرع») — read off its own
 *  gauge limit key, never guessed from its name. */
function capacityUnitWord(plan: Plan, t: Translator): string {
  for (const [key, lim] of Object.entries(plan.limits ?? {})) {
    if (lim.kind === 'boolean') continue;
    if ((typeof lim.limit === 'number' && lim.limit > 0) || lim.limit === 'unlimited') {
      const unitKey = LIMIT_KEYS[key]?.unit;
      if (unitKey) return t(unitKey);
    }
  }
  return t('plans.genericUnit');
}

/**
 * ONE CARD PER CAPACITY KIND (موظفين، فروع)، WITH A +/- INSTEAD OF A REPEATED «أضِف».
 *
 * A CAPACITY PLAN IS PRICED PER UNIT — this card is the one place that price is multiplied by how
 * many he wants, live, before he ever presses anything that charges him. THE FIRST UNIT GOES
 * THROUGH THE ORDINARY CARD-FORM PURCHASE (a real subscription needs a payment token the first
 * time); every unit after that is the SAME subscription's own `quantity` moved up or down.
 *
 * ZERO IS NOT A QUANTITY THIS CARD EVER SENDS — deciding what "remove the last one" means is not
 * this stepper's job; that is the caller's own confirm-then-cancel, reached through `onRemoveLast`.
 */
export function CapacityAddonCard({
  plan, sub, busy, sellable, unreadNote, onBuyFirst, onChangeQuantity, onRemoveLast,
}: {
  plan: Plan;
  /** `undefined` — nothing bought yet, the stepper reads as zero. */
  sub: Subscription | undefined;
  busy: boolean;
  sellable: boolean;
  unreadNote?: string;
  onBuyFirst: () => void;
  onChangeQuantity: (quantity: number) => void;
  onRemoveLast: () => void;
}) {
  const { t } = useOperatorI18n();
  const price = monthly(plan);
  const unit = capacityUnitWord(plan, t);
  const qty = sub?.quantity ?? 0;
  const unitMinor = price?.amount_minor ?? 0;
  return (
    <Card className="flex h-full flex-col gap-2 p-3">
      <h3 className="text-sm font-medium leading-tight">{plan.name}</h3>
      {unitMinor ? (
        <p className="text-xs text-text-secondary">
          {tf(t, 'plans.capacity.pricePerUnit', { price: riyals(unitMinor), unit })}
        </p>
      ) : null}
      <div className="mt-auto flex items-center justify-between gap-2 border-t border-border-subtle pt-2">
        <div className="flex items-center gap-2" role="group" aria-label={tf(t, 'plans.capacity.countAriaLabel', { name: plan.name })}>
          <Button type="button" variant="outline" size="sm" aria-label={tf(t, 'plans.capacity.decreaseAriaLabel', { unit })}
                  disabled={busy || !sellable || qty === 0}
                  onClick={() => (qty > 1 ? onChangeQuantity(qty - 1) : onRemoveLast())}>
            <Minus size={14} />
          </Button>
          <span className="min-w-[1.5rem] text-center text-sm font-medium tabular-nums">{qty}</span>
          <Button type="button" variant="outline" size="sm" aria-label={tf(t, 'plans.capacity.increaseAriaLabel', { unit })}
                  disabled={busy || !sellable}
                  onClick={() => (qty === 0 ? onBuyFirst() : onChangeQuantity(qty + 1))}>
            <Plus size={14} />
          </Button>
        </div>
        {qty > 0 && unitMinor ? (
          <span className="text-sm font-semibold tabular-nums">{tf(t, 'plans.capacity.totalRiyals', { amount: riyals(unitMinor * qty) })}</span>
        ) : null}
      </div>
      {unreadNote ? <p className="text-xs text-text-secondary">{unreadNote}</p> : null}
    </Card>
  );
}
