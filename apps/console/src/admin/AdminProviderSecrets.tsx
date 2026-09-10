/**
 * مفاتيح المزوّدين الخارجيين — secrets-admin's own screen. NOT `AdminSecrets.tsx` (that one is
 * every OURS service's own `platform.secrets` operator/secrets route — a shop's payment key, a
 * delivery driver's token). This is a DIFFERENT, unrelated capability
 * (`platform.secrets_manage`): rewriting the credential Meta/the AI backend/etc. secrets that are sealed
 * into OTHER services' own K8s Secret objects — see services/secrets-admin/app/admin_actions.py's
 * own header for why there is, and will never be, a third action of the obvious kind.
 *
 * WRITE-ONLY, STRUCTURALLY, NOT BY DISCIPLINE. `secrets.list`'s own response cannot carry a value
 * — the backend route never even reads `data`, only annotations (see that service's own
 * api/v1/secrets.py). This component holds no state that could ever contain one either: `newValue`
 * is cleared the instant a save resolves, success or failure, and there is no "show" affordance
 * anywhere below — not behind a second click, not behind a second capability. A future edit that
 * wants to add one should read the backend module's own docstring first.
 *
 * ONE DELIBERATE EXCEPTION: GENERATABLE keys (below) are values WE invent, not ones a provider
 * hands us — nothing is ever "read back" because nothing was ever stored yet. Generating one
 * reveals it in plain text for exactly as long as it takes to copy it into Meta's own webhook
 * config, the one other place it has to match — this is showing a brand-new local value, not
 * the write-only guarantee above, which is about a value already saved.
 */
import { useEffect, useState, type ReactNode } from 'react';
import {
  AlertTriangle, CheckCircle2, ChevronLeft, CircleHelp, Clock, Copy, CreditCard, Loader2,
  MessageCircle, PhoneOff, Send, Sparkles, UserX, XCircle,
} from 'lucide-react';
import { Button } from '../rj-ui/Button';
import { Field, Input, Select } from '../rj-ui/Field';
import { Badge } from '../rj-ui/Badge';
import { KpiCard } from '../rj-ui/KpiCard';
import { Segmented } from '../rj-ui/Segmented';
import { TabBar } from '../rj-ui/TabBar';
import { Modal } from '../rj-ui/Modal';
import { BlockView, type Block } from '@base-ui/components/BlockRenderer';
import { fetchCatalog, type AdminAction, type AdminCatalog } from './catalog';
import { req, type AdminSession } from './api';
import { sentenceFor } from '../api';
import { NoActionAvailable } from './NoActionAvailable';

interface SecretRow {
  key: string;
  label: string;
  configured: boolean | null;
  last4: string | null;
  updated_at: string | null;
  updated_by: string | null;
  unreadable?: boolean;
}

// WHAT EACH KEY IS AND WHERE IT COMES FROM — matches services/secrets-admin/app/core/
// secret_registry.py's own SECRETS tuple exactly; that file is the real source of truth for
// WHICH keys exist, this is only the console's own explanatory text for them, since the backend
// route never sends more than {key, label, ...}. An unknown key (a new one added there but not
// here) still shows fine — just without the "؟" hint, never hidden.
const SECRET_HELP: Record<string, string> = {
  META_APP_ID: 'من لوحة مطوّري Meta (developers.facebook.com) — تطبيقك ← إعدادات أساسية ← "معرّف التطبيق".',
  META_APP_SECRET: 'من نفس صفحة إعدادات التطبيق بلوحة مطوّري Meta — "سر التطبيق" (يحتاج تأكيد كلمة مرور حسابك لإظهاره).',
  // ليست سرّية فعلياً (تُرسَل من المتصفح بالوضوح بكل نافذة Embedded Signup) — تمر من هنا فقط
  // عشان الإعداد كله يصير من مكان واحد بلا إعادة نشر للكونسول.
  META_APP_CONFIG_ID: 'من لوحة مطوّري Meta — تطبيقك ← "Facebook Login for Business" ← إعداد التسجيل المُنشأ لعملية Embedded Signup الخاصة بواتساب — "Configuration ID".',
  WHATSAPP_WEBHOOK_VERIFY_TOKEN: 'نص تختاره أنت بنفسك (أي نص عشوائي قوي) وتُدخِله هنا وبنفس الوقت بإعدادات الـwebhook بلوحة Meta — يجب أن يتطابق النصّان بالضبط.',
  // هوية واتساب المنصة نفسها (لا محل معيّن) — إرسالات النظام زي رمز التحقق (OTP) عند التسجيل.
  // خطوات ميتا: Business Manager ← Users ← System users ← أنشئ واحداً بصلاحية Admin ← فعّل صلاحية
  // whatsapp_business_messaging (وwhatsapp_business_management لو بنسجّل قوالب) ← ولّد توكن دائم.
  WHATSAPP_ACCESS_TOKEN: 'توكن دائم (Permanent) من System User بلوحة Meta Business Manager — Users ← System users ← أنشئ مستخدماً بصلاحية Admin وفعّل له صلاحية whatsapp_business_messaging، ثم ولّد توكناً. يُنسخ مرة واحدة فقط عند إنشائه.',
  WHATSAPP_PHONE_NUMBER_ID: 'من لوحة WhatsApp Manager بنفس حساب الأعمال — رقم هاتف المنصة نفسه (لا رقم محل) ← "معرّف رقم الهاتف" (Phone Number ID)، رقم وليس رقم الجوال نفسه.',
  WHATSAPP_BUSINESS_ACCOUNT_ID: 'من نفس WhatsApp Manager — معرّف حساب واتساب الأعمال (WABA ID) نفسه، يظهر أعلى لوحة الحساب. يلزم فقط لتسجيل القوالب، لا للإرسال نفسه.',
  // البوت يتصل بالذكاء الاصطناعي عبر Vertex AI (Google Cloud)، لا Google AI Studio مباشرة —
  // يحتاج مشروع Google Cloud حقيقي (لا يوجد بعد) ومفتاح خدمة (Service Account) عليه.
  // القيمتان تخصّان مشروع Google Cloud اللي بوت واتساب المحلات (لا خدمة عملاء المنصة) يتصل به
  // ليفكّر ويرد — لازم مشروع حقيقي جاهز أول، لا تُكتبان قبله.
  ASSISTANT_MODEL_PROJECT: 'اسم مشروعنا داخل Google Cloud. تلقاه أول ما تفتح console.cloud.google.com — مكتوب أعلى الصفحة تحت "Project ID" بالضبط (ليس اسم المشروع العادي، الرقم/الرمز المميز الظاهر تحته).',
  ASSISTANT_MODEL_CREDENTIAL: 'ملف صغير يُثبت لجوجل إن الطلب فعلاً من مشروعنا. بنفس الموقع: اكتب "Service Accounts" بالبحث الأعلى ← أنشئ واحداً جديداً ← افتحه ← تبويب "Keys" ← "Add Key" ← "JSON". بينزل ملف — افتحه بأي محرر نصوص، انسخ كل محتواه من أول { لآخر }، والصقه هنا كاملاً.',
  // خانة عامة يعيد استخدامها كل مزوّد دفع (Moyasar/Tap/HyperPay/PayTabs/Geidea/APS/TuwaiqPay) —
  // بلا اسم مزوّد مكتوب هنا بالكود عمداً، لأن أي مزوّد نشط اليوم قد لا يكون النشط غداً: أي مزوّد
  // بوابة الدفع المفعّل حالياً بإعدادات النشر (PAYMENT_GATEWAY_DRIVER) — راجع بيانات حسابك عنده.
  PAYMENT_API_KEY: 'اسم المستخدم لحساب التاجر لدى مزوّد بوابة الدفع المفعّل حالياً بإعدادات النشر.',
  // ثالث خانة عامة، وُجدت ناقصة 2026-09-07 — بعض المزوّدين يحتاجونها وبعضهم لا، حسب أي واحد مفعّل:
  // معرّف حساب التاجر عند HyperPay (entityId)/PayTabs (profile_id)/APS (merchant_identifier)، أو
  // معرّف ثانٍ عند PayPal/Stripe (client_secret). راجع لوحة تحكّم المزوّد المفعّل حالياً لتعرف
  // بالضبط أي حقل هو عندهم — الاسم يختلف من مزوّد لآخر رغم إنه نفس الخانة هنا.
  PAYMENT_EXTRA_ID: 'معرّف إضافي لحساب التاجر لدى مزوّد بوابة الدفع المفعّل حالياً (اسمه يختلف حسب المزوّد — راجع لوحة تحكّمه).',
  PAYMENT_EXTRA_SECRET: 'كلمة مرور نفس حساب التاجر لدى مزوّد بوابة الدفع المفعّل حالياً.',
  // يظهر لمتصفح العميل مباشرة (شاشة الاشتراك) — ليس سرّاً بنفس معنى الاثنين أعلاه، لكنه بلا مكان
  // آمن يُكتب فيه غير هنا حتى الآن.
  PAYMENT_PUBLISHABLE_KEY: 'المفتاح العام (Publishable) لنفس حساب التاجر — من لوحة تحكّم مزوّد بوابة الدفع المفعّل حالياً، وليس سرّياً بذاته لكنه ما زال يحتاج مكاناً واحداً موثوقاً يُكتب فيه.',
};

// مفاتيح نخترعها نحن، لا يصدرها مزوّد خارجي — زر "توليد" يبني قيمة عشوائية قوية بدل ما يُكتب
// يدوياً (عرضة للأخطاء وضعف العشوائية). كل مفتاح هنا يُدخَل بنفس القيمة بمكان ثانٍ خارج هذا
// النظام (هنا: إعداد الـwebhook بلوحة Meta) — القيمة تُعرض فور توليدها لأنها لم تُحفظ بعد أصلاً.
const GENERATABLE = new Set(['WHATSAPP_WEBHOOK_VERIFY_TOKEN']);

/** توكن عشوائي قوي بترميز base64url (32 بايت ~ 43 حرفاً) عبر Web Crypto — لا Math.random(). */
function generateToken(): string {
  const bytes = crypto.getRandomValues(new Uint8Array(32));
  let binary = '';
  for (const b of bytes) binary += String.fromCharCode(b);
  return btoa(binary).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
}

