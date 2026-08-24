/**
 * الرئيسية (لوحة القيادة) — المرحلة 4: أول أرقام حقيقية غير مُخترعة، محسوبة من إجراءين معلَنَين
 * أصلاً (`billing.platform_invoices`, `tenant.list`) — انظر `platformMetrics.ts`. باقي البنود
 * الـ35 (الاحتفاظ المجمَّع، صحة واتساب، تنبيهات...) تُبنى بمراحل لاحقة، ولا رقم يُعرَض هنا قبل
 * أن يكون له مصدر حقيقي.
 */
import { useEffect, useState } from 'react';
import { AlertTriangle, DollarSign, ShieldAlert, TrendingUp, Store, Sparkles } from 'lucide-react';
import { Badge } from '../rj-ui/Badge';
import { KpiCard } from '../rj-ui/KpiCard';
import { riyalsLabel } from '../money';
import { allActions, fetchCatalog, type AdminCatalog } from './catalog';
import {
  activeTeamCount, backupHealth, monthRevenueHalalas, openTicketsCount,
  pendingAffiliateApplications, suspiciousLogins, tenantCounts, unreachableServices,
  type TenantCounts,
} from './platformMetrics';
import type { AdminSession } from './api';

interface Loaded {
  revenueThisMonth: number | null;    // halalas, null when the caller lacks platform.billing
  revenueLastMonth: number | null;
  tenants: TenantCounts | null;       // null when the caller lacks platform.tenants
  actionCount: number;
  unreachable: string[];
  suspiciousActors: { actor: string; count: number }[] | null;   // null = no audit.query capability
  pendingApplications: number | null;
  openTickets: { count: number; atLeast: boolean } | null;
  backupCritical: number | null;    // count of services in critical backup state
  backupAlerts: { service: string; severity: 'degraded' | 'critical'; reason: string }[];
  activeTeam: { count: number; atLeast: boolean } | null;
}

