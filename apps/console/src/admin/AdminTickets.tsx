/**
 * تذاكر — صندوق وارد موحّد عبر كل المستأجرين، لا اختيار محل أولاً. أول نسخة كانت رحلة
 * "اختر عميل → شوف تذاكره" لأن ticket-service وقتها كان يطلب tenant إلزامياً على كل قراءة —
 * طلبنا صراحة مسار عابر للمستأجرين (v0.18.21)، والمستخدم أكّد إنه هذا اللي يبيه بالضبط: تذاكر
 * مباشرة وفلاتر عليها، بلا ضغطة على عميل قبلها.
 *
 * قيد حقيقي من الخادم، لا نقص بالواجهة: `tenant` صار اختيارياً لكن لا بحث بلا أي فلتر إطلاقاً —
 * قاعدة بياناتهم ترفض where فاضٍ (تسريب عابر للمستأجرين بخطأ كتابة واحد)، نفس قاعدة
 * billing.list_invoices الموجودة أصلاً بمنتجنا. فالفلتر الافتراضي status=open محقَّق دائماً —
 * "أعطني الوارد النشط الآن"، بلا اختيار محل.
 *
 * فلتر المحل نفسه مضاف الآن كفلتر حقيقي (كان مفقوداً — المسار يقبله فعلاً، اسمه فقط ما كان
 * معروضاً كخيار بالواجهة). موظف الدعم اللي يبي "تذاكر هذا المحل تحديداً" كان يضطر يقرأ عمود
 * الاسم بكل صف بعينه؛ الآن يختاره من قائمة ويصفّي عليه مباشرة، نفس فلاتر الحالة/النوع/الأولوية.
 *
 * التسمية بكل صفّ: كل تذكرة تحمل tenant الخاص بها (مؤكَّد من الفريق الشريك) — نجيب tenant.list
 * مرة وحدة لبناء خارطة id→اسم للعرض ولخيارات فلتر المحل.
 *
 * تفاصيل تذكرة واحدة تبقى مسار منفصل ومتعمَّد (tenant + ticket_id معاً) — لا محتوى كامل (نص+ردود)
 * بصندوق الوارد نفسه، metadata فقط (id/type/status/priority/تواريخ/مسؤول)، بتصميم من الفريق
 * الشريك: قراءة عابرة للمستأجرين تعرض محتوى كامل لكل تذكرة دفعة وحدة نطاق أوسع مما نحتاجه فعلاً.
 *
 * العلاقة بتذاكر المسوّقين (spec وصف-بوابة-المسوقين.md §13): منفصلة تماماً عن هذي الشاشة —
 * الدعم الفني هنا يملك صلاحية إشراف (platform.tickets) تفوق كل شيء بلا حاجة موافقة، بينما
 * المسوّق يرى فقط عبر ShareGrant محدود النوع لمحلاته المُحالة. لا تعارض ولا تداخل: هذي شاشة
 * الإشراف الكامل، شاشة المسوّق منفصلة كلياً بـapps/console/src/affiliates/AffiliateTools.tsx.
 *
 * والعلاقة بتبويب "التذاكر والدعم" داخل ملف عميل واحد (CustomerDetail.tsx's own TicketsTab):
 * ليست تكراراً — تلك الشاشة تعرض تذاكر محل واحد بالذات وأنت أصلاً بصفحته (مفيدة حتى بعد إضافة
 * فلتر المحل هنا، توفّر التنقّل)؛ هذي الشاشة صندوق وارد النشاط الآن عبر المنصة كلها، بلا اختيار
 * محل أولاً — سؤالان مختلفان حقيقيان، لا شاشة زائدة عن الحاجة.
 */
import { useEffect, useMemo, useState } from 'react';
import { CircleAlert, Clock, Ticket } from 'lucide-react';
import { Badge } from '../rj-ui/Badge';
import { Input, Select } from '../rj-ui/Field';
import { KpiCard } from '../rj-ui/KpiCard';
import { Table, type TableColumn } from '../rj-ui/Table';
import { NoActionAvailable } from './NoActionAvailable';
import {
  TicketDetailView, statusTone,
  type TicketSummary, type TicketDetail, type TicketEvent,
} from './CustomerDetail';
import { allActions, fetchCatalog, type AdminCatalog } from './catalog';
import type { Tenant } from './CustomerList';
import { req, type AdminSession } from './api';

interface TicketFilters { status: string; type: string; priority: string; assignee: string; tenant: string; }
const DEFAULT_FILTERS: TicketFilters = { status: 'open', type: '', priority: '', assignee: '', tenant: '' };

function sweepQuery(f: TicketFilters, cursor?: string): string {
  const p = new URLSearchParams();
  if (f.status) p.set('status', f.status);
  if (f.type) p.set('type', f.type);
  if (f.priority) p.set('priority', f.priority);
  if (f.assignee) p.set('assignee', f.assignee);
  if (f.tenant) p.set('tenant', f.tenant);
  p.set('limit', '50');
  if (cursor) p.set('cursor', cursor);
  return p.toString();
}

