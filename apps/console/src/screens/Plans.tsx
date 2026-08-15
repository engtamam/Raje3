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
import { useEffect, useState } from 'react';
import { Badge } from '@base-ui/design-system/Badge';
import { Button } from '@base-ui/design-system/Button';
import { Skeleton } from '@base-ui/design-system/Skeleton';
import { action, call, type Catalog } from '../catalog';
import type { Session } from '../session';

interface Price { type?: string; currency?: string; interval?: string; amount_minor?: number; includes_tax?: boolean }
interface Limit { kind?: string; limit?: number; period?: string; overage?: string }
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
  'feature.insights.engine': { label: 'محرّك المؤشرات والتوصيات' },
  'feature.api': { label: 'ربط برمجي مع أنظمتك' },
  // NOT AN APP, AND STILL WORDED HERE. `feature.base` is how the purchase rules answer «هل عنده
  // اشتراك أساسي؟» — billing has no route that lists a shop's subscriptions. It appears on the
  // base's own card as what that card IS, and a key with no sentence is silently not rendered.
  'feature.base': { label: 'الأساس: عملاؤك وزياراتهم وتذكيرهم' },
};

/** Halalas on the wire, riyals on the screen. Western digits, always. */
function riyals(minor: number): string {
  const whole = Math.round(minor / 100);
  return String(whole);
}

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
    const n = lim.limit ?? 0;
    if (lim.kind === 'boolean') {
      if (n > 0) out.push(words.label);
      continue;
    }
    // -1 IS UNLIMITED IN THIS SERVICE, not an error and not zero. Printing «-1 رسالة» once got as
    // far as a screenshot.
    if (n < 0) out.push(`${words.label}: بلا حد`);
    else if (n > 0) out.push(`${words.label}: ${n}`);
  }
  return out;
}

/**
 * What this plan adds over the one below it — and nothing it merely repeats.
 *
 * FOUR PLANS THAT SHARE MOST OF THEIR LIST make the reader do the diffing: he reads twenty lines
 * to find the three that changed, and the thing he is actually buying — the difference — is the
 * one thing the screen never says out loud. «كل ما في الأساسية +» says it in four words.
 *
 * A LINE SURVIVES ONLY IF ITS VALUE CHANGED. Comparing whole sentences is what makes this safe:
 * «مقاعد للموظفين: 5» and «مقاعد للموظفين: 12» are different strings, so the seat increase shows;
 * an identical line is inherited and stays quiet.
 *
 * AND THE FIRST PLAN KEEPS ITS FULL LIST, because there is nothing beneath it to inherit from.
 */
export function planDelta(plan: Plan, below: Plan | undefined): string[] {
  const lines = planLines(plan);
  if (!below) return lines;
  const had = new Set(planLines(below));
  return lines.filter((l) => !had.has(l));
}