// أي مفتاح يخص أي مزوّد — بطاقة واحدة لكل مزوّد، لا صف طويل لكل مفتاح على حدة. مفتاح غير معروف
// (مزوّد سادس أُضيف بـsecret_registry.py ولم يُضف هنا) يقع في بطاقة "أخرى" العامة، لا يُفقد أبداً.
const PROVIDER_OF: Record<string, string> = {
  META_APP_ID: 'meta', META_APP_SECRET: 'meta', META_APP_CONFIG_ID: 'meta',
  WHATSAPP_WEBHOOK_VERIFY_TOKEN: 'meta',
  WHATSAPP_ACCESS_TOKEN: 'meta', WHATSAPP_PHONE_NUMBER_ID: 'meta', WHATSAPP_BUSINESS_ACCOUNT_ID: 'meta',
  ASSISTANT_MODEL_PROJECT: 'assistant_ai', ASSISTANT_MODEL_CREDENTIAL: 'assistant_ai',
  PAYMENT_API_KEY: 'payment', PAYMENT_EXTRA_ID: 'payment', PAYMENT_EXTRA_SECRET: 'payment',
  PAYMENT_PUBLISHABLE_KEY: 'payment',
};
const PROVIDER_META: Record<string, { label: string; icon: typeof MessageCircle }> = {
  // الاسم التقني الدقيق كما هو — هذي لوحة إدارة داخلية (لفريق المنصة)، لا شاشة يقرأها صاحب محل،
  // فلا حاجة لتلطيف الاسم أو تبسيطه (قرار يلغي التسمية الأطول السابقة).
  meta: { label: 'Meta', icon: MessageCircle },
  // "الذكاء الاصطناعي" عام عمداً الآن — بس فيه فئة واحدة اليوم فقط. لو انضاف ذكاء اصطناعي ثانٍ
  // لغرض مختلف مستقبلاً (خدمة عملاء المنصة مثلاً)، هذا الاسم يحتاج توضيحاً وقتها (مثلاً "ذكاء
  // واتساب المحلات" مقابل الاسم الثاني) — ليس اليوم، وفيه فئة واحدة بس.
  assistant_ai: { label: 'الذكاء الاصطناعي', icon: Sparkles },
  payment: { label: 'بوابة الدفع', icon: CreditCard },
  other: { label: 'أخرى', icon: CircleHelp },
};

