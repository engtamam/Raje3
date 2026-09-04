/**
 * جدول العملاء — المرحلة ١ من "العملاء والدعم" (انظر AdminCustomers.tsx's own header). يجيب كل
 * المستأجرين (tenant.list، لا فلترة خادم بعد — TENANT_LIST_LIMIT=100 حالياً، بحث اسم يصير محلياً
 * بالمتصفح إلى أن يُضاف معامل بحث بالخادم) ويربطهم بأحدث اشتراك لكل واحد عبر خمس استدعاءات
 * bulk (حالة بحالة: trialing/active/past_due/paused/canceled) بدل N+1 طلب لكل صف — نفس منطق
 * billing.platform_subscriptions المتاح فعلاً بفلتر tenant، هنا نستخدمه بفلتر status فقط ونبني
 * خارطة tenant→اشتراك بالمتصفح.
 *
 * البحث بالجوال غير متاح بعد — لا معامل بحث ولا فهرس جوال على المستأجر نفسه بالخادم حالياً (الجوال
 * يعيش على عضويات identity-service، لا على سجل tenant). موثّق كفجوة معروفة، لا تظاهر بدعمها.
 */
import { useEffect, useMemo, useState } from 'react';
import { Search, Users, Sparkles, AlertTriangle, Ban } from 'lucide-react';
import { Input } from './../rj-ui/Field';
import { Badge } from './../rj-ui/Badge';
import { Segmented } from './../rj-ui/Segmented';
import { KpiCard } from './../rj-ui/KpiCard';
import { EmptyState } from './../rj-ui/EmptyState';
import { NoActionAvailable } from './NoActionAvailable';
import { allActions, fetchCatalog, type AdminAction, type AdminCatalog } from './catalog';
import { req, type AdminSession } from './api';
import { CustomerDetail } from './CustomerDetail';

export interface Tenant {
  id: string; slug: string; name: string;
  status: 'pending' | 'active' | 'suspended' | 'deleted';
  created_at: string; updated_at: string;
}

export interface Subscription {
  id: string; tenant: string; plan_id: string;
  status: 'trialing' | 'active' | 'past_due' | 'paused' | 'canceled';
  current_period_end: number; trial_end: number;
}

const TENANT_STATUS_META: Record<Tenant['status'], { label: string; tone: 'neutral' | 'success' | 'danger' | 'warning' }> = {
  pending: { label: 'قيد التفعيل', tone: 'warning' },
  active: { label: 'نشطة', tone: 'success' },
  suspended: { label: 'معلَّقة', tone: 'danger' },
  deleted: { label: 'محذوفة', tone: 'neutral' },
};

export const SUB_STATUS_META: Record<Subscription['status'], { label: string; tone: 'neutral' | 'success' | 'danger' | 'warning' | 'accent' }> = {
  trialing: { label: 'تجريبي', tone: 'accent' },
  active: { label: 'نشط', tone: 'success' },
  past_due: { label: 'متأخر الدفع', tone: 'danger' },
  paused: { label: 'متوقف', tone: 'warning' },
  canceled: { label: 'ملغى', tone: 'neutral' },
};

const SUB_STATUSES: Subscription['status'][] = ['trialing', 'active', 'past_due', 'paused', 'canceled'];

