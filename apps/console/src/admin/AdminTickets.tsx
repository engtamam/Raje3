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
 * التسمية بكل صفّ: كل تذكرة تحمل tenant الخاص بها (مؤكَّد من الفريق الشريك) — نجيب tenant.list
 * مرة وحدة لبناء خارطة id→اسم للعرض فقط، لا لتصفية القائمة.
 *
 * تفاصيل تذكرة واحدة تبقى مسار منفصل ومتعمَّد (tenant + ticket_id معاً) — لا محتوى كامل (نص+ردود)
 * بصندوق الوارد نفسه، metadata فقط (id/type/status/priority/تواريخ/مسؤول)، بتصميم من الفريق
 * الشريك: قراءة عابرة للمستأجرين تعرض محتوى كامل لكل تذكرة دفعة وحدة نطاق أوسع مما نحتاجه فعلاً.
 *
 * العلاقة بتذاكر المسوّقين (spec وصف-بوابة-المسوقين.md §13): منفصلة تماماً عن هذي الشاشة —
 * الدعم الفني هنا يملك صلاحية إشراف (platform.tickets) تفوق كل شيء بلا حاجة موافقة، بينما
 * المسوّق يرى فقط عبر ShareGrant محدود النوع لمحلاته المُحالة. لا تعارض ولا تداخل: هذي شاشة
 * الإشراف الكامل، شاشة المسوّق منفصلة كلياً بـapps/console/src/affiliates/AffiliateTools.tsx.
 */
import { useEffect, useMemo, useState } from 'react';
import { Badge } from '../rj-ui/Badge';
import { Input, Select } from '../rj-ui/Field';
import { EmptyState } from '../rj-ui/EmptyState';
import { NoActionAvailable } from './NoActionAvailable';
import {
  TicketDetailView, statusTone,
  type TicketSummary, type TicketDetail, type TicketEvent,
} from './CustomerDetail';
import { allActions, fetchCatalog, type AdminCatalog } from './catalog';
import type { Tenant } from './CustomerList';
import { req, type AdminSession } from './api';

interface TicketFilters { status: string; type: string; priority: string; assignee: string; }
const DEFAULT_FILTERS: TicketFilters = { status: 'open', type: '', priority: '', assignee: '' };

function sweepQuery(f: TicketFilters, cursor?: string): string {
  const p = new URLSearchParams();
  if (f.status) p.set('status', f.status);
  if (f.type) p.set('type', f.type);
  if (f.priority) p.set('priority', f.priority);
  if (f.assignee) p.set('assignee', f.assignee);
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

  // للعرض فقط — لا تصفية. لو تعذّرت القراءة نعرض معرّف التينانت الخام بدل الاسم، لا نمنع الشاشة.
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

  return (
    <div className="flex flex-col gap-4 p-6">
      <h1 className="text-2xl leading-tight tracking-tight">تذاكر</h1>

      <div className="flex flex-wrap items-center gap-2">
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
      {!filters.status && !filters.type && !filters.priority && !filters.assignee ? (
        <p role="alert" className="text-sm text-danger">
          لازم فلتر واحد على الأقل — لا قراءة عابرة لكل المستأجرين بلا حدود، نفس قاعدة الفواتير.
        </p>
      ) : null}

      {tickets === 'loading' ? <p className="text-sm text-text-secondary">جارٍ التحميل…</p>
       : tickets === 'failed' ? <p role="alert" className="text-danger text-sm">تعذّرت القراءة.</p>
       : tickets.length === 0 ? <EmptyState title="لا تذاكر تطابق هذي الفلاتر" />
       : (
        <div className="flex flex-col gap-2">
          {tickets.map((t) => (
            <button key={`${t.tenant}:${t.id}`} type="button" onClick={() => setSelected(t)}
                    className="flex flex-wrap items-center justify-between gap-2 rounded-lg bg-surface-2 p-3 text-sm text-start hover:bg-surface-3">
              <span className="font-medium">{tenantName(t.tenant)}</span>
              <span dir="ltr" className="font-mono text-text-muted">{t.id}</span>
              {t.type ? <span className="text-label text-text-muted">{t.type}</span> : null}
              {t.priority ? <span className="text-label text-text-muted">{t.priority}</span> : null}
              <span dir="ltr" className="text-label text-text-muted">{new Date(t.updated).toLocaleString('ar-SA')}</span>
              <Badge tone={statusTone(t.status)}>{t.status}</Badge>
            </button>
          ))}
          {cursor ? (
            <button type="button" onClick={loadMore} disabled={loadingMore}
                    className="self-center text-label text-brand disabled:opacity-50">
              {loadingMore ? 'جارٍ التحميل…' : 'حمّل المزيد'}
            </button>
          ) : null}
        </div>
      )}
    </div>
  );
}
