/**
 * «الاشتراك» — the plans, what each one actually buys, and the one door that must open first.
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
 * rather than printed as itself. That is deliberate — a plan that lists a line nobody understands
 * is worse at selling than a plan that lists one line fewer.
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
import { Badge } from '@base-ui/design-system/Badge';
import { Button } from '@base-ui/design-system/Button';
import { Skeleton } from '@base-ui/design-system/Skeleton';
import {
  CalendarClock, Check, Gift, Layers, Megaphone, Sparkles, type LucideIcon,
} from 'lucide-react';
import { action, call, type Catalog } from '../catalog';
import { isReady, type Loading } from '../loading';
import { APP_ROWS, owns, type Owned } from '../apps';
import type { Session } from '../session';
import { riyals } from '../money';

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
  /** Seconds on the wire — the model's real field name is `current_period_end`; `period_end` here
   *  was declared and never actually read by anything in this file. */
  current_period_end?: number;
  /** True once he has asked to leave — the subscription still serves him until the date above,
   *  and nothing charges again after it. */
  cancel_at_period_end?: boolean;
}

/**
 * One sentence per limit key, and a plan says only what we can say plainly.
 *
 * `gauge` counts things that exist at once (seats, branches); `counter` counts events inside a
 * period; `boolean` is a capability that is on or off. The renderer below reads `kind` rather than
 * guessing from the key, so a new gauge needs a sentence here and nothing else.
 */
const LIMIT_WORDS: Record<string, { label: string; unit?: string }> = {
  'staff.seats': { label: 'مقاعد للموظفين', unit: 'مقعد' },
  branches: { label: 'فروع', unit: 'فرع' },
  'messages.monthly': { label: 'رسائل في الشهر', unit: 'رسالة' },
  'templates.custom': { label: 'قوالب خاصة بك', unit: 'قالب' },
  'feature.loyalty': { label: 'نقاط ومكافآت' },
  'feature.campaigns': { label: 'حملات على شرائح عملائك' },
  'feature.insights.engine': { label: 'فرصي: أين الفرصة في محلّك' },
  'feature.api': { label: 'ربط برمجي مع أنظمتك' },
  // SOLD, NOT BUILT YET (ci/check_entitlements.py's SOLD_UNBUILT). The plan itself carries
  // `listed: false`, so this sentence never actually renders a card — it exists so the wording
  // is ready the day the plan flips to listed, not written under launch pressure.
  'feature.bookings': { label: 'نظام الحجوزات ومواعيد العملاء' },
  // THE BASE ITSELF, and it has a sentence for the same reason every other key does: it is
  // charged for, so the page where he decides must name it. «سجلّ الزيارات» rather than «الأساس»
  // — the card is already titled الأساس, and repeating the title tells him nothing about what
  // the money buys.
  'feature.base': { label: 'سجلّ الزيارات والتذكيرات' },
};

// Halalas on the wire, riyals on the screen — see money.ts. This rounded to whole riyals, so a
// plan at 9950 was advertised as «100 ريال»: fifty halalas above what we charge, on the screen
// whose only job is to state the price before he agrees to it.

function monthly(p: Plan): Price | undefined {
  return p.prices?.find((x) => x.interval === 'month') ?? p.prices?.[0];
}

/** Cheapest first — the order is the server's numbers, never a hand-kept list. */
function ordered(plans: Plan[]): Plan[] {
  return [...plans].sort((a, b) => (monthly(a)?.amount_minor ?? 0) - (monthly(b)?.amount_minor ?? 0));
}

/**
 * The readable lines for one plan.
 *
 * A `boolean` at 0 is omitted rather than rendered as «لا»: a list of what a plan does NOT do,
 * printed under its price, reads as a warning label. The comparison between plans comes from the
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

/**
 * WHAT KIND OF THING IS THIS ROW — read off its limits, never off its name.
 *
 * A NAME WOULD PUT THE PRICE LIST IN TWO PLACES, and the copy in code is the one that goes stale
 * the day marketing renames a row. A plan IS a base when it carries the message meter; it is an
 * app when it turns a feature on; it is capacity when all it carries is seats or branches.
 *
 * `limit: 0` IS A DECLARED DENY, not a grant. The base carries every app at 0 so no screen has to
 * tell «not bought» from «never heard of» — read as grants, the base would look like everything.
 */
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
 * shop; «هذه في باقة أعلى» is a fact about us, and only one of them makes anybody buy. It comes
 * from the app registry — the same file the locks read — so the shop is never told one thing here
 * and another where the lock is drawn.
 *
 * AND THE LIMITS ARE STILL THE SERVER'S. The lines under the price are the plan's own `limits`,
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


