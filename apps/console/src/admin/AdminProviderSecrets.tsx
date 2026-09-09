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
import { ChevronLeft, CircleHelp, Copy, CreditCard, MessageCircle, Sparkles } from 'lucide-react';
import { Button } from '../rj-ui/Button';
import { Field, Input } from '../rj-ui/Field';
import { Badge } from '../rj-ui/Badge';
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
  META_APP_ID: 'meta', META_APP_SECRET: 'meta', WHATSAPP_WEBHOOK_VERIFY_TOKEN: 'meta',
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
  // "الإدارة" — النموذج والسلوك، عبر خدمة الذكاء الاصطناعي مباشرة (platform.config)، لا عبر
  // secrets-admin: هذي قيم سياسة تُقرأ صراحة (RuntimeConfig)، لا أسرار مختومة بمفتاح.
  const configGetAction = findAction('whatsapp_assistant.operator_config');
  const configSetAction = findAction('whatsapp_assistant.set_operator_config');
  const configClearAction = findAction('whatsapp_assistant.clear_operator_config');
  const personaPreviewAction = findAction('whatsapp_assistant.persona_preview');
  // "المحاسبة" — القراءات/الجدولة عبر مسار تسعير مستقل عمداً (POST /pricing/schedule)، لا
  // set_operator_config: تعديل سعر لا يسري فوراً أبداً — انظر operator.py's own note.
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
              ) : pricingReportAction && pricingPendingAction ? (
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
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
              <SecretsCard providerLabel={(PROVIDER_META[active ?? ''] ?? PROVIDER_META.other).label}
                          rows={activeRows} session={session} updateAction={updateAction}
                          onSaved={() => listAction && reload(listAction)} />
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

// ── "الإدارة" — نموذج الذكاء الاصطناعي وسلوكه (app/runtime_policy.py، حيّ بلا إعادة نشر) ──────────
const CONFIG_KEY_META: Record<string, { label: string; help: string }> = {
  ASSISTANT_MODEL_NAME: { label: 'اسم النموذج',
    help: 'اسم نموذج Vertex AI بالضبط (مثال: gemini-2.5-flash) — تغييره يسري على المحادثة التالية فوراً.' },
  SOFT_DECLINE_THRESHOLD: { label: 'عتبة التوقف عن الاقتراح',
    help: 'عدد مرات رفض العميل لاقتراح قبل ما يتوقف المساعد عن اقتراح أي شي عليه (بلا تصعيد لموظف).' },
  MAX_CAROUSEL_CARDS: { label: 'أقصى بطاقات بالعرض',
    help: 'أقصى عدد بطاقات خدمات/باقات يعرضها المساعد بردّ واحد.' },
  MAX_REPLY_TOKENS: { label: 'أقصى طول رد',
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
                        setAction={setAction} clearAction={clearAction} onSaved={reload} />
            ))}
          </div>
        )}
      </Modal>
    </>
  );
}

function ConfigRow({ session, k, currentValue, setAction, clearAction, onSaved }: {
  session: AdminSession; k: string; currentValue: unknown;
  setAction?: AdminAction; clearAction?: AdminAction; onSaved: () => void;
}) {
  const [value, setValue] = useState(String(currentValue ?? ''));
  // خطوة تأكيد داخل نفس النافذة — لا نافذة ثانية فوق الأولى. `Modal` هنا (بخلاف ConfirmDialog) لا
  // يدعم التكديس (انظر تعليقه الخاص)، فأي تأكيد يصير محتوى بديل داخل نفس النافذة المفتوحة أصلاً.
  const [step, setStep] = useState<'edit' | 'confirm-set' | 'confirm-clear'>('edit');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const meta = CONFIG_KEY_META[k];

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
        <Input id={`config-${k}`} dir="ltr" value={value} onChange={(e) => setValue(e.target.value)}
              className="max-w-xs" />
        {setAction ? (
          <Button size="sm" disabled={!value} onClick={() => setStep('confirm-set')}>تحديث</Button>
        ) : null}
        {clearAction ? (
          <Button size="sm" variant="outline" onClick={() => setStep('confirm-clear')}>
            استرجاع الافتراضي
          </Button>
        ) : null}
      </div>
      {error ? <p role="alert" className="text-danger text-sm">{error}</p> : null}
    </div>
  );
}

