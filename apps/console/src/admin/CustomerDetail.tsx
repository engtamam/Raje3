/**
 * ملف العميل — نافذة مركزية كبيرة (rj-ui/Modal، size="xl") بستة تبويبات، لا شريط جانبي — طُلب
 * صراحة بدل الشكل الجانبي الأول (انظر AdminCustomers.tsx's own header للخطة الكاملة).
 *
 * المرحلة 1: "نظرة عامة" و"التطبيقات والفوترة" ببيانات حقيقية. المرحلة 2: "السجل والتدقيق" حقيقي
 * كذلك — audit.query يدعم فلتر tenant فعلاً بالخادم، اكتشفنا هذا بالفحص المباشر بعد ما ذكرته
 * خطأً كفجوة بالاقتراح الأول. "الفروع والمستخدمين" جزئياً حقيقي الآن (المرحلة 3) — العدد الفعلي
 * فقط أول ما شُحِن (operations.tenant_capacity) — ثم x/y كامل: الحد يُقرأ من نفس فحص الباقة
 * (`billing entitlements/check`) اللي يمنع المحل أصلاً من تجاوزه عند الإضافة، لا مسار جديد ولا
 * رقم مخترَع. الباقي (التذاكر والدعم، واتساب) يبقى "قريباً" صريح يشرح بالضبط ما
 * ينقصه — لا يختفي، نفس انضباط AdminWhatsAppTemplates.tsx's "لا عذر صامت".
 *
 * تبويب التذاكر (المرحلة 4): مسار إداري جديد كلياً من ticket-service (v0.18.20)، بناءً على طلب
 * صريح — GET /api/v1/tickets/admin/tickets(?tenant=) للقائمة، و.../{ticket_id} للتفاصيل الكاملة
 * (نص + ردود)، بصلاحية platform.tickets وحدها (دور tenant/operator يُرفض 403). كل قراءة تُسجَّل
 * fail-closed (ticket.platform_viewed) — شرط طلبناه صراحة، لا اقتراح منهم.
 */
import { useEffect, useState } from 'react';
import { Badge } from './../rj-ui/Badge';
import { Segmented } from './../rj-ui/Segmented';
import { Modal } from './../rj-ui/Modal';
import { req, type AdminSession } from './api';
import type { AdminCatalog } from './catalog';
import { findCustomerAction, SUB_STATUS_META, type Tenant, type Subscription } from './CustomerList';

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
        {tab === 'whatsapp' ? (
          <ComingSoon text="قوالب واتساب حالياً عامة للمنصة كلها، لا يوجد مفهوم قالب خاص بمنشأة — فجوة معمارية حقيقية، ليست مجرد فلتر ناقص." />
        ) : null}
        {tab === 'audit' ? <AuditTab session={session} tenant={tenant} catalog={catalog} /> : null}
      </div>
    </Modal>
  );
}

