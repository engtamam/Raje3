/**
 * ملف العميل — نافذة مركزية كبيرة (rj-ui/Modal، size="xl") بستة تبويبات، لا شريط جانبي — طُلب
 * صراحة بدل الشكل الجانبي الأول (انظر AdminCustomers.tsx's own header للخطة الكاملة).
 *
 * المرحلة 1: "نظرة عامة" و"التطبيقات والفوترة" ببيانات حقيقية. المرحلة 2: "السجل والتدقيق" حقيقي
 * كذلك — audit.query يدعم فلتر tenant فعلاً بالخادم، اكتشفنا هذا بالفحص المباشر بعد ما ذكرته
 * خطأً كفجوة بالاقتراح الأول. "الفروع والمستخدمين" جزئياً حقيقي الآن (المرحلة 3) — العدد الفعلي
 * فقط أول ما شُحِن (operations.tenant_capacity) — ثم x/y كامل: الحد يُقرأ من نفس فحص الحدود
 * المجمَّعة عبر كل اشتراكات المحل (`billing entitlements/check` — ليست "باقة" واحدة؛ الحد
 * مجموع اشتراكاته المستقلة) اللي يمنع المحل أصلاً من تجاوزه عند الإضافة، لا مسار جديد ولا
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
import { Activity, ArrowRight, Building2, CheckCircle2, CircleAlert, Clock, Package, RefreshCw, Users } from 'lucide-react';
import { Badge } from './../rj-ui/Badge';
import { Segmented } from './../rj-ui/Segmented';
import { Button } from './../rj-ui/Button';
import { KpiCard } from './../rj-ui/KpiCard';
import { Table, type TableColumn } from './../rj-ui/Table';
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

/** منذ متى معنا، بكلمات — نفس منطق `ago()` المستخدم بشاشة المحل نفسها (screens/Customer.tsx)،
 *  محلياً هنا لأن هذا الملف لا يستورد من apps/console/src/screens. */
function tenureText(createdAt: string): string {
  if (!createdAt) return '—';
  const days = Math.floor((Date.now() - new Date(createdAt).getTime()) / 86400000);
  if (days < 1) return 'اليوم';
  if (days < 30) return `${days} يوم`;
  const months = Math.floor(days / 30);
  if (months < 12) return `${months} شهر`;
  const years = Math.floor(months / 12);
  return `${years} سنة`;
}

/**
 * الشارة المركّبة — تدمج حالة الحساب وحالة التطبيق سوا برأي واحد، بدل ما المشغّل يجمّع الاثنين
 * بعقله. الترتيب مقصود: الأخطر أولاً (حساب معلَّق يطغى على كل شيء)، وبلا تطبيق نشط حالة تستاهل
 * انتباه حتى لو الحساب نفسه سليم ظاهرياً.
 */
function accountHealth(tenant: Tenant, subscription: Subscription | null):
  { label: string; tone: 'success' | 'warning' | 'danger' | 'info' } {
  if (tenant.status === 'suspended') return { label: 'معلَّق', tone: 'danger' };
  if (tenant.status === 'pending') return { label: 'قيد التفعيل', tone: 'warning' };
  if (tenant.status === 'deleted') return { label: 'محذوف', tone: 'danger' };
  if (!subscription) return { label: 'بلا تطبيق نشط', tone: 'warning' };
  if (subscription.status === 'past_due') return { label: 'متأخر بالدفع', tone: 'danger' };
  if (subscription.status === 'paused' || subscription.status === 'canceled') {
    return { label: 'التطبيق متوقف', tone: 'warning' };
  }
  if (subscription.status === 'trialing') return { label: 'تجريبي', tone: 'info' };
  return { label: 'سليم', tone: 'success' };
}

/**
 * الصفحة الكاملة — لا نافذة منبثقة، هذي أول شاشة إدارية تحمل لمسة الفخامة اللي شاشات المحل نفسه
 * تحملها (`shadow-glow`، `text-display`) بعد دراسة الثيم الكاملة.
 */
