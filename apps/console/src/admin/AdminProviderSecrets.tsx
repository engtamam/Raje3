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
import { useEffect, useState } from 'react';
import { CircleHelp, ChevronDown, Copy, CreditCard, MessageCircle, Sparkles } from 'lucide-react';
import { Button } from '../rj-ui/Button';
import { Input } from '../rj-ui/Field';
import { Badge } from '../rj-ui/Badge';
import { EmptyState } from '../rj-ui/EmptyState';
import { ConfirmDialog } from '../rj-ui/ConfirmDialog';
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
  PAYMENT_API_KEY: 'payment', PAYMENT_EXTRA_SECRET: 'payment',
  PAYMENT_PUBLISHABLE_KEY: 'payment',
};
const PROVIDER_META: Record<string, { label: string; icon: typeof MessageCircle }> = {
  meta: { label: 'Meta (واتساب)', icon: MessageCircle },
  // اسم مقصود التحديد لا التعميم — "ذكاء واتساب المحلات" لا "الذكاء الاصطناعي" وحدها، عشان لو
  // انضاف ذكاء اصطناعي ثاني لغرض مختلف مستقبلاً (خدمة عملاء المنصة مثلاً) يكون له بطاقته الخاصة
  // بلا لبس مع هذا.
  assistant_ai: { label: 'ذكاء واتساب المحلات', icon: Sparkles },
  payment: { label: 'بوابة الدفع', icon: CreditCard },
  other: { label: 'أخرى', icon: CircleHelp },
};

export function AdminProviderSecrets({ session, initialOpenProvider }: {
  session: AdminSession;
  /** رابط تحويل مباشر من شاشة ثانية (مثل "بوابات الدفع" بالمالية) — يفتح بطاقة هذا المزوّد فور
   *  الوصول، بدل ما يوصل الشخص شاشة مطوية عليه يفتحها بنفسه من جديد. */
  initialOpenProvider?: string;
}) {
  const [catalog, setCatalog] = useState<AdminCatalog | 'loading' | 'failed'>('loading');
  const [rows, setRows] = useState<SecretRow[] | 'loading' | 'failed'>('loading');
  // بطاقة مفتوحة واحدة كحد أقصى — نفس منطق أي قائمة قابلة للطي، أوضح من فتح الكل دفعة واحدة.
  const [openProvider, setOpenProvider] = useState<string | null>(initialOpenProvider ?? null);

  useEffect(() => {
    let cancelled = false;
    fetchCatalog(session).then((c) => { if (!cancelled) setCatalog(c); })
      .catch(() => { if (!cancelled) setCatalog('failed'); });
    return () => { cancelled = true; };
  }, [session]);

  const listAction = catalog !== 'loading' && catalog !== 'failed'
    ? catalog.services.flatMap((s) => s.actions).find((a) => a.id === 'secrets.list')
    : undefined;
  const updateAction = catalog !== 'loading' && catalog !== 'failed'
    ? catalog.services.flatMap((s) => s.actions).find((a) => a.id === 'secrets.update')
    : undefined;

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

  return (
    <div className="flex flex-col gap-6 p-6">
      <h1 className="text-2xl leading-tight tracking-tight">مفاتيح المزوّدين الخارجيين</h1>
      <p className="text-sm text-text-secondary">
        تحديث مفتاح يعيد تشغيل الخدمة التي تقرأه — انقطاع ثوانٍ. القيمة لا تُعرض هنا أبداً، لا
        عند الحفظ ولا بعده — آخر أربعة أحرف فقط، كتأكيد أنك حفظت المفتاح الصحيح.
      </p>
      {rows === 'loading' ? (
        <p className="text-sm text-text-secondary">جارٍ التحميل…</p>
      ) : rows === 'failed' ? (
        <p role="alert" className="text-danger text-sm">تعذّرت قراءة قائمة المفاتيح.</p>
      ) : (
        <div className="flex flex-col gap-3">
          {groupByProvider(rows).map(([provider, providerRows]) => {
            const meta = PROVIDER_META[provider] ?? PROVIDER_META.other;
            const Icon = meta.icon;
            const open = openProvider === provider;
            const configuredCount = providerRows.filter((r) => r.configured).length;
            return (
              <section key={provider} className="rounded-card border border-border-subtle bg-surface-1">
                <button type="button" onClick={() => setOpenProvider(open ? null : provider)}
                       aria-expanded={open}
                       className="flex w-full items-center gap-3 p-4 text-start">
                  <span className="inline-flex rounded-lg bg-accent-soft p-2 text-accent-on-soft">
                    <Icon size={18} />
                  </span>
                  <span className="flex-1">
                    <span className="block font-medium">{meta.label}</span>
                    <span className="text-label text-text-secondary">
                      {configuredCount} / {providerRows.length} مُعدّ
                    </span>
                  </span>
                  <ChevronDown size={18}
                              className={`text-text-secondary transition-transform ${open ? 'rotate-180' : ''}`} />
                </button>
                {open ? (
                  <div className="flex flex-col gap-3 border-t border-border-subtle p-4 pt-3">
                    {providerRows.map((row) => (
                      <SecretRowCard key={row.key} row={row} session={session}
                                     updateAction={updateAction}
                                     onSaved={() => listAction && reload(listAction)} />
                    ))}
                  </div>
                ) : null}
              </section>
            );
          })}
        </div>
      )}
    </div>
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

function SecretRowCard({ row, session, updateAction, onSaved }: {
  row: SecretRow; session: AdminSession; updateAction?: AdminAction; onSaved: () => void;
}) {
  const [value, setValue] = useState('');
  const [arm, setArm] = useState(false);
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
      setArm(false);
    }
  }

  return (
    <section className="flex flex-col gap-3 rounded-card border border-border-subtle bg-surface-1 p-4">
      <div className="flex items-center justify-between gap-2">
        <div className="flex flex-col">
          <div className="flex items-center gap-1.5">
            <span className="font-medium">{row.label}</span>
            {help ? (
              <button type="button" onClick={() => setShowHelp((v) => !v)}
                     aria-expanded={showHelp} aria-label={`ايش هذا؟ ومن وين آخذه — ${row.label}`}
                     className="text-text-secondary hover:text-accent">
                <CircleHelp size={15} />
              </button>
            ) : null}
          </div>
          {/* اسم المتغيّر البرمجي تحت الاسم — يفيد لو احتجت تراجعه بمكان ثانٍ (لوحة Meta، ملف env محلي...) */}
          <span dir="ltr" className="text-label font-mono text-text-muted">{row.key}</span>
          {showHelp && help ? (
            <p className="mt-1 max-w-md text-label text-text-secondary">{help}</p>
          ) : null}
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
              onSubmit={(e) => { e.preventDefault(); setArm(true); }}>
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

      <ConfirmDialog open={arm} onClose={() => setArm(false)} onConfirm={doSave} busy={busy}
                    danger title={`تحديث "${row.label}"؟`}
                    body="سيُستبدل المفتاح فوراً وتُعاد تشغيل الخدمة التي تقرأه — انقطاع ثوانٍ. القيمة لا يمكن استرجاعها بعد الحفظ." />
    </section>
  );
}
