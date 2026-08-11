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
import { TrendingUp, Users, RefreshCw, AlertTriangle } from 'lucide-react';
import { Waiting } from '../Waiting';
import { action, call, type Catalog } from '../catalog';
import type { Session } from '../session';

interface Blocked { indicator: string; message?: string; reason?: string }
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
const HEADLINE: { key: string; label: string; icon: typeof Users; percent?: boolean; suffix?: string }[] = [
  { key: 'return_rate', label: 'نسبة العودة', icon: RefreshCw, percent: true },
  { key: 'active_customers', label: 'عملاء نشطون', icon: Users },
  { key: 'return_cycle_days', label: 'دورة العودة', icon: TrendingUp, suffix: 'يوماً' },
  { key: 'churn_rate', label: 'نسبة التسرّب', icon: AlertTriangle, percent: true },
];

export function LocalScreen({ session, catalog }: { session: Session; catalog: Catalog }) {
  const [data, setData] = useState<Dashboard | null>(null);
  const [failed, setFailed] = useState(false);
  /** Whether HE receives the weekly report. Optimistic, and reverted if the save fails. */
  const [digest, setDigest] = useState(true);

  useEffect(() => {
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

      <div className="flex items-center gap-2 text-sm text-text-secondary">
        <span className="tabular-nums">
          {data.as_of_hours_ago === 0 ? 'محسوبة الآن' : `محسوبة قبل ${data.as_of_hours_ago} ساعة`}
        </span>
        {data.stale ? <Badge tone="warning">قديمة</Badge> : null}
      </div>

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        {HEADLINE.map((h) => {
          const raw = data.values[h.key];
          // ABSENT IS NOT ZERO. A key his plan withheld, or one the snapshot could not compute, is
          // skipped entirely rather than rendered as 0 — see the module note.
          if (typeof raw !== 'number') return null;
          const shown = h.percent ? `${Math.round(raw * 100)}%` : String(raw);
          return (
            <KpiCard
              key={h.key}
              icon={<h.icon size={18} />}
              label={h.label}
              value={h.suffix ? `${shown} ${h.suffix}` : shown}
            />
          );
        })}
      </div>

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

      {data.audience ? (
        // HIS OWN NUMBER, NOT AN ADVERT. Customers who explicitly agreed to receive his offers,
        // sitting there while his plan cannot send one. It is the truest upgrade motivator in the
        // product for exactly that reason, so it stays a LINE and never becomes a banner.
        <p className="rounded-card bg-surface-1 p-4 text-sm shadow-sm">{data.audience.message}</p>
      ) : null}

      {data.teaser?.message ? (
        <p className="rounded-card bg-surface-1 p-4 text-sm shadow-sm">{data.teaser.message}</p>
      ) : null}
    </div>
  );
}
