/**
 * الامتثال — ستة أقسام كانت مُعلَنة بالكامل في الخلفية (20 فعلًا إداريًا) ولا شاشة واحدة تستخدمها.
 * أهمها عمليًا اليوم: حظر الحذف (Legal hold) — الآلية الفعلية وراء ميزة "منع حذف حساب لأسباب
 * قانونية"، وطلبات الحذف/الاطلاع (DSAR) نفسها.
 *
 * تبويبات صريحة لكل مجموعة، لا المحرّك العام تلقائيًا: مجموعة "Data map" تحمل قائمتين حقيقيتين
 * (جهات البيانات وسجل المعالجة RoPA)، والمحرّك العام يلتقط أول قائمة فقط لكل مجموعة — فيبتلع
 * إحداهما. هنا كل تبويب يُمرَّر قائمته وأفعال صفّه بالاسم مباشرة، فلا تصادم.
 */
import { useEffect, useState } from 'react';
import { Search, User, XCircle } from 'lucide-react';
import { Segmented } from '../rj-ui/Segmented';
import { Button } from '../rj-ui/Button';
import { Field, Input } from '../rj-ui/Field';
import { fetchCatalog, type AdminAction, type AdminCatalog } from './catalog';
import { req, type AdminSession } from './api';
import { NoActionAvailable } from './NoActionAvailable';
import { ActionListGroup } from './ActionRenderer';

interface FoundCustomer {
  id: string; tenant: string; phone: string; name: string;
  visit_count: number; last_visit: number;
}

/**
 * بحث سريع عن عميل بمنشأة معروفة + رقم جواله — الباب اللي طلبه تمام بدل انتظار المرحلة أ
 * كاملة: موظف الدعم يعرف المحل الذي يخدمه العميل (لا بحث عبر كل المنشآت دفعة واحدة — مطابقة
 * تامة فقط، لا تخمين تقريبي)، فيكتب الاثنين ويحصل على ملفّه مباشرة.
 *
 * سجل الامتثال الفعلي لهذا العميل (DSAR/الموافقات/حظر الحذف) غير مربوط هنا بعد — الشاشة أدناه
 * لا تزال عامة على مستوى المنصة كلها بسبب خلل حقيقي بخدمة الامتثال (رُفع لفريق base-services)،
 * فربط البطاقة بسجله الفعلي ينتظر ذلك الإصلاح. هذي الخطوة تكتفي بإيجاد العميل نفسه.
 */
function CustomerLookup({ session, action }: { session: AdminSession; action: AdminAction }) {
  const [tenant, setTenant] = useState('');
  const [phone, setPhone] = useState('');
  const [state, setState] = useState<'idle' | 'loading' | 'found' | 'missed' | 'failed'>('idle');
  const [result, setResult] = useState<FoundCustomer | null>(null);

  const search = async () => {
    if (!tenant.trim() || !phone.trim()) return;
    setState('loading'); setResult(null);
    try {
      const q = `?tenant=${encodeURIComponent(tenant.trim())}&phone=${encodeURIComponent(phone.trim())}`;
      const r = await req<{ customer: FoundCustomer | null }>(
        `${action.path}${q}`, 'GET', undefined, session.access_token);
      if (r.customer) { setResult(r.customer); setState('found'); } else { setState('missed'); }
    } catch {
      setState('failed');
    }
  };

  return (
    <section className="flex flex-col gap-3 rounded-card border border-border-subtle bg-surface-1 p-4">
      <h2 className="font-medium">ابحث عن عميل</h2>
      <div className="flex flex-col gap-3 sm:flex-row sm:items-end">
        <Field label="المنشأة (tenant)" className="flex-1">
          <Input value={tenant} onChange={(e) => setTenant(e.target.value)}
                placeholder="tnt_..." dir="ltr" />
        </Field>
        <Field label="رقم الجوال" className="flex-1">
          <Input value={phone} onChange={(e) => setPhone(e.target.value)}
                placeholder="05xxxxxxxx" dir="ltr"
                onKeyDown={(e) => { if (e.key === 'Enter') search(); }} />
        </Field>
        <Button onClick={search} disabled={state === 'loading' || !tenant.trim() || !phone.trim()}>
          <Search size={16} /> بحث
        </Button>
      </div>

      {state === 'failed' ? (
        <p role="alert" className="text-sm text-danger">تعذّر البحث. حاول مرة أخرى.</p>
      ) : null}
      {state === 'missed' ? (
        <p className="flex items-center gap-2 text-sm text-text-secondary">
          <XCircle size={16} className="shrink-0" /> لا عميل بهذا الرقم في هذه المنشأة.
        </p>
      ) : null}
      {state === 'found' && result ? (
        <div className="flex items-center gap-3 rounded-card bg-accent-soft p-3">
          <User size={20} className="shrink-0 text-accent-on-soft" />
          <div className="flex flex-col text-sm">
            <span className="font-medium">{result.name || 'بلا اسم مسجَّل'}</span>
            <span dir="ltr" className="text-text-secondary">{result.phone}</span>
            <span className="text-label text-text-secondary">
              {result.visit_count} زيارة — آخر زيارة{' '}
              {result.last_visit ? new Date(result.last_visit * 1000).toLocaleDateString('ar-SA-u-nu-latn') : '—'}
            </span>
          </div>
        </div>
      ) : null}
    </section>
  );
}

