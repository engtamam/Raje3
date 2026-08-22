/**
 * «محلّي» — rebuilt as one file (2026-08-22, Tamam: "نصمم بطريقتنا الاحترافية... ملف واحد مخصص
 * بالكامل"). Replaces Today.tsx + Local.tsx + this file's own old three-line shell.
 *
 * OUR OWN PRESENTATION, NOT THE SPEC'S TAXONOMY. docs/وصف-منصة-راجع.md groups indicators into five
 * named categories (retention, cross-sell, segmentation, operational efficiency, staff) — that
 * grouping is a content inventory, not a design a phone screen should render as five boxes. What
 * decides layout here is urgency and depth, not which document section a number came from: what
 * stops the shop, then the one number the whole product is about, then what surrounds it, then
 * what he might act on, then everything else — folded, never hidden.
 *
 * ONE FILE, NOT ONE COMPONENT. Every section below still keeps its OWN fetch and its OWN three
 * states (loading/failed/ready) — `reminders.today` can be unreachable while `insights.dashboard`
 * answers perfectly, and collapsing them into one shared loading state would throw away a working
 * retention rate because a different service briefly is not answering. See each section's own hook.
 *
 * A NEW VISUAL IDENTITY, SCOPED TO THIS SCREEN ONLY. The rest of the console still reads
 * `var(--rj-gold)` etc. from the shared theme; this screen defines its own local tokens on its own
 * root element (violet/teal/coral — see the comment on `TOKENS` below) rather than touching the
 * platform-wide palette, which stays a separate decision for a separate day.
 */
import { useEffect, useMemo, useState, type CSSProperties } from 'react';
import { Button } from '@base-ui/design-system/Button';
import { EmptyState } from '@base-ui/design-system/EmptyState';
import { Skeleton } from '@base-ui/design-system/Skeleton';
import type { ShellContext } from '../shell-context';
import { Link, useOutletContext } from 'react-router-dom';
import { hasFailed, isLoading, isReady } from '../loading';
import { Waiting } from '../Waiting';
import { ApiError, sentenceFor } from '../api';
import { action, call, type Catalog } from '../catalog';
import type { Session } from '../session';
import { asLocal } from '../phone';
import { outsideVisits } from '../branch-scope';

export { outsideVisits };

/** This screen's own palette — violet/teal/coral on a cool near-white ground, nothing beige,
 *  nothing borrowed from the platform's gold. Applied once, on the outer wrapper, and read by
 *  every child via `var(--sh-*)` the same way the rest of the console already reads `--rj-*`. */
const TOKENS: CSSProperties = {
  ['--sh-ground' as string]: '#f4f5fa',
  ['--sh-surface' as string]: '#ffffff',
  ['--sh-surface-2' as string]: '#eceefa',
  ['--sh-ink' as string]: '#131226',
  ['--sh-ink-soft' as string]: '#5a5a78',
  ['--sh-ink-faint' as string]: '#9797ad',
  ['--sh-line' as string]: '#e5e6f2',
  ['--sh-violet' as string]: '#6a4cf5',
  ['--sh-violet-deep' as string]: '#4c34c4',
  ['--sh-violet-soft' as string]: '#ece7fe',
  ['--sh-teal' as string]: '#0fb897',
  ['--sh-teal-deep' as string]: '#0a8871',
  ['--sh-teal-soft' as string]: '#dcf7f1',
  ['--sh-coral' as string]: '#ff6b52',
  ['--sh-coral-deep' as string]: '#d9472f',
  ['--sh-coral-soft' as string]: '#ffe4dd',
  background: 'var(--sh-ground)',
  color: 'var(--sh-ink)',
};

/* ── shared shapes, unchanged from the services that answer them ─────────────────────────────── */
interface Today {
  can_send?: boolean;
  blocked?: string;
  messages: { sent_today: number; waiting: number; retrying?: number; retrying_reason?: string };
  ceiling: { known: boolean; unlimited: boolean; limit: number; reached_today: number;
            remaining: number; quality: string };
}
interface CustomerRow { id: string; phone: string; name?: string }
interface Blocked {
  indicator: string; lost?: string; why?: string; do?: string; owner?: string; request?: string;
  progress?: { have?: number; need?: number };
}
const BLOCKED_OWNER: Record<string, string> = {
  pos_vendor: 'على مزوّد الكاشير', establishment: 'عليك أنت', time: 'على الوقت', unknown: 'غير محدّد',
};
interface Effect { ready?: boolean; reason?: string; visits?: number; window_days?: number; partial?: boolean }
interface OptOut {
  ready?: boolean; reason?: string; rate?: number; per?: number; sent?: number; need?: number;
  opt_outs?: number; partial?: boolean;
}
interface Holdout {
  ready?: boolean; reason?: string; held?: number; reached?: number; need?: number;
  held_rate?: number; reached_rate?: number; gap?: number; window_days?: number;
}
interface Series {
  points?: { at: number; customers: number; value: number | null }[];
  learning?: boolean; first?: number; last?: number; delta?: number; months?: number;
}
interface Dashboard {
  computing: boolean; empty_branch?: boolean; message?: string; values: Record<string, unknown>;
  audience?: { consented: number; message: string } | null; as_of_hours_ago?: number;
  entitlements?: string[]; stale?: boolean; visits?: number; not_enabled?: Blocked[];
  teaser?: { message?: string } | null;
}
interface Pairs { learning?: boolean; have?: number; need?: number;
                 pairs?: { a: string; b: string; verdict: string; customers: number }[] }
interface Bundle { a_name?: string; b_name?: string; why?: string; customers?: number;
                  action?: string; action_label?: string }
interface Branches { rows?: { branch_id?: string; name?: string; visits?: number; customers?: number }[];
                    unknown?: number; can_rank?: boolean }
interface WeekWindow { visits: number; previous: number | null; window_days: number }
interface AtRiskRow { subject_ref: string; days_overdue: number; own_cycle_days: number; visits: number }
interface CustomerHitLite { id: string; phone: string; name?: string; subject_ref?: string }

export function blockedSentence(b: Blocked): string {
  const why = (b.why ?? '').trim();
  if (!why) return '';
  const have = b.progress?.have, need = b.progress?.need;
  if (typeof have === 'number' && typeof need === 'number' && need > 0) return `${why} — ${have} من ${need}.`;
  return why;
}

/* ── the whole screen ──────────────────────────────────────────────────────────────────────────── */
export function ShopScreen() {
  const { session, catalog, branch, setBranch } = useOutletContext<ShellContext>();

  return (
    // A FIXED SIDE COLUMN WAS THE SAME MISTAKE IN A NEW SHAPE — today's pulse and the recent list
    // are short, so a rigid `[1fr_23rem]` split left a tall dead strip of the shell's own ground
    // under the short column while the wide column kept scrolling well past it. CSS multi-column
    // (inside `IndicatorsPanel`, which now also renders `RecentVisits` as one more block in its own
    // flow) balances by actual content height instead of by a column boundary picked in advance —
    // the one layout primitive built for exactly this problem. Only today's pulse — status, not a
    // number to compare — stays a plain full-width lead above it.
    //
    // `-m-4 sm:-m-6 md:-m-8` CANCELS THE SHELL'S OWN PADDING (AppShell's content wrapper carries
    // no background of its own — it just inherits the shell's ivory `bg-surface-0`), then `p-4
    // sm:p-6 md:p-8` reapplies the identical spacing as OUR OWN padding, over OUR OWN ground. Left
    // as inherited padding, that gap was a strip of the old platform's ivory framing every card on
    // every side — the seam that made a screen with a brand-new identity read as pasted onto an
    // unchanged shell rather than actually redesigned.
    <div style={TOKENS} className="-m-4 flex flex-col gap-3 p-4 sm:-m-6 sm:p-6 md:-m-8 md:p-8">
      <TodayPulse session={session} catalog={catalog} />
      <IndicatorsPanel session={session} catalog={catalog} branch={branch} onBranch={setBranch} />
    </div>
  );
}

