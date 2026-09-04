/**
 * تذاكر — صفحة مستقلة بالشريط الجانبي لتتبّع التذاكر عبر المنصة، لا داخل مودال عميل واحد فقط
 * (طلب صريح: "نبغ نسوي على الشريط الجانب صفحة متخصصة للتذاكر وتتابع التذاكر"). عنصر سادس
 * تشغيلي عمداً — يخالف قيد "5 إلى 6" الأصلي بـAdminNav.tsx، والمستخدم وافق صراحةً على رفع
 * السقف لوضوح الفصل بدل دمجها تحت "العملاء والدعم".
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
import { Search } from 'lucide-react';
import { Input } from '../rj-ui/Field';
import { NoActionAvailable } from './NoActionAvailable';
import { TicketsTab } from './CustomerDetail';
import { allActions, fetchCatalog, type AdminCatalog } from './catalog';
import type { Tenant } from './CustomerList';
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

  const filtered = useMemo(() => {
    if (tenants === 'loading' || tenants === 'failed') return [];
    const q = query.trim();
    return q ? tenants.filter((t) => t.name.includes(q) || t.slug.includes(q)) : tenants;
  }, [tenants, query]);

  if (catalog === 'loading') return <p className="p-6 text-sm text-text-secondary">جارٍ التحميل…</p>;
  if (catalog === 'failed') return <p role="alert" className="p-6 text-danger">تعذّرت قراءة كتالوج الإدارة.</p>;

  return (
    <div className="flex flex-col gap-4 p-6">
      <h1 className="text-2xl leading-tight tracking-tight">تذاكر</h1>

      {selected ? (
        <div className="flex flex-col gap-3">
          <button type="button" onClick={() => setSelected(null)} className="self-start text-label text-brand">
            ← اختيار عميل آخر
          </button>
          <h2 className="font-medium">{selected.name}</h2>
          <TicketsTab session={session} tenant={selected} catalog={catalog} />
        </div>
      ) : (
        <div className="flex flex-col gap-3">
          <div className="relative min-w-64 max-w-sm">
            <Search size={15} className="pointer-events-none absolute inset-y-0 start-3 my-auto text-text-muted" />
            <Input value={query} onChange={(e) => setQuery(e.target.value)}
                  placeholder="ابحث باسم العميل…" className="ps-8" />
          </div>
          {tenants === 'loading' ? <p className="text-sm text-text-secondary">جارٍ التحميل…</p>
           : tenants === 'failed' ? <p role="alert" className="text-danger text-sm">تعذّرت القراءة.</p>
           : !listAction ? <NoActionAvailable catalog={catalog} permissionTitle="لا صلاحية لديك لعرض قائمة العملاء" />
           : filtered.length === 0 ? <p className="text-sm text-text-muted">لا نتائج.</p>
           : (
            <div className="flex flex-col gap-2">
              {filtered.map((t) => (
                <button key={t.id} type="button" onClick={() => setSelected(t)}
                        className="flex items-center justify-between gap-2 rounded-lg bg-surface-2 p-3 text-sm text-start hover:bg-surface-3">
                  <span>{t.name}</span>
                  <span dir="ltr" className="text-label text-text-muted">{t.slug}</span>
                </button>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