export function AdminProviderSecrets({ session, initialOpenProvider }: {
  session: AdminSession;
  /** رابط تحويل مباشر من شاشة ثانية (مثل "بوابات الدفع" بالمالية) — يفتح فئة هذا المزوّد فور
   *  الوصول، بدل ما يوصل الشخص الفئة الافتراضية (أول واحدة) ويبحث بنفسه. */
  initialOpenProvider?: string;
}) {
  const [catalog, setCatalog] = useState<AdminCatalog | 'loading' | 'failed'>('loading');
  const [rows, setRows] = useState<SecretRow[] | 'loading' | 'failed'>('loading');
  // فئة واحدة معروضة كحد أقصى، بتبويبات مثل بقية الشاشات (المالية...) — لا قائمة قابلة للطي، كل
  // مزوّد عالمه الكامل (إعداداته وأسراره معاً) بمكان واحد بلا تنقّل بين شاشتين. `null` يعني
  // "أول فئة موجودة فعلياً بالاستجابة" — يُحسم أول ما تصل الصفوف (انظر أدناه)، لا فئة مجمّدة
  // بالكود قد لا تكون موجودة أصلاً لهذا الحساب.
  const [openProvider, setOpenProvider] = useState<string | null>(initialOpenProvider ?? null);

  useEffect(() => {
    let cancelled = false;
    fetchCatalog(session).then((c) => { if (!cancelled) setCatalog(c); })
      .catch(() => { if (!cancelled) setCatalog('failed'); });
    return () => { cancelled = true; };
  }, [session]);

  const allActions = catalog !== 'loading' && catalog !== 'failed'
    ? catalog.services.flatMap((s) => s.actions) : [];
  const findAction = (id: string) => allActions.find((a) => a.id === id);
  const listAction = findAction('secrets.list');
  const updateAction = findAction('secrets.update');
  // "الحالة" — رؤية تشغيلية حقيقية لواتساب المنصة نفسها (Raje3 Meta-panel Phase 1): لا اتصال
  // جديد بميتا، فقط بيانات نملكها فعلاً (ConnectionStore بoperations، وDeliveryStore/
  // WhatsAppNumberIndex/PreferenceStore بnotification-service) مجمّعة بمسار إداري واحد.
  const platformStatusAction = findAction('operations.whatsapp_platform_status');
  // "الإدارة" — النموذج والسلوك، عبر خدمة الذكاء الاصطناعي مباشرة (platform.config)، لا عبر
  // secrets-admin: هذي قيم سياسة تُقرأ صراحة (RuntimeConfig)، لا أسرار مختومة بمفتاح.
  const configGetAction = findAction('whatsapp_assistant.operator_config');
  const configSetAction = findAction('whatsapp_assistant.set_operator_config');
  const configClearAction = findAction('whatsapp_assistant.clear_operator_config');
  const personaPreviewAction = findAction('whatsapp_assistant.persona_preview');
  // "المحاسبة" — القراءات/الجدولة عبر مسار تسعير مستقل عمداً (POST /pricing/schedule)، لا
  // set_operator_config: تعديل سعر لا يسري فوراً أبداً — انظر operator.py's own note.
  // pricing_report — استهلاك حقيقي (COST_LEDGER)، لا تخمين: معاينة "كم وحدة تستهلكها رسالة عادية
  // فعلياً" قبل جدولة أي تعديل بحاسبة وحدات الذكاء أدناه.
  const pricingReportAction = findAction('whatsapp_assistant.pricing_report');
  const pricingPendingAction = findAction('whatsapp_assistant.pricing_pending');
  const pricingScheduleAction = findAction('whatsapp_assistant.schedule_pricing');
  const pricingCancelAction = findAction('whatsapp_assistant.cancel_pending_pricing');
  // "الإدارة"/"المحاسبة" — فقط داخل فئة الذكاء الاصطناعي؛ ما فيه سبب يتكرر بأي فئة ثانية اليوم.
  const [aiTab, setAiTab] = useState<'admin' | 'calc'>('admin');
  // المسار — أي محرّك/خدمة ذكاء اصطناعي داخل الفئة نفسها تتحكّم فيه هذه الشاشة. واحد فقط اليوم
  // (مساعد واتساب المحلات)، لكن المُختار موجود ومرئي من الآن — لو انضاف مسار ثانٍ مستقبلاً (خدمة
  // عملاء المنصة مثلاً، أو محرّك ذكاء ثانٍ لواتساب نفسه) يظهر هنا مباشرة بلا إعادة تصميم، وaiTab/
  // بطاقات "الإدارة" أدناه تتحوّل حسب `aiPath` بدل ما تفترض مساعد واتساب دائماً.
  const AI_PATHS = [{ value: 'whatsapp_assistant', label: 'مساعد واتساب المحلات' }] as const;
  const [aiPath, setAiPath] = useState<string>(AI_PATHS[0].value);

  const reload = (action: AdminAction) => {
    setRows('loading');
    req<{ secrets: SecretRow[] }>(action.path, 'GET', undefined, session.access_token)
      .then((body) => setRows(body.secrets))
      .catch(() => setRows('failed'));
  };

  useEffect(() => {
    if (listAction) reload(listAction);
    // eslint-disable-next-line react-hooks/exhaustive-deps -- reload is stable per listAction identity
  }, [listAction]);

  if (catalog === 'loading') return <p className="p-6 text-sm text-text-secondary">جارٍ التحميل…</p>;
  if (catalog === 'failed') return <p role="alert" className="p-6 text-danger">تعذّرت قراءة كتالوج الإدارة.</p>;
  if (!listAction) {
    // NOT FILTERED OUT ON PURPOSE — see this file's own header and secrets-admin's
    // admin_actions.py's own note. Whoever lacks platform.secrets_manage is told so here rather
    // than finding the tab simply missing, which reads as a bug rather than a boundary — BUT see
    // NoActionAvailable's own header first: "the action is missing" and "I lack the capability"
    // are not the same fact, and secrets-admin itself being undeployed (deploy/services-pending/)
    // is exactly the live incident that taught this the hard way.
    return <NoActionAvailable catalog={catalog} permissionTitle="هذه الشاشة ليست ضمن صلاحياتك" />;
  }

  if (rows === 'loading' || rows === 'failed') {
    return (
      <div className="flex flex-col gap-6 p-6">
        <h1 className="text-2xl leading-tight tracking-tight">المزوّدين الخارجيين</h1>
        {rows === 'loading' ? (
          <p className="text-sm text-text-secondary">جارٍ التحميل…</p>
        ) : (
          <p role="alert" className="text-danger text-sm">تعذّرت قراءة قائمة المفاتيح.</p>
        )}
      </div>
    );
  }

  const groups = groupByProvider(rows);
  // أول فئة فعلياً موجودة بالاستجابة، لا فئة مجمّدة بالكود قد لا تظهر لهذا الحساب (رأسه بلا صلاحية
  // عليها أصلاً) — ونفس المنطق لو رابط التحويل المباشر سمّى فئة غير موجودة هنا.
  const active = (openProvider && groups.some(([p]) => p === openProvider))
    ? openProvider : (groups[0]?.[0] ?? null);
  const activeRows = groups.find(([p]) => p === active)?.[1] ?? [];

  return (
    <div className="flex flex-col gap-6 p-6">
      <div>
        <h1 className="text-2xl leading-tight tracking-tight">المزوّدين الخارجيين</h1>
        <p className="mt-1 text-sm text-text-secondary">
          كل مزوّد بفئته الخاصة — إعداداته وأسراره معاً بمكان واحد. تحديث مفتاح يعيد تشغيل الخدمة
          التي تقرأه — انقطاع ثوانٍ. القيمة لا تُعرض هنا أبداً، لا عند الحفظ ولا بعده — آخر أربعة
          أحرف فقط، كتأكيد أنك حفظت المفتاح الصحيح.
        </p>
      </div>
      {groups.length === 0 ? (
        <p className="text-sm text-text-secondary">لا مفاتيح مُعرَّفة بعد.</p>
      ) : (
        <>
          <Segmented
            value={active ?? ''}
            onChange={(v) => setOpenProvider(v)}
            options={groups.map(([provider, providerRows]) => {
              const meta = PROVIDER_META[provider] ?? PROVIDER_META.other;
              const configuredCount = providerRows.filter((r) => r.configured).length;
              // A REAL COLOUR-CODED PILL NOW, NOT PLAIN TEXT BAKED INTO THE LABEL — the owner
              // flagged "(2/6)" with zero colour directly; complete/partial/empty now actually
              // reads as such at a glance.
              const badgeTone: 'complete' | 'partial' | 'empty' =
                configuredCount === 0 ? 'empty'
                  : configuredCount === providerRows.length ? 'complete' : 'partial';
              return {
                value: provider, label: meta.label,
                badge: `${configuredCount}/${providerRows.length}`, badgeTone,
              };
            })}
          />
          {active === 'assistant_ai' ? (
            <div className="flex flex-col gap-4">
              {/* المسار — واحد فقط اليوم. شريطان مُقسَّمان (Segmented) فوق بعض بلا شي بينهما
                 "مسطرة تحت مسطرة" — نفس القاعدة اللي بنت عليها `TabBar` (rj-ui/TabBar.tsx's own
                 docstring) و`ci/check_no_two_tab_strips_stack_in_one_view.py`. لا داعي لعنصر
                 تحكّم كامل لخيار واحد إجباري أصلاً — يظهر اسم المسار كنص عادي، ويتحوّل إلى عنصر
                 اختيار حقيقي (مثلاً قائمة منسدلة، لا Segmented ثانٍ) فقط يوم ينضاف مسار ثانٍ
                 فعلياً. */}
              {AI_PATHS.length > 1 ? (
                <div className="flex flex-col gap-1">
                  <span className="text-label font-medium text-text-secondary">المسار</span>
                  <Segmented size="sm" value={aiPath} onChange={setAiPath}
                            options={AI_PATHS.map((p) => ({ value: p.value, label: p.label }))} />
                </div>
              ) : (
                <p className="text-label text-text-secondary">
                  المسار: <span className="font-medium text-text-primary">{AI_PATHS[0].label}</span>
                </p>
              )}
              {/* الإدارة/المحاسبة — قسمان حقيقيان من نفس الشاشة، لا فلتر: شريط تبويب حقيقي
                 (`TabBar`) بدل Segmented ثانٍ تحت شريط المزوّدين أعلاه. */}
              <TabBar value={aiTab} onChange={(v) => setAiTab(v)}
                     options={[{ value: 'admin', label: 'الإدارة' }, { value: 'calc', label: 'المحاسبة' }]} />
              {aiTab === 'admin' ? (
                <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
                  <SecretsCard providerLabel="الذكاء الاصطناعي" rows={activeRows} session={session}
                              updateAction={updateAction}
                              onSaved={() => listAction && reload(listAction)} />
                  {configGetAction ? (
                    <AIConfigCard session={session} getAction={configGetAction}
                                 setAction={configSetAction} clearAction={configClearAction} />
                  ) : null}
                  {personaPreviewAction ? (
                    <AIPersonaCard session={session} previewAction={personaPreviewAction} />
                  ) : null}
                </div>
              ) : pricingPendingAction ? (
                <AIPricingCalculator session={session}
                                     reportAction={pricingReportAction}
                                     pendingAction={pricingPendingAction}
                                     scheduleAction={pricingScheduleAction}
                                     cancelAction={pricingCancelAction} />
              ) : (
                <p className="rounded-card border border-dashed border-border-subtle p-6 text-sm text-text-secondary">
                  تعذّر الوصول لمسارات المحاسبة — راجع صلاحياتك.
                </p>
              )}
            </div>
          ) : (
            <div className="flex flex-col gap-4">
              {/* "الحالة" تظهر فوق "الأسرار" — رؤية تشغيلية قبل خزنة الأسرار، لا بدلاً عنها ولا
                 داخلها. فئة meta فقط اليوم (هي الوحيدة اللي عندها بيانات تشغيلية حقيقية جاهزة). */}
              {active === 'meta' && platformStatusAction ? (
                <MetaStatusSection session={session} action={platformStatusAction} />
              ) : null}
              <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
                <SecretsCard providerLabel={(PROVIDER_META[active ?? ''] ?? PROVIDER_META.other).label}
                            rows={activeRows} session={session} updateAction={updateAction}
                            onSaved={() => listAction && reload(listAction)} />
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}

// ── البطاقة المصغّرة المشتركة — نفس شكل الزر لكل أنواع الإعدادات (سر، إعداد تشغيل، معاينة)، والنقر
// عليها يفتح التفاصيل بنافذة بدل تمرير طويل. حالة "بلا صلاحية تعديل" (updateAction غير موجود) ما
// زالت تُفتح — الشاشة تُقال، لا تُخفى (نفس مبدأ NoActionAvailable أعلاه). ──────────────────────────
function CardTrigger({ onClick, title, subtitle, trailing }: {
  onClick: () => void; title: ReactNode; subtitle?: ReactNode; trailing?: ReactNode;
}) {
  return (
    <button type="button" onClick={onClick}
           className="flex flex-col gap-2 rounded-card border border-border-subtle bg-surface-1 p-4 text-right transition hover:border-accent/50 hover:bg-surface-2 focus-ring">
      <div className="flex items-start justify-between gap-2">
        <span className="font-medium">{title}</span>
        {trailing}
      </div>
      {subtitle}
      <span className="mt-auto flex items-center gap-1 self-start text-label text-text-muted">
        <ChevronLeft size={13} /> فتح الإعدادات
      </span>
    </button>
  );
}

// ── "الحالة" (Raje3 Meta-panel Phase 1) — رؤية تشغيلية حقيقية لواتساب المنصة نفسها، لا اتصال
// جديد بميتا. مصدران مستقلان مُجمَّعان بمسار operations واحد: حالة كل رقم (ConnectionStore، فوري
// بلا استدعاء خارجي) + معدّل إرسال حقيقي/أرقام مربوطة/انسحاب تسويقي (notification-service). كل
// رقم يُبلَّغ عن نفسه (`peer_unavailable`) بدل ما يُسقِط الشاشة كلها. ─────────────────────────────
interface ConnectionRow {
  id: string; tenant: string; state: string; step: string; waba_id: string;
  phone_number_id: string; business_id: string; detail: string; at: number; branch_id: string;
}
interface DeliveryCounts {
  // A capped count over the most-recent rows (platform v0.19.6), never a clock-bounded window —
  // `sampled` is how many of the most-recent messages this was actually computed over, and
  // `capped` is true when there were more than that (the true totals are higher).
  sent: number; failed: number; delivered: number; read: number; sampled: number; capped: boolean;
}
interface PlatformStatusResponse {
  connections: { total: number; by_state: Record<string, number>; numbers: ConnectionRow[] };
  peer_unavailable: boolean;
  deliveries: DeliveryCounts | null;
  numbers_bound: number | null;
  numbers_bound_capped?: boolean;
  marketing_opt_outs: number | null;
  marketing_opt_outs_capped?: boolean;
}

// الحالات الأربع الحقيقية بConnectionStore (core/connect.py) + "failed" النظرية — لون كل حالة
// يُقرأ فوراً: مربوط أخضر، متوقف/معطّل أحمر، بالانتظار أصفر/رمادي. لا تخمين ولا تدرّج جديد — نفس
// نغمات Badge المستخدمة بكل الشاشة أصلاً.
const CONNECTION_STATE_META: Record<string, { label: string; tone: 'success' | 'warning' | 'danger' | 'info' | 'neutral'; icon: typeof CheckCircle2 }> = {
  connected: { label: 'مربوط', tone: 'success', icon: CheckCircle2 },
  exchanging: { label: 'جارٍ الإتمام', tone: 'info', icon: Loader2 },
  finished_unconfirmed: { label: 'أُنشئ ولم يُؤكَّد', tone: 'warning', icon: Clock },
  stopped: { label: 'متوقف', tone: 'danger', icon: PhoneOff },
  failed: { label: 'فشل', tone: 'danger', icon: XCircle },
};
function connectionStateMeta(state: string) {
  return CONNECTION_STATE_META[state]
    ?? { label: state || 'غير معروف', tone: 'neutral' as const, icon: CircleHelp };
}

function fmtDateTimeFromEpoch(at: number): string {
  if (!at) return '—';
  return new Date(at * 1000).toLocaleString('ar-SA-u-nu-latn', {
    year: 'numeric', month: 'long', day: 'numeric', hour: 'numeric', minute: '2-digit',
  });
}

function MetaStatusSection({ session, action }: { session: AdminSession; action: AdminAction }) {
  const [status, setStatus] = useState<PlatformStatusResponse | 'loading' | 'failed'>('loading');

  function reload() {
    setStatus('loading');
    req<PlatformStatusResponse>(action.path, 'GET', undefined, session.access_token)
      .then(setStatus)
      .catch(() => setStatus('failed'));
  }

  // eslint-disable-next-line react-hooks/exhaustive-deps -- reload is stable per action.path identity
  useEffect(reload, [action.path, session.access_token]);

  if (status === 'loading') {
    return <p className="text-sm text-text-secondary">جارٍ تحميل حالة واتساب المنصة…</p>;
  }
  if (status === 'failed') {
    return <p role="alert" className="text-danger text-sm">تعذّرت قراءة حالة واتساب المنصة.</p>;
  }

  const d = status.deliveries;
  const byState = status.connections.by_state;
  const connectedCount = byState.connected ?? 0;
  const problemCount = (byState.stopped ?? 0) + (byState.failed ?? 0);
  const deliveryRate = d && d.sent + d.failed > 0
    ? Math.round((d.sent / (d.sent + d.failed)) * 100) : null;

  return (
    <section className="flex flex-col gap-3 rounded-card border border-border-subtle bg-surface-1 p-4">
      <div className="flex items-center justify-between gap-2">
        <div>
          <h2 className="font-medium">حالة واتساب المنصة</h2>
          <p className="text-label text-text-secondary">
            واتساب المنصة نفسها — إرسالات مثل رمز التحقق عند التسجيل، لا رقم أي محل.
          </p>
        </div>
        <Button size="sm" variant="ghost" onClick={reload}>تحديث</Button>
      </div>

      {status.peer_unavailable ? (
        <div className="flex items-center gap-2 rounded-card bg-warning-soft p-3 text-sm text-warning-on-soft">
          <AlertTriangle size={16} className="shrink-0" />
          تعذّر الاتصال بخدمة الإشعارات — أرقام الإرسال والانسحاب أدناه غير متاحة الآن، وحالة
          الأرقام (بالأسفل) مقروءة محلياً وسليمة رغم ذلك.
        </div>
      ) : null}

      {/* بطاقات مؤشرات ملوَّنة — نفس مكوّن KpiCard المستخدم بشاشات المحفظة/الحجوزات، لا أرقام
         عادية بلا لون. */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
        <KpiCard icon={<CheckCircle2 size={18} />} label="أرقام مربوطة الآن"
                value={connectedCount} tone={connectedCount > 0 ? 'success' : 'neutral'}
                hint={`من إجمالي ${status.connections.total} رقم متصل تاريخياً`}
                testId="kpi-connected-numbers" />
        <KpiCard icon={<PhoneOff size={18} />} label="أرقام متوقفة/فاشلة"
                value={problemCount} tone={problemCount > 0 ? 'danger' : 'neutral'}
                testId="kpi-problem-numbers" />
        <KpiCard icon={<Send size={18} />} label="رسائل مُرسَلة"
                value={d ? d.sent : '—'} tone={d && d.sent > 0 ? 'success' : 'neutral'}
                hint={d ? `من آخر ${d.sampled}${d.capped ? '+' : ''} رسالة` : 'تعذّرت القراءة'}
                testId="kpi-sent" />
        <KpiCard icon={<XCircle size={18} />} label="رسائل فشلت"
                value={d ? d.failed : '—'}
                tone={d && d.failed > 0 ? 'danger' : (d ? 'success' : 'neutral')}
                hint={deliveryRate !== null ? `نجاح ${deliveryRate}٪` : undefined}
                testId="kpi-failed" />
        <KpiCard icon={<Sparkles size={18} />} label="أرقام مربوطة (المنصّة)"
                value={status.numbers_bound === null ? '—'
                       : `${status.numbers_bound}${status.numbers_bound_capped ? '+' : ''}`}
                tone="accent" testId="kpi-numbers-bound" />
        <KpiCard icon={<UserX size={18} />} label="ألغوا الاشتراك التسويقي"
                value={status.marketing_opt_outs === null ? '—'
                       : `${status.marketing_opt_outs}${status.marketing_opt_outs_capped ? '+' : ''}`}
                tone="warning" testId="kpi-opt-outs" />
      </div>

      {/* حالة كل رقم — شارة ملوَّنة لكل حالة، لا نص عادي. */}
      {status.connections.numbers.length === 0 ? (
        <p className="text-sm text-text-secondary">لا اتصالات مسجَّلة بعد.</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-right text-sm">
            <thead>
              <tr className="text-label text-text-secondary">
                <th className="p-2 font-medium">المحل</th>
                <th className="p-2 font-medium">الحالة</th>
                <th className="p-2 font-medium">آخر تحديث</th>
              </tr>
            </thead>
            <tbody>
              {status.connections.numbers.map((row) => {
                const meta = connectionStateMeta(row.state);
                const Icon = meta.icon;
                return (
                  <tr key={row.id} className="border-t border-border-subtle">
                    <td className="p-2">
                      <span dir="ltr" className="font-mono text-label">{row.tenant}</span>
                      {row.branch_id ? <span className="text-text-muted"> · {row.branch_id}</span> : null}
                    </td>
                    <td className="p-2">
                      <Badge tone={meta.tone}>
                        <Icon size={12} className={row.state === 'exchanging' ? 'animate-spin' : undefined} />
                        {meta.label}
                      </Badge>
                    </td>
                    <td className="p-2 text-text-secondary">{fmtDateTimeFromEpoch(row.at)}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}

// ── قائمة النماذج، مقسّمة حسب المزوّد — كلهم فعلياً على نفس مشروع Vertex AI (منطقة الدمام
// me-central2 تستضيف نماذج من هذي المزوّدين السبعة عبر Model Garden، بنفس المشروع/بيانات
// الاعتماد المسجَّلة أعلاه) — الفرق ليس "جوجل مقابل غيره"، الفرق شكل الاستدعاء (`shape`) اللي
// نمرره لـassistant-service (base-services، v0.18.61+) عند إنشاء الاتصال، وهي اللي فعلياً تتصل
// بجوجل. `adapters/llm/assistant_service.py`'s الخاص بـ`_model_url_and_shape` يبني الرابط والشكل
// الصحيحين حسب بادئة اسم النموذج (gemini-/claude-/غيره) — مطابق تماماً لتصنيف `wired` هنا، فلا
// يفترقان صامتاً. "غير مدعوم بعد" ليست تخميناً حالة بحالة:
//   • xAI (Grok): لا يوجد تأكيد إنه موجود على Vertex Model Garden أصلاً — لم يُتحقق منه.
//   • Alibaba (Qwen): مؤكَّد أنه غير موجود على Vertex Model Garden (يحتاج DashScope مباشرة، مضيف
//     ومصادقة مختلفين كلياً عن مشروعنا الحالي) — Vertex ليس فقط "غير مبني"، بل غير الطريق الصحيح.
// كل الباقي (Google/Anthropic/Zhipu/OpenAI's gpt-oss/MiniMax) مؤكَّد على Vertex ومسار الاستدعاء
// مبني ومُختبر (tests/unit/test_assistant_connections.py) — يبقى الشرط التشغيلي الوحيد قبل أول
// استدعاء حقيقي: مشروع GCP حقيقي (لا يوجد بعد، انظر memory) + لأي ناشر شريك (Claude تحديداً)
// تفعيل صريح من Model Garden وزيادة حصة (quota) من نفس لوحة GCP، موافقتها 24-48 ساعة.
const MODEL_PROVIDER_META: Record<string, string> = {
  google: 'Google', anthropic: 'Anthropic', xai: 'xAI', zhipu: 'Zhipu AI',
  openai: 'OpenAI', minimax: 'MiniMax', alibaba: 'Alibaba',
};
interface ModelOption {
  id: string; label: string; provider: keyof typeof MODEL_PROVIDER_META; wired: boolean;
  /** Shown next to the label ONLY when `wired` is false — the real, per-provider reason, not a
   *  generic "not built yet" that reads as a promise (Qwen never will be, via this project). */
  disabledReason?: string;
}
const MODEL_OPTIONS: ModelOption[] = [
  // الافتراضي الحالي (deploy/services/whatsapp-assistant.values.yaml، 2026-09-09) — لاحظ إن
  // التأكيد الرسمي لتوفّر me-central2 (توثيق Google، 2026-09-02) كان لـ3.5-flash-lite بالذات، لا
  // 3.1 — انظر تعليق ASSISTANT_MODEL_NAME بنفس ملف القيم.
  { id: 'gemini-3.1-flash-lite', label: 'Gemini 3.1 Flash Lite (الحالي)', provider: 'google', wired: true },
  { id: 'gemini-3.5-flash-lite', label: 'Gemini 3.5 Flash Lite', provider: 'google', wired: true },
  { id: 'gemini-3.5-flash', label: 'Gemini 3.5 Flash', provider: 'google', wired: true },
  { id: 'gemini-3.5-pro', label: 'Gemini 3.5 Pro', provider: 'google', wired: true },
  { id: 'gemini-2.5-flash-lite', label: 'Gemini 2.5 Flash Lite', provider: 'google', wired: true },
  { id: 'gemini-2.5-flash', label: 'Gemini 2.5 Flash', provider: 'google', wired: true },
  { id: 'gemini-2.5-pro', label: 'Gemini 2.5 Pro', provider: 'google', wired: true },
  { id: 'claude-opus-5', label: 'Claude Opus 5', provider: 'anthropic', wired: true },
  { id: 'claude-sonnet-5', label: 'Claude Sonnet 5', provider: 'anthropic', wired: true },
  { id: 'claude-haiku-4-5', label: 'Claude Haiku 4.5', provider: 'anthropic', wired: true },
  { id: 'grok-4', label: 'Grok 4', provider: 'xai', wired: false,
    disabledReason: 'غير مؤكَّد على Vertex AI' },
  { id: 'grok-4-fast', label: 'Grok 4 Fast', provider: 'xai', wired: false,
    disabledReason: 'غير مؤكَّد على Vertex AI' },
  { id: 'glm-4.6', label: 'GLM-4.6', provider: 'zhipu', wired: true },
  { id: 'glm-4.5-air', label: 'GLM-4.5 Air', provider: 'zhipu', wired: true },
  { id: 'gpt-oss-120b', label: 'gpt-oss-120b', provider: 'openai', wired: true },
  { id: 'gpt-oss-20b', label: 'gpt-oss-20b', provider: 'openai', wired: true },
  { id: 'minimax-m2', label: 'MiniMax M2', provider: 'minimax', wired: true },
  { id: 'qwen3-max', label: 'Qwen3 Max', provider: 'alibaba', wired: false,
    disabledReason: 'ليس على Vertex — يحتاج DashScope' },
  { id: 'qwen3-235b-a22b', label: 'Qwen3 235B A22B', provider: 'alibaba', wired: false,
    disabledReason: 'ليس على Vertex — يحتاج DashScope' },
];

// ── "الإدارة" — نموذج الذكاء الاصطناعي وسلوكه (app/runtime_policy.py، حيّ بلا إعادة نشر) ──────────
// `min`/`max` MIRROR app/config.py's OWN field_validators + app/runtime_policy.py's
// `validate_runtime_override` — the backend refuses anything outside these bounds regardless
// (a raw API call cannot bypass this screen), so these are a courtesy: catching a typo before
// the round trip, not the actual enforcement. A key with no `min`/`max` here renders a free-text
// input, same as before.
const CONFIG_KEY_META: Record<string, { label: string; help: string; min?: number; max?: number }> = {
  ASSISTANT_MODEL_NAME: { label: 'النموذج',
    help: 'اختر من قائمة النماذج المتاحة، مبوّبة حسب المزوّد — تغييره يسري على المحادثة التالية فوراً حتى للمحلات اللي بدأت تحادث قبل التغيير. Grok وQwen معطّلان: Grok غير مؤكَّد على Vertex AI أصلاً، وQwen مؤكَّد أنه خارج Vertex كلياً (يحتاج مضيفاً/مصادقة مختلفين تماماً). باقي الناشرين مبنيّون ومُختبرون، بانتظار مشروع GCP حقيقي (ولـClaude تحديداً: تفعيل + حصة إضافية من نفس اللوحة).' },
  SOFT_DECLINE_THRESHOLD: { label: 'عتبة التوقف عن الاقتراح', min: 1, max: 100,
    help: 'عدد مرات رفض العميل لاقتراح قبل ما يتوقف المساعد عن اقتراح أي شي عليه (بلا تصعيد لموظف).' },
  MAX_CAROUSEL_CARDS: { label: 'أقصى بطاقات بالعرض', min: 2, max: 10,
    help: 'أقصى عدد بطاقات خدمات/باقات يعرضها المساعد بردّ واحد. حدود ميتا نفسها بقالب العرض: 2-10 بطاقات.' },
  MAX_REPLY_TOKENS: { label: 'أقصى طول رد', min: 1, max: 4000,
    help: 'سقف حماية تقني (توكن) لطول رد النموذج نفسه — يمنع رداً غير طبيعي الطول من تكلفة أضعاف رد عادي. لا علاقة له بحد كلمات رسالة العميل (إعداد المحل الخاص به).' },
};

function AIConfigCard({ session, getAction, setAction, clearAction }: {
  session: AdminSession; getAction: AdminAction; setAction?: AdminAction; clearAction?: AdminAction;
}) {
  const [open, setOpen] = useState(false);
  const [config, setConfig] = useState<Record<string, unknown> | 'loading' | 'failed'>('loading');

  function reload() {
    setConfig('loading');
    req<{ config: Record<string, unknown> }>(getAction.path, 'GET', undefined, session.access_token)
      .then((body) => setConfig(body.config))
      .catch(() => setConfig('failed'));
  }

  useEffect(reload, [getAction.path, session.access_token]);

  // PRICING_* IS EXCLUDED HERE, DELIBERATELY — the backend refuses them on this instant-apply
  // route (see operator.py's own guard: "cannot be changed at runtime... only via POST /pricing/
  // schedule"), so listing them here would show a "تحديث" button that always fails. They live in
  // "المحاسبة" instead, through the scheduled path only.
  const entries = typeof config === 'object'
    ? Object.entries(config).filter(([k]) => !k.startsWith('PRICING_')) : [];
  const count = entries.length;

  // STILL READ HERE, even though PRICING_* is excluded from `entries` just above — the ONE
  // question the model dropdown needs answered: "is the currently-selected model actually
  // priced?" An operator picking a model with no cost entry used to find out only after the fact
  // (core/ai_unit_pricing.py's own model_rate_halalas_per_1k substitutes a rate rather than
  // blocking, so nothing here would otherwise ever surface the gap). Same JSON `config` already
  // fetched for this card — no second request.
  const pricedModelIds = new Set<string>();
  if (typeof config === 'object') {
    try {
      const parsed = JSON.parse(String(config.PRICING_AI_UNIT_MODEL_COSTS_JSON ?? '{}'));
      if (parsed && typeof parsed === 'object') Object.keys(parsed).forEach((k) => pricedModelIds.add(k));
    } catch { /* malformed JSON reads as "nothing priced" — same fail-safe direction as the backend */ }
  }

  return (
    <>
      <CardTrigger onClick={() => setOpen(true)} title="النموذج والسلوك"
                   subtitle={<span className="text-label text-text-secondary">
                     {count ? `${count} إعداد قابل للتعديل الآن` : 'إعدادات النموذج الحيّة'}
                   </span>} />
      <Modal open={open} onClose={() => setOpen(false)} title="النموذج والسلوك"
            subtitle="تعديل يسري على المحادثة التالية فوراً — بلا إعادة تشغيل.">
        {config === 'loading' ? (
          <p className="text-sm text-text-secondary">جارٍ التحميل…</p>
        ) : config === 'failed' ? (
          <p role="alert" className="text-danger text-sm">تعذّرت قراءة الإعدادات الحالية.</p>
        ) : (
          <div className="flex flex-col gap-4">
            {entries.map(([key, value]) => (
              <ConfigRow key={key} session={session} k={key} currentValue={value}
                        setAction={setAction} clearAction={clearAction} onSaved={reload}
                        pricedModelIds={key === 'ASSISTANT_MODEL_NAME' ? pricedModelIds : undefined} />
            ))}
          </div>
        )}
      </Modal>
    </>
  );
}

function ConfigRow({ session, k, currentValue, setAction, clearAction, onSaved, pricedModelIds }: {
  session: AdminSession; k: string; currentValue: unknown;
  setAction?: AdminAction; clearAction?: AdminAction; onSaved: () => void;
  /** Only passed for k === 'ASSISTANT_MODEL_NAME' — see AIConfigCard's own note on where this
   *  comes from. `undefined` for every other row (no warning rendered at all). */
  pricedModelIds?: Set<string>;
}) {
  const [value, setValue] = useState(String(currentValue ?? ''));
  // خطوة تأكيد داخل نفس النافذة — لا نافذة ثانية فوق الأولى. `Modal` هنا (بخلاف ConfirmDialog) لا
  // يدعم التكديس (انظر تعليقه الخاص)، فأي تأكيد يصير محتوى بديل داخل نفس النافذة المفتوحة أصلاً.
  const [step, setStep] = useState<'edit' | 'confirm-set' | 'confirm-clear'>('edit');
  const meta = CONFIG_KEY_META[k];
  const isNumeric = meta?.min !== undefined || meta?.max !== undefined;
  // A COURTESY, NOT THE ENFORCEMENT — app/runtime_policy.py's `validate_runtime_override` refuses
  // the same range server-side regardless (see this file's own note on CONFIG_KEY_META above).
  // Empty is caught separately (the "تحديث" button is already disabled on `!value`).
  const numericInvalid = isNumeric && value !== '' && (() => {
    if (!/^-?\d+$/.test(value)) return true;
    const n = Number(value);
    return (meta.min !== undefined && n < meta.min) || (meta.max !== undefined && n > meta.max);
  })();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  async function doSet() {
    if (!setAction || !value) return;
    setBusy(true); setError('');
    try {
      await req(setAction.path, 'PUT', { key: k, value }, session.access_token);
      onSaved();
      setStep('edit');
    } catch (err) {
      setError(sentenceFor(err, 'تعذّر حفظ القيمة.'));
    } finally { setBusy(false); }
  }

  async function doClear() {
    if (!clearAction) return;
    setBusy(true); setError('');
    try {
      await req(clearAction.path.replace('{key}', encodeURIComponent(k)), 'DELETE', undefined, session.access_token);
      onSaved();
      setStep('edit');
    } catch (err) {
      setError(sentenceFor(err, 'تعذّر حذف الإعداد.'));
    } finally { setBusy(false); }
  }

  if (step !== 'edit') {
    const clearing = step === 'confirm-clear';
    return (
      <div className="flex flex-col gap-3 rounded-card border border-border-subtle p-3">
        <p className="font-medium">
          {clearing ? `استرجاع افتراضي "${meta?.label ?? k}"؟` : `تعديل "${meta?.label ?? k}"؟`}
        </p>
        <p className="text-label text-text-secondary">
          {clearing ? 'يعود للقيمة المبنيّة في الخدمة بدل القيمة المعدَّلة يدوياً.'
                    : 'يسري على المحادثة التالية فوراً — بلا إعادة تشغيل.'}
        </p>
        {error ? <p role="alert" className="text-danger text-sm">{error}</p> : null}
        <div className="flex justify-end gap-2">
          <Button variant="ghost" onClick={() => setStep('edit')} disabled={busy}>رجوع</Button>
          <Button variant={clearing ? 'solid' : 'danger'} onClick={clearing ? doClear : doSet} disabled={busy}>
            تأكيد
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-1.5 border-t border-border-subtle pt-3 first:border-t-0 first:pt-0">
      <div className="flex items-center justify-between gap-2">
        <label className="text-sm font-medium" htmlFor={`config-${k}`}>{meta?.label ?? k}</label>
        <span dir="ltr" className="text-label font-mono text-text-muted">{k}</span>
      </div>
      {meta?.help ? <p className="text-label text-text-secondary">{meta.help}</p> : null}
      <div className="flex flex-wrap items-center gap-2">
        {k === 'ASSISTANT_MODEL_NAME' ? (
          <Select id={`config-${k}`} dir="ltr" value={value} onChange={(e) => setValue(e.target.value)}
                 className="max-w-xs">
            {/* القيمة الحالية قد تكون معرّفاً لم يعد بالقائمة (نسخة قديمة، تعديل خارج الشاشة) —
               تُضاف كخيار وحيد ظاهر بدل ما تُفقد صامتة أو تُستبدل بأول نموذج بالقائمة. */}
            {!MODEL_OPTIONS.some((m) => m.id === value) && value ? (
              <option value={value}>{value} (قيمة حالية غير مدرجة)</option>
            ) : null}
            {Object.entries(MODEL_PROVIDER_META).map(([provider, providerLabel]) => (
              <optgroup key={provider} label={providerLabel}>
                {MODEL_OPTIONS.filter((m) => m.provider === provider).map((m) => (
                  <option key={m.id} value={m.id} disabled={!m.wired}>
                    {m.label}{m.wired ? '' : ` — ${m.disabledReason ?? 'غير مدعوم'}`}
                  </option>
                ))}
              </optgroup>
            ))}
          </Select>
        ) : (
          <Input id={`config-${k}`} dir="ltr" value={value} onChange={(e) => setValue(e.target.value)}
                type={isNumeric ? 'number' : 'text'} min={meta?.min} max={meta?.max} step={1}
                className="max-w-xs" />
        )}
        {isNumeric && meta ? (
          <span className="text-label text-text-muted">المدى المسموح: {meta.min}–{meta.max}</span>
        ) : null}
        {setAction ? (
          <Button size="sm" disabled={!value || numericInvalid} onClick={() => setStep('confirm-set')}>
            تحديث
          </Button>
        ) : null}
        {clearAction ? (
          <Button size="sm" variant="outline" onClick={() => setStep('confirm-clear')}>
            استرجاع الافتراضي
          </Button>
        ) : null}
      </div>
      {numericInvalid ? (
        <p role="alert" className="text-danger text-sm">
          يجب أن تكون قيمة صحيحة بين {meta?.min} و{meta?.max}.
        </p>
      ) : null}
      {pricedModelIds && value && !pricedModelIds.has(value) ? (
        <p role="alert" className="text-warning text-sm">
          هذا النموذج بلا سعر مسجَّل بـ«المحاسبة» — سيُحاسَب بسعر بديل (الأغلى بين النماذج
          المسجَّلة حالياً) لحد ما يُسجَّل سعره الحقيقي.
        </p>
      ) : null}
      {error ? <p role="alert" className="text-danger text-sm">{error}</p> : null}
    </div>
  );
}

// ── "المحاسبة" — إعدادات تسعير «وحدات الذكاء» (core/ai_unit_pricing.py): السعر الحقيقي لكل
// نموذج عند جوجل + هامش = المعدّل الذي يُستهلَك منه رصيد المحفظة، وتطبيق يمرّ دائماً عبر جدولة
// مؤجَّلة — انظر core/pricing_schedule.py's own docstring: تعديل سعر لا يسري فوراً أبداً. ─────────
interface PendingChange { key: string; value: string | number | boolean; effective_at: number; scheduled_by: string; scheduled_at: number; }
interface UsageReport {
  days: number; calls: number; conversations: number; input_tokens: number; output_tokens: number;
  avg_input_tokens_per_call: number; avg_output_tokens_per_call: number;
  avg_calls_per_conversation: number; truncated: boolean;
}

const PRICING_KEY_LABEL: Record<string, string> = {
  PRICING_AI_UNIT_UNITS_PER_HALALA: 'وحدات لكل هللة',
  PRICING_AI_UNIT_INPUT_MARGIN_MULTIPLIER: 'مضاعف هامش الدخل',
  PRICING_AI_UNIT_OUTPUT_MARGIN_MULTIPLIER: 'مضاعف هامش الخرج',
  PRICING_AI_UNIT_USD_TO_SAR: 'سعر صرف الدولار',
  PRICING_AI_UNIT_MODEL_COSTS_JSON: 'تكلفة جوجل الحقيقية لكل نموذج',
};

function fmtDate(epoch: number): string {
  return new Date(epoch * 1000).toLocaleDateString('ar-SA-u-nu-latn', {
    year: 'numeric', month: 'long', day: 'numeric',
  });
}

/** The secrets list's own `updated_at` — an ISO string ("2026-09-04T12:31:18Z"), never an epoch
 *  number like `fmtDate` above takes. Shown raw before this: an operator reading a settings screen
 *  should never have to parse ISO 8601 by eye. Falls back to the raw string on a value `Date`
 *  cannot parse, rather than showing nothing or crashing the row. */
function fmtDateTime(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString('ar-SA-u-nu-latn', {
    year: 'numeric', month: 'long', day: 'numeric', hour: 'numeric', minute: '2-digit',
  });
}

function AIPricingCalculator({ session, reportAction, pendingAction, scheduleAction, cancelAction }: {
  session: AdminSession; reportAction?: AdminAction; pendingAction: AdminAction;
  scheduleAction?: AdminAction; cancelAction?: AdminAction;
}) {
  const [pending, setPending] = useState<PendingChange[] | 'loading' | 'failed'>('loading');
  // استهلاك حقيقي (COST_LEDGER) — لا تخمين. يغذّي معاينة "كم وحدة فعلياً" تحت حاسبة وحدات الذكاء،
  // بنفس الدور اللي كان له بحاسبة تسعير الاشتراك القديمة (المحذوفة) قبل ما نظام الوحدات يُبنى.
  const [report, setReport] = useState<UsageReport | 'loading' | 'failed'>('loading');
  const days = 30;

  useEffect(() => {
    if (!reportAction) { setReport('failed'); return; }
    req<UsageReport>(`${reportAction.path}?days=${days}`, 'GET', undefined, session.access_token)
      .then(setReport).catch(() => setReport('failed'));
  }, [reportAction, session.access_token]);   // eslint-disable-line react-hooks/exhaustive-deps

  // ── وحدات الذكاء — سعر عرض ثابت (وحدات لكل هللة) حول تكلفة حقيقية تختلف باختلاف النموذج. كل
  // حقل هنا مفتاح تسعير مثل أي مفتاح فوق — يمرّ بنفس بوابة الجدولة، لا يُطبَّق فوراً أبداً.
  const [unitsPerHalala, setUnitsPerHalala] = useState('1000');
  const [inputMargin, setInputMargin] = useState('5');
  const [outputMargin, setOutputMargin] = useState('2');
  const [usdToSar, setUsdToSar] = useState('3.75');
  const [modelCostsJson, setModelCostsJson] = useState(
    '{"gemini-3.1-flash-lite": {"input_usd_per_million": 0.25, "output_usd_per_million": 1.50}}');
  const [aiUnitEffectiveInDays, setAiUnitEffectiveInDays] = useState('15');
  const [aiUnitScheduling, setAiUnitScheduling] = useState(false);
  const [aiUnitScheduleError, setAiUnitScheduleError] = useState('');
  const [aiUnitScheduleDone, setAiUnitScheduleDone] = useState(false);

  async function doScheduleAiUnit() {
    if (!scheduleAction) return;
    setAiUnitScheduling(true); setAiUnitScheduleError(''); setAiUnitScheduleDone(false);
    const days_ = Number(aiUnitEffectiveInDays) || 0;
    try {
      let parsedCosts: unknown;
      try { parsedCosts = JSON.parse(modelCostsJson); } catch { throw new Error('صيغة تكلفة النماذج ليست JSON صحيحاً.'); }
      if (typeof parsedCosts !== 'object' || parsedCosts === null) throw new Error('صيغة تكلفة النماذج ليست JSON صحيحاً.');
      const fields: [string, string | number][] = [
        ['PRICING_AI_UNIT_UNITS_PER_HALALA', Math.round(Number(unitsPerHalala) || 0)],
        ['PRICING_AI_UNIT_INPUT_MARGIN_MULTIPLIER', Number(inputMargin) || 0],
        ['PRICING_AI_UNIT_OUTPUT_MARGIN_MULTIPLIER', Number(outputMargin) || 0],
        ['PRICING_AI_UNIT_USD_TO_SAR', Number(usdToSar) || 0],
        ['PRICING_AI_UNIT_MODEL_COSTS_JSON', modelCostsJson],
      ];
      // بالتتابع، لا Promise.all — التناسق أهم من السرعة هنا، وأي رفض (حد غير منطقي) يجب أن
      // يوقف الباقي بدل جدولة نصف التعديل فقط.
      for (const [key, value] of fields) {
        await req(scheduleAction.path, 'POST', { key, value, effective_in_days: days_ },
          session.access_token);
      }
      setAiUnitScheduleDone(true);
      reload();
    } catch (err) {
      setAiUnitScheduleError(sentenceFor(err, 'تعذّرت جدولة إعدادات وحدات الذكاء.'));
    } finally { setAiUnitScheduling(false); }
  }

  function reload() {
    setPending('loading');
    req<{ pending: PendingChange[] }>(pendingAction.path, 'GET', undefined, session.access_token)
      .then((body) => setPending(body.pending)).catch(() => setPending('failed'));
  }

  useEffect(reload, [pendingAction.path, session.access_token]);

  async function doCancel(key: string) {
    if (!cancelAction) return;
    await req(cancelAction.path.replace('{key}', encodeURIComponent(key)), 'DELETE',
      undefined, session.access_token).catch(() => {});
    reload();
  }

  return (
    <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
      {/* ── تعديلات مجدولة قادمة ─────────────────────────────────────────────────────────── */}
      <section className="flex flex-col gap-3 rounded-card border border-border-subtle bg-surface-1 p-4">
        <h3 className="font-medium">تعديلات مجدولة قادمة</h3>
        {pending === 'loading' ? (
          <p className="text-sm text-text-secondary">جارٍ التحميل…</p>
        ) : pending === 'failed' ? (
          <p role="alert" className="text-danger text-sm">تعذّرت القراءة.</p>
        ) : pending.length === 0 ? (
          <p className="text-sm text-text-secondary">لا شي مجدوَل حالياً.</p>
        ) : (
          <div className="flex flex-col gap-2">
            {pending.map((c) => (
              <div key={c.key} className="flex items-center justify-between gap-2 rounded-card bg-surface-2 p-3 text-sm">
                <div>
                  <p className="font-medium">{PRICING_KEY_LABEL[c.key] ?? c.key}</p>
                  <p className="text-label text-text-secondary">
                    القيمة الجديدة: {String(c.value)} — يسري {fmtDate(c.effective_at)}
                  </p>
                </div>
                {cancelAction ? (
                  <Button variant="ghost" size="sm" onClick={() => doCancel(c.key)}>إلغاء</Button>
                ) : null}
              </div>
            ))}
          </div>
        )}
      </section>

      {/* ── وحدات الذكاء — سعر عرض ثابت حول تكلفة حقيقية بالنموذج ───────────────────────────── */}
      <section className="flex flex-col gap-4 rounded-card border border-border-subtle bg-surface-1 p-4 lg:col-span-2">
        <div>
          <h3 className="font-medium">إعدادات وحدات الذكاء</h3>
          <p className="text-label text-text-secondary">
            رصيد الذكاء يُعرَض للمحل بـ«وحدات الذكاء» — سعر صرف ثابت لا يتغيّر (وحدات لكل هللة)، ملفوف
            حول تكلفة حقيقية تختلف باختلاف النموذج فعلاً (النموذج الأغلى يستهلك وحدات أكثر لنفس
            الرسالة). كل حقل هنا يمرّ ببوابة الجدولة نفسها فوق — لا يسري فوراً أبداً.
          </p>
        </div>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          <Field label="وحدات لكل هللة" htmlFor="calc-units-per-halala">
            <Input id="calc-units-per-halala" dir="ltr" type="number" min={1} value={unitsPerHalala}
                  onChange={(e) => setUnitsPerHalala(e.target.value)} />
            <p className="text-label text-text-secondary">
              سعر عرض ثابت — لا علاقة له بأي نموذج، مجرد مقياس عرض للرصيد والاستهلاك.
            </p>
          </Field>
          <Field label="سعر صرف الدولار (ريال)" htmlFor="calc-usd-to-sar">
            <Input id="calc-usd-to-sar" dir="ltr" type="number" step="0.01" value={usdToSar}
                  onChange={(e) => setUsdToSar(e.target.value)} />
            <p className="text-label text-text-secondary">جوجل يسعّر بالدولار — التثبيت الرسمي 3.75.</p>
          </Field>
          <Field label="مضاعف هامش الدخل (Input)" htmlFor="calc-input-margin">
            <Input id="calc-input-margin" dir="ltr" type="number" step="0.1" value={inputMargin}
                  onChange={(e) => setInputMargin(e.target.value)} />
            <p className="text-label text-text-secondary">
              يُضرَب في تكلفة الدخل الحقيقية لكل نموذج — منفصل عن هامش الخرج عمداً.
            </p>
          </Field>
          <Field label="مضاعف هامش الخرج (Output)" htmlFor="calc-output-margin">
            <Input id="calc-output-margin" dir="ltr" type="number" step="0.1" value={outputMargin}
                  onChange={(e) => setOutputMargin(e.target.value)} />
            <p className="text-label text-text-secondary">
              الخرج يكلّف جوجل أعلى بكثير من الدخل لكل توكن — لهذا مضاعف الخرج مستقل عن الدخل.
            </p>
          </Field>
        </div>
        <Field label="تكلفة جوجل الحقيقية لكل نموذج (JSON)" htmlFor="calc-model-costs">
          <textarea id="calc-model-costs" dir="ltr"
                   className="w-full rounded-input border border-border-subtle bg-surface-0 p-2 font-mono text-sm"
                   rows={3} value={modelCostsJson}
                   onChange={(e) => setModelCostsJson(e.target.value)} />
          <p className="text-label text-text-secondary">
            السعر الحقيقي كما هو من فاتورة جوجل الفعلية أو صفحة تسعيرها الرسمية لكل نموذج — بالدولار لكل
            مليون توكن، دخل وخرج منفصلين — بلا أي هامش إقليمي مضاف هنا، الرقم المُدخَل هو التكلفة
            الحقيقية كما هي. نموذج غير مذكور هنا يُحتسَب بمعدّل احتياطي صفري بدل إيقاف المساعد.
          </p>
        </Field>
        <AiUnitConsumptionPreview report={report} unitsPerHalala={unitsPerHalala}
                                  inputMargin={inputMargin} outputMargin={outputMargin}
                                  usdToSar={usdToSar} modelCostsJson={modelCostsJson} />
        {scheduleAction ? (
          <div className="flex flex-col gap-2 border-t border-border-subtle pt-3">
            <div className="flex flex-wrap items-end gap-2">
              <Field label="يسري بعد (أيام)" htmlFor="calc-ai-unit-effective-days">
                <Input id="calc-ai-unit-effective-days" dir="ltr" type="number" min={1}
                      value={aiUnitEffectiveInDays}
                      onChange={(e) => setAiUnitEffectiveInDays(e.target.value)} className="max-w-[8rem]" />
              </Field>
              <Button onClick={doScheduleAiUnit} disabled={aiUnitScheduling}>
                {aiUnitScheduling ? 'جارٍ الجدولة…' : 'جدولة إعدادات وحدات الذكاء'}
              </Button>
            </div>
            <p className="text-label text-text-secondary">
              لا يسري فوراً — بعد {aiUnitEffectiveInDays || '؟'} يوم من الآن، عشان تقدر تُعلم المحلات قبلها.
            </p>
            {aiUnitScheduleError ? <p role="alert" className="text-danger text-sm">{aiUnitScheduleError}</p> : null}
            {aiUnitScheduleDone ? <p className="text-success text-sm">تمّت الجدولة.</p> : null}
          </div>
        ) : null}
      </section>
    </div>
  );
}

// ── معاينة الاستهلاك — الأرقام المكتوبة فوق (لم تُجدوَل بعد) مطبّقة على الاستهلاك الفعلي الحقيقي
// (COST_LEDGER)، لا افتراض 300/150 توكن اعتباطي. أول نموذج مذكور بـmodelCostsJson فقط — نفس منطق
// core/ai_unit_pricing.py's الخاص بالمعاودة على نموذج غير مذكور، مبسَّط هنا لعرض واحد واضح بدل
// عرض كل نموذج بالسجل دفعة وحدة. أي خطأ صيغة/رقم غير منطقي يُخفي المعاينة بدل ما يعرض NaN.
function AiUnitConsumptionPreview({ report, unitsPerHalala, inputMargin, outputMargin, usdToSar,
                                   modelCostsJson }: {
  report: UsageReport | 'loading' | 'failed'; unitsPerHalala: string; inputMargin: string;
  outputMargin: string; usdToSar: string; modelCostsJson: string;
}) {
  if (report === 'loading') {
    return <p className="text-label text-text-secondary">جارٍ قراءة الاستهلاك الفعلي…</p>;
  }
  if (report === 'failed') {
    return (
      <p className="text-label text-text-secondary">
        تعذّرت قراءة الاستهلاك الفعلي — المعاينة تحتاجه، الجدولة نفسها لا تحتاجه.
      </p>
    );
  }
  if (report.calls === 0) {
    return (
      <p className="text-label text-text-secondary">
        لا استهلاك فعلي بعد (آخر {report.days} يوم) — معاينة الاستهلاك تظهر أول ما يرد البوت على
        رسالة حقيقية.
      </p>
    );
  }

  let firstModelCost: { input_usd_per_million: number; output_usd_per_million: number } | null = null;
  try {
    const parsed = JSON.parse(modelCostsJson) as Record<string, { input_usd_per_million: number;
      output_usd_per_million: number }>;
    const firstKey = Object.keys(parsed)[0];
    firstModelCost = firstKey ? parsed[firstKey] : null;
  } catch { /* معاينة فقط — صيغة غير صالحة تُخفي المعاينة، لا تُبلغ خطأ الجدولة الحقيقي */ }

  const unitsPerHalalaNum = Number(unitsPerHalala);
  const inputMarginNum = Number(inputMargin);
  const outputMarginNum = Number(outputMargin);
  const usdToSarNum = Number(usdToSar);
  const valid = firstModelCost
    && Number.isFinite(unitsPerHalalaNum) && Number.isFinite(inputMarginNum)
    && Number.isFinite(outputMarginNum) && Number.isFinite(usdToSarNum);
  if (!valid || !firstModelCost) {
    return (
      <p className="text-label text-text-secondary">
        عدّل الأرقام فوق لأرقام صحيحة لمعاينة الاستهلاك.
      </p>
    );
  }

  // نفس معادلة halalas_per_1k_tokens بـai_unit_pricing.py بالضبط: دولار/مليون × سعر الصرف ×
  // الهامش = هللات لكل مليون، ÷1000 = هللات لكل 1000 توكن، ×وحدات/هللة = وحدات لكل 1000 توكن.
  const unitsPer1k = (usdPerMillion: number, margin: number) =>
    ((usdPerMillion * usdToSarNum * margin * 100) / 1000) * unitsPerHalalaNum;
  const inUnits = unitsPer1k(firstModelCost.input_usd_per_million, inputMarginNum);
  const outUnits = unitsPer1k(firstModelCost.output_usd_per_million, outputMarginNum);
  const perCall = (report.avg_input_tokens_per_call / 1000) * inUnits
    + (report.avg_output_tokens_per_call / 1000) * outUnits;

  return (
    <p className="text-label text-text-secondary">
      متوسط رسالة فعلي (آخر {report.days} يوم، {report.calls} رد): {report.avg_input_tokens_per_call}{' '}
      دخل + {report.avg_output_tokens_per_call} خرج — بهذي الأرقام تسحب تقريباً{' '}
      <span className="font-medium text-text-primary">{Math.round(perCall).toLocaleString('en-US')} وحدة</span>.
    </p>
  );
}

// ── "الشخصية والسلوك" — نفس نمط معاينة AdminLegal (BlockView)، للاطّلاع فقط اليوم: build_system_
// prompt نص ثابت بالكود لا قالب مخزَّن، فما فيه شي يُحفظ من هنا بعد — انظر operator.py's own note. ──
function AIPersonaCard({ session, previewAction }: { session: AdminSession; previewAction: AdminAction }) {
  const [open, setOpen] = useState(false);
  const [prompt, setPrompt] = useState<string | 'loading' | 'failed'>('loading');
  const [ownerNotes, setOwnerNotes] = useState('');

  function load() {
    setPrompt('loading');
    const qs = ownerNotes ? `?owner_notes=${encodeURIComponent(ownerNotes)}` : '';
    req<{ prompt: string }>(`${previewAction.path}${qs}`, 'GET', undefined, session.access_token)
      .then((body) => setPrompt(body.prompt))
      .catch(() => setPrompt('failed'));
  }

  // eslint-disable-next-line react-hooks/exhaustive-deps -- يُحمَّل مرة عند الفتح، وبزر "معاينة" بعدها
  useEffect(load, [previewAction.path]);

  const block: Block = { type: 'text', data: { md_ar: typeof prompt === 'string' ? prompt : '', md_en: '' } };

  return (
    <>
      <CardTrigger onClick={() => setOpen(true)} title="الشخصية والسلوك"
                   subtitle={<span className="text-label text-text-secondary">النص المرسَل للنموذج — للاطّلاع</span>} />
      <Modal open={open} onClose={() => setOpen(false)} title="الشخصية والسلوك" size="lg"
            subtitle="هذا النص بالضبط يُرسَل للنموذج كشخصية المساعد — للاطّلاع فقط، لا يُعدَّل من هنا بعد.">
        <div className="flex flex-col gap-3">
          <div className="flex flex-wrap items-end gap-2">
            <div className="flex-1">
              <label className="text-label font-medium text-text-secondary" htmlFor="persona-owner-notes">
                جرّب بملاحظات محل حقيقية (اختياري)
              </label>
              <Input id="persona-owner-notes" value={ownerNotes} onChange={(e) => setOwnerNotes(e.target.value)} />
            </div>
            <Button size="sm" variant="outline" onClick={load}>معاينة</Button>
          </div>
          {prompt === 'loading' ? (
            <p className="text-sm text-text-secondary">جارٍ التحميل…</p>
          ) : prompt === 'failed' ? (
            <p role="alert" className="text-danger text-sm">تعذّرت قراءة النص.</p>
          ) : (
            <div className="rounded-card border border-border-subtle bg-surface-0 p-4">
              <BlockView block={block} locale="ar" />
            </div>
          )}
        </div>
      </Modal>
    </>
  );
}

/** الصفوف بترتيب المزوّدين الأول-ظهوراً بالاستجابة (لا ترتيب أبجدي عشوائي)، كل مزوّد مع صفوفه. */
function groupByProvider(rows: SecretRow[]): [string, SecretRow[]][] {
  const order: string[] = [];
  const byProvider = new Map<string, SecretRow[]>();
  for (const row of rows) {
    const provider = PROVIDER_OF[row.key] ?? 'other';
    if (!byProvider.has(provider)) { byProvider.set(provider, []); order.push(provider); }
    byProvider.get(provider)!.push(row);
  }
  return order.map((p) => [p, byProvider.get(p)!]);
}

// البطاقة المصغّرة (المُشغِّل) — تُفتح نافذة فيها النموذج الكامل بدل عرضه مفرودًا بالصفحة.
// بطاقة واحدة لكل الأسرار داخل الفئة الحالية معاً — لا بطاقة منفصلة لكل مفتاح (قرار 2026-09-07):
// كلها "بيانات اتصال" لنفس المزوّد، وفتحها منفصلة كان يُرجع نفس التمرير الطويل بشكل آخر.
function SecretsCard({ providerLabel, rows, session, updateAction, onSaved }: {
  providerLabel: string; rows: SecretRow[]; session: AdminSession; updateAction?: AdminAction;
  onSaved: () => void;
}) {
  const [open, setOpen] = useState(false);
  const configuredCount = rows.filter((r) => r.configured).length;
  if (rows.length === 0) return null;
  return (
    <>
      <CardTrigger onClick={() => setOpen(true)} title="الأسرار"
                   subtitle={<span className="text-label text-text-secondary">
                     {configuredCount}/{rows.length} مُعدّ
                   </span>}
                   trailing={<Badge tone={configuredCount === rows.length ? 'success' : 'neutral'}>
                     {rows.length} {rows.length === 1 ? 'مفتاح' : 'مفاتيح'}
                   </Badge>} />
      <Modal open={open} onClose={() => setOpen(false)} title={`أسرار ${providerLabel}`} size="lg">
        <div className="flex flex-col gap-5">
          {rows.map((row, i) => (
            <div key={row.key}
                className={i > 0 ? 'flex flex-col gap-3 border-t border-border-subtle pt-5' : 'flex flex-col gap-3'}>
              <div className="flex items-center justify-between gap-2">
                <div className="flex flex-col">
                  <span className="font-medium">{row.label}</span>
                  <span dir="ltr" className="text-label font-mono text-text-muted">{row.key}</span>
                  {row.unreadable ? (
                    <span className="text-label text-danger">تعذّر الاتصال بالعنقود — الحالة غير معروفة حالياً</span>
                  ) : row.configured ? (
                    <span dir="ltr" className="text-label text-text-secondary">····{row.last4}</span>
                  ) : null}
                </div>
                {!row.unreadable ? (
                  <Badge tone={row.configured ? 'success' : 'neutral'}>
                    {row.configured ? 'مُعدّ' : 'غير مُعدّ'}
                  </Badge>
                ) : null}
              </div>
              <SecretForm row={row} session={session} updateAction={updateAction}
                         onSaved={onSaved} onClose={() => setOpen(false)} />
            </div>
          ))}
        </div>
      </Modal>
    </>
  );
}

function SecretForm({ row, session, updateAction, onSaved, onClose }: {
  row: SecretRow; session: AdminSession; updateAction?: AdminAction; onSaved: () => void; onClose: () => void;
}) {
  const [value, setValue] = useState('');
  // خطوة تأكيد داخل نفس النافذة — لا نافذة ثانية فوقها (انظر `Modal`'s own scope note: لا يدعم
  // التكديس، فأي "تأكيد" هنا محتوى بديل داخل النافذة المفتوحة أصلاً، لا ConfirmDialog منفصل).
  const [step, setStep] = useState<'edit' | 'confirm'>('edit');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [savedLast4, setSavedLast4] = useState<string | null>(null);
  const [showHelp, setShowHelp] = useState(false);
  // يتفعّل فقط بعد ضغط "توليد" لهذا الصف — يكشف الحقل نصاً صريحاً ريثما تُنسخ القيمة، ويُطفأ
  // فوراً بأي كتابة يدوية أو بعد الحفظ (نفس تنظيف `value` نفسه، ما فيه قيمة قديمة تبقى مكشوفة).
  const [revealed, setRevealed] = useState(false);
  const inputId = `provider-secret-${row.key}`;
  const help = SECRET_HELP[row.key];
  const generatable = GENERATABLE.has(row.key);

  function doGenerate() {
    setValue(generateToken());
    setRevealed(true);
  }

  async function copyValue() {
    try { await navigator.clipboard.writeText(value); } catch { /* المتصفح رفض — تُنسخ يدوياً */ }
  }

  async function doSave() {
    if (!updateAction || !value) return;
    setBusy(true);
    setError('');
    try {
      const out = await req<{ key: string; last4: string; updated_at: string }>(
        updateAction.path.replace('{key}', encodeURIComponent(row.key)),
        'POST', { value }, session.access_token);
      setSavedLast4(out.last4);
      onSaved();
    } catch (err) {
      setError(sentenceFor(err, 'تعذّر حفظ المفتاح.'));
    } finally {
      // THE FIELD CLEARS EITHER WAY — success or failure, nothing typed here survives the
      // request. A failed save is retried by typing again, never by re-submitting what is
      // already gone from this component's own state.
      setValue('');
      setRevealed(false);
      setBusy(false);
      setStep('edit');
    }
  }

  if (step === 'confirm') {
    return (
      <div className="flex flex-col gap-3">
        <p className="font-medium">تحديث "{row.label}"؟</p>
        <p className="text-label text-text-secondary">
          سيُستبدل المفتاح فوراً وتُعاد تشغيل الخدمة التي تقرأه — انقطاع ثوانٍ. القيمة لا يمكن استرجاعها بعد الحفظ.
        </p>
        {error ? <p role="alert" className="text-danger text-sm">{error}</p> : null}
        <div className="flex justify-end gap-2">
          <Button variant="ghost" onClick={() => setStep('edit')} disabled={busy}>رجوع</Button>
          <Button variant="danger" onClick={doSave} disabled={busy}>تأكيد</Button>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-center gap-1.5">
        {help ? (
          <button type="button" onClick={() => setShowHelp((v) => !v)}
                 aria-expanded={showHelp} aria-label={`ايش هذا؟ ومن وين آخذه — ${row.label}`}
                 className="flex items-center gap-1 text-label text-text-secondary hover:text-accent">
            <CircleHelp size={15} /> ايش هذا؟
          </button>
        ) : null}
      </div>
      {showHelp && help ? <p className="text-label text-text-secondary">{help}</p> : null}
      {/* الحالة (····{last4}/تعذّر الاتصال) تظهر على البطاقة نفسها قبل الفتح — لا تُكرَّر هنا. */}
      {row.updated_at ? (
        <p className="text-label text-text-secondary">
          آخر تحديث: {fmtDateTime(row.updated_at)}
          {/* row.updated_by غير معروض عمداً — معرّف مشغّل تقني خام لا اسم، ولا يوجد بالمنصة كلها
             (حتى سجل التدقيق الكامل) أي مكان يحوّله لاسم حقيقي اليوم. عرضه هنا وحده كان سيخلق
             تناقضاً بلا فائدة فعلية لصاحب اللوحة. */}
        </p>
      ) : null}
      {savedLast4 ? (
        <p className="text-label text-success">حُفظ. ينتهي بـ ····{savedLast4}</p>
      ) : null}

      {updateAction ? (
        <form className="flex flex-col gap-1.5 border-t border-border-subtle pt-3 sm:flex-row sm:items-end sm:gap-2"
              onSubmit={(e) => { e.preventDefault(); setStep('confirm'); }}>
          <div className="flex-1">
            <label className="text-label font-medium text-text-secondary" htmlFor={inputId}>القيمة الجديدة</label>
            <div className="flex items-center gap-1.5">
              {/* type="password" + autoComplete="off" — masked as it is typed, never stored
                 anywhere but this one field, and cleared the instant the request settles either
                 way. `revealed` (only true right after "توليد" على قيمة لم تُحفظ بعد) switches
                 it to plain text so the value can actually be read and copied elsewhere. */}
              <Input id={inputId} dir="ltr" type={revealed ? 'text' : 'password'} autoComplete="off"
                    value={value}
                    onChange={(e) => { setValue(e.target.value); setRevealed(false); }} />
              {revealed && value ? (
                <button type="button" onClick={copyValue} aria-label="انسخ القيمة"
                       className="shrink-0 text-text-secondary hover:text-accent">
                  <Copy size={15} />
                </button>
              ) : null}
            </div>
          </div>
          {generatable ? (
            <Button type="button" size="sm" variant="outline" onClick={doGenerate}>توليد</Button>
          ) : null}
          <Button type="submit" size="sm" disabled={!value}>تحديث</Button>
        </form>
      ) : null}

      {error ? <p role="alert" className="text-danger text-sm">{error}</p> : null}
      {savedLast4 ? <Button variant="ghost" onClick={onClose}>إغلاق</Button> : null}
    </div>
  );
}