export function CustomerDetail({ session, tenant, subscription, planNames, catalog, onClose }: {
  session: AdminSession; tenant: Tenant; subscription: Subscription | null;
  planNames: Map<string, string>; catalog: AdminCatalog; onClose: () => void;
}) {
  const [tab, setTab] = useState<Tab>('overview');
  const subMeta = subscription ? SUB_STATUS_META[subscription.status] : null;
  const health = accountHealth(tenant, subscription);

  return (
    <div className="flex min-h-full flex-col gap-5 p-6">
      {/* رأس الصفحة الفاخر — توهّج بلون العلامة عند المرور (shadow-glow)، وحجم خط display الأكبر
         بالنظام لاسم المحل. أول استخدام للاثنين بلوحة الإدارة كاملة. */}
      <header className="flex items-center gap-4 rounded-card border border-border-subtle bg-surface-1 p-5
                         shadow-md transition-shadow duration-base ease-smooth hover:shadow-glow">
        <Button variant="ghost" size="icon" aria-label="رجوع" onClick={onClose}>
          <ArrowRight size={20} />
        </Button>
        <div className="flex flex-col gap-1">
          <h1 className="text-display font-semibold tracking-tight text-text-primary">{tenant.name}</h1>
          <span dir="ltr" className="text-label text-text-secondary">{tenant.slug}</span>
        </div>
      </header>

      {/* صف الـKPIs — من بيانات هذي الصفحة نفسها (tenant/subscription)، لا أرقام مختلقة. مؤشرات
         أعمق (نشاط واتساب حقيقي، استهلاك المحفظة، تذاكر مفتوحة) تحتاج قراءات إضافية وتُضاف مع كل
         تبويب لما يُبنى — لا رقم يُعرض هنا قبل ما يكون مصدره حقيقياً. */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <KpiCard icon={<Clock size={18} />} label="منذ متى معنا" value={tenureText(tenant.created_at)}
                tone="accent" hint={tenant.created_at?.slice(0, 10)} />
        {/* الشارة المركّبة — حالة الحساب + حالة التطبيق برأي واحد، لا رقمين يُجمَعان بعقل المشغّل. */}
        <KpiCard icon={<Activity size={18} />} label="صحة الحساب" value={health.label} tone={health.tone} />
        {/* التطبيق قابل للنقر — يوديك مباشرة لتبويب الفوترة، بدل ما تدوّر عليه يدوياً. */}
        <button type="button" onClick={() => setTab('billing')} className="text-start">
          <KpiCard icon={<Package size={18} />} label="التطبيق" value={subMeta?.label ?? 'بلا تطبيق'}
                  tone={subMeta?.tone ?? 'neutral'}
                  hint={subscription ? (planNames.get(subscription.plan_id) ?? subscription.plan_id) : 'اضغط للفوترة'} />
        </button>
        <KpiCard icon={<RefreshCw size={18} />} label="آخر تحديث" value={tenureText(tenant.updated_at)}
                tone="neutral" hint={tenant.updated_at?.slice(0, 10)} />
      </div>

      <Segmented value={tab} onChange={(v) => setTab(v as Tab)}
                options={[
                  { value: 'overview', label: 'نظرة عامة' },
                  { value: 'billing', label: 'التطبيقات والفوترة' },
                  { value: 'seats', label: 'الفروع والمستخدمين' },
                  { value: 'tickets', label: 'التذاكر والدعم' },
                  { value: 'whatsapp', label: 'واتساب' },
                  { value: 'audit', label: 'السجل والتدقيق' },
                ]} />

      {tab === 'overview' ? <OverviewTab tenant={tenant} /> : null}
      {tab === 'billing' ? <BillingTab session={session} tenant={tenant} catalog={catalog} planNames={planNames} /> : null}
      {tab === 'seats' ? <SeatsTab session={session} tenant={tenant} catalog={catalog} /> : null}
      {tab === 'tickets' ? <TicketsTab session={session} tenant={tenant} catalog={catalog} /> : null}
      {tab === 'whatsapp' ? <WhatsAppTab session={session} tenant={tenant} catalog={catalog} /> : null}
      {tab === 'audit' ? <AuditTab session={session} tenant={tenant} catalog={catalog} /> : null}
    </div>
  );
}

/**
 * ما تبقّى هنا بعد صف الـKPIs بالأعلى (الحالة/التطبيق/التواريخ صارت هناك، أوضح وملوّنة، والـslug
 * بالرأس أصلاً) — فقط ما لا يظهر بمكان ثانٍ: الرقم التعريفي الكامل، وفجوة معروفة صريحة (المسوّق).
 */
function OverviewTab({ tenant }: { tenant: Tenant }) {
  return (
    <div className="flex flex-col gap-3">
      <Row label="المعرّف"><span dir="ltr" className="text-text-secondary">{tenant.id}</span></Row>
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

/** minor units (halalas) to a "12.34 SAR" string — the one place this file formats money, so every
 *  amount on this tab reads the same way. */
function money(minor: number, currency: string): string {
  return `${(minor / 100).toFixed(2)} ${currency}`;
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

  // مؤشرات حقيقية من نفس البيانات المجلوبة هنا — لا استدعاء إضافي، لا رقم مُلفَّق. العملة تُقرأ من
  // أول فاتورة موجودة (كلها بنفس العملة لمنشأة واحدة) بدل افتراض "ريال" دائماً.
  const invRows = Array.isArray(invoices) ? invoices : [];
  const currency = invRows[0]?.currency ?? 'SAR';
  const overdue = invRows.filter((i) => i.status === 'open' || i.status === 'partially_paid');
  const overdueTotal = overdue.reduce((sum, i) => sum + i.total_minor, 0);
  const paidTotal = invRows.filter((i) => i.status === 'paid').reduce((sum, i) => sum + i.total_minor, 0);
  const activeApps = Array.isArray(subs) ? subs.filter((s) => s.status === 'active').length : 0;

  const subColumns: TableColumn<Subscription>[] = [
    { key: 'app', header: 'التطبيق', render: (s) => planNames.get(s.plan_id) ?? s.plan_id },
    { key: 'status', header: 'الحالة', render: (s) => (
      <Badge tone={SUB_STATUS_META[s.status]?.tone ?? 'neutral'}>{SUB_STATUS_META[s.status]?.label ?? s.status}</Badge>
    ) },
  ];
  const invColumns: TableColumn<Invoice>[] = [
    { key: 'number', header: 'الفاتورة', render: (inv) => <span dir="ltr" className="font-mono">{inv.number || inv.id}</span> },
    { key: 'amount', header: 'المبلغ', render: (inv) => <span dir="ltr">{money(inv.total_minor, inv.currency)}</span> },
    { key: 'status', header: 'الحالة', render: (inv) => (
      <Badge tone={INVOICE_STATUS_META[inv.status]?.tone ?? 'neutral'}>{INVOICE_STATUS_META[inv.status]?.label ?? inv.status}</Badge>
    ) },
    { key: 'created', header: 'التاريخ', hideOnCard: true, render: (inv) => <span dir="ltr" className="text-label text-text-secondary">{inv.created?.slice(0, 10)}</span> },
  ];

  return (
    <div className="flex flex-col gap-5">
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
        <KpiCard icon={<Package size={18} />} label="تطبيقات نشطة" value={activeApps}
                tone={activeApps > 0 ? 'success' : 'warning'} />
        <KpiCard icon={<CircleAlert size={18} />} label="مستحق غير مدفوع" value={money(overdueTotal, currency)}
                tone={overdueTotal > 0 ? 'danger' : 'neutral'} hint={overdue.length ? `${overdue.length} فاتورة` : undefined} />
        <KpiCard icon={<CheckCircle2 size={18} />} label="محصَّل" value={money(paidTotal, currency)} tone="success" />
      </div>

      <div>
        <h3 className="mb-2 font-medium">التطبيقات المفعّلة</h3>
        {!subsAction ? <p className="text-sm text-text-secondary">لا صلاحية.</p> : (
          <Table columns={subColumns} rows={subs} getRowId={(s) => s.id}
                emptyTitle="بلا تطبيقات مفعّلة" failedTitle="تعذّرت قراءة التطبيقات" />
        )}
      </div>

      <div>
        <h3 className="mb-2 font-medium">الفواتير</h3>
        {!invAction ? <p className="text-sm text-text-secondary">لا صلاحية.</p> : (
          <Table columns={invColumns} rows={invoices} getRowId={(inv) => inv.id}
                emptyTitle="بلا فواتير" failedTitle="تعذّرت قراءة الفواتير" />
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

/** x/y — العدد الفعلي مقابل الحد المجمَّع من كل اشتراكات المحل (operations.tenant_capacity،
 * يقرأ نفس فحص entitlements/check اللي يمنع المحل من إضافة موظف/فرع فوق حده، لا مسار جديد).
 * ‎-1 = غير محدود أو تعذّر الوصول لخدمة الفوترة — تُعرض بلا سقف حينها، لا نخترع رقماً. */
function seatsLabel(current: number, limit: number): string {
  return limit < 0 ? String(current) : `${current}/${limit}`;
}

/** اللون يعكس القرب من الحد — لا نفس اللون المحايد لمحل مليان تمامًا ومحل بالكاد بدأ. غير محدود
 *  (limit < 0) يبقى محايداً دائماً — لا سقف يُقاس القرب منه. */
function capacityTone(current: number, limit: number): 'success' | 'warning' | 'danger' | 'neutral' {
  if (limit < 0) return 'neutral';
  if (current >= limit) return 'danger';
  if (limit > 0 && current / limit >= 0.8) return 'warning';
  return 'success';
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

  const branchTone = capacityTone(capacity.branches, capacity.branches_limit);
  const seatTone = capacityTone(capacity.operators, capacity.operators_limit);

  return (
    <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
      <KpiCard icon={<Building2 size={18} />} label="الفروع"
              value={seatsLabel(capacity.branches, capacity.branches_limit)} tone={branchTone}
              hint={branchTone === 'danger' ? 'وصل الحد — إضافة فرع تحتاج ترقية' :
                    branchTone === 'warning' ? 'قريب من الحد' : undefined} />
      <KpiCard icon={<Users size={18} />} label="الموظفون"
              value={seatsLabel(capacity.operators, capacity.operators_limit)} tone={seatTone}
              hint={seatTone === 'danger' ? 'وصل الحد — إضافة موظف تحتاج ترقية' :
                    seatTone === 'warning' ? 'قريب من الحد' : undefined} />
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