// ── "المحاسبة" — حاسبة تسعير الذكاء الاصطناعي: سعر جوجل الحقيقي + هامش = سعرنا، على استهلاك
// حقيقي (COST_LEDGER عبر pricing/report) أو افتراض يدوي، وتطبيق يمرّ دائماً عبر جدولة مؤجَّلة —
// انظر core/pricing_schedule.py's own docstring: تعديل سعر لا يسري فوراً أبداً. ──────────────────
interface UsageReport {
  days: number; calls: number; conversations: number; input_tokens: number; output_tokens: number;
  avg_input_tokens_per_call: number; avg_output_tokens_per_call: number;
  avg_calls_per_conversation: number; truncated: boolean;
}
interface PendingChange { key: string; value: string | number | boolean; effective_at: number; scheduled_by: string; scheduled_at: number; }

const PRICING_KEY_LABEL: Record<string, string> = {
  PRICING_STRATEGY: 'طريقة التسعير',
  PRICING_USAGE_HALALAS_PER_1K_TOKENS: 'هللات لكل 1000 وحدة',
  PRICING_USAGE_HALALAS_PER_CONVERSATION: 'هللات لكل محادثة',
  PRICING_TIER_BASE_HALALAS: 'سعر الباقة الأساسي',
  PRICING_TIER_INCLUDED_CONVERSATIONS: 'محادثات مشمولة بالباقة',
  PRICING_TIER_OVERAGE_HALALAS_PER_CONVERSATION: 'هللات لكل محادثة زيادة',
  PRICING_ADDON_FLAT_HALALAS: 'سعر إضافة ثابتة',
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
  session: AdminSession; reportAction: AdminAction; pendingAction: AdminAction;
  scheduleAction?: AdminAction; cancelAction?: AdminAction;
}) {
  const [report, setReport] = useState<UsageReport | 'loading' | 'failed'>('loading');
  const [pending, setPending] = useState<PendingChange[] | 'loading' | 'failed'>('loading');
  const [days, setDays] = useState(30);

  // ── مصدر عدد الرسائل الشهري للتوقع — حقيقي (report.calls) أو يدوي، قبل وجود استهلاك فعلي.
  const [monthlySource, setMonthlySource] = useState<'real' | 'manual'>('real');
  const [manualMonthlyCalls, setManualMonthlyCalls] = useState('1000');

  // ── الأسعار المرجعية (جوجل) — بالريال مباشرة، لا عملة ثانية بالنظام أصلاً. ندخلها نحن يدوياً
  // ونحدّثها وقت ما تتغيّر (جوجل ما توفر API لأسعارها) — مين يحدّثها يحوّلها بنفسه وقتها. الوحدة
  // قابلة للتبديل (لكل 1000 / لكل مليون) لراحة المقارنة مع صفحة تسعير جوجل نفسها.
  const [unit, setUnit] = useState<'1k' | '1m'>('1m');
  const [googleInputSar, setGoogleInputSar] = useState('1.13');
  const [googleOutputSar, setGoogleOutputSar] = useState('9.38');

  // THE TOGGLE MUST RESCALE THE NUMBERS, NOT JUST RELABEL THEM. `unit` also picks `divisor` below
  // for the actual cost math — so switching it while leaving googleInputSar/googleOutputSar
  // untouched silently changes what the SAME typed number MEANS (1.13 "per 1000 tokens" is 1000×
  // Google's real price if it was actually typed as "per million"), not just how it displays. A
  // real bug, found from a screenshot: identical inputs, real cost off by ~1000× between
  // the two tabs. Converting here keeps the number always meaning the same real price no matter
  // which unit it is being viewed/typed in.
  function changeUnit(next: '1k' | '1m') {
    if (next === unit) return;
    const factor = next === '1k' ? 1 / 1000 : 1000; // 1m→1k: ÷1000. 1k→1m: ×1000.
    const rescale = (v: string) => {
      const n = Number(v);
      if (!Number.isFinite(n)) return v;
      // Rounded to 8 decimals and trailing zeros trimmed — plain `n * factor` leaves float noise
      // like 0.009380000000000001 sitting in the field the owner is about to read and type over.
      return String(Math.round(n * factor * 1e8) / 1e8);
    };
    setGoogleInputSar((v) => rescale(v));
    setGoogleOutputSar((v) => rescale(v));
    setUnit(next);
  }

  // ── متوسط التوكنات — يدوي أو من استهلاك حقيقي (report). ──────────────────────────────────────
  const [tokenSource, setTokenSource] = useState<'system' | 'manual'>('system');
  const [manualAvgInput, setManualAvgInput] = useState('300');
  const [manualAvgOutput, setManualAvgOutput] = useState('150');

  const [multiplier, setMultiplier] = useState('3');
  const [effectiveInDays, setEffectiveInDays] = useState('15');
  const [scheduling, setScheduling] = useState(false);
  const [scheduleError, setScheduleError] = useState('');
  const [scheduleDone, setScheduleDone] = useState(false);

  function reload() {
    setReport('loading');
    req<UsageReport>(`${reportAction.path}?days=${days}`, 'GET', undefined, session.access_token)
      .then(setReport).catch(() => setReport('failed'));
    setPending('loading');
    req<{ pending: PendingChange[] }>(pendingAction.path, 'GET', undefined, session.access_token)
      .then((body) => setPending(body.pending)).catch(() => setPending('failed'));
  }

  // eslint-disable-next-line react-hooks/exhaustive-deps -- reload يُستدعى صراحة عند تغيّر days أيضاً
  useEffect(reload, [reportAction.path, pendingAction.path, session.access_token, days]);

  const hasReport = typeof report === 'object';
  const avgInput = tokenSource === 'system' && hasReport
    ? report.avg_input_tokens_per_call : Number(manualAvgInput) || 0;
  const avgOutput = tokenSource === 'system' && hasReport
    ? report.avg_output_tokens_per_call : Number(manualAvgOutput) || 0;
  const divisor = unit === '1m' ? 1_000_000 : 1_000;
  const costPerCallSar = (avgInput / divisor) * (Number(googleInputSar) || 0)
    + (avgOutput / divisor) * (Number(googleOutputSar) || 0);
  const m = Number(multiplier) || 0;
  const suggestedPriceSar = costPerCallSar * m;
  const suggestedHalalas = suggestedPriceSar * 100;
  const totalTokens = avgInput + avgOutput;
  const suggestedHalalasPer1k = totalTokens > 0 ? (suggestedHalalas / totalTokens) * 1000 : 0;
  const marginPercent = m > 0 ? (1 - 1 / m) * 100 : 0;

  // ── التوقع الشهري — يستخدم الاستهلاك الحقيقي (report.calls) مُقاساً لشهر كامل، بغض النظر عن
  // نافذة القراءة الفعلية (`days`) — لا يفترض حجماً، يمدّد الحجم المُلاحَظ فعلياً. قبل أي استهلاك
  // حقيقي (لا محل بعد يستخدم البوت فعلياً) الرقم صفر بصدق — «يدوي» يعطي رقماً مفترَضاً بدل
  // انتظار بيانات لا وجود لها بعد، مفصول تماماً عن مصدر متوسط التوكنات (tokenSource) أعلاه — هذا
  // عدد الرسائل، ذاك متوسط توكناتها، سؤالان مختلفان.
  const monthlyScale = hasReport && report.days > 0 ? 30 / report.days : 0;
  const monthlyCalls = monthlySource === 'manual'
    ? Number(manualMonthlyCalls) || 0
    : hasReport ? Math.round(report.calls * monthlyScale) : 0;
  const monthlyRevenueSar = (monthlyCalls * suggestedHalalas) / 100;
  const monthlyGoogleCostSar = monthlyCalls * costPerCallSar;

  async function doSchedule() {
    if (!scheduleAction) return;
    setScheduling(true); setScheduleError(''); setScheduleDone(false);
    const days_ = Number(effectiveInDays) || 0;
    try {
      // اثنان لا واحد — الطريقة (usage_based) والمعدّل نفسه، بنفس تاريخ السريان، عشان تبقى
      // متّسقتين لحظة ما تُطبَّقان معاً بالتِك (لا يصير معدّل جديد على طريقة قديمة أو العكس).
      await req(scheduleAction.path, 'POST',
        { key: 'PRICING_STRATEGY', value: 'usage_based', effective_in_days: days_ },
        session.access_token);
      await req(scheduleAction.path, 'POST',
        { key: 'PRICING_USAGE_HALALAS_PER_1K_TOKENS', value: Math.round(suggestedHalalasPer1k),
         effective_in_days: days_ },
        session.access_token);
      setScheduleDone(true);
      reload();
    } catch (err) {
      setScheduleError(sentenceFor(err, 'تعذّرت جدولة التعديل.'));
    } finally { setScheduling(false); }
  }

  async function doCancel(key: string) {
    if (!cancelAction) return;
    await req(cancelAction.path.replace('{key}', encodeURIComponent(key)), 'DELETE',
      undefined, session.access_token).catch(() => {});
    reload();
  }

  return (
    <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
      {/* ── المدخلات ─────────────────────────────────────────────────────────────────────── */}
      <section className="flex flex-col gap-4 rounded-card border border-border-subtle bg-surface-1 p-4">
        <h3 className="font-medium">المدخلات</h3>

        <div className="flex flex-col gap-2">
          <div className="flex items-center justify-between gap-2">
            <span className="text-label font-medium text-text-secondary">سعر جوجل (ريال)</span>
            <Segmented value={unit} onChange={(v) => changeUnit(v as '1k' | '1m')}
                      options={[{ value: '1k', label: 'لكل 1000 توكن' }, { value: '1m', label: 'لكل مليون توكن' }]} />
          </div>
          <p className="text-label text-text-secondary">
            جوجل يسعّر بالدولار — حوّلها بنفسك للريال وقت ما تحدّث الرقم من صفحة تسعيرهم.
          </p>
          <div className="grid grid-cols-2 gap-2">
            <Field label="سعر الدخل (Input)" htmlFor="calc-google-in">
              <Input id="calc-google-in" dir="ltr" type="number" step="0.01" value={googleInputSar}
                    onChange={(e) => setGoogleInputSar(e.target.value)} />
            </Field>
            <Field label="سعر الخرج (Output)" htmlFor="calc-google-out">
              <Input id="calc-google-out" dir="ltr" type="number" step="0.01" value={googleOutputSar}
                    onChange={(e) => setGoogleOutputSar(e.target.value)} />
            </Field>
          </div>
        </div>

        <div className="flex flex-col gap-2 border-t border-border-subtle pt-3">
          <span className="text-label font-medium text-text-secondary">متوسط التوكنات لكل رسالة</span>
          <Segmented value={tokenSource} onChange={(v) => setTokenSource(v as 'system' | 'manual')}
                    options={[{ value: 'system', label: 'من قيمة النظام' }, { value: 'manual', label: 'يدوي' }]} />
          {tokenSource === 'manual' ? (
            <div className="grid grid-cols-2 gap-2">
              <Field label="دخل (Input)" htmlFor="calc-avg-in">
                <Input id="calc-avg-in" dir="ltr" type="number" value={manualAvgInput}
                      onChange={(e) => setManualAvgInput(e.target.value)} />
              </Field>
              <Field label="خرج (Output)" htmlFor="calc-avg-out">
                <Input id="calc-avg-out" dir="ltr" type="number" value={manualAvgOutput}
                      onChange={(e) => setManualAvgOutput(e.target.value)} />
              </Field>
            </div>
          ) : report === 'loading' ? (
            <p className="text-label text-text-secondary">جارٍ التحميل…</p>
          ) : report === 'failed' ? (
            <p role="alert" className="text-label text-danger">تعذّرت قراءة الاستهلاك الحقيقي.</p>
          ) : (
            <p className="text-label text-text-secondary">
              {avgInput} دخل + {avgOutput} خرج (متوسط آخر {report.days} يوم، {report.calls} رسالة فعلية)
            </p>
          )}
        </div>

        <Field label="المضاعف (هامش الربح)" htmlFor="calc-multiplier">
          <Input id="calc-multiplier" dir="ltr" type="number" step="0.1" value={multiplier}
                onChange={(e) => setMultiplier(e.target.value)} className="max-w-[8rem]" />
        </Field>
      </section>

      {/* ── النتيجة والتطبيق ─────────────────────────────────────────────────────────────── */}
      <section className="flex flex-col gap-4 rounded-card border border-border-subtle bg-surface-1 p-4">
        <h3 className="font-medium">النتيجة المقترحة</h3>
        <div className="grid grid-cols-2 gap-3">
          <div className="rounded-card bg-surface-2 p-3">
            <p className="text-label text-text-secondary">السعر المقترح لكل 1000 وحدة</p>
            <p className="text-lg font-semibold tabular-nums">{suggestedHalalasPer1k.toFixed(1)} هللة</p>
          </div>
          <div className="rounded-card bg-surface-2 p-3">
            <p className="text-label text-text-secondary">تكلفتنا الحقيقية عند جوجل / رسالة</p>
            <p className="text-lg font-semibold tabular-nums">{(costPerCallSar * 100).toFixed(2)} هللة</p>
          </div>
          <div className="rounded-card bg-surface-2 p-3">
            <p className="text-label text-text-secondary">سعرنا المقترح / رسالة</p>
            <p className="text-lg font-semibold tabular-nums">{suggestedHalalas.toFixed(2)} هللة</p>
          </div>
          <div className="rounded-card bg-surface-2 p-3">
            <p className="text-label text-text-secondary">هامش الربح</p>
            <p className="text-lg font-semibold tabular-nums">{marginPercent.toFixed(0)}٪</p>
          </div>
        </div>

        <div className="rounded-card border border-dashed border-border-subtle p-3">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <p className="text-label font-medium text-text-secondary">
              {monthlySource === 'manual' ? 'توقع شهري (على عدد رسائل تفترضه)'
                                          : 'توقع شهري (على استهلاك حقيقي، مُمدَّد لشهر كامل)'}
            </p>
            {/* لا محل بعد يستخدم البوت فعلياً يعني «حقيقي» يعطي صفراً صادقاً — «يدوي» يفترض
               عدداً بدل انتظار بيانات لا وجود لها بعد، لتجربة الحاسبة نفسها. */}
            <Segmented size="sm" value={monthlySource} onChange={(v) => setMonthlySource(v as 'real' | 'manual')}
                      options={[{ value: 'real', label: 'حقيقي' }, { value: 'manual', label: 'يدوي' }]} />
          </div>
          {monthlySource === 'manual' ? (
            <Field label="عدد الرسائل المفترض شهرياً" htmlFor="calc-manual-monthly-calls" className="mt-2 max-w-[10rem]">
              <Input id="calc-manual-monthly-calls" dir="ltr" type="number" min={0} value={manualMonthlyCalls}
                    onChange={(e) => setManualMonthlyCalls(e.target.value)} />
            </Field>
          ) : null}
          {monthlySource === 'manual' || hasReport ? (
            <div className="mt-2 flex flex-col gap-1 text-sm">
              <p>عدد الرسائل المتوقع: <span className="font-semibold tabular-nums">{monthlyCalls.toLocaleString('en-US')}</span></p>
              <p>الإيراد المتوقع: <span className="font-semibold tabular-nums">{monthlyRevenueSar.toFixed(0)} ﷼</span></p>
              <p>تكلفة جوجل الحقيقية المتوقعة: <span className="font-semibold tabular-nums">{monthlyGoogleCostSar.toFixed(0)} ﷼</span></p>
              <p>الربح المتوقع: <span className="font-semibold tabular-nums">{(monthlyRevenueSar - monthlyGoogleCostSar).toFixed(0)} ﷼</span></p>
              {/* التذكير اللي يفسّر لماذا "عدد الرسائل" رقم قرار لا رقم معلومة فقط — نموذج أغلى
                 يقلّل الرسائل المتوقعة عند نفس الهامش، فيحتاج تعديل الهامش لا تجاهل الأثر. */}
              <p className="text-label text-text-secondary">
                نموذج أغلى بنفس الهامش يعني سعراً أعلى للعميل، وغالباً رسائل أقل — إن قلّ الهامش
                المطلوب، عدّله بدل ما تتجاهل التأثير على العدد.
              </p>
            </div>
          ) : (
            <p className="mt-2 text-sm text-text-secondary">بانتظار الاستهلاك الحقيقي…</p>
          )}
        </div>

        {scheduleAction ? (
          <div className="flex flex-col gap-2 border-t border-border-subtle pt-3">
            <div className="flex flex-wrap items-end gap-2">
              <Field label="يسري بعد (أيام)" htmlFor="calc-effective-days">
                <Input id="calc-effective-days" dir="ltr" type="number" min={1} value={effectiveInDays}
                      onChange={(e) => setEffectiveInDays(e.target.value)} className="max-w-[8rem]" />
              </Field>
              <Button onClick={doSchedule} disabled={scheduling || !multiplier}>
                {scheduling ? 'جارٍ الجدولة…' : 'جدولة التعديل'}
              </Button>
            </div>
            <p className="text-label text-text-secondary">
              لا يسري فوراً — بعد {effectiveInDays || '؟'} يوم من الآن، عشان تقدر تُعلم المحلات قبلها.
            </p>
            {scheduleError ? <p role="alert" className="text-danger text-sm">{scheduleError}</p> : null}
            {scheduleDone ? <p className="text-success text-sm">تمّت الجدولة.</p> : null}
          </div>
        ) : null}
      </section>

      {/* ── الاستهلاك الحقيقي ────────────────────────────────────────────────────────────── */}
      <section className="flex flex-col gap-3 rounded-card border border-border-subtle bg-surface-1 p-4">
        <div className="flex items-center justify-between gap-2">
          <h3 className="font-medium">الاستهلاك الحقيقي</h3>
          <Segmented value={String(days)} onChange={(v) => setDays(Number(v))}
                    options={[{ value: '7', label: '7 أيام' }, { value: '30', label: '30 يوم' }, { value: '90', label: '90 يوم' }]} />
        </div>
        {report === 'loading' ? (
          <p className="text-sm text-text-secondary">جارٍ التحميل…</p>
        ) : report === 'failed' ? (
          <p role="alert" className="text-danger text-sm">تعذّرت القراءة.</p>
        ) : (
          <div className="grid grid-cols-2 gap-3 text-sm sm:grid-cols-3">
            <p>الرسائل: <span className="font-semibold tabular-nums">{report.calls.toLocaleString('en-US')}</span></p>
            <p>المحادثات: <span className="font-semibold tabular-nums">{report.conversations.toLocaleString('en-US')}</span></p>
            <p>رسالة/محادثة: <span className="font-semibold tabular-nums">{report.avg_calls_per_conversation}</span></p>
            <p>متوسط دخل: <span className="font-semibold tabular-nums">{report.avg_input_tokens_per_call}</span></p>
            <p>متوسط خرج: <span className="font-semibold tabular-nums">{report.avg_output_tokens_per_call}</span></p>
            {report.truncated ? (
              <p className="text-label text-danger">الأرقام حد أدنى — الاستهلاك الفعلي أعلى.</p>
            ) : null}
          </div>
        )}
      </section>

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
    </div>
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
