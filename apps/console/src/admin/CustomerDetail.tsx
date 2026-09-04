/**
 * ملف العميل — نافذة مركزية كبيرة (rj-ui/Modal، size="xl") بستة تبويبات، لا شريط جانبي — طُلب
 * صراحة بدل الشكل الجانبي الأول (انظر AdminCustomers.tsx's own header للخطة الكاملة).
 *
 * المرحلة 1: "نظرة عامة" و"التطبيقات والفوترة" ببيانات حقيقية. المرحلة 2: "السجل والتدقيق" حقيقي
 * كذلك — audit.query يدعم فلتر tenant فعلاً بالخادم، اكتشفنا هذا بالفحص المباشر بعد ما ذكرته
 * خطأً كفجوة بالاقتراح الأول. "الفروع والمستخدمين" جزئياً حقيقي الآن (المرحلة 3) — العدد الفعلي
 * فقط أول ما شُحِن (operations.tenant_capacity) — ثم x/y كامل: الحد يُقرأ من نفس فحص الباقة
 * (`billing entitlements/check`) اللي يمنع المحل أصلاً من تجاوزه عند الإضافة، لا مسار جديد ولا
 * رقم مخترَع.
 *
 * تبويب واتساب (المرحلة 5): سجلّ إرسال الشحنة الفعلي لهذا المحل تحديداً — نفس
 * operations.whatsapp_diagnostics اللي تستخدمه AdminWhatsAppDiagnostics.tsx، هنا بلا إدخال يدوي
 * لمعرّف التينانت (نعرفه أصلاً، العميل مفتوح). لا مسار جديد.
 *
 * تصحيح: القوالب المخصَّصة لكل منشأة موجودة فعلاً، وهذا خطأ ذُكر هنا ولمستخدم المنصة قبل
 * التحقّق من الكود — راجع services/reminders/app/core/custom_templates.py: المالك يكتب نصّه
 * الخاص من تبويب "رسائلي" بالكونسول (screens/Messages.tsx)، يُقدَّم مباشرة لاعتماد Meta على
 * رقمه هو (لا مراجعة منّا بينه وبين Meta)، بحالات draft/pending/approved/rejected/retired وسلسلة
 * إصدارات (تعديل نص معتمَد = تقديم جديد، لا يوقف إرسال القديم). الفجوة الحقيقية الوحيدة المتبقية:
 * لا شاشة إدارية بهذا الملف تعرض للمنصة نصوص محل معيّن أو حالة اعتمادها — المالك يشوفها بشاشته
 * هو فقط، لا فجوة ببناء الميزة نفسها.
 *
 * تبويب التذاكر (المرحلة 4): مسار إداري جديد كلياً من ticket-service (v0.18.20)، بناءً على طلب
 * صريح — GET /api/v1/tickets/admin/tickets(?tenant=) للقائمة، و.../{ticket_id} للتفاصيل الكاملة
 * (نص + ردود)، بصلاحية platform.tickets وحدها (دور tenant/operator يُرفض 403). كل قراءة تُسجَّل
 * fail-closed (ticket.platform_viewed) — شرط طلبناه صراحة، لا اقتراح منهم. فلاتر status/type/
 * priority/assignee والصفحات بـcursor كلها server-side حقيقية (المسار يدعمها فعلاً) — لا فلترة
 * محلية بالمتصفح على قائمة مجتزَأة، ولا سقف وهمي 50 بلا وسيلة تشوف الباقي.
 */
import { useEffect, useState } from 'react';
import { Badge } from './../rj-ui/Badge';
import { Segmented } from './../rj-ui/Segmented';
import { Modal } from './../rj-ui/Modal';
import { Input, Select } from './../rj-ui/Field';
import { req, type AdminSession } from './api';
import type { AdminCatalog } from './catalog';
import { findCustomerAction, SUB_STATUS_META, type Tenant, type Subscription } from './CustomerList';
import { StatusBadge, type DeliveryRow } from './AdminWhatsAppDiagnostics';

interface Invoice {
  id: string; tenant: string; number: string; status: 'draft' | 'open' | 'partially_paid' | 'paid' | 'uncollectible' | 'void';
  total_minor: number; currency: string; created: string;
}