/* ── ① what stops the shop, and today's pulse — own fetch, own three states ─────────────────────── */
export function TodayPulse({ session, catalog }: { session: Session; catalog: Catalog }) {
  const [today, setToday] = useState<Today | null | undefined>(undefined);
  const [connected, setConnected] = useState<{ state: string; message: string; can_send?: boolean } | null | undefined>(undefined);

  useEffect(() => {
    const a = action(catalog, 'reminders.today');
    if (a) call<Today>(session, a).then(setToday).catch(() => setToday(null));
    else setToday(null);
    const w = action(catalog, 'whatsapp.connect_status');
    if (w) call<{ state: string; message: string; can_send?: boolean }>(session, w)
      .then(setConnected).catch(() => {});
  }, [session, catalog]);

  const warning = (() => {
    if (connected && connected.state !== 'connected' && connected.state !== '') return connected.message;
    if (connected && connected.state === '') return 'واتساب غير مربوط — اربطه لتبدأ الرسائل. دقائق.';
    if (connected && connected.can_send === false) return 'واتساب مربوط ولم يبدأ الإرسال — أدخل رمز التحقق بخطوتين في «حسابي» لتفعيله.';
    if (today?.ceiling.known && !today.ceiling.unlimited && today.ceiling.remaining <= 0) return 'بلغت سقف واتساب اليوم. الرسائل المتبقية ستُرسل غداً تلقائياً.';
    return '';
  })();

  if (today === null) {
    return (
      <p className="rounded-2xl px-4 py-3 text-sm" style={{ background: 'var(--sh-surface)', color: 'var(--sh-ink-soft)' }}>
        تعذّرت قراءة حالة اليوم — حسابك سليم، والأرقام أدناه صحيحة.
      </p>
    );
  }
  if (today === undefined) {
    return <div className="grid gap-2 sm:grid-cols-3"><Skeleton height={68} /><Skeleton height={68} /><Skeleton height={68} /></div>;
  }

  return (
    <>
      {today.blocked ? (
        <div className="flex flex-col gap-1.5 rounded-2xl px-4 py-4 text-white"
             style={{ background: 'linear-gradient(120deg, var(--sh-coral), #ff8f5c)',
                     boxShadow: '0 10px 24px -10px rgba(255,107,82,.5)' }}>
          <div className="flex items-center gap-2 text-[15px] font-bold">
            <span className="size-2 shrink-0 rounded-full bg-white" style={{ boxShadow: '0 0 0 4px rgba(255,255,255,.3)' }} />
            رسائلك متوقّفة الآن
          </div>
          <p className="text-[13px] leading-relaxed opacity-95">{today.blocked}</p>
          <a href="/app/account" className="mt-0.5 w-fit text-[13px] font-semibold underline underline-offset-2">افتح «حسابي» ←</a>
        </div>
      ) : null}

      {(today.messages.retrying ?? 0) > 0 ? (
        <div className="flex flex-col gap-1 rounded-2xl px-4 py-3"
             style={{ background: 'var(--sh-coral-soft)', color: 'var(--sh-coral-deep)' }}>
          <span className="font-semibold text-[14px]">{today.messages.retrying} رسالة تحاول الخروج</span>
          {today.messages.retrying_reason ? <span className="text-[13px]">{today.messages.retrying_reason}</span> : null}
        </div>
      ) : null}

      {warning ? (
        <div className="rounded-2xl px-4 py-3 text-[13px]" style={{ background: '#fdf0dc', color: '#8a5a12' }}>
          {warning}
        </div>
      ) : null}

      <div className="grid grid-cols-3 gap-2">
        <Tile label="رسائل خرجت اليوم" value={String(today.messages.sent_today)} tone="violet" />
        <Tile label="بانتظار الإرسال" value={String(today.messages.waiting)} tone="flat" />
        <Tile
          label="سقفك المتبقي اليوم"
          value={!today.ceiling.known ? '—' : today.ceiling.unlimited ? 'بلا حدّ' : String(today.ceiling.remaining)}
          tone={!today.ceiling.known || today.ceiling.unlimited ? 'flat' : today.ceiling.remaining <= 0 ? 'coral' : 'teal'}
        />
      </div>
    </>
  );
}

/** No icon slot on purpose — a dot that repeats on every single tile regardless of what the tile
 *  means is decoration pretending to be information, and worse than no icon: it teaches the eye
 *  to skip it. The tone-colored number itself IS the signal; a top rule in the tone carries the
 *  same distinction an icon would have, honestly. */
function Tile({ label, value, tone, delta }: {
  label: string; value: string; tone: 'violet' | 'teal' | 'coral' | 'flat';
  /** THE COMPARISON THAT MAKES A LEVEL MEAN SOMETHING — «good» means "up from before" for most
   *  numbers, so a rising churn rate must still read as bad even though it went up. Pass
   *  `goodIsUp: false` for a tile where more is worse. Omit `delta` entirely when there is no
   *  earlier period to compare against — never render a fabricated "+0". */
  delta?: { current: number; previous: number; goodIsUp?: boolean; percent?: boolean };
}) {
  const fg = tone === 'violet' ? 'var(--sh-violet-deep)' : tone === 'teal' ? 'var(--sh-teal-deep)'
    : tone === 'coral' ? 'var(--sh-coral-deep)' : 'var(--sh-ink)';
  const rule = tone === 'violet' ? 'var(--sh-violet)' : tone === 'teal' ? 'var(--sh-teal)'
    : tone === 'coral' ? 'var(--sh-coral)' : 'var(--sh-line)';
  const diff = delta ? delta.current - delta.previous : null;
  const good = delta && diff !== null ? (delta.goodIsUp === false ? diff <= 0 : diff >= 0) : null;
  return (
    <div className="flex flex-col gap-1 rounded-2xl p-3 text-center" style={{ background: 'var(--sh-surface)', boxShadow: '0 1px 2px rgba(19,18,38,.04), 0 6px 16px -8px rgba(19,18,38,.12)', borderTop: `2.5px solid ${rule}` }}>
      <span dir="ltr" className="text-[20px] font-extrabold" style={{ color: fg, fontVariantNumeric: 'tabular-nums' }}>{value}</span>
      <span className="text-[10.5px]" style={{ color: 'var(--sh-ink-faint)' }}>{label}</span>
      {diff !== null ? (
        <span dir="ltr" className="text-[10px] font-semibold" style={{
          color: diff === 0 ? 'var(--sh-ink-faint)' : good ? 'var(--sh-teal-deep)' : 'var(--sh-coral-deep)',
          fontVariantNumeric: 'tabular-nums',
        }}>
          {diff === 0 ? '= عن الشهر اللي فات' : `${diff > 0 ? '↑' : '↓'} ${delta!.percent ? `${Math.abs(Math.round(diff * 100))}%` : Math.abs(diff)} عن الشهر اللي فات`}
        </span>
      ) : null}
    </div>
  );
}

