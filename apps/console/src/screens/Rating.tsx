/**
 * «التقييم» — its own rail section now (nav.ts), not a tab under «عملائي» any more. Two tabs:
 * «نظرة عامة» (the shop's own pulse plus a fair staff comparison) and «التقييمات» (every rated
 * visit, one by one) — the real React build of the approved violet mockup
 * (rating-app-screen-pitch-violet.html), reading real data instead of the mockup's fixture rows.
 *
 * WHY A FAIR COMPARISON, NOT A RAW LEADERBOARD ALONE. A star average punishes a busy operator's
 * larger sample and rewards one barely rated at all — see `StaffQuadrant.tsx`'s own header note.
 * The switchable podium below stays honest the same way: it never blends metrics into one score,
 * and the active metric's own name sits right above it, so nobody reads "الأكثر زيارات" as
 * "الأفضل تقييماً".
 */
import { useEffect, useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import {
  Star, Users, MessageSquareText, Download, ChevronLeft, ExternalLink,
} from 'lucide-react';
import { PageHeader } from '../rj-ui/PageHeader';
import { KpiCard } from '../rj-ui/KpiCard';
import { Segmented } from '../rj-ui/Segmented';
import { TabBar } from '../rj-ui/TabBar';
import { Button } from '../rj-ui/Button';
import { Badge } from '../rj-ui/Badge';
import { Skeleton } from '../rj-ui/Skeleton';
import { EmptyState } from '../rj-ui/EmptyState';
import { Table, type TableColumn } from '../rj-ui/Table';
import { StaffQuadrant, StaffQuadrantLegend, type StaffQuadrantRow } from '../rj-ui/StaffQuadrant';
import { action, call, type Catalog } from '../catalog';
import { fresh } from '../renew';
import type { Session } from '../session';
import { scopeQuery } from '../branch-scope';
import { useOperatorI18n, tf } from '../operator-i18n';
import './rating-i18n';

interface StaffRow {
  operator_id: string; operator_name: string; visits: number; ratings: number;
  average_rating: number; no_show_rate?: number;
}

interface RatingRow {
  id: string; customer_id: string; customer_name: string; customer_phone: string;
  operator_id: string; operator_name: string; rating: number; feedback_text: string;
  rated_at: number; rating_handled_at: number; rating_handled_note: string;
}

const API_BASE = (import.meta.env.VITE_API_BASE ?? '').replace(/\/$/, '');

type Period = 'week' | 'month' | 'quarter' | 'custom';

/** Today, as the date input's own `value` shape (`yyyy-mm-dd`, the browser's local calendar day —
 *  same "his own clock, not UTC's" reasoning every other date picker in this console already
 *  follows, e.g. AdminFinance.tsx's own `type="date"` fields). */
function todayInput(): string {
  return new Date().toISOString().slice(0, 10);
}
function daysAgoInput(days: number): string {
  return new Date(Date.now() - days * 86_400_000).toISOString().slice(0, 10);
}

/** [since, until], in unix seconds. For the three fixed windows this is just "N days back from
 *  now"; for `custom` it is exactly the two calendar days he picked — `until` extended to the END
 *  of that day, since a date input names a whole day and a report for "حتى 30" that silently
 *  stopped at 00:00 that same day would read as missing its own last day entirely. `null` means
 *  the custom range is not usable yet (empty, or reversed) — the caller must not fetch on it. */
function rangeFor(
  period: Period, now: number, custom?: { since: string; until: string },
): { since: number; until: number } | null {
  if (period === 'custom') {
    if (!custom?.since || !custom?.until) return null;
    const since = Math.floor(new Date(`${custom.since}T00:00:00`).getTime() / 1000);
    const until = Math.floor(new Date(`${custom.until}T00:00:00`).getTime() / 1000) + 86_400 - 1;
    if (!Number.isFinite(since) || !Number.isFinite(until) || until < since) return null;
    return { since, until };
  }
  const days = period === 'week' ? 7 : period === 'month' ? 30 : 90;
  return { since: now - days * 86_400, until: now };
}

const METRICS = {
  visits: { labelKey: 'rating.leaderboard.metric.visits', unitKey: 'rating.leaderboard.visitsUnit', value: (s: StaffRow) => s.visits },
  ratings: { labelKey: 'rating.leaderboard.metric.ratings', unitKey: 'rating.leaderboard.ratingsUnit', value: (s: StaffRow) => s.ratings },
  avg: { labelKey: 'rating.leaderboard.metric.avg', unitKey: 'rating.leaderboard.avgUnit', value: (s: StaffRow) => s.average_rating },
} as const;
type MetricKey = keyof typeof METRICS;

function StarRow({ n, size = 14 }: { n: number; size?: number }) {
  return (
    <span dir="ltr" className="flex items-center gap-0.5">
      {Array.from({ length: 5 }, (_, i) => (
        <Star key={i} size={size} className={i < Math.round(n) ? 'fill-warning text-warning' : 'text-text-muted'} />
      ))}
    </span>
  );
}

/** The podium's own medal — real artwork ported verbatim from the approved violet mockup
 *  (`.rating-medal`/`.rating-podium-card` in index.css), not a simplified stand-in: rank 1's disc
 *  is brand violet with a sheen sweep across the whole card, ranks 2/3 stay the universal silver/
 *  bronze every ranking convention already uses (unrelated to brand identity). WESTERN DIGITS in
 *  the disc — the mockup's own Eastern-Arabic numerals do not survive `ci/check_deploy_wiring.py`'s
 *  platform-wide "digits are always western" rule, the one deliberate departure from the mockup's
 *  literal pixels, forced by a real, pre-existing platform constraint rather than by convenience. */
function RankMedal({ rank }: { rank: 1 | 2 | 3 }) {
  return (
    <div className={`rating-medal rank-${rank}`}>
      <svg className="rating-medal-ribbon" viewBox="0 0 26 30" aria-hidden>
        <path className="a" d="M4 0h8l6 20-10-6-10 6L4 0Z" />
        <path className="b" d="M14 0h8l-6 20-4-2 2-18Z" />
      </svg>
      <div className="rating-medal-disc">{rank}</div>
    </div>
  );
}

export function RatingScreen({ session, catalog, branch }: { session: Session; catalog: Catalog; branch: string }) {
  const { t } = useOperatorI18n();
  const [tab, setTab] = useState<'overview' | 'ratings'>('overview');
  const [period, setPeriod] = useState<Period>('month');
  const [customSince, setCustomSince] = useState(daysAgoInput(30));
  const [customUntil, setCustomUntil] = useState(todayInput());
  const [staff, setStaff] = useState<StaffRow[] | null | undefined>(undefined);
  const [metric, setMetric] = useState<MetricKey>('avg');
  const [exporting, setExporting] = useState(false);
  const [exportError, setExportError] = useState('');

  const perfAction = action(catalog, 'operations.staff_performance');
  const exportAction = action(catalog, 'operations.staff_performance_export');
  const range = rangeFor(period, Math.floor(Date.now() / 1000), { since: customSince, until: customUntil });

  useEffect(() => {
    if (!perfAction) { setStaff(null); return; }
    // NOT YET A USABLE RANGE (an incomplete or reversed custom pick) — leave `staff` exactly as it
    // was rather than fetching on it; `OverviewTab` reads `rangeInvalid` on its own to show the one
    // sentence for this, distinct from "read failed" and from "no data this period".
    if (!range) return;
    setStaff(undefined);
    call<{ staff: StaffRow[]; error?: string }>(session, perfAction, { ...range, ...scopeQuery(branch) })
      .then((x) => setStaff(x.error ? null : (x.staff ?? [])))
      .catch(() => setStaff(null));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [session, catalog, branch, period, customSince, customUntil]);

  // A RAW fetch, NOT `call()` — the response is a PDF byte stream, not the JSON `call()` always
  // parses (same reasoning AdminDisputeReports.tsx's own export button already settled on).
  const exportReport = async () => {
    if (!exportAction || exporting || !range) return;
    setExporting(true); setExportError('');
    try {
      const { since, until } = range;
      const bearer = await fresh(session.token);
      const res = await fetch(`${API_BASE}${exportAction.path}`, {
        method: exportAction.method,
        headers: { Authorization: `Bearer ${bearer}`, 'Content-Type': 'application/json' },
        body: JSON.stringify({ since, until, ...scopeQuery(branch), file_format: 'pdf' }),
      });
      if (!res.ok) throw new Error('export failed');
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url; a.download = 'staff-performance.pdf';
      document.body.appendChild(a); a.click(); a.remove();
      URL.revokeObjectURL(url);
    } catch {
      setExportError(t('rating.exportFailed'));
    } finally {
      setExporting(false);
    }
  };

  return (
    <div className="flex flex-col gap-4 p-4">
      <PageHeader
        icon={Star}
        title={t('rating.title')}
        action={(
          <Segmented
            size="sm"
            value={period}
            onChange={setPeriod}
            ariaLabel={t('rating.title')}
            options={[
              { value: 'week', label: t('rating.period.week') },
              { value: 'month', label: t('rating.period.month') },
              { value: 'quarter', label: t('rating.period.quarter') },
              { value: 'custom', label: t('rating.period.custom') },
            ]}
          />
        )}
      />
      <p className="-mt-2 text-sm text-text-secondary">{t('rating.subtitle')}</p>

      {period === 'custom' ? (
        <div className="flex flex-wrap items-end gap-3">
          <label className="flex flex-col gap-1">
            <span className="text-xs font-medium text-text-secondary">{t('rating.customSince')}</span>
            <input type="date" dir="ltr" value={customSince} max={customUntil}
                   onChange={(e) => setCustomSince(e.target.value)}
                   className="h-9 rounded-lg bg-surface-2 px-2 text-sm" />
          </label>
          <label className="flex flex-col gap-1">
            <span className="text-xs font-medium text-text-secondary">{t('rating.customUntil')}</span>
            <input type="date" dir="ltr" value={customUntil} min={customSince} max={todayInput()}
                   onChange={(e) => setCustomUntil(e.target.value)}
                   className="h-9 rounded-lg bg-surface-2 px-2 text-sm" />
          </label>
          {!range ? <p className="text-xs text-danger">{t('rating.customRangeInvalid')}</p> : null}
        </div>
      ) : null}

      <TabBar
        fullWidth
        ariaLabel={t('rating.title')}
        value={tab}
        onChange={setTab}
        options={[
          { value: 'overview', label: t('rating.tab.overview') },
          { value: 'ratings', label: t('rating.tab.ratings') },
        ]}
      />

      {tab === 'overview' ? (
        <OverviewTab
          staff={staff} rangeReady={Boolean(range)} metric={metric} setMetric={setMetric}
          exportAvailable={Boolean(exportAction)} exporting={exporting} exportError={exportError}
          onExport={() => void exportReport()}
        />
      ) : (
        <RatingsListTab session={session} catalog={catalog} branch={branch} tab={tab} period={period} />
      )}
    </div>
  );
}

function OverviewTab({ staff, rangeReady, metric, setMetric, exportAvailable, exporting, exportError, onExport }: {
  staff: StaffRow[] | null | undefined;
  /** `false` only for an incomplete/reversed custom date pick — a distinct sentence from "still
   *  loading" and from "read failed", asking him to fix the dates rather than to wait or retry. */
  rangeReady: boolean;
  metric: MetricKey; setMetric: (m: MetricKey) => void;
  exportAvailable: boolean; exporting: boolean; exportError: string;
  onExport: () => void;
}) {
  const { t } = useOperatorI18n();

  if (!rangeReady) {
    return <EmptyState icon={<Star size={20} aria-hidden />} title={t('rating.customRangeInvalid')} description={t('rating.customRangeInvalidDesc')} />;
  }
  if (staff === undefined) return <Skeleton height={280} />;
  if (staff === null) {
    return <EmptyState icon={<Star size={20} aria-hidden />} title={t('rating.readFailed.title')} description={t('rating.readFailed.desc')} />;
  }

  const totalRatings = staff.reduce((sum, s) => sum + s.ratings, 0);
  const weightedAvg = totalRatings > 0
    ? staff.reduce((sum, s) => sum + s.average_rating * s.ratings, 0) / totalRatings
    : 0;

  if (staff.length === 0) {
    return <EmptyState icon={<Star size={20} aria-hidden />} title={t('rating.empty.title')} description={t('rating.empty.desc')} />;
  }

  const ranked = [...staff].sort((a, b) => METRICS[metric].value(b) - METRICS[metric].value(a));
  const podium = ranked.slice(0, 3);
  const rest = ranked.slice(3);
  const quadrantRows: StaffQuadrantRow[] = staff.map((s) => ({
    operator_id: s.operator_id, operator_name: s.operator_name, visits: s.visits,
    ratings: s.ratings, average_rating: s.average_rating,
  }));

  const columns: TableColumn<StaffRow>[] = [
    {
      key: 'operator', header: t('rating.table.operator'),
      render: (s) => (
        <span className="flex items-center gap-2 font-medium">
          <span className="grid size-7 shrink-0 place-items-center rounded-lg bg-accent-soft text-xs font-bold text-accent-on-soft">
            {(s.operator_name || '?')[0]}
          </span>
          {s.operator_name || t('rating.card.noName')}
        </span>
      ),
    },
    { key: 'visits', header: t('rating.table.visits'), render: (s) => <span className="tabular-nums">{s.visits}</span> },
    { key: 'ratings', header: t('rating.table.ratings'), render: (s) => <span className="tabular-nums">{s.ratings}</span> },
    {
      key: 'engagement', header: t('rating.table.engagement'), hideOnCard: true,
      render: (s) => <span className="tabular-nums">%{s.visits > 0 ? Math.round((s.ratings / s.visits) * 100) : 0}</span>,
    },
    {
      key: 'average', header: t('rating.table.average'),
      render: (s) => (
        <span className="flex items-center gap-1.5">
          <StarRow n={s.average_rating} size={12} /> <span className="tabular-nums">{s.average_rating.toFixed(1)}</span>
        </span>
      ),
    },
    {
      key: 'noShow', header: t('rating.table.noShow'), hideOnCard: true,
      render: (s) => (
        <span className="tabular-nums">
          {typeof s.no_show_rate === 'number' ? `%${Math.round(s.no_show_rate * 100)}` : '—'}
        </span>
      ),
    },
  ];

  return (
    <div className="flex flex-col gap-5">
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
        <KpiCard icon={<Star size={18} aria-hidden />} tone="warning"
                value={<>{weightedAvg.toFixed(1)} <span className="text-sm font-normal text-text-secondary">{t('rating.tile.outOf5')}</span></>}
                label={t('rating.tile.avgRating')} />
        <KpiCard icon={<MessageSquareText size={18} aria-hidden />} tone="info"
                value={totalRatings} label={t('rating.tile.totalRatings')} hint={t('rating.tile.ratingsUnit')} />
        <KpiCard icon={<Users size={18} aria-hidden />} tone="accent"
                value={staff.length} label={t('rating.tile.staffCount')} />
      </div>

      <section className="flex flex-col gap-3">
        <div className="flex flex-wrap items-end justify-between gap-2">
          <div>
            <h2 className="text-lg font-bold">{t('rating.leaderboard.title')}</h2>
            <p className="text-xs text-text-secondary">{t('rating.leaderboard.note')}</p>
          </div>
          {exportAvailable ? (
            <Button type="button" variant="outline" size="sm" disabled={exporting} onClick={onExport}>
              <Download size={15} aria-hidden /> {exporting ? t('rating.exporting') : t('rating.export')}
            </Button>
          ) : null}
        </div>
        {exportError ? <p className="text-xs text-danger">{exportError}</p> : null}

        <Segmented
          size="sm"
          value={metric}
          onChange={setMetric}
          ariaLabel={t('rating.leaderboard.title')}
          options={(Object.keys(METRICS) as MetricKey[]).map((k) => ({ value: k, label: t(METRICS[k].labelKey) }))}
        />

        {/* SAME VISUAL ORDER AS THE APPROVED MOCKUP — rank 2 on one side, rank 1 in the middle
            (raised above its neighbours, same as a real podium), rank 3 on the other. */}
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
          {[podium[1], podium[0], podium[2]].map((s, slot) => {
            const rank = ([2, 1, 3] as const)[slot];
            if (!s) return <div key={rank} aria-hidden />;
            return (
              <div key={s.operator_id}
                  className={
                    'rating-podium-card flex flex-col items-center gap-1.5 rounded-card border p-4 text-center shadow-sm ' +
                    (rank === 1 ? 'rank-1' : 'border-border-subtle bg-surface-1') +
                    (rank === 3 ? ' sm:mt-4' : rank === 2 ? ' sm:mt-2' : '')
                  }>
                <RankMedal rank={rank} />
                <p className="font-bold">{s.operator_name || t('rating.card.noName')}</p>
                <p className={'text-sm tabular-nums ' + (rank === 1 ? 'text-accent' : 'text-text-secondary')}>
                  {tf(t, METRICS[metric].unitKey, { n: metric === 'avg' ? s.average_rating.toFixed(1) : METRICS[metric].value(s) })}
                </p>
                <p className={'text-[11px] ' + (rank === 1 ? 'text-[#b7a8ea]' : 'text-text-muted')}>{t(METRICS[metric].labelKey)}</p>
              </div>
            );
          })}
        </div>

        {rest.length > 0 ? (
          <div className="flex flex-col gap-1 rounded-card border border-border-subtle bg-surface-1 p-2">
            {rest.map((s, i) => (
              <div key={s.operator_id} className="flex items-center gap-3 rounded-lg px-2 py-2 text-sm">
                <span className="w-5 text-center font-bold text-text-muted tabular-nums">{i + 4}</span>
                <span className="grid size-7 shrink-0 place-items-center rounded-lg bg-surface-2 text-xs font-bold">{(s.operator_name || '?')[0]}</span>
                <span className="flex-1 font-medium">{s.operator_name || t('rating.card.noName')}</span>
                <span className="text-text-secondary tabular-nums">{tf(t, METRICS[metric].unitKey, { n: metric === 'avg' ? s.average_rating.toFixed(1) : METRICS[metric].value(s) })}</span>
              </div>
            ))}
          </div>
        ) : null}
      </section>

      <section className="flex flex-col gap-2">
        <div>
          <h2 className="text-lg font-bold">{t('rating.quadrant.title')}</h2>
          <p className="text-xs text-text-secondary">{t('rating.quadrant.note')}</p>
        </div>
        <StaffQuadrant rows={quadrantRows} />
        <StaffQuadrantLegend />
      </section>

      <section className="flex flex-col gap-2">
        <h2 className="text-base font-bold">{t('rating.table.title')}</h2>
        <Table columns={columns} rows={staff} getRowId={(s) => s.operator_id} />
      </section>
    </div>
  );
}

function ago(at: number, t: (key: string) => string): string {
  const days = Math.floor((Date.now() / 1000 - at) / 86_400);
  if (days <= 0) return t('rating.ago.today');
  if (days === 1) return t('rating.ago.yesterday');
  if (days === 2) return t('rating.ago.twoDaysAgo');
  return tf(t, 'rating.ago.daysAgo', { n: days });
}

function RatingsListTab({ session, catalog, branch, tab, period }: {
  session: Session; catalog: Catalog; branch: string; tab: string; period: Period;
}) {
  const navigate = useNavigate();
  const location = useLocation();
  const { t } = useOperatorI18n();
  const [stars, setStars] = useState('');
  const [handled, setHandled] = useState('false');
  const [rows, setRows] = useState<RatingRow[] | null | undefined>(undefined);
  const [noteDraft, setNoteDraft] = useState<Record<string, string>>({});
  const [busyId, setBusyId] = useState<string | null>(null);

  const listAction = action(catalog, 'operations.ratings');
  const handleAction = action(catalog, 'operations.mark_rating_handled');

  const load = () => {
    if (!listAction) { setRows(null); return; }
    const query: Record<string, string> = { ...scopeQuery(branch) };
    if (stars) query.stars = stars;
    if (handled) query.handled = handled;
    call<{ ratings: RatingRow[] }>(session, listAction, query)
      .then((x) => setRows(x.ratings ?? []))
      .catch(() => setRows(null));
  };

  useEffect(load, [session, catalog, branch, stars, handled]); // eslint-disable-line react-hooks/exhaustive-deps

  if (!listAction) return null;

  const markHandled = async (id: string) => {
    if (!handleAction || busyId) return;
    setBusyId(id);
    try {
      await call(session, handleAction, { visit_id: id, note: noteDraft[id] ?? '' });
      if (handled === 'false') setRows((cur) => (cur ?? []).filter((r) => r.id !== id));
      else load();
    } catch {
      // A failed mark-handled leaves the row exactly as it was.
    } finally {
      setBusyId(null);
    }
  };

  // SMART BACK-NAVIGATION — the exact tab/filter state this list is in right now, carried through
  // navigation state, never through a component the customer's own page has to know about. Coming
  // back from `/customers/:id` (its own back button reads `location.state?.from`) lands on this
  // same list, same filters, same period — not a fresh, reset screen.
  const backHere = `${location.pathname}?tab=${tab}&stars=${stars}&handled=${handled}&period=${period}`;
  const openCustomer = (customerId: string) => navigate(`/customers/${customerId}`, { state: { from: backHere } });

  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap gap-1">
        {[
          { value: 'false', label: t('rating.filter.unhandled') },
          { value: '', label: t('rating.filter.all') },
          { value: 'true', label: t('rating.filter.handled') },
        ].map((o) => (
          <button key={o.value} type="button" onClick={() => setHandled(o.value)}
                 className={'rounded-full px-3 py-1 text-xs font-medium transition-colors ' +
                   (handled === o.value ? 'bg-info-soft text-info-on-soft' : 'bg-surface-2 text-text-secondary hover:bg-surface-3')}>
            {o.label}
          </button>
        ))}
      </div>
      <div className="flex flex-wrap gap-1">
        {[
          { value: '', label: t('rating.filter.allStars') },
          { value: '5', label: t('rating.filter.star5') }, { value: '4', label: t('rating.filter.star4') },
          { value: '3', label: t('rating.filter.star3') }, { value: '2', label: t('rating.filter.star2') },
          { value: '1', label: t('rating.filter.star1') },
        ].map((o) => (
          <button key={o.value} type="button" onClick={() => setStars(o.value)}
                 className={'rounded-full px-3 py-1 text-xs font-medium transition-colors ' +
                   (stars === o.value ? 'bg-info-soft text-info-on-soft' : 'bg-surface-2 text-text-secondary hover:bg-surface-3')}>
            {o.label}
          </button>
        ))}
      </div>

      {rows === undefined ? (
        <Skeleton height={200} />
      ) : rows === null ? (
        <EmptyState title={t('rating.emptyList.readErrorTitle')} description={t('rating.emptyList.readErrorDesc')} />
      ) : rows.length === 0 ? (
        <EmptyState
          icon={<Star size={22} aria-hidden />}
          title={handled === 'false' ? t('rating.emptyList.unhandledTitle') : t('rating.emptyList.title')}
          description={handled === 'false' ? t('rating.emptyList.unhandledDesc') : t('rating.emptyList.desc')}
        />
      ) : (
        <ul className="flex flex-col gap-2">
          {rows.map((r) => {
            const isHandled = r.rating_handled_at > 0;
            return (
              <li key={r.id} className="flex flex-col gap-2 rounded-card bg-surface-1 p-4 shadow-sm">
                <div className="flex flex-wrap items-start justify-between gap-2">
                  <div className="flex items-center gap-2.5">
                    <span className="grid size-9 shrink-0 place-items-center rounded-lg bg-surface-2 text-xs font-bold text-text-secondary">
                      {(r.customer_name || '?')[0]}
                    </span>
                    <div>
                      <p className="text-sm font-bold">{r.customer_name || t('rating.card.noName')}</p>
                      {r.customer_phone ? <span dir="ltr" className="text-xs text-text-muted">{r.customer_phone}</span> : null}
                    </div>
                  </div>
                  {r.customer_id ? (
                    <Button type="button" variant="outline" size="sm" onClick={() => openCustomer(r.customer_id)}>
                      <ExternalLink size={13} aria-hidden /> {t('rating.card.openProfile')}
                    </Button>
                  ) : null}
                </div>

                <div className="flex items-center justify-between gap-2">
                  <StarRow n={r.rating} />
                  <span className="flex items-center gap-2 text-xs text-text-muted">
                    {r.operator_name ? tf(t, 'rating.card.operatorLabel', { name: r.operator_name }) : ''}
                    <ChevronLeft size={12} aria-hidden />
                    {ago(r.rated_at, t)}
                  </span>
                </div>

                {r.feedback_text ? <p className="text-sm text-text-secondary">{r.feedback_text}</p> : null}

                <div className="flex items-center justify-between gap-2">
                  {isHandled ? (
                    <Badge tone="neutral">{t('rating.card.handled')}</Badge>
                  ) : (
                    <Badge tone="warning">{t('rating.card.unhandled')}</Badge>
                  )}
                  {isHandled ? (
                    r.rating_handled_note ? <p className="text-xs text-text-muted">{r.rating_handled_note}</p> : null
                  ) : handleAction ? (
                    <div className="flex flex-1 items-center gap-2">
                      <input
                        value={noteDraft[r.id] ?? ''}
                        onChange={(e) => setNoteDraft((m) => ({ ...m, [r.id]: e.target.value }))}
                        placeholder={t('rating.card.notePlaceholder')}
                        maxLength={500}
                        className="h-9 flex-1 rounded-lg bg-surface-2 px-2 text-sm"
                      />
                      <Button variant="outline" size="sm" disabled={busyId === r.id} onClick={() => markHandled(r.id)}>
                        {t('rating.card.markHandled')}
                      </Button>
                    </div>
                  ) : null}
                </div>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
