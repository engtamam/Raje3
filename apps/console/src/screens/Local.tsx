/**
 * «محلّي» — the indicators, and the one section that sells the plan.
 *
 * IT WAS BUILT LAST ON PURPOSE. Every other section answers a question the owner already had;
 * this one hands him questions he did not know to ask, and it is only worth reading once the
 * visits behind it are real.
 *
 * THREE SENTENCES THIS SCREEN MUST KEEP APART, because mixing any two tells him to fix something
 * he cannot:
 *
 *   computing      — we have not finished the first pass. Not an empty shop.
 *   not_enabled    — the data is too thin, and there IS something he can do about it.
 *   absent         — his plan does not include it, so nothing is rendered at all (§8.6.1).
 *
 * The server already draws these lines. The screen renders `values` as it arrives and never
 * substitutes a zero for a missing key: a key that is not there is not a zero, and painting one
 * turns "you have not bought this" into "your shop is dead".
 *
 * AND THE AGE IS ALWAYS SHOWN. An owner comparing our number to his till at 2pm must see that
 * ours was computed at 3am, or he stops trusting both.
 */
import { useEffect, useState } from 'react';
import { Badge } from '@base-ui/design-system/Badge';
import { EmptyState } from '@base-ui/design-system/EmptyState';
import { KpiCard } from '@base-ui/design-system/KpiCard';
import { Ring } from '@base-ui/design-system/Ring';
import { TrendingUp, Users, RefreshCw, AlertTriangle } from 'lucide-react';
import { Waiting } from '../Waiting';
import { action, call, type Catalog } from '../catalog';
import type { Session } from '../session';

interface Blocked { indicator: string; message?: string; reason?: string }
/** Visits credited to a message, and stops per thousand — what the engine moved, and what it cost. */
interface Effect { visits?: number; window_days?: number }
interface OptOut { ready?: boolean; rate?: number; per?: number; sent?: number; need?: number; opt_outs?: number }
/** The two groups: what the tenth we leave alone did, against what everyone else did. */
interface Holdout {
  ready?: boolean; reason?: string; held?: number; reached?: number; need?: number;
  held_rate?: number; reached_rate?: number; gap?: number; window_days?: number;
}
/** The return rate as a line — one point a month, `null` where the window held too few people. */
interface Series {
  points?: { at: number; customers: number; value: number | null }[];
  learning?: boolean; first?: number; last?: number; delta?: number; months?: number;
}
interface Dashboard {
  computing: boolean;
  message?: string;
  values: Record<string, unknown>;
  audience?: { consented: number; message: string } | null;
  as_of_hours_ago?: number;
  stale?: boolean;
  visits?: number;
  not_enabled?: Blocked[];
  teaser?: { message?: string } | null;
}

/** The headline four, by the names the snapshot stores them under. */
const HEADLINE: {
  key: string; label: string; icon: typeof Users; percent?: boolean; suffix?: string;
  tone?: 'neutral' | 'accent' | 'success' | 'warning' | 'danger';
}[] = [
  // return_rate is rendered as the ring above — it stays in this list so the "absent is not zero"
  // rule keeps one home, and the grid filters it out rather than a second list drifting from this.
  { key: 'return_rate', label: 'نسبة العودة', icon: RefreshCw, percent: true },
  { key: 'active_customers', label: 'عملاء نشطون', icon: Users, tone: 'accent' },
  { key: 'return_cycle_days', label: 'دورة العودة', icon: TrendingUp, suffix: 'يوماً' },
  // THE ONLY ONE WHERE A RISE IS BAD, and the only one wearing a warning colour. Painting all four
  // the same taught the eye that none of them mattered.
  { key: 'churn_rate', label: 'التسرّب', icon: AlertTriangle, percent: true, tone: 'warning' },
];

/** Two services that arrive together, and how sure the engine is. */
interface Pairs {
  learning?: boolean;
  have?: number;
  need?: number;
  pairs?: { a: string; b: string; verdict: string; customers: number }[];
}