/* ── ② the number this product is about, and everything that surrounds it ───────────────────────── */
export function IndicatorsPanel({ session, catalog, branch, onBranch }: {
  session: Session; catalog: Catalog; branch: string; onBranch: (id: string) => void;
}) {
  const [data, setData] = useState<Dashboard | null | undefined>(undefined);
  const [failed, setFailed] = useState(false);
  const [mustChoose, setMustChoose] = useState<string[]>([]);
  const [refreshing, setRefreshing] = useState(false);
  const [note, setNote] = useState('');
  const [pairs, setPairs] = useState<Pairs | null | undefined>(undefined);
  const [bundles, setBundles] = useState<Bundle[] | null | undefined>(undefined);
  const [locked, setLocked] = useState<Record<string, string>>({});
  const [branches, setBranches] = useState<Branches | null | undefined>(undefined);

  useEffect(() => {
    const br = action(catalog, 'insights.branches');
    if (br) call<Branches>(session, br).then(setBranches).catch(() => setBranches(null));
  }, [session, catalog]);

  useEffect(() => {
    const a = action(catalog, 'insights.dashboard');
    if (!a) { setFailed(true); return; }
    setMustChoose([]);
    call<Dashboard>(session, a, branch ? { branch_id: branch } : {})
      .then((d) => {
        setData(d);
        const engine = (d.entitlements ?? []).includes('feature.insights.engine');
        if (!engine) { setPairs(null); setBundles(null); return; }
        const paidRead = (id: string, key: string, take: (r: any) => void) => {
          const a2 = action(catalog, id);
          if (!a2) return;
          call<any>(session, a2).then(take).catch((e) => {
            if (e instanceof ApiError && e.status === 402) {
              setLocked((was) => ({ ...was, [key]: sentenceFor(e, 'غير مشمول بباقتك.') }));
              return;
            }
            take(null);
          });
        };
        paidRead('insights.associations', 'associations', (r) => setPairs(r));
        paidRead('insights.bundles', 'bundles', (r) => setBundles(r === null ? null : r.bundles ?? []));
      })
      .catch((e) => {
        if (e instanceof ApiError && e.status === 409 && (e.body as { error?: string } | undefined)?.error === 'MANY_BRANCHES') {
          setMustChoose((e.body as { branches?: string[] } | undefined)?.branches ?? []);
          return;
        }
        setFailed(true);
      });
  }, [session, catalog, branch]);

  if (failed) return <div className="p-4"><EmptyState title="تعذّر قراءة المؤشرات" description="حاول بعد قليل." /></div>;

  if (mustChoose.length) {
    const named = branches?.rows ?? [];
    return (
      <div className="flex flex-col items-center gap-3 p-4">
        <EmptyState title="لوحتك تغطي أكثر من فرع" description="اختر فرعاً لتقرأ مؤشراته. لوحة واحدة تجمع فروعك غير متاحة بعد." />
        <div className="flex flex-wrap items-center justify-center gap-2">
          {mustChoose.map((id) => (
            <button key={id} type="button" onClick={() => onBranch(id)}
                   className="rounded-full px-3 py-1 text-sm" style={{ background: 'var(--sh-surface-2)', color: 'var(--sh-ink-soft)' }}>
              {named.find((r) => r.branch_id === id)?.name || id}
            </button>
          ))}
        </div>
      </div>
    );
  }

  if (!data) return <Waiting what="نقرأ مؤشرات محلّك" />;

  const refreshNow = async () => {
    const a = action(catalog, 'insights.refresh');
    const d = action(catalog, 'insights.dashboard');
    if (!a || !d || refreshing) return;
    setRefreshing(true); setNote('');
    try {
      const r = await call<{ ok?: boolean; message?: string }>(session, a);
      if (r?.message) setNote(r.message);
      setData(await call<Dashboard>(session, d, branch ? { branch_id: branch } : {}));
    } catch { setNote('تعذّر التحديث الآن — حاول بعد قليل.'); }
    finally { setRefreshing(false); }
  };

  if (data.empty_branch) return <div className="p-4"><EmptyState title="فرعك لم يبدأ بعد" description={data.message || ''} /></div>;

  if (data.computing) {
    return (
      <div className="flex flex-col items-center gap-3 p-4">
        <EmptyState title="نحسب مؤشرات محلك" description={data.message || ''} />
        {action(catalog, 'insights.refresh') ? (
          <Button disabled={refreshing} onClick={refreshNow}>{refreshing ? 'نحسب…' : 'احسبها الآن'}</Button>
        ) : null}
        {note ? <p className="text-sm" style={{ color: 'var(--sh-ink-soft)' }}>{note}</p> : null}
      </div>
    );
  }

  const somethingToDo = Boolean(data.audience) || Boolean(locked.bundles) || Boolean(bundles?.length);
  const returnRate = data.values['return_rate'];
  const series = data.values['retention_series'] as Series | undefined;
  const eff = data.values['returned_after_reminder'] as Effect | undefined;
  const opt = data.values['opt_out_rate'] as OptOut | undefined;
  const holdout = data.values['holdout_comparison'] as Holdout | undefined;
  const week = data.values['visits_week'] as WeekWindow | undefined;
  const split = data.values['new_vs_returning'] as { new: number; returning: number } | undefined;
  const perVisit = data.values['services_per_visit'];
  const flow = data.values['expected_flow'];
  const cycleCompletion = data.values['cycle_completion'];
  const atRisk = data.values['at_risk'] as AtRiskRow[] | undefined;
  const serviceNames = (data.values['service_names'] as Record<string, string> | undefined) ?? {};
  const popularity = data.values['service_popularity'] as { service_id: string; count: number; share: number }[] | undefined;
  const weak = data.values['weak_services'] as string[] | undefined;
  const peak = data.values['peak_map'] as { grid?: Record<string, number>; busiest?: string } | undefined;

  return (
    <div className="flex flex-col gap-3">
      {typeof returnRate === 'number' ? (
        <RetentionHero
          pct={returnRate}
          series={series && !series.learning ? series : undefined}
          sampleSize={typeof data.values['active_customers'] === 'number' ? data.values['active_customers'] as number : undefined}
        />
      ) : null}

      {atRisk && atRisk.length > 0 ? <AtRiskCard session={session} catalog={catalog} rows={atRisk} /> : null}

      {/* EVERYTHING BELOW THE TWO LEAD CARDS FLOWS INTO TWO COLUMNS PAST `lg` — a `flex-col` stack
          here was still one long vertical scroll no matter how wide محلّي's own outer column got;
          the width was spent on margin, not on the content actually rebalancing across it. CSS
          multi-column (not grid) is the right tool: it flows an unpredictable, conditionally-
          rendered set of cards left-to-right by READING ORDER with no per-card column assignment
          to maintain, and `break-inside-avoid` keeps each card from splitting across the seam. */}
      <div className="flex flex-col gap-3 lg:block lg:columns-2 lg:gap-4">
        <div className="mb-3 break-inside-avoid"><SurroundingKpis values={data.values} /></div>
        <div className="mb-3 break-inside-avoid"><RecentVisits session={session} catalog={catalog} /></div>

        {week ? <div className="mb-3 break-inside-avoid"><WeekPulse week={week} /></div> : null}
        {split && (split.new + split.returning) > 0
          ? <div className="mb-3 break-inside-avoid"><NewVsReturning split={split} /></div> : null}

        {(typeof perVisit === 'number' || typeof flow === 'number' || typeof cycleCompletion === 'number') ? (
          <div className="mb-3 grid gap-2 break-inside-avoid" style={{ gridTemplateColumns: 'repeat(3,1fr)' }}>
            {typeof perVisit === 'number' ? <Tile label="خدمات لكل زيارة" value={perVisit.toLocaleString('en-US')} tone="flat" /> : null}
            {typeof flow === 'number' ? <Tile label="متوقّع الأسبوع الجاي" value={String(Math.round(flow))} tone="violet" /> : null}
            {typeof cycleCompletion === 'number' ? <Tile label="التزام الدورة الدورية" value={`${Math.round(cycleCompletion * 100)}%`} tone="teal" /> : null}
          </div>
        ) : null}

        {(eff || opt) ? <div className="mb-3 break-inside-avoid"><MessageFlow eff={eff} opt={opt} /></div> : null}
        {holdout ? <div className="mb-3 break-inside-avoid"><HoldoutCard h={holdout} /></div> : null}

        {(popularity && popularity.length > 0) || (weak && weak.length > 0) ? (
          <div className="mb-3 break-inside-avoid">
            <Section title="خدماتك">
              {popularity && popularity.length > 0 ? <ServicePopularity rows={popularity} names={serviceNames} /> : null}
              {weak && weak.length > 0 ? <WeakServices ids={weak} names={serviceNames} /> : null}
            </Section>
          </div>
        ) : null}

        {peak?.grid && Object.keys(peak.grid).length > 0 ? (
          <div className="mb-3 break-inside-avoid"><PeakHeatmap grid={peak.grid} busiest={peak.busiest} /></div>
        ) : null}

        {/* THE SCREEN NEVER GOES QUIET. It used to say nothing at all here the moment there was no
            cross-sell opportunity and no locked upsell to show — and «nothing» reads as «we have
            no idea what you should do next», which is worse than a plain, honest suggestion. This
            always renders something, in priority order, ending in a real positive nudge (never a
            fabricated one) rather than silence. */}
        <div className="mb-3 break-inside-avoid">
          <Section title="الخطوة التالية">
            {locked.bundles ? (
              <LockedLine title="باقات مقترحة" text={locked.bundles} />
            ) : bundles && bundles.length ? (
              <div className="flex flex-col gap-2 rounded-2xl p-4" style={{ background: 'var(--sh-surface)', boxShadow: cardShadow }}>
                <h3 className="text-[12px] font-semibold" style={{ color: 'var(--sh-ink-soft)' }}>باقات مقترحة</h3>
                {bundles.slice(0, 4).map((b, i) => (
                  <div key={i} className="flex flex-col gap-1 pt-2 first:pt-0" style={{ borderTop: i ? '1px dashed var(--sh-line)' : 'none' }}>
                    <span className="text-[13px] font-semibold">{b.a_name} + {b.b_name}</span>
                    {b.why ? <span className="text-[11.5px]" style={{ color: 'var(--sh-ink-soft)' }}>{b.why}</span> : null}
                    <div className="flex items-center justify-between gap-2">
                      {b.action_label ? <span className="text-[11px]" style={{ color: 'var(--sh-violet-deep)' }}>{b.action_label}</span> : <span />}
                      <span dir="ltr" className="text-[11px]" style={{ color: 'var(--sh-ink-faint)', fontVariantNumeric: 'tabular-nums' }}>{b.customers} فرصة</span>
                    </div>
                  </div>
                ))}
              </div>
            ) : data.audience ? (
              <p className="rounded-2xl p-4 text-sm" style={{ background: 'var(--sh-surface)', boxShadow: cardShadow }}>{data.audience.message}</p>
            ) : weak && weak.length > 0 ? (
              <div className="flex items-center justify-between gap-3 rounded-2xl p-4" style={{ background: 'var(--sh-coral-soft)' }}>
                <p className="text-[13px]" style={{ color: 'var(--sh-coral-deep)' }}>
                  عندك {weak.length} {weak.length === 1 ? 'خدمة' : 'خدمات'} ما تُطلب كثيرًا — رَوِّج لها أو راجع سعرها.
                </p>
              </div>
            ) : (
              // THE HONEST GOOD-NEWS CASE — no invented "growth" or fake urgency, and never
              // silence: `reward_loyal` is the same real campaign goal `win_back` is, just for the
              // shop with nothing currently wrong.
              <div className="flex items-center justify-between gap-3 rounded-2xl p-4" style={{ background: 'var(--sh-teal-soft)' }}>
                <p className="text-[13px]" style={{ color: 'var(--sh-teal-deep)' }}>وضعك ثابت ولا شي يستحق تنبيهًا الآن — جرّب تكافئ عملاءك الدائمين.</p>
                {action(catalog, 'campaigns.create') ? (
                  <Link
                    to="/messages?tab=campaigns&launch=reward_loyal"
                    className="shrink-0 rounded-full px-3 py-1.5 text-[11.5px] font-semibold"
                    style={{ background: 'var(--sh-teal)', color: '#ffffff' }}
                  >
                    كافئهم
                  </Link>
                ) : null}
              </div>
            )}
          </Section>
        </div>

        {data.entitlements && !data.entitlements.includes('feature.insights.engine') ? (
          <p className="mb-3 flex items-center gap-2 break-inside-avoid px-1 text-xs" style={{ color: 'var(--sh-ink-faint)' }}>
            🔒 باقات مقترحة — في باقة أعلى.
          </p>
        ) : null}
      </div>

      <Section title="تفاصيل أكثر" hint="ما يُطلب معاً · فروعك · ما ينقصه بيانات" folded>
        {data.not_enabled && data.not_enabled.length > 0 ? (
          <div className="rounded-2xl p-4" style={{ background: 'var(--sh-surface)', boxShadow: cardShadow }}>
            <h3 className="mb-1 text-[13px] font-semibold">أرقامٌ لسه ما نقدر نعرضها</h3>
            <p className="mb-3 text-[11.5px]" style={{ color: 'var(--sh-ink-soft)' }}>كلٌّ منها ينقصه شيء واحد — وهذا ما هو، ومن يستطيع إتمامه.</p>
            <ul className="flex flex-col gap-3">
              {data.not_enabled.map((b) => <MissingRow key={b.indicator} b={b} />)}
            </ul>
          </div>
        ) : null}

        {locked.associations ? <LockedLine title="ما يُطلب معًا" text={locked.associations} /> : null}
        {pairs && !pairs.learning && (pairs.pairs ?? []).length ? (
          <div className="flex flex-col gap-2 rounded-2xl p-4" style={{ background: 'var(--sh-surface)', boxShadow: cardShadow }}>
            <h3 className="text-[12px]" style={{ color: 'var(--sh-ink-soft)' }}>ما يُطلب معًا</h3>
            {(pairs.pairs ?? []).slice(0, 6).map((p) => (
              <div key={`${p.a}|${p.b}`} className="flex items-center justify-between gap-3 pt-2 first:pt-0" style={{ borderTop: '1px solid var(--sh-line)' }}>
                <span className="text-[13px]">{p.a} + {p.b}</span>
                <span dir="ltr" className="text-[11px]" style={{ color: 'var(--sh-ink-faint)', fontVariantNumeric: 'tabular-nums' }}>{p.customers} عميلاً</span>
              </div>
            ))}
          </div>
        ) : null}
        {pairs?.learning ? (
          <p className="rounded-2xl p-4 text-sm" style={{ background: 'var(--sh-surface)', boxShadow: cardShadow, color: 'var(--sh-ink-soft)' }}>
            ما زلنا نتعلّم ما يُطلب معًا في محلّك — {pairs.have ?? 0} زيارة من {pairs.need ?? 0}.
          </p>
        ) : null}

        {branches && (branches.rows ?? []).length > 1 ? <BranchCompare branches={branches} /> : null}
      </Section>

      {data.teaser?.message ? (
        <p className="rounded-2xl p-4 text-sm" style={{ background: 'var(--sh-surface)', boxShadow: cardShadow }}>{data.teaser.message}</p>
      ) : null}

      <div className="flex flex-wrap items-center justify-center gap-2 py-1 text-[11px]" style={{ color: 'var(--sh-ink-faint)' }}>
        <span>{data.as_of_hours_ago === 0 ? 'محسوبة الآن' : `محسوبة قبل ${data.as_of_hours_ago} ساعة`}</span>
        {data.stale ? <span className="rounded-full px-2 py-0.5" style={{ background: '#fdf0dc', color: '#8a5a12' }}>قديمة</span> : null}
        {action(catalog, 'insights.refresh') ? (
          <button type="button" disabled={refreshing} onClick={refreshNow}
                 className="rounded-full px-3 py-1 font-semibold" style={{ background: 'var(--sh-surface-2)', color: 'var(--sh-ink-soft)' }}>
            ↻ {refreshing ? 'نحدّث…' : 'حدّث الآن'}
          </button>
        ) : null}
        {note ? <span>{note}</span> : null}
      </div>
    </div>
  );
}

