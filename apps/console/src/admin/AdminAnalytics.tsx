/**
 * التحليل المتقدم — الأشكال والخرائط الحقيقية المطلوبة صراحة ("تكون أشكال وأدوات تحليل
 * قوية وخرائط... أقوى من صفحة محلي"). كل قسم هنا مبني فوق مصدر حقيقي محدَّد بالمرحلة 11، ولا
 * قسم يُعرَض دون التحقق من إتاحته — نفس انضباط بقية `AdminHome.tsx`.
 */
import { useEffect, useState } from 'react';
import { AlertTriangle, DollarSign, TrendingUp, Users } from 'lucide-react';
import { AreaTrend, type TrendPoint } from '../rj-ui/AreaTrend';
import { Heatmap, type HeatmapCell } from '../rj-ui/Heatmap';
import { GeoMap, type GeoPoint } from '../rj-ui/GeoMap';
import { KpiCard } from '../rj-ui/KpiCard';
import { Card } from '../rj-ui/Card';
import { riyalsLabel } from '../money';
import { fetchCatalog, type AdminCatalog } from './catalog';
import {
  affiliateLeaderboard, affiliateStats, branchGeoPoints, leadsGeoPoints, platformInsights,
  type AffiliateStats, type LeaderboardRow, type PlatformInsights,
} from './platformMetrics';
import type { AdminSession } from './api';

interface Loaded {
  insights: { computing: true } | { computing: false; data: PlatformInsights } | null;
  affiliates: AffiliateStats | null;
  leaderboard: LeaderboardRow[];
  leadPoints: GeoPoint[];
  branchPoints: GeoPoint[];
}