/** A bundle the shop could offer. WE SAY WHERE, NEVER HOW MUCH — the price is his (§10.6.2.1). */
interface Bundle {
  a_name?: string; b_name?: string; why?: string;
  customers?: number; action?: string; action_label?: string;
}

interface Branches {
  rows?: { branch_id?: string; name?: string; visits?: number; customers?: number }[];
  unknown?: number;
  can_rank?: boolean;
}

/**
 * A GROUP, AND NOT A TAB — the decision this screen turns on.
 *
 * It was one long scroll where a branch table and a suggested bundle carried the same weight, met
 * in the order we happened to build them. Tabs were the obvious fix and the wrong one: a tab hides
 * what he did not think to ask for, and the two most valuable things here — the bundle worth 340
 * customers, and pairs he has never noticed — are exactly what nobody opens a tab to look for.
 *
 * So: three groups on one page, ordered by DECISION rather than subject. What needs him now, then
 * how the shop is doing, then detail folded away one press from open. Folded, not absent —
 * `<details>` keeps it in the page, in find-in-page, and in the reading order.
 */

/**
 * THE TREND, DRAWN SMALL AND SAID IN WORDS.
 *
 * A shop owner does not read charts, and this is not one: it is a line the width of the card with
 * a sentence under it — «كان 20% · صار 60%» — because the sentence is what he repeats to himself
 * and the line is only what makes him believe it.
 *
 * A GAP IS A GAP, NEVER A ZERO. A window with too few customers in it produces `null`, and the
 * path breaks there. Painting it at zero would say «nobody came back that month», which is a
 * different and much worse sentence than «we do not know».
 *
 * NO AXES, NO GRID, NO TOOLTIP. Every one of those would ask him to study the picture, and the
 * moment a number needs studying he stops reading it.
 */
function Trend({ series }: { series: Series }) {
  const pts = (series.points ?? []).map((p) => p.value);
  const drawn = pts.filter((v): v is number => typeof v === 'number');
  if (drawn.length < 2) return null;

  const W = 260, H = 44, PAD = 3;
  const lo = Math.min(...drawn), hi = Math.max(...drawn);
  const span = hi - lo || 1;
  const x = (i: number) => PAD + (i * (W - PAD * 2)) / (pts.length - 1);
  const y = (v: number) => H - PAD - ((v - lo) / span) * (H - PAD * 2);

  // Segments, not one path: a break in the data must be a break in the line.
  const segs: string[] = [];
  let cur: string[] = [];
  pts.forEach((v, i) => {
    if (typeof v === 'number') cur.push(`${cur.length ? 'L' : 'M'}${x(i).toFixed(1)},${y(v).toFixed(1)}`);
    else { if (cur.length > 1) segs.push(cur.join(' ')); cur = []; }
  });
  if (cur.length > 1) segs.push(cur.join(' '));

  const up = (series.delta ?? 0) > 0;
  const flat = Math.abs(series.delta ?? 0) < 0.01;
  const stroke = flat ? 'var(--text-muted)' : up ? 'var(--success)' : 'var(--danger)';

  return (
    <div className="flex w-full flex-col items-center gap-1 px-5">
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full max-w-[280px]" role="img"
           aria-label={`الاحتفاظ: كان ${Math.round((series.first ?? 0) * 100)}% وصار ${Math.round((series.last ?? 0) * 100)}%`}>
        {segs.map((d, i) => (
          <path key={i} d={d} fill="none" stroke={stroke} strokeWidth={2.5}
                strokeLinecap="round" strokeLinejoin="round" />
        ))}
      </svg>
      <p className="text-xs text-text-secondary">
        <span className="tabular-nums">{Math.round((series.first ?? 0) * 100)}%</span>
        {' '}قبل {series.months} أشهر{' · '}
        <span className="tabular-nums font-semibold text-text-primary">
          {Math.round((series.last ?? 0) * 100)}%
        </span>{' '}اليوم
      </p>
    </div>
  );
}