const cardShadow = '0 1px 2px rgba(19,18,38,.04), 0 6px 16px -8px rgba(19,18,38,.12)';

/** A "game-like" element that is actually computed, not decorated on — how many of the trailing
 *  points in `retention_series.points` moved the SAME direction in a row, ending at the newest
 *  one. Needs three to speak (two real moves in a row), because two points is just the badge above
 *  restated, and a swing that reverses instantly is noise, not a streak. */
export function retentionStreak(
  points?: { value: number | null }[],
): { length: number; rising: boolean } | null {
  const drawn = (points ?? []).filter((p): p is { value: number } => p.value !== null);
  if (drawn.length < 3) return null;
  const rising = drawn[drawn.length - 1].value > drawn[drawn.length - 2].value;
  let length = 1;
  for (let i = drawn.length - 1; i > 0; i--) {
    const up = drawn[i].value > drawn[i - 1].value;
    const flat = drawn[i].value === drawn[i - 1].value;
    if (flat || up !== rising) break;
    length++;
  }
  return length >= 3 ? { length, rising } : null;
}

/** THE HERO — a narrated sentence, the number set large inline, never a bare ring. «من كل ١٠
 *  عملاء زاروك، ٦٫٧ يرجعون لك» is the sentence an owner actually repeats to himself; the number
 *  alone inside a circle was a fact he had to translate before it meant anything.
 *
 *  BUT PROJECTING TO A ROUND TEN LIES ON A SMALL SAMPLE. A shop with one active customer who
 *  happened to return reads «من كل ١٠، ١٠ يرجعون» — a sentence built for a hundred customers,
 *  stated as if it were a fact about ten. An owner does not do the mental math back to «that's
 *  actually just me and my one customer»; he reads it as ten real people. Below a real floor we
 *  say the true, small count instead of a projection dressed as one. */
