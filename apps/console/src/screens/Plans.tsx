/**
 * «الاشتراك» — the apps, what each one actually buys, and the one door that must open first.
 *
 * THE PLANS ARE ROWS IN billing, NEVER A LIST IN THIS FILE. Their names, their prices and their
 * limits all arrive from `billing.plans`; a price written here would be a second price, and the
 * two would disagree the first time one of them changed. Even the ORDER is derived — cheapest
 * first, from the amount the server sent.
 *
 * WHAT A PLAN MEANS IS ITS LIMITS, AND THEY ARRIVE AS MACHINE KEYS. `staff.seats`, `branches`,
 * `feature.campaigns` — an owner cannot read those, and printing them raw would be a table of
 * jargon dressed as a comparison. So each key has one Arabic sentence here and ONLY here: the
 * numbers stay the server's, the wording is ours, and a key we have no sentence for is left out
 * rather than printed as itself. That is deliberate — an app that lists a line nobody understands
 * is worse at selling than an app that lists one line fewer.
 *
 * AND PRESSING A PLAN BEFORE WHATSAPP IS CONNECTED SUBSCRIBES HIM.
 *
 * THE ORDER WAS THE OTHER WAY ROUND: connect, then pay. The reasoning was sound — a subscription
 * with no connected number bills against a channel that cannot carry a reminder — and it was still
 * wrong, because of WHERE it put the errand. It asked a man who had just decided to buy to go and
 * spend ten minutes with Meta first, at the moment his intent was highest and most perishable. The
 * ones who did not come back were not lost to the product.
 *
 * PAYING IS THE STRONGEST REASON TO FINISH CONNECTING. A shop that has paid completes what it
 * started; a shop that has not is still deciding. So the subscription goes through, and the
 * connection becomes the next step rather than the toll.
 *
 * AND HE IS TOLD, IN THE SAME BREATH AS THE RECEIPT. The server returns a `notice` naming the one
 * thing left and what already works without it. A silent success here would be the real sale of
 * something undeliverable: he would learn it a week later from messages that never went.
 */
import { canMintToken, confirmToken, NO_CARD_FORM } from '../payment';
import { takePending, type PendingPayment } from '../pendingPayment';
import { CardForm } from './CardForm';
import { useEffect, useState } from 'react';
import { Badge } from '../rj-ui/Badge';
import { Button } from '../rj-ui/Button';
import { Modal } from '../rj-ui/Modal';
import { Skeleton } from '../rj-ui/Skeleton';
import {
  CalendarClock, Check, Gift, Layers, Megaphone, Minus, Plus, Sparkles, type LucideIcon,
} from 'lucide-react';
import { action, call, type Catalog } from '../catalog';
import { isDenied, isReady, type Loading } from '../loading';
import { APP_ROWS, owns, type Owned } from '../apps';
import type { Session } from '../session';
import { riyals } from '../money';
import { AssistantHint } from '../AssistantHint';

/** The anchor for one status badge's plain-language explanation, or none for the states that
 *  already say what happens next right on the card (cancelling, active, stopped). */
function statusAnchor(label?: string): string | undefined {
  if (label === 'تجريبي') return 'store.trialStatus';
  if (label === 'متأخر الدفع') return 'store.pastDueStatus';
  if (label === 'موقوف مؤقتاً') return 'store.pausedStatus';
  return undefined;
}

/**
 * Where each app's surface lives, in the words on the rail.
 *
 * FROM nav.ts's IDS, WORDED HERE. «اشتريته وين ألقاه؟» is the first support question after every
 * purchase, and the registry already knows the answer as a section id — this is the one place that
 * turns that id into the label he actually reads on the left of his screen.
 */
const SECTION_LABEL: Record<string, string> = {
  messages: 'رسائلي',
  points: 'نقاطي',
  bookings: 'الحجوزات',
  team: 'فريقي',
  account: 'حسابي',
  shop: 'محلّي',
};

/** One face per app, by its `apps.ts` id — the same registry the card's copy already reads, so a
 *  new app gets a sentence AND an icon from one place rather than two. `base` gets no card of its
 *  own icon treatment; every card falls back to `Layers` if its id is not listed here yet. */
const APP_ICON: Record<string, LucideIcon> = {
  base: Layers,
  campaigns: Megaphone,
  loyalty: Gift,
  bookings: CalendarClock,
  insights: Sparkles,
};

interface Price { type?: string; currency?: string; interval?: string; amount_minor?: number; includes_tax?: boolean }
/** `limit` is a NUMBER OR THE WORD `unlimited` — billing's own sentinel, which its merge treats as
 *  beating every arithmetic. We used to seed -1 for the same idea; billing read that as a plain
 *  number and SUMMED it, so «المؤسسات» plus a capacity pack came out at 9 seats instead of no
 *  limit, and two bases summed to -2 messages — which refuses every send. */