export function AdminTickets({ session }: { session: AdminSession }) {
  const [catalog, setCatalog] = useState<AdminCatalog | 'loading' | 'failed'>('loading');
  const [tenants, setTenants] = useState<Tenant[]>([]);
  const [filters, setFilters] = useState<TicketFilters>(DEFAULT_FILTERS);
  const [tickets, setTickets] = useState<TicketSummary[] | 'loading' | 'failed'>('loading');
  const [cursor, setCursor] = useState<string | undefined>(undefined);
  const [loadingMore, setLoadingMore] = useState(false);
  const [selected, setSelected] = useState<TicketSummary | null>(null);
  const [detail, setDetail] = useState<{ ticket: TicketDetail; events: TicketEvent[] } | 'loading' | 'failed' | null>(null);

  useEffect(() => {
    fetchCatalog(session).then(setCatalog).catch(() => setCatalog('failed'));
  }, [session]);

  const listAction = catalog !== 'loading' && catalog !== 'failed'
    ? allActions(catalog).find((a) => a.id === 'tickets.platform_inbox') : undefined;
  const detailAction = catalog !== 'loading' && catalog !== 'failed'
    ? allActions(catalog).find((a) => a.id === 'tickets.platform_detail') : undefined;
  const tenantListAction = catalog !== 'loading' && catalog !== 'failed'
    ? allActions(catalog).find((a) => a.id === 'tenant.list') : undefined;

  // نفس القائمة تخدم غرضين الآن: عرض الاسم بكل صف، وخيارات فلتر المحل.
  useEffect(() => {
    if (!tenantListAction) return;
    req<{ tenants: Tenant[] }>(tenantListAction.path, 'GET', undefined, session.access_token)
      .then((r) => setTenants(r.tenants)).catch(() => {});
    // eslint-disable-next-line react-hooks/exhaustive-deps -- tenantListAction identity is stable per catalog load
  }, [tenantListAction]);
  const tenantName = useMemo(() => {
    const m = new Map(tenants.map((t) => [t.id, t.name]));
    return (id?: string) => (id ? (m.get(id) ?? id) : '—');
  }, [tenants]);

  useEffect(() => {
    if (!listAction) { setTickets('failed'); return; }
    req<{ tickets: TicketSummary[]; cursor?: string }>(
      `${listAction.path}?${sweepQuery(filters)}`, 'GET', undefined, session.access_token)
      .then((r) => { setTickets(r.tickets); setCursor(r.cursor); }).catch(() => setTickets('failed'));
    setSelected(null);
    setDetail(null);
    // eslint-disable-next-line react-hooks/exhaustive-deps -- refetches on any filter change
  }, [listAction, filters]);

  function loadMore() {
    if (!listAction || !cursor || tickets === 'loading' || tickets === 'failed') return;
    setLoadingMore(true);
    req<{ tickets: TicketSummary[]; cursor?: string }>(
      `${listAction.path}?${sweepQuery(filters, cursor)}`, 'GET', undefined, session.access_token)
      .then((r) => { setTickets((prev) => (prev === 'loading' || prev === 'failed' ? r.tickets : [...prev, ...r.tickets])); setCursor(r.cursor); })
      .finally(() => setLoadingMore(false));
  }

  useEffect(() => {
    if (!selected) return;
    if (!detailAction || !selected.tenant) { setDetail('failed'); return; }
    setDetail('loading');
    const path = detailAction.path.replace(/\{[^}]*\}/, encodeURIComponent(selected.id));
    req<{ ticket: TicketDetail; events: TicketEvent[] }>(
      `${path}?tenant=${encodeURIComponent(selected.tenant)}`, 'GET', undefined, session.access_token)
      .then((r) => setDetail({ ticket: r.ticket, events: r.events })).catch(() => setDetail('failed'));
  }, [selected, detailAction, session.access_token]);

  const distinct = (key: 'status' | 'type' | 'priority'): string[] => {
    const vals = new Set<string>(tickets !== 'loading' && tickets !== 'failed' ? tickets.map((t) => t[key]).filter(Boolean) : []);
    if (filters[key]) vals.add(filters[key]);
    return Array.from(vals).sort();
  };

  if (catalog === 'loading') return <p className="p-6 text-sm text-text-secondary">جارٍ التحميل…</p>;
  if (catalog === 'failed') return <p role="alert" className="p-6 text-danger">تعذّرت قراءة كتالوج الإدارة.</p>;
  if (!listAction) return <div className="p-6"><NoActionAvailable catalog={catalog} permissionTitle="هذه الشاشة ليست ضمن صلاحياتك" /></div>;

  if (selected) {
    return (
      <div className="flex flex-col gap-4 p-6">
        <div className="flex items-center gap-3">
          <button type="button" onClick={() => setSelected(null)} className="text-label text-brand">
            ← تذاكر
          </button>
          <span className="text-text-muted">/</span>
          <h1 className="text-lg font-medium">{tenantName(selected.tenant)}</h1>
        </div>
        {detail === 'loading' || detail === null ? <p className="text-sm text-text-secondary">جارٍ التحميل…</p>
         : detail === 'failed' ? <p role="alert" className="text-danger text-sm">تعذّرت القراءة.</p>
         : <TicketDetailView ticket={detail.ticket} events={detail.events} />}
      </div>
    );
  }

  // مؤشرات من الصفحة المعروضة الآن — نفس انضباط CustomerDetail.tsx's own TicketsTab: لا رقم
  // يوهم بأنه إجمالي شامل عبر المنصة، هذي الصفحة الحالية فقط.
  const shownTickets = tickets === 'loading' || tickets === 'failed' ? [] : tickets;
  const escalated = shownTickets.filter((t) => statusTone(t.status) === 'danger').length;
  const pending = shownTickets.filter((t) => statusTone(t.status) === 'warning').length;

  const columns: TableColumn<TicketSummary>[] = [
    { key: 'tenant', header: 'المحل', render: (t) => <span className="font-medium">{tenantName(t.tenant)}</span> },
    { key: 'id', header: 'التذكرة', hideOnCard: true, render: (t) => <span dir="ltr" className="font-mono text-text-muted">{t.id}</span> },
    { key: 'type', header: 'النوع', render: (t) => t.type || '—' },
    { key: 'priority', header: 'الأولوية', hideOnCard: true, render: (t) => t.priority || '—' },
    { key: 'updated', header: 'آخر تحديث', render: (t) => <span dir="ltr" className="text-label text-text-secondary">{new Date(t.updated).toLocaleString('ar-SA')}</span> },
    { key: 'status', header: 'الحالة', render: (t) => <Badge tone={statusTone(t.status)}>{t.status}</Badge> },
  ];

  return (
    <div className="flex flex-col gap-4 p-6">
      <h1 className="text-2xl leading-tight tracking-tight">تذاكر</h1>

      {shownTickets.length > 0 ? (
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
          <KpiCard icon={<Ticket size={18} />} label="المعروضة" value={shownTickets.length} tone="neutral" />
          <KpiCard icon={<CircleAlert size={18} />} label="مصعَّدة" value={escalated} tone={escalated > 0 ? 'danger' : 'neutral'} />
          <KpiCard icon={<Clock size={18} />} label="بالانتظار" value={pending} tone={pending > 0 ? 'warning' : 'neutral'} />
        </div>
      ) : null}

      <div className="flex flex-wrap items-center gap-2">
        <Select value={filters.tenant} onChange={(e) => setFilters((f) => ({ ...f, tenant: e.target.value }))}
               className="w-auto min-w-40" aria-label="فلترة بالمحل">
          <option value="">كل المحلات</option>
          {tenants.map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}
        </Select>
        <Select value={filters.status} onChange={(e) => setFilters((f) => ({ ...f, status: e.target.value }))}
               className="w-auto min-w-32" aria-label="فلترة بالحالة">
          <option value="">كل الحالات</option>
          {distinct('status').map((s) => <option key={s} value={s}>{s}</option>)}
        </Select>
        <Select value={filters.type} onChange={(e) => setFilters((f) => ({ ...f, type: e.target.value }))}
               className="w-auto min-w-32" aria-label="فلترة بالنوع">
          <option value="">كل الأنواع</option>
          {distinct('type').map((s) => <option key={s} value={s}>{s}</option>)}
        </Select>
        <Select value={filters.priority} onChange={(e) => setFilters((f) => ({ ...f, priority: e.target.value }))}
               className="w-auto min-w-32" aria-label="فلترة بالأولوية">
          <option value="">كل الأولويات</option>
          {distinct('priority').map((s) => <option key={s} value={s}>{s}</option>)}
        </Select>
        <Input value={filters.assignee} onChange={(e) => setFilters((f) => ({ ...f, assignee: e.target.value }))}
              placeholder="المسؤول…" className="w-36" aria-label="فلترة بالمسؤول" />
      </div>
      {!filters.status && !filters.type && !filters.priority && !filters.assignee && !filters.tenant ? (
        <p role="alert" className="text-sm text-danger">
          لازم فلتر واحد على الأقل — لا قراءة عابرة لكل المستأجرين بلا حدود، نفس قاعدة الفواتير.
        </p>
      ) : null}

      <Table columns={columns} rows={tickets} getRowId={(t) => `${t.tenant}:${t.id}`} onRowClick={setSelected}
            emptyTitle="لا تذاكر تطابق هذي الفلاتر" failedTitle="تعذّرت قراءة التذاكر" />
      {cursor ? (
        <button type="button" onClick={loadMore} disabled={loadingMore}
                className="self-center text-label text-brand disabled:opacity-50">
          {loadingMore ? 'جارٍ التحميل…' : 'حمّل المزيد'}
        </button>
      ) : null}
    </div>
  );
}