const INVOICE_STATUS_META: Record<Invoice['status'], { label: string; tone: 'neutral' | 'success' | 'danger' | 'warning' }> = {
  draft: { label: 'مسوّدة', tone: 'neutral' },
  open: { label: 'مستحقة', tone: 'warning' },
  partially_paid: { label: 'مدفوعة جزئياً', tone: 'warning' },
  paid: { label: 'مدفوعة', tone: 'success' },
  uncollectible: { label: 'متعذّر تحصيلها', tone: 'danger' },
  void: { label: 'ملغاة', tone: 'neutral' },
};

type Tab = 'overview' | 'billing' | 'seats' | 'tickets' | 'whatsapp' | 'audit';

export function CustomerDetail({ session, tenant, subscription, planNames, catalog, onClose }: {
  session: AdminSession; tenant: Tenant; subscription: Subscription | null;
  planNames: Map<string, string>; catalog: AdminCatalog; onClose: () => void;
}) {
  const [tab, setTab] = useState<Tab>('overview');

  return (
    <Modal open onClose={onClose} size="xl" title={tenant.name} subtitle={<span dir="ltr">{tenant.slug}</span>}>
      <div className="flex flex-col gap-4">
        <Segmented value={tab} onChange={(v) => setTab(v as Tab)}
                  options={[
                    { value: 'overview', label: 'نظرة عامة' },
                    { value: 'billing', label: 'التطبيقات والفوترة' },
                    { value: 'seats', label: 'الفروع والمستخدمين' },
                    { value: 'tickets', label: 'التذاكر والدعم' },
                    { value: 'whatsapp', label: 'واتساب' },
                    { value: 'audit', label: 'السجل والتدقيق' },
                  ]} />

        {tab === 'overview' ? <OverviewTab tenant={tenant} subscription={subscription} planNames={planNames} /> : null}
        {tab === 'billing' ? <BillingTab session={session} tenant={tenant} catalog={catalog} planNames={planNames} /> : null}
        {tab === 'seats' ? <SeatsTab session={session} tenant={tenant} catalog={catalog} /> : null}
        {tab === 'tickets' ? <TicketsTab session={session} tenant={tenant} catalog={catalog} /> : null}
        {tab === 'whatsapp' ? <WhatsAppTab session={session} tenant={tenant} catalog={catalog} /> : null}
        {tab === 'audit' ? <AuditTab session={session} tenant={tenant} catalog={catalog} /> : null}
      </div>
    </Modal>
  );
}

function OverviewTab({ tenant, subscription, planNames }: {
  tenant: Tenant; subscription: Subscription | null; planNames: Map<string, string>;
}) {
  const subMeta = subscription ? SUB_STATUS_META[subscription.status] : null;
  return (
    <div className="flex flex-col gap-3">
      <Row label="الحالة"><Badge tone={tenant.status === 'active' ? 'success' : tenant.status === 'suspended' ? 'danger' : 'neutral'}>{tenant.status}</Badge></Row>
      <Row label="التطبيق">
        {subMeta ? (
          <span className="flex items-center gap-2">
            <Badge tone={subMeta.tone}>{subMeta.label}</Badge>
            <span>{planNames.get(subscription!.plan_id) ?? subscription!.plan_id}</span>
          </span>
        ) : <span className="text-text-muted">بلا تطبيق مفعّل</span>}
      </Row>
      <Row label="تاريخ الانضمام"><span dir="ltr">{tenant.created_at?.slice(0, 10)}</span></Row>
      <Row label="آخر تحديث"><span dir="ltr">{tenant.updated_at?.slice(0, 10)}</span></Row>
      <Row label="المسوّق">
        <span className="text-text-muted">غير متاح — الربط موجود بكود affiliate-service (of_tenant) لكن غير مكشوف كمسار إداري بعد.</span>
      </Row>
    </div>
  );
}

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between gap-3 border-b border-border-subtle pb-2">
      <span className="text-label text-text-secondary">{label}</span>
      {children}
    </div>
  );
}

