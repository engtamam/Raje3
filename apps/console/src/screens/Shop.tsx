/**
 * «محلّي» — rebuilt as one file: نصمم بطريقتنا الاحترافية، ملف واحد مخصص
 * بالكامل. Replaces Today.tsx + Local.tsx + this file's own old three-line shell.
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
 * `var(--rj-accent)` etc. from the shared theme; this screen defines its own local tokens on its own
 * root element (violet/teal/coral — see the comment on `TOKENS` below) rather than touching the
 * platform-wide palette, which stays a separate decision for a separate day.
 */
import { useEffect, useMemo, useState, type CSSProperties } from 'react';
import { ChevronDown } from 'lucide-react';
import { Button } from '../rj-ui/Button';
import { EmptyState } from '../rj-ui/EmptyState';
import { Skeleton } from '../rj-ui/Skeleton';
import type { ShellContext } from '../shell-context';
import { Link, useOutletContext } from 'react-router-dom';
import { hasFailed, isLoading, isReady } from '../loading';
import { Waiting } from '../Waiting';
import { ApiError, sentenceFor } from '../api';
import { action, call, type Catalog } from '../catalog';
import type { Session } from '../session';
import { asLocal } from '../phone';
import { outsideVisits } from '../branch-scope';
import { AssistantHint } from '../AssistantHint';
import { riyalsLabel } from '../money';

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
/** One rule's answer, from `services/insights/app/core/next_step.py::pick()` — never invented
 *  client-side; the console only ever renders what the registry already decided and ranked. */
interface NextStepCard {
  id: string; category: string; category_label: string; message: string;
  cta_label?: string; cta_link?: string; tone?: 'info' | 'warning' | 'success';
}
interface NextStep { primary: NextStepCard; secondary?: NextStepCard | null }
interface Dashboard {
  computing: boolean; empty_branch?: boolean; message?: string; values: Record<string, unknown>;
  audience?: { consented: number; message: string } | null; as_of_hours_ago?: number;
  entitlements?: string[]; stale?: boolean; visits?: number; not_enabled?: Blocked[];
  teaser?: { message?: string } | null;
  next_step?: NextStep;
}
interface Pairs { learning?: boolean; have?: number; need?: number;
                 pairs?: { a: string; b: string; verdict: string; customers: number }[] }
interface Bundle { a?: string; b?: string; a_name?: string; b_name?: string; why?: string;
                  customers?: number; action?: string; action_label?: string;
                  /** THE PACKAGE'S OWN id (packages feature) — set only when `action ===
                   *  'extend_package'`, i.e. one side of the pair is already a package
                   *  (insights' bundles.py) and the opportunity is adding the OTHER side to it,
                   *  not creating a new one. */
                  package_id?: string }
interface Branches { rows?: { branch_id?: string; name?: string; visits?: number; customers?: number; return_rate?: number }[];
                    unknown?: number; can_rank?: boolean }
interface OperatorRow { operator_id?: string; name?: string; visits?: number; customers?: number; return_rate?: number }
interface WeekWindow { visits: number; previous: number | null; window_days: number }
interface AtRiskRow { subject_ref: string; days_overdue: number; own_cycle_days: number; visits: number }
interface MissedOpp { subject_ref: string; has: string; missing: string; verdict: 'real' | 'temporal' | string }
interface CustomerHitLite { id: string; phone: string; name?: string; subject_ref?: string }
/** services/whatsapp-assistant/app/core/shop_impact_report.py::ShopImpactReport.as_dict() —
 *  THIS SHOP'S OWN numbers only, never a platform aggregate (see that module's own docstring). */
interface ShopImpact {
  days: number; conversations: number; ai_bookings: number; conversion_rate: number | null;
  avg_invoice_value_minor: number | null; upsell_offered: number; upsell_accepted: number;
  upsell_acceptance_rate: number | null; truncated: boolean;
}

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

  // «دقائق» WAS A CLAIM ABOUT HOW LONG SOMETHING TAKES WITH NO LINK TO GO DO IT — the owner read
  // "minutes" and still had to go find «حسابي» himself. Dropped the estimate, added the real link.
  const warning: { text: string; href?: string } | null = (() => {
    if (connected && connected.state !== 'connected' && connected.state !== '') return { text: connected.message };
    if (connected && connected.state === '') return { text: 'واتساب غير مربوط — رسائلك لا تُرسل بعد.', href: '/account?tab=whatsapp' };
    if (connected && connected.can_send === false) return { text: 'واتساب مربوط ولم يبدأ الإرسال — أدخل رمز التحقق بخطوتين في «حسابي» لتفعيله.', href: '/account?tab=whatsapp' };
    if (today?.ceiling.known && !today.ceiling.unlimited && today.ceiling.remaining <= 0) return { text: 'بلغت سقف واتساب اليوم. الرسائل المتبقية ستُرسل غداً تلقائياً.' };
    return null;
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
        <div className="flex flex-wrap items-center justify-between gap-2 rounded-2xl px-4 py-3 text-[13px]" style={{ background: '#fdf0dc', color: '#8a5a12' }}>
          <span>{warning.text}</span>
          {warning.href ? (
            <Link to={warning.href} className="shrink-0 font-semibold underline underline-offset-2">اربطه الآن ←</Link>
          ) : null}
        </div>
      ) : null}

      <div className="grid grid-cols-3 gap-2">
        <Tile label="رسائل خرجت اليوم" value={String(today.messages.sent_today)} tone="violet"
             session={session} helpAnchor="shop.messages_sent_today" />
        <Tile label="بانتظار الإرسال" value={String(today.messages.waiting)} tone="flat"
             session={session} helpAnchor="shop.messages_waiting" />
        <Tile
          label="سقفك المتبقي اليوم"
          value={!today.ceiling.known ? '—' : today.ceiling.unlimited ? 'بلا حدّ' : String(today.ceiling.remaining)}
          tone={!today.ceiling.known || today.ceiling.unlimited ? 'flat' : today.ceiling.remaining <= 0 ? 'coral' : 'teal'}
          session={session} helpAnchor="shop.ceiling_remaining"
        />
      </div>
    </>
  );
}

/** No icon slot on purpose — a dot that repeats on every single tile regardless of what the tile
 *  means is decoration pretending to be information, and worse than no icon: it teaches the eye
 *  to skip it. The tone-colored number itself IS the signal.
 *
 *  A SOFT-TINTED SURFACE, NOT A WHITE CARD WITH A COLOURED HAIRLINE — the earlier version put the
 *  same near-white background on every tile regardless of tone, so a screen of six or eight tiles
 *  read as identical boxes distinguished only by a 2px line most eyes never register (a
 *  screenshot of a fresh shop: "كلها مربعات… مافي أشكال احترافية"). Each tone now owns its own
 *  panel colour, so the eye sorts the row by shape/colour before it ever reads a number — the same
 *  move `MessageFlow`/`HoldoutCard` already make with their own tinted panels, applied here too. A
 *  tile with no real signal yet (`empty`) drops the tint entirely and dashes its own border, so
 *  "no data yet" reads as a different KIND of tile, not just a lower number. */
