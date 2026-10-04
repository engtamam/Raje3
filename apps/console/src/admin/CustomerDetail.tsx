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
 * الخاص من تبويب "الحملات" بالكونسول (screens/Messages.tsx)، يُقدَّم مباشرة لاعتماد Meta على
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
import { Activity, ArrowRight, Building2, CheckCircle2, CircleAlert, Clock, FileSearch, Gavel, History, MessageCircle, Package, RefreshCw, ShieldCheck, Ticket, Users } from 'lucide-react';
import { Badge } from './../rj-ui/Badge';
import { Segmented } from './../rj-ui/Segmented';
import { Button } from './../rj-ui/Button';
import { KpiCard } from './../rj-ui/KpiCard';
import { Table, type TableColumn } from './../rj-ui/Table';
import { Input, Select } from './../rj-ui/Field';
import { ConfirmDialog } from './../rj-ui/ConfirmDialog';
import { req, AdminRefused, type AdminSession } from './api';
import type { AdminCatalog } from './catalog';
import { findCustomerAction, SUB_STATUS_META, type Tenant, type Subscription } from './CustomerList';
import { StatusBadge, type DeliveryRow } from './AdminWhatsAppDiagnostics';
import { Toggle } from './../rj-ui/Toggle';
import { appDisplayName, appKey, type Plan } from './../billingShared';

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

type Tab = 'overview' | 'billing' | 'seats' | 'tickets' | 'whatsapp' | 'privacy' | 'audit';

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
                  { value: 'privacy', label: 'الخصوصية والدعم' },
                  { value: 'audit', label: 'السجل والتدقيق' },
                ]} />

      {tab === 'overview' ? <OverviewTab tenant={tenant} /> : null}
      {tab === 'billing' ? <BillingTab session={session} tenant={tenant} catalog={catalog} planNames={planNames} /> : null}
      {tab === 'seats' ? <SeatsTab session={session} tenant={tenant} catalog={catalog} /> : null}
      {tab === 'tickets' ? <TicketsTab session={session} tenant={tenant} catalog={catalog} /> : null}
      {tab === 'whatsapp' ? <WhatsAppTab session={session} tenant={tenant} catalog={catalog} /> : null}
      {tab === 'privacy' ? <PrivacySupportTab session={session} tenant={tenant} catalog={catalog} /> : null}
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

      <AppVisibilityPanel session={session} tenant={tenant} catalog={catalog} />
    </div>
  );
}

/**
 * تطبيقات مخفية عن الجميع، أظهرها لهذا المحل تحديداً — core/app_visibility.py's own module
 * docstring للتصميم الكامل. لا يشترك أحداً: يظهر التطبيق (أو يختفي) في متجر هذا المحل وحده، والمحل
 * يشترك بنفسه بزر "اشترك" العادي بمجرد ما يشوفه.
 *
 * المرشَّحون فقط التطبيقات غير المُدرَجة أصلاً (`listed: false`) — تطبيق مُدرَج للجميع أصلاً لا
 * معنى لتخصيصه لمحل واحد. `billing.list_plans?include_hidden=true` هو نفس القراءة PlanCards.tsx
 * تستخدمها بالضبط، فتشمل الصفوف غير المُدرَجة.
 */
function AppVisibilityPanel({ session, tenant, catalog }: {
  session: AdminSession; tenant: Tenant; catalog: AdminCatalog;
}) {
  const listAction = findCustomerAction(catalog, 'billing.list_plans');
  const overridesGetAction = findCustomerAction(catalog, 'operations.app_visibility_list');
  const overridesSetAction = findCustomerAction(catalog, 'operations.app_visibility_set');

  const [unlistedPlans, setUnlistedPlans] = useState<Plan[] | 'loading' | 'failed'>('loading');
  const [visibleKeys, setVisibleKeys] = useState<Set<string> | 'loading' | 'failed'>('loading');
  const [busyKey, setBusyKey] = useState('');
  const [error, setError] = useState('');

  const reloadOverrides = () => {
    if (!overridesGetAction) { setVisibleKeys('failed'); return; }
    req<{ overrides: { feature_key: string; visible: boolean }[] }>(
      `${overridesGetAction.path}?tenant=${encodeURIComponent(tenant.id)}`,
      'GET', undefined, session.access_token)
      .then((r) => setVisibleKeys(new Set(r.overrides.filter((o) => o.visible).map((o) => o.feature_key))))
      .catch(() => setVisibleKeys('failed'));
  };

  useEffect(() => {
    if (!listAction) { setUnlistedPlans('failed'); return; }
    req<{ plans: Plan[] }>(`${listAction.path}?include_hidden=true`, 'GET', undefined, session.access_token)
      .then((r) => setUnlistedPlans(r.plans.filter((p) => p.listed === false && !!appKey(p))))
      .catch(() => setUnlistedPlans('failed'));
    reloadOverrides();
    // eslint-disable-next-line react-hooks/exhaustive-deps -- runs once per opened tenant
  }, [tenant.id]);

  if (!overridesGetAction || !overridesSetAction) return null; // لا صلاحية — القسم يختفي كلياً
  if (unlistedPlans === 'failed' || visibleKeys === 'failed') {
    return <p role="alert" className="text-danger text-sm">تعذّرت قراءة تطبيقات مخفية.</p>;
  }
  if (unlistedPlans === 'loading' || visibleKeys === 'loading') {
    return <p className="text-sm text-text-secondary">جارٍ التحميل…</p>;
  }
  if (unlistedPlans.length === 0) return null; // لا تطبيقات مخفية على المنصة حالياً

  const toggle = async (plan: Plan, next: boolean) => {
    const key = appKey(plan);
    setBusyKey(key);
    setError('');
    try {
      await req(overridesSetAction.path, 'PUT',
        { tenant: tenant.id, feature_key: key, visible: next }, session.access_token);
      reloadOverrides();
    } catch (e) {
      setError(errMsg(e));
    } finally {
      setBusyKey('');
    }
  };

  return (
    <div>
      <h3 className="mb-2 font-medium">تطبيقات مخفية عن الجميع — أظهرها لهذا المحل تحديداً</h3>
      <p className="mb-3 text-label text-text-secondary">
        لا يشترك المحل تلقائياً — يظهر له التطبيق في متجره فقط، وهو يشترك بنفسه إن أراد.
      </p>
      <div className="flex flex-col gap-2">
        {unlistedPlans.map((plan) => {
          const key = appKey(plan);
          const name = appDisplayName(plan);
          return (
            <div key={plan.id} className="flex items-center justify-between rounded-card border border-border-subtle p-3">
              <span className="text-sm">{name}</span>
              <Toggle checked={visibleKeys.has(key)} disabled={busyKey === key}
                     onChange={(next) => toggle(plan, next)}
                     ariaLabel={`أظهر ${name} لهذا المحل`} />
            </div>
          );
        })}
      </div>
      {error ? <p role="alert" className="mt-2 text-sm text-danger">{error}</p> : null}
    </div>
  );
}