interface Limit { kind?: string; limit?: number | string; period?: string; overage?: string }
export interface Plan {
  id: string;
  name: string;
  active?: boolean;
  listed?: boolean;
  prices?: Price[];
  limits?: Record<string, Limit>;
}
export interface Subscription {
  id: string; plan_id?: string; plan_name?: string; status?: string;
  /** How many units of a CAPACITY row this one subscription holds — Odoo-style per-seat licensing,
   *  not one row per unit. Defaults to 1 server-side; absent entirely on rows minted before this
   *  existed, so `?? 1` at every read site, never a bare `sub.quantity`. */
  quantity?: number;
  /** Seconds on the wire — the model's real field name is `current_period_end`; `period_end` here
   *  was declared and never actually read by anything in this file. */
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
export const LIMIT_WORDS: Record<string, { label: string; unit?: string }> = {
  'staff.seats': { label: 'مقاعد للموظفين', unit: 'مقعد' },
  branches: { label: 'فروع', unit: 'فرع' },
  'messages.monthly': { label: 'رسائل في الشهر', unit: 'رسالة' },
  'templates.custom': { label: 'قوالب خاصة بك', unit: 'قالب' },
  'feature.loyalty': { label: 'نقاط ومكافآت' },
  'feature.campaigns': { label: 'حملات على شرائح عملائك' },
  'feature.insights.engine': { label: 'فرصي: أين الفرصة في محلّك' },
  'feature.api': { label: 'ربط برمجي مع أنظمتك' },
  // SOLD, NOT BUILT YET (ci/check_entitlements.py's SOLD_UNBUILT). The app itself carries
  // `listed: false`, so this sentence never actually renders a card — it exists so the wording
  // is ready the day the app flips to listed, not written under launch pressure.
  'feature.bookings': { label: 'نظام الحجوزات ومواعيد العملاء' },
  // BUILT (verified 2026-09-08, full pipeline audit — see plans.json's own note on this row) —
  // NOT in ci/check_entitlements.py's SOLD_UNBUILT (that dict is empty). `listed: false` in
  // plans.json is a pure go-live decision now; this sentence is ready and simply never prints
  // until that flips, since `Plans.tsx` never offers an unlisted plan for purchase.
  'feature.rating': { label: 'تقييم العملاء بعد الزيارة' },
  // THE BASE ITSELF, and it has a sentence for the same reason every other key does: it is
  // charged for, so the page where he decides must name it. «سجلّ الزيارات» rather than «الأساس»
  // — the card is already titled الأساس, and repeating the title tells him nothing about what
  // the money buys.
  'feature.base': { label: 'سجلّ الزيارات والتذكيرات' },
  'feature.whatsapp': { label: 'مساعد ذكي يرد على عملائك عبر واتساب' },
  // THE ONE APP SOLD WITHOUT الأساس UNDERNEATH IT (see plans.json's own note on this plan row) —
  // a real, customer-meaningful fact worth a line on the card, not an internal implementation
  // detail: a shop with no other subscription reads this and knows it can buy this one alone.
  'plan.standalone': { label: 'يُشترى وحده، بلا حاجة لاشتراك أساسي' },
  // `plan.requires_any` (services/operations/app/core/subscribe.py) NEVER ACTUALLY PRINTS: its
  // value is `{ kind: 'list', list: [...] }`, never a positive `limit`, so `planLines` below
  // never pushes this label — the entry exists only so `ci/check_entitlements.py` finds the
  // wording it demands for every sold limit. The reader-facing sentence for THIS key lives beside
  // the "needs base first" note ("التطبيقات تُضاف…" above the apps grid), which names the actual
  // missing app(s) — see `missingRequirement` and its render site just below.
  'plan.requires_any': { label: 'يحتاج تطبيقاً آخر مفعّلاً أولاً' },
  // بيانات التواصل — the FREE app (see plans.json's own note on the row). Grants exactly one
  // door: resolving or creating a customer by phone with no visit attached.
  'feature.contacts': { label: 'تسجيل بيانات العملاء وحفظها' },
  // تسجيل زيارة — the visit register itself, sold on its own (see plans.json's own note on the
  // row for why it no longer needs الأساس underneath it).
  'feature.visit': { label: 'تسجيل الزيارات وتأكيدها والتذكير بها' },
};

// Halalas on the wire, riyals on the screen — see money.ts. This rounded to whole riyals, so an
// app priced at 9950 was advertised as «100 ريال»: fifty halalas above what we charge, on the screen
// whose only job is to state the price before he agrees to it.

function monthly(p: Plan): Price | undefined {
  return p.prices?.find((x) => x.interval === 'month') ?? p.prices?.[0];
}

/** Cheapest first — the order is the server's numbers, never a hand-kept list. */
function ordered(plans: Plan[]): Plan[] {
  return [...plans].sort((a, b) => (monthly(a)?.amount_minor ?? 0) - (monthly(b)?.amount_minor ?? 0));
}

/**
 * The readable lines for one app.
 *
 * A `boolean` at 0 is omitted rather than rendered as «لا»: a list of what an app does NOT do,
 * printed under its price, reads as a warning label. The comparison between apps comes from the
 * lines that are present, which is how a person actually reads three cards side by side.
 */
export function planLines(p: Plan): string[] {
  const out: string[] = [];
  for (const [key, lim] of Object.entries(p.limits ?? {})) {
    const words = LIMIT_WORDS[key];
    if (!words) continue;                       // no sentence for it → it is not shown
    const raw = lim.limit ?? 0;
    // THE SENTINEL IS A WORD, AND IT IS CHECKED BEFORE ANYTHING NUMERIC. `-1` is kept as a reading
    // only so a row seeded before the change still renders «بلا حد» rather than nothing at all.
    const unlimited = raw === 'unlimited' || (typeof raw === 'number' && raw < 0);
    const n = typeof raw === 'number' ? raw : 0;
    if (lim.kind === 'boolean') {
      if (unlimited || n > 0) out.push(words.label);
      continue;
    }
    if (unlimited) out.push(`${words.label}: بلا حد`);
    else if (n > 0) out.push(`${words.label}: ${n}`);
  }
  return out;
}

export type Kind = 'base' | 'app' | 'capacity';

/** Read straight off the SAME field operations' own `may_add`/`is_standalone` reads
 * (deploy/seed/plans.json's `plan.standalone`) — never a name or an id, same discipline as
 * `kindOf` just below. THE ONE APP SOLD WITHOUT الأساس UNDERNEATH IT: a plan carrying this may be
 * bought (and its purchase button stays enabled) even when `hasBase === false`. */
export function isStandalone(plan: Plan): boolean {
  const raw = plan.limits?.['plan.standalone']?.limit;
  return typeof raw === 'string' ? raw.toLowerCase() === 'unlimited' : Number(raw ?? 0) !== 0;
}

/**
 * WHAT KIND OF THING IS THIS ROW — read off its limits, never off its name.
 *
 * A NAME WOULD PUT THE PRICE LIST IN TWO PLACES, and the copy in code is the one that goes stale
 * the day marketing renames a row. A row IS a base when it carries the message meter; it is an
 * app when it turns a feature on; it is capacity when all it carries is seats or branches.
 *
 * `limit: 0` IS A DECLARED DENY, not a grant. The base carries every app at 0 so no screen has to
 * tell «not bought» from «never heard of» — read as grants, the base would look like everything.
 */
/** Short, readable names for the small set of keys `requiresAny` is likely to name — same list,
 * same wording spirit, as `_REQUIRES_ANY_LABELS` in services/operations/app/core/subscribe.py.
 * A key missing from this map falls back to its raw name rather than crashing — a future
 * dependency works (both the purchase refusal and this note) the moment its plans.json row
 * carries `requires_any`; adding it here is a readability improvement, not a precondition. */
export const REQUIRES_ANY_LABELS: Record<string, string> = {
  'feature.base': 'الأساس',
  'feature.visit': 'تسجيل زيارة',
  'feature.bookings': 'الحجوزات',
  'feature.contacts': 'بيانات التواصل',
};

/** The OTHER feature keys this plan's own row says at least one of must already be held —
 * `services/operations/app/core/subscribe.py::requires_any` reads the SAME field, off the same
 * shape, purchase-time. Never merged, never a tenant's held entitlements — the candidate plan's
 * own declaration, exactly like `isStandalone` just above. */
export function requiresAny(plan: Plan): string[] {
  const raw = (plan.limits?.['plan.requires_any'] as unknown as { list?: unknown })?.list;
  return Array.isArray(raw) ? raw.filter((k): k is string => typeof k === 'string' && Boolean(k)) : [];
}

/** The sentence for a locked/disabled buy state when this shop holds none of `requiresAny`'s
 * keys yet — empty when the plan declares no dependency, when the read has not settled or could
 * not be asked, or when he is DENIED the read entirely (same "show the surface, not a lock" rule
 * `owns` follows), so the card never flashes a lock it cannot yet justify. */
export function missingRequirement(plan: Plan, owned: Loading<Owned>): string {
  const need = requiresAny(plan);
  if (!need.length) return '';
  if (isDenied(owned) || !isReady(owned) || !owned.checked) return '';
  if (need.some((k) => owned.keys.includes(k))) return '';
  const names = need.map((k) => REQUIRES_ANY_LABELS[k] ?? k).join(' أو ');
  return `يحتاج تفعيل ${names} أولاً.`;
}

export function kindOf(plan: Plan): Kind {
  const limits = plan.limits ?? {};
  // THE METER MAKES IT A BASE — the same fact operations decides from, off the same field. An app
  // may never repeat `messages.monthly` (two of them sum to -2 and «unlimited» stops meaning
  // anything), so carrying it and being a whole subscription are one statement.
  if ('messages.monthly' in limits) return 'base';
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

/**
 * ONE CARD, AND IT ANSWERS EVERY QUESTION AN OWNER ASKS BEFORE HE PAYS.
 *
 * WHAT A CARD MUST SAY, in the order he asks it: what is this · what will it do FOR MY SHOP · how
 * much · what exactly do I get · where does it show up · do I already have it. A card that answers
 * four of the six sends him to WhatsApp to ask us the other two, and that conversation is the
 * conversion he did not make.
 *
 * THE SENTENCE IS ABOUT HIM, NEVER ABOUT OUR PRICE LIST. «نقاطٌ على كل زيارة» is a fact about his
 * shop; «هذه تحتاج تطبيقاً آخر» is a fact about us, and only one of them makes anybody buy. It comes
 * from the app registry — the same file the locks read — so the shop is never told one thing here
 * and another where the lock is drawn.
 *
 * AND THE LIMITS ARE STILL THE SERVER'S. The lines under the price are the app's own `limits`,
 * worded by LIMIT_WORDS and nothing else; a number typed here would be a second price list.
 */
/**
 * MAY THIS PRESS BUY ANYTHING? (د-15)
 *
 * Three separate facts, and the screen used to check two. `gatewayEnabled` answers «is there
 * a gateway key on the server»; `canMint` answers «can this browser hand back a card token».
 * They were read as one fact, so with a key configured every paid row was drawn live, posted
 * `{ plan_id }` with no token, and came back 402 — while the base slipped through only
 * because its trial skips the payment check entirely.
 *
 * A FUNCTION RATHER THAN A CONDITION INSIDE THE HANDLER, so the rule can be stated and broken
 * on purpose — the condition in the press was reachable only by pressing.
 */
export function canBuy(
  { hasAction, gatewayEnabled, canMint }:
  { hasAction: boolean; gatewayEnabled: boolean; canMint: boolean },
): boolean {
  return hasAction && gatewayEnabled && canMint;
}

/** The server's own sentence when billing was ASKED and could not answer — empty otherwise.
 *
 * TWO STATES, NOT ONE. `undefined`/`null` means the read is still in flight or failed in the
 * browser; `checked: false` means operations reached us and said it could not reach billing, and
 * it sends the sentence with it. Merging them prints «جارٍ التحقق…» over an outage, which is a
 * spinner that never ends on the screen where an owner goes to buy.
 *
 * AND THE SENTENCE IS NOT REWRITTEN HERE. Two vocabularies for one failure is how an owner comes
 * to believe there are two problems — the same rule `Locked.tsx` follows.
 */
export function unreadSentence(answer: Owned | null | undefined): string {
  return answer && !answer.checked ? answer.message : '';
}


/** How many DIFFERENT days this shop is charged on — the base's and each owned app's.
 *
 * Counted off days rather than timestamps: two subscriptions bought hours apart on the same date
 * are one billing day to the person paying, and telling him he has «تاريخان» because of a clock
 * difference would be true of the data and false of his month. An unread billing (`checked` false)
 * counts nothing — it has no dates to count.
 */
export function distinctRenewalDays(answer: Owned | null | undefined): Set<string> {
  if (!answer?.checked) return new Set();
  const days = new Set<string>();
  for (const a of answer.apps) if (a.owned && a.renews_at) days.add(renewalDay(a.renews_at));
  const base = renewalDay(answer.base?.renews_at);
  if (base) days.add(base);
  return days;
}


/** A day an owner can plan around: western digits and a Gregorian month, like every other date
 *  in this product. Seconds on the wire — the subscription's `current_period_end`. */
function renewalDay(epoch: number | null | undefined): string {
  return epoch
    ? new Date(epoch * 1000).toLocaleDateString('ar-SA-u-nu-latn-ca-gregory',
                                                { day: 'numeric', month: 'long' })
    : '';
}


// «تطبيقات، لا باقات» — راجِع does not sell subscription TIERS of one
// product; it sells INDEPENDENT APPS a shop adds to its base, each with its own price, its own
// subscription, its own cancel. `الأساس` is itself one of them — the one every other app needs
// running under it, not a different kind of thing. This card is the one place that fact has to
// read true at a glance, so it is named, and built, around an app — never a "plan".
function AppCard({
  plan, owned, busy, sellable, onBuy, ownedLabel, buyLabel, renewsAt, unreadNote, lockedNote, compact,
  onSwitch, switchLabel, switching, onCancel, cancelLabel, cancelPending, cancelPendingNote,
  canceling, statusLabel, statusTone, switchPending, switchPendingNote, onCancelSwitch, cancelingSwitch,
  onUndoCancel, undoingCancel, session,
}: {
  /** Only for the "?" beside a status badge that genuinely needs one (trial/past-due/paused) —
   *  every other passive label on this card is already said in plain Arabic right on it. */
  session: Session;
  plan: Plan;
  /** true · false · null while the answer has not arrived or billing could not be asked. */
  owned: boolean | null;
  busy: boolean;
  sellable: boolean;
  onBuy: () => void;
  ownedLabel: string;
  buyLabel: string;
  /** When THIS app renews — its own subscription's date, not the shop's base. */
  renewsAt?: number | null;
  /** The server's own sentence when billing was ASKED and could not answer. Empty while the read
   *  is still in flight — the two are different states and the card must not merge them. */
  unreadNote?: string;
  /** `missingRequirement`'s own sentence — this shop holds none of `plan.requires_any`'s keys yet
   *  (e.g. نقاطي needs تسجيل زيارة or الحجوزات first). Same placement/styling as the "needs base
   *  first" note above the apps grid, but per-card, since the requirement is per-plan. Empty
   *  when the plan declares no dependency, or the dependency is already satisfied. */
  lockedNote?: string;
  /** CAPACITY ROWS ONLY. One feature line and a price is the whole card — the base's own padding
   *  and icon size read as empty space around that little, not as room to breathe. */
  compact?: boolean;
  /** BASE TIERS ONLY (audit #5, 2026-08-22) — given instead of `onBuy` when he already owns a
   *  DIFFERENT base. Buying a second base subscribes him twice; this is the one card state that
   *  means «تبديل», not «شراء». */
  onSwitch?: () => void;
  switchLabel?: string;
  switching?: boolean;
  /** OWNED CARDS ONLY («كل تطبيق له إدارة اشتراكه الخاص»). One shape, two callers:
   *  an app cancels itself immediately; the base opens the confirmation dialog (which also
   *  cancels every app with it) — the card only ever triggers whichever its caller gave it. */
  onCancel?: () => void;
  cancelLabel?: string;
  cancelPending?: boolean;
  /** What to say INSTEAD of the cancel button while pending — the base names its date («ينتهي
   *  في…»), an app says the generic sentence. Falls back to the generic one if omitted. */
  cancelPendingNote?: string;
  canceling?: boolean;
  /** THE BASE CARD ONLY — overrides the plain «اشتراكك» badge with the honest status word
   *  (فعّال/متأخر الدفع/قيد الإلغاء) the deleted top summary card used to carry alone. Apps stay
   *  on the default success badge (`ownedLabel`) — an app has no `past_due` of its own to report. */
  statusLabel?: string;
  statusTone?: 'success' | 'warning' | 'danger';
  /** THE BASE CARD ONLY (v0.16.33) — a SCHEDULED DOWNGRADE, taking effect at the next renewal.
   *  Shown instead of the cancel control on the OWNED card (the subscription he still has, in full, until
   *  then), with its own undo — never a proration, never a credit, so there is nothing here to
   *  reverse but the schedule itself. */
  switchPending?: boolean;
  switchPendingNote?: string;
  onCancelSwitch?: () => void;
  cancelingSwitch?: boolean;
  /** «تراجع عن إيقاف التجديد» (v0.16.34) — undoes a scheduled cancel before it takes effect, on
   *  ANY owned card that has one (base or app, same shape). Shown beside `cancelPendingNote`
   *  instead of replacing it: he still needs to know exactly when it would have ended if he does
   *  nothing, and the undo is the second half of that sentence, not a substitute for it. */
  onUndoCancel?: () => void;
  undoingCancel?: boolean;
}) {
  const price = monthly(plan);
  const lines = planLines(plan);
  // THE BASE HAS NO PURCHASE KEY IN THE REGISTRY — `owns()` treats it as always held, which is
  // what stops «الأساس» being drawn locked while an entitlement read is still in flight. So it is
  // found by id, and every other row by the key it grants.
  const app = kindOf(plan) === 'base'
    ? APP_ROWS.find((a) => a.id === 'base')
    : APP_ROWS.find((a) => a.key === appKey(plan));
  const has = owned === true;
  const Icon = APP_ICON[app?.id ?? ''] ?? Layers;
  return (
    <article
      className={[
        'group relative flex h-full flex-col overflow-hidden rounded-card',
        compact ? 'gap-2 p-3' : 'gap-3 p-5',
        // TRANSFORM, NOT JUST SHADOW - a card a shop can buy responds to the pointer arriving on
        // it the same way rj-ui's own Button does (a small lift, not a bounce): a screen full of
        // app cards should read as a store with pressable things in it, not a page of printed
        // tiles.
        'transition-[transform,box-shadow] duration-200',
        has
          // OWNED READS AS SETTLED, NOT AS SOLD. A ring rather than a fill: a card he already owns
          // must not compete for attention with the ones he might buy.
          ? 'bg-surface-1 shadow-sm ring-1 ring-success-soft'
          : 'bg-surface-1 shadow-sm hover:-translate-y-0.5 hover:shadow-md',
      ].join(' ')}
    >
      {/* A HAIRLINE OF ACCENT ALONG THE TOP of what he owns - the whole decoration budget of this
          screen. Anything louder turns a shop into an advertisement. */}
      {has ? <span aria-hidden className="absolute inset-x-0 top-0 h-0.5 bg-success" /> : null}

      <header className="flex items-start justify-between gap-2">
        <div className={compact ? 'flex items-center gap-1.5' : 'flex items-center gap-2.5'}>
          {/* THE FACE OF THE APP, NOT DECORATION FOR ITS OWN SAKE - the same icon this app wears
              in the rail once he owns it, so the card that sells campaigns and the row it lands
              on afterward are visibly the same thing. Capacity rows carry no app icon of their
              own (they grant seats or branches, not a feature), so this is skipped there - a
              generic Layers badge beside a seat count would say nothing true. */}
          {compact ? null : (
            <span
              aria-hidden
              className={[
                'grid h-10 w-10 shrink-0 place-items-center rounded-full',
                has ? 'bg-success-soft text-success-on-soft' : 'bg-surface-2 text-text-secondary',
              ].join(' ')}
            >
              <Icon size={18} />
            </span>
          )}
          <h3 className={compact ? 'text-sm font-medium leading-tight' : 'text-base font-medium leading-tight'}>
            {plan.name}
          </h3>
        </div>
        {has && statusLabel ? (
          <span className="flex items-center gap-1">
            <Badge tone={statusTone ?? 'success'}>{statusLabel}</Badge>
            {statusAnchor(statusLabel) ? <AssistantHint anchor={statusAnchor(statusLabel)!} session={session} /> : null}
          </span>
        ) : has && ownedLabel ? <Badge tone="success">{ownedLabel}</Badge> : null}
      </header>

      {/* WHAT IT DOES FOR HIM. The one line that does the selling - first, before a single number,
          because that is the order a shop owner actually decides in. */}
      {app?.what ? (
        <p className="text-sm leading-relaxed text-text-secondary">{app.what}</p>
      ) : null}

      {/* THE PRICE AND ITS TAX NOTE, ONE UNIT - was two elements pulled together with a negative
          margin, which is a hack pretending to be a gap. Grouped in one flex column so the tax
          line reads as a footnote OF the price above it, not a stray sentence near it. */}
      {price?.amount_minor ? (
        <div className="flex flex-col gap-0.5">
          <div className="flex items-baseline gap-1.5">
            <span className={compact
              ? 'text-xl font-semibold tabular-nums leading-none'
              : 'text-3xl font-semibold tabular-nums leading-none'}>
              {riyals(price.amount_minor)}
            </span>
            <span className="text-sm text-text-secondary">ريال / شهر</span>
          </div>
          {/* SAID, NOT ASSUMED - the server's own flag. A shop owner reading a price without it
              budgets the wrong number. Skipped in the compact card: a capacity row's tax note
              would be the longest line on a card whose whole point is to stay short. */}
          {price.includes_tax && !compact ? (
            <span className="text-xs text-text-secondary">شامل ضريبة القيمة المضافة</span>
          ) : null}
        </div>
      ) : null}

      {lines.length ? (
        <ul className={compact
          ? 'flex flex-col gap-1 border-t border-border-subtle pt-2 text-xs'
          : 'flex flex-col gap-1 border-t border-border-subtle pt-3 text-sm'}>
          {lines.map((line) => (
            <li key={line} className="flex items-start gap-2 text-text-secondary">
              <Check size={compact ? 12 : 15} className="mt-0.5 shrink-0 text-text-secondary" aria-hidden />
              <span>{line}</span>
            </li>
          ))}
        </ul>
      ) : null}

      {/* THE OWNED APP'S OWN META ROW - renewal date and where it lives, together on one line
          instead of stacked as two identical grey paragraphs competing for the same attention.
          "where did I put what I bought" is the first support question after every purchase, and
          "when am I charged" the second; a shop owner who already owns this app wants both in one
          glance, not two lines he has to read separately to notice they are related. */}
      {has && (renewalDay(renewsAt) || app?.section) ? (
        <p className="flex flex-wrap items-center gap-x-1.5 text-xs text-text-secondary">
          {renewalDay(renewsAt) ? <span>يتجدّد في {renewalDay(renewsAt)}</span> : null}
          {renewalDay(renewsAt) && app?.section ? <span aria-hidden className="text-text-muted">·</span> : null}
          {app?.section ? <span>يظهر في «{SECTION_LABEL[app.section] ?? app.section}»</span> : null}
        </p>
      ) : null}

      <div className="mt-auto pt-2">
        {has ? (
          // «كل تطبيق له إدارة اشتراكه الخاص» - drawn on ANY owned card that was given a cancel
          // control: an app cancels itself here directly; the base opens the confirmation
          // dialog instead (still this same button, a different `onCancel`).
          //
          // PRIORITY: cancel_at_period_end WINS over a scheduled switch (mirrors billing-service's
          // own rule that an ending subscription never renews onto anything) - so a card never
          // has to say both "ending" and "switching to X" about the same future date at once.
          cancelPending ? (
            <div className="flex flex-col gap-1.5">
              <p className="text-xs text-text-secondary">
                {cancelPendingNote || 'لن يتجدّد بعد نهاية الفترة.'}
              </p>
              {onUndoCancel ? (
                <Button type="button" variant="ghost" size="sm" disabled={undoingCancel} onClick={onUndoCancel}>
                  {undoingCancel ? 'يُرجَع…' : 'تراجع عن إيقاف التجديد'}
                </Button>
              ) : null}
            </div>
          ) : switchPending ? (
            <div className="flex flex-col gap-1.5">
              <p className="text-xs text-text-secondary">{switchPendingNote}</p>
              {onCancelSwitch ? (
                <Button type="button" variant="ghost" size="sm" disabled={cancelingSwitch} onClick={onCancelSwitch}>
                  {cancelingSwitch ? 'يُلغى…' : 'تراجع عن التبديل'}
                </Button>
              ) : null}
            </div>
          ) : onCancel ? (
            // RED, DELIBERATELY — leaving is the one action on this card that costs him something,
            // and a neutral grey button said that no louder than the "buy" button beside it does on
            // every other card. Colour is the fastest signal a glance reads; a destructive action
            // wearing the same tone as a neutral one is a colour that is not saying anything.
            <Button type="button" variant="danger" size="sm" disabled={canceling} onClick={onCancel}>
              {canceling ? 'يُوقَف…' : (cancelLabel || 'إيقاف التجديد')}
            </Button>
          ) : null
        ) : onSwitch ? (
          <Button type="button" variant="outline" disabled={busy || switching} onClick={onSwitch}>
            {switching ? 'يُبدَّل…' : switchLabel}
          </Button>
        ) : (
          // FULL WIDTH, LIKE THE CARD'S OWN «إيقاف التجديد» BUTTON BELOW IT — «أضِفه» is four
          // letters, and `Button` shrinks to its label by default (inline-flex, no width of its
          // own), so next to the danger button's long "إيقاف تجديد هذا التطبيق" text this one sat
          // as a small floating pill on an otherwise full-width card (screenshot). The card's own
          // weight, not the label's length, should decide how big the one action on it reads.
          <Button type="button" size="lg" className="w-full"
                 disabled={busy || !sellable} onClick={onBuy}>
            {buyLabel}
          </Button>
        )}
        {/* THE THIRD STATE, SAID RATHER THAN GUESSED. While the answer has not arrived — or when
            billing could not be asked — the card claims neither. Telling a paying shop it has not
            paid is worse than telling it to wait a moment.
            AND «ما زلنا نقرأ» IS NOT «سألنا ولم نصل». Both used to print «جارٍ التحقق…», so a
            billing outage read as a spinner that never ends, on the one screen an owner opens to
            BUY — no reason, and nothing to retry. `Locked.tsx` has told these two apart since م;
            this card is where the rule had not reached. The sentence is the server's own, because
            it knows what happened and a second vocabulary for one failure invents a second
            problem. */}
        {owned === null ? (
          <p className="mt-2 text-xs text-text-secondary">
            {unreadNote || 'جارٍ التحقق من اشتراكك…'}
          </p>
        ) : null}
        {/* `plan.requires_any` — this shop holds none of the app(s) this plan needs yet. Said
            here rather than discovered as a refusal after he presses, same posture as the base
            note above the apps grid. */}
        {lockedNote ? (
          <p className="mt-2 text-xs text-text-secondary">{lockedNote}</p>
        ) : null}
      </div>
    </article>
  );
}

/** The word for ONE of whatever this capacity row grants («مقعد»/«فرع») — read off its own
 *  gauge limit key, never guessed from its name. Falls back to a generic word rather than the raw
 *  machine key, matching `planLines`' own rule: a key we have no sentence for says nothing sooner
 *  than it says something wrong. */
function capacityUnitWord(plan: Plan): string {
  for (const [key, lim] of Object.entries(plan.limits ?? {})) {
    if (lim.kind === 'boolean') continue;
    if ((typeof lim.limit === 'number' && lim.limit > 0) || lim.limit === 'unlimited') {
      const word = LIMIT_WORDS[key]?.unit;
      if (word) return word;
    }
  }
  return 'وحدة';
}

/**
 * ONE CARD PER CAPACITY KIND (موظفين، فروع)، WITH A +/- INSTEAD OF A REPEATED «أضِف».
 *
 * A CAPACITY PLAN IS PRICED PER UNIT — the row itself already says so (one seat, one branch); this
 * card is the one place that price is multiplied by how many he wants, live, before he ever presses
 * anything that charges him. THE FIRST UNIT GOES THROUGH THE ORDINARY CARD-FORM PURCHASE (a real
 * subscription needs a payment token the first time); every unit after that is the SAME
 * subscription's own `quantity` moved up or down — no repeated purchase, no second row.
 *
 * ZERO IS NOT A QUANTITY THIS CARD EVER SENDS. Billing refuses `quantity < 1` outright, and
 * deciding what "remove the last one" means is not this stepper's job — that is the same confirm
 * dialog an app's own cancel already uses, reached here identically.
 */
function CapacityAddonCard({
  plan, sub, busy, sellable, unreadNote, onBuyFirst, onChangeQuantity, onRemoveLast,
}: {
  plan: Plan;
  /** `undefined` — nothing bought yet, the stepper reads as zero. */
  sub: Subscription | undefined;
  /** THIS card's own press in flight — never the screen-wide `busy` (that one is the card-form
   *  purchase only; the stepper has its own so a customer bumping seats does not grey out every
   *  other capacity card too). */
  busy: boolean;
  sellable: boolean;
  unreadNote?: string;
  onBuyFirst: () => void;
  onChangeQuantity: (quantity: number) => void;
  onRemoveLast: () => void;
}) {
  const price = monthly(plan);
  const unit = capacityUnitWord(plan);
  const qty = sub?.quantity ?? 0;
  const unitMinor = price?.amount_minor ?? 0;
  return (
    <article className="flex h-full flex-col gap-2 rounded-card bg-surface-1 p-3 shadow-sm">
      <h3 className="text-sm font-medium leading-tight">{plan.name}</h3>
      {unitMinor ? (
        <p className="text-xs text-text-secondary">
          {riyals(unitMinor)} ريال / شهر لكل {unit}
        </p>
      ) : null}
      <div className="mt-auto flex items-center justify-between gap-2 border-t border-border-subtle pt-2">
        <div className="flex items-center gap-2" role="group" aria-label={`عدد ${plan.name}`}>
          <Button type="button" variant="outline" size="sm" aria-label={`إنقاص ${unit}`}
                  disabled={busy || !sellable || qty === 0}
                  onClick={() => (qty > 1 ? onChangeQuantity(qty - 1) : onRemoveLast())}>
            <Minus size={14} />
          </Button>
          <span className="min-w-[1.5rem] text-center text-sm font-medium tabular-nums">{qty}</span>
          <Button type="button" variant="outline" size="sm" aria-label={`زيادة ${unit}`}
                  disabled={busy || !sellable}
                  onClick={() => (qty === 0 ? onBuyFirst() : onChangeQuantity(qty + 1))}>
            <Plus size={14} />
          </Button>
        </div>
        {qty > 0 && unitMinor ? (
          <span className="text-sm font-semibold tabular-nums">{riyals(unitMinor * qty)} ريال</span>
        ) : null}
      </div>
      {unreadNote ? <p className="text-xs text-text-secondary">{unreadNote}</p> : null}
    </article>
  );
}


export function PlansPane({
  session, catalog, onGoConnect, owned,
}: {
  session: Session;
  catalog: Catalog;
  /** What billing says this shop holds, in the four states of ../loading.ts: `undefined` while
   *  the read is in flight, `null` if it failed, DENIED where the role cannot ask, and the answer
   *  itself. It is NEVER rendered as «not bought» — telling a paying shop it has not paid is the
   *  one mistake this pane must not make. */
  owned?: Loading<Owned>;
  /** Takes him to the connection pane. Passed in, because this pane does not own the navigation. */
  onGoConnect: () => void;
}) {
  const [plans, setPlans] = useState<Plan[] | null | undefined>(undefined);
  /** EVERY subscription he holds, not just one. A shop with a base and two apps holds three rows,
   *  and cancelling the RIGHT one — the base, ending the relationship, not an app, dropping a
   *  feature — needs the whole list rather than whichever row billing happened to return first. */
  const [subs, setSubs] = useState<Subscription[] | null | undefined>(undefined);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  /** What the server says is still owed after a successful subscription. Never an error. */
  const [notice, setNotice] = useState('');
  /** «إلغاء الاشتراك» — its own dialog, its own busy flag, its own error. Kept apart from `busy`/
   *  `error` above: those belong to BUYING, and a cancel in flight must not grey out every app
   *  card on the screen as if a purchase were happening. */
  const [confirmingCancel, setConfirmingCancel] = useState(false);
  const [cancelBusy, setCancelBusy] = useState(false);
  const [cancelError, setCancelError] = useState('');
  /** Which APP's own cancel is in flight — separate from `cancelBusy` (the base's), since either
   *  can happen while the other is untouched. */
  const [cancelingAppId, setCancelingAppId] = useState('');
  const [appCancelError, setAppCancelError] = useState('');
  /** THE APP'S OWN CONFIRMATION — same discipline the base already has, asked for directly: a
   *  press must never fire the request itself, only open the dialog that names what actually
   *  happens (works exactly as-is until the date already on the card, then stops renewing). Holds
   *  the pending subscription id AND its app's name, since the dialog needs both and neither
   *  the id alone nor `apps` alone can answer «which app, in his own words» on its own. */
  const [confirmingCancelApp, setConfirmingCancelApp] = useState<{ subId: string; name: string } | null>(null);
  /** WHICH CAPACITY ROW'S STEPPER IS MID-PRESS — its plan id, not its subscription id: the very
   *  first + (nothing owned yet) has no subscription id to key on, only the plan being bought. */
  const [capacityBusyPlanId, setCapacityBusyPlanId] = useState('');
  const [capacityError, setCapacityError] = useState('');
  /** THE CARD FORM, OPEN FOR ONE OF TWO REASONS — buying an app, or replacing the card on the
   *  base subscription. `null` is closed; it is not a screen of its own, same as `reading` on
   *  «رسائلي». Which reason decides what a resolved token is handed to next. */
  const [cardFormPending, setCardFormPending] = useState<PendingPayment | null>(null);
  /** True only while resolving a token AFTER the 3DS redirect brought him back — a distinct wait
   *  from `busy`, because there is no form and no button to grey out at that moment. */
  const [resolvingReturn, setResolvingReturn] = useState(false);
  /** «تبديل الاشتراك الأساسي» (audit #5) — its own dialog, its own busy flag, its own error, same
   *  reasoning as cancel's: switching in flight must not grey out the whole apps grid. */
  const [confirmingChange, setConfirmingChange] = useState<Plan | null>(null);
  const [changeBusy, setChangeBusy] = useState(false);
  const [changeError, setChangeError] = useState('');
  /** Its own banner, not `notice` — that one is titled «تم الاشتراك ✓» and offers «اربط واتسابي
   *  الآن», neither of which is true of a SUBSCRIPTION SWITCH on an already-connected shop. */
  const [changeNotice, setChangeNotice] = useState('');
  /** «تراجع عن التبديل» (v0.16.33) — undoing a SCHEDULED downgrade before its renewal, a distinct
   *  action from `changeBusy`/`changeError` above (those cover the confirm dialog picking a new
   *  subscription; this covers cancelling one already picked). */
  const [cancelSwitchBusy, setCancelSwitchBusy] = useState(false);
  const [cancelSwitchError, setCancelSwitchError] = useState('');
  /** «تراجع عن إيقاف التجديد» (v0.16.34) — undoing an already-scheduled cancel, on either the base
   *  or an app. One flag per kind rather than a shared boolean: the base and an app can each have
   *  their own pending cancel at once, and undoing one must not grey out the other's button. */
  const [undoBaseCancelBusy, setUndoBaseCancelBusy] = useState(false);
  const [undoingAppCancelId, setUndoingAppCancelId] = useState('');
  const [undoCancelError, setUndoCancelError] = useState('');
  /**
   * WHETHER THERE IS A LIVE WAY TO PAY AT ALL — asked, never assumed.
   *
   * With no gateway configured this screen was a shop with no till: every press wrote «اشتراكك» over
   * the last one and no riyal moved, so an owner could walk between «الأساسية» and «الاحترافية»
   * all afternoon. A product that hands out its paid tiers to whoever presses hardest is not
   * generous; it is broken, and the first shop to notice tells the second.
   *
   * `undefined` while unknown, so the buttons are not rendered as live before we know they are.
   */
  const [pay, setPay] = useState<{ enabled: boolean; message?: string } | undefined>(undefined);

  const canBrowse = action(catalog, 'billing.plans');
  // OUR PATH, NOT BILLING'S OWN. `subscription.activate` is the only route that enforces the one
  // rule that is ours: no PAID subscription before WhatsApp is connected (§6.2.1) — a shop that
  // buys first and cannot send is a refund and a bad first week. `billing.subscribe` is
  // billing-service's raw route; it knows nothing about WhatsApp, because it is the platform's and
  // shared by every product built on it.
  //
  // THE SCREEN WAS CALLING THE RAW ONE. The gate existed, was tested, and sat on a road nobody
  // drove down. It falls back to `billing.subscribe` only where ours is absent from the catalogue,
  // so an owner whose operations manifest is unreachable is not stranded mid-purchase.
  const canSubscribe = action(catalog, 'subscription.activate')
    ?? action(catalog, 'billing.subscribe');

  const load = () => {
    if (canBrowse) {
      call<{ plans: Plan[] }>(session, canBrowse)
        .then((x) => setPlans(ordered((x.plans ?? []).filter((p) => p.active !== false && p.listed !== false))))
        .catch(() => setPlans(null));
    } else {
      setPlans([]);
    }
    const mine = action(catalog, 'billing.my_subscriptions');
    if (mine) {
      call<{ subscriptions: Subscription[] }>(session, mine)
        .then((x) => setSubs(x.subscriptions ?? []))
        .catch(() => setSubs(null));
    } else {
      setSubs(null);
    }
  };

  // «إلغاء الاشتراك» — THE BUTTON THAT DID NOT EXIST (audit finding #2, 2026-08-22). The route was
  // whole: cancel-at-period-end, tested, declared in the manifest — and nothing in this console
  // ever called it. A customer wanting to end the relationship had no self-service path at all,
  // which the audit rightly called a regulatory exposure, not a missing convenience.
  //
  // AT PERIOD END, ALWAYS, NOT A CHOICE HERE. `POST .../cancel` defaults to `at_period_end=true`
  // server-side (billing.py's own default) — service keeps working through what he already paid
  // for, and nothing charges again after it. An immediate/forfeit cancel is a support conversation,
  // deliberately: it is the destructive, rarer path, and a self-service button for it belongs next
  // to a real refund policy, not bundled into this pass.
  // CANCELLING THE BASE TAKES EVERY APP WITH IT — stated plainly in the confirmation dialog
  // below, and ACTUALLY DONE here rather than left for the backend to infer: nothing in
  // billing-service cascades a subscription cancellation to any other row, so a base-only cancel
  // would leave every app subscription billing on, independently, while its whole reason for
  // existing (the base under it) is gone. Each app's own cancel is idempotent to call twice —
  // billing.cancel is a no-op on an already-pending or already-canceled row — so this is safe even
  // the day base-services DOES add a cascade of its own.
  const cancelBase = async () => {
    const a = action(catalog, 'billing.cancel');
    if (!a || !baseSub) return;
    setCancelBusy(true); setCancelError('');
    try {
      await Promise.all([
        call(session, a, { id: baseSub.id }),
        ...activeAppSubs.map((s) => call(session, a, { id: s.id })),
      ]);
      setConfirmingCancel(false);
      load();
    } catch (e) {
      setCancelError(e instanceof Error ? e.message : 'تعذّر إلغاء الاشتراك.');
    } finally {
      setCancelBusy(false);
    }
  };

  /** «إيقاف تجديد هذا التطبيق» — an app's own, independent cancellation. Never touches the base or
   *  any other app; the reverse direction (base takes every app with it) is `cancelBase` above.
   *  Only ever fired from `confirmingCancelApp`'s own confirm button — never directly from the
   *  card, same discipline the base already had and the app was missing. */
  const cancelApp = async (subId: string) => {
    const a = action(catalog, 'billing.cancel');
    if (!a) return;
    setCancelingAppId(subId); setAppCancelError('');
    try {
      await call(session, a, { id: subId });
      setConfirmingCancelApp(null);
      load();
    } catch (e) {
      setAppCancelError(e instanceof Error ? e.message : 'تعذّر إيقاف تجديد التطبيق.');
    } finally {
      setCancelingAppId('');
    }
  };

  /** «تبديل الاشتراك الأساسي» (audit #5) — THE ACTION THAT DID NOT EXIST. billing-service's `/change` route is
   *  whole, proration and all; nothing in this console ever called it, so switching base tiers
   *  meant a second «شراء» - a second subscription rather than a swap.
   *
   *  THE STRIPE-STYLE SPLIT (no negative balance or refund, ever — fixed
   *  upstream v0.16.33): an UPGRADE is charged the prorated difference FIRST and takes effect only
   *  once that charge clears - `applied: "upgraded"`. A DOWNGRADE touches nothing now; the shop
   *  keeps its current, already-paid subscription at full value until the period ends, and the new one is
   *  SCHEDULED for the next renewal at full price - `applied: "scheduled_downgrade"`, never a
   *  credit line, never a negative balance. The two need two different sentences, because they are
   *  two different promises: one says "already happened", the other says "will start". */
  const changeBase = async () => {
    const a = action(catalog, 'billing.change_plan');
    if (!a || !baseSub || !confirmingChange) return;
    setChangeBusy(true); setChangeError('');
    try {
      const out = await call<{ applied?: string; proration_minor?: number }>(
        session, a, { id: baseSub.id, plan_id: confirmingChange.id });
      setConfirmingChange(null);
      if (out?.applied === 'scheduled_downgrade') {
        setChangeNotice(
          `سيتحول اشتراكك إلى «${confirmingChange.name}» عند نهاية الفترة الحالية، بالسعر الكامل ` +
          'للفترة الجديدة — لن يُخصم أو يُضاف أي فرق قبل ذلك.');
      } else {
        const d = out?.proration_minor;
        setChangeNotice(
          typeof d === 'number' && d > 0
            ? `تم تبديل اشتراكك إلى «${confirmingChange.name}». حُصِّل ${riyals(d)} ريال فرق السعر لبقية هذه الفترة.`
            : `تم تبديل اشتراكك إلى «${confirmingChange.name}».`);
      }
      load();
    } catch (e) {
      setChangeError(e instanceof Error ? e.message : 'تعذّر تبديل الاشتراك.');
    } finally {
      setChangeBusy(false);
    }
  };

  /** THE CAPACITY STEPPER'S +/- — same route as `changeBase` (`billing.change_plan`), same
   *  plan id on both sides, only `quantity` moves. Server-side this is `change_plan()` editing
   *  `sub.quantity` IN PLACE on the one row he already holds: raising it charges the prorated
   *  difference now (an upgrade, by price), lowering it schedules the smaller amount for the next
   *  renewal (a downgrade) — never a second subscription, never a refund line here.
   *
   *  NEVER CALLED AT quantity < 1 — the backend itself refuses that (`ge=1`), and it is not this
   *  screen's job to guess what removing the last unit should mean; that is `cancelApp` above,
   *  reached through the same confirm dialog an app's own cancel uses. */
  const changeCapacityQuantity = async (plan: Plan, sub: Subscription, quantity: number) => {
    const a = action(catalog, 'billing.change_plan');
    if (!a || quantity < 1) return;
    setCapacityBusyPlanId(plan.id); setCapacityError('');
    try {
      await call(session, a, { id: sub.id, plan_id: plan.id, quantity });
      load();
    } catch (e) {
      setCapacityError(e instanceof Error ? e.message : 'تعذّر تعديل العدد.');
    } finally {
      setCapacityBusyPlanId('');
    }
  };

  /** «تراجع عن التبديل» (v0.16.33) — undoes a SCHEDULED downgrade before its renewal. Idempotent on
   *  the server (a no-op when nothing is scheduled), so a stale button or a double click is
   *  harmless rather than an error. */
  const cancelScheduledChange = async () => {
    const a = action(catalog, 'billing.cancel_scheduled_change');
    if (!a || !baseSub) return;
    setCancelSwitchBusy(true); setCancelSwitchError('');
    try {
      await call(session, a, { id: baseSub.id });
      load();
    } catch (e) {
      setCancelSwitchError(e instanceof Error ? e.message : 'تعذّر التراجع عن التبديل.');
    } finally {
      setCancelSwitchBusy(false);
    }
  };

  /** «تراجع عن إيقاف التجديد» (v0.16.34) — undoes an already-scheduled cancel (base or app, same
   *  route: billing.undo_cancel is idempotent and never resurrects an already-ended subscription,
   *  so calling it on a stale button is harmless). One function, two callers below — same shape
   *  `cancelApp`/`cancelBase` already split into. */
  const undoCancel = async (subId: string, which: 'base' | 'app') => {
    const a = action(catalog, 'billing.undo_cancel');
    if (!a) return;
    if (which === 'base') setUndoBaseCancelBusy(true); else setUndoingAppCancelId(subId);
    setUndoCancelError('');
    try {
      await call(session, a, { id: subId });
      load();
    } catch (e) {
      setUndoCancelError(e instanceof Error ? e.message : 'تعذّر التراجع عن إيقاف التجديد.');
    } finally {
      if (which === 'base') setUndoBaseCancelBusy(false); else setUndoingAppCancelId('');
    }
  };

  useEffect(() => {
    const a = action(catalog, 'subscription.payment_state');
    if (!a) { setPay({ enabled: false, message: '' }); return; }
    call<{ enabled: boolean; message?: string }>(session, a)
      .then(setPay)
      // A FAILED READ IS NOT AN OPEN TILL. Erring the other way sells an app nobody can charge for.
      .catch(() => setPay({ enabled: false, message: '' }));
  }, [session, catalog]);

  useEffect(load, [session, catalog]);   // eslint-disable-line react-hooks/exhaustive-deps

  // OPENS THE CARD FORM RATHER THAN MINTING INLINE. Tokenising is no longer one call an owner
  // never sees — it is a real form, and almost always a full redirect to his bank's own 3DS page
  // and back (see payment.ts). `choose` only decides WHETHER a card is needed at all; the form
  // and the redirect-return effect below do the rest.
  const choose = (p: Plan, quantity = 1) => {
    setError('');
    // NOT GATED ON THE CONNECTION ANY MORE — see the module note. Only on having the action at
    // all, which is a capability question and not a readiness one.
    // NOT WHILE THE TILL IS SHUT. The press is still remembered — his choice is not lost — but
    // nothing is written and no subscription starts.
    // AND NOT WITHOUT A TOKEN WE CAN ACTUALLY MINT (د-15). `pay.enabled` answers «is there a
    // gateway key», which is a different question from «can this browser hand back a card
    // token». The screen used to press on regardless, posting `{ plan_id }` alone, and every
    // paid row came back 402 — a live-looking button that could never work, while the base
    // slipped through only because its trial skips the check.
    if (!canSubscribe) return;
    if (!canBuy({ hasAction: true, gatewayEnabled: Boolean(pay?.enabled),
                 canMint: canMintToken })) return;
    setCardFormPending({ kind: 'subscribe', planId: p.id, quantity });
  };

  /** The purchase itself, once a token exists — reached either straight from the form (a card
   *  that skipped 3DS) or from the redirect-return effect below (the ordinary case).
   *
   *  `quantity` — sent even at its default of 1 rather than omitted, so this call always states
   *  what it means: a capacity row's first unit is a subscription with quantity 1, not a bare
   *  subscribe that happens to read as one. */
  const finishSubscribe = async (planId: string, payment_token: string, quantity = 1) => {
    if (!canSubscribe) return;
    setBusy(true); setError('');
    try {
      const out = await call<{ notice?: string }>(session, canSubscribe,
                                                 { plan_id: planId, payment_token, quantity });
      // THE SERVER'S SENTENCE, NOT OURS. What is still owed after a successful subscription is a
      // product rule and it lives in one place; a second copy here is the one that goes stale.
      setNotice(out?.notice ?? '');
      setCardFormPending(null);
      load();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'تعذّر تفعيل الاشتراك.');
    } finally {
      setBusy(false);
    }
  };

  /** «تحديث بطاقة الدفع» — closes audit gap #3 on our side. Only renders/reaches here once
   *  billing.update_payment_method exists in the catalogue; until base-services ships that route
   *  (see the escalation) this whole path is simply unreachable, never rendered-and-refused. */
  const finishUpdatePaymentMethod = async (subscriptionId: string, payment_token: string) => {
    const a = action(catalog, 'billing.update_payment_method');
    if (!a) return;
    setBusy(true); setError('');
    try {
      await call(session, a, { id: subscriptionId, payment_token });
      setCardFormPending(null);
      setNotice('تم تحديث بطاقة الدفع.');
      load();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'تعذّر تحديث البطاقة.');
    } finally {
      setBusy(false);
    }
  };