function Tile({ label, value, tone, delta, empty, href, hint, session, helpAnchor }: {
  label: string; value: string; tone: 'violet' | 'teal' | 'coral' | 'flat';
  /** THE COMPARISON THAT MAKES A LEVEL MEAN SOMETHING — «good» means "up from before" for most
   *  numbers, so a rising churn rate must still read as bad even though it went up. Pass
   *  `goodIsUp: false` for a tile where more is worse. Omit `delta` entirely when there is no
   *  earlier period to compare against — never render a fabricated "+0". */
  delta?: { current: number; previous: number; goodIsUp?: boolean; percent?: boolean };
  /** TRUE ONLY WHEN THE ZERO MEANS "NOTHING RECORDED YET", never for a real, meaningful zero (a
   *  0% churn rate on an active shop is still a real number and stays in its own tone). */
  empty?: boolean;
  /** WHERE TO GO TO CHANGE THIS NUMBER — a shop reading "0" on day one has to know which screen
   *  fixes that; a tile with nowhere to send him is silent about the one thing he'd ask next. */
  href?: string;
  hint?: string;
  /** THE HELP ICON, WHEN THIS TILE'S NUMBER NEEDS EXPLAINING — optional, since some tiles (a plain
   *  count) need no explanation and the icon would be one more thing to skip past on a busy row. */
  session?: Session;
  helpAnchor?: string;
}) {
  const soft = tone === 'violet' ? 'var(--sh-violet-soft)' : tone === 'teal' ? 'var(--sh-teal-soft)'
    : tone === 'coral' ? 'var(--sh-coral-soft)' : 'var(--sh-surface-2)';
  const fg = tone === 'violet' ? 'var(--sh-violet-deep)' : tone === 'teal' ? 'var(--sh-teal-deep)'
    : tone === 'coral' ? 'var(--sh-coral-deep)' : 'var(--sh-ink)';
  const diff = delta ? delta.current - delta.previous : null;
  const good = delta && diff !== null ? (delta.goodIsUp === false ? diff <= 0 : diff >= 0) : null;
  const body = (
    <div className="flex flex-col gap-1 rounded-2xl p-3 text-center transition-colors" style={
      empty
        ? { background: 'var(--sh-surface)', border: '1.5px dashed var(--sh-line)' }
        : { background: soft, boxShadow: '0 1px 2px rgba(19,18,38,.04)' }
    }>
      <span dir="ltr" className="text-[20px] font-extrabold" style={{ color: empty ? 'var(--sh-ink-faint)' : fg, fontVariantNumeric: 'tabular-nums' }}>{value}</span>
      <span className="flex items-center justify-center gap-0.5 text-[10.5px]" style={{ color: empty ? 'var(--sh-ink-faint)' : 'var(--sh-ink-soft)' }}>
        {label}
        {session && helpAnchor ? <AssistantHint session={session} anchor={helpAnchor} /> : null}
      </span>
      {empty && hint ? <span className="text-[9.5px] leading-tight" style={{ color: 'var(--sh-violet-deep)' }}>{hint}{href ? ' ←' : ''}</span> : null}
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
  return href ? <Link to={href} className="block">{body}</Link> : body;
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
  const [dismissingStep, setDismissingStep] = useState(false);

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

  // «ليس الآن» — cools this one rule (services/insights/app/core/next_step.py's own cooldown),
  // then re-reads the dashboard so a DIFFERENT rule leads immediately rather than on next visit.
  const dismissNextStep = async (id: string) => {
    const dismiss = action(catalog, 'insights.dismiss_next_step');
    const d = action(catalog, 'insights.dashboard');
    if (!dismiss || !d || dismissingStep) return;
    setDismissingStep(true);
    try {
      await call(session, dismiss, { id });
      setData(await call<Dashboard>(session, d, branch ? { branch_id: branch } : {}));
    } catch { /* the card stays as it was — a failed dismiss is not worth a sentence here */ }
    finally { setDismissingStep(false); }
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
  const aiEntitled = (data.entitlements ?? []).includes('feature.whatsapp');
  const serviceNames = (data.values['service_names'] as Record<string, string> | undefined) ?? {};
  const popularity = data.values['service_popularity'] as { service_id: string; count: number; share: number }[] | undefined;
  const weak = data.values['weak_services'] as string[] | undefined;
  const peak = data.values['peak_map'] as { grid?: Record<string, number>; busiest?: string } | undefined;
  const missed = data.values['missed_opportunities'] as MissedOpp[] | undefined;
  const serviceDayGrid = data.values['service_day_heatmap'] as Record<string, number> | undefined;
  const branchDayGrid = data.values['branch_day_heatmap'] as Record<string, number> | undefined;
  const branchNames = (data.values['branch_names'] as Record<string, string> | undefined) ?? {};
  const operatorRows = data.values['operator_rows'] as OperatorRow[] | undefined;
  const operatorUnknown = data.values['operator_unknown'] as number | undefined;
  const operatorCanRank = data.values['operator_can_rank'] as boolean | undefined;
  const serviceDayRows = topEntitiesByDay(serviceDayGrid, serviceNames, 6);
  const branchDayRows = topEntitiesByDay(branchDayGrid, branchNames, 6);
  // EACH ONE RENDERED IN ITS OWN INDICATOR'S SLOT NOW, NOT COLLECTED INTO A SEPARATE LIST — direct
  // feedback on the old block: «اغبى تصميم بالكامل … كل مؤشر بمكانه المناسب». `not_enabled` still
  // names exactly the same three indicators (`coverage.py`'s own `BLOCKED_REASONS`); only where
  // each one is READ changed, right beside the real card it stands in for.
  const notEnabled = data.not_enabled ?? [];
  const branchBlocked = notEnabled.find((b) => b.indicator === 'branch_comparison');
  const staffBlocked = notEnabled.find((b) => b.indicator === 'staff_performance');
  const associationsBlocked = notEnabled.find((b) => b.indicator === 'associations');

  // ONE SLOT, ALWAYS SOMETHING IN IT — direct and repeated: «always render لكل المكونات في
  // محلي ضروري لازم ما تجلس تخفي شي ابدا». Every card below either draws itself (real data,
  // even a single real row) or draws THIS — muted, stamped, honestly explained — never nothing.
  const muted = (title: string, note: string) => <MutedIndicator title={title} note={note} />;

  return (
    <div className="flex flex-col gap-3">
      {typeof returnRate === 'number' ? (
        <RetentionHero
          pct={returnRate}
          series={series && !series.learning ? series : undefined}
          sampleSize={typeof data.values['active_customers'] === 'number' ? data.values['active_customers'] as number : undefined}
          session={session}
        />
      ) : muted('نسبة عودة عملائك', 'ما نقدر نحسبها بعد — تحتاج زيارات حقيقية أولاً.')}

      {/* THE SECOND-TIER LEAD ROW — side by side on a wide screen, never a THIRD full-width card
          stacked under the hero above (direct feedback: "سرد بطاقات بطل تحت بعض مو كويس"). Only
          `RetentionHero` stays alone at full width as the one true headline. AtRiskCard shares the
          row with AIImpactCard when the shop actually has the AI feature to show; otherwise it
          keeps the whole row via `lg:col-span-2` — the non-subscriber case gets its own marketing
          through «الخطوة التالية» instead (NextStepView's `whatsapp_ai_teaser`), not a second card
          here that would have nothing real to show. */}
      <div className="grid grid-cols-1 gap-3 lg:grid-cols-2 lg:gap-4">
        <div className={aiEntitled ? '' : 'lg:col-span-2'}>
          {atRisk && atRisk.length > 0 ? <AtRiskCard session={session} catalog={catalog} rows={atRisk} />
            // A REAL EMPTY LIST HERE IS GOOD NEWS, NOT "NOT ACTIVE YET" — the muted/stamped language
            // means "pending", and applying it to «ولا عميل متأخر» would tell an owner in great shape
            // that something on his own screen is still forming. A plain, undecorated reassurance line
            // instead — still always shown, never a silently missing card.
            : atRisk ? (
              <div className="rounded-2xl p-4" style={{ background: 'var(--sh-teal-soft)', color: 'var(--sh-teal-deep)' }}>
                <p className="text-[12.5px] font-medium">ولا عميل متأخر عن دورته المعتادة الآن — وضعك جيد.</p>
              </div>
            ) : null}
        </div>
        {aiEntitled ? <div><AIImpactCard session={session} catalog={catalog} /></div> : null}
      </div>

      {/* EVERYTHING BELOW THE TWO LEAD CARDS FLOWS INTO TWO COLUMNS PAST `lg` — a `flex-col` stack
          here was still one long vertical scroll no matter how wide محلّي's own outer column got;
          the width was spent on margin, not on the content actually rebalancing across it. CSS
          multi-column (not grid) is the right tool: it flows an unpredictable, conditionally-
          rendered set of cards left-to-right by READING ORDER with no per-card column assignment
          to maintain, and `break-inside-avoid` keeps each card from splitting across the seam. */}
      <div className="flex flex-col gap-3 lg:block lg:columns-2 lg:gap-4">
        <div className="mb-3 break-inside-avoid"><SurroundingKpis values={data.values} session={session} /></div>

        {week ? <div className="mb-3 break-inside-avoid"><WeekPulse week={week} session={session} /></div>
          : <div className="mb-3 break-inside-avoid">{muted('زياراتك آخر أيام', 'ما نقدر نقرأ نافذة الأسبوع الآن.')}</div>}
        {split && (split.new + split.returning) > 0
          ? <div className="mb-3 break-inside-avoid"><NewVsReturning split={split} session={session} /></div>
          : <div className="mb-3 break-inside-avoid">{muted('عملاء جدد وعائدون', 'ما فيه زيارات كافية هذا الشهر لنقسمها بعد.')}</div>}

        {(typeof perVisit === 'number' || typeof flow === 'number' || typeof cycleCompletion === 'number') ? (
          <div className="mb-3 grid gap-2 break-inside-avoid" style={{ gridTemplateColumns: 'repeat(3,1fr)' }}>
            {/* ROUNDED FOR DISPLAY ONLY — insights-service's services_per_visit() is a genuine
                average (round(x, 2), e.g. 1.5) and stays exact on the wire; a KPI tile reading
                "1.5" beside a whole count of visits reads as a typo rather than a statistic, so
                the tile shows the nearest whole number a shop owner can act on. */}
            {typeof perVisit === 'number' ? <Tile label="خدمات لكل زيارة" value={Math.round(perVisit).toLocaleString('en-US')} tone="flat" session={session} helpAnchor="shop.services_per_visit" /> : null}
            {typeof flow === 'number' ? <Tile label="متوقّع الأسبوع الجاي" value={String(Math.round(flow))} tone="violet" session={session} helpAnchor="shop.expected_flow" /> : null}
            {typeof cycleCompletion === 'number' ? <Tile label="التزام الدورة الدورية" value={`${Math.round(cycleCompletion * 100)}%`} tone="teal" session={session} helpAnchor="shop.cycle_completion" /> : null}
          </div>
        ) : (
          <div className="mb-3 break-inside-avoid">{muted('خدماتك لكل زيارة، والالتزام بالدورة', 'تحتاج زياراتٍ حقيقية أولاً لتُحسب.')}</div>
        )}

        {(eff || opt) ? <div className="mb-3 break-inside-avoid"><MessageFlow eff={eff} opt={opt} session={session} /></div>
          : <div className="mb-3 break-inside-avoid">{muted('أثر رسائلك', 'ما وصلنا سجل الرسائل بعد.')}</div>}
        {holdout ? <div className="mb-3 break-inside-avoid"><HoldoutCard h={holdout} session={session} /></div>
          : <div className="mb-3 break-inside-avoid">{muted('أثر الرسائل، مقيساً', 'يحتاج مجموعتين حقيقيتين للمقارنة — لسا ما تكوّنتا.')}</div>}

        {/* A RANKING OF HIS OWN BRANCHES AND STAFF IS NOT A DETAIL — it is the comparison
            asked for by name, and it must ALWAYS draw itself, muted when thin (never absent —
            «always render لكل المكونات … لازم ما تجلس تخفي شي ابدا»).
            `BranchCompare`/`StaffCompare` now handle the thin case internally; `branchBlocked`/
            `staffBlocked` (coverage.py's own signal) is the richer explanation when we HAVE it,
            and the plain muted fallback covers the rest. */}
        <div className="mb-3 break-inside-avoid">
          {branches ? <BranchCompare branches={branches} session={session} />
            : branchBlocked ? <BlockedStamp b={branchBlocked} />
            : muted('مقارنة الفروع', 'ما نقدر نقرأ فروعك الآن.')}
        </div>
        <div className="mb-3 break-inside-avoid">
          {operatorRows ? (
            <StaffCompare rows={operatorRows} unknown={operatorUnknown} canRank={operatorCanRank} session={session} />
          ) : staffBlocked ? (
            // THE ONE STAMP WITH A REAL LINK — a team he can invite into the product is the actual
            // fix for "visits arrive with nobody's name on them", unlike the other two (both
            // `owner: 'time'`, which genuinely have nowhere to send him).
            <BlockedStamp b={staffBlocked} cta={action(catalog, 'operations.list_operators') ? { label: 'فريقي', href: '/team' } : undefined} />
          ) : muted('مقارنة الموظفين', 'ما نقدر نقارن الموظفين بهذا العرض الآن.')}
        </div>

        <div className="mb-3 break-inside-avoid">
          <Section title="خدماتك">
            {popularity && popularity.length > 0 ? <ServicePopularity rows={popularity} names={serviceNames} session={session} /> : null}
            {weak && weak.length > 0 ? <WeakServices ids={weak} names={serviceNames} session={session} /> : null}
            {!(popularity && popularity.length > 0) && !(weak && weak.length > 0)
              ? muted('خدماتك', 'ما فيه بيانات خدمات كافية بعد — سجّل بضع زيارات وتبدأ تظهر.') : null}
          </Section>
        </div>

        {peak?.grid && Object.keys(peak.grid).length > 0 ? (
          <div className="mb-3 break-inside-avoid"><PeakHeatmap grid={peak.grid} busiest={peak.busiest} session={session} /></div>
        ) : (
          <div className="mb-3 break-inside-avoid">{muted('أكثر أوقاتك ازدحامًا', 'تحتاج زياراتٍ موزّعة على أيام وساعات كافية لنرسمها.')}</div>
        )}

        {serviceDayRows.length > 0 ? (
          <div className="mb-3 break-inside-avoid">
            <EntityDayHeatmap
              title="خدماتك حسب يوم الأسبوع"
              hue="teal"
              rows={serviceDayRows}
              hint="أي خدمة تُطلب بيوم معيّن أكثر — يساعدك تجهّز الطاقم المناسب ذاك اليوم."
            />
          </div>
        ) : (
          <div className="mb-3 break-inside-avoid">{muted('خدماتك حسب يوم الأسبوع', 'تحتاج زياراتٍ موزّعة على أيام كافية لنرسمها.')}</div>
        )}

        {/* واحدة تتصدّر دائماً، من محرك حقيقي (services/insights/app/core/next_step.py) — لا
            سلسلة if/else يدوية. أي قاعدة تختارها المنصة تُعرض كما هي، بلا اختراع نص هنا. */}
        <div className="mb-3 break-inside-avoid">
          <Section title="الخطوة التالية" session={session} helpAnchor="shop.next_step">
            {data.next_step ? (
              <NextStepView step={data.next_step} onDismiss={dismissNextStep} busy={dismissingStep} />
            ) : null}
          </Section>
        </div>

        {branchDayRows.length > 0 ? (
          <div className="mb-3 break-inside-avoid">
            <EntityDayHeatmap
              title="فروعك حسب يوم الأسبوع"
              hue="violet"
              rows={branchDayRows}
              hint="فروعك ما تشترك بالضرورة بنفس الإيقاع — فرع بمول يزدحم بعطلة، وفرع حيّ يزدحم بعد الدوام."
            />
          </div>
        ) : (
          <div className="mb-3 break-inside-avoid">{muted('فروعك حسب يوم الأسبوع', 'تحتاج فرعاً ثانياً وزياراتٍ موزّعة على أيام كافية لنرسمها.')}</div>
        )}

        {/* ما يُطلب معًا وباقاته — كل حالة بمكانها، لا قائمة منفصلة مجمّعة آخر الصفحة. باقات مقترحة
            نفسها مبنية من نفس الاقترانات (`_bundles.build(pairs, …)` في insights.py)، فسكوتها هو
            نفس سكوت الاقترانات — لا حاجة لختم ثانٍ يكرّر نفس السبب. */}
        {locked.bundles ? (
          <div className="mb-3 break-inside-avoid"><LockedLine title="باقات مقترحة" text={locked.bundles} /></div>
        ) : bundles && bundles.length ? (
          <div className="mb-3 flex flex-col gap-2 break-inside-avoid rounded-2xl p-4" style={{ background: 'var(--sh-surface)', boxShadow: cardShadow }}>
            <h3 className="flex items-center gap-1 text-[12px] font-semibold" style={{ color: 'var(--sh-ink-soft)' }}>
              باقات مقترحة
              <AssistantHint session={session} anchor="shop.bundles" />
            </h3>
            {bundles.slice(0, 4).map((b, i) => {
              // WHERE THE BUTTON GOES (packages feature). `bundle` pre-fills a brand-new
              // package's create form with both services already picked; `extend_package`
              // opens the EXISTING package instead, with the one real service beside it (not
              // itself) offered to add — see insights' bundles.py for which action means which.
              const other = b.a === `pkg:${b.package_id}` ? b.b : b.a;
              const href = b.action === 'bundle' && b.a && b.b
                ? `/services?tab=packages&prefill_a=${encodeURIComponent(b.a)}&prefill_b=${encodeURIComponent(b.b)}`
                : b.action === 'extend_package' && b.package_id && other
                ? `/services?tab=packages&extend_package=${encodeURIComponent(b.package_id)}&extend_service=${encodeURIComponent(other)}`
                : '';
              return (
                <div key={i} className="flex flex-col gap-1 pt-2 first:pt-0" style={{ borderTop: i ? '1px dashed var(--sh-line)' : 'none' }}>
                  <span className="text-[13px] font-semibold">{b.a_name} + {b.b_name}</span>
                  {b.why ? <span className="text-[11.5px]" style={{ color: 'var(--sh-ink-soft)' }}>{b.why}</span> : null}
                  <div className="flex items-center justify-between gap-2">
                    {b.action_label && href ? (
                      <Link to={href} className="text-[11px] font-semibold underline-offset-2 hover:underline"
                           style={{ color: 'var(--sh-violet-deep)' }}>
                        {b.action_label}
                      </Link>
                    ) : b.action_label ? (
                      <span className="text-[11px]" style={{ color: 'var(--sh-violet-deep)' }}>{b.action_label}</span>
                    ) : <span />}
                    <span dir="ltr" className="text-[11px]" style={{ color: 'var(--sh-ink-faint)', fontVariantNumeric: 'tabular-nums' }}>{b.customers} فرصة</span>
                  </div>
                </div>
              );
            })}
          </div>
        ) : bundles ? (
          <div className="mb-3 break-inside-avoid">{muted('باقات مقترحة', 'ما فيه اقترانات كافية بعد لنقترح باقة منها.')}</div>
        ) : null}

        {locked.associations ? (
          <div className="mb-3 break-inside-avoid"><LockedLine title="ما يُطلب معًا" text={locked.associations} /></div>
        ) : pairs && !pairs.learning && (pairs.pairs ?? []).length ? (
          <div className="mb-3 flex flex-col gap-2 break-inside-avoid rounded-2xl p-4" style={{ background: 'var(--sh-surface)', boxShadow: cardShadow }}>
            <h3 className="flex items-center gap-1 text-[12px]" style={{ color: 'var(--sh-ink-soft)' }}>
              ما يُطلب معًا
              <AssistantHint session={session} anchor="shop.associations" />
            </h3>
            {/* `p.a`/`p.b` ARE SERVICE IDS, NOT NAMES — `associations.build` derives every pair
                from raw `service_ids` on the visit and never resolves them, so this rendered a
                literal id (e.g. `svc_a1b2c3`) beside its partner until now. `service_names` was
                already in `data.values` for exactly this reason; nothing else here changed. */}
            {(pairs.pairs ?? []).slice(0, 6).map((p) => (
              <div key={`${p.a}|${p.b}`} className="flex items-center justify-between gap-3 pt-2 first:pt-0" style={{ borderTop: '1px solid var(--sh-line)' }}>
                <span className="text-[13px]">{serviceNames[p.a] || p.a} + {serviceNames[p.b] || p.b}</span>
                <span dir="ltr" className="text-[11px]" style={{ color: 'var(--sh-ink-faint)', fontVariantNumeric: 'tabular-nums' }}>{p.customers} عميلاً</span>
              </div>
            ))}
          </div>
        ) : pairs?.learning ? (
          <div className="mb-3 break-inside-avoid">
            <BlockedStamp b={{
              indicator: 'associations_learning',
              lost: 'ما نعرف بعد ما الذي يُطلب مع ماذا',
              why: 'التعرّف على الاقترانات يحتاج زياراتٍ أكثر ليصير الاستنتاج صحيحاً لا صدفة.',
              do: 'لا شيء عليك — يكتمل وحده مع زيارات محلّك.',
              owner: 'time',
              progress: { have: pairs.have ?? 0, need: pairs.need ?? 0 },
            }} />
          </div>
        ) : associationsBlocked ? (
          <div className="mb-3 break-inside-avoid"><BlockedStamp b={associationsBlocked} /></div>
        ) : null}

        {/* THE INVERSE OF THE PAIR ABOVE — «ما يُطلب معًا» says a relationship exists in the
            aggregate; this names the specific customers standing on the wrong side of it, the
            same move `at_risk` already made for churn (a list to act on, not a percentage). Only
            appears once a real or temporal pair exists to be missing FROM — «he never bought X»
            means nothing without a rule saying X usually comes with what he did buy. */}
        {missed && missed.length > 0 ? (
          <div className="mb-3 break-inside-avoid">
            <MissedOpportunities session={session} catalog={catalog} rows={missed} names={serviceNames} />
          </div>
        ) : missed ? (
          <div className="mb-3 break-inside-avoid">{muted('فرص فائتة', 'لا عملاء واضحين بعد ناقصين خدمة تُشترى عادة مع خدماتهم.')}</div>
        ) : null}
      </div>

      {/* THE STANDALONE «teaser» PARAGRAPH THAT USED TO SIT HERE IS GONE — the same fact is one
          of `next_step`'s own PLAN-category rules (`associations_teaser`) now, arbitrated against
          everything else rather than always shown unconditionally at the bottom of the page. A
          shop for whom it is genuinely the most relevant thing sees it at the top, in the one
          card that leads; nothing here repeats it a second time lower down. */}

      {/* REASSURANCE, LAST ON PURPOSE — «آخر الزيارات» tells him nothing he needs to ACT on, only
          that the system is really recording what happens in his shop. Everything above this line
          is something to read or do; this is just proof, and proof belongs after the substance,
          not mixed into the same flow as the things that matter. */}
      <RecentVisits session={session} catalog={catalog} />

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

/** THE HERO — a narrated sentence, the number set large inline, never a bare ring. «من كل 10
 *  عملاء زاروك، 7 يرجعون لك» is the sentence an owner actually repeats to himself; the number
 *  alone inside a circle was a fact he had to translate before it meant anything.
 *
 *  A WHOLE NUMBER, NEVER A DECIMAL — this sentence counts people, and «7.8 يرجعون» reads as a
 *  fraction of a person on the one screen built to be simple for a non-technical owner.
 *
 *  BUT PROJECTING TO A ROUND TEN LIES ON A SMALL SAMPLE. A shop with one active customer who
 *  happened to return reads «من كل 10، 10 يرجعون» — a sentence built for a hundred customers,
 *  stated as if it were a fact about ten. An owner does not do the mental math back to «that's
 *  actually just me and my one customer»; he reads it as ten real people. Below a real floor we
 *  say the true, small count instead of a projection dressed as one. */
function RetentionHero({ pct, series, sampleSize, session }: { pct: number; series?: Series; sampleSize?: number; session?: Session }) {
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
        // A WHOLE NUMBER, NOT A DECIMAL — the previous version kept one decimal place
        // («7.8 يرجعون») for extra precision, but this sentence counts PEOPLE: «7.8 عميل يرجعون»
        // reads as a fraction of a person, which is exactly the kind of thing this screen exists
        // to make simple for a non-technical owner (feedback while watching the recorded tour built
        // around it: «صاحب المحل بسيط، الرقم 7.8 غلط لازم يكون رقم صحيح»). The small-sample
        // honesty concern this hero already handles separately (SAMPLE_FLOOR, above) — rounding
        // the projected-to-ten sentence to a whole person loses a sliver of precision nobody was
        // reading as precision in the first place.
        const of10 = Math.round(pct * 10).toLocaleString('en-US');
        return (
          <>
            من كل 10 عملاء زاروك، <b dir="ltr" className="mx-0.5 inline-block text-[40px] font-extrabold" style={{ fontVariantNumeric: 'tabular-nums' }}>{of10}</b> يرجعون لك مرة ثانية.
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
      <div className="flex items-center gap-1 text-[11.5px] font-semibold opacity-75">
        نسبة عودة عملائك
        {session ? <AssistantHint session={session} anchor="shop.retention_hero" /> : null}
      </div>
      <p className="mt-2 text-[20px] font-medium leading-relaxed">{sentence}</p>
      {tooSmall ? (
        <p className="mt-1 text-[12px] opacity-75">العدد يعتبر صغير — النسبة راح تكون أدق مع عملاء أكثر.</p>
      ) : null}
      {deltaPts !== null && series?.months ? (
        <div className="mt-3 flex items-center gap-2">
          <span className="inline-flex shrink-0 items-center gap-1 rounded-full px-2.5 py-1 text-[11.5px] font-bold" style={{ background: 'rgba(255,255,255,.16)', color: deltaPts >= 0 ? '#baf5da' : '#ffd3c9' }}>
            {deltaPts >= 0 ? '↑' : '↓'} {Math.abs(deltaPts)}+ عن {series.months} أشهر
          </span>
          {/* THE STREAK, BESIDE THE BADGE — a real, computed thing (three or more consecutive
              points moving the same way in `retention_series.points`), not invented to feel like a
              game. It answers the exact question a renewing owner asks himself: "is this actually
              working, lately, or did it work once a while back?" */}
          {streak ? (
            <span className="text-[11.5px] font-medium" style={{ color: streak.rising ? '#baf5da' : '#ffd3c9' }}>
              {streak.rising ? '📈' : '📉'} {streak.rising ? 'تتحسّن' : 'تتراجع'} منذ {streak.length} فترات
            </span>
          ) : null}
        </div>
      ) : null}
      {/* THE LINE, NOT JUST ITS SIGN — an aggregate ratio can hold steady, or even climb, while
          real customers churn underneath it and new ones backfill the count. The badge above says
          only «up» or «down» over the whole span; the shape says WHEN, which is the question an
          owner asking «متى» actually has. Given its own full-width row and real presence now — a
          128×34 sliver squeezed beside the badge was there but invisible; the ask was for it to be
          worth opening the page for: «سويها بشكل احترافي عالي الجمال ويخليه ينبسط منها». */}
      {series?.points && series.points.length > 1 ? (
        <div className="mt-4 -mx-1"><RetentionTrend points={series.points} /></div>
      ) : null}
    </div>
  );
}

/** THE TREND THE AGGREGATE HIDES, drawn as a real area chart rather than a hairline — a soft
 *  gradient fill under a smoothed curve, the newest point lit with a glow, and the two dates that
 *  bound the window spelled out underneath so «إلى أين» reads as an actual answer, not a shape with
 *  no axis. Each point is the SAME measurement — return rate over a trailing window — ending one
 *  step earlier than the point after it (see `retention_series`'s own docstring), so the shape is
 *  the shop changing, not the method changing. A point with `value: null` is a gap in the curve —
 *  too few customers in that window to trust — never bridged into a false continuity. */
function RetentionTrend({ points }: { points: { at: number; customers: number; value: number | null }[] }) {
  const W = 300, H = 84, PAD_X = 4, PAD_TOP = 10, PAD_BOTTOM = 4;
  const drawn = points.map((p) => p.value).filter((v): v is number => v !== null);
  if (drawn.length < 2) return null;
  const min = Math.min(...drawn), max = Math.max(...drawn);
  const span = max - min || 0.1;
  const x = (i: number) => PAD_X + (i / (points.length - 1)) * (W - PAD_X * 2);
  const y = (v: number) => H - PAD_BOTTOM - ((v - min) / span) * (H - PAD_TOP - PAD_BOTTOM);

  // ONE RUN PER UNBROKEN STRETCH of non-null points — a single path across a gap would draw a
  // false connection where the docstring explicitly says there must be none.
  const runs: { x: number; y: number }[][] = [];
  let current: { x: number; y: number }[] = [];
  points.forEach((p, i) => {
    if (p.value === null) { if (current.length) runs.push(current); current = []; return; }
    current.push({ x: x(i), y: y(p.value) });
  });
  if (current.length) runs.push(current);

  // A SMOOTHED PATH, NOT A JOIN-THE-DOTS LINE — six monthly points read as a staircase drawn
  // straight; a quadratic curve through each pair's midpoint is the smallest change that reads as
  // a trend a human drew rather than a chart library's default.
  const smoothPath = (run: { x: number; y: number }[]) => {
    if (run.length < 2) return '';
    let d = `M ${run[0].x} ${run[0].y}`;
    for (let i = 1; i < run.length; i++) {
      const mid = { x: (run[i - 1].x + run[i].x) / 2, y: (run[i - 1].y + run[i].y) / 2 };
      d += ` Q ${run[i - 1].x} ${run[i - 1].y} ${mid.x} ${mid.y}`;
    }
    const p = run.at(-1)!;
    d += ` T ${p.x} ${p.y}`;
    return d;
  };

  const longest = runs.reduce((a, b) => (b.length > a.length ? b : a), runs[0]);
  const first = longest[0], last = longest.at(-1)!;
  const areaPath = `${smoothPath(longest)} L ${last.x} ${H} L ${first.x} ${H} Z`;
  const oldestAt = points[0].at;
  const fmt = (s: number) => new Date(s * 1000).toLocaleDateString('ar-SA-u-nu-latn', { month: 'short', day: 'numeric' });

  return (
    <div className="flex flex-col gap-1">
      <svg width="100%" height={H} viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" aria-hidden="true">
        <defs>
          <linearGradient id="retentionFill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#ffffff" stopOpacity="0.32" />
            <stop offset="100%" stopColor="#ffffff" stopOpacity="0" />
          </linearGradient>
        </defs>
        <path d={areaPath} fill="url(#retentionFill)" />
        {runs.map((run, i) => (
          <path key={i} d={smoothPath(run)} fill="none" stroke="rgba(255,255,255,.85)" strokeWidth={2.25} strokeLinecap="round" />
        ))}
        {/* THE NEWEST POINT, LIT — a soft halo behind a solid dot, the one point on the whole curve
            that is also the number spelled out above it in the hero's own sentence. */}
        <circle cx={last.x} cy={last.y} r={6} fill="#ffffff" opacity="0.18" />
        <circle cx={last.x} cy={last.y} r={3} fill="#ffffff" />
      </svg>
      {/* THE WINDOW, NAMED — a curve with no axis invites "trend of what, exactly since when?".
          Real dates from the same points the curve is drawn from, never invented. */}
      <div dir="ltr" className="flex items-center justify-between px-1 text-[10px] font-medium" style={{ color: 'rgba(255,255,255,.55)' }}>
        <span>{fmt(oldestAt)}</span>
        <span>الآن</span>
      </div>
    </div>
  );
}

/** The three that surround the hero — absent is not zero: a key the plan withheld or the snapshot
 *  could not compute is skipped entirely rather than drawn as 0. */
function SurroundingKpis({ values, session }: { values: Record<string, unknown>; session: Session }) {
  // A SHOP WITH ZERO ACTIVE CUSTOMERS HAS NOT REALLY STARTED — churn and return-cycle are both
  // undefined on nobody, so all three tiles fall back to the dashed "empty" treatment together
  // rather than reading as three unrelated zeros.
  const justStarted = values['active_customers'] === 0;
  const items: { key: string; label: string; percent?: boolean; suffix?: string; tone: 'violet' | 'teal' | 'coral' | 'flat';
                trendKey?: string; goodIsUp?: boolean; weight?: number; href?: string; hint?: string; helpAnchor?: string }[] = [
    // WEIGHT IS A DESIGN CHOICE, NOT A DATA ONE — «عملاء نشطون» is the headline count of the
    // three (the other two are context on it), so it keeps more room whether it happens to be
    // high or low today. A size that swung with the number itself would be a second, competing
    // way of saying "this matters," on top of colour — one signal per idea, not two fighting
    // each other.
    { key: 'active_customers', label: 'عملاء نشطون', tone: 'violet', trendKey: 'active_customers_trend', goodIsUp: true, weight: 1.3, href: '/visit', hint: 'سجّل أول زيارة', helpAnchor: 'shop.active_customers' },
    { key: 'return_cycle_days', label: 'دورة العودة', suffix: 'يومًا', tone: 'flat', hint: 'تُحسب تلقائياً بعد أول زيارات', helpAnchor: 'shop.return_cycle_days' },
    // MORE TSARRUB IS WORSE — `goodIsUp: false`, so a rising number still shades coral, never teal.
    { key: 'churn_rate', label: 'التسرّب', percent: true, tone: 'coral', trendKey: 'churn_rate_trend', goodIsUp: false, hint: 'لا عملاء بعد ليُحسب منهم', helpAnchor: 'shop.churn_rate' },
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
        return (
          <Tile key={h.key} label={h.label} value={h.suffix ? `${v} ${h.suffix}` : v} tone={h.tone}
               delta={justStarted ? undefined : delta} empty={justStarted}
               href={justStarted ? h.href : undefined} hint={justStarted ? h.hint : undefined}
               session={session} helpAnchor={h.helpAnchor} />
        );
      })}
    </div>
  );
}

/** What the messages moved, and what they cost — a flow, not two boxes. */
function MessageFlow({ eff, opt, session }: { eff?: Effect; opt?: OptOut; session?: Session }) {
  return (
    <div className="rounded-2xl p-4" style={{ background: 'var(--sh-surface)', boxShadow: cardShadow }}>
      <h3 className="mb-2 flex items-center gap-1 text-[12px] font-semibold" style={{ color: 'var(--sh-ink-soft)' }}>
        أثر رسائلك
        {session ? <AssistantHint session={session} anchor="shop.message_flow" /> : null}
      </h3>
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
function HoldoutCard({ h, session }: { h: Holdout; session?: Session }) {
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
      <h3 className="flex items-center gap-1 text-[13px] font-semibold">
        أثر الرسائل، مقيساً
        {session ? <AssistantHint session={session} anchor="shop.holdout" /> : null}
      </h3>
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
function WeekPulse({ week, session }: { week: WeekWindow; session?: Session }) {
  const delta = week.previous === null ? null : week.visits - week.previous;
  // A SHOP WITH ZERO VISITS AND NOTHING TO COMPARE AGAINST IS NOT "MISSING A COMPARISON" — it has
  // not started. Same dashed/linked treatment `Tile` now gives that exact case, so this card stops
  // reading as one more plain white box beside it.
  const justStarted = week.visits === 0 && week.previous === null;
  if (justStarted) {
    return (
      <Link to="/visit" className="flex items-center justify-between gap-3 rounded-2xl p-4"
           style={{ background: 'var(--sh-surface)', border: '1.5px dashed var(--sh-line)' }}>
        <div className="flex flex-col">
          <span className="text-[11.5px]" style={{ color: 'var(--sh-ink-faint)' }}>زياراتك آخر {week.window_days} أيام</span>
          <span dir="ltr" className="text-[22px] font-extrabold" style={{ color: 'var(--sh-ink-faint)', fontVariantNumeric: 'tabular-nums' }}>0</span>
        </div>
        <span className="text-[11px] font-semibold" style={{ color: 'var(--sh-violet-deep)' }}>سجّل أول زيارة ←</span>
      </Link>
    );
  }
  return (
    <div className="flex items-center justify-between rounded-2xl p-4" style={{ background: 'var(--sh-surface)', boxShadow: cardShadow }}>
      <div className="flex flex-col">
        <span className="flex items-center gap-1 text-[11.5px]" style={{ color: 'var(--sh-ink-faint)' }}>
          زياراتك آخر {week.window_days} أيام
          {session ? <AssistantHint session={session} anchor="shop.week_pulse" /> : null}
        </span>
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
function NewVsReturning({ split, session }: { split: { new: number; returning: number }; session?: Session }) {
  const total = Math.max(1, split.new + split.returning);
  const newPct = Math.round((split.new / total) * 100);
  return (
    <div className="flex flex-col gap-2 rounded-2xl p-4" style={{ background: 'var(--sh-surface)', boxShadow: cardShadow }}>
      <div className="flex items-center justify-between text-[12px]" style={{ color: 'var(--sh-ink-soft)' }}>
        <span className="flex items-center gap-1">
          عملاء جدد هذا الشهر — {split.new}
          {session ? <AssistantHint session={session} anchor="shop.new_vs_returning" /> : null}
        </span>
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
        <h3 className="flex items-center gap-1 text-[13px] font-bold" style={{ color: 'var(--sh-violet-deep)' }}>
          {rows.length === 1 ? 'عميل واحد يستحق متابعتك الآن' : `${rows.length} عملاء يستحقون متابعتك الآن`}
          <AssistantHint session={session} anchor="shop.at_risk" />
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

/** محلّي's own "أثر الذكاء الاصطناعي" — ONLY rendered when the dashboard's own entitlements
 *  already say this shop bought the WhatsApp AI feature (see IndicatorsPanel's own `aiEntitled`);
 *  a shop that has NOT bought it gets no card here at all — the marketing for that case lives in
 *  «الخطوة التالية» instead (NextStepView's own `whatsapp_ai_teaser` special-case below), shown
 *  as a suggestion, not a permanent fixture. Self-fetches, same pattern as `AtRiskCard`. */
function AIImpactCard({ session, catalog }: { session: Session; catalog: Catalog }) {
  const [data, setData] = useState<ShopImpact | null | undefined>(undefined);

  useEffect(() => {
    const a = action(catalog, 'whatsapp_assistant.my_impact');
    if (!a) { setData(null); return; }
    call<ShopImpact>(session, a).then(setData).catch(() => setData(null));
  }, [session, catalog]);

  if (data === undefined) return <Skeleton height={140} />;
  if (data === null) return null;   // no capability on this session — nothing to show, quietly

  const pct = data.conversion_rate !== null ? Math.round(data.conversion_rate * 100) : null;

  return (
    <div className="flex flex-col gap-3 rounded-2xl p-4" style={{ background: 'var(--sh-teal-soft)' }}>
      <div className="flex items-center justify-between gap-2">
        <h3 className="flex items-center gap-1 text-[13px] font-bold" style={{ color: 'var(--sh-teal-deep)' }}>
          أثر الذكاء الاصطناعي — آخر {data.days} يوماً
          <AssistantHint session={session} anchor="shop.ai_impact" />
        </h3>
      </div>
      {pct === null ? (
        <p className="text-[12.5px]" style={{ color: 'var(--sh-teal-deep)' }}>
          ما بدأت محادثات كافية بعد لنحسب معدل التحويل — يبدأ يتكوّن مع أول رسائل عملائك.
        </p>
      ) : (
        <p className="text-[13px] leading-relaxed" style={{ color: 'var(--sh-teal-deep)' }}>
          من كل 10 محادثات مع البوت، <b dir="ltr" className="mx-0.5 inline-block text-[26px] font-extrabold" style={{ fontVariantNumeric: 'tabular-nums' }}>{Math.round((data.conversion_rate as number) * 10)}</b> تنتهي بحجز حقيقي.
        </p>
      )}
      <div className="grid grid-cols-3 gap-2">
        <Tile label="محادثات" value={String(data.conversations)} tone="teal" session={session} />
        <Tile label="متوسط الفاتورة" value={data.avg_invoice_value_minor !== null ? riyalsLabel(data.avg_invoice_value_minor) : '—'} tone="teal"
             empty={data.avg_invoice_value_minor === null} hint={data.avg_invoice_value_minor === null ? 'يحتاج حجوزات حضرها العميل' : undefined} />
        <Tile label="قبول الباقات المقترحة"
             value={data.upsell_acceptance_rate !== null ? `${Math.round(data.upsell_acceptance_rate * 100)}%` : '—'}
             tone="teal" empty={data.upsell_acceptance_rate === null}
             hint={data.upsell_acceptance_rate === null ? 'يحتاج اقتراح باقة أولاً' : undefined} />
      </div>
    </div>
  );
}

/** THE INVERSE OF «ما يُطلب معًا» — a relationship the engine already trusts (`real` or
 *  `temporal`, never a raw co-occurrence), and the specific customers standing on one side of it
 *  without the other. Resolved the same way `AtRiskCard` resolves its own pseudonyms — a customer
 *  he can actually reach, not a statistic. Capped at 8 resolutions for the same reason `AtRiskCard`
 *  caps at 8: a PII lookup grows with the list, and the folded section is not the place for it to
 *  grow unbounded. */
function MissedOpportunities({ session, catalog, rows, names }: {
  session: Session; catalog: Catalog; rows: MissedOpp[]; names: Record<string, string>;
}) {
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
    <div className="flex flex-col gap-2 rounded-2xl p-4" style={{ background: 'var(--sh-surface)', boxShadow: cardShadow }}>
      <h3 className="flex items-center gap-1 text-[12px]" style={{ color: 'var(--sh-ink-soft)' }}>
        عملاء ما جرّبوا كل اللي يناسبهم
        <AssistantHint session={session} anchor="shop.missed_opportunities" />
      </h3>
      {who === undefined ? <Skeleton height={40} /> : (
        <ul className="flex flex-col gap-2">
          {rows.slice(0, 8).map((r) => {
            const c = who?.[r.subject_ref];
            return (
              <li key={`${r.subject_ref}|${r.missing}`} className="flex items-center justify-between gap-3 pt-2 first:pt-0" style={{ borderTop: '1px solid var(--sh-line)' }}>
                <span dir={c?.name ? undefined : 'ltr'} className="text-[13px]">{c ? (c.name || asLocal(c.phone)) : 'عميل'}</span>
                <span className="text-[11.5px]" style={{ color: 'var(--sh-ink-faint)' }}>
                  عنده {names[r.has] || r.has} — ما جرّب {names[r.missing] || r.missing}
                </span>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}

/** A RANKED BAR LIST, THE SAME LANGUAGE `BranchCompare` BELOW ALREADY SPEAKS — a name, its real
 *  count and share stated in numerals, and one thin teal bar under it sized against the busiest
 *  service. The card used to size AND shade wrapped tiles by the same variable, which read as a
 *  cluster of same-toned buttons rather than a ranking — two rows of nearly-equal mint green with
 *  no baseline to compare against. A bar chart reads at a glance; a treemap of two items never had
 *  enough rows to earn its own shape. One hue only (share of demand is a magnitude, not a
 *  category), rounded ends, a hairline gap from the track — the marks this list's siblings use. */
function ServicePopularity({ rows, names, session }: { rows: { service_id: string; count: number; share: number }[]; names: Record<string, string>; session?: Session }) {
  const top = rows.slice(0, 8);
  const max = Math.max(1, ...top.map((r) => r.count));
  return (
    <div className="flex flex-col gap-2.5 rounded-2xl p-4" style={{ background: 'var(--sh-surface)', boxShadow: cardShadow }}>
      <h3 className="flex items-center gap-1 text-[13px] font-semibold">
        الأكثر طلبًا عندك
        {session ? <AssistantHint session={session} anchor="shop.service_popularity" /> : null}
      </h3>
      <ul className="flex flex-col gap-2.5">
        {top.map((r) => {
          const pct = Math.round((r.count / max) * 100);
          return (
            <li key={r.service_id} className="flex flex-col gap-1">
              <div className="flex items-center justify-between gap-2 text-[12.5px]">
                <span className="truncate font-medium">{names[r.service_id] || r.service_id}</span>
                {/* SAID PLAINLY, IN PLAIN WORDS, AND IN THE RIGHT ORDER. "2 · 67%" read as two
                    unrelated numbers with no unit; wrapping the whole Arabic phrase in one
                    `dir="ltr"` span (to keep the digits Western) reversed the WORD order too —
                    "طُلبت 2 مرة" came out as "2 مرة طُلبت". Only the digits need `dir="ltr"`; the
                    words around them stay in the page's own RTL flow. */}
                <span className="shrink-0" style={{ color: 'var(--sh-ink-faint)' }}>
                  طُلبت <span dir="ltr" style={{ fontVariantNumeric: 'tabular-nums' }}>{r.count}</span> مرة
                  {' · '}
                  <span dir="ltr" style={{ fontVariantNumeric: 'tabular-nums' }}>{Math.round(r.share * 100)}%</span>
                </span>
              </div>
              <div className="h-2 overflow-hidden rounded-full" style={{ background: 'var(--sh-surface-2)' }}>
                <div className="h-full rounded-full" style={{ width: `${pct}%`, background: 'var(--sh-teal)' }} />
              </div>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

/** The quietest fifth of his OWN catalogue — a judgement about his shop, never an invented
 *  threshold. A service he never sold is weakest of all and belongs here too.
 *
 *  THE CALL TO ACTION LIVES HERE NOW, NOT IN A SECOND CARD. «الخطوة التالية» used to repeat this
 *  exact count and sentence in its own coral box above — the same fact said twice, once as a
 *  summary with no names attached and once as this list of names with no sentence attached. One
 *  card, both halves: what to do, then which services it's about. */
function WeakServices({ ids, names, session }: { ids: string[]; names: Record<string, string>; session?: Session }) {
  return (
    <div className="flex flex-col gap-2 rounded-2xl p-4" style={{ background: 'var(--sh-surface)', boxShadow: cardShadow }}>
      <h3 className="flex items-center gap-1 text-[13px] font-semibold">
        خدمات ما تُطلب كثيرًا
        {session ? <AssistantHint session={session} anchor="shop.weak_services" /> : null}
      </h3>
      {/* "WEAK" IS RELATIVE TO HIS OWN CATALOGUE, NEVER A FIXED NUMBER — insights-service ranks
          his services by demand and names the bottom fifth, ties included (weak_services()).
          A car wash and a body shop cannot share one absolute threshold, so this says exactly
          what the list means instead of leaving him to guess at a percentage or a zero. */}
      <p className="text-[11.5px]" style={{ color: 'var(--sh-ink-soft)' }}>
        أقلّ خُمس خدماتك طلبًا — رَوِّج لها أو راجع سعرها.
      </p>
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
function PeakHeatmap({ grid, busiest, session }: { grid: Record<string, number>; busiest?: string; session?: Session }) {
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
      <h3 className="flex items-center gap-1 text-[13px] font-semibold">
        أكثر أوقاتك ازدحامًا
        {session ? <AssistantHint session={session} anchor="shop.peak_heatmap" /> : null}
      </h3>
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

/** ONE ROW PER ENTITY (a service, a branch), SEVEN COLUMNS FOR THE WEEK — the same grid idea as
 *  `PeakHeatmap`, generalised past hours. Shading is relative to THIS heatmap's own busiest cell,
 *  not a shop-wide max, so a quiet service still shows real contrast between its own good and bad
 *  days instead of reading as a flat, pale row beside a busier one. */
function EntityDayHeatmap({ title, hue, rows, hint }: {
  title: string; hue: 'violet' | 'teal'; hint?: string;
  rows: { label: string; days: number[] }[]; // days[0..6] = Sun..Sat
}) {
  if (!rows.length) return null;
  const max = Math.max(1, ...rows.flatMap((r) => r.days));
  const color = hue === 'violet' ? 'var(--sh-violet)' : 'var(--sh-teal)';
  return (
    <div className="flex flex-col gap-2.5 rounded-2xl p-4" style={{ background: 'var(--sh-surface)', boxShadow: cardShadow }}>
      <h3 className="text-[13px] font-semibold">{title}</h3>
      <div className="flex flex-col gap-[3px]">
        {/* THE DAY LETTERS, ONCE, ABOVE THE GRID — لا داعي لإعادتها كل صف؛ العمود يبقى نفسه. */}
        <div dir="ltr" className="flex items-center gap-[2px]">
          <span className="w-20 shrink-0" />
          {DAY_LETTERS.map((l, i) => (
            <span key={i} className="flex-1 text-center text-[9.5px]" style={{ color: 'var(--sh-ink-faint)' }}>{l}</span>
          ))}
        </div>
        {rows.map((r) => (
          <div key={r.label} dir="ltr" className="flex items-center gap-[2px]">
            <span className="w-20 shrink-0 truncate text-[11px]" style={{ color: 'var(--sh-ink-soft)' }} dir="rtl">{r.label}</span>
            {r.days.map((v, d) => (
              <div
                key={d}
                title={v ? `${DAY_NAMES[d]} — ${v}` : undefined}
                className="h-4 flex-1 rounded-[2px]"
                style={{ background: v ? `color-mix(in srgb, ${color} ${Math.round(12 + (v / max) * 78)}%, white)` : 'var(--sh-surface-2)' }}
              />
            ))}
          </div>
        ))}
      </div>
      {hint ? <p className="text-[11px]" style={{ color: 'var(--sh-ink-soft)' }}>{hint}</p> : null}
    </div>
  );
}

/** Turns a flat `"entityId:day"` grid (`service_day_heatmap`, `branch_day_heatmap`) into the
 *  top-N entities by total, each with a 7-slot day array — the shape `EntityDayHeatmap` wants. */
export function topEntitiesByDay(
  grid: Record<string, number> | undefined, names: Record<string, string>, limit: number,
): { label: string; days: number[] }[] {
  if (!grid) return [];
  const totals: Record<string, number[]> = {};
  for (const [key, count] of Object.entries(grid)) {
    const sep = key.lastIndexOf(':');
    if (sep < 0) continue;
    const id = key.slice(0, sep);
    const day = Number(key.slice(sep + 1));
    if (!(day >= 0 && day < 7)) continue;
    (totals[id] ??= [0, 0, 0, 0, 0, 0, 0])[day] += count;
  }
  return Object.entries(totals)
    .map(([id, days]) => ({ label: names[id] || id, days, sum: days.reduce((a, b) => a + b, 0) }))
    .sort((a, b) => b.sum - a.sum)
    .slice(0, limit)
    .map(({ label, days }) => ({ label, days }));
}

/** THE ONE CARD "الخطوة التالية" EVER RENDERS, plus a second quiet line when the engine found a
 *  genuinely different thing worth mentioning. Neither line invents its own wording — both are
 *  exactly what `next_step.pick()` returned; this component only chooses colours from `tone`. */
function NextStepView({ step, onDismiss, busy }: {
  step: NextStep;
  onDismiss: (id: string) => void;
  busy: boolean;
}) {
  // «info» USED TO STAY PLAIN WHITE — the one card the screen guarantees always has something to
  // say read as the flattest one on it ("الشاشة كلها بياض"). It now takes the
  // same tint language every other card on the screen already uses.
  const TONE_BG: Record<string, string> = {
    warning: 'var(--sh-coral-soft)', success: 'var(--sh-teal-soft)', info: 'var(--sh-violet-soft)',
  };
  const TONE_FG: Record<string, string> = {
    warning: 'var(--sh-coral-deep)', success: 'var(--sh-teal-deep)', info: 'var(--sh-violet-deep)',
  };
  const p = step.primary;
  const bg = TONE_BG[p.tone ?? 'info'] ?? TONE_BG.info;
  const fg = TONE_FG[p.tone ?? 'info'] ?? TONE_FG.info;
  // THE ONE RULE THIS VIEW SPECIAL-CASES — a "ملكي فاخر" treatment for the WhatsApp-AI teaser
  // specifically, so it visually stands apart from an ordinary tip the moment it wins the slot
  // (agreed design: "لما يظهر بوت الواتساب كاقتراح ابغاه يكون بتصميم ملكي فاخر عشان يلفتهم مو
  // مثل العادة"). Keyed on the rule's own `id` — the message/cta text still travels from
  // next_step.py unchanged, never invented client-side; only the frame around it differs.
  const luxury = p.id === 'whatsapp_ai_teaser';
  return (
    <div className="flex flex-col gap-2">
      {luxury ? (
        <div className="relative overflow-hidden rounded-2xl p-4" style={{
          background: 'radial-gradient(120% 140% at 100% 0%, rgba(212,175,55,.35) 0%, transparent 45%),'
            + 'linear-gradient(135deg,#1a1030,#2d1b4e 55%,#3a1f52)',
          boxShadow: '0 6px 14px rgba(19,18,38,.12), 0 20px 40px -16px rgba(58,31,82,.45)',
        }}>
          <div className="flex items-center justify-between gap-3">
            <div className="flex items-center gap-2">
              <span className="grid size-7 shrink-0 place-items-center rounded-full text-[15px]" style={{ background: 'rgba(212,175,55,.22)' }}>✨</span>
              <p className="text-[13px] font-medium leading-relaxed text-white">{p.message}</p>
            </div>
            {p.cta_label && p.cta_link ? (
              <Link
                to={p.cta_link}
                className="shrink-0 rounded-full px-3.5 py-1.5 text-[11.5px] font-bold"
                style={{ background: 'linear-gradient(135deg,#e8c766,#c9a13a)', color: '#241608' }}
              >
                {p.cta_label}
              </Link>
            ) : null}
          </div>
        </div>
      ) : (
        <div className="flex items-center justify-between gap-3 rounded-2xl p-4" style={{ background: bg, boxShadow: cardShadow }}>
          <p className="text-[13px]" style={{ color: fg }}>{p.message}</p>
          {p.cta_label && p.cta_link ? (
            <Link
              to={p.cta_link}
              className="shrink-0 rounded-full px-3 py-1.5 text-[11.5px] font-semibold"
              style={{ background: fg, color: '#ffffff' }}
            >
              {p.cta_label}
            </Link>
          ) : null}
        </div>
      )}
      {/* «ليس الآن» — لا زر بارز، سطر خفيف: هذا ليس تجاهل معلومة، هو طلب يظهر شي آخر بدلها الآن،
          وترجع هي بنفسها لو ظلّت صحيحة بعد فترة (تبريد، لا حذف — core/next_step.py). */}
      <button
        type="button"
        disabled={busy}
        onClick={() => onDismiss(p.id)}
        className="self-start text-[11px] underline underline-offset-2"
        style={{ color: 'var(--sh-ink-faint)' }}
      >
        ليس الآن
      </button>
      {step.secondary ? (
        <p className="px-1 text-[11.5px]" style={{ color: 'var(--sh-ink-faint)' }}>
          وأيضاً: {step.secondary.message}
        </p>
      ) : null}
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

/** THE ROTATED CORNER BADGE every "not active yet" surface on this screen now shares — the real
 *  chart/list card AND the standalone placeholder alike («كلها تظهر بشكلها الفعلي بالكامل
 *  بس بلون باهت شوية … زي الختم»). One visual vocabulary for "this is real, just not full yet". */
function StampBadge() {
  return (
    <span dir="ltr" className="absolute -top-1 left-3 z-10 rotate-[-6deg] rounded-b-md px-2.5 py-1 text-[9.5px] font-bold tracking-wide" style={{ background: 'var(--sh-ink-faint)', color: 'var(--sh-surface)' }}>
      قيد التكوّن
    </span>
  );
}

/** THE FALLBACK FOR A CARD WITH LITERALLY NOTHING TO PLOT YET — no series, no rows, not even one.
 *  Same muted/stamped language as `BranchCompare`/`StaffCompare` above, so an owner reads "not
 *  active yet" the same way everywhere on the screen rather than the card just being missing with
 *  no trace it was ever meant to be there. NEVER a fabricated number — a plain, honest sentence
 *  naming the section, standing exactly where the real card would draw itself once it can. */
function MutedIndicator({ title, note }: { title: string; note: string }) {
  return (
    <div className="relative flex flex-col gap-1.5 overflow-hidden rounded-2xl p-4" style={{
      background: 'var(--sh-surface)', boxShadow: cardShadow, border: '1px solid var(--sh-line)',
      opacity: 0.6, filter: 'grayscale(0.35)',
    }}>
      <StampBadge />
      <h3 className="pt-2 text-[13px] font-semibold" style={{ color: 'var(--sh-ink-soft)' }}>{title}</h3>
      <p className="text-[12px]" style={{ color: 'var(--sh-ink-faint)' }}>{note}</p>
    </div>
  );
}

/** A "قيد التكوّن" STAMP, standing IN THE INDICATOR'S OWN PLACE — not collected into a separate
 *  list elsewhere on the page (feedback on that list: «اغبى تصميم بالكامل»). The dashed
 *  border and rotated corner badge read as "not active yet" at a glance, the same way the empty
 *  `Tile` treatment already does — real explanation, real progress when there is one, a real link
 *  when there is somewhere on the platform that actually finishes it, never an invented one.
 *
 *  ONLY USED WHEN THE REAL CARD HAS NOTHING AT ALL TO SHOW (`associations`, no pairs learned yet).
 *  `BranchCompare`/`StaffCompare` below take the other path — the real chart, muted — for exactly
 *  the case caught in review: a shop WITH visits but one operator still went completely silent on
 *  staff, because the real component's own render guard (`rows.length > 1`) hid it outright while
 *  this stamp's own trigger (a coverage RATIO) never fired for a single, fully-attributed
 *  operator. Two different thresholds guarding the same missing card is how it went dark twice. */
function BlockedStamp({ b, cta }: { b: Blocked; cta?: { label: string; href: string } }) {
  const [copied, setCopied] = useState<'ok' | 'failed' | null>(null);
  const headline = (b.lost ?? '').trim() || blockedSentence(b);
  if (!headline) return null;
  const owner = BLOCKED_OWNER[b.owner ?? 'unknown'];
  const have = b.progress?.have, need = b.progress?.need;
  const showBar = typeof have === 'number' && typeof need === 'number' && need > 0;
  return (
    <div className="relative flex flex-col gap-2 overflow-hidden rounded-2xl p-4" style={{ background: 'var(--sh-surface-2)', border: '1.5px dashed var(--sh-ink-faint)' }}>
      <span dir="ltr" className="absolute -top-1 left-3 rotate-[-6deg] rounded-b-md px-2.5 py-1 text-[9.5px] font-bold tracking-wide" style={{ background: 'var(--sh-ink-faint)', color: 'var(--sh-surface)' }}>
        قيد التكوّن
      </span>
      <div className="flex flex-wrap items-center gap-2 pt-2">
        <span className="text-[13px] font-semibold" style={{ color: 'var(--sh-ink-soft)' }}>{headline}</span>
        {owner ? <span className="rounded-full px-2 py-0.5 text-[10px] font-semibold" style={{ background: 'var(--sh-surface)', color: 'var(--sh-ink-soft)' }}>{owner}</span> : null}
      </div>
      {b.why ? <span className="text-[12px]" style={{ color: 'var(--sh-ink-faint)' }}>{b.why}</span> : null}
      {showBar ? (
        <div className="flex items-center gap-2">
          <div className="h-1.5 flex-1 overflow-hidden rounded-full" style={{ background: 'var(--sh-surface)' }}>
            <div className="h-full rounded-full" style={{ width: `${Math.min(100, Math.round((have! / need!) * 100))}%`, background: 'var(--sh-ink-faint)' }} />
          </div>
          <span dir="ltr" className="text-[10.5px]" style={{ color: 'var(--sh-ink-faint)' }}>{have} من {need}</span>
        </div>
      ) : null}
      {b.do ? <span className="text-[12.5px]" style={{ color: 'var(--sh-ink-soft)' }}>{b.do}</span> : null}
      {cta ? (
        <Link to={cta.href} className="self-start text-[11px] font-semibold underline underline-offset-2" style={{ color: 'var(--sh-violet-deep)' }}>
          {cta.label} ←
        </Link>
      ) : null}
      {b.request ? (
        <button type="button" onClick={() => {
          const write = navigator.clipboard?.writeText(b.request ?? '');
          if (!write) { setCopied('failed'); return; }
          write.then(() => setCopied('ok')).catch(() => setCopied('failed'));
        }} className="self-start rounded-full px-3 py-1.5 text-[11px] font-semibold" style={{ background: 'var(--sh-surface)', color: 'var(--sh-ink-soft)' }}>
          {copied === 'ok' ? 'نُسخت — أرسلها له' : copied === 'failed' ? 'تعذّر النسخ — ظلّلها بإصبعك وانسخها' : 'انسخ الرسالة لمزوّد الكاشير'}
        </button>
      ) : null}
      {b.request && copied === 'failed' ? <p className="select-all rounded-lg p-2 text-[11px]" style={{ background: 'var(--sh-surface)' }}>{b.request}</p> : null}
    </div>
  );
}

/** Branch comparison as points on one axis — closer to the strong end means a higher return rate,
 *  never two bars of equal visual weight pretending a two-branch shop needs a chart. */
/** THE RANK BADGE both comparison cards share — a filled numeral disc, gold/silver/bronze for the
 *  top three and a plain neutral disc after that, the same "podium" language a shop owner already
 *  reads instinctively. This is the whole of the "فخامة" ask: not new data, a treatment worthy of
 *  a ranking rather than a plain list. */
function RankBadge({ n }: { n: number }) {
  const tone = n === 1 ? { bg: 'linear-gradient(135deg,#f5cf6b,#c9932e)', fg: '#3a2a06' }
    : n === 2 ? { bg: 'linear-gradient(135deg,#dfe4ea,#a9b1bb)', fg: '#2b3138' }
    : n === 3 ? { bg: 'linear-gradient(135deg,#d79a6a,#a2603a)', fg: '#3a1f0c' }
    : { bg: 'var(--sh-surface-2)', fg: 'var(--sh-ink-soft)' };
  return (
    <span dir="ltr" className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-[11px] font-bold"
          style={{ background: tone.bg, color: tone.fg, fontVariantNumeric: 'tabular-nums' }}>
      {n}
    </span>
  );
}

function RatePill({ rate, label }: { rate: number; label: string }) {
  return (
    <span dir="ltr" className="rounded-full px-1.5 py-0.5 text-[10px] font-bold" style={{
      background: `color-mix(in srgb, ${rate >= 0.4 ? 'var(--sh-teal)' : 'var(--sh-coral)'} ${Math.round(15 + rate * 60)}%, white)`,
      color: rate >= 0.4 ? 'var(--sh-teal-deep)' : 'var(--sh-coral-deep)',
    }}>
      {Math.round(rate * 100)}% {label}
    </span>
  );
}

/** THE EMPTY ROW BOTH COMPARISON CARDS FALL BACK TO — same skeleton bar shape as a real row, at
 *  0%, so the card's OWN SHAPE is what says "nothing recorded here yet", never a sentence standing
 *  in for a chart that simply isn't drawn. */
function GhostRow({ label }: { label: string }) {
  return (
    <li className="flex flex-col gap-1">
      <div className="flex items-center justify-between text-[12.5px]">
        <span className="font-medium" style={{ color: 'var(--sh-ink-faint)' }}>{label}</span>
        <span dir="ltr" style={{ color: 'var(--sh-ink-faint)' }}>—</span>
      </div>
      <div className="h-2 overflow-hidden rounded-full" style={{ background: 'var(--sh-surface-2)' }} />
    </li>
  );
}

/** ALWAYS RENDERED, NEVER SWAPPED FOR A DIFFERENT CARD — the earlier version hid this ENTIRELY
 *  below `rows.length > 1`, and `BlockedStamp` elsewhere on the page only fires off a SEPARATE
 *  coverage signal that does not cover every reason a chart is thin. The two thresholds disagreeing
 *  is exactly how a shop WITH real visits saw neither the real chart nor any placeholder for staff
 *  («متأكد في مؤشرات اساسا؟»). Now: real rows always show at full colour; below two rows the
 *  WHOLE CARD mutes (opacity + a touch of grayscale) and carries the stamp + a plain explanation,
 *  its real shape still fully visible underneath — «تظهر بشكلها الفعلي بالكامل بس بلون باهت شوية». */
function BranchCompare({ branches, session }: { branches: Branches; session?: Session }) {
  const rows = (branches.rows ?? []).slice(0, 6);
  const max = Math.max(1, ...rows.map((r) => r.visits ?? 0));
  const thin = rows.length < 2;
  return (
    <div className="relative flex flex-col gap-3 overflow-hidden rounded-2xl p-4 transition-opacity" style={{
      background: 'var(--sh-surface)', boxShadow: cardShadow, border: '1px solid var(--sh-line)',
      opacity: thin ? 0.6 : 1, filter: thin ? 'grayscale(0.35)' : undefined,
    }}>
      {thin ? <StampBadge /> : null}
      <h3 className="flex items-center gap-1 text-[13px] font-semibold pt-2">
        مقارنة الفروع
        {session ? <AssistantHint session={session} anchor="shop.branch_compare" /> : null}
      </h3>
      <ul className="flex flex-col gap-2.5">
        {rows.length ? rows.map((r, i) => {
          const pct = Math.round(((r.visits ?? 0) / max) * 100);
          return (
            <li key={r.branch_id} className="flex flex-col gap-1">
              <div className="flex items-center justify-between text-[12.5px]">
                <span className="flex items-center gap-1.5 font-medium">
                  <RankBadge n={i + 1} />
                  {r.name || r.branch_id || 'بلا اسم'}
                  {/* THE AGGREGATE HERO NUMBER, PER BRANCH — a chain reading 46% overall can be
                      one branch at 70% carrying one at 20%, invisible until it is broken out. Same
                      colour language «التسرّب» already uses: coral means low, teal means high. */}
                  {typeof r.return_rate === 'number' ? <RatePill rate={r.return_rate} label="عودة" /> : null}
                </span>
                <span dir="ltr" style={{ color: 'var(--sh-ink-faint)', fontVariantNumeric: 'tabular-nums' }}>{r.visits ?? 0} زيارة · {r.customers ?? 0} عميلاً</span>
              </div>
              <div className="h-2 overflow-hidden rounded-full" style={{ background: 'var(--sh-surface-2)' }}>
                <div className="h-full rounded-full" style={{ width: `${pct}%`, background: 'linear-gradient(90deg,var(--sh-violet),var(--sh-teal))' }} />
              </div>
            </li>
          );
        }) : <GhostRow label="لا فروع مسجَّلة بعد" />}
      </ul>
      {branches.unknown ? <p className="text-[11px]" style={{ color: 'var(--sh-ink-faint)' }}>{branches.unknown} زيارة بلا فرع محدَّد — لا تُحتسب لأي فرع.</p> : null}
      {thin ? (
        <p className="text-[11px]" style={{ color: 'var(--sh-ink-faint)' }}>
          {rows.length === 0 ? 'لا نقارن الفروع بعد — يحتاج فرعان فأكثر بزيارات حقيقية.'
            : 'فرع واحد فعّال حتى الآن — المقارنة تحتاج فرعاً ثانياً بزيارات حقيقية.'}
        </p>
      ) : branches.can_rank === false ? (
        <p className="text-[11px]" style={{ color: 'var(--sh-ink-faint)' }}>لا نرتّب الفروع بعد — الفترة قصيرة، والمقارنة الآن تظلم الأحدث.</p>
      ) : null}
    </div>
  );
}

/** THE STAFF EQUIVALENT OF `BranchCompare` ABOVE, same shape, same always-visible/muted treatment —
 *  the metric chosen is visits + distinct customers PLUS a return rate computed on the
 *  EMPLOYEE'S OWN slice of visits (`operator_rows` in tick.py), so "72% عودة" here means the
 *  customer came back to THIS person specifically, not to the shop in general. Fairness was the
 *  point of asking. */
function StaffCompare({ rows, unknown, canRank, session }: { rows: OperatorRow[]; unknown?: number; canRank?: boolean; session?: Session }) {
  const top = [...rows].sort((a, b) => (b.visits ?? 0) - (a.visits ?? 0)).slice(0, 6);
  const max = Math.max(1, ...top.map((r) => r.visits ?? 0));
  const thin = top.length < 2;
  return (
    <div className="relative flex flex-col gap-3 overflow-hidden rounded-2xl p-4 transition-opacity" style={{
      background: 'var(--sh-surface)', boxShadow: cardShadow, border: '1px solid var(--sh-line)',
      opacity: thin ? 0.6 : 1, filter: thin ? 'grayscale(0.35)' : undefined,
    }}>
      {thin ? <StampBadge /> : null}
      <h3 className="flex items-center gap-1 text-[13px] font-semibold pt-2">
        مقارنة الموظفين
        {session ? <AssistantHint session={session} anchor="shop.staff_compare" /> : null}
      </h3>
      <ul className="flex flex-col gap-2.5">
        {top.length ? top.map((r, i) => {
          const pct = Math.round(((r.visits ?? 0) / max) * 100);
          const label = (r.name || r.operator_id || 'بلا اسم').trim();
          const initial = label ? label[0] : '؟';
          return (
            <li key={r.operator_id} className="flex flex-col gap-1">
              <div className="flex items-center justify-between text-[12.5px]">
                <span className="flex items-center gap-1.5 font-medium">
                  <RankBadge n={i + 1} />
                  <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-[11px] font-bold"
                        style={{ background: 'var(--sh-violet-soft, var(--sh-surface-2))', color: 'var(--sh-violet-deep)' }}>
                    {initial}
                  </span>
                  {label}
                  {typeof r.return_rate === 'number' ? <RatePill rate={r.return_rate} label="عودة له" /> : null}
                </span>
                <span dir="ltr" style={{ color: 'var(--sh-ink-faint)', fontVariantNumeric: 'tabular-nums' }}>{r.visits ?? 0} زيارة · {r.customers ?? 0} عميلاً</span>
              </div>
              <div className="h-2 overflow-hidden rounded-full" style={{ background: 'var(--sh-surface-2)' }}>
                <div className="h-full rounded-full" style={{ width: `${pct}%`, background: 'linear-gradient(90deg,var(--sh-violet),var(--sh-teal))' }} />
              </div>
            </li>
          );
        }) : <GhostRow label="لا موظفون منسوبون بعد" />}
      </ul>
      {unknown ? <p className="text-[11px]" style={{ color: 'var(--sh-ink-faint)' }}>{unknown} زيارة بلا موظف محدَّد — لا تُحتسب لأحد.</p> : null}
      {thin ? (
        <p className="text-[11px]" style={{ color: 'var(--sh-ink-faint)' }}>
          {top.length === 0 ? 'لا نقارن الموظفين بعد — يحتاج موظفان فأكثر بزيارات منسوبة لهم.'
            : 'موظف واحد منسوب حتى الآن — المقارنة تحتاج موظفاً ثانياً بزيارات حقيقية.'}
        </p>
      ) : canRank === false ? (
        <p className="text-[11px]" style={{ color: 'var(--sh-ink-faint)' }}>لا نرتّب الموظفين بعد — الفترة قصيرة، والمقارنة الآن تظلم الأحدث.</p>
      ) : null}
    </div>
  );
}

function Section({ title, hint, children, folded = false, session, helpAnchor }: { title: string; hint?: string; children: React.ReactNode; folded?: boolean; session?: Session; helpAnchor?: string }) {
  const empty = useMemo(() => {
    const arr = Array.isArray(children) ? children : [children];
    return arr.every((c) => c === null || c === undefined || c === false);
  }, [children]);
  if (empty) return null;
  if (folded) {
    return (
      <details className="group rounded-2xl" style={{ background: 'var(--sh-surface)', boxShadow: cardShadow }}>
        <summary className="flex cursor-pointer list-none items-center justify-between p-4 text-[13px] font-semibold">
          <span className="flex items-center gap-1">
            {title}{hint ? <span className="mr-2 text-[11px] font-normal" style={{ color: 'var(--sh-ink-soft)' }}>{hint}</span> : null}
            {session && helpAnchor ? <AssistantHint session={session} anchor={helpAnchor} /> : null}
          </span>
          {/* THE ONLY VISUAL CUE THIS WAS EXPANDABLE AT ALL used to be the cursor on hover — a
              chevron is the one universal signal for "there is more below", and it turns with the
              element's own open state via `group`, no extra state to keep in sync. */}
          <ChevronDown size={16} className="shrink-0 transition-transform group-open:rotate-180" style={{ color: 'var(--sh-ink-faint)' }} />
        </summary>
        <div className="flex flex-col gap-3 p-4 pt-0">{children}</div>
      </details>
    );
  }
  return (
    <section className="flex flex-col gap-2.5">
      <h2 className="flex items-center gap-1 px-1 text-[13px] font-bold">
        {title}{hint ? <span className="mr-2 text-[11px] font-normal" style={{ color: 'var(--sh-ink-soft)' }}>{hint}</span> : null}
        {session && helpAnchor ? <AssistantHint session={session} anchor={helpAnchor} /> : null}
      </h2>
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
      <h2 className="mb-3 flex items-center gap-1 text-[12px] font-semibold" style={{ color: 'var(--sh-ink-soft)' }}>
        آخر الزيارات
        <AssistantHint session={session} anchor="shop.recent_visits" />
      </h2>
      {isLoading(recent) ? <Skeleton height={64} />
      : hasFailed(recent) ? <EmptyState title="تعذّرت قراءة آخر الزيارات" description="والخلل عندنا — الزيارات محفوظة. أعد المحاولة بعد قليل." />
      : recent.length === 0 ? (
        <EmptyState title="لم تُسجَّل زيارة بعد" description="من هنا تبدأ كل مؤشرات الصفحة تتكوّن."
                    action={<Link to="/visit" className="rounded-full px-4 py-2 text-[12.5px] font-semibold text-white" style={{ background: 'var(--sh-violet)' }}>سجّل أول زيارة</Link>} />
      )
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