type TabId = 'legal_hold' | 'dsar' | 'consent' | 'data_targets' | 'ropa' | 'breach';

const TABS: { id: TabId; label: string; hint: string }[] = [
  { id: 'legal_hold', label: 'حظر الحذف',
    hint: 'حسابات يُمنع تنفيذ طلب حذفها الآن — لأسباب قانونية أو نزاع قائم' },
  { id: 'dsar', label: 'طلبات الحذف والاطّلاع',
    hint: 'كل طلب DSAR فتحه عميل: الاطّلاع، التصدير، التصحيح، أو الحذف' },
  { id: 'consent', label: 'الموافقات', hint: 'سجل موافقات العملاء وسحبها' },
  { id: 'data_targets', label: 'جهات البيانات',
    hint: 'الخدمات المسجَّلة كوجهة لطلبات الحذف والاطّلاع' },
  { id: 'ropa', label: 'سجل أنشطة المعالجة', hint: 'سجل RoPA النظامي' },
  { id: 'breach', label: 'الاختراقات', hint: 'تسجيل حادثة اختراق وإشعارها' },
];

const ACTION_IDS: Record<TabId, { list: string; row: string[] }> = {
  legal_hold: { list: 'compliance.list_legal_holds',
    row: ['compliance.place_legal_hold', 'compliance.release_legal_hold'] },
  dsar: { list: 'compliance.list_dsar',
    row: ['compliance.open_dsar', 'compliance.verify_dsar', 'compliance.process_dsar'] },
  consent: { list: 'compliance.consent_history',
    row: ['compliance.grant_consent', 'compliance.withdraw_consent'] },
  data_targets: { list: 'compliance.list_data_targets',
    row: ['compliance.register_data_target', 'compliance.delete_data_target'] },
  ropa: { list: 'compliance.list_ropa', row: ['compliance.create_ropa', 'compliance.delete_ropa'] },
  breach: { list: 'compliance.list_breaches',
    row: ['compliance.register_breach', 'compliance.notify_breach'] },
};

export function AdminCompliance({ session }: { session: AdminSession }) {
  const [catalog, setCatalog] = useState<AdminCatalog | 'loading' | 'failed'>('loading');
  const [tab, setTab] = useState<TabId>('legal_hold');

  useEffect(() => {
    let cancelled = false;
    fetchCatalog(session).then((c) => { if (!cancelled) setCatalog(c); })
      .catch(() => { if (!cancelled) setCatalog('failed'); });
    return () => { cancelled = true; };
  }, [session]);

  if (catalog === 'loading') return <p className="p-6 text-sm text-text-secondary">جارٍ التحميل…</p>;
  if (catalog === 'failed') return <p role="alert" className="p-6 text-danger">تعذّرت قراءة كتالوج الإدارة.</p>;

  const actions = catalog.services.flatMap((s) => s.actions);
  const byId = new Map(actions.map((a) => [a.id, a]));
  // فعل مستقل عن التبويبات الستة أدناه (صلاحيته platform.operations لا platform.compliance) —
  // يُحسب هنا قبل أي رفض بسبب التبويبات، فلا يحرم موظفاً يملك واحدة دون الأخرى من البحث.
  const lookupAction = byId.get('operations.customer_by_phone');

  // تبويب لا يملك المستخدم صلاحية قراءته إطلاقًا لا يُعرض — بدل تبويب فارغ يفتح على رفض دائم.
  const visibleTabs = TABS.filter((t) => byId.has(ACTION_IDS[t.id].list));
  if (visibleTabs.length === 0) {
    return (
      <div className="flex flex-col gap-4 p-6">
        <h1 className="text-2xl leading-tight tracking-tight">الامتثال</h1>
        {lookupAction ? <CustomerLookup session={session} action={lookupAction} /> : null}
        <NoActionAvailable catalog={catalog} permissionTitle="لا صلاحية لديك لأي قسم من الامتثال." />
      </div>
    );
  }
  const realActive = visibleTabs.some((t) => t.id === tab) ? tab : visibleTabs[0].id;
  const active = TABS.find((t) => t.id === realActive)!;
  const ids = ACTION_IDS[realActive];
  const listAction = byId.get(ids.list);
  const rowActions = ids.row.map((id) => byId.get(id)).filter((a): a is AdminAction => Boolean(a));

  return (
    <div className="flex flex-col gap-4 p-6">
      <h1 className="text-2xl leading-tight tracking-tight">الامتثال</h1>

      {lookupAction ? <CustomerLookup session={session} action={lookupAction} /> : null}

      <Segmented
        className="grid w-full grid-cols-2 gap-1 sm:grid-cols-3 sm:flex sm:flex-wrap [&>button]:truncate"
        ariaLabel="أقسام الامتثال"
        value={realActive}
        onChange={(v) => setTab(v as TabId)}
        options={visibleTabs.map((t) => ({ value: t.id, label: t.label }))}
      />
      <p className="text-sm text-text-secondary">{active.hint}</p>

      {listAction ? (
        <ActionListGroup session={session} listAction={listAction} rowActions={rowActions} />
      ) : (
        <NoActionAvailable catalog={catalog} permissionTitle={`لا صلاحية لديك لقراءة «${active.label}».`} />
      )}
    </div>
  );
}
