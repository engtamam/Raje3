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
import { Input } from '../rj-ui/Field';
import { Badge } from '../rj-ui/Badge';
import { Segmented } from '../rj-ui/Segmented';
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
  // الاسم التقني الدقيق كما هو — هذي لوحة إدارة داخلية (تمام وفريقه)، لا شاشة يقرأها صاحب محل،
  // فلا حاجة لتلطيف الاسم أو تبسيطه (قرار 2026-09-07، يلغي التسمية الأطول السابقة).
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
              return { value: provider, label: `${meta.label} (${configuredCount}/${providerRows.length})` };
            })}
          />
          {active === 'assistant_ai' ? (
            <div className="flex flex-col gap-4">
              {/* المسار — واحد فقط اليوم، لكن ظاهر ومُختار من الآن. مسار ثانٍ مستقبلاً (محرّك ذكاء
                 ثانٍ، أو خدمة عملاء المنصة) يضاف هنا بلا إعادة تصميم — انظر تعليق `AI_PATHS` أعلاه. */}
              <div className="flex flex-col gap-1">
                <span className="text-label font-medium text-text-secondary">المسار</span>
                <Segmented value={aiPath} onChange={setAiPath}
                          options={AI_PATHS.map((p) => ({ value: p.value, label: p.label }))} />
              </div>
              <Segmented value={aiTab} onChange={(v) => setAiTab(v as 'admin' | 'calc')}
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
              ) : (
                // مساحة الحاسبة (تسعير الذكاء الاصطناعي، هامش الربح، التوقعات المالية) — مشروع لاحق،
                // تصميمه نوقش لكن ما بُني بعد. مكانها هنا محجوز عمداً بدل ما تُقحَم مستقبلاً.
                <p className="rounded-card border border-dashed border-border-subtle p-6 text-sm text-text-secondary">
                  الحاسبة المالية للذكاء الاصطناعي — قريباً.
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

  const count = typeof config === 'object' ? Object.keys(config).length : 0;

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
            {Object.entries(config).map(([key, value]) => (
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
          آخر تحديث: {row.updated_at}{row.updated_by ? ` — ${row.updated_by}` : ''}
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