export function CustomerList({ session }: { session: AdminSession }) {
  const [catalog, setCatalog] = useState<AdminCatalog | 'loading' | 'failed'>('loading');
  const [tenants, setTenants] = useState<Tenant[] | 'loading' | 'failed'>('loading');
  const [subsByTenant, setSubsByTenant] = useState<Map<string, Subscription>>(new Map());
  const [query, setQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState<Tenant['status'] | 'all'>('all');
  const [openTenant, setOpenTenant] = useState<Tenant | null>(null);

  useEffect(() => {
    fetchCatalog(session).then(setCatalog).catch(() => setCatalog('failed'));
  }, [session]);

  const listAction = catalog !== 'loading' && catalog !== 'failed'
    ? allActions(catalog).find((a) => a.id === 'tenant.list') : undefined;
  const subsAction = catalog !== 'loading' && catalog !== 'failed'
    ? allActions(catalog).find((a) => a.id === 'billing.platform_subscriptions') : undefined;

  useEffect(() => {
    if (!listAction) return;
    setTenants('loading');
    req<{ tenants: Tenant[] }>(listAction.path, 'GET', undefined, session.access_token)
      .then((r) => setTenants(r.tenants))
      .catch(() => setTenants('failed'));
    // eslint-disable-next-line react-hooks/exhaustive-deps -- listAction identity is stable per catalog load
  }, [listAction]);

  useEffect(() => {
    if (!subsAction) return;
    // خمس طلبات bulk (حالة بحالة) بدل استدعاء منفصل لكل مستأجر — نفس المسار، فلتر status بدل tenant.
    Promise.all(SUB_STATUSES.map((st) =>
      req<{ subscriptions: Subscription[] }>(
        `${subsAction.path}?status=${st}&limit=1000`, 'GET', undefined, session.access_token)
        .then((r) => r.subscriptions).catch(() => [] as Subscription[])))
      .then((groups) => {
        const map = new Map<string, Subscription>();
        for (const group of groups) for (const s of group) map.set(s.tenant, s);
        setSubsByTenant(map);
      });
    // eslint-disable-next-line react-hooks/exhaustive-deps -- subsAction identity is stable per catalog load
  }, [subsAction]);

  // كل الـhooks قبل أي return مبكر — ترتيبها يجب يثبت بكل تصيير (Rules of Hooks)، وإلا React
  // يخلط حالة hook بأخرى بين تصييرة "جارٍ التحميل" (بلا useMemo) وتصييرة البيانات (معه).
  const rows = Array.isArray(tenants) ? tenants : [];
  const kpis = useMemo(() => {
    const active = rows.filter((t) => t.status === 'active').length;
    const trialing = [...subsByTenant.values()].filter((s) => s.status === 'trialing').length;
    const pastDue = [...subsByTenant.values()].filter((s) => s.status === 'past_due').length;
    const suspended = rows.filter((t) => t.status === 'suspended').length;
    return { total: rows.length, active, trialing, pastDue, suspended };
  }, [rows, subsByTenant]);

  if (catalog === 'loading') return <p className="p-6 text-sm text-text-secondary">جارٍ التحميل…</p>;
  if (catalog === 'failed') return <p role="alert" className="p-6 text-danger">تعذّرت قراءة كتالوج الإدارة.</p>;
  if (!listAction) {
    return <NoActionAvailable catalog={catalog} permissionTitle="هذه الشاشة ليست ضمن صلاحياتك" />;
  }

  const shown = rows.filter((t) => {
    if (statusFilter !== 'all' && t.status !== statusFilter) return false;
    if (query.trim() && !t.name.toLowerCase().includes(query.trim().toLowerCase())
       && !t.slug.toLowerCase().includes(query.trim().toLowerCase())) return false;
    return true;
  });

  return (
    <div className="flex flex-col gap-5 p-6">
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-5">
        <KpiCard icon={<Users size={18} />} label="إجمالي العملاء" value={kpis.total} tone="neutral" />
        <KpiCard icon={<Sparkles size={18} />} label="نشطة الآن" value={kpis.active} tone="success" />
        <KpiCard icon={<Sparkles size={18} />} label="تجريبي" value={kpis.trialing} tone="accent" />
        <KpiCard icon={<AlertTriangle size={18} />} label="متأخر الدفع" value={kpis.pastDue} tone="danger" />
        <KpiCard icon={<Ban size={18} />} label="معلَّقة" value={kpis.suspended} tone="warning" />
      </div>

      <div className="flex flex-wrap items-center gap-3">
        <div className="relative min-w-64 flex-1">
          <Search size={15} className="pointer-events-none absolute inset-y-0 start-3 my-auto text-text-muted" />
          <Input value={query} onChange={(e) => setQuery(e.target.value)}
                placeholder="ابحث بالاسم…" className="ps-8" />
        </div>
        <Segmented value={statusFilter} onChange={(v) => setStatusFilter(v as Tenant['status'] | 'all')}
                  options={[
                    { value: 'all', label: 'الكل' },
                    { value: 'active', label: 'نشطة' },
                    { value: 'pending', label: 'قيد التفعيل' },
                    { value: 'suspended', label: 'معلَّقة' },
                    { value: 'deleted', label: 'محذوفة' },
                  ]} />
      </div>

      {/* البحث بالجوال غير متاح — لا فهرس جوال على المستأجر بالخادم حالياً، انظر تعليق الملف. */}
      <p className="text-label text-text-muted">البحث بالاسم فقط حالياً — البحث برقم الجوال يحتاج ربطاً جديداً بالخادم.</p>

      {tenants === 'loading' ? (
        <p className="text-sm text-text-secondary">جارٍ التحميل…</p>
      ) : tenants === 'failed' ? (
        <p role="alert" className="text-danger text-sm">تعذّرت قراءة قائمة العملاء.</p>
      ) : shown.length === 0 ? (
        <EmptyState title="لا عملاء مطابقون" description="جرّب تغيير البحث أو الفلتر." />
      ) : (
        <div className="overflow-x-auto rounded-card border border-border-subtle">
          <table className="w-full text-sm">
            <thead className="bg-surface-2 text-label text-text-secondary">
              <tr>
                <th className="p-3 text-start">المنشأة</th>
                <th className="p-3 text-start">الحالة</th>
                <th className="p-3 text-start">الاشتراك</th>
                <th className="p-3 text-start">تاريخ الانضمام</th>
              </tr>
            </thead>
            <tbody>
              {shown.map((t) => {
                const meta = TENANT_STATUS_META[t.status] ?? TENANT_STATUS_META.pending;
                const sub = subsByTenant.get(t.id);
                const subMeta = sub ? SUB_STATUS_META[sub.status] : null;
                return (
                  <tr key={t.id} onClick={() => setOpenTenant(t)}
                     className="cursor-pointer border-t border-border-subtle hover:bg-surface-2">
                    <td className="p-3 font-medium">{t.name}</td>
                    <td className="p-3"><Badge tone={meta.tone}>{meta.label}</Badge></td>
                    <td className="p-3">
                      {subMeta ? <Badge tone={subMeta.tone}>{subMeta.label}</Badge>
                       : <span className="text-text-muted">بلا اشتراك</span>}
                    </td>
                    <td className="p-3 text-text-secondary" dir="ltr">{t.created_at?.slice(0, 10)}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {openTenant ? (
        <CustomerDetail session={session} tenant={openTenant} subscription={subsByTenant.get(openTenant.id) ?? null}
                        catalog={catalog} onClose={() => setOpenTenant(null)} />
      ) : null}
    </div>
  );
}

export function findCustomerAction(catalog: AdminCatalog, id: string): AdminAction | undefined {
  return allActions(catalog).find((a) => a.id === id);
}