function BillingTab({ session, tenant, catalog, planNames }: {
  session: AdminSession; tenant: Tenant; catalog: AdminCatalog; planNames: Map<string, string>;
}) {
  const [subs, setSubs] = useState<Subscription[] | 'loading' | 'failed'>('loading');
  const [invoices, setInvoices] = useState<Invoice[] | 'loading' | 'failed'>('loading');

  const subsAction = findCustomerAction(catalog, 'billing.platform_subscriptions');
  const invAction = findCustomerAction(catalog, 'billing.platform_invoices');

  useEffect(() => {
    if (!subsAction) { setSubs('failed'); return; }
    req<{ subscriptions: Subscription[] }>(
      `${subsAction.path}?tenant=${encodeURIComponent(tenant.id)}&limit=50`, 'GET', undefined, session.access_token)
      .then((r) => setSubs(r.subscriptions)).catch(() => setSubs('failed'));
    if (!invAction) { setInvoices('failed'); return; }
    req<{ invoices: Invoice[] }>(
      `${invAction.path}?tenant=${encodeURIComponent(tenant.id)}&limit=50`, 'GET', undefined, session.access_token)
      .then((r) => setInvoices(r.invoices)).catch(() => setInvoices('failed'));
    // eslint-disable-next-line react-hooks/exhaustive-deps -- runs once per opened tenant
  }, [tenant.id]);

  return (
    <div className="flex flex-col gap-5">
      <div>
        <h3 className="mb-2 font-medium">التطبيقات المفعّلة</h3>
        {!subsAction ? <p className="text-sm text-text-secondary">لا صلاحية.</p>
         : subs === 'loading' ? <p className="text-sm text-text-secondary">جارٍ التحميل…</p>
         : subs === 'failed' ? <p role="alert" className="text-danger text-sm">تعذّرت القراءة.</p>
         : subs.length === 0 ? <p className="text-sm text-text-muted">بلا تطبيقات مفعّلة.</p>
         : (
          <div className="flex flex-col gap-2">
            {subs.map((s) => (
              <div key={s.id} className="flex items-center justify-between rounded-lg bg-surface-2 p-3 text-sm">
                <span>{planNames.get(s.plan_id) ?? s.plan_id}</span>
                <Badge tone={SUB_STATUS_META[s.status]?.tone ?? 'neutral'}>{SUB_STATUS_META[s.status]?.label ?? s.status}</Badge>
              </div>
            ))}
          </div>
        )}
      </div>

      <div>
        <h3 className="mb-2 font-medium">الفواتير</h3>
        {!invAction ? <p className="text-sm text-text-secondary">لا صلاحية.</p>
         : invoices === 'loading' ? <p className="text-sm text-text-secondary">جارٍ التحميل…</p>
         : invoices === 'failed' ? <p role="alert" className="text-danger text-sm">تعذّرت القراءة.</p>
         : invoices.length === 0 ? <p className="text-sm text-text-muted">بلا فواتير.</p>
         : (
          <div className="flex flex-col gap-2">
            {invoices.map((inv) => (
              <div key={inv.id} className="flex items-center justify-between rounded-lg bg-surface-2 p-3 text-sm">
                <span dir="ltr" className="font-mono">{inv.number || inv.id}</span>
                <span dir="ltr">{(inv.total_minor / 100).toFixed(2)} {inv.currency}</span>
                <Badge tone={INVOICE_STATUS_META[inv.status]?.tone ?? 'neutral'}>{INVOICE_STATUS_META[inv.status]?.label ?? inv.status}</Badge>
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="rounded-card border border-dashed border-border-subtle bg-surface-2 p-4 text-center">
        <p className="text-sm text-text-secondary">
          "منح تجربة مجانية" — إجراء إداري جديد كلياً، غير موجود بالخادم حالياً. يحتاج تصميماً وبناءً منفصلاً قبل إضافته هنا.
        </p>
      </div>
    </div>
  );
}

interface AuditEvent {
  id: string; seq: number; ts: string; service: string; action: string;
  actor: string; resource: string; ip: string;
}

/**
 * audit.query يدعم فلتر tenant فعلاً بالخادم (services/audit-service's own admin_actions.py) —
 * على عكس ما ذكرته أول مرة بالاقتراح (كنت أفترض فجوة هنا، والفحص المباشر للكود نفى ذلك). هذا
 * التبويب إذن جاهز بالكامل من أول مرحلة 2، بلا أي عمل خلفي جديد.
 */
function AuditTab({ session, tenant, catalog }: { session: AdminSession; tenant: Tenant; catalog: AdminCatalog }) {
  const [events, setEvents] = useState<AuditEvent[] | 'loading' | 'failed'>('loading');
  const action = findCustomerAction(catalog, 'audit.query');

  useEffect(() => {
    if (!action) { setEvents('failed'); return; }
    req<{ events: AuditEvent[] }>(
      `${action.path}?tenant=${encodeURIComponent(tenant.id)}&limit=100`, 'GET', undefined, session.access_token)
      .then((r) => setEvents(r.events)).catch(() => setEvents('failed'));
    // eslint-disable-next-line react-hooks/exhaustive-deps -- runs once per opened tenant
  }, [tenant.id]);

  if (!action) return <p className="text-sm text-text-secondary">لا صلاحية.</p>;
  if (events === 'loading') return <p className="text-sm text-text-secondary">جارٍ التحميل…</p>;
  if (events === 'failed') return <p role="alert" className="text-danger text-sm">تعذّرت قراءة السجل.</p>;
  if (events.length === 0) return <p className="text-sm text-text-muted">لا أحداث بعد على هذا العميل.</p>;

  return (
    <div className="flex flex-col gap-2">
      {events.map((e) => (
        <div key={e.id} className="flex flex-wrap items-center justify-between gap-2 rounded-lg bg-surface-2 p-3 text-sm">
          <span dir="ltr" className="text-label text-text-muted">{new Date(e.ts).toLocaleString('ar-SA')}</span>
          <span className="font-medium">{e.action}</span>
          <span dir="ltr" className="text-label text-text-secondary">{e.service}</span>
          <span dir="ltr" className="text-label text-text-muted">{e.actor || '—'}</span>
        </div>
      ))}
    </div>
  );
}

interface Capacity {
  branches: number; operators: number;
  branches_limit: number; operators_limit: number;   // -1 = unlimited or unreachable
}

/** x/y — العدد الفعلي مقابل حدّ الباقة (operations.tenant_capacity، يقرأ نفس فحص
 * entitlements/check اللي يمنع المحل من إضافة موظف/فرع فوق حده، لا مسار جديد). ‎-1 = غير محدود
 * أو تعذّر الوصول لخدمة الفوترة — تُعرض بلا سقف حينها، لا نخترع رقماً. */
function seatsLabel(current: number, limit: number): string {
  return limit < 0 ? String(current) : `${current}/${limit}`;
}
function SeatsTab({ session, tenant, catalog }: { session: AdminSession; tenant: Tenant; catalog: AdminCatalog }) {
  const [capacity, setCapacity] = useState<Capacity | 'loading' | 'failed'>('loading');
  const action = findCustomerAction(catalog, 'operations.tenant_capacity');

  useEffect(() => {
    if (!action) { setCapacity('failed'); return; }
    req<Capacity>(
      action.path.replace('{tenant_id}', encodeURIComponent(tenant.id)),
      'GET', undefined, session.access_token)
      .then(setCapacity).catch(() => setCapacity('failed'));
    // eslint-disable-next-line react-hooks/exhaustive-deps -- runs once per opened tenant
  }, [tenant.id]);

  if (!action) return <p className="text-sm text-text-secondary">لا صلاحية.</p>;
  if (capacity === 'loading') return <p className="text-sm text-text-secondary">جارٍ التحميل…</p>;
  if (capacity === 'failed') return <p role="alert" className="text-danger text-sm">تعذّرت القراءة.</p>;

  return (
    <div className="flex flex-col gap-3">
      <Row label="الفروع">
        <span className="font-medium">{seatsLabel(capacity.branches, capacity.branches_limit)}</span>
      </Row>
      <Row label="الموظفون">
        <span className="font-medium">{seatsLabel(capacity.operators, capacity.operators_limit)}</span>
      </Row>
    </div>
  );
}

export interface TicketSummary {
  id: string; type: string; status: string; priority: string;
  created: string; updated: string; assignee: string; tags: string[]; raiser_ref: string;
  // Present when the row came from the all-tenants sweep (ticket-service v0.18.21) — absent when
  // it came from a single-tenant list, where the caller already knows which tenant it asked for.
  tenant?: string;
}

export interface TicketEvent {
  id: string; kind: string; ts: string; actor: string; body?: string;
}

export interface TicketDetail extends TicketSummary {
  subject: string;
  body: string;
}

/** لا خريطة حالات ثابتة عمداً — الحالة نص حرّ يحدّده تدفّق عمل (workflow) كل تينانت
 * (GET /api/v1/workflows بـticket-service)، لا قيمة مغلقة من مجموعة معروفة سلفاً. عرض الخام
 * كما هو أصدق من تلوين حالة قد لا تطابق تعريفها الحقيقي. */
export function statusTone(status: string): 'neutral' | 'success' | 'danger' | 'warning' {
  const s = status.toLowerCase();
  if (s.includes('resolv') || s.includes('closed') || s.includes('حُل') || s.includes('مغلق')) return 'success';
  if (s.includes('escalat') || s.includes('تصعيد')) return 'danger';
  if (s.includes('pending') || s.includes('انتظار')) return 'warning';
  return 'neutral';
}

/** مُصدَّرة — نفس عرض التفاصيل يُستخدم من التبويب داخل ملف عميل واحد (TicketsTab) وشاشة صندوق
 * الوارد الموحّد عبر كل المستأجرين (AdminTickets.tsx)، بلا تكرار JSX. قراءة فقط هنا أيضاً. */
export function TicketDetailView({ ticket, events }: { ticket: TicketDetail; events: TicketEvent[] }) {
  return (
    <div className="flex flex-col gap-4">
      <div>
        <div className="mb-1 flex items-center justify-between gap-2">
          <h3 className="font-medium">{ticket.subject || ticket.id}</h3>
          <Badge tone={statusTone(ticket.status)}>{ticket.status}</Badge>
        </div>
        <p className="whitespace-pre-wrap text-sm text-text-secondary">{ticket.body}</p>
      </div>
      <div>
        <h4 className="mb-2 text-label text-text-muted">سجل الردود</h4>
        {events.length === 0 ? <p className="text-sm text-text-muted">لا ردود بعد.</p> : (
          <div className="flex flex-col gap-2">
            {events.map((e) => (
              <div key={e.id} className="rounded-lg bg-surface-2 p-3 text-sm">
                <div className="mb-1 flex items-center justify-between gap-2">
                  <span dir="ltr" className="text-label text-text-muted">{e.actor || '—'}</span>
                  <span dir="ltr" className="text-label text-text-muted">{new Date(e.ts).toLocaleString('ar-SA')}</span>
                </div>
                {e.body ? <p className="whitespace-pre-wrap">{e.body}</p> : <span className="text-text-muted">{e.kind}</span>}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

/**
 * قائمة/تفاصيل — نفس نمط الاختيار من قائمة يفتح تفاصيل تحتها المستخدم بمكونات ثانية بهذا الملف
 * (لا Modal متداخل). قراءة فقط: لا ردّ ولا تغيير حالة من هنا — هذي شاشة دعم المنصة على تذاكر
 * عميل، لا لوحة عامل التذاكر نفسها.
 */
/** مُصدَّرة — نفس المكوّن يُستخدم هنا (تبويب داخل ملف عميل واحد) وبصفحة "تذاكر" المستقلة
 * بالشريط الجانبي (AdminTickets.tsx) بعد اختيار مستأجر من قائمة — لا تكرار منطق. */
/** فلاتر الخادم الأربعة اللي يدعمها المسار فعلاً (ticket-service v0.18.20) — status/type/priority
 * كنصوص حرّة تُبنى كقوائم اختيار من القيم الظاهرة فعلياً بالنتيجة الحالية (لا تعداد ثابت، الحالة
 * تدفّق عمل قابل للتخصيص لكل تينانت)، وassignee كبحث نصي حر. */
interface TicketFilters { status: string; type: string; priority: string; assignee: string; }
const EMPTY_FILTERS: TicketFilters = { status: '', type: '', priority: '', assignee: '' };

function ticketsQuery(tenantId: string, f: TicketFilters, cursor?: string): string {
  const p = new URLSearchParams({ tenant: tenantId, limit: '50' });
  if (f.status) p.set('status', f.status);
  if (f.type) p.set('type', f.type);
  if (f.priority) p.set('priority', f.priority);
  if (f.assignee) p.set('assignee', f.assignee);
  if (cursor) p.set('cursor', cursor);
  return p.toString();
}

export function TicketsTab({ session, tenant, catalog }: { session: AdminSession; tenant: Tenant; catalog: AdminCatalog }) {
  const [tickets, setTickets] = useState<TicketSummary[] | 'loading' | 'failed'>('loading');
  const [cursor, setCursor] = useState<string | undefined>(undefined);
  const [loadingMore, setLoadingMore] = useState(false);
  const [filters, setFilters] = useState<TicketFilters>(EMPTY_FILTERS);
  const [selected, setSelected] = useState<string | null>(null);
  const [detail, setDetail] = useState<{ ticket: TicketDetail; events: TicketEvent[] } | 'loading' | 'failed' | null>(null);

  const listAction = findCustomerAction(catalog, 'tickets.platform_inbox');
  const detailAction = findCustomerAction(catalog, 'tickets.platform_detail');

  useEffect(() => {
    if (!listAction) { setTickets('failed'); return; }
    req<{ tenant: string; tickets: TicketSummary[]; cursor?: string }>(
      `${listAction.path}?${ticketsQuery(tenant.id, filters)}`, 'GET', undefined, session.access_token)
      .then((r) => { setTickets(r.tickets); setCursor(r.cursor); }).catch(() => setTickets('failed'));
    setSelected(null);
    setDetail(null);
    // eslint-disable-next-line react-hooks/exhaustive-deps -- refetches on tenant AND on any filter change
  }, [tenant.id, filters]);

  function loadMore() {
    if (!listAction || !cursor || tickets === 'loading' || tickets === 'failed') return;
    setLoadingMore(true);
    req<{ tenant: string; tickets: TicketSummary[]; cursor?: string }>(
      `${listAction.path}?${ticketsQuery(tenant.id, filters, cursor)}`, 'GET', undefined, session.access_token)
      .then((r) => { setTickets((prev) => (prev === 'loading' || prev === 'failed' ? r.tickets : [...prev, ...r.tickets])); setCursor(r.cursor); })
      .finally(() => setLoadingMore(false));
  }

  // خيارات كل قائمة اختيار مبنيّة من القيم الظاهرة فعلياً بالصفحة الحالية — لا قيمة مخترَعة، ولا
  // تُفقَد القيمة المختارة حالياً لو اختفت من الصفحة (تُبقى مضافة للخيارات يدوياً).
  const distinct = (key: 'status' | 'type' | 'priority'): string[] => {
    const vals = new Set<string>(tickets !== 'loading' && tickets !== 'failed' ? tickets.map((t) => t[key]).filter(Boolean) : []);
    if (filters[key]) vals.add(filters[key]);
    return Array.from(vals).sort();
  };

  useEffect(() => {
    if (!selected) return;
    if (!detailAction) { setDetail('failed'); return; }
    setDetail('loading');
    const path = detailAction.path.replace(/\{[^}]*\}/, encodeURIComponent(selected));
    req<{ tenant: string; ticket: TicketDetail; events: TicketEvent[] }>(
      `${path}?tenant=${encodeURIComponent(tenant.id)}`, 'GET', undefined, session.access_token)
      .then((r) => setDetail({ ticket: r.ticket, events: r.events })).catch(() => setDetail('failed'));
  }, [selected, detailAction, tenant.id, session.access_token]);

  if (!listAction) return <p className="text-sm text-text-secondary">لا صلاحية.</p>;

  if (selected) {
    return (
      <div className="flex flex-col gap-3">
        <button type="button" onClick={() => setSelected(null)} className="self-start text-label text-brand">
          ← رجوع للقائمة
        </button>
        {detail === 'loading' || detail === null ? <p className="text-sm text-text-secondary">جارٍ التحميل…</p>
         : detail === 'failed' ? <p role="alert" className="text-danger text-sm">تعذّرت القراءة.</p>
         : <TicketDetailView ticket={detail.ticket} events={detail.events} />}
      </div>
    );
  }

  const hasActiveFilter = filters.status || filters.type || filters.priority || filters.assignee;

  return (
    <div className="flex flex-col gap-3">
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
        {hasActiveFilter ? (
          <button type="button" onClick={() => setFilters(EMPTY_FILTERS)} className="text-label text-brand">
            مسح الفلاتر
          </button>
        ) : null}
      </div>

      {tickets === 'loading' ? <p className="text-sm text-text-secondary">جارٍ التحميل…</p>
       : tickets === 'failed' ? <p role="alert" className="text-danger text-sm">تعذّرت القراءة.</p>
       : tickets.length === 0 ? (
        <p className="text-sm text-text-muted">
          {hasActiveFilter ? 'لا تذاكر تطابق هذي الفلاتر.' : 'لا تذاكر لهذا العميل.'}
        </p>
      ) : (
        <div className="flex flex-col gap-2">
          {tickets.map((t) => (
            <button key={t.id} type="button" onClick={() => setSelected(t.id)}
                    className="flex flex-wrap items-center justify-between gap-2 rounded-lg bg-surface-2 p-3 text-sm text-start hover:bg-surface-3">
              <span dir="ltr" className="font-mono text-text-muted">{t.id}</span>
              {t.type ? <span className="text-label text-text-muted">{t.type}</span> : null}
              {t.priority ? <span className="text-label text-text-muted">{t.priority}</span> : null}
              {t.assignee ? <span dir="ltr" className="text-label text-text-muted">{t.assignee}</span> : null}
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

/** نفس مسار operations.whatsapp_diagnostics اللي تستخدمه AdminWhatsAppDiagnostics.tsx — هنا
 * بلا نموذج بحث، تينانت العميل المفتوح مُمرَّر مباشرة. لا مسار جديد ولا تكرار منطق العرض
 * (StatusBadge/DeliveryRow مُصدَّرتان من نفس الملف). */
function WhatsAppTab({ session, tenant, catalog }: { session: AdminSession; tenant: Tenant; catalog: AdminCatalog }) {
  const [rows, setRows] = useState<DeliveryRow[] | 'loading' | 'failed'>('loading');
  const action = findCustomerAction(catalog, 'operations.whatsapp_diagnostics');

  useEffect(() => {
    if (!action) { setRows('failed'); return; }
    req<{ deliveries: DeliveryRow[] }>(
      `${action.path}?tenant=${encodeURIComponent(tenant.id)}`, 'GET', undefined, session.access_token)
      .then((r) => setRows(r.deliveries ?? [])).catch(() => setRows('failed'));
    // eslint-disable-next-line react-hooks/exhaustive-deps -- runs once per opened tenant
  }, [tenant.id]);

  if (!action) return <p className="text-sm text-text-secondary">لا صلاحية.</p>;
  if (rows === 'loading') return <p className="text-sm text-text-secondary">جارٍ التحميل…</p>;
  if (rows === 'failed') return <p role="alert" className="text-danger text-sm">تعذّرت القراءة.</p>;
  if (rows.length === 0) return <p className="text-sm text-text-muted">لا رسائل واتساب مسجَّلة لهذا المحل.</p>;

  return (
    <ul className="flex flex-col gap-2">
      {rows.map((r, i) => (
        <li key={r.id ?? i} className="flex flex-col gap-1 rounded-card border border-border-subtle bg-surface-2 p-3 text-sm">
          <div className="flex items-center justify-between gap-2">
            <span dir="ltr" className="font-mono text-text-muted">{r.recipient_masked ?? '—'}</span>
            <StatusBadge status={r.status} />
          </div>
          {r.receipt_status ? <span className="text-text-secondary">حالة ميتا: {r.receipt_status}</span> : null}
          {r.error ? <span className="text-danger">{r.error}</span> : null}
          {r.created ? <span className="text-caption text-text-muted" dir="ltr">{new Date(r.created).toLocaleString('ar-SA')}</span> : null}
        </li>
      ))}
    </ul>
  );
}