export function PlansPane({
  session, catalog, connected, onGoConnect,
}: {
  session: Session;
  catalog: Catalog;
  /** Whether his WhatsApp number is linked — the condition a plan cannot run without. */
  connected: boolean;
  /** Takes him to the connection pane. Passed in, because this pane does not own the navigation. */
  onGoConnect: () => void;
}) {
  const [plans, setPlans] = useState<Plan[] | null>(null);
  const [sub, setSub] = useState<Subscription | null | undefined>(undefined);
  const [chosen, setChosen] = useState<Plan | null>(null);
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
        .catch(() => setPlans([]));
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
    // THE ORDER, AND IT IS ANSWERED RATHER THAN REFUSED. See the module note: his choice is kept
    // and the screen shows him the step that makes it work.
    setChosen(p);
    // NOT GATED ON THE CONNECTION ANY MORE — see the module note. Only on having the action at
    // all, which is a capability question and not a readiness one.
    // NOT WHILE THE TILL IS SHUT. The press is still remembered — his choice is not lost — but
    // nothing is written and no plan starts.
    if (!canSubscribe || !pay?.enabled) return;
    setBusy(true);
    try {
      const out = await call<{ notice?: string }>(session, canSubscribe, { plan_id: p.id });
      // THE SERVER'S SENTENCE, NOT OURS. What is still owed after a successful subscription is a
      // product rule and it lives in one place; a second copy here is the one that goes stale.
      setNotice(out?.notice ?? '');
      setChosen(null);
      load();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'تعذّر تفعيل الباقة.');
    } finally {
      setBusy(false);
    }
  };

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
      {sub ? (
        <div className="rounded-card bg-surface-1 p-4 shadow-sm">
          <div className="flex items-center justify-between">
            <span>باقتك الحالية «{sub.plan_name ?? '—'}»</span>
            <Badge tone={sub.status === 'active' ? 'success' : 'warning'}>
              {sub.status === 'active' ? 'فعّالة' : 'متوقفة'}
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

      {/* SIDE BY SIDE ON A PHONE, NOT STACKED. Four plans in a column are compared from memory:
          by the time he reaches «المتقدّمة» the price of «الأساسية» is off the screen and he is
          scrolling back and forth to hold two numbers in his head. A snapping row puts them next
          to each other at a thumb's swipe, which is the comparison this screen exists to make.
          The grid returns at md, where three fit without either. */}
      <ul className="flex snap-x snap-mandatory gap-3 overflow-x-auto pb-2 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden [&>li]:w-[80%] [&>li]:shrink-0 [&>li]:snap-start md:grid md:grid-cols-3 md:overflow-visible md:[&>li]:w-auto">
        {plans.map((p) => {
          const price = monthly(p);
          const current = sub?.plan_id === p.id || sub?.plan_name === p.name;
          return (
            <li key={p.id}>
              <div
                className={[
                  // TIGHTER, BECAUSE THE CARD IS THE COMPARISON. p-5 with gap-3 spread four
                  // short facts over a screen and a half, so «الأساسية» and «الذكية» could not be
                  // read against each other without scrolling — which is the one thing this
                  // screen is for. The tax line joins the price instead of taking a row.
                  'flex h-full flex-col gap-2 rounded-card p-4 shadow-sm',
                  current ? 'bg-accent-soft text-accent-on-soft' : 'bg-surface-1',
                ].join(' ')}
              >
                <div className="flex items-baseline justify-between">
                  <span className="text-lg font-medium">{p.name}</span>
                  {current ? <Badge tone="success">باقتك</Badge> : null}
                </div>
                {price?.amount_minor ? (
                  <div className="flex items-baseline gap-1">
                    <span className="text-2xl font-semibold tabular-nums">{riyals(price.amount_minor)}</span>
                    <span className="text-sm text-text-secondary">ريال / شهر</span>
                  </div>
                ) : null}
                {/* SAID, NOT ASSUMED. «شامل الضريبة» is the server's flag; a shop owner reading a
                    price without it budgets the wrong number. */}
                {price?.includes_tax ? (
                  <span className="-mt-1 text-xs text-text-secondary">شامل ضريبة القيمة المضافة</span>
                ) : null}
                <ul className="flex flex-col gap-0.5 text-sm leading-snug">
                  {/* THE INHERITANCE, SAID ONCE. The plans arrive cheapest first, so the one below
                      is the previous entry — and naming it is what makes the short list read as
                      "more" rather than as "less". */}
                  {plans[plans.indexOf(p) - 1] ? (
                    <li className="font-medium">
                      كل ما في «{plans[plans.indexOf(p) - 1].name}» +
                    </li>
                  ) : null}
                  {planDelta(p, plans[plans.indexOf(p) - 1]).map((line) => (
                    <li key={line} className="text-text-secondary">• {line}</li>
                  ))}
                </ul>
                <div className="mt-auto pt-1">
                  {current ? null : (
                    <Button type="button" disabled={busy} onClick={() => choose(p)}>
                      اختر هذه الباقة
                    </Button>
                  )}
                </div>
              </div>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