function RetentionHero({ pct, series, sampleSize }: { pct: number; series?: Series; sampleSize?: number }) {
  const SAMPLE_FLOOR = 10;
  const tooSmall = typeof sampleSize === 'number' && sampleSize < SAMPLE_FLOOR;
  const deltaPts = series ? Math.round(((series.last ?? 0) - (series.first ?? 0)) * 100) : null;
  const streak = retentionStreak(series?.points);
  const sentence = tooSmall
    ? (() => {
        const returned = Math.round(pct * (sampleSize as number));
        const base = sampleSize === 1 ? 'عميل واحد' : `${sampleSize} عملاء`;
        return (
          <>
            من أصل {base} زاروك، <b dir="ltr" className="mx-0.5 inline-block text-[40px] font-extrabold" style={{ fontVariantNumeric: 'tabular-nums' }}>{returned}</b> يرجعون لك مرة ثانية.
          </>
        );
      })()
    : (() => {
        const of10 = (pct * 10).toLocaleString('en-US', { maximumFractionDigits: 1 });
        return (
          <>
            من كل ١٠ عملاء زاروك، <b dir="ltr" className="mx-0.5 inline-block text-[40px] font-extrabold" style={{ fontVariantNumeric: 'tabular-nums' }}>{of10}</b> يرجعون لك مرة ثانية.
          </>
        );
      })();
  return (
    <div className="rounded-3xl p-6 pb-5 text-white" style={{
      background: 'radial-gradient(120% 90% at 15% 0%, #8f6bff 0%, transparent 55%),'
        + 'radial-gradient(110% 100% at 100% 100%, #0fb897 0%, transparent 50%),'
        + 'linear-gradient(160deg,#4c34c4,#2a1f7a)',
      boxShadow: '0 6px 14px rgba(19,18,38,.08), 0 26px 50px -18px rgba(19,18,38,.3)',
    }}>
      <div className="text-[11.5px] font-semibold opacity-75">نسبة عودة عملائك</div>
      <p className="mt-2 text-[20px] font-medium leading-relaxed">{sentence}</p>
      {tooSmall ? (
        <p className="mt-1 text-[12px] opacity-75">العدد لسه صغير — النسبة راح تكون أدق مع عملاء أكثر.</p>
      ) : null}
      {deltaPts !== null && series?.months ? (
        <div className="mt-3 flex items-center gap-3">
          <span className="inline-flex shrink-0 items-center gap-1 rounded-full px-2.5 py-1 text-[11.5px] font-bold" style={{ background: 'rgba(255,255,255,.16)', color: deltaPts >= 0 ? '#baf5da' : '#ffd3c9' }}>
            {deltaPts >= 0 ? '↑' : '↓'} {Math.abs(deltaPts)}+ عن {series.months} أشهر
          </span>
          {/* THE LINE, NOT JUST ITS SIGN — an aggregate ratio can hold steady, or even climb, while
              real customers churn underneath it and new ones backfill the count. The badge above
              says only «up» or «down» over the whole span; the line says WHEN, which is the
              question an owner asking «متى» actually has. Drawn from `retention_series.points`,
              already computed on every tick and, until now, thrown away after the two numbers the
              badge needed. */}
          {series?.points && series.points.length > 1 ? <RetentionSparkline points={series.points} /> : null}
        </div>
      ) : null}
      {/* THE STREAK — a real, computed thing (three or more consecutive points moving the same
          way in `retention_series.points`), not a badge invented to feel like a game. It answers
          the exact question a renewing owner asks himself: "is this actually working, lately, or
          did it work once a while back?" */}
      {streak ? (
        <p className="mt-2 text-[12px] font-medium" style={{ color: streak.rising ? '#baf5da' : '#ffd3c9' }}>
          {streak.rising ? '📈' : '📉'} {streak.rising ? 'تتحسّن' : 'تتراجع'} منذ {streak.length} فترات متتالية
        </p>
      ) : null}
    </div>
  );
}

/** The trend the aggregate hides. Each point is the SAME measurement — return rate over a trailing
 *  window — ending one step earlier than the point after it (see `retention_series`'s own
 *  docstring), so the shape is the shop changing, not the method changing. A point with `value:
 *  null` is a gap in the line — too few customers in that window to trust — never bridged into a
 *  false continuity, and never drawn as zero. */
function RetentionSparkline({ points }: { points: { at: number; customers: number; value: number | null }[] }) {
  const W = 128, H = 34, PAD = 3;
  const drawn = points.map((p) => p.value).filter((v): v is number => v !== null);
  if (drawn.length < 2) return null;
  const min = Math.min(...drawn), max = Math.max(...drawn);
  const span = max - min || 1;
  const x = (i: number) => PAD + (i / (points.length - 1)) * (W - PAD * 2);
  const y = (v: number) => H - PAD - ((v - min) / span) * (H - PAD * 2);

  // ONE <polyline> PER UNBROKEN RUN of non-null points — a single path across a gap would draw a
  // false connection where the docstring explicitly says there must be none.
  const runs: { x: number; y: number }[][] = [];
  let current: { x: number; y: number }[] = [];
  points.forEach((p, i) => {
    if (p.value === null) { if (current.length) runs.push(current); current = []; return; }
    current.push({ x: x(i), y: y(p.value) });
  });
  if (current.length) runs.push(current);

  const last = runs.at(-1)?.at(-1);
  return (
    <svg width={W} height={H} viewBox={`0 0 ${W} ${H}`} className="shrink-0" aria-hidden="true">
      {runs.map((run, i) => (
        <polyline
          key={i}
          points={run.map((p) => `${p.x},${p.y}`).join(' ')}
          fill="none"
          stroke="rgba(255,255,255,.75)"
          strokeWidth={2}
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      ))}
      {last ? <circle cx={last.x} cy={last.y} r={2.6} fill="#ffffff" /> : null}
    </svg>
  );
}

/** The three that surround the hero — absent is not zero: a key the plan withheld or the snapshot
 *  could not compute is skipped entirely rather than drawn as 0. */
function SurroundingKpis({ values }: { values: Record<string, unknown> }) {
  const items: { key: string; label: string; percent?: boolean; suffix?: string; tone: 'violet' | 'teal' | 'coral' | 'flat';
                trendKey?: string; goodIsUp?: boolean; weight?: number }[] = [
    // WEIGHT IS A DESIGN CHOICE, NOT A DATA ONE — «عملاء نشطون» is the headline count of the
    // three (the other two are context on it), so it keeps more room whether it happens to be
    // high or low today. A size that swung with the number itself would be a second, competing
    // way of saying "this matters," on top of colour — one signal per idea, not two fighting
    // each other.
    { key: 'active_customers', label: 'عملاء نشطون', tone: 'violet', trendKey: 'active_customers_trend', goodIsUp: true, weight: 1.3 },
    { key: 'return_cycle_days', label: 'دورة العودة', suffix: 'يومًا', tone: 'flat' },
    // MORE TSARRUB IS WORSE — `goodIsUp: false`, so a rising number still shades coral, never teal.
    { key: 'churn_rate', label: 'التسرّب', percent: true, tone: 'coral', trendKey: 'churn_rate_trend', goodIsUp: false },
  ];
  const shown = items.filter((h) => typeof values[h.key] === 'number');
  if (!shown.length) return null;
  return (
    <div className="grid gap-2" style={{ gridTemplateColumns: shown.map((h) => `${h.weight ?? 1}fr`).join(' ') }}>
      {shown.map((h) => {
        const raw = values[h.key] as number;
        const v = h.percent ? `${Math.round(raw * 100)}%` : String(raw);
        const trend = h.trendKey ? values[h.trendKey] as { current?: number; previous?: number | null } | undefined : undefined;
        const delta = trend && typeof trend.current === 'number' && typeof trend.previous === 'number'
          ? { current: trend.current, previous: trend.previous, goodIsUp: h.goodIsUp, percent: h.percent }
          : undefined;
        return <Tile key={h.key} label={h.label} value={h.suffix ? `${v} ${h.suffix}` : v} tone={h.tone} delta={delta} />;
      })}
    </div>
  );
}