export function AdminHome({ session }: { session: AdminSession }) {
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

      const [revNow, revBefore, tenants, suspicious, pending, tickets, backup, team] = await Promise.all([
        monthRevenueHalalas(session, catalog, 0),
        monthRevenueHalalas(session, catalog, 1),
        tenantCounts(session, catalog),
        suspiciousLogins(session, catalog),
        pendingAffiliateApplications(session, catalog),
        openTicketsCount(session, catalog),
        backupHealth(session, catalog),
        activeTeamCount(session, catalog),
      ]);
      if (cancelled) return;
      setState({
        revenueThisMonth: revNow.ok ? revNow.halalas : null,
        revenueLastMonth: revBefore.ok ? revBefore.halalas : null,
        tenants: tenants.ok ? tenants.counts : null,
        actionCount: allActions(catalog).length,
        unreachable: unreachableServices(catalog),
        suspiciousActors: suspicious.ok ? suspicious.actors : null,
        pendingApplications: pending.ok ? pending.count : null,
        openTickets: tickets.ok ? { count: tickets.count, atLeast: tickets.atLeast } : null,
        backupCritical: backup.ok ? backup.body.summary.critical + backup.body.summary.degraded : null,
        backupAlerts: backup.ok ? backup.body.alerts : [],
        activeTeam: team.ok ? { count: team.count, atLeast: team.atLeast } : null,
      });
    })();
    return () => { cancelled = true; };
  }, [session]);

  return (
    <div className="flex flex-col gap-4 p-6">
      <h1 className="text-2xl leading-tight tracking-tight">الرئيسية</h1>

      {state === 'loading' ? (
        <p className="text-sm text-text-secondary">جارٍ التحميل…</p>
      ) : state === 'failed' ? (
        <p role="alert" className="text-danger">تعذّرت قراءة كتالوج الإدارة. أعد المحاولة بعد قليل.</p>
      ) : (
        <>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
            {state.revenueThisMonth != null ? (
              <KpiCard icon={<DollarSign size={18} />} tone="accent" label="الإيراد الكلي هالشهر"
                      value={riyalsLabel(state.revenueThisMonth)}
                      hint={revenueDelta(state.revenueThisMonth, state.revenueLastMonth)} />
            ) : null}
            {state.tenants != null ? (
              <>
                <KpiCard icon={<Store size={18} />} tone="neutral" label="إجمالي المحلات النشطة"
                        value={String(state.tenants.active)} hint={`من أصل ${state.tenants.total}`} />
                <KpiCard icon={<Sparkles size={18} />} tone="success" label="محلات جديدة هالشهر"
                        value={String(state.tenants.newThisMonth)} />
              </>
            ) : null}
            {state.pendingApplications != null ? (
              <KpiCard icon={<TrendingUp size={18} />} tone="accent" label="طلبات مسوّقين معلّقة"
                      value={String(state.pendingApplications)} />
            ) : null}
            {state.openTickets != null ? (
              <KpiCard icon={<AlertTriangle size={18} />} tone="warning" label="تذاكر مفتوحة"
                      value={`${state.openTickets.count}${state.openTickets.atLeast ? '+' : ''}`} />
            ) : null}
            {state.activeTeam != null ? (
              <KpiCard icon={<Sparkles size={18} />} tone="neutral" label="أعضاء فريق الإدارة النشطين"
                      value={`${state.activeTeam.count}${state.activeTeam.atLeast ? '+' : ''}`} />
            ) : null}
          </div>

          {state.unreachable.length > 0 || (state.backupCritical ?? 0) > 0 || (state.suspiciousActors?.length ?? 0) > 0 ? (
            <div className="flex flex-col gap-2 rounded-card border border-danger/30 bg-danger-soft p-4">
              <h2 className="flex items-center gap-1.5 font-semibold text-danger-on-soft">
                <ShieldAlert size={16} /> تنبيهات فورية
              </h2>
              <ul className="flex flex-col gap-1.5 text-sm">
                {state.unreachable.map((svc) => (
                  <li key={svc} className="flex items-center gap-1.5">
                    <Badge tone="danger">خدمة</Badge> {svc} لم تُجب عند بناء الكتالوج.
                  </li>
                ))}
                {state.backupAlerts.map((a, i) => (
                  <li key={i} className="flex items-center gap-1.5">
                    <Badge tone={a.severity === 'critical' ? 'danger' : 'warning'}>نسخة احتياطية</Badge>
                    {a.service} — {a.reason}
                  </li>
                ))}
                {(state.suspiciousActors ?? []).map((s) => (
                  <li key={s.actor} className="flex items-center gap-1.5">
                    <Badge tone="danger">دخول</Badge> {s.count} محاولة دخول فاشلة من {s.actor} آخر 24 ساعة.
                  </li>
                ))}
              </ul>
            </div>
          ) : null}

          {state.revenueThisMonth == null && state.tenants == null ? (
            <p className="text-sm text-text-secondary">
              حسابك لا يحمل صلاحية {'"'}platform.billing{'"'} ولا {'"'}platform.tenants{'"'} —
              لا أرقام مالية لعرضها لك.
            </p>
          ) : null}

          <p className="flex items-center gap-1.5 text-sm text-text-secondary">
            <TrendingUp size={14} /> {state.actionCount} إجراء إداري متاح لصلاحياتك الحالية.
          </p>
        </>
      )}
    </div>
  );
}

function revenueDelta(nowHalalas: number, beforeHalalas: number | null): string {
  if (beforeHalalas == null) return '';
  if (beforeHalalas === 0) return nowHalalas > 0 ? 'أول إيراد مسجَّل' : '';
  const pct = Math.round(((nowHalalas - beforeHalalas) / beforeHalalas) * 100);
  const sign = pct > 0 ? '+' : '';
  return `${sign}${pct}٪ عن الشهر الماضي`;
}