  // THE RETURN FROM 3DS. Moyasar's own callback shape appends `id`/`status`/`message` to the URL
  // we gave it as `callback_url` — the same page, so this effect fires on every ordinary load
  // too, and `takePending()` is the guard: no pending payment, nothing to do, and a bookmarked or
  // refreshed URL carrying a stale `id` cannot replay anything a second time (`takePending`
  // clears itself on the first read, pending or not).
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const tokenId = params.get('id');
    const pending = takePending();
    if (!tokenId || !pending) return;
    setResolvingReturn(true);
    confirmToken(tokenId)
      .then((result) => {
        if (result.kind === 'error') { setError(result.message); return; }
        if (result.kind !== 'token') return;
        if (pending.kind === 'subscribe') {
          return finishSubscribe(pending.planId, result.token, pending.quantity ?? 1);
        }
        return finishUpdatePaymentMethod(pending.subscriptionId, result.token);
      })
      .finally(() => {
        setResolvingReturn(false);
        // THE URL IS CLEANED EITHER WAY. A refresh of this page must not re-run verification
        // against a token `takePending()` has already consumed and Moyasar may have expired.
        const url = new URL(window.location.href);
        for (const k of ['id', 'status', 'message']) url.searchParams.delete(k);
        window.history.replaceState({}, '', url.toString());
      });
    // Runs once, on mount only — a pending payment is read and cleared exactly once regardless of
    // what else on this screen re-renders afterward.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // ── GROUPED BY WHAT A ROW GRANTS, never by its name or its position in a list ─────────────
  // This is what makes the next app free to add: invoicing and CRM arrive as rows in the price
  // list and land in the right section without a line here.
  const bases = plans?.filter((p) => kindOf(p) === 'base') ?? [];
  const apps = plans?.filter((p) => kindOf(p) === 'app') ?? [];
  const capacity = plans?.filter((p) => kindOf(p) === 'capacity') ?? [];
  // THE ONE ROW «إلغاء الاشتراك» ACTS ON — matched by which PLAN it is a subscription TO, never
  // by position: `subs[0]` is whichever row billing happened to return first, and an app row
  // bought after the base would have been cancelled instead of the base itself. The bare
  // `subs?.[0]` this file used to keep around for the status badge and the past-due alert carried
  // exactly that same position bug into two more places — removed rather than fixed-in-place,
  // so it cannot regrow a third use.
  const baseSub = (subs ?? []).find((s) => bases.some((p) => p.id === s.plan_id));
  // EVERY APP'S OWN SUBSCRIPTION ROW — matched the same way (by which row it IS, never by
  // position). Each app is independently cancellable — «كل تطبيق له إدارة
  // اشتراكه الخاص» — but none of them exists without the base, so cancelling the base is stated
  // plainly as cancelling all of them together, never a silent side effect.
  const appSubs = (subs ?? []).filter((s) => apps.some((p) => p.id === s.plan_id));
  const activeAppSubs = appSubs.filter((s) => s.status !== 'canceled' && !s.cancel_at_period_end);
  // A CAPACITY ROW'S OWN SUBSCRIPTION — same matching rule as `appSubs`, one row per plan (its
  // `quantity` is what varies now, not how many rows exist). `undefined` reads as "none bought yet"
  // at every call site below, same as `appSub` above never guesses at a missing app subscription.
  const capacitySubs = (subs ?? []).filter((s) => capacity.some((p) => p.id === s.plan_id))
    .filter((s) => s.status !== 'canceled' && !s.cancel_at_period_end);
  // FOUR ANSWERS NOW, and none of them is «he has not bought». The read may be in flight
  // (`undefined`), have failed (`null`), be one his role cannot make (DENIED), or have arrived
  // with `checked: false` because billing itself could not be asked. The sections claim nothing
  // in every one of those cases — telling a paying shop it has not paid is the mistake this pane
  // exists to avoid.
  const answer = isReady(owned) ? owned : null;
  const hasBase = !answer || !answer.checked ? null : Boolean(answer.base);
  // WHAT BILLING SAID WHEN IT COULD NOT ANSWER — its sentence, not ours. Empty while the read is
  // still in flight, so the cards below can tell «ما زلنا نقرأ» from «سألنا ولم نصل» instead of
  // printing one line for both.
  const unreadNote = unreadSentence(answer);