/** What the messages moved, and what they cost — a flow, not two boxes. */
function MessageFlow({ eff, opt }: { eff?: Effect; opt?: OptOut }) {
  return (
    <div className="rounded-2xl p-4" style={{ background: 'var(--sh-surface)', boxShadow: cardShadow }}>
      <h3 className="mb-2 text-[12px] font-semibold" style={{ color: 'var(--sh-ink-soft)' }}>أثر رسائلك</h3>
      <div className="flex items-center gap-2">
        <FlowNode
          value={eff?.ready ? String(eff.visits ?? 0) : '—'}
          label={eff?.ready ? `زيارة عادت خلال ${eff.window_days ?? 30} يومًا${eff.partial ? ' — على الأقل' : ''}` : 'لم نستطع قراءة سجل الرسائل بعد'}
        />
        <div className="h-[3px] flex-1 rounded" style={{ background: 'linear-gradient(90deg,var(--sh-violet-soft),var(--sh-teal-soft))' }} />
        <FlowNode
          value={opt?.ready ? String(opt.rate ?? 0) : '—'}
          label={opt?.ready ? `إيقافًا لكل ألف رسالة${(opt.rate ?? 0) > 20 ? ' — راجع حملاتك' : ''}` : 'قياس الإزعاج يبدأ بعد رسائل أكثر'}
          warn={opt?.ready && (opt.rate ?? 0) > 20}
        />
      </div>
    </div>
  );
}
function FlowNode({ value, label, warn }: { value: string; label: string; warn?: boolean }) {
  return (
    <div className="flex flex-1 flex-col items-center gap-1 text-center">
      <span dir="ltr" className="text-[19px] font-extrabold" style={{ fontVariantNumeric: 'tabular-nums', color: warn ? 'var(--sh-coral-deep)' : 'var(--sh-ink)' }}>{value}</span>
      <span className="max-w-[110px] text-[10px] leading-tight" style={{ color: 'var(--sh-ink-faint)' }}>{label}</span>
    </div>
  );
}

/** Two real cards, the winner visibly warmer — never two numbers with nothing between them. */
function HoldoutCard({ h }: { h: Holdout }) {
  if (!h?.ready) {
    if (h?.reason === 'holdout_off') {
      return <p className="rounded-2xl p-4 text-sm" style={{ background: 'var(--sh-surface)', boxShadow: cardShadow, color: 'var(--sh-ink-soft)' }}>قياس أثر الرسائل غير مُفعَّل — كل عملائك يصلهم كل شيء، فلا مجموعة نقارن بها.</p>;
    }
    const held = h?.held ?? 0, reached = h?.reached ?? 0, need = h?.need ?? 15;
    if (!held && !reached) return null;
    return <p className="rounded-2xl p-4 text-sm" style={{ background: 'var(--sh-surface)', boxShadow: cardShadow, color: 'var(--sh-ink-soft)' }}>ما زلنا نقيس أثر الرسائل على محلّك — {Math.min(held, reached)} من {need} في أصغر المجموعتين.</p>;
  }
  const pct = (v?: number) => `${Math.round((v ?? 0) * 100)}%`;
  const better = (h.gap ?? 0) > 0;
  return (
    <div className="flex flex-col gap-3 rounded-2xl p-4" style={{ background: 'var(--sh-surface)', boxShadow: cardShadow }}>
      <h3 className="text-[13px] font-semibold">أثر الرسائل، مقيساً</h3>
      <div className="flex items-stretch gap-2">
        <div className="flex flex-1 flex-col items-center gap-0.5 rounded-xl p-3" style={{ background: 'var(--sh-surface-2)' }}>
          <span dir="ltr" className="text-[20px] font-extrabold" style={{ fontVariantNumeric: 'tabular-nums' }}>{pct(h.held_rate)}</span>
          <span className="text-center text-[10.5px] leading-tight" style={{ color: 'var(--sh-ink-soft)' }}>بلا رسائل<br />({h.held} عميلاً)</span>
        </div>
        <div className="flex flex-1 flex-col items-center gap-0.5 rounded-xl p-3" style={{ background: better ? 'var(--sh-teal-soft)' : 'var(--sh-surface-2)', color: better ? 'var(--sh-teal-deep)' : 'inherit' }}>
          <span dir="ltr" className="text-[20px] font-extrabold" style={{ fontVariantNumeric: 'tabular-nums' }}>{pct(h.reached_rate)}</span>
          <span className="text-center text-[10.5px] leading-tight opacity-80">وصلتهم رسائلك<br />({h.reached} عميلاً)</span>
        </div>
      </div>
      <p className="text-[11px] leading-relaxed" style={{ color: 'var(--sh-ink-soft)' }}>
        نترك {Math.round(((h.held ?? 0) / ((h.held ?? 0) + (h.reached ?? 1))) * 100)}% من عملائك بلا حملات ولا عروض — لتقارن بنفسك، لا لتصدّقنا.
      </p>
    </div>
  );
}

/** This week against last — the pair the weekly report is actually about, never the shop's whole
 *  life mislabelled as «this week». `previous` is null, not 0, when the history does not reach
 *  back — a triumph invented out of the signup date is worse than no comparison at all. */
function WeekPulse({ week }: { week: WeekWindow }) {
  const delta = week.previous === null ? null : week.visits - week.previous;
  return (
    <div className="flex items-center justify-between rounded-2xl p-4" style={{ background: 'var(--sh-surface)', boxShadow: cardShadow }}>
      <div className="flex flex-col">
        <span className="text-[11.5px]" style={{ color: 'var(--sh-ink-faint)' }}>زياراتك آخر {week.window_days} أيام</span>
        <span dir="ltr" className="text-[22px] font-extrabold" style={{ fontVariantNumeric: 'tabular-nums' }}>{week.visits}</span>
      </div>
      {delta !== null ? (
        <span className="rounded-full px-2.5 py-1 text-[12px] font-bold" style={{
          background: delta >= 0 ? 'var(--sh-teal-soft)' : 'var(--sh-coral-soft)',
          color: delta >= 0 ? 'var(--sh-teal-deep)' : 'var(--sh-coral-deep)',
        }}>
          {delta >= 0 ? '↑' : '↓'} {Math.abs(delta)} عن الأسبوع اللي قبله
        </span>
      ) : (
        <span className="text-[11px]" style={{ color: 'var(--sh-ink-faint)' }}>لسه ما عندنا أسبوع كامل نقارنه</span>
      )}
    </div>
  );
}

/** Who came for the first time this month, against who came back — a split, not two lone numbers. */
function NewVsReturning({ split }: { split: { new: number; returning: number } }) {
  const total = Math.max(1, split.new + split.returning);
  const newPct = Math.round((split.new / total) * 100);
  return (
    <div className="flex flex-col gap-2 rounded-2xl p-4" style={{ background: 'var(--sh-surface)', boxShadow: cardShadow }}>
      <div className="flex items-center justify-between text-[12px]" style={{ color: 'var(--sh-ink-soft)' }}>
        <span>عملاء جدد هذا الشهر — {split.new}</span>
        <span>عائدون — {split.returning}</span>
      </div>
      <div className="flex h-2.5 overflow-hidden rounded-full" style={{ background: 'var(--sh-surface-2)' }}>
        <div className="h-full" style={{ width: `${newPct}%`, background: 'var(--sh-violet)' }} />
        <div className="h-full flex-1" style={{ background: 'var(--sh-teal)' }} />
      </div>
    </div>
  );
}

/** THE MOST ACTIONABLE CARD ON THE SCREEN — a list of names, not a percentage. «12% من عملائك
 *  متأخرون» does nothing; a name and a tap-to-message does. `subject_ref` is a pseudonym (the
 *  indicator never held a phone number); resolved the same way «من تأخّر» resolves one on
 *  عملائي, via `operations.customers_by_refs`. */
