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
import { Segmented } from '../rj-ui/Segmented';
import { fetchCatalog, type AdminAction, type AdminCatalog } from './catalog';
import type { AdminSession } from './api';
import { NoActionAvailable } from './NoActionAvailable';
import { ActionListGroup } from './ActionRenderer';
import { CustomerByPhoneLookup, type FoundCustomer } from './CustomerByPhoneLookup';

// العميل الموجود يُصفّي التبويبات الستة أدناه تلقائياً (`onFound`) بمنشأته — الخلل اللي كان
// يمنع هذا (compliance-service عمياء عن أي محل حقيقي) انحل بمعزل عن هذا الملف (platform v0.19.7)،
// فما احتجنا نغيّر شيء هنا غير تمرير النتيجة لأعلى. التصفية بالمنشأة فقط، لا بالعميل نفسه: DSAR
// وحظر الحذف لا يقبلان تصفية "بعميل واحد" أصلاً بالخادم اليوم — القائمة تضيق للمحل الصحيح، والعين
// تُكمل. سجل الموافقات وحده يقبل `subject` أيضاً (رقم الجوال مباشرة)، فيُصفّى للعميل بالضبط.
const FOUND_NOTE = 'التبويبات أدناه مصفّاة الآن على منشأته — الموافقات مصفّاة عليه هو بالذات.';

type TabId = 'legal_hold' | 'dsar' | 'consent' | 'data_targets' | 'ropa' | 'breach';

/** TABS THAT SCOPE BY `tenant` — compliance-service v0.19.29 fixed the real gap this session
 *  found (owner's own report: a DSAR that genuinely arrived read back as "لا نتائج" with nothing
 *  explaining why): a platform.compliance caller with NO `tenant` param now gets every tenant's
 *  still-OPEN/ACTIVE rows (`scope: "all_open"`/`"all_active"` on the response), not a silent read
 *  of the operator's own meaningless `_platform` tenant. Searching a customer still narrows to
 *  ONE shop — that behaviour is unchanged, just no longer required to see anything at all. Named
 *  here once so the note below and any future reader agree on exactly which tabs this applies to. */
const TENANT_SCOPED_TABS = new Set<TabId>(['legal_hold', 'dsar']);

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
  // العميل الموجود عبر البحث بالجوال — يُصفّي التبويبات الستة أدناه. `null` يعني «لا فلتر»، لا
  // «ابحث الآن»: تبويبات الامتثال تبقى شغّالة عادي قبل أي بحث، على منشأة المشغّل نفسها كسابقاً.
  const [foundCustomer, setFoundCustomer] = useState<FoundCustomer | null>(null);

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
        {lookupAction ? (
          <CustomerByPhoneLookup session={session} action={lookupAction} onFound={setFoundCustomer} foundNote={FOUND_NOTE} />
        ) : null}
        <NoActionAvailable catalog={catalog} permissionTitle="لا صلاحية لديك لأي قسم من الامتثال." />
      </div>
    );
  }
  const realActive = visibleTabs.some((t) => t.id === tab) ? tab : visibleTabs[0].id;
  const active = TABS.find((t) => t.id === realActive)!;
  const ids = ACTION_IDS[realActive];
  const listAction = byId.get(ids.list);
  const rowActions = ids.row.map((id) => byId.get(id)).filter((a): a is AdminAction => Boolean(a));
  // منشأة العميل الموجود تُمرَّر لكل تبويب — DSAR وحظر الحذف يقبلان `tenant` فقط، والموافقات
  // تقبل `subject` أيضاً فتُصفّى للعميل بالضبط لا لكل عملاء منشأته.
  const extraQuery: Record<string, string> | undefined = foundCustomer
    ? { tenant: foundCustomer.tenant, ...(realActive === 'consent' ? { subject: foundCustomer.phone } : {}) }
    : undefined;

  return (
    <div className="flex flex-col gap-4 p-6">
      <h1 className="text-2xl leading-tight tracking-tight">الامتثال</h1>

      {lookupAction ? (
        <CustomerByPhoneLookup session={session} action={lookupAction} onFound={setFoundCustomer} foundNote={FOUND_NOTE} />
      ) : null}

      <Segmented
        className="grid w-full grid-cols-2 gap-1 sm:grid-cols-3 sm:flex sm:flex-wrap [&>button]:truncate"
        ariaLabel="أقسام الامتثال"
        value={realActive}
        onChange={(v) => setTab(v as TabId)}
        options={visibleTabs.map((t) => ({ value: t.id, label: t.label }))}
      />
      <p className="text-sm text-text-secondary">{active.hint}</p>

      {/* NEUTRAL, NOT A WARNING — compliance-service v0.19.29 fixed the actual gap (see
          TENANT_SCOPED_TABS's own note): the list below already shows everything, this just says
          so and names the narrowing search as optional. Shown ONLY on the two tabs that scope this
          way, and only before a search narrows them to one shop. */}
      {TENANT_SCOPED_TABS.has(realActive) && !foundCustomer ? (
        <p className="rounded-card bg-surface-2 px-3 py-2 text-sm text-text-secondary">
          القائمة أدناه تعرض كل الطلبات المفتوحة من كل المحلات، الأقدم أولاً — ابحث عن عميل برقم
          جواله أعلاه لو تبي تضيّقها لمحل واحد بعينه.
        </p>
      ) : null}

      {listAction ? (
        <ActionListGroup session={session} listAction={listAction} rowActions={rowActions}
                         extraQuery={extraQuery} />
      ) : (
        <NoActionAvailable catalog={catalog} permissionTitle={`لا صلاحية لديك لقراءة «${active.label}».`} />
      )}
    </div>
  );
}