  if (plans === null || subs === undefined) {
    return (
      <div className="flex flex-col gap-3">
        <Skeleton height={120} />
        <Skeleton height={120} />
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-4">
      {/* «متأخر الدفع» — ITS OWN ALERT, NOT BURIED IN A CARD. The aggregate
          «اشتراكك: الأساس + N تطبيقات» summary card is gone entirely — each subscription now
          carries its own status and its own cancel control on its own card, base included, below.
          A failing charge is the loudest thing an owner needs to see the moment he opens this
          screen, not a detail he finds by scrolling to the base card among the others.
          ANY SUBSCRIPTION, NOT JUST THE FIRST ONE IN THE ARRAY — same bug class as the base badge
          fix beside it: `subs?.[0]` is an arbitrary row, and a
          past-due APP subscription is just as real a billing problem as a past-due base. */}
      {(subs ?? []).some((s) => s.status === 'past_due') ? (
        <div className="flex flex-col gap-2 rounded-card border border-danger/30 bg-danger-soft p-4">
          <p className="text-sm text-danger">آخر محاولة سحب لم تنجح. حدّث بطاقتك حتى لا يتوقف اشتراكك.</p>
          {/* «تحديث بطاقة الدفع» — audit #3's other half, the one that closes the involuntary-
              churn loop: `dunning_sweep` on the backend keeps retrying the SAME stored token
              forever, and this was the only way that token could ever change. Reachable only
              once `billing.update_payment_method` exists in the catalogue AND this build can
              actually mint a token (`canMintToken` — false until Ops sets the Moyasar
              publishable key) — never rendered-and-refused. */}
          {baseSub && action(catalog, 'billing.update_payment_method') && canMintToken ? (
            <div>
              <Button type="button" variant="danger" size="sm"
                      onClick={() => setCardFormPending({ kind: 'update_payment_method',
                                                          subscriptionId: baseSub.id })}>
                تحديث بطاقة الدفع
              </Button>
            </div>
          ) : null}
        </div>
      ) : null}

      {/* THE CARD FORM — subscribing to a paid app, or replacing the card on the base. Shown
          inline rather than in a modal: it is a full-page redirect away and back on the ordinary
          path (3DS), and a modal that survives that round trip is a modal fighting its own DOM. */}
      {cardFormPending ? (
        <CardForm
          pending={cardFormPending}
          onCancel={() => setCardFormPending(null)}
          onToken={(token) => {
            if (cardFormPending.kind === 'subscribe') {
              void finishSubscribe(cardFormPending.planId, token, cardFormPending.quantity ?? 1);
            }
            else void finishUpdatePaymentMethod(cardFormPending.subscriptionId, token);
          }}
        />
      ) : null}

      {resolvingReturn ? (
        <p className="text-sm text-text-secondary">نتحقق من بطاقتك…</p>
      ) : null}

      {/* THE CONFIRMATION — never a silent press. He is ending a paid relationship, and the one
          thing he must know before he presses again is that nothing is taken from him: the shop
          keeps working exactly as it does today, until the day already printed above.
          A REAL MODAL, NOT A DIV IN THE PAGE FLOW — CONFIRMED BUG (screenshot): this used to
          render inline, at the TOP of the screen, while the button that opens it lives on a card
          inside the apps grid further down the page. Pressing "إيقاف التجديد" on any app near the
          bottom opened a dialog off-screen above — invisible without scrolling up, which reads
          exactly like the press did nothing at all. A portal-to-body modal is always visible
          regardless of where its trigger sits. */}
      <Modal open={confirmingCancel && Boolean(baseSub)}
            onClose={() => { setConfirmingCancel(false); setCancelError(''); }}
            title="تأكيد إيقاف تجديد الاشتراك">
        {baseSub ? (
          <div className="flex flex-col gap-4">
            <p className="text-sm text-text-secondary">
              {renewalDay(baseSub.current_period_end)
                ? `يستمر محلّك يعمل بلا أي تغيير حتى ${renewalDay(baseSub.current_period_end)}، ولن يتجدّد الاشتراك بعدها. لن نخصم منك شيئاً إضافياً.`
                : 'يستمر محلّك يعمل بلا أي تغيير حتى نهاية الفترة التي دفعت عنها، ولن يتجدّد الاشتراك بعدها.'}
            </p>
            {/* NO APP SURVIVES ITS BASE — stated plainly, not discovered a month later on a
                statement he did not expect. No app exists without the base under it, so cancelling
                it takes every app with it, on the same schedule. */}
            {activeAppSubs.length > 0 ? (
              <p className="text-sm text-text-secondary">
                يتوقف معه أيضاً: {activeAppSubs.map((s) => apps.find((p) => p.id === s.plan_id)?.name ?? 'تطبيق').join('، ')}
                — على نفس الموعد.
              </p>
            ) : null}
            {cancelError ? <p className="text-sm text-danger">{cancelError}</p> : null}
            <div className="flex gap-2">
              <Button type="button" variant="danger" disabled={cancelBusy} onClick={() => void cancelBase()}>
                تأكيد إيقاف التجديد
              </Button>
              <Button type="button" variant="ghost" disabled={cancelBusy}
                      onClick={() => { setConfirmingCancel(false); setCancelError(''); }}>
                تراجع
              </Button>
            </div>
          </div>
        ) : null}
      </Modal>

      {/* THE APP'S OWN CONFIRMATION — same discipline as the base's, one app at a time: he never
          fires this from the card itself, only opens this dialog, which names the exact app and
          the exact date before anything happens. Same modal fix as the base's, above. */}
      <Modal open={Boolean(confirmingCancelApp)}
            onClose={() => { setConfirmingCancelApp(null); setAppCancelError(''); }}
            title={confirmingCancelApp ? `تأكيد إيقاف تجديد «${confirmingCancelApp.name}»` : ''}>
        {confirmingCancelApp ? (
          <div className="flex flex-col gap-4">
            <p className="text-sm text-text-secondary">
              {(() => {
                const s = appSubs.concat(capacitySubs).find((x) => x.id === confirmingCancelApp.subId);
                return renewalDay(s?.current_period_end)
                  ? `يستمر «${confirmingCancelApp.name}» يعمل بلا أي تغيير حتى ${renewalDay(s?.current_period_end)}، ولن يتجدّد بعدها. لن نخصم منك شيئاً إضافياً.`
                  : `يستمر «${confirmingCancelApp.name}» يعمل بلا أي تغيير حتى نهاية الفترة التي دفعت عنها، ولن يتجدّد بعدها.`;
              })()}
            </p>
            {appCancelError ? <p className="text-sm text-danger">{appCancelError}</p> : null}
            <div className="flex gap-2">
              <Button type="button" variant="danger" disabled={cancelingAppId === confirmingCancelApp.subId}
                      onClick={() => void cancelApp(confirmingCancelApp.subId)}>
                تأكيد إيقاف التجديد
              </Button>
              <Button type="button" variant="ghost" disabled={cancelingAppId === confirmingCancelApp.subId}
                      onClick={() => { setConfirmingCancelApp(null); setAppCancelError(''); }}>
                تراجع
              </Button>
            </div>
          </div>
        ) : null}
      </Modal>

      {/* «تبديل الاشتراك الأساسي» CONFIRMATION — same discipline as cancel's: he is changing what he pays, and
          the one thing he must know before pressing again is what actually happens NOW.
          TWO DIFFERENT PROMISES (v0.16.33: «مافي رصيد سالب أو استرداد إطلاقاً»): an
          UPGRADE charges the prorated difference immediately and switches only once that clears —
          said as something about to be charged, not a fact already true. A DOWNGRADE changes
          NOTHING today; the current, already-paid subscription keeps working in full until the period
          ends, and only then does the new one — and its new price — begin. Neither sentence is a
          guess: this is exactly what billing-service now does. */}
      <Modal open={Boolean(confirmingChange)}
            onClose={() => { setConfirmingChange(null); setChangeError(''); }}
            title={confirmingChange ? `تأكيد التبديل إلى «${confirmingChange.name}»` : ''}>
        {confirmingChange ? (
          <div className="flex flex-col gap-4">
            <p className="text-sm text-text-secondary">
              {(monthly(confirmingChange)?.amount_minor ?? 0)
                >= (baseSub ? monthly(bases.find((b) => b.id === baseSub.plan_id) ?? confirmingChange)?.amount_minor ?? 0 : 0)
                ? 'حدود اشتراكك الجديد تسري فوراً، بعد تحصيل فرق السعر لبقية هذه الفترة من بطاقتك.'
                : 'يستمر اشتراكك الحالي كما هو حتى نهاية الفترة الحالية — لا يُخصم شيء الآن. عند التجديد القادم يبدأ سعر وحدود «' + confirmingChange.name + '».'}
            </p>
            {changeError ? <p className="text-sm text-danger">{changeError}</p> : null}
            <div className="flex gap-2">
              <Button type="button" disabled={changeBusy} onClick={() => void changeBase()}>
                تأكيد التبديل
              </Button>
              <Button type="button" variant="ghost" disabled={changeBusy}
                      onClick={() => { setConfirmingChange(null); setChangeError(''); }}>
                تراجع
              </Button>
            </div>
          </div>
        ) : null}
      </Modal>

      {changeNotice ? (
        <div className="rounded-card border border-success-soft bg-success-soft/40 p-5 shadow-sm">
          <p className="mb-1 font-medium">تم التبديل ✓</p>
          <p className="mb-4 text-sm text-text-secondary">{changeNotice}</p>
          <Button type="button" variant="ghost" onClick={() => setChangeNotice('')}>تمام</Button>
        </div>
      ) : null}

      {/* WHAT IS LEFT, AFTER THE SUBSCRIPTION SUCCEEDED. Not a refusal and not styled as one: the
          payment went through, and this is the one step between him and messages going out. It is
          the server's sentence — the rule lives in one place — with the button that does it. */}
      {/* NO TILL, SO NOTHING IS SOLD — and it is said plainly rather than by a button that does
          nothing. The day a gateway is configured this sentence disappears by itself: one key
          decides, read from the server, with no edit here and no rebuild. */}
      {pay?.enabled && !canMintToken ? (
        <div className="rounded-card border border-border-subtle bg-surface-2 p-5 text-center">
          <p className="mb-1 font-medium">الدفع بالبطاقة قريباً</p>
          <p className="text-sm text-text-secondary">{NO_CARD_FORM}</p>
        </div>
      ) : null}

      {pay && !pay.enabled && pay.message ? (
        <div className="rounded-card border border-border-subtle bg-surface-2 p-5 text-center">
          <p className="mb-1 font-medium">الدفع مغلق مؤقتاً</p>
          <p className="text-sm text-text-secondary">{pay.message}</p>
        </div>
      ) : null}

      {notice ? (
        <div className="rounded-card border border-success-soft bg-success-soft/40 p-5 shadow-sm">
          <p className="mb-1 font-medium">تم الاشتراك ✓</p>
          <p className="mb-4 text-sm text-text-secondary">{notice}</p>
          <div className="flex gap-2">
            <Button type="button" onClick={onGoConnect}>اربط واتسابي الآن</Button>
            <Button type="button" variant="ghost" onClick={() => setNotice('')}>لاحقاً</Button>
          </div>
        </div>
      ) : null}

      {error ? <p className="text-sm text-danger">{error}</p> : null}

      {/* ── THE STORE, NOT A LADDER ────────────────────────────────────────────────────────
          FOUR TIERS SOLD THE WRONG THING. A workshop that wanted campaigns and would never open
          an association engine had to buy the engine to reach them, and had to read the
          difference between four columns to discover that. Here he reads one line per thing and
          buys the thing.

          AND IT IS WHAT MAKES THE NEXT APP CHEAP TO ADD. Invoicing and CRM arrive as rows in the
          price list; this screen groups by what a row GRANTS, so neither needs a line here. */}
      {undoCancelError ? <p className="text-sm text-danger">{undoCancelError}</p> : null}
      {cancelSwitchError ? <p className="text-sm text-danger">{cancelSwitchError}</p> : null}

      {/* ── THE BASE, WIDE, WITH ITS CAPACITY BESIDE IT ────────────────────────────────────
          ONE ROW, NOT A STACK BELOW A STACK. The base is what he already pays for; «السعة» is
          what he adds to THAT subscription — a second branch, more seats. They are one decision,
          so they share a row: the base takes the wide two-thirds a real card needs to breathe,
          capacity the narrow third beside it. Below `lg` both fall back to one column, because on
          a phone there is no beside. */}
      {bases.length || capacity.length ? (
        <div className="grid gap-4 lg:grid-cols-[2fr_1fr] lg:items-start">
          {bases.length ? (
            <section className="flex flex-col gap-2">
              <h2 className="flex items-center gap-1 text-sm text-text-secondary">
                الاشتراك الأساسي
                <AssistantHint anchor="store.baseSection" session={session} />
              </h2>
              <ul className="grid gap-3">
                {bases.map((p) => {
                  // WHICH BASE, NOT JUST WHETHER ONE - `hasBase` alone used to mark EVERY base
                  // card owned the moment he had any one of them (audit #5's other half of the
                  // same bug: a shop on the cheap tier saw every tier badged as already his).
                  const isThisOne = hasBase === true ? baseSub?.plan_id === p.id : hasBase;
                  // UPGRADE OR SCHEDULED DOWNGRADE, NEVER A CREDIT (fixed
                  // upstream v0.16.33): billing-service now splits change_plan itself - an
                  // upgrade charges the difference and flips immediately, a downgrade schedules
                  // the same target for the next renewal at full price and touches nothing now.
                  // Both directions are safe to offer; only the label and the confirmation text
                  // differ, because they are two different promises to make him before he presses.
                  const currentBase = bases.find((b) => b.id === baseSub?.plan_id);
                  const isUpgrade = (monthly(p)?.amount_minor ?? 0)
                    >= (currentBase ? monthly(currentBase)?.amount_minor ?? 0 : 0);
                  const canSwitchToThis = hasBase === true && !isThisOne
                    && Boolean(action(catalog, 'billing.change_plan'));
                  // THE BASE'S OWN CARD NOW CARRIES WHAT THE DELETED SUMMARY CARD USED TO SAY:
                  // its honest status (including the متأخر الدفع fourth
                  // state, audit #3) and its own cancel control, exactly as an app card carries
                  // its. GATED ON THE SUBSCRIPTION ROW ITSELF, not on `isThisOne`/`hasBase`: the
                  // deleted summary card read `baseSub` straight off `billing.my_subscriptions`,
                  // never off the entitlements roll-up, so a viewer whose role can't check
                  // entitlements (`hasBase === null`) could still see and use billing controls -
                  // cancel must keep working for that viewer exactly as it did before.
                  const isBaseSubRow = baseSub?.plan_id === p.id;
                  // READ FROM baseSub, NOT sub — CONFIRMED BUG: `sub`
                  // is `subs?.[0]`, an arbitrary FIRST row of whatever order billing.my_subscriptions
                  // happened to return, not necessarily the base's own row. A shop with the base
                  // active and an app subscription first in the array read the base's badge as
                  // «متوقف» while every app card correctly read «مفعّل» — the base's status must
                  // come from the base's own subscription record, same as `cancel_at_period_end`
                  // two lines above already correctly does.
                  // FIVE REAL STATUSES, NOT TWO — CONFIRMED BUG (screenshot): billing-service's
                  // Subscription.status is trialing|active|past_due|paused|canceled (models.py),
                  // and a subscription DEFAULTS to "trialing" until its first run_cycle bills it
                  // active. This card only ever recognised "active" as working and printed
                  // «متوقف» for every other status — including a brand-new, perfectly healthy
                  // trial subscription — while every app card beside it correctly read «مفعّل»
                  // off the entitlements roll-up instead. Named honestly now, one word per status.
                  const statusLabel = isBaseSubRow
                    ? (baseSub?.cancel_at_period_end ? 'قيد الإلغاء'
                      : baseSub?.status === 'past_due' ? 'متأخر الدفع'
                      : baseSub?.status === 'trialing' ? 'تجريبي'
                      : baseSub?.status === 'paused' ? 'موقوف مؤقتاً'
                      : baseSub?.status === 'active' ? 'فعّال' : 'متوقف')
                    : undefined;
                  const statusTone = isBaseSubRow
                    ? (baseSub?.cancel_at_period_end ? 'warning'
                      : baseSub?.status === 'past_due' ? 'danger'
                      : baseSub?.status === 'trialing' ? 'success'
                      : baseSub?.status === 'paused' ? 'warning'
                      : baseSub?.status === 'active' ? 'success' : 'warning')
                    : undefined;
                  // A SCHEDULED DOWNGRADE, NAMED (v0.16.33) - shown only on the card he still owns
                  // (the subscription he keeps, in full, until the switch happens), never on the target -
                  // buying that card outright is still a different action from the one already
                  // scheduled toward it.
                  const pendingPlan = baseSub?.pending_plan_id
                    ? bases.find((b) => b.id === baseSub.pending_plan_id) : undefined;
                  const switchPending = isBaseSubRow && !baseSub?.cancel_at_period_end
                    && Boolean(pendingPlan);
                  return (
                    <li key={p.id}>
                      <AppCard
                        plan={p}
                        session={session}
                        owned={isBaseSubRow ? true : isThisOne}
                        busy={busy}
                        sellable={Boolean(canSubscribe && pay?.enabled && canMintToken)}
                        onBuy={() => choose(p)}
                        unreadNote={unreadNote}
                        ownedLabel="اشتراكك"
                        buyLabel="فعّل الأساس"
                        onSwitch={canSwitchToThis ? () => setConfirmingChange(p) : undefined}
                        switchLabel={isUpgrade ? 'بدّل إلى هذه' : 'جدولة التبديل عند التجديد'}
                        switching={changeBusy && confirmingChange?.id === p.id}
                        statusLabel={statusLabel}
                        statusTone={statusTone}
                        cancelLabel="إيقاف تجديد الاشتراك"
                        onCancel={isBaseSubRow && action(catalog, 'billing.cancel')
                          ? () => setConfirmingCancel(true) : undefined}
                        cancelPending={isBaseSubRow && Boolean(baseSub?.cancel_at_period_end)}
                        cancelPendingNote={baseSub && renewalDay(baseSub.current_period_end)
                          ? `اشتراكك يعمل حتى ${renewalDay(baseSub.current_period_end)} ولن يتجدّد بعدها.`
                          : 'اشتراكك لن يتجدّد بعد نهاية الفترة الحالية.'}
                        canceling={cancelBusy}
                        switchPending={switchPending}
                        switchPendingNote={pendingPlan && renewalDay(baseSub?.current_period_end)
                          ? `سيتحوّل إلى «${pendingPlan.name}» في ${renewalDay(baseSub?.current_period_end)}، بالسعر الكامل.`
                          : pendingPlan ? `سيتحوّل إلى «${pendingPlan.name}» عند نهاية الفترة الحالية.` : undefined}
                        onCancelSwitch={switchPending && action(catalog, 'billing.cancel_scheduled_change')
                          ? () => void cancelScheduledChange() : undefined}
                        cancelingSwitch={cancelSwitchBusy}
                        onUndoCancel={isBaseSubRow && baseSub?.cancel_at_period_end && action(catalog, 'billing.undo_cancel')
                          ? () => void undoCancel(baseSub.id, 'base') : undefined}
                        undoingCancel={undoBaseCancelBusy}
                      />
                    </li>
                  );
                })}
              </ul>
            </section>
          ) : null}

          {/* THE ROWS THE LADDER HID. Seats and branches came bundled with a tier, so a two-branch
              shop that wanted nothing else had to buy a whole tier for the second branch. They are
              bought AGAIN rather than owned: each purchase adds to what he has. */}
          {capacity.length ? (
            <section className="flex flex-col gap-2">
              <h2 className="flex items-center gap-1 text-sm text-text-secondary">
                السعة
                <AssistantHint anchor="store.capacitySection" session={session} />
              </h2>
              {capacityError ? <p className="text-sm text-danger">{capacityError}</p> : null}
              <ul className="grid gap-3 grid-cols-2">
                {capacity.map((p) => {
                  const sub = capacitySubs.find((s) => s.plan_id === p.id);
                  return (
                    <li key={p.id}>
                      <CapacityAddonCard
                        plan={p}
                        sub={sub}
                        busy={capacityBusyPlanId === p.id}
                        sellable={Boolean(canSubscribe && pay?.enabled && canMintToken && hasBase !== false)}
                        unreadNote={unreadNote}
                        onBuyFirst={() => choose(p, 1)}
                        onChangeQuantity={(quantity) => sub && void changeCapacityQuantity(p, sub, quantity)}
                        onRemoveLast={() => sub && setConfirmingCancelApp({ subId: sub.id, name: p.name })}
                      />
                    </li>
                  );
                })}
              </ul>
            </section>
          ) : null}
        </div>
      ) : null}

      {/* ── THE APPS, BELOW BOTH, FULL WIDTH ───────────────────────────────────────────────
          A SHELF, NOT A HALF-COLUMN. These are what he is actually choosing between, so they get
          the screen's full width to lay out three and four across instead of competing for a
          half-width column beside the base. */}
      {apps.length ? (
        <section className="flex flex-col gap-2">
          <h2 className="flex items-center gap-1 text-sm text-text-secondary">
            التطبيقات
            <AssistantHint anchor="store.appsSection" session={session} />
          </h2>
          {/* AN APP NEEDS THE BASE UNDER IT — said once, here, rather than discovered as a refusal
              after he presses. operations refuses the pair regardless; this is so he never meets
              that refusal. EXCEPT a `plan.standalone` row (e.g. بوت خدمة العملاء الذكي) — the one
              app sold with no base at all, so the note beneath it is never shown and its own card
              stays purchasable regardless of `hasBase`. */}
          {hasBase === false && apps.some((p) => !isStandalone(p)) ? (
            <p className="text-sm text-text-secondary">تُضاف إلى الاشتراك الأساسي بعد تفعيله.</p>
          ) : null}
          <ul className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
            {apps.map((p) => {
              // «كل تطبيق له إدارة اشتراكه الخاص» — an app cancels
              // independently of every other app and of the base; only the reverse (base takes
              // every app with it) is automatic. Matched by which subscription it IS, same rule
              // as `baseSub` above.
              const appSub = appSubs.find((s) => s.plan_id === p.id);
              // TRIAL, SAID PLAINLY — same honesty the base card just got (screenshot). An app
              // subscription defaults to "trialing" the same way the base's does; without this
              // it read as the same flat «مفعّل» a fully-paying app gets, which is a different
              // fact he needs to know before the trial ends and the first real charge lands.
              const appStatusLabel = appSub?.status === 'trialing' ? 'تجريبي' : undefined;
              // `plan.requires_any` — an INDEPENDENT gate from the base-required rule just above:
              // an app can need both. Empty when the plan declares no dependency, when the read
              // has not settled, or when the dependency is already satisfied.
              const lockedNote = missingRequirement(p, owned);
              return (
                <li key={p.id}>
                  <AppCard
                    plan={p}
                    session={session}
                    owned={owns(owned ?? null, appKey(p))}
                    busy={busy}
                    sellable={Boolean(canSubscribe && pay?.enabled && canMintToken
                                     && (hasBase !== false || isStandalone(p)) && !lockedNote)}
                    onBuy={() => choose(p)}
                    unreadNote={unreadNote}
                    lockedNote={lockedNote}
                    ownedLabel="مفعّل"
                    statusLabel={appStatusLabel}
                    statusTone={appStatusLabel ? 'success' : undefined}
                    buyLabel="أضِفه"
                    renewsAt={answer?.apps.find((a) => a.key === appKey(p))?.renews_at ?? null}
                    cancelLabel="إيقاف تجديد هذا التطبيق"
                    cancelPending={appSub?.cancel_at_period_end}
                    onCancel={appSub && action(catalog, 'billing.cancel')
                      ? () => setConfirmingCancelApp({ subId: appSub.id, name: p.name }) : undefined}
                    canceling={cancelingAppId === appSub?.id}
                    onUndoCancel={appSub?.cancel_at_period_end && action(catalog, 'billing.undo_cancel')
                      ? () => void undoCancel(appSub.id, 'app') : undefined}
                    undoingCancel={undoingAppCancelId === appSub?.id}
                  />
                </li>
              );
            })}
          </ul>
        </section>
      ) : null}

    </div>
  );
}