/**
 * THE ONE CARD THAT IS NOT OUR WORD FOR OUR OWN WORK.
 *
 * Every other number here says how his shop is doing. This one says what we did to it, measured
 * against the tenth of his customers our engine deliberately never messages — so «هل الرسائل تنفع
 * أم تزعج؟» is answered by his data instead of by us.
 *
 * IT SAYS THE TWO RATES AND STOPS. No «راجِع رفع احتفاظك 27 نقطة», because a gap is evidence and a
 * claim is a sentence he did not write — and the day the gap is negative, a product that had been
 * boasting has nothing honest left to say. Reporting both numbers works in both directions, which
 * is the only reason to trust it in either.
 */
function HoldoutCard({ h }: { h: Holdout }) {
  if (!h?.ready) {
    // LEARNING IS A STATE, NOT AN ABSENCE — the same contract the pairs use, so the screen tells
    // one story about waiting rather than three.
    const held = h?.held ?? 0, reached = h?.reached ?? 0, need = h?.need ?? 15;
    if (!held && !reached) return null;
    return (
      <p className="rounded-card bg-surface-1 p-4 text-sm text-text-secondary shadow-sm">
        ما زلنا نقيس أثر الرسائل على محلّك — {Math.min(held, reached)} من {need} في أصغر المجموعتين.
      </p>
    );
  }
  const pct = (v?: number) => `${Math.round((v ?? 0) * 100)}%`;
  const better = (h.gap ?? 0) > 0;
  return (
    <section className="flex flex-col gap-3 rounded-card bg-surface-1 p-4 shadow-sm">
      <h3 className="text-sm font-medium">أثر الرسائل، مقيساً</h3>
      <div className="flex items-stretch gap-2">
        <div className="flex flex-1 flex-col items-center gap-0.5 rounded-xl bg-surface-2 p-3">
          <span className="text-xl font-bold tabular-nums">{pct(h.held_rate)}</span>
          <span className="text-center text-[11px] leading-tight text-text-secondary">
            بلا رسائل<br />({h.held} عميلاً)
          </span>
        </div>
        <div className={`flex flex-1 flex-col items-center gap-0.5 rounded-xl p-3 ${
          better ? 'bg-success-soft text-success-on-soft' : 'bg-surface-2'}`}>
          <span className="text-xl font-bold tabular-nums">{pct(h.reached_rate)}</span>
          <span className="text-center text-[11px] leading-tight opacity-80">
            وصلتهم رسائلك<br />({h.reached} عميلاً)
          </span>
        </div>
      </div>
      <p className="text-xs leading-relaxed text-text-secondary">
        نترك {Math.round(((h.held ?? 0) / ((h.held ?? 0) + (h.reached ?? 1))) * 100)}% من عملائك
        بلا حملات ولا عروض — لتقارن بنفسك، لا لتصدّقنا. تُوقفه من إعدادات محلّك.
      </p>
    </section>
  );
}

function Group({ title, hint, children, folded = false }: {
  title: string; hint?: string; children: React.ReactNode; folded?: boolean;
}) {
  if (folded) {
    return (
      <details className="rounded-card bg-surface-1 shadow-sm">
        <summary className="cursor-pointer list-none p-4 text-sm font-medium">
          {title}
          {hint ? <span className="mr-2 text-xs font-normal text-text-secondary">{hint}</span> : null}
        </summary>
        <div className="flex flex-col gap-3 border-t border-border-subtle p-4">{children}</div>
      </details>
    );
  }
  return (
    <section className="flex flex-col gap-3">
      <h2 className="text-sm font-medium">
        {title}
        {hint ? <span className="mr-2 text-xs font-normal text-text-secondary">{hint}</span> : null}
      </h2>
      {children}
    </section>
  );
}