function AtRiskCard({ session, catalog, rows }: { session: Session; catalog: Catalog; rows: AtRiskRow[] }) {
  const [who, setWho] = useState<Record<string, CustomerHitLite> | null | undefined>(undefined);

  useEffect(() => {
    const resolve = action(catalog, 'operations.customers_by_refs');
    if (!resolve) { setWho(null); return; }
    const refs = rows.slice(0, 8).map((r) => r.subject_ref);
    call<{ customers: CustomerHitLite[] }>(session, resolve, { refs })
      .then((x) => {
        const by: Record<string, CustomerHitLite> = {};
        for (const c of x.customers ?? []) if (c.subject_ref) by[c.subject_ref] = c;
        setWho(by);
      })
      .catch(() => setWho(null));
  }, [session, catalog, rows]);

  return (
    <div className="flex flex-col gap-3 rounded-2xl p-4" style={{ background: 'var(--sh-violet-soft)' }}>
      <div className="flex items-center justify-between gap-2">
        <h3 className="text-[13px] font-bold" style={{ color: 'var(--sh-violet-deep)' }}>
          {rows.length === 1 ? 'عميل واحد يستحق متابعتك الآن' : `${rows.length} عملاء يستحقون متابعتك الآن`}
        </h3>
        {/* THE LIST WAS THE DEAD END. `win_back` already exists as a full campaign goal — the same
            1.5×-cycle threshold this card's own rows are built from — but nothing on this screen
            reached it, so an owner reading twelve overdue names still had to go find «رسائلي»,
            press «أطلق حملة», and pick the one goal he already came here for. This carries the
            decision with him instead of asking him to make it twice. */}
        {action(catalog, 'campaigns.create') ? (
          <Link
            to="/messages?tab=campaigns&launch=win_back"
            className="shrink-0 rounded-full px-3 py-1.5 text-[11.5px] font-semibold"
            style={{ background: 'var(--sh-violet)', color: '#ffffff' }}
          >
            أرسل رسالة رجوع
          </Link>
        ) : null}
      </div>
      {who === undefined ? <Skeleton height={40} /> : (
        <ul className="flex flex-col gap-2">
          {rows.slice(0, 5).map((r) => {
            const c = who?.[r.subject_ref];
            return (
              <li key={r.subject_ref} className="flex items-center justify-between rounded-xl px-3 py-2" style={{ background: 'var(--sh-surface)' }}>
                <span dir={c?.name ? undefined : 'ltr'} className="text-[13px] font-medium">
                  {c ? (c.name || asLocal(c.phone)) : 'عميل'}
                </span>
                <span dir="ltr" className="text-[11px]" style={{ color: 'var(--sh-ink-faint)', fontVariantNumeric: 'tabular-nums' }}>
                  متأخر {r.days_overdue} يومًا عن دورته المعتادة
                </span>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}

/** What his own customers ask for most — real counts, real names, never a placeholder. */
/** A TILE PER SERVICE, SIZED AND SHADED BY DEMAND — a bar list already said this once as a length;
 *  this says it again as an area, which reads at a glance the way a bar chart reads only after
 *  scanning every row. Both size and colour depth carry the SAME variable (share of demand) rather
 *  than a second, invented one — a service's growth over time isn't data this snapshot has, and a
 *  colour that pretended to encode it would be a colour that lied. `flexBasis` approximates a
 *  treemap without a squarified-layout algorithm: honest proportional area, not pixel-exact packing. */
function ServicePopularity({ rows, names }: { rows: { service_id: string; count: number; share: number }[]; names: Record<string, string> }) {
  const top = rows.slice(0, 8);
  const total = top.reduce((s, r) => s + r.count, 0) || 1;
  return (
    <div className="flex flex-col gap-2.5 rounded-2xl p-4" style={{ background: 'var(--sh-surface)', boxShadow: cardShadow }}>
      <h3 className="text-[13px] font-semibold">الأكثر طلبًا عندك</h3>
      <div className="flex flex-wrap gap-1.5">
        {top.map((r) => {
          const pct = r.count / total;
          // A FLOOR ON WIDTH so a 2%-of-demand service still fits its name, AND A CEILING so one
          // busy service never swallows the whole row — the number beside it still says the real
          // share either way, so the tile's size is a hint, never the only place the truth lives.
          const basis = Math.min(58, Math.max(24, Math.round(pct * 100)));
          return (
            <div
              key={r.service_id}
              className="flex flex-col gap-0.5 rounded-lg px-2.5 py-1.5"
              style={{
                flexBasis: `${basis}%`,
                background: `color-mix(in srgb, var(--sh-teal) ${Math.round(18 + pct * 72)}%, white)`,
              }}
            >
              <span className="truncate text-[11.5px] font-semibold leading-tight" style={{ color: 'var(--sh-teal-deep)' }}>
                {names[r.service_id] || r.service_id}
              </span>
              <span dir="ltr" className="text-[10px] font-medium" style={{ color: 'var(--sh-teal-deep)', fontVariantNumeric: 'tabular-nums' }}>
                {r.count} · {Math.round(r.share * 100)}%
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

/** The quietest fifth of his OWN catalogue — a judgement about his shop, never an invented
 *  threshold. A service he never sold is weakest of all and belongs here too. */
function WeakServices({ ids, names }: { ids: string[]; names: Record<string, string> }) {
  return (
    <div className="flex flex-col gap-2 rounded-2xl p-4" style={{ background: 'var(--sh-surface)', boxShadow: cardShadow }}>
      <h3 className="text-[13px] font-semibold">خدمات ما تُطلب كثيرًا</h3>
      <div className="flex flex-wrap gap-1.5">
        {ids.slice(0, 8).map((id) => (
          <span key={id} className="rounded-full px-2.5 py-1 text-[11.5px]" style={{ background: 'var(--sh-coral-soft)', color: 'var(--sh-coral-deep)' }}>
            {names[id] || id}
          </span>
        ))}
      </div>
    </div>
  );
}

const DAY_LETTERS = ['ح', 'ن', 'ث', 'ر', 'خ', 'ج', 'س'];
const DAY_NAMES = ['الأحد', 'الإثنين', 'الثلاثاء', 'الأربعاء', 'الخميس', 'الجمعة', 'السبت'];

/** WHEN HE'S ACTUALLY BUSY — not "the shop's own city, on a real map" (nothing here is
 *  geographic), but the same visual idea the request asked for: a grid where colour depth alone
 *  says which cell matters, no legend to read first. 7 days × 24 hours, one sequential hue —
 *  darker means busier, never a second hue crossing zero, because this has no "bad" side. The
 *  offset into Riyadh time already happened in `peak_map` itself, deliberately, so a UTC grid never
 *  puts a Saudi evening rush at three in the afternoon here. */
function PeakHeatmap({ grid, busiest }: { grid: Record<string, number>; busiest?: string }) {
  const cells: number[][] = Array.from({ length: 7 }, () => Array(24).fill(0));
  let max = 0;
  for (const [key, count] of Object.entries(grid)) {
    const [d, h] = key.split(':').map(Number);
    if (d >= 0 && d < 7 && h >= 0 && h < 24) { cells[d][h] = count; if (count > max) max = count; }
  }
  if (max <= 0) return null;
  const [bd, bh] = (busiest ?? '').split(':').map(Number);
  const busiestName = Number.isFinite(bd) && DAY_NAMES[bd] ? `${DAY_NAMES[bd]} حوالي الساعة ${bh}:00` : '';

  return (
    <div className="flex flex-col gap-2.5 rounded-2xl p-4" style={{ background: 'var(--sh-surface)', boxShadow: cardShadow }}>
      <h3 className="text-[13px] font-semibold">أكثر أوقاتك ازدحامًا</h3>
      <div dir="ltr" className="flex flex-col gap-[2px]">
        {cells.map((row, d) => (
          <div key={d} className="flex items-center gap-[2px]">
            <span className="w-4 shrink-0 text-center text-[10px]" style={{ color: 'var(--sh-ink-faint)' }}>{DAY_LETTERS[d]}</span>
            {row.map((v, h) => (
              <div
                key={h}
                title={v ? `${DAY_NAMES[d]} ${h}:00 — ${v} زيارة` : undefined}
                className="h-3 flex-1 rounded-[2px]"
                style={{ background: v ? `color-mix(in srgb, var(--sh-violet) ${Math.round(12 + (v / max) * 78)}%, white)` : 'var(--sh-surface-2)' }}
              />
            ))}
          </div>
        ))}
      </div>
      {busiestName ? <p className="text-[11px]" style={{ color: 'var(--sh-ink-soft)' }}>أكثر وقت زحمة عندك: {busiestName}.</p> : null}
    </div>
  );
}

function LockedLine({ title, text }: { title: string; text: string }) {
  return (
    <div className="flex items-start gap-2 rounded-2xl p-4" style={{ background: 'var(--sh-surface)', boxShadow: cardShadow }}>
      <span className="mt-0.5 shrink-0" style={{ color: 'var(--sh-ink-faint)' }}>🔒</span>
      <div className="flex flex-col gap-1">
        <h3 className="text-[13px] font-semibold">{title}</h3>
        <p className="text-[12.5px]" style={{ color: 'var(--sh-ink-soft)' }}>{text}</p>
      </div>
    </div>
  );
}

function MissingRow({ b }: { b: Blocked }) {
  const [copied, setCopied] = useState<'ok' | 'failed' | null>(null);
  const headline = (b.lost ?? '').trim() || blockedSentence(b);
  if (!headline) return null;
  const owner = BLOCKED_OWNER[b.owner ?? 'unknown'];
  const have = b.progress?.have, need = b.progress?.need;
  const showBar = typeof have === 'number' && typeof need === 'number' && need > 0;
  return (
    <li className="flex flex-col gap-1 pt-3 first:pt-0" style={{ borderTop: '1px solid var(--sh-line)' }}>
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-[13px] font-semibold">{headline}</span>
        {owner ? <span className="rounded-full px-2 py-0.5 text-[10px] font-semibold" style={{ background: 'var(--sh-surface-2)', color: 'var(--sh-ink-soft)' }}>{owner}</span> : null}
      </div>
      {b.why ? <span className="text-[12px]" style={{ color: 'var(--sh-ink-soft)' }}>{b.why}</span> : null}
      {showBar ? (
        <div className="flex items-center gap-2">
          <div className="h-1.5 flex-1 overflow-hidden rounded-full" style={{ background: 'var(--sh-surface-2)' }}>
            <div className="h-full rounded-full" style={{ width: `${Math.min(100, Math.round((have! / need!) * 100))}%`, background: 'var(--sh-violet)' }} />
          </div>
          <span dir="ltr" className="text-[10.5px]" style={{ color: 'var(--sh-ink-faint)' }}>{have} من {need}</span>
        </div>
      ) : null}
      {b.do ? <span className="text-[12.5px]">{b.do}</span> : null}
      {b.request ? (
        <button type="button" onClick={() => {
          const write = navigator.clipboard?.writeText(b.request ?? '');
          if (!write) { setCopied('failed'); return; }
          write.then(() => setCopied('ok')).catch(() => setCopied('failed'));
        }} className="self-start rounded-full px-3 py-1.5 text-[11px] font-semibold" style={{ background: 'var(--sh-surface-2)', color: 'var(--sh-ink-soft)' }}>
          {copied === 'ok' ? 'نُسخت — أرسلها له' : copied === 'failed' ? 'تعذّر النسخ — ظلّلها بإصبعك وانسخها' : 'انسخ الرسالة لمزوّد الكاشير'}
        </button>
      ) : null}
      {b.request && copied === 'failed' ? <p className="select-all rounded-lg p-2 text-[11px]" style={{ background: 'var(--sh-surface-2)' }}>{b.request}</p> : null}
    </li>
  );
}

/** Branch comparison as points on one axis — closer to the strong end means a higher return rate,
 *  never two bars of equal visual weight pretending a two-branch shop needs a chart. */
function BranchCompare({ branches }: { branches: Branches }) {
  const rows = (branches.rows ?? []).slice(0, 6);
  const max = Math.max(1, ...rows.map((r) => r.visits ?? 0));
  return (
    <div className="flex flex-col gap-3 rounded-2xl p-4" style={{ background: 'var(--sh-surface)', boxShadow: cardShadow }}>
      <h3 className="text-[13px] font-semibold">فروعك</h3>
      <ul className="flex flex-col gap-2.5">
        {rows.map((r) => {
          const pct = Math.round(((r.visits ?? 0) / max) * 100);
          return (
            <li key={r.branch_id} className="flex flex-col gap-1">
              <div className="flex items-center justify-between text-[12.5px]">
                <span className="font-medium">{r.name || r.branch_id || 'بلا اسم'}</span>
                <span dir="ltr" style={{ color: 'var(--sh-ink-faint)', fontVariantNumeric: 'tabular-nums' }}>{r.visits ?? 0} زيارة · {r.customers ?? 0} عميلاً</span>
              </div>
              <div className="h-2 overflow-hidden rounded-full" style={{ background: 'var(--sh-surface-2)' }}>
                <div className="h-full rounded-full" style={{ width: `${pct}%`, background: 'linear-gradient(90deg,var(--sh-violet),var(--sh-teal))' }} />
              </div>
            </li>
          );
        })}
      </ul>
      {branches.unknown ? <p className="text-[11px]" style={{ color: 'var(--sh-ink-faint)' }}>{branches.unknown} زيارة بلا فرع محدَّد — لا تُحتسب لأي فرع.</p> : null}
      {branches.can_rank === false ? <p className="text-[11px]" style={{ color: 'var(--sh-ink-faint)' }}>لا نرتّب الفروع بعد — الفترة قصيرة، والمقارنة الآن تظلم الأحدث.</p> : null}
    </div>
  );
}

function Section({ title, hint, children, folded = false }: { title: string; hint?: string; children: React.ReactNode; folded?: boolean }) {
  const empty = useMemo(() => {
    const arr = Array.isArray(children) ? children : [children];
    return arr.every((c) => c === null || c === undefined || c === false);
  }, [children]);
  if (empty) return null;
  if (folded) {
    return (
      <details className="rounded-2xl" style={{ background: 'var(--sh-surface)', boxShadow: cardShadow }}>
        <summary className="flex cursor-pointer list-none items-center justify-between p-4 text-[13px] font-semibold">
          <span>{title}{hint ? <span className="mr-2 text-[11px] font-normal" style={{ color: 'var(--sh-ink-soft)' }}>{hint}</span> : null}</span>
        </summary>
        <div className="flex flex-col gap-3 p-4 pt-0">{children}</div>
      </details>
    );
  }
  return (
    <section className="flex flex-col gap-2.5">
      <h2 className="px-1 text-[13px] font-bold">{title}{hint ? <span className="mr-2 text-[11px] font-normal" style={{ color: 'var(--sh-ink-soft)' }}>{hint}</span> : null}</h2>
      {children}
    </section>
  );
}

/* ── ③ reassurance, last — «آخر الزيارات» ─────────────────────────────────────────────────────── */
function RecentVisits({ session, catalog }: { session: Session; catalog: Catalog }) {
  const [recent, setRecent] = useState<CustomerRow[] | null | undefined>(undefined);

  useEffect(() => {
    const r = action(catalog, 'operations.recent');
    if (!r) { setRecent(null); return; }
    call<{ customers: CustomerRow[] }>(session, r, { limit: 5 })
      .then((x) => setRecent(x.customers)).catch(() => setRecent(null));
  }, [session, catalog]);

  return (
    <section className="rounded-2xl p-4" style={{ background: 'var(--sh-surface)', boxShadow: cardShadow }}>
      <h2 className="mb-3 text-[12px] font-semibold" style={{ color: 'var(--sh-ink-soft)' }}>آخر الزيارات</h2>
      {isLoading(recent) ? <Skeleton height={64} />
      : hasFailed(recent) ? <EmptyState title="تعذّرت قراءة آخر الزيارات" description="والخلل عندنا — الزيارات محفوظة. أعد المحاولة بعد قليل." />
      : recent.length === 0 ? <EmptyState title="لم تُسجَّل زيارة بعد" description="سجّل أول زيارة من «تسجيل زيارة»." />
      : (
        <ul className="flex flex-col gap-2">
          {recent.map((c) => (
            <li key={c.id} className="flex items-center justify-between gap-2 text-[13px]">
              <span className="flex items-center gap-2">
                <span className="grid size-6 shrink-0 place-items-center rounded-full text-[10.5px] font-bold" style={{ background: 'var(--sh-surface-2)', color: 'var(--sh-ink-soft)' }}>
                  {(c.name || '—').slice(0, 1)}
                </span>
                <span style={{ color: 'var(--sh-ink-soft)' }}>{c.name || '—'}</span>
              </span>
              <span dir="ltr" style={{ fontVariantNumeric: 'tabular-nums' }}>{asLocal(c.phone)}</span>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