interface AuditEvent {
  id: string; seq: number; ts: string; service: string; action: string;
  actor: string; resource: string; ip: string;
}

/** لون الفعل من نوعه — بلا خريطة أفعال ثابتة (الأفعال حرة، مصدرها 20+ خدمة، لا تعداد يُحصى).
 *  نفس أسلوب statusTone/severityTone بهذا الملف: تصنيف من جزء الكلمة، لا مطابقة تامة. حذف/سحب/
 *  رفض أحمر (فعل ناقض)، منح/إنشاء/تأكيد أخضر (فعل بنّاء)، قراءة/تصدير/عرض أزرق معلوماتي (لا
 *  تغيير)، الباقي محايد. */
function auditTone(action: string): 'success' | 'warning' | 'danger' | 'info' | 'neutral' {
  const a = action.toLowerCase();
  if (/delet|revok|refus|reject|suspend|remov|withdr|release/.test(a)) return 'danger';
  if (/grant|creat|placed?|approv|confirm|set_|_set|regist/.test(a)) return 'success';
  if (/view|read|query|export|scan|search/.test(a)) return 'info';
  return 'neutral';
}

interface AuditFilters { actor: string; action: string; service: string; hours: string; }
const AUDIT_EMPTY_FILTERS: AuditFilters = { actor: '', action: '', service: '', hours: '' };

/**
 * سجل التدقيق — أعيد بناؤه ليكون مفهوماً لغير التقني: كل فعل بلونه حسب نوعه (لا نص خام يحتاج
 * خبرة تقنية يفسّره)، وفلاتره الثلاثة (الفاعل/الفعل/الخدمة) قوائم اختيار من القيم الحقيقية
 * الظاهرة بالصفحة — لا كتابة يدوية، ولا فلتر بلا معنى (اختيار قيمة غير موجودة أصلاً). المدة
 * الزمنية وحدها تبقى قائمة مدد جاهزة (نفس نمط AdminSignals.tsx's own HOUR_PRESETS) بدل تاريخ
 * حرّ يحتاج فهم صيغة.
 *
 * audit.query يدعم فلتر tenant فعلاً بالخادم (services/audit-service's own admin_actions.py) —
 * على عكس ما ذكرته أول مرة بالاقتراح (كنت أفترض فجوة هنا، والفحص المباشر للكود نفى ذلك). هذا
 * التبويب إذن جاهز بالكامل من أول مرحلة 2، بلا أي عمل خلفي جديد — والفلاتر الأربعة (actor/action/
 * service/since) فعلية بالخادم أيضاً (audit-service's own admin_actions.py، مُعلَنة صراحة).
 */