export function LocalScreen({ session, catalog }: { session: Session; catalog: Catalog }) {
  const [data, setData] = useState<Dashboard | null>(null);
  const [failed, setFailed] = useState(false);
  /** Whether HE receives the weekly report. Optimistic, and reverted if the save fails. */
  const [digest, setDigest] = useState(true);
  /**
   * THE THREE PANELS THE ENGINE COMPUTES AND NOTHING RENDERED.
   *
   * `insights.associations`, `insights.bundles` and `insights.branches` were built, tested,
   * deployed and reachable by nothing — so «محلّي» showed the headline numbers and the shop never
   * saw the answers the engine exists to produce: which two services go together, which bundle to
   * suggest, and which branch is ahead.
   *
   * ABSENT WHERE THE PLAN DOES NOT INCLUDE THEM, and absent is right (§8.6.1). The gateway drops
   * the action from the catalogue, so the panel is not rendered at all rather than rendered locked
   * — the teaser line above already does the selling, once, in a sentence that is true.
   */
  const [pairs, setPairs] = useState<Pairs | null>(null);
  const [bundles, setBundles] = useState<Bundle[] | null>(null);
  const [branches, setBranches] = useState<Branches | null>(null);

  useEffect(() => {
    // EACH ONE ON ITS OWN, and a failure in one leaves the others. They are three separate
    // answers, and a shop whose branch table cannot be read should still see its pairs.
    const assoc = action(catalog, 'insights.associations');
    if (assoc) call<Pairs>(session, assoc).then(setPairs).catch(() => setPairs(null));
    const bun = action(catalog, 'insights.bundles');
    if (bun) call<{ bundles: Bundle[] }>(session, bun)
      .then((r) => setBundles(r.bundles ?? [])).catch(() => setBundles(null));
    const br = action(catalog, 'insights.branches');
    if (br) call<Branches>(session, br).then(setBranches).catch(() => setBranches(null));

    const a = action(catalog, 'insights.dashboard');
    if (!a) { setFailed(true); return; }
    call<Dashboard>(session, a).then(setData).catch(() => setFailed(true));
  }, [session, catalog]);

  if (failed) {
    return (
      <div className="p-4">
        <EmptyState title="تعذّر قراءة المؤشرات" description="حاول بعد قليل." />
      </div>
    );
  }
  // A PAGE WITH NO KNOWN SHAPE YET WAITS IN OUR OWN MARK, not as one grey rectangle —
  // see Waiting.tsx. The skeletons inside the page stay: there the shape IS known.
  if (!data) return <Waiting what="نقرأ مؤشرات محلّك" />;

  if (data.computing) {
    // NOT AN EMPTY DASHBOARD. A first-day shop that sees zeros concludes the product does not
    // work; the server sends a sentence saying the first pass is running, and we show it whole.
    return (
      <div className="p-4">
        <EmptyState title="نحسب مؤشرات محلك" description={data.message || ''} />
      </div>
    );
  }

  const digestAction = action(catalog, 'insights.digest');

  return (
    <div className="flex flex-col gap-4 p-4">
      {/* THE WEEKLY REPORT, SWITCHED HERE — and it was a severed wire until now. `insights.digest`
          was declared, served, and called by no screen: §10.6.6 promises that an optional notice
          can be switched off, and the switch existed everywhere except where a person could reach
          it. PER PERSON, deliberately (the route says so): a manager may want the report and the
          owner may not, and one flag on the establishment makes unsubscribing an act that silently
          switches a colleague off. */}
      {digestAction ? (
        <label className="flex items-center justify-between gap-3 rounded-card bg-surface-1 p-3 shadow-sm">
          <span className="flex flex-col">
            <span className="text-sm">تقريري الأسبوعي على واتساب</span>
            <span className="text-xs text-text-secondary">
              صباح الأحد — أسبوعك في تسعة أسطر، بلا فتح اللوحة. لك وحدك: إيقافه لا يوقفه عن زملائك.
            </span>
          </span>
          <input
            type="checkbox"
            checked={digest}
            aria-label="تقريري الأسبوعي على واتساب"
            onChange={async (e) => {
              const on = e.target.checked;
              setDigest(on);
              // THE SWITCH FOLLOWS THE SERVER, NOT THE OTHER WAY ROUND. A failed save that leaves
              // the box ticked teaches him he is subscribed when he is not — and he finds out by
              // a report that never comes.
              await call(session, digestAction, { on }).catch(() => setDigest(!on));
            }}
            className="size-6 shrink-0 accent-[var(--accent)]"
          />
        </label>
      ) : null}

      {/* ── 1 · what needs him now ───────────────────────────────────────────────────────
          FIRST, BECAUSE IT IS THE ONLY GROUP WITH A VERB IN IT. A suggested bundle naming 340
          customers is worth more than every percentage below it, and it used to sit under two
          tables he had to scroll past. */}
      <Group title="يحتاج تصرّفاً منك">
      {/* ── the bundles ───────────────────────────────────────────────────────────────────
            WE SAY WHERE, NEVER HOW MUCH (§10.6.2.1). The price is the shop's and nothing here
            suggests one — a platform that prices a workshop's work is a platform that is wrong in
            public. */}
        {bundles && bundles.length ? (
          <section className="flex flex-col gap-2 rounded-card bg-surface-1 p-4 shadow-sm">
            <h2 className="text-sm text-text-secondary">باقات مقترحة</h2>
            {bundles.slice(0, 4).map((b, i) => (
              <div key={i} className="flex flex-col gap-1 border-t border-border-subtle pt-2 first:border-0 first:pt-0">
                <span className="text-sm font-medium">{b.a_name} + {b.b_name}</span>
                {b.why ? <span className="text-xs text-text-secondary">{b.why}</span> : null}
                <div className="flex items-center justify-between gap-2">
                  {b.action_label ? (
                    <span className="text-xs text-accent-on-soft">{b.action_label}</span>
                  ) : <span />}
                  <span className="tabular-nums text-xs text-text-secondary">
                    {b.customers} فرصة
                  </span>
                </div>
              </div>
            ))}
          </section>
        ) : null}

      {data.audience ? (
          // HIS OWN NUMBER, NOT AN ADVERT. Customers who explicitly agreed to receive his offers,
          // sitting there while his plan cannot send one. It is the truest upgrade motivator in the
          // product for exactly that reason, so it stays a LINE and never becomes a banner.
          <p className="rounded-card bg-surface-1 p-4 text-sm shadow-sm">{data.audience.message}</p>
        ) : null}

      </Group>

      {/* ── 2 · how the shop is doing ─────────────────────────────────────────────────────
          THE AGE STAYS ATTACHED TO THE NUMBERS IT DESCRIBES. An owner comparing our figure to his
          till at 2pm must see that ours was computed at 3am, or he stops trusting both — and a
          freshness line floating above three sections describes none of them. */}
      <Group
        title="كيف يمشي محلك"
        hint={data.as_of_hours_ago === 0 ? 'محسوبة الآن' : `محسوبة قبل ${data.as_of_hours_ago} ساعة`}
      >
      {data.stale ? <Badge tone="warning">قديمة</Badge> : null}

      {/* ── ONE NUMBER, LARGE ────────────────────────────────────────────────────────────────
          FOUR EQUAL TILES ARE FOUR NUMBERS NOBODY REMEMBERS. On a phone they became two rows of
          small type with no order between them, and the owner left knowing none of them.
          نسبة العودة is the one this whole product is about, so it is a jewel at the top and the
          rest are its supporting cast. The ring animates from zero on mount and respects
          prefers-reduced-motion — the kit's own behaviour, not a flourish added here. */}
      {typeof data.values['return_rate'] === 'number' ? (
        <div className="flex flex-col items-center gap-1 rounded-card border border-border-subtle bg-surface-1 py-7 shadow-sm">
          <Ring
            value={Math.round((data.values['return_rate'] as number) * 100)}
            size={148}
            stroke={11}
            caption="نسبة العودة"
          />
          <p className="px-6 text-center text-xs leading-relaxed text-text-secondary">
            من عملائك رجعوا لك مرة ثانية.
          </p>
          {/* AND WHETHER IT IS MOVING — the question the ring alone cannot answer, and the one he
              is actually asking when he decides whether to keep paying. */}
          {(() => {
            const series = data.values['retention_series'] as Series | undefined;
            return series && !series.learning ? <Trend series={series} /> : null;
          })()}
        </div>
      ) : null}

      {(() => {
        const h = data.values['holdout_comparison'] as Holdout | undefined;
        return h ? <HoldoutCard h={h} /> : null;
      })()}

      {/* ── what the messages moved, and what they cost ───────────────────────────────────────
          TWO SENTENCES, SIDE BY SIDE, AND NEITHER IS A BOAST. The first is a COUNT of visits and
          not a percentage: every honest denominator (people messaged? due? alive?) is arguable,
          and a count is not. He multiplies by the average bill only he knows — we hold no prices
          and never will.

          The second is the one that protects him from us: stops per thousand messages, rising
          before a number is blocked. A blocked number does not lose a message, it loses the
          channel for every customer of the shop, for good. */}
      {(() => {
        const eff = data.values['returned_after_reminder'] as Effect | undefined;
        const opt = data.values['opt_out_rate'] as OptOut | undefined;
        if (!eff && !opt) return null;
        return (
          <div className="grid grid-cols-2 gap-2">
            {eff ? (
              <div className="flex flex-col gap-0.5 rounded-card bg-surface-1 p-4 shadow-sm">
                <span className="text-2xl font-bold tabular-nums text-accent-on-soft">
                  {eff.visits ?? 0}
                </span>
                <span className="text-xs leading-relaxed text-text-secondary">
                  زيارة عادت بعد رسالة، خلال {eff.window_days ?? 30} يوماً
                </span>
              </div>
            ) : null}
            {opt ? (
              <div className="flex flex-col gap-0.5 rounded-card bg-surface-1 p-4 shadow-sm">
                {opt.ready ? (
                  <>
                    <span className={`text-2xl font-bold tabular-nums ${
                      (opt.rate ?? 0) > 20 ? 'text-warning-on-soft' : 'text-text-primary'}`}>
                      {opt.rate}
                    </span>
                    <span className="text-xs leading-relaxed text-text-secondary">
                      إيقافاً لكل ألف رسالة{(opt.rate ?? 0) > 20 ? ' — راجع حملاتك' : ''}
                    </span>
                  </>
                ) : (
                  <span className="text-xs leading-relaxed text-text-secondary">
                    نقيس الإزعاج بعد {opt.need ?? 200} رسالة — أرسلت {opt.sent ?? 0}.
                  </span>
                )}
              </div>
            ) : null}
          </div>
        );
      })()}
      <div className="grid grid-cols-3 gap-2">
        {HEADLINE.filter((h) => h.key !== 'return_rate').map((h) => {
          const raw = data.values[h.key];
          // ABSENT IS NOT ZERO. A key his plan withheld, or one the snapshot could not compute, is
          // skipped entirely rather than rendered as 0 — see the module note.
          if (typeof raw !== 'number') return null;
          const shown = h.percent ? `${Math.round(raw * 100)}%` : String(raw);
          return (
            <KpiCard
              key={h.key}
              icon={<h.icon size={16} />}
              tone={h.tone}
              label={h.label}
              value={h.suffix ? `${shown} ${h.suffix}` : shown}
            />
          );
        })}
      </div>
      </Group>

      {/* ── 3 · the detail, folded ─────────────────────────────────────────────────────────
          FOLDED, NOT REMOVED. Pairs, branches and the indicators still too thin to be honest are
          all worth reading — once, when he is looking for them — and none of them is worth the
          top of the screen every time he opens it. */}
      <Group title="تفاصيل أكثر" hint="ما يُطلب معاً · فروعك · ما ينقصه بيانات" folded>
      {data.not_enabled && data.not_enabled.length > 0 ? (
        <section className="rounded-card bg-surface-1 p-4 shadow-sm">
          <h2 className="mb-2 text-sm text-text-secondary">مؤشرات تحتاج بيانات أكثر</h2>
          {/* SHOW THE GAP, SILENCE ONLY THE CLAIM. These are indicators whose inputs are too thin
              to be honest yet — and every one of them names something he can do to close it. */}
          <ul className="flex flex-col gap-2">
            {data.not_enabled.map((b) => (
              <li key={b.indicator} className="text-sm">{b.message || b.reason}</li>
            ))}
          </ul>
        </section>
      ) : null}

      {/* ── what goes with what ───────────────────────────────────────────────────────────
          A PAIR IS NOT ADVICE UNTIL IT IS EXPLAINED. Each row carries the engine's own sentence,
          because «غيار زيت + فلتر» with no reason is a coincidence the owner has to trust us
          about — and the one thing he cannot check is the one thing he will not act on. */}
      {pairs && !pairs.learning && (pairs.pairs ?? []).length ? (
        <section className="flex flex-col gap-2 rounded-card bg-surface-1 p-4 shadow-sm">
          <h2 className="text-sm text-text-secondary">ما يُطلب معاً</h2>
          {(pairs.pairs ?? []).slice(0, 6).map((p) => (
            <div key={`${p.a}|${p.b}`} className="flex items-center justify-between gap-3 border-t border-border-subtle pt-2 first:border-0 first:pt-0">
              <span className="text-sm">{p.a} + {p.b}</span>
              <span className="tabular-nums text-xs text-text-secondary">{p.customers} عميلاً</span>
            </div>
          ))}
        </section>
      ) : null}

      {/* STILL LEARNING IS A STATE, NOT AN ABSENCE. A shop three weeks old has no pairs because it
          has no history, and saying so — with the count it still needs — is the difference between
          a product that is working and one that looks broken. */}
      {pairs?.learning ? (
        <p className="rounded-card bg-surface-1 p-4 text-sm text-text-secondary shadow-sm">
          ما زلنا نتعلّم ما يُطلب معاً في محلّك — {pairs.have ?? 0} زيارة من {pairs.need ?? 0}.
        </p>
      ) : null}

      {/* ── the branches ──────────────────────────────────────────────────────────────────
          RENDERED ONLY FOR A SHOP THAT HAS MORE THAN ONE. A comparison table with one row is a
          table about nothing, and `can_rank` is the server saying whether the comparison is even
          fair yet — a branch opened last week does not lose to one open three years. */}
      {branches && (branches.rows ?? []).length > 1 ? (
        <section className="flex flex-col gap-2 rounded-card bg-surface-1 p-4 shadow-sm">
          <h2 className="text-sm text-text-secondary">فروعك</h2>
          {(branches.rows ?? []).map((r, i) => (
            <div key={r.branch_id || i} className="flex items-center justify-between gap-3 border-t border-border-subtle pt-2 first:border-0 first:pt-0">
              <span className="text-sm">{r.name || r.branch_id || 'بلا اسم'}</span>
              <span className="tabular-nums text-xs text-text-secondary">
                {r.visits ?? 0} زيارة · {r.customers ?? 0} عميلاً
              </span>
            </div>
          ))}
          {branches.unknown ? (
            // THE UNSPECIFIED ROW IS SHOWN, NOT HIDDEN. Visits recorded without a branch belong to
            // somebody, and a table that silently drops them makes every branch look smaller.
            <p className="text-xs text-text-secondary">
              {branches.unknown} زيارة بلا فرع محدَّد — لا تُحتسب لأي فرع.
            </p>
          ) : null}
          {branches.can_rank === false ? (
            <p className="text-xs text-text-secondary">
              لا نرتّب الفروع بعد — الفترة قصيرة، والمقارنة الآن تظلم الأحدث.
            </p>
          ) : null}
        </section>
      ) : null}

      </Group>

      {data.teaser?.message ? (
        <p className="rounded-card bg-surface-1 p-4 text-sm shadow-sm">{data.teaser.message}</p>
      ) : null}
    </div>
  );
}