function PlanCard({
  plan, owned, busy, sellable, onBuy, ownedLabel, buyLabel, renewsAt, unreadNote, compact,
  onSwitch, switchLabel, switching,
}: {
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
  /** CAPACITY ROWS ONLY. One feature line and a price is the whole card — the base's own padding
   *  and icon size read as empty space around that little, not as room to breathe. */
  compact?: boolean;
  /** BASE TIERS ONLY (audit #5, 2026-08-22) — given instead of `onBuy` when he already owns a
   *  DIFFERENT base. Buying a second base subscribes him twice; this is the one card state that
   *  means «تبديل», not «شراء». */
  onSwitch?: () => void;
  switchLabel?: string;
  switching?: boolean;
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
        'transition-shadow duration-200',
        has
          // OWNED READS AS SETTLED, NOT AS SOLD. A ring rather than a fill: a card he already owns
          // must not compete for attention with the ones he might buy.
          ? 'bg-surface-1 shadow-sm ring-1 ring-accent-soft'
          : 'bg-surface-1 shadow-sm hover:shadow-md',
      ].join(' ')}
    >
      {/* A HAIRLINE OF ACCENT ALONG THE TOP of what he owns — the whole decoration budget of this
          screen. Anything louder turns a shop into an advertisement. */}
      {has ? <span aria-hidden className="absolute inset-x-0 top-0 h-0.5 bg-accent" /> : null}

      <header className="flex items-start justify-between gap-2">
        <div className={compact ? 'flex items-center gap-1.5' : 'flex items-center gap-2.5'}>
          {/* THE FACE OF THE APP, NOT DECORATION FOR ITS OWN SAKE — the same icon this app wears
              in the rail once he owns it, so the card that sells «الحجوزات» and the row it lands
              on afterward are visibly the same thing. Capacity rows carry no app icon of their
              own (they grant seats or branches, not a feature), so this is skipped there —
              a generic Layers badge beside «10 مقاعد إضافية» would say nothing true. */}
          {compact ? null : (
            <span
              aria-hidden
              className={[
                'grid h-9 w-9 shrink-0 place-items-center rounded-full',
                has ? 'bg-accent-soft text-accent-on-soft' : 'bg-surface-2 text-text-secondary',
              ].join(' ')}
            >
              <Icon size={17} />
            </span>
          )}
          <h3 className={compact ? 'text-sm font-medium leading-tight' : 'text-base font-medium leading-tight'}>
            {plan.name}
          </h3>
        </div>
        {has && ownedLabel ? <Badge tone="success">{ownedLabel}</Badge> : null}
      </header>

      {/* THE DAY THIS ONE IS CHARGED. Only when he owns it and billing answered — an app he has
          not bought has no date, and an unread billing has none to print. */}
      {has && renewalDay(renewsAt) ? (
        <p className="-mt-1 text-xs text-text-secondary">يتجدّد في {renewalDay(renewsAt)}</p>
      ) : null}

      {/* WHAT IT DOES FOR HIM. The one line that does the selling. */}
      {app?.what ? (
        <p className="text-sm leading-relaxed text-text-secondary">{app.what}</p>
      ) : null}

      {price?.amount_minor ? (
        <div className="flex items-baseline gap-1.5">
          <span className={compact
            ? 'text-xl font-semibold tabular-nums leading-none'
            : 'text-3xl font-semibold tabular-nums leading-none'}>
            {riyals(price.amount_minor)}
          </span>
          <span className="text-sm text-text-secondary">ريال / شهر</span>
        </div>
      ) : null}
      {/* SAID, NOT ASSUMED — the server's own flag. A shop owner reading a price without it
          budgets the wrong number. Skipped in the compact card: a capacity row's tax note would
          be the longest line on a card whose whole point is to stay short. */}
      {price?.includes_tax && !compact ? (
        <span className="-mt-2 text-xs text-text-secondary">شامل ضريبة القيمة المضافة</span>
      ) : null}

      {lines.length ? (
        <ul className={compact
          ? 'flex flex-col gap-1 border-t border-border-subtle pt-2 text-xs'
          : 'flex flex-col gap-1 border-t border-border-subtle pt-3 text-sm'}>
          {lines.map((line) => (
            <li key={line} className="flex items-start gap-2 text-text-secondary">
              <Check size={compact ? 12 : 15} className="mt-0.5 shrink-0 text-accent" aria-hidden />
              <span>{line}</span>
            </li>
          ))}
        </ul>
      ) : null}

      {/* WHERE IT SHOWS UP, because «اشتريته وين ألقاه؟» is the first support question after every
          purchase — and the answer is already written down in the registry. */}
      {app?.section ? (
        <p className="text-xs text-text-secondary">
          يظهر في «{SECTION_LABEL[app.section] ?? app.section}»
        </p>
      ) : null}

      <div className="mt-auto pt-2">
        {has ? null : onSwitch ? (
          <Button type="button" variant="outline" disabled={busy || switching} onClick={onSwitch}>
            {switching ? 'يُبدَّل…' : switchLabel}
          </Button>
        ) : (
          <Button type="button" disabled={busy || !sellable} onClick={onBuy}>
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
      </div>
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
   *  `error` above: those belong to BUYING, and a cancel in flight must not grey out every plan
   *  card on the screen as if a purchase were happening. */
  const [confirmingCancel, setConfirmingCancel] = useState(false);
  const [cancelBusy, setCancelBusy] = useState(false);
  const [cancelError, setCancelError] = useState('');
  /** THE CARD FORM, OPEN FOR ONE OF TWO REASONS — buying a plan, or replacing the card on the
   *  base subscription. `null` is closed; it is not a screen of its own, same as `reading` on
   *  «رسائلي». Which reason decides what a resolved token is handed to next. */
  const [cardFormPending, setCardFormPending] = useState<PendingPayment | null>(null);
  /** True only while resolving a token AFTER the 3DS redirect brought him back — a distinct wait
   *  from `busy`, because there is no form and no button to grey out at that moment. */
  const [resolvingReturn, setResolvingReturn] = useState(false);
  /** «بدّل الباقة» (audit #5) — its own dialog, its own busy flag, its own error, same reasoning
   *  as cancel's: switching in flight must not grey out the whole plan grid. */
  const [confirmingChange, setConfirmingChange] = useState<Plan | null>(null);
  const [changeBusy, setChangeBusy] = useState(false);
  const [changeError, setChangeError] = useState('');
  /** Its own banner, not `notice` — that one is titled «تم الاشتراك ✓» and offers «اربط واتسابي
   *  الآن», neither of which is true of a plan SWITCH on an already-connected shop. */
  const [changeNotice, setChangeNotice] = useState('');
  /**
   * WHETHER THERE IS A LIVE WAY TO PAY AT ALL — asked, never assumed.
   *
   * With no gateway configured this screen was a shop with no till: every press wrote «باقتك» over
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
  const cancelBase = async () => {
    const a = action(catalog, 'billing.cancel');
    if (!a || !baseSub) return;
    setCancelBusy(true); setCancelError('');
    try {
      await call(session, a, { id: baseSub.id });
      setConfirmingCancel(false);
      load();
    } catch (e) {
      setCancelError(e instanceof Error ? e.message : 'تعذّر إلغاء الاشتراك.');
    } finally {
      setCancelBusy(false);
    }
  };

  /** «بدّل الباقة» (audit #5) — THE ACTION THAT DID NOT EXIST. billing-service's `/change` route is
   *  whole, proration and all; nothing in this console ever called it, so switching base tiers
   *  meant a second «شراء» — a second subscription rather than a swap. The switch takes effect
   *  immediately (his entitlements move to the new plan's limits the moment this returns).
   *
   *  THE PRORATION FIGURE IS NOW A REAL PROMISE (escalated as a follow-up finding, fixed
   *  upstream v0.16.32 — billing_service.change_plan used to compute the delta and discard it;
   *  it now accumulates as `pending_adjustment_minor` and folds into the NEXT invoice, VAT
   *  included, with credit carried forward if it exceeds one cycle). So this says «سيُضاف
   *  لفاتورتك القادمة» / «سيُخصم من فاتورتك القادمة» — an actual statement about what happens,
   *  not the hedge it had to be while the backend only reported the number. */
  const changeBase = async () => {
    const a = action(catalog, 'billing.change_plan');
    if (!a || !baseSub || !confirmingChange) return;
    setChangeBusy(true); setChangeError('');
    try {
      const out = await call<{ proration_minor?: number }>(
        session, a, { id: baseSub.id, plan_id: confirmingChange.id });
      setConfirmingChange(null);
      const d = out?.proration_minor;
      setChangeNotice(
        typeof d === 'number' && d !== 0
          ? `تم تبديل باقتك إلى «${confirmingChange.name}». ${
              d > 0 ? `سيُضاف ${riyals(d)} ريال لفاتورتك القادمة` : `سيُخصم ${riyals(Math.abs(d))} ريال من فاتورتك القادمة`
            } — فرق سعر بقية هذه الفترة.`
          : `تم تبديل باقتك إلى «${confirmingChange.name}».`);
      load();
    } catch (e) {
      setChangeError(e instanceof Error ? e.message : 'تعذّر تبديل الباقة.');
    } finally {
      setChangeBusy(false);
    }
  };

  useEffect(() => {
    const a = action(catalog, 'subscription.payment_state');
    if (!a) { setPay({ enabled: false, message: '' }); return; }
    call<{ enabled: boolean; message?: string }>(session, a)
      .then(setPay)
      // A FAILED READ IS NOT AN OPEN TILL. Erring the other way sells a plan nobody can charge for.
      .catch(() => setPay({ enabled: false, message: '' }));
  }, [session, catalog]);

  useEffect(load, [session, catalog]);   // eslint-disable-line react-hooks/exhaustive-deps

  // OPENS THE CARD FORM RATHER THAN MINTING INLINE. Tokenising is no longer one call an owner
  // never sees — it is a real form, and almost always a full redirect to his bank's own 3DS page
  // and back (see payment.ts). `choose` only decides WHETHER a card is needed at all; the form
  // and the redirect-return effect below do the rest.
  const choose = (p: Plan) => {
    setError('');
    // NOT GATED ON THE CONNECTION ANY MORE — see the module note. Only on having the action at
    // all, which is a capability question and not a readiness one.
    // NOT WHILE THE TILL IS SHUT. The press is still remembered — his choice is not lost — but
    // nothing is written and no plan starts.
    // AND NOT WITHOUT A TOKEN WE CAN ACTUALLY MINT (د-15). `pay.enabled` answers «is there a
    // gateway key», which is a different question from «can this browser hand back a card
    // token». The screen used to press on regardless, posting `{ plan_id }` alone, and every
    // paid row came back 402 — a live-looking button that could never work, while the base
    // slipped through only because its trial skips the check.
    if (!canSubscribe) return;
    if (!canBuy({ hasAction: true, gatewayEnabled: Boolean(pay?.enabled),
                 canMint: canMintToken })) return;
    setCardFormPending({ kind: 'subscribe', planId: p.id });
  };

  /** The purchase itself, once a token exists — reached either straight from the form (a card
   *  that skipped 3DS) or from the redirect-return effect below (the ordinary case). */
  const finishSubscribe = async (planId: string, payment_token: string) => {
    if (!canSubscribe) return;
    setBusy(true); setError('');
    try {
      const out = await call<{ notice?: string }>(session, canSubscribe,
                                                 { plan_id: planId, payment_token });
      // THE SERVER'S SENTENCE, NOT OURS. What is still owed after a successful subscription is a
      // product rule and it lives in one place; a second copy here is the one that goes stale.
      setNotice(out?.notice ?? '');
      setCardFormPending(null);
      load();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'تعذّر تفعيل الباقة.');
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
        if (pending.kind === 'subscribe') return finishSubscribe(pending.planId, result.token);
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
  // by position: `subs[0]` is whichever row billing happened to return first (the same bug the
  // summary line below was already rewritten to avoid), and an app row bought after the base would
  // have been cancelled instead of the base itself.
  const sub = subs?.[0];
  const baseSub = (subs ?? []).find((s) => bases.some((p) => p.id === s.plan_id));
  // FOUR ANSWERS NOW, and none of them is «he has not bought». The read may be in flight
  // (`undefined`), have failed (`null`), be one his role cannot make (DENIED), or have arrived
  // with `checked: false` because billing itself could not be asked. The sections claim nothing
  // in every one of those cases — telling a paying shop it has not paid is the mistake this pane
  // exists to avoid.
  const answer = isReady(owned) ? owned : null;
  const hasBase = !answer || !answer.checked ? null : Boolean(answer.base);
  // Counted off the answer, not off the rows: a subscription list can hold a lapsed row, and what
  // he OWNS is the only number that matches the badges on the cards below.
  const ownedApps = apps.filter((p) => owns(owned, appKey(p)) === true).length;
  // WESTERN DIGITS AND A GREGORIAN MONTH, like every other date in this product. Seconds on the
  // wire — the row's `current_period_end` — and a day a person can plan around on the screen.
  const renews = renewalDay(answer?.base?.renews_at);
  // EVERY APP RENEWS ON ITS OWN DAY, because billing starts each subscription's period at the
  // moment it was bought. A shop that added «الحملات» two weeks after the base is charged twice a
  // month on two days; until now the screen printed the base's day and said nothing about the
  // rest, so the second charge arrived unannounced. One billing day for the whole shop, with the
  // first cycle prorated, is billing-service's `subscribe` to fix (#347) — it is read-only to us.
  // Saying the truth we already hold is not.
  const appDays = distinctRenewalDays(answer);
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
      {/* ── WHAT HE HAS, IN ONE LINE ────────────────────────────────────────────────────────
          THIS USED TO NAME `subscriptions[0]` and call it «باقتك الحالية». With a base and apps
          bought one by one a shop holds SEVERAL subscriptions, and the first row is whichever one
          billing happened to return first — so an owner paying for four things could open this
          screen and read «باقتك الحالية «الحملات»». It is a summary now, counted from what he
          owns rather than from a row.

          AND IT COUNTS THE APPS RATHER THAN LISTING THEM: each one is a card below, badged
          «مفعّل», and repeating the names here would be the same list twice on one screen. */}
      {sub ? (
        <div className="flex flex-col gap-3 rounded-card bg-surface-1 p-4 shadow-sm">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <span>
              {hasBase === false
                ? 'لا اشتراك أساسي بعد'
                : `اشتراكك: الأساس${ownedApps > 0 ? ` + ${ownedApps} تطبيقات` : ''}`}
              {/* WHEN IT RENEWS — the first question an owner opens this screen with, and one a
                  boolean flag could never answer. It arrives on the subscription row itself. */}
              {renews ? <span className="text-text-secondary"> · يتجدّد {renews}</span> : null}
            </span>
            {/* AND WHEN THEY ARE NOT ALL ON ONE DAY, said here rather than discovered on the card
                statement. The date on each card answers «متى يُخصم هذا»; this answers «كم مرة
                يُخصم مني في الشهر», which is the question an owner actually has. */}
            {appDays.size > 1 ? (
              <p className="w-full text-xs text-text-secondary">
                تطبيقاتك تتجدّد في {appDays.size} تواريخ مختلفة — كلٌّ في يوم شرائه.
              </p>
            ) : null}
            {/* FOUR STATES NOW, SAID PLAINLY — «متأخر الدفع» is the honest fourth (audit #3,
                2026-08-22). Before this the screen only ever read `sub.status === 'active'` as
                «فعّال» and printed «متوقف» for everything else, including `past_due` — the one
                state where he is still being SERVED but a charge is failing behind the scenes,
                said in the exact word the product used for "he cancelled and it already ended".
                An owner reading «متوقف» had no reason to think a card needed fixing. */}
            <Badge tone={baseSub?.cancel_at_period_end ? 'warning'
              : sub.status === 'past_due' ? 'danger'
              : sub.status === 'active' ? 'success' : 'warning'}>
              {baseSub?.cancel_at_period_end ? 'قيد الإلغاء'
                : sub.status === 'past_due' ? 'متأخر الدفع'
                : sub.status === 'active' ? 'فعّال' : 'متوقف'}
            </Badge>
          </div>

          {/* WHY IT IS متأخر, AND WHAT TO DO ABOUT IT — the sentence «متوقف» never had. */}
          {sub.status === 'past_due' ? (
            <p className="text-sm text-danger">
              آخر محاولة سحب لم تنجح. حدّث بطاقتك حتى لا يتوقف اشتراكك.
            </p>
          ) : null}

          <div className="flex flex-wrap gap-2">
            {/* «إلغاء الاشتراك» — THE ACTION THAT DID NOT EXIST (audit #2, 2026-08-22). The backend
                route was complete and reachable; nothing in this console ever called it, so a
                customer wanting to leave had no self-service path at all. Shown only for the BASE
                — cancelling an app is a downgrade (a different, separate gap: #5), not a departure. */}
            {baseSub && action(catalog, 'billing.cancel') ? (
              baseSub.cancel_at_period_end ? (
                <p className="text-sm text-text-secondary">
                  {renewalDay(baseSub.current_period_end)
                    ? `اشتراكك يعمل حتى ${renewalDay(baseSub.current_period_end)} ولن يتجدّد بعدها.`
                    : 'اشتراكك لن يتجدّد بعد نهاية الفترة الحالية.'}
                </p>
              ) : (
                <Button type="button" variant="ghost" onClick={() => setConfirmingCancel(true)}>
                  إلغاء الاشتراك
                </Button>
              )
            ) : null}

            {/* «تحديث بطاقة الدفع» — audit #3's other half, the one that closes the involuntary-
                churn loop: `dunning_sweep` on the backend keeps retrying the SAME stored token
                forever, and this was the only way that token could ever change. Reachable only
                once `billing.update_payment_method` exists in the catalogue AND this build can
                actually mint a token (`canMintToken` — false until Ops sets the Moyasar
                publishable key) — never rendered-and-refused. */}
            {baseSub && action(catalog, 'billing.update_payment_method') && canMintToken ? (
              <Button type="button" variant="ghost"
                      onClick={() => setCardFormPending({ kind: 'update_payment_method',
                                                          subscriptionId: baseSub.id })}>
                تحديث بطاقة الدفع
              </Button>
            ) : null}
          </div>
        </div>
      ) : null}

      {/* THE CARD FORM — subscribing to a paid plan, or replacing the card on the base. Shown
          inline rather than in a modal: it is a full-page redirect away and back on the ordinary
          path (3DS), and a modal that survives that round trip is a modal fighting its own DOM. */}
      {cardFormPending ? (
        <CardForm
          pending={cardFormPending}
          onCancel={() => setCardFormPending(null)}
          onToken={(token) => {
            if (cardFormPending.kind === 'subscribe') void finishSubscribe(cardFormPending.planId, token);
            else void finishUpdatePaymentMethod(cardFormPending.subscriptionId, token);
          }}
        />
      ) : null}

      {resolvingReturn ? (
        <p className="text-sm text-text-secondary">نتحقق من بطاقتك…</p>
      ) : null}

      {/* THE CONFIRMATION — never a silent press. He is ending a paid relationship, and the one
          thing he must know before he presses again is that nothing is taken from him: the shop
          keeps working exactly as it does today, until the day already printed above. */}
      {confirmingCancel && baseSub ? (
        <div className="rounded-card border border-border-subtle bg-surface-1 p-5 shadow-sm">
          <p className="mb-1 font-medium">تأكيد إلغاء الاشتراك</p>
          <p className="mb-4 text-sm text-text-secondary">
            {renewalDay(baseSub.current_period_end)
              ? `يستمر محلّك يعمل بلا أي تغيير حتى ${renewalDay(baseSub.current_period_end)}، ولن يتجدّد الاشتراك بعدها. لن نخصم منك شيئاً إضافياً.`
              : 'يستمر محلّك يعمل بلا أي تغيير حتى نهاية الفترة التي دفعت عنها، ولن يتجدّد الاشتراك بعدها.'}
          </p>
          {cancelError ? <p className="mb-3 text-sm text-danger">{cancelError}</p> : null}
          <div className="flex gap-2">
            <Button type="button" variant="danger" disabled={cancelBusy} onClick={() => void cancelBase()}>
              تأكيد الإلغاء
            </Button>
            <Button type="button" variant="ghost" disabled={cancelBusy}
                    onClick={() => { setConfirmingCancel(false); setCancelError(''); }}>
              تراجع
            </Button>
          </div>
        </div>
      ) : null}

      {/* «بدّل الباقة» CONFIRMATION — same discipline as cancel's: he is changing what he pays,
          and the one thing he must know before pressing again is that the new limits apply
          immediately, and what the price difference for the rest of THIS period is computed as.
          THE FIGURE IS SAID AS COMPUTED, NOT PROMISED — billing_service.change_plan works out
          the number and hands it back without writing it to any invoice; a sentence claiming it
          «will be added to your next bill» would be a promise the backend does not keep today. */}
      {confirmingChange ? (
        <div className="rounded-card border border-border-subtle bg-surface-1 p-5 shadow-sm">
          <p className="mb-1 font-medium">تأكيد التبديل إلى «{confirmingChange.name}»</p>
          <p className="mb-4 text-sm text-text-secondary">
            حدود باقتك الجديدة تسري فوراً. فرق السعر لبقية هذه الفترة يُحتسب تناسبياً ويظهر في فاتورتك القادمة.
          </p>
          {changeError ? <p className="mb-3 text-sm text-danger">{changeError}</p> : null}
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

      {changeNotice ? (
        <div className="rounded-card border border-accent-soft bg-accent-soft/40 p-5 shadow-sm">
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
        <div className="rounded-card border border-accent-soft bg-accent-soft/40 p-5 shadow-sm">
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
              <h2 className="text-sm text-text-secondary">الاشتراك الأساسي</h2>
              <ul className="grid gap-3">
                {bases.map((p) => {
                  // WHICH BASE, NOT JUST WHETHER ONE — `hasBase` alone used to mark EVERY base
                  // card «owned» the moment he had any one of them (audit #5's other half of the
                  // same bug: a shop on the cheap tier saw every tier badged as already his).
                  const isThisOne = hasBase === true ? baseSub?.plan_id === p.id : hasBase;
                  // UPGRADES ONLY, FOR NOW (Tamam, 2026-08-22): «مافي رصيد سالب أو استرداد — لو
                  // نزّل باقته يكمل الفترة إلى أن تخلص، مثل المنصات العالمية». billing-service's
                  // change_plan (even after v0.16.32) switches and credits IMMEDIATELY on a
                  // downgrade — exactly the negative-balance shape the product does not want.
                  // Offering the button for a cheaper plan would let a shop trigger that credit
                  // path today; hidden here until base-services builds the effective-at-period-
                  // end downgrade this needs (escalated separately) — an upgrade's delta is
                  // always ≥ 0, so that half is safe to offer as-is.
                  const currentBase = bases.find((b) => b.id === baseSub?.plan_id);
                  const isUpgrade = (monthly(p)?.amount_minor ?? 0)
                    >= (currentBase ? monthly(currentBase)?.amount_minor ?? 0 : 0);
                  const canSwitchToThis = hasBase === true && !isThisOne && isUpgrade
                    && Boolean(action(catalog, 'billing.change_plan'));
                  return (
                    <li key={p.id}>
                      <PlanCard
                        plan={p}
                        owned={isThisOne}
                        busy={busy}
                        sellable={Boolean(canSubscribe && pay?.enabled)}
                        onBuy={() => choose(p)}
                        unreadNote={unreadNote}
                        ownedLabel="اشتراكك"
                        buyLabel="فعّل الأساس"
                        onSwitch={canSwitchToThis ? () => setConfirmingChange(p) : undefined}
                        switchLabel="بدّل إلى هذه"
                        switching={changeBusy && confirmingChange?.id === p.id}
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
              <h2 className="text-sm text-text-secondary">السعة</h2>
              <ul className="grid gap-3 grid-cols-2">
                {capacity.map((p) => (
                  <li key={p.id}>
                    <PlanCard
                      plan={p}
                      owned={false}
                      busy={busy}
                      sellable={Boolean(canSubscribe && pay?.enabled && hasBase !== false)}
                      onBuy={() => choose(p)}
                      unreadNote={unreadNote}
                      ownedLabel=""
                      buyLabel="أضِف"
                      compact
                    />
                  </li>
                ))}
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
          <h2 className="text-sm text-text-secondary">التطبيقات</h2>
          {/* AN APP NEEDS THE BASE UNDER IT — said once, here, rather than discovered as a refusal
              after he presses. operations refuses the pair regardless; this is so he never meets
              that refusal. */}
          {hasBase === false ? (
            <p className="text-sm text-text-secondary">تُضاف إلى الاشتراك الأساسي بعد تفعيله.</p>
          ) : null}
          <ul className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
            {apps.map((p) => (
              <li key={p.id}>
                <PlanCard
                  plan={p}
                  owned={owns(owned ?? null, appKey(p))}
                  busy={busy}
                  sellable={Boolean(canSubscribe && pay?.enabled && hasBase !== false)}
                  onBuy={() => choose(p)}
                  unreadNote={unreadNote}
                  ownedLabel="مفعّل"
                  buyLabel="أضِفه"
                  renewsAt={answer?.apps.find((a) => a.key === appKey(p))?.renews_at ?? null}
                />
              </li>
            ))}
          </ul>
        </section>
      ) : null}

    </div>
  );
}