function ComingSoon({ text }: { text: string }) {
  return (
    <div className="rounded-card border border-dashed border-border-subtle bg-surface-2 p-6 text-center">
      <p className="text-sm text-text-secondary">قريباً — {text}</p>
    </div>
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

interface TicketSummary {
  id: string; type: string; status: string; priority: string;
  created: string; updated: string; assignee: string; tags: string[]; raiser_ref: string;
}

interface TicketEvent {
  id: string; kind: string; ts: string; actor: string; body?: string;
}

interface TicketDetail extends TicketSummary {
  subject: string;
  body: string;
}

/** لا خريطة حالات ثابتة عمداً — الحالة نص حرّ يحدّده تدفّق عمل (workflow) كل تينانت
 * (GET /api/v1/workflows بـticket-service)، لا قيمة مغلقة من مجموعة معروفة سلفاً. عرض الخام
 * كما هو أصدق من تلوين حالة قد لا تطابق تعريفها الحقيقي. */
function statusTone(status: string): 'neutral' | 'success' | 'danger' | 'warning' {
  const s = status.toLowerCase();
  if (s.includes('resolv') || s.includes('closed') || s.includes('حُل') || s.includes('مغلق')) return 'success';
  if (s.includes('escalat') || s.includes('تصعيد')) return 'danger';
  if (s.includes('pending') || s.includes('انتظار')) return 'warning';
  return 'neutral';
}

/**
 * قائمة/تفاصيل — نفس نمط الاختيار من قائمة يفتح تفاصيل تحتها المستخدم بمكونات ثانية بهذا الملف
 * (لا Modal متداخل). قراءة فقط: لا ردّ ولا تغيير حالة من هنا — هذي شاشة دعم المنصة على تذاكر
 * عميل، لا لوحة عامل التذاكر نفسها.
 */
/** مُصدَّرة — نفس المكوّن يُستخدم هنا (تبويب داخل ملف عميل واحد) وبصفحة "تذاكر" المستقلة
 * بالشريط الجانبي (AdminTickets.tsx) بعد اختيار مستأجر من قائمة — لا تكرار منطق. */
export function TicketsTab({ session, tenant, catalog }: { session: AdminSession; tenant: Tenant; catalog: AdminCatalog }) {
  const [tickets, setTickets] = useState<TicketSummary[] | 'loading' | 'failed'>('loading');
  const [selected, setSelected] = useState<string | null>(null);
  const [detail, setDetail] = useState<{ ticket: TicketDetail; events: TicketEvent[] } | 'loading' | 'failed' | null>(null);

  const listAction = findCustomerAction(catalog, 'tickets.platform_inbox');
  const detailAction = findCustomerAction(catalog, 'tickets.platform_detail');

  useEffect(() => {
    if (!listAction) { setTickets('failed'); return; }
    req<{ tenant: string; tickets: TicketSummary[] }>(
      `${listAction.path}?tenant=${encodeURIComponent(tenant.id)}&limit=50`, 'GET', undefined, session.access_token)
      .then((r) => setTickets(r.tickets)).catch(() => setTickets('failed'));
    setSelected(null);
    setDetail(null);
    // eslint-disable-next-line react-hooks/exhaustive-deps -- runs once per opened tenant
  }, [tenant.id]);

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
  if (tickets === 'loading') return <p className="text-sm text-text-secondary">جارٍ التحميل…</p>;
  if (tickets === 'failed') return <p role="alert" className="text-danger text-sm">تعذّرت القراءة.</p>;
  if (tickets.length === 0) return <p className="text-sm text-text-muted">لا تذاكر لهذا العميل.</p>;

  if (selected) {
    return (
      <div className="flex flex-col gap-3">
        <button type="button" onClick={() => setSelected(null)} className="self-start text-label text-brand">
          ← رجوع للقائمة
        </button>
        {detail === 'loading' || detail === null ? <p className="text-sm text-text-secondary">جارٍ التحميل…</p>
         : detail === 'failed' ? <p role="alert" className="text-danger text-sm">تعذّرت القراءة.</p>
         : (
          <div className="flex flex-col gap-4">
            <div>
              <div className="mb-1 flex items-center justify-between gap-2">
                <h3 className="font-medium">{detail.ticket.subject || detail.ticket.id}</h3>
                <Badge tone={statusTone(detail.ticket.status)}>{detail.ticket.status}</Badge>
              </div>
              <p className="whitespace-pre-wrap text-sm text-text-secondary">{detail.ticket.body}</p>
            </div>
            <div>
              <h4 className="mb-2 text-label text-text-muted">سجل الردود</h4>
              {detail.events.length === 0 ? <p className="text-sm text-text-muted">لا ردود بعد.</p> : (
                <div className="flex flex-col gap-2">
                  {detail.events.map((e) => (
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
        )}
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-2">
      {tickets.map((t) => (
        <button key={t.id} type="button" onClick={() => setSelected(t.id)}
                className="flex items-center justify-between gap-2 rounded-lg bg-surface-2 p-3 text-sm text-start hover:bg-surface-3">
          <span dir="ltr" className="font-mono text-text-muted">{t.id}</span>
          <span dir="ltr" className="text-label text-text-muted">{new Date(t.updated).toLocaleString('ar-SA')}</span>
          <Badge tone={statusTone(t.status)}>{t.status}</Badge>
        </button>
      ))}
    </div>
  );
}
