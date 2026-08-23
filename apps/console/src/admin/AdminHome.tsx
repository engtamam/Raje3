/**
 * الرئيسية (لوحة القيادة) — المرحلة ٤: أول أرقام حقيقية غير مُخترعة، محسوبة من إجراءين معلَنَين
 * أصلاً (`billing.platform_invoices`, `tenant.list`) — انظر `platformMetrics.ts`. باقي البنود
 * الـ٣٥ (الاحتفاظ المجمَّع، صحة واتساب، تنبيهات...) تُبنى بمراحل لاحقة، ولا رقم يُعرَض هنا قبل
 * أن يكون له مصدر حقيقي.
 */
import { useEffect, useState } from 'react';
import { DollarSign, TrendingUp, Store, Sparkles } from 'lucide-react';
import { KpiCard } from '../rj-ui/KpiCard';
import { riyalsLabel } from '../money';
import { fetchCatalog, type AdminCatalog } from './catalog';
import { monthRevenueHalalas, tenantCounts, type TenantCounts } from './platformMetrics';
import type { AdminSession } from './api';

interface Loaded {
  revenueThisMonth: number | null;    // halalas, null when the caller lacks platform.billing
  revenueLastMonth: number | null;
  tenants: TenantCounts | null;       // null when the caller lacks platform.tenants
  actionCount: number;
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

      const [revNow, revBefore, tenants] = await Promise.all([
        monthRevenueHalalas(session, catalog, 0),
        monthRevenueHalalas(session, catalog, 1),
        tenantCounts(session, catalog),
      ]);
      if (cancelled) return;
      setState({
        revenueThisMonth: revNow.ok ? revNow.halalas : null,
        revenueLastMonth: revBefore.ok ? revBefore.halalas : null,
        tenants: tenants.ok ? tenants.counts : null,
        actionCount: catalog.actions.length,
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
          </div>

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
