/**
 * تذاكر — صفحة مستقلة بالشريط الجانبي لتتبّع التذاكر عبر المنصة، لا داخل مودال عميل واحد فقط
 * (طلب صريح: "نبغ نسوي على الشريط الجانب صفحة متخصصة للتذاكر وتتابع التذاكر"). عنصر سادس
 * تشغيلي عمداً — يخالف قيد "5 إلى 6" الأصلي بـAdminNav.tsx، والمستخدم وافق صراحةً على رفع
 * السقف لوضوح الفصل بدل دمجها تحت "العملاء والدعم".
 *
 * جدول اختيار العميل هنا يطابق عمداً جدول CustomerList.tsx (نفس عمود الحالة، نفس KpiCard، نفس
 * EmptyState) — لا قائمة أزرار مرتجلة. أول نسخة كانت أزراراً بسيطة بلا حالة ولا KPIs، وطلعت
 * "بدائية جداً... مو طريقة إدارة تذاكر عالمية" — نص هذا التصحيح، لا تكرار الخطأ بشاشة قادمة.
 *
 * لا مسار "كل التذاكر بلا مستأجر" — عمداً من الفريق الشريك: `tenant` مطلوب على كلا مساري
 * ticket-service (422 بدونه)، لأن قائمة عابرة لكل المستأجرين بلا حدود بوّابة تسريب بيانات
 * شخصية، نفس منطق `billing.list_plans`'s own tenant filter. فالشاشة هنا اختيار مستأجر أولاً
 * (نفس tenant.list) ثم TicketsTab نفسها المُصدَّرة من CustomerDetail.tsx، بلا تكرار منطق. تغذية
 * "أحدث التذاكر عبر كل المنصة" تحتاج قراراً منفصلاً (نطاق قراءة أوسع) لو احتجناها لاحقاً.
 *
 * العلاقة بتذاكر المسوّقين (spec وصف-بوابة-المسوقين.md §13): منفصلة تماماً عن هذي الشاشة —
 * الدعم الفني هنا يملك صلاحية إشراف (platform.tickets) تفوق كل شيء بلا حاجة موافقة، بينما
 * المسوّق يرى فقط عبر ShareGrant محدود النوع لمحلاته المُحالة. لا تعارض ولا تداخل: هذي شاشة
 * الإشراف الكامل، شاشة المسوّق منفصلة كلياً بـapps/console/src/affiliates/AffiliateTools.tsx.
 */
import { useEffect, useMemo, useState } from 'react';
import { Search, Users, Sparkles } from 'lucide-react';
import { Input } from '../rj-ui/Field';
import { Badge } from '../rj-ui/Badge';
import { KpiCard } from '../rj-ui/KpiCard';
import { EmptyState } from '../rj-ui/EmptyState';
import { NoActionAvailable } from './NoActionAvailable';
import { TicketsTab } from './CustomerDetail';
import { allActions, fetchCatalog, type AdminCatalog } from './catalog';
import { TENANT_STATUS_META, type Tenant } from './CustomerList';
import { req, type AdminSession } from './api';

export function AdminTickets({ session }: { session: AdminSession }) {
  const [catalog, setCatalog] = useState<AdminCatalog | 'loading' | 'failed'>('loading');
  const [tenants, setTenants] = useState<Tenant[] | 'loading' | 'failed'>('loading');
  const [query, setQuery] = useState('');
  const [selected, setSelected] = useState<Tenant | null>(null);

  useEffect(() => {
    fetchCatalog(session).then(setCatalog).catch(() => setCatalog('failed'));
  }, [session]);

  const listAction = catalog !== 'loading' && catalog !== 'failed'
    ? allActions(catalog).find((a) => a.id === 'tenant.list') : undefined;

  useEffect(() => {
    if (!listAction) return;
    req<{ tenants: Tenant[] }>(listAction.path, 'GET', undefined, session.access_token)
      .then((r) => setTenants(r.tenants)).catch(() => setTenants('failed'));
    // eslint-disable-next-line react-hooks/exhaustive-deps -- listAction identity is stable per catalog load
  }, [listAction]);

  const rows = Array.isArray(tenants) ? tenants : [];
  const kpis = useMemo(() => ({
    total: rows.length,
    active: rows.filter((t) => t.status === 'active').length,
  }), [rows]);

  const shown = useMemo(() => {
    const q = query.trim().toLowerCase();
    return q ? rows.filter((t) => t.name.toLowerCase().includes(q) || t.slug.toLowerCase().includes(q)) : rows;
  }, [rows, query]);

  if (catalog === 'loading') return <p className="p-6 text-sm text-text-secondary">جارٍ التحميل…</p>;
  if (catalog === 'failed') return <p role="alert" className="p-6 text-danger">تعذّرت قراءة كتالوج الإدارة.</p>;

  if (selected) {
    return (
      <div className="flex flex-col gap-4 p-6">
        <div className="flex items-center gap-3">
          <button type="button" onClick={() => setSelected(null)} className="text-label text-brand">
            ← تذاكر
          </button>
          <span className="text-text-muted">/</span>
          <h1 className="text-lg font-medium">{selected.name}</h1>
        </div>
        <TicketsTab session={session} tenant={selected} catalog={catalog} />
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-5 p-6">
      <h1 className="text-2xl leading-tight tracking-tight">تذاكر</h1>

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <KpiCard icon={<Users size={18} />} label="إجمالي العملاء" value={kpis.total} tone="neutral" />
        <KpiCard icon={<Sparkles size={18} />} label="نشطة الآن" value={kpis.active} tone="success" />
      </div>

      <div className="relative min-w-64 max-w-sm">
        <Search size={15} className="pointer-events-none absolute inset-y-0 start-3 my-auto text-text-muted" />
        <Input value={query} onChange={(e) => setQuery(e.target.value)}
              placeholder="ابحث باسم العميل…" className="ps-8" />
      </div>

      {tenants === 'loading' ? <p className="text-sm text-text-secondary">جارٍ التحميل…</p>
       : tenants === 'failed' ? <p role="alert" className="text-danger text-sm">تعذّرت قراءة قائمة العملاء.</p>
       : !listAction ? <NoActionAvailable catalog={catalog} permissionTitle="هذه الشاشة ليست ضمن صلاحياتك" />
       : shown.length === 0 ? <EmptyState title="لا عملاء مطابقون" description="جرّب تغيير البحث." />
       : (
        <div className="overflow-x-auto rounded-card border border-border-subtle">
          <table className="w-full text-sm">
            <thead className="bg-surface-2 text-label text-text-secondary">
              <tr>
                <th className="p-3 text-start">المنشأة</th>
                <th className="p-3 text-start">الحالة</th>
                <th className="p-3 text-start">تاريخ الانضمام</th>
              </tr>
            </thead>
            <tbody>
              {shown.map((t) => {
                const meta = TENANT_STATUS_META[t.status] ?? TENANT_STATUS_META.pending;
                return (
                  <tr key={t.id} onClick={() => setSelected(t)}
                     className="cursor-pointer border-t border-border-subtle hover:bg-surface-2">
                    <td className="p-3 font-medium">{t.name}</td>
                    <td className="p-3"><Badge tone={meta.tone}>{meta.label}</Badge></td>
                    <td className="p-3 text-text-secondary" dir="ltr">{t.created_at?.slice(0, 10)}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