function AuditTab({ session, tenant, catalog }: { session: AdminSession; tenant: Tenant; catalog: AdminCatalog }) {
  const [events, setEvents] = useState<AuditEvent[] | 'loading' | 'failed'>('loading');
  const [filters, setFilters] = useState<AuditFilters>(AUDIT_EMPTY_FILTERS);
  const action = findCustomerAction(catalog, 'audit.query');

  useEffect(() => {
    if (!action) { setEvents('failed'); return; }
    setEvents('loading');
    const p = new URLSearchParams({ tenant: tenant.id, limit: '100' });
    if (filters.actor) p.set('actor', filters.actor);
    if (filters.action) p.set('action', filters.action);
    if (filters.service) p.set('service', filters.service);
    if (filters.hours) p.set('since', new Date(Date.now() - Number(filters.hours) * 3600_000).toISOString());
    req<{ events: AuditEvent[] }>(`${action.path}?${p.toString()}`, 'GET', undefined, session.access_token)
      .then((r) => setEvents(r.events)).catch(() => setEvents('failed'));
    // eslint-disable-next-line react-hooks/exhaustive-deps -- refetches on tenant AND any filter change
  }, [tenant.id, filters]);

  if (!action) return <p className="text-sm text-text-secondary">لا صلاحية.</p>;
  if (events === 'failed') return <p role="alert" className="text-danger text-sm">تعذّرت قراءة السجل.</p>;

  const shown = events === 'loading' ? [] : events;
  const distinct = (key: 'actor' | 'action' | 'service'): string[] => {
    const vals = new Set<string>(shown.map((e) => e[key]).filter(Boolean));
    if (filters[key]) vals.add(filters[key]);
    return Array.from(vals).sort();
  };
  const critical = shown.filter((e) => auditTone(e.action) === 'danger').length;
  const hasActiveFilter = filters.actor || filters.action || filters.service || filters.hours;

  const columns: TableColumn<AuditEvent>[] = [
    { key: 'ts', header: 'الوقت', render: (e) => <span dir="ltr" className="text-label text-text-secondary">{new Date(e.ts).toLocaleString('ar-SA-u-nu-latn')}</span> },
    { key: 'action', header: 'الفعل', render: (e) => <Badge tone={auditTone(e.action)}>{e.action}</Badge> },
    { key: 'service', header: 'الخدمة', hideOnCard: true, render: (e) => <span dir="ltr" className="text-text-secondary">{e.service}</span> },
    { key: 'actor', header: 'الفاعل', render: (e) => <span dir="ltr" className="font-mono text-label text-text-muted">{e.actor || '—'}</span> },
    { key: 'resource', header: 'العنصر', hideOnCard: true, render: (e) => <span dir="ltr" className="font-mono text-label text-text-muted">{e.resource || '—'}</span> },
  ];

  return (
    <div className="flex flex-col gap-4">
      {shown.length > 0 ? (
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-2">
          <KpiCard icon={<History size={18} />} label="أحداث معروضة" value={shown.length} tone="neutral" />
          <KpiCard icon={<CircleAlert size={18} />} label="أفعال حسّاسة (حذف/سحب/رفض)" value={critical}
                  tone={critical > 0 ? 'danger' : 'neutral'} />
        </div>
      ) : null}

      <div className="flex flex-wrap items-center gap-2">
        <Select value={filters.actor} onChange={(e) => setFilters((f) => ({ ...f, actor: e.target.value }))}
               className="w-auto min-w-32" aria-label="فلترة بالفاعل">
          <option value="">كل الفاعلين</option>
          {distinct('actor').map((a) => <option key={a} value={a}>{a}</option>)}
        </Select>
        <Select value={filters.action} onChange={(e) => setFilters((f) => ({ ...f, action: e.target.value }))}
               className="w-auto min-w-32" aria-label="فلترة بالفعل">
          <option value="">كل الأفعال</option>
          {distinct('action').map((a) => <option key={a} value={a}>{a}</option>)}
        </Select>
        <Select value={filters.service} onChange={(e) => setFilters((f) => ({ ...f, service: e.target.value }))}
               className="w-auto min-w-32" aria-label="فلترة بالخدمة">
          <option value="">كل الخدمات</option>
          {distinct('service').map((s) => <option key={s} value={s}>{s}</option>)}
        </Select>
        <Select value={filters.hours} onChange={(e) => setFilters((f) => ({ ...f, hours: e.target.value }))}
               className="w-auto min-w-32" aria-label="فلترة بالمدة">
          <option value="">كل المدة</option>
          <option value="24">آخر 24 ساعة</option>
          <option value="168">آخر أسبوع</option>
          <option value="720">آخر 30 يوم</option>
        </Select>
        {hasActiveFilter ? (
          <button type="button" onClick={() => setFilters(AUDIT_EMPTY_FILTERS)} className="text-label text-brand">
            مسح الفلاتر
          </button>
        ) : null}
      </div>

      <Table columns={columns} rows={events} getRowId={(e) => e.id}
            emptyTitle={hasActiveFilter ? 'لا أحداث تطابق هذي الفلاتر' : 'لا أحداث بعد على هذا العميل'}
            failedTitle="تعذّرت قراءة السجل" />
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
              <div key={e.id} className="rounded-lg border border-border-subtle bg-surface-1 p-3 text-sm">
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
  // مؤشرات من نفس القائمة المجلوبة — على حسب لون statusTone (تصعيد/انتظار)، لا تعداد حالة ثابت
  // (الحالة تدفّق عمل حرّ لكل تينانت، statusTone نفسه أصلاً مبني على نفس الأساس). العدد عن
  // الصفحة المعروضة فقط، مو كل تذاكر العميل تاريخياً — لا رقم يوهم بأنه إجمالي شامل.
  const shownTickets = tickets === 'loading' || tickets === 'failed' ? [] : tickets;
  const escalated = shownTickets.filter((t) => statusTone(t.status) === 'danger').length;
  const pending = shownTickets.filter((t) => statusTone(t.status) === 'warning').length;

  const columns: TableColumn<TicketSummary>[] = [
    { key: 'id', header: 'التذكرة', render: (t) => <span dir="ltr" className="font-mono text-text-muted">{t.id}</span> },
    { key: 'type', header: 'النوع', render: (t) => t.type || '—' },
    { key: 'priority', header: 'الأولوية', hideOnCard: true, render: (t) => t.priority || '—' },
    { key: 'assignee', header: 'المسؤول', hideOnCard: true, render: (t) => <span dir="ltr">{t.assignee || '—'}</span> },
    { key: 'updated', header: 'آخر تحديث', render: (t) => <span dir="ltr" className="text-label text-text-secondary">{new Date(t.updated).toLocaleString('ar-SA')}</span> },
    { key: 'status', header: 'الحالة', render: (t) => <Badge tone={statusTone(t.status)}>{t.status}</Badge> },
  ];

  return (
    <div className="flex flex-col gap-4">
      {shownTickets.length > 0 ? (
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
          <KpiCard icon={<Ticket size={18} />} label="المعروضة" value={shownTickets.length} tone="neutral" />
          <KpiCard icon={<CircleAlert size={18} />} label="مصعَّدة" value={escalated} tone={escalated > 0 ? 'danger' : 'neutral'} />
          <KpiCard icon={<Clock size={18} />} label="بالانتظار" value={pending} tone={pending > 0 ? 'warning' : 'neutral'} />
        </div>
      ) : null}

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

      <Table columns={columns} rows={tickets} getRowId={(t) => t.id} onRowClick={(t) => setSelected(t.id)}
            emptyTitle={hasActiveFilter ? 'لا تذاكر تطابق هذي الفلاتر' : 'لا تذاكر لهذا العميل'}
            failedTitle="تعذّرت قراءة التذاكر" />
      {cursor ? (
        <button type="button" onClick={loadMore} disabled={loadingMore}
                className="self-center text-label text-brand disabled:opacity-50">
          {loadingMore ? 'جارٍ التحميل…' : 'حمّل المزيد'}
        </button>
      ) : null}
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
  if (rows === 'failed') return <p role="alert" className="text-danger text-sm">تعذّرت القراءة.</p>;

  // مؤشرات من نفس السجل المجلوب — لا استدعاء إضافي. «نجحت» تشمل sent/delivered (نفس تعريف
  // StatusBadge's own tone success)، حتى تقرأ العين "كم وصل" بنظرة واحدة بدل عدّ الشارات صفاً صفاً.
  const shown = rows === 'loading' ? [] : rows;
  const sent = shown.filter((r) => r.status === 'sent' || r.status === 'delivered').length;
  const failed = shown.filter((r) => r.status === 'failed' || r.status === 'suppressed').length;

  const columns: TableColumn<DeliveryRow>[] = [
    { key: 'recipient', header: 'المستلم', render: (r) => <span dir="ltr" className="font-mono text-text-muted">{r.recipient_masked ?? '—'}</span> },
    { key: 'status', header: 'الحالة', render: (r) => <StatusBadge status={r.status} /> },
    { key: 'receipt', header: 'حالة ميتا', hideOnCard: true, render: (r) => r.receipt_status ? <span className="text-text-secondary">{r.receipt_status}</span> : <span className="text-text-muted">—</span> },
    { key: 'error', header: 'الخطأ', render: (r) => r.error ? <span className="text-danger">{r.error}</span> : <span className="text-text-muted">—</span> },
    { key: 'created', header: 'الوقت', render: (r) => r.created ? <span dir="ltr" className="text-label text-text-secondary">{new Date(r.created).toLocaleString('ar-SA')}</span> : '—' },
  ];

  return (
    <div className="flex flex-col gap-4">
      {shown.length > 0 ? (
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
          <KpiCard icon={<MessageCircle size={18} />} label="المعروضة" value={shown.length} tone="neutral" />
          <KpiCard icon={<CheckCircle2 size={18} />} label="وصلت" value={sent} tone={sent > 0 ? 'success' : 'neutral'} />
          <KpiCard icon={<CircleAlert size={18} />} label="فشلت" value={failed} tone={failed > 0 ? 'danger' : 'neutral'} />
        </div>
      ) : null}
      <Table columns={columns} rows={rows} getRowId={(r) => r.id ?? `${r.recipient_masked}-${r.created}`}
            emptyTitle="لا رسائل واتساب مسجَّلة لهذا المحل" failedTitle="تعذّرت قراءة سجل واتساب" />
    </div>
  );
}

/** The one sentence a refused admin action carries — same idiom AdminRefused already uses
 *  everywhere else in this panel. */
function errMsg(e: unknown): string {
  return e instanceof AdminRefused ? e.message : 'تعذّر إكمال الطلب. حاول مرة أخرى.';
}

interface DsarRow {
  id: string; tenant: string; subject: string; subject_kind: string; type: string;
  status: string; verified: boolean; targets: Record<string, boolean>;
  refusal_reason: string; created_at: number; deadline_at: number; completed_at: number;
}

interface LegalHoldRow {
  id: string; tenant: string; subject: string; reason: string; active: boolean;
  placed_at: number; released_at: number;
}

interface ConsentRow {
  tenant: string; subject: string; purpose: string; granted: boolean;
  notice_version: string; method: string; expires_at: number; updated_at: number;
  basis: string; consented_by: string; relation: string;
}

interface ConsentProofRow {
  id: string; subject: string; purpose: string; action: string; at: number;
  actor: string; basis: string;
}

function unixDate(sec: number): string {
  return sec ? new Date(sec * 1000).toLocaleDateString('ar-SA-u-nu-latn') : '—';
}

const DSAR_STATUS_TONE: Record<string, 'neutral' | 'success' | 'danger' | 'warning'> = {
  pending: 'warning', in_progress: 'warning', completed: 'success', refused: 'danger',
};

/**
 * المرحلة أ — توصيل خمس مجموعات إجراءات موجودة فعلاً بالكتالوج الإداري (compliance-service،
 * operations، loyalty) بلا أي شغل خلفي جديد: طلبات الخصوصية (DSAR)، سجل الموافقة، الحجز
 * القانوني، إصلاح رصيد نقاط عميل، وملف الأدلة. كل مجموعة تختفي بأدب ("لا صلاحية") لو الكتالوج
 * ما يحمل إجراءها — بلا استثناء يوقف باقي التبويب.
 */
function PrivacySupportTab({ session, tenant, catalog }: {
  session: AdminSession; tenant: Tenant; catalog: AdminCatalog;
}) {
  return (
    <div className="flex flex-col gap-8">
      <DsarSection session={session} tenant={tenant} catalog={catalog} />
      <ConsentSection session={session} tenant={tenant} catalog={catalog} />
      <LegalHoldsSection session={session} tenant={tenant} catalog={catalog} />
      <LoyaltySection session={session} tenant={tenant} catalog={catalog} />
      <EvidenceFileSection session={session} tenant={tenant} catalog={catalog} />
    </div>
  );
}

function SectionHeader({ icon, title }: { icon: React.ReactNode; title: string }) {
  return (
    <h3 className="flex items-center gap-2 font-medium text-text-primary">
      {icon}{title}
    </h3>
  );
}

/** طلبات الخصوصية (DSAR) — فتح/تحقّق/تنفيذ، وقائمة طلبات هذا المحل. */
function DsarSection({ session, tenant, catalog }: {
  session: AdminSession; tenant: Tenant; catalog: AdminCatalog;
}) {
  const [rows, setRows] = useState<DsarRow[] | 'loading' | 'failed'>('loading');
  const [subject, setSubject] = useState('');
  const [type, setType] = useState<'erase' | 'export'>('export');
  const [opening, setOpening] = useState(false);
  const [openErr, setOpenErr] = useState('');
  const [tokens, setTokens] = useState<Record<string, string>>({});
  const [busyId, setBusyId] = useState<string | null>(null);
  const [armProcess, setArmProcess] = useState<DsarRow | null>(null);
  const [rowErr, setRowErr] = useState('');

  const listAction = findCustomerAction(catalog, 'compliance.list_dsar');
  const openAction = findCustomerAction(catalog, 'compliance.open_dsar');
  const verifyAction = findCustomerAction(catalog, 'compliance.verify_dsar');
  const processAction = findCustomerAction(catalog, 'compliance.process_dsar');

  const load = () => {
    if (!listAction) { setRows('failed'); return; }
    req<{ requests: DsarRow[] }>(
      `${listAction.path}?tenant=${encodeURIComponent(tenant.id)}`, 'GET', undefined, session.access_token)
      .then((r) => setRows(r.requests ?? [])).catch(() => setRows('failed'));
  };
  useEffect(load, [tenant.id]); // eslint-disable-line react-hooks/exhaustive-deps

  const openDsar = async () => {
    if (!openAction || !subject.trim()) return;
    setOpening(true); setOpenErr('');
    try {
      await req(openAction.path, 'POST', { tenant: tenant.id, subject: subject.trim(), type },
                session.access_token);
      setSubject('');
      load();
    } catch (e) {
      setOpenErr(errMsg(e));
    } finally {
      setOpening(false);
    }
  };

  const verify = async (row: DsarRow) => {
    if (!verifyAction) return;
    const token = (tokens[row.id] ?? '').trim();
    if (!token) return;
    setBusyId(row.id); setRowErr('');
    try {
      const path = verifyAction.path.replace('{dsar_id}', encodeURIComponent(row.id));
      await req(`${path}?token=${encodeURIComponent(token)}&tenant=${encodeURIComponent(tenant.id)}`,
                'POST', undefined, session.access_token);
      load();
    } catch (e) {
      setRowErr(errMsg(e));
    } finally {
      setBusyId(null);
    }
  };

  const process = async (row: DsarRow) => {
    if (!processAction) return;
    setBusyId(row.id); setRowErr('');
    try {
      const path = processAction.path.replace('{dsar_id}', encodeURIComponent(row.id));
      await req(`${path}?tenant=${encodeURIComponent(tenant.id)}`, 'POST', undefined, session.access_token);
      setArmProcess(null);
      load();
    } catch (e) {
      setRowErr(errMsg(e));
    } finally {
      setBusyId(null);
    }
  };

  const columns: TableColumn<DsarRow>[] = [
    { key: 'subject', header: 'صاحب الطلب', render: (d) => <span dir="ltr" className="font-mono text-text-muted">{d.subject}</span> },
    { key: 'type', header: 'النوع', render: (d) => (d.type === 'erase' ? 'حذف' : 'اطّلاع') },
    { key: 'status', header: 'الحالة', render: (d) => <Badge tone={DSAR_STATUS_TONE[d.status] ?? 'neutral'}>{d.status}</Badge> },
    { key: 'verified', header: 'مؤكّد الهوية', hideOnCard: true, render: (d) => (d.verified ? 'نعم' : 'لا') },
    { key: 'created_at', header: 'فُتح', render: (d) => unixDate(d.created_at) },
    { key: 'deadline_at', header: 'الموعد النهائي', hideOnCard: true, render: (d) => unixDate(d.deadline_at) },
    {
      key: 'actions', header: 'إجراء', render: (d) => {
        if (d.status === 'completed' || d.status === 'refused') return <span className="text-text-muted">—</span>;
        if (!d.verified) {
          if (!verifyAction) return <span className="text-text-muted">—</span>;
          return (
            <div className="flex items-center gap-1">
              <Input value={tokens[d.id] ?? ''} placeholder="رمز التحقّق"
                    onChange={(e) => setTokens((t) => ({ ...t, [d.id]: e.target.value }))}
                    className="w-28" />
              <Button size="sm" variant="outline" disabled={busyId === d.id || !(tokens[d.id] ?? '').trim()}
                      onClick={() => void verify(d)}>تحقّق</Button>
            </div>
          );
        }
        if (!processAction) return <span className="text-text-muted">—</span>;
        return (
          <Button size="sm" variant="danger" disabled={busyId === d.id} onClick={() => setArmProcess(d)}>
            نفّذ
          </Button>
        );
      },
    },
  ];

  return (
    <div className="flex flex-col gap-3">
      <SectionHeader icon={<FileSearch size={18} />} title="طلبات الخصوصية (DSAR)" />
      {!listAction ? <p className="text-sm text-text-secondary">لا صلاحية.</p> : (
        <>
          {openAction ? (
            <div className="flex flex-wrap items-end gap-2">
              <Input value={subject} onChange={(e) => setSubject(e.target.value)}
                    placeholder="رقم جوال صاحب الطلب" className="w-40" aria-label="صاحب الطلب" />
              <Select value={type} onChange={(e) => setType(e.target.value as typeof type)}
                     className="w-auto" aria-label="نوع الطلب">
                <option value="export">اطّلاع</option>
                <option value="erase">حذف</option>
              </Select>
              <Button size="sm" disabled={opening || !subject.trim()} onClick={() => void openDsar()}>
                {opening ? 'جارٍ الفتح…' : 'فتح طلب جديد'}
              </Button>
              {openErr ? <p role="alert" className="text-danger text-sm">{openErr}</p> : null}
            </div>
          ) : null}
          {rowErr ? <p role="alert" className="text-danger text-sm">{rowErr}</p> : null}
          <Table columns={columns} rows={rows} getRowId={(d) => d.id}
                emptyTitle="لا طلبات خصوصية لهذا المحل" failedTitle="تعذّرت قراءة الطلبات" />
        </>
      )}
      <ConfirmDialog open={armProcess !== null} onClose={() => setArmProcess(null)}
                    onConfirm={() => armProcess && void process(armProcess)}
                    title="تنفيذ طلب الخصوصية" danger busy={busyId === armProcess?.id}
                    body="سيُرسَل الطلب لكل الخدمات المعنية لتنفيذه فعلياً — لا تراجع بعده.">
      </ConfirmDialog>
    </div>
  );
}

/** سجل الموافقة — بحث برقم صاحب العلاقة، ثم عرض المنح والسحب + نموذجا منح/سحب. */
function ConsentSection({ session, tenant, catalog }: {
  session: AdminSession; tenant: Tenant; catalog: AdminCatalog;
}) {
  const [subject, setSubject] = useState('');
  const [asked, setAsked] = useState('');
  const [consents, setConsents] = useState<ConsentRow[] | 'loading' | 'failed' | null>(null);
  const [proofs, setProofs] = useState<ConsentProofRow[]>([]);
  const [purpose, setPurpose] = useState('');
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState('');
  const [armWithdraw, setArmWithdraw] = useState<ConsentRow | null>(null);

  const historyAction = findCustomerAction(catalog, 'compliance.consent_history');
  const grantAction = findCustomerAction(catalog, 'compliance.grant_consent');
  const withdrawAction = findCustomerAction(catalog, 'compliance.withdraw_consent');

  const search = () => {
    if (!historyAction || !subject.trim()) return;
    setConsents('loading'); setAsked(subject.trim());
    req<{ consents: ConsentRow[]; proofs: ConsentProofRow[] }>(
      `${historyAction.path}?subject=${encodeURIComponent(subject.trim())}&tenant=${encodeURIComponent(tenant.id)}`,
      'GET', undefined, session.access_token)
      .then((r) => { setConsents(r.consents ?? []); setProofs(r.proofs ?? []); })
      .catch(() => setConsents('failed'));
  };

  const grant = async () => {
    if (!grantAction || !asked || !purpose.trim()) return;
    setBusy(true); setErr('');
    try {
      await req(grantAction.path, 'POST', { tenant: tenant.id, subject: asked, purpose: purpose.trim() },
                session.access_token);
      setPurpose('');
      search();
    } catch (e) {
      setErr(errMsg(e));
    } finally {
      setBusy(false);
    }
  };

  const withdraw = async (row: ConsentRow) => {
    if (!withdrawAction) return;
    setBusy(true);
    try {
      await req(withdrawAction.path, 'POST', { tenant: tenant.id, subject: row.subject, purpose: row.purpose },
                session.access_token);
      setArmWithdraw(null);
      search();
    } catch (e) {
      setErr(errMsg(e));
    } finally {
      setBusy(false);
    }
  };

  const consentColumns: TableColumn<ConsentRow>[] = [
    { key: 'purpose', header: 'الغرض' },
    { key: 'granted', header: 'الحالة', render: (c) => <Badge tone={c.granted ? 'success' : 'danger'}>{c.granted ? 'ممنوحة' : 'مسحوبة'}</Badge> },
    { key: 'basis', header: 'الأساس', hideOnCard: true, render: (c) => (c.basis === 'self' ? 'شخصي' : c.basis) },
    { key: 'updated_at', header: 'آخر تحديث', render: (c) => unixDate(c.updated_at) },
    {
      key: 'actions', header: 'إجراء', render: (c) => (
        !withdrawAction || !c.granted ? <span className="text-text-muted">—</span> :
        <Button size="sm" variant="danger" onClick={() => setArmWithdraw(c)}>سحب</Button>
      ),
    },
  ];

  const proofColumns: TableColumn<ConsentProofRow>[] = [
    { key: 'purpose', header: 'الغرض' },
    { key: 'action', header: 'الفعل', render: (p) => (p.action === 'granted' ? 'منح' : 'سحب') },
    { key: 'actor', header: 'الفاعل', hideOnCard: true, render: (p) => <span dir="ltr" className="text-text-muted">{p.actor || '—'}</span> },
    { key: 'at', header: 'الوقت', render: (p) => unixDate(p.at) },
  ];

  return (
    <div className="flex flex-col gap-3">
      <SectionHeader icon={<ShieldCheck size={18} />} title="سجل الموافقة" />
      {!historyAction ? <p className="text-sm text-text-secondary">لا صلاحية.</p> : (
        <>
          <div className="flex flex-wrap items-center gap-2">
            <Input value={subject} onChange={(e) => setSubject(e.target.value)}
                  placeholder="رقم جوال صاحب العلاقة" className="w-40" aria-label="صاحب العلاقة" />
            <Button size="sm" variant="outline" disabled={!subject.trim()} onClick={search}>ابحث</Button>
          </div>
          {consents === null ? null : (
            <>
              {grantAction && asked ? (
                <div className="flex flex-wrap items-end gap-2">
                  <Input value={purpose} onChange={(e) => setPurpose(e.target.value)}
                        placeholder="الغرض (مثال: تسويق)" className="w-40" aria-label="الغرض" />
                  <Button size="sm" disabled={busy || !purpose.trim()} onClick={() => void grant()}>
                    منح موافقة
                  </Button>
                </div>
              ) : null}
              {err ? <p role="alert" className="text-danger text-sm">{err}</p> : null}
              <Table columns={consentColumns} rows={consents} getRowId={(c) => `${c.subject}-${c.purpose}`}
                    emptyTitle="لا موافقات مسجَّلة لهذا الرقم" failedTitle="تعذّرت قراءة السجل" />
              {proofs.length > 0 ? (
                <div>
                  <h4 className="mb-2 text-label text-text-muted">سجل الأحداث</h4>
                  <Table columns={proofColumns} rows={proofs} getRowId={(p) => p.id}
                        emptyTitle="" failedTitle="" />
                </div>
              ) : null}
            </>
          )}
        </>
      )}
      <ConfirmDialog open={armWithdraw !== null} onClose={() => setArmWithdraw(null)}
                    onConfirm={() => armWithdraw && void withdraw(armWithdraw)}
                    title="سحب الموافقة" danger busy={busy}
                    body={armWithdraw ? `سيُسحَب غرض «${armWithdraw.purpose}» فوراً.` : ''}>
      </ConfirmDialog>
    </div>
  );
}

/** الحجز القانوني — قائمة حجوزات المحل + نموذج وضع حجز جديد + رفع الحجز. */
function LegalHoldsSection({ session, tenant, catalog }: {
  session: AdminSession; tenant: Tenant; catalog: AdminCatalog;
}) {
  const [rows, setRows] = useState<LegalHoldRow[] | 'loading' | 'failed'>('loading');
  const [subject, setSubject] = useState('');
  const [reason, setReason] = useState('');
  const [placing, setPlacing] = useState(false);
  const [err, setErr] = useState('');
  const [armRelease, setArmRelease] = useState<LegalHoldRow | null>(null);
  const [busy, setBusy] = useState(false);

  const listAction = findCustomerAction(catalog, 'compliance.list_legal_holds');
  const placeAction = findCustomerAction(catalog, 'compliance.place_legal_hold');
  const releaseAction = findCustomerAction(catalog, 'compliance.release_legal_hold');

  const load = () => {
    if (!listAction) { setRows('failed'); return; }
    req<{ holds: LegalHoldRow[] }>(
      `${listAction.path}?tenant=${encodeURIComponent(tenant.id)}`, 'GET', undefined, session.access_token)
      .then((r) => setRows(r.holds ?? [])).catch(() => setRows('failed'));
  };
  useEffect(load, [tenant.id]); // eslint-disable-line react-hooks/exhaustive-deps

  const place = async () => {
    if (!placeAction || !subject.trim() || !reason.trim()) return;
    setPlacing(true); setErr('');
    try {
      await req(placeAction.path, 'POST', { tenant: tenant.id, subject: subject.trim(), reason: reason.trim() },
                session.access_token);
      setSubject(''); setReason('');
      load();
    } catch (e) {
      setErr(errMsg(e));
    } finally {
      setPlacing(false);
    }
  };

  const release = async (row: LegalHoldRow) => {
    if (!releaseAction) return;
    setBusy(true);
    try {
      const path = releaseAction.path.replace('{id}', encodeURIComponent(row.id));
      await req(path, 'POST', undefined, session.access_token);
      setArmRelease(null);
      load();
    } catch (e) {
      setErr(errMsg(e));
    } finally {
      setBusy(false);
    }
  };

  const columns: TableColumn<LegalHoldRow>[] = [
    { key: 'subject', header: 'صاحب العلاقة', render: (h) => <span dir="ltr" className="font-mono text-text-muted">{h.subject}</span> },
    { key: 'reason', header: 'السبب' },
    { key: 'active', header: 'الحالة', render: (h) => <Badge tone={h.active ? 'warning' : 'neutral'}>{h.active ? 'قائم' : 'مرفوع'}</Badge> },
    { key: 'placed_at', header: 'وُضع', hideOnCard: true, render: (h) => unixDate(h.placed_at) },
    {
      key: 'actions', header: 'إجراء', render: (h) => (
        !releaseAction || !h.active ? <span className="text-text-muted">—</span> :
        <Button size="sm" variant="danger" onClick={() => setArmRelease(h)}>ارفع الحجز</Button>
      ),
    },
  ];

  return (
    <div className="flex flex-col gap-3">
      <SectionHeader icon={<Gavel size={18} />} title="الحجز القانوني" />
      {!listAction ? <p className="text-sm text-text-secondary">لا صلاحية.</p> : (
        <>
          {placeAction ? (
            <div className="flex flex-wrap items-end gap-2">
              <Input value={subject} onChange={(e) => setSubject(e.target.value)}
                    placeholder="رقم جوال صاحب العلاقة" className="w-40" aria-label="صاحب العلاقة" />
              <Input value={reason} onChange={(e) => setReason(e.target.value)}
                    placeholder="سبب الحجز" className="w-48" aria-label="السبب" />
              <Button size="sm" disabled={placing || !subject.trim() || !reason.trim()}
                      onClick={() => void place()}>
                {placing ? 'جارٍ الوضع…' : 'ضع حجزاً'}
              </Button>
            </div>
          ) : null}
          {err ? <p role="alert" className="text-danger text-sm">{err}</p> : null}
          <Table columns={columns} rows={rows} getRowId={(h) => h.id}
                emptyTitle="لا حجوزات قانونية لهذا المحل" failedTitle="تعذّرت قراءة الحجوزات" />
        </>
      )}
      <ConfirmDialog open={armRelease !== null} onClose={() => setArmRelease(null)}
                    onConfirm={() => armRelease && void release(armRelease)}
                    title="رفع الحجز القانوني" danger busy={busy}
                    body="سيُسمَح بحذف بيانات صاحب العلاقة عند أي طلب لاحق — تأكد أن السبب انتهى فعلاً.">
      </ConfirmDialog>
    </div>
  );
}

interface LoyaltyEntryRow {
  id: string; tenant: string; subject_ref: string; delta: number; reason: string;
  source: string; actor: string; branch_id: string; balance_after: number;
  note: string; created_at: number;
}

const LOYALTY_REASON_LABEL: Record<string, string> = {
  earn: 'كسب', redeem: 'استبدال', expire: 'انتهاء صلاحية', adjust: 'تعديل يدوي',
};

/** نقاط الولاء — رصيد وسجل حركات عميل معيّن (بصلاحية منصة، لأي منشأة)، وإصلاح الرصيد من نفس
 *  المكان بدل ما يُصلَح بالعمى. */
function LoyaltySection({ session, tenant, catalog }: {
  session: AdminSession; tenant: Tenant; catalog: AdminCatalog;
}) {
  const [subjectRef, setSubjectRef] = useState('');
  const [asked, setAsked] = useState('');
  const [balance, setBalance] = useState<{ points: number } | 'loading' | 'failed' | null>(null);
  const [entries, setEntries] = useState<LoyaltyEntryRow[]>([]);
  const [reason, setReason] = useState('');
  const [arm, setArm] = useState(false);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState('');
  // THE REAL RESPONSE SHAPE — `app/core/ledger.py::reconcile()`, verified against the actual
  // route rather than guessed: `was` is the balance BEFORE the repair, `ledger` is the recomputed
  // truth it was replaced with (or left at, if they already agreed), `repaired` says whether
  // anything was actually wrong. An earlier pass here read `before`/`after`, fields this route has
  // never returned — the result silently showed "—" for both on every real call. Caught before
  // shipping any further.
  const [result, setResult] = useState<
    { subject_ref: string; ledger: number; was: number; drift: number; repaired: boolean } | null
  >(null);

  const balanceAction = findCustomerAction(catalog, 'loyalty.platform_balance');
  const historyAction = findCustomerAction(catalog, 'loyalty.platform_history');
  const reconcileAction = findCustomerAction(catalog, 'loyalty.platform_reconcile');
  const ready = subjectRef.trim().length >= 8 && reason.trim().length >= 3;

  const search = () => {
    if (!subjectRef.trim()) return;
    const ref = subjectRef.trim();
    setAsked(ref); setResult(null); setErr('');
    if (balanceAction) {
      setBalance('loading');
      req<{ points: number }>(
        `${balanceAction.path}?tenant=${encodeURIComponent(tenant.id)}&subject_ref=${encodeURIComponent(ref)}`,
        'GET', undefined, session.access_token)
        .then(setBalance).catch(() => setBalance('failed'));
    }
    if (historyAction) {
      req<{ entries: LoyaltyEntryRow[] }>(
        `${historyAction.path}?tenant=${encodeURIComponent(tenant.id)}&subject_ref=${encodeURIComponent(ref)}&limit=25`,
        'GET', undefined, session.access_token)
        .then((r) => setEntries(r.entries ?? [])).catch(() => setEntries([]));
    }
  };

  const reconcile = async () => {
    if (!reconcileAction || !ready) return;
    setBusy(true); setErr(''); setResult(null);
    try {
      const out = await req<
        { subject_ref: string; ledger: number; was: number; drift: number; repaired: boolean }
      >(reconcileAction.path, 'POST',
        { tenant: tenant.id, subject_ref: subjectRef.trim(), reason: reason.trim() },
        session.access_token);
      setResult(out);
      setArm(false);
      if (asked === subjectRef.trim()) search();
    } catch (e) {
      setErr(errMsg(e));
    } finally {
      setBusy(false);
    }
  };

  const columns: TableColumn<LoyaltyEntryRow>[] = [
    { key: 'reason', header: 'الحركة', render: (e) => LOYALTY_REASON_LABEL[e.reason] ?? e.reason },
    { key: 'delta', header: 'التغيير', render: (e) => (
      <span dir="ltr" className={e.delta >= 0 ? 'text-success font-mono' : 'text-danger font-mono'}>
        {e.delta >= 0 ? `+${e.delta}` : e.delta}
      </span>
    ) },
    { key: 'balance_after', header: 'الرصيد بعدها', hideOnCard: true, render: (e) => <span dir="ltr" className="font-mono">{e.balance_after}</span> },
    { key: 'note', header: 'ملاحظة', render: (e) => e.note || '—' },
    { key: 'created_at', header: 'الوقت', render: (e) => unixDate(e.created_at) },
  ];

  if (!balanceAction && !historyAction && !reconcileAction) {
    return (
      <div className="flex flex-col gap-3">
        <SectionHeader icon={<RefreshCw size={18} />} title="نقاط الولاء" />
        <p className="text-sm text-text-secondary">لا صلاحية.</p>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-3">
      <SectionHeader icon={<RefreshCw size={18} />} title="نقاط الولاء" />
      <div className="flex flex-wrap items-center gap-2">
        <Input value={subjectRef} onChange={(e) => setSubjectRef(e.target.value)}
              placeholder="مرجع العميل (subject_ref)" className="w-48" aria-label="مرجع العميل" />
        {balanceAction || historyAction ? (
          <Button size="sm" variant="outline" disabled={!subjectRef.trim()} onClick={search}>ابحث</Button>
        ) : null}
      </div>
      {asked ? (
        <>
          {balance === 'loading' ? <p className="text-sm text-text-secondary">جارٍ التحميل…</p> : null}
          {balance === 'failed' ? <p role="alert" className="text-danger text-sm">تعذّرت قراءة الرصيد.</p> : null}
          {balance && balance !== 'loading' && balance !== 'failed' ? (
            <KpiCard icon={<RefreshCw size={18} />} label="الرصيد الحالي" value={balance.points} tone="accent" />
          ) : null}
          {historyAction ? (
            <Table columns={columns} rows={entries} getRowId={(e) => e.id}
                  emptyTitle="لا حركات نقاط لهذا العميل" failedTitle="تعذّرت قراءة السجل" />
          ) : null}
        </>
      ) : null}
      {reconcileAction ? (
        <div className="flex flex-wrap items-end gap-2 border-t border-border-subtle pt-3">
          <Input value={reason} onChange={(e) => setReason(e.target.value)}
                placeholder="سبب الإصلاح" className="w-48" aria-label="السبب" />
          <Button size="sm" disabled={!ready} onClick={() => setArm(true)}>أصلح الرصيد</Button>
        </div>
      ) : null}
      {err ? <p role="alert" className="text-danger text-sm">{err}</p> : null}
      {result ? (
        <p className="text-sm text-text-secondary">
          {result.repaired ? (
            <>
              كان <span dir="ltr" className="font-mono">{result.was}</span>، وصار{' '}
              <span dir="ltr" className="font-mono">{result.ledger}</span> — الفرق كان{' '}
              <span dir="ltr" className="font-mono">{result.drift}</span> نقطة.
            </>
          ) : (
            <>الرصيد كان صحيحًا أصلاً (<span dir="ltr" className="font-mono">{result.ledger}</span>) — لا فرق يُصلَح.</>
          )}
        </p>
      ) : null}
      <ConfirmDialog open={arm} onClose={() => setArm(false)} onConfirm={() => void reconcile()}
                    title="إصلاح الرصيد" danger busy={busy}
                    body="سيُعاد حساب الرصيد من سجل الحركات الفعلي ويُستبدَل الرقم الحالي به.">
      </ConfirmDialog>
    </div>
  );
}

interface EvidenceSection { status: string; records: unknown[]; count: number; reason?: string; }
interface EvidenceFile {
  tenant: string; since: number; until: number; generated_at: number; requested_by: string;
  sections: Record<string, EvidenceSection>;
}

const EVIDENCE_SECTION_LABEL: Record<string, string> = {
  privacy_requests: 'طلبات الخصوصية', consent: 'الموافقة',
  messages: 'الرسائل', agreements: 'الموافقات القانونية',
};

/** ملف الأدلة — كل ما تحتفظ به المنصة عن هذا المحل بفترة معيّنة، لدعم شكوى. */
function EvidenceFileSection({ session, tenant, catalog }: {
  session: AdminSession; tenant: Tenant; catalog: AdminCatalog;
}) {
  const [since, setSince] = useState('');
  const [until, setUntil] = useState('');
  const [arm, setArm] = useState(false);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState('');
  const [file, setFile] = useState<EvidenceFile | null>(null);

  const action = findCustomerAction(catalog, 'operations.evidence_file');

  const toUnix = (d: string): number => (d ? Math.floor(new Date(d).getTime() / 1000) : 0);

  const build = async () => {
    if (!action) return;
    setBusy(true); setErr('');
    try {
      const out = await req<EvidenceFile>(
        action.path, 'POST',
        { tenant: tenant.id, since: toUnix(since), until: toUnix(until) },
        session.access_token);
      setFile(out);
      setArm(false);
    } catch (e) {
      setErr(errMsg(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="flex flex-col gap-3">
      <SectionHeader icon={<History size={18} />} title="ملف الأدلة" />
      {!action ? <p className="text-sm text-text-secondary">لا صلاحية.</p> : (
        <>
          <div className="flex flex-wrap items-end gap-2">
            <label className="flex flex-col gap-1 text-label text-text-secondary">
              من
              <Input type="date" value={since} onChange={(e) => setSince(e.target.value)} className="w-36" />
            </label>
            <label className="flex flex-col gap-1 text-label text-text-secondary">
              إلى
              <Input type="date" value={until} onChange={(e) => setUntil(e.target.value)} className="w-36" />
            </label>
            <Button size="sm" onClick={() => setArm(true)}>أنشئ ملف الأدلة</Button>
          </div>
          {err ? <p role="alert" className="text-danger text-sm">{err}</p> : null}
          {file ? (
            <div className="flex flex-col gap-3">
              <p className="text-label text-text-muted">
                أُنشئ بواسطة <span dir="ltr">{file.requested_by}</span> — {unixDate(file.generated_at)}
              </p>
              {Object.entries(file.sections).map(([key, section]) => (
                <div key={key} className="rounded-card border border-border-subtle bg-surface-1 p-3">
                  <div className="mb-2 flex items-center justify-between gap-2">
                    <h4 className="text-sm font-medium">{EVIDENCE_SECTION_LABEL[key] ?? key}</h4>
                    <Badge tone={section.status === 'read' ? 'success' : 'neutral'}>
                      {section.status === 'read' ? `${section.count} سجل` : (section.reason ?? 'غير متاح')}
                    </Badge>
                  </div>
                  {section.records.length > 0 ? (
                    <pre className="max-h-64 overflow-auto whitespace-pre-wrap font-mono text-xs text-text-secondary">
                      {JSON.stringify(section.records, null, 2)}
                    </pre>
                  ) : null}
                </div>
              ))}
            </div>
          ) : null}
        </>
      )}
      <ConfirmDialog open={arm} onClose={() => setArm(false)} onConfirm={() => void build()}
                    title="إنشاء ملف الأدلة" danger={false} busy={busy}
                    body="سيُسجَّل الاطّلاع هذا باسمك — استخدمه لدعم شكوى فعلي فقط.">
      </ConfirmDialog>
    </div>
  );
}