export function AdminAnalytics({ session }: { session: AdminSession }) {
  const [state, setState] = useState<Loaded | 'loading' | 'failed'>('loading');

  useEffect(() => {
    let cancelled = false;
    (async () => {
      let catalog: AdminCatalog;
      try {
        catalog = await fetchCatalog(session);
      } catch {
        if (!cancelled) setState('failed');
        return;
      }
      const [insights, affStats, board, leads, branches] = await Promise.all([
        platformInsights(session, catalog),
        affiliateStats(session, catalog),
        affiliateLeaderboard(session, catalog, 5),
        leadsGeoPoints(session, catalog),
        branchGeoPoints(session, catalog),
      ]);
      if (cancelled) return;
      setState({
        insights: insights.ok ? (insights.computing ? { computing: true } : { computing: false, data: insights.data }) : null,
        affiliates: affStats.ok ? affStats.data : null,
        leaderboard: board.ok ? board.rows : [],
        leadPoints: leads.ok ? leads.points : [],
        branchPoints: branches.ok ? branches.points : [],
      });
    })();
    return () => { cancelled = true; };
  }, [session]);

  if (state === 'loading') return <p className="p-6 text-sm text-text-secondary">جارٍ التحميل…</p>;
  if (state === 'failed') return <p role="alert" className="p-6 text-danger">تعذّرت قراءة كتالوج الإدارة.</p>;

  const nothingToShow = !state.insights && !state.affiliates
    && state.leaderboard.length === 0 && state.leadPoints.length === 0 && state.branchPoints.length === 0;
  if (nothingToShow) return null;

  return (
    <div className="flex flex-col gap-4">
      <h2 className="flex items-center gap-1.5 text-lg font-semibold">
        <TrendingUp size={16} /> تحليل متقدم
      </h2>

      {state.insights ? <InsightsSection insights={state.insights} /> : null}
      {state.affiliates || state.leaderboard.length > 0 ? (
        <AffiliatesSection stats={state.affiliates} leaderboard={state.leaderboard} />
      ) : null}
      {state.leadPoints.length > 0 || state.branchPoints.length > 0 ? (
        <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
          {state.leadPoints.length > 0 ? (
            <Card className="flex flex-col gap-2 p-4">
              <h3 className="font-semibold">خريطة العملاء المحتملين</h3>
              <GeoMap points={state.leadPoints} />
            </Card>
          ) : null}
          {state.branchPoints.length > 0 ? (
            <Card className="flex flex-col gap-2 p-4">
              <h3 className="font-semibold">خريطة المحلات الفعلية</h3>
              <GeoMap points={state.branchPoints} />
            </Card>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}

function InsightsSection({ insights }: {
  insights: { computing: true } | { computing: false; data: PlatformInsights };
}) {
  if (insights.computing) {
    return (
      <Card className="p-4 text-sm text-text-secondary">
        ملخص المنصّة الكلي لم يُحسب بعد — يظهر بعد أول دورة تجميع.
      </Card>
    );
  }
  const { data } = insights;
  const trendPoints: TrendPoint[] = (data.retentionSeries ?? []).map((p, i) => ({
    label: p.at ? new Date(p.at * 1000).toLocaleDateString('ar-SA', { month: 'short' }) : String(i),
    value: p.value,
  }));
  const heatCells: HeatmapCell[] = data.peakGrid.map((c) => ({ row: c.day, col: c.hour, value: c.value }));
  const heatRows = Array.from(new Set(data.peakGrid.map((c) => c.day)));
  const heatCols = Array.from(new Set(data.peakGrid.map((c) => c.hour))).sort();

  return (
    <Card className="flex flex-col gap-4 p-4">
      <h3 className="font-semibold">صحة المنصّة والاحتفاظ (عبر {data.tenantsWithSnapshot} محلاً)</h3>
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        {data.returnRate != null ? (
          <KpiCard icon={<TrendingUp size={18} />} tone="info" label="متوسط معدل الاحتفاظ"
                  value={`${Math.round(data.returnRate * 100)}٪`} />
        ) : null}
        {data.atRiskTenantCount != null ? (
          <KpiCard icon={<AlertTriangle size={18} />} tone="warning" label="محلات بخطر انقطاع عملائها"
                  value={String(data.atRiskTenantCount)} />
        ) : null}
      </div>
      {trendPoints.length >= 2 ? (
        <div>
          <p className="mb-1 text-sm text-text-secondary">اتجاه الاحتفاظ (6 نقاط)</p>
          <AreaTrend points={trendPoints} formatValue={(v) => `${Math.round(v * 100)}٪`} />
        </div>
      ) : null}
      {heatCells.length > 0 ? (
        <div>
          <p className="mb-1 text-sm text-text-secondary">خريطة أوقات الذروة عبر المنصّة</p>
          <Heatmap rows={heatRows} cols={heatCols} cells={heatCells} />
        </div>
      ) : null}
    </Card>
  );
}

function AffiliatesSection({ stats, leaderboard }: {
  stats: AffiliateStats | null; leaderboard: LeaderboardRow[];
}) {
  return (
    <Card className="flex flex-col gap-4 p-4">
      <h3 className="font-semibold">المسوّقين والتسويق</h3>
      {stats ? (
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          <KpiCard icon={<Users size={18} />} tone="info" label="مسوّقون نشطون" value={String(stats.activeAffiliates)}
                  hint={`من أصل ${stats.totalAffiliates}`} />
          <KpiCard icon={<DollarSign size={18} />} tone="success" label="الإيراد المُحال عبر القناة"
                  value={riyalsLabel(stats.totalNetRevenueMinor)}
                  hint={stats.revenuePartial ? 'رقم جزئي — بعض المحلات تعذّر قراءتها' : undefined} />
        </div>
      ) : null}
      {leaderboard.length > 0 ? (
        <ul className="flex flex-col gap-2">
          {leaderboard.map((r, i) => (
            <li key={r.affiliateId} className="flex flex-wrap items-center justify-between gap-2 rounded-input border border-border-subtle p-2 text-sm">
              <span className="min-w-0 break-words font-medium">{i + 1}. {r.name || r.affiliateId}</span>
              <span className="text-text-secondary">
                {r.totalReferrals} إحالة · احتفاظ {Math.round(r.retentionRate * 100)}٪
              </span>
            </li>
          ))}
        </ul>
      ) : null}
    </Card>
  );
}
