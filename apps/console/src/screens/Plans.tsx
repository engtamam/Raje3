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
import { canMintToken, mintPaymentToken, NO_CARD_FORM } from '../payment';
import { useEffect, useState } from 'react';
import { Badge } from '@base-ui/design-system/Badge';
import { Button } from '@base-ui/design-system/Button';
import { Skeleton } from '@base-ui/design-system/Skeleton';
import { Check } from 'lucide-react';
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
export interface Subscription { id: string; plan_id?: string; plan_name?: string; status?: string; period_end?: number }

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

function PlanCard({
  plan, owned, busy, sellable, onBuy, ownedLabel, buyLabel,
}: {
  plan: Plan;
  /** true · false · null while the answer has not arrived or billing could not be asked. */
  owned: boolean | null;
  busy: boolean;
  sellable: boolean;
  onBuy: () => void;
  ownedLabel: string;
  buyLabel: string;
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
  return (
    <article
      className={[
        'group relative flex h-full flex-col gap-3 overflow-hidden rounded-card p-5',
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
        <h3 className="text-base font-medium leading-tight">{plan.name}</h3>
        {has && ownedLabel ? <Badge tone="success">{ownedLabel}</Badge> : null}
      </header>

      {/* WHAT IT DOES FOR HIM. The one line that does the selling. */}
      {app?.what ? (
        <p className="text-sm leading-relaxed text-text-secondary">{app.what}</p>
      ) : null}

      {price?.amount_minor ? (
        <div className="flex items-baseline gap-1.5">
          <span className="text-3xl font-semibold tabular-nums leading-none">
            {riyals(price.amount_minor)}
          </span>
          <span className="text-sm text-text-secondary">ريال / شهر</span>
        </div>
      ) : null}
      {/* SAID, NOT ASSUMED — the server's own flag. A shop owner reading a price without it
          budgets the wrong number. */}
      {price?.includes_tax ? (
        <span className="-mt-2 text-xs text-text-secondary">شامل ضريبة القيمة المضافة</span>
      ) : null}

      {lines.length ? (
        <ul className="flex flex-col gap-1 border-t border-border-subtle pt-3 text-sm">
          {lines.map((line) => (
            <li key={line} className="flex items-start gap-2 text-text-secondary">
              <Check size={15} className="mt-0.5 shrink-0 text-accent" aria-hidden />
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
        {has ? null : (
          <Button type="button" disabled={busy || !sellable} onClick={onBuy}>
            {buyLabel}
          </Button>
        )}
        {/* THE THIRD STATE, SAID RATHER THAN GUESSED. While the answer has not arrived — or when
            billing could not be asked — the card claims neither. Telling a paying shop it has not
            paid is worse than telling it to wait a moment. */}
        {owned === null ? (
          <p className="mt-2 text-xs text-text-secondary">جارٍ التحقق من اشتراكك…</p>
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
  const [sub, setSub] = useState<Subscription | null | undefined>(undefined);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  /** What the server says is still owed after a successful subscription. Never an error. */
  const [notice, setNotice] = useState('');
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
        .then((x) => setSub(x.subscriptions?.[0] ?? null))
        .catch(() => setSub(null));
    } else {
      setSub(null);
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

  const choose = async (p: Plan) => {
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
    setBusy(true);
    try {
      const payment_token = await mintPaymentToken();
      const out = await call<{ notice?: string }>(session, canSubscribe,
                                                 { plan_id: p.id, payment_token });
      // THE SERVER'S SENTENCE, NOT OURS. What is still owed after a successful subscription is a
      // product rule and it lives in one place; a second copy here is the one that goes stale.
      setNotice(out?.notice ?? '');
      load();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'تعذّر تفعيل الباقة.');
    } finally {
      setBusy(false);
    }
  };

  // ── GROUPED BY WHAT A ROW GRANTS, never by its name or its position in a list ─────────────
  // This is what makes the next app free to add: invoicing and CRM arrive as rows in the price
  // list and land in the right section without a line here.
  const bases = plans?.filter((p) => kindOf(p) === 'base') ?? [];
  const apps = plans?.filter((p) => kindOf(p) === 'app') ?? [];
  const capacity = plans?.filter((p) => kindOf(p) === 'capacity') ?? [];
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
  const renews = answer?.base?.renews_at
    ? new Date(answer.base.renews_at * 1000).toLocaleDateString('ar-SA-u-nu-latn-ca-gregory',
                                                               { day: 'numeric', month: 'long' })
    : '';

  if (plans === null || sub === undefined) {
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
        <div className="rounded-card bg-surface-1 p-4 shadow-sm">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <span>
              {hasBase === false
                ? 'لا اشتراك أساسي بعد'
                : `اشتراكك: الأساس${ownedApps > 0 ? ` + ${ownedApps} تطبيقات` : ''}`}
              {/* WHEN IT RENEWS — the first question an owner opens this screen with, and one a
                  boolean flag could never answer. It arrives on the subscription row itself. */}
              {renews ? <span className="text-text-secondary"> · يتجدّد {renews}</span> : null}
            </span>
            <Badge tone={sub.status === 'active' ? 'success' : 'warning'}>
              {sub.status === 'active' ? 'فعّال' : 'متوقف'}
            </Badge>
          </div>
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

      {/* ── THE THREE OF THEM IN ONE LOOK ──────────────────────────────────────────────────
          ONE DECISION, NOT THREE PAGES. Stacked full-width, «السعة» sat below two other sections
          and an owner who wanted a second branch had to scroll past everything he already had to
          learn a second branch was for sale. Two columns on a wide screen: what he pays for and
          what he can add to it on one side, the apps that plug into it on the other. Below `lg`
          it falls back to the same stack, because on a phone there is no beside. */}
      <div className="grid gap-4 lg:grid-cols-2 lg:items-start">
        <div className="flex flex-col gap-4">
        {/* ── 1 · the base ─────────────────────────────────────────────────────────────────── */}
        {bases.length ? (
          <section className="flex flex-col gap-2">
            <h2 className="text-sm text-text-secondary">الاشتراك الأساسي</h2>
            {/* HALF THE WIDTH, ON THE SAME GRID AS THE APPS BELOW IT. Full-bleed, the base card alone
                was taller than the fold and pushed «السعة» off the screen entirely — he had to scroll
                to learn that a second branch is for sale. The three sections are one decision. */}
            <ul className="grid gap-3 md:grid-cols-2">
              {bases.map((p) => (
                <li key={p.id}>
                  <PlanCard
                    plan={p}
                    owned={hasBase}
                    busy={busy}
                    sellable={Boolean(canSubscribe && pay?.enabled)}
                    onBuy={() => choose(p)}
                    ownedLabel="اشتراكك"
                    buyLabel="فعّل الأساس"
                  />
                </li>
              ))}
            </ul>
          </section>
        ) : null}

        {/* ── 3 · capacity ────────────────────────────────────────────────────────────────────
            THE TWO ROWS THE LADDER HID. Seats and branches came bundled with a tier, so a
            two-branch shop that wanted nothing else had to buy a whole tier for the second branch.
            They are bought AGAIN rather than owned: each purchase adds to what he has. */}
        {capacity.length ? (
          <section className="flex flex-col gap-2">
            <h2 className="text-sm text-text-secondary">السعة</h2>
            {/* THREE UP, BECAUSE THERE IS ALMOST NOTHING TO READ. A capacity row carries one feature
                line — «فروع: 1» — so a half-width card is mostly empty space, and empty space here
                costs the height that «السعة» needs to be visible at all. */}
            <ul className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {capacity.map((p) => (
                <li key={p.id}>
                  <PlanCard
                    plan={p}
                    owned={false}
                    busy={busy}
                    sellable={Boolean(canSubscribe && pay?.enabled && hasBase !== false)}
                    onBuy={() => choose(p)}
                    ownedLabel=""
                    buyLabel="أضِف"
                  />
                </li>
              ))}
            </ul>
          </section>
        ) : null}
        </div>
        {/* ── 2 · the apps ─────────────────────────────────────────────────────────────────── */}
        {apps.length ? (
          <section className="flex flex-col gap-2">
            <h2 className="text-sm text-text-secondary">التطبيقات</h2>
            {/* AN APP NEEDS THE BASE UNDER IT — said once, here, rather than discovered as a refusal
                after he presses. operations refuses the pair regardless; this is so he never meets
                that refusal. */}
            {hasBase === false ? (
              <p className="text-sm text-text-secondary">تُضاف إلى الاشتراك الأساسي بعد تفعيله.</p>
            ) : null}
            <ul className="grid gap-3 md:grid-cols-2">
              {apps.map((p) => (
                <li key={p.id}>
                  <PlanCard
                    plan={p}
                    owned={owns(owned ?? null, appKey(p))}
                    busy={busy}
                    sellable={Boolean(canSubscribe && pay?.enabled && hasBase !== false)}
                    onBuy={() => choose(p)}
                    ownedLabel="مفعّل"
                    buyLabel="أضِفه"
                  />
                </li>
              ))}
            </ul>
          </section>
        ) : null}
      </div>

    </div>
  );
}
