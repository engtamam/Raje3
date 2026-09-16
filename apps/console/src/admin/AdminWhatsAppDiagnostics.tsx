/**
 * تشخيص واتساب لمحل — «ليش ما وصلته الرسالة؟» بحث بمعرّف تينانت أو رقم ميتا (phone_number_id)،
 * مبنية يدوياً لأن نتيجتها ليست صفوفاً بشكل ثابت (استجابة `notification-service`'s الداخلية،
 * تُعرَض كما هي). لا زر "أنشئ تذكرة بهذا الدليل" بعد — `ticket-service` لا يملك إجراء إداري
 * لإنشاء تذكرة نيابةً عن عميل اليوم، فالحدّ حقيقي لا قصور بالواجهة.
 *
 * أسفل نتيجة البحث — أدوات رقم واتساب المحل نفسه (platform v0.19.9): سقف الإرسال اليومي، أحداث
 * الويبهوك المشترَكة فعلياً، حالة تحقّق النشاط التجاري، وتعيين رمز التحقّق بخطوتين. الأربعة تعمل
 * على رقم واتساب هذا المحل تحديداً (tenant)، لا هوية المنصة نفسها بـ«المزوّدين الخارجيين ← Meta» —
 * لذلك مكانها هنا، بجانب تشخيص الإرسال لنفس المحل، لا هناك. تحتاج tenant صراحة (لا phone_number_id
 * وحده) لأن المسارات الأربعة تتصل بـMeta عبر رقم المحل المخزَّن لدينا.
 */
import { useEffect, useState } from 'react';
import {
  BadgeCheck, CheckCircle2, Gauge, Lock, ShieldQuestion, XCircle,
} from 'lucide-react';
import { Button } from '../rj-ui/Button';
import { Card } from '../rj-ui/Card';
import { Input } from '../rj-ui/Field';
import { Badge } from '../rj-ui/Badge';
import { EmptyState } from '../rj-ui/EmptyState';
import { ConfirmDialog } from '../rj-ui/ConfirmDialog';
import { fetchCatalog, type AdminAction, type AdminCatalog } from './catalog';
import { req, AdminRefused, type AdminSession } from './api';
import { sentenceFor } from '../api';
import { NoActionAvailable } from './NoActionAvailable';

export interface DeliveryRow {
  id?: string; status?: string; receipt_status?: string; error?: string;
  channel?: string; created?: string; recipient_masked?: string; [key: string]: unknown;
}

export function AdminWhatsAppDiagnostics({ session }: { session: AdminSession }) {
  const [catalog, setCatalog] = useState<AdminCatalog | 'loading' | 'failed'>('loading');

  useEffect(() => {
    let cancelled = false;
    fetchCatalog(session).then((c) => { if (!cancelled) setCatalog(c); })
      .catch(() => { if (!cancelled) setCatalog('failed'); });
    return () => { cancelled = true; };
  }, [session]);

  if (catalog === 'loading') return <p className="p-6 text-sm text-text-secondary">جارٍ التحميل…</p>;
  if (catalog === 'failed') return <p role="alert" className="p-6 text-danger">تعذّرت قراءة كتالوج الإدارة.</p>;

  const allActions = catalog.services.flatMap((s) => s.actions);
  const action = allActions.find((a) => a.id === 'operations.whatsapp_diagnostics');

  if (!action) {
    return <NoActionAvailable catalog={catalog} permissionTitle="لا صلاحية لديك لتشخيص واتساب" />;
  }

  return (
    <DiagnosticsSearch session={session} action={action}
      limitAction={allActions.find((a) => a.id === 'operations.whatsapp_messaging_limit')}
      fieldsAction={allActions.find((a) => a.id === 'operations.whatsapp_subscribed_fields')}
      verifyAction={allActions.find((a) => a.id === 'operations.whatsapp_business_verification')}
      pinAction={allActions.find((a) => a.id === 'operations.whatsapp_set_two_step_pin')} />
  );
}

function DiagnosticsSearch({ session, action, limitAction, fieldsAction, verifyAction, pinAction }: {
  session: AdminSession; action: AdminAction;
  limitAction?: AdminAction; fieldsAction?: AdminAction; verifyAction?: AdminAction; pinAction?: AdminAction;
}) {
  const [tenant, setTenant] = useState('');
  const [phone, setPhone] = useState('');
  const [rows, setRows] = useState<DeliveryRow[] | 'idle' | 'loading' | 'failed'>('idle');
  const [error, setError] = useState('');
  // What the operator actually SEARCHED BY LAST — the four number-management cards below need a
  // real tenant id, never a bare phone_number_id (all four peer routes take tenant only), so they
  // render only after a search that resolved one.
  const [searchedTenant, setSearchedTenant] = useState('');

  async function search() {
    const t = tenant.trim();
    const p = phone.trim();
    if (!t && !p) return;
    setRows('loading');
    setError('');
    setSearchedTenant('');
    const qs = t ? `tenant=${encodeURIComponent(t)}` : `phone_number_id=${encodeURIComponent(p)}`;
    try {
      const body = await req<{ deliveries: DeliveryRow[]; tenant?: string }>(
        `${action.path}?${qs}`, 'GET', undefined, session.access_token,
      );
      setRows(body.deliveries ?? []);
      // Prefer the peer's own resolved tenant (real for a phone-only search) — fall back to what
      // the operator typed when the peer's body carries none.
      setSearchedTenant(body.tenant || t);
    } catch (err) {
      setRows('failed');
      setError(sentenceFor(err, 'تعذّر جلب سجلّ الإرسال.'));
    }
  }

  return (
    <div className="flex flex-col gap-4 p-6">
      <h1 className="text-2xl leading-tight tracking-tight">تشخيص واتساب لمحل</h1>
      <form className="flex flex-col gap-2 sm:flex-row" onSubmit={(e) => { e.preventDefault(); search(); }}>
        <label className="flex-1">
          <span className="text-label font-medium text-text-secondary">معرّف التينانت</span>
          <Input dir="ltr" value={tenant} onChange={(e) => setTenant(e.target.value)} />
        </label>
        <span className="self-center text-text-muted">أو</span>
        <label className="flex-1">
          <span className="text-label font-medium text-text-secondary">رقم ميتا (phone_number_id)</span>
          <Input dir="ltr" value={phone} onChange={(e) => setPhone(e.target.value)} />
        </label>
        <Button type="submit" disabled={!tenant.trim() && !phone.trim()} className="self-end">بحث</Button>
      </form>

      {rows === 'loading' ? <p className="text-sm text-text-secondary">جارٍ البحث…</p> : null}
      {rows === 'failed' ? <p role="alert" className="text-danger text-sm">{error}</p> : null}
      {rows === 'idle' ? (
        <EmptyState title="ابحث بمعرّف تينانت أو رقم ميتا" description="لا نتائج قبل البحث." />
      ) : null}
      {Array.isArray(rows) ? (
        rows.length === 0 ? (
          <EmptyState title="لا رسائل مسجَّلة لهذا المحل" />
        ) : (
          <ul className="flex flex-col gap-2">
            {rows.map((r, i) => (
              <li key={r.id ?? i} className="flex flex-col gap-1 rounded-card border border-border-subtle bg-surface-1 p-3 text-sm">
                <div className="flex items-center justify-between gap-2">
                  <span className="font-medium">{r.recipient_masked ?? '—'}</span>
                  <StatusBadge status={r.status} />
                </div>
                {r.receipt_status ? <span className="text-text-secondary">حالة ميتا: {r.receipt_status}</span> : null}
                {r.error ? <span className="text-danger">{r.error}</span> : null}
                {r.created ? <span className="text-caption text-text-muted">{new Date(r.created).toLocaleString('ar-SA')}</span> : null}
              </li>
            ))}
          </ul>
        )
      ) : null}

      {/* أدوات رقم المحل نفسه عند ميتا — تظهر فقط بعد بحث أعطى tenant حقيقياً، لا أثناء "idle" ولا
         لبحث برقم ميتا وحده بلا تينانت مُستخلَص (نادر: الاستجابة كانت تُعرِّف tenant دوماً هنا). */}
      {searchedTenant && (limitAction || fieldsAction || verifyAction || pinAction) ? (
        <WhatsAppNumberTools session={session} tenant={searchedTenant}
                            limitAction={limitAction} fieldsAction={fieldsAction}
                            verifyAction={verifyAction} pinAction={pinAction} />
      ) : null}
    </div>
  );
}

// ── one shop's own connected WhatsApp number (platform v0.19.9) — four independent reads/one write,
// each answered on its own: an operator may have permission for some and not others, and one card
// failing (e.g. NOT_CONNECTED) must never blank the other three. ──────────────────────────────────
interface MessagingLimitOut {
  ok: boolean; limit: number; tier: string; quality_rating: string;
  display_phone_number: string; verified_name: string; name_status: string; error?: string;
}
interface SubscribedApp { whatsapp_business_api_data?: { id?: string; name?: string }; subscribed_fields?: string[]; }
interface BusinessVerificationOut { business_verification_status: string; status: string; }

const QUALITY_TONE: Record<string, 'success' | 'warning' | 'danger' | 'neutral'> = {
  GREEN: 'success', YELLOW: 'warning', RED: 'danger', NA: 'neutral', UNKNOWN: 'neutral',
};
const NAME_STATUS_META: Record<string, { label: string; tone: 'success' | 'warning' | 'danger' | 'neutral' }> = {
  APPROVED: { label: 'مُعتمَد', tone: 'success' },
  PENDING_REVIEW: { label: 'بانتظار المراجعة', tone: 'warning' },
  DECLINED: { label: 'مرفوض', tone: 'danger' },
  AVAILABLE_WITHOUT_REVIEW: { label: 'متاح بلا مراجعة', tone: 'success' },
  EXPIRED: { label: 'منتهٍ', tone: 'danger' },
  NONE: { label: 'لا اسم مُسجَّل', tone: 'neutral' },
};
const VERIFICATION_META: Record<string, { label: string; tone: 'success' | 'warning' | 'danger' | 'neutral' }> = {
  verified: { label: 'موثَّق', tone: 'success' },
  pending: { label: 'قيد التحقّق', tone: 'warning' },
  rejected: { label: 'مرفوض', tone: 'danger' },
  not_verified: { label: 'غير موثَّق', tone: 'neutral' },
};

// PIN-reason vocabulary — distinct sentences, never one generic "فشل". Matches
// notification-service's own `_classify` + this admin route's 409 mapping exactly.
const PIN_REASON_TEXT: Record<string, string> = {
  WRONG_PIN: 'الرمز غير صحيح — تأكَّد من الرقم الصحيح المسجَّل لدى المحل وحاول مرة أخرى.',
  RATE_LIMITED: 'محاولات كثيرة متتالية — ميتا توقف المحاولات مؤقتاً بعد عشر محاولات كل 72 ساعة. انتظر قبل إعادة المحاولة.',
  TOKEN_REVOKED: 'توكن اتصال هذا المحل بميتا أُلغي — يحتاج المحل إعادة ربط واتساب من جديد قبل أي محاولة أخرى.',
  UNREACHABLE: 'تعذّر الوصول إلى ميتا — تحقّق من الاتصال وحاول لاحقاً.',
  NOT_CONNECTED: 'هذا المحل غير مربوط بواتساب أصلاً — لا رقم أو توكن محفوظ له.',
};
function pinReasonText(reason: string): string {
  if (PIN_REASON_TEXT[reason]) return PIN_REASON_TEXT[reason];
  if (reason.startsWith('META_ERROR')) return `رفض ميتا الطلب: ${reason.slice('META_ERROR'.length).replace(/^:\s*/, '') || 'سبب غير معروف'}`;
  return reason || 'تعذّر تنفيذ الطلب لسبب غير معروف.';
}

function WhatsAppNumberTools({ session, tenant, limitAction, fieldsAction, verifyAction, pinAction }: {
  session: AdminSession; tenant: string;
  limitAction?: AdminAction; fieldsAction?: AdminAction; verifyAction?: AdminAction; pinAction?: AdminAction;
}) {
  return (
    <Card className="flex flex-col gap-3 p-4">
      <div>
        <h2 className="font-medium">رقم واتساب هذا المحل عند ميتا</h2>
        <p className="text-label text-text-secondary" dir="ltr">{tenant}</p>
      </div>
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {limitAction ? <MessagingLimitCard session={session} tenant={tenant} action={limitAction} /> : null}
        {verifyAction ? <BusinessVerificationCard session={session} tenant={tenant} action={verifyAction} /> : null}
        {fieldsAction ? <SubscribedFieldsCard session={session} tenant={tenant} action={fieldsAction} /> : null}
      </div>
      {pinAction ? <TwoStepPinCard session={session} tenant={tenant} action={pinAction} /> : null}
    </Card>
  );
}

function MessagingLimitCard({ session, tenant, action }: { session: AdminSession; tenant: string; action: AdminAction }) {
  const [out, setOut] = useState<MessagingLimitOut | 'loading' | 'failed'>('loading');

  function reload() {
    setOut('loading');
    req<MessagingLimitOut>(`${action.path}?tenant=${encodeURIComponent(tenant)}`, 'GET', undefined, session.access_token)
      .then(setOut).catch(() => setOut('failed'));
  }
  // eslint-disable-next-line react-hooks/exhaustive-deps -- reload is stable per (action.path, tenant)
  useEffect(reload, [action.path, tenant, session.access_token]);

  return (
    <div className="flex flex-col gap-2 rounded-card border border-border-subtle p-3">
      <div className="flex items-center justify-between gap-2">
        <span className="flex items-center gap-1.5 font-medium"><Gauge size={16} /> سقف الإرسال اليومي</span>
        <Button size="sm" variant="ghost" onClick={reload}>تحديث</Button>
      </div>
      {out === 'loading' ? <p className="text-label text-text-secondary">جارٍ التحميل…</p>
       : out === 'failed' ? <p role="alert" className="text-danger text-label">تعذّرت القراءة.</p>
       : !out.ok ? <p className="text-label text-text-secondary">{out.error || 'غير متاح لهذا المحل.'}</p>
       : (
        <div className="flex flex-col gap-1.5 text-label">
          <div className="flex items-center justify-between">
            <span className="text-text-secondary">السقف</span>
            <span className="font-medium">{out.limit < 0 ? 'بلا حد' : out.limit.toLocaleString('en-US')}</span>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-text-secondary">الدرجة</span>
            <span dir="ltr" className="font-mono">{out.tier || '—'}</span>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-text-secondary">تقييم الجودة</span>
            <Badge tone={QUALITY_TONE[out.quality_rating] ?? 'neutral'}>{out.quality_rating || 'غير معروف'}</Badge>
          </div>
        </div>
      )}
    </div>
  );
}

function BusinessVerificationCard({ session, tenant, action }: { session: AdminSession; tenant: string; action: AdminAction }) {
  const [out, setOut] = useState<BusinessVerificationOut | 'loading' | 'failed' | { reason: string }>('loading');

  function reload() {
    setOut('loading');
    req<BusinessVerificationOut>(`${action.path}?tenant=${encodeURIComponent(tenant)}`, 'GET', undefined, session.access_token)
      .then(setOut)
      .catch((err) => setOut({ reason: sentenceFor(err, 'تعذّرت القراءة.') }));
  }
  // eslint-disable-next-line react-hooks/exhaustive-deps -- reload is stable per (action.path, tenant)
  useEffect(reload, [action.path, tenant, session.access_token]);

  const errorReason = out === 'failed' ? 'تعذّرت القراءة.'
    : (out !== 'loading' && 'reason' in out) ? out.reason : null;
  const ready = out !== 'loading' && out !== 'failed' && !errorReason;

  return (
    <div className="flex flex-col gap-2 rounded-card border border-border-subtle p-3">
      <div className="flex items-center justify-between gap-2">
        <span className="flex items-center gap-1.5 font-medium"><BadgeCheck size={16} /> تحقّق النشاط التجاري</span>
        <Button size="sm" variant="ghost" onClick={reload}>تحديث</Button>
      </div>
      {out === 'loading' ? <p className="text-label text-text-secondary">جارٍ التحميل…</p>
       : errorReason ? <p role="alert" className="text-danger text-label">{errorReason}</p>
       : ready ? (
        <div className="flex flex-col gap-1.5 text-label">
          {(() => {
            const v = out as BusinessVerificationOut;
            const meta = VERIFICATION_META[v.business_verification_status] ?? { label: v.business_verification_status || 'غير معروف', tone: 'neutral' as const };
            return (
              <>
                <div className="flex items-center justify-between">
                  <span className="text-text-secondary">التحقّق</span>
                  <Badge tone={meta.tone}>{meta.label}</Badge>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-text-secondary">حالة الحساب</span>
                  <span dir="ltr" className="font-mono">{v.status || '—'}</span>
                </div>
              </>
            );
          })()}
        </div>
      ) : null}
    </div>
  );
}

function SubscribedFieldsCard({ session, tenant, action }: { session: AdminSession; tenant: string; action: AdminAction }) {
  const [apps, setApps] = useState<SubscribedApp[] | 'loading' | 'failed' | { reason: string }>('loading');

  function reload() {
    setApps('loading');
    req<{ apps: SubscribedApp[] }>(`${action.path}?tenant=${encodeURIComponent(tenant)}`, 'GET', undefined, session.access_token)
      .then((body) => setApps(body.apps ?? []))
      .catch((err) => setApps({ reason: sentenceFor(err, 'تعذّرت القراءة.') }));
  }
  // eslint-disable-next-line react-hooks/exhaustive-deps -- reload is stable per (action.path, tenant)
  useEffect(reload, [action.path, tenant, session.access_token]);

  const errorReason = apps === 'failed' ? 'تعذّرت القراءة.'
    : (!Array.isArray(apps) && apps !== 'loading') ? apps.reason : null;

  return (
    <div className="flex flex-col gap-2 rounded-card border border-border-subtle p-3 sm:col-span-2 lg:col-span-1">
      <div className="flex items-center justify-between gap-2">
        <span className="flex items-center gap-1.5 font-medium"><ShieldQuestion size={16} /> أحداث الويبهوك المشترَكة</span>
        <Button size="sm" variant="ghost" onClick={reload}>تحديث</Button>
      </div>
      {/* عرض فقط دائماً — ميتا تضبط الأحداث المشترَكة بمستوى التطبيق (App Dashboard)، لا بمستوى
         الـWABA، فلا يوجد مسار تعديل هنا ولن يُضاف زر تعديل وهمي. */}
      <p className="text-caption text-text-muted">عرض فقط — تعديلها يصير من لوحة مطوّري ميتا (App Dashboard)، لا هنا.</p>
      {apps === 'loading' ? <p className="text-label text-text-secondary">جارٍ التحميل…</p>
       : errorReason ? <p role="alert" className="text-danger text-label">{errorReason}</p>
       : Array.isArray(apps) && apps.length === 0 ? <p className="text-label text-text-secondary">لا تطبيقات مشترِكة حالياً.</p>
       : Array.isArray(apps) ? (
        <ul className="flex flex-col gap-2 text-label">
          {apps.map((a, i) => (
            <li key={a.whatsapp_business_api_data?.id ?? i} className="rounded-md bg-surface-2 p-2">
              <div className="font-medium">{a.whatsapp_business_api_data?.name || a.whatsapp_business_api_data?.id || '—'}</div>
              {a.subscribed_fields && a.subscribed_fields.length ? (
                <div dir="ltr" className="mt-1 flex flex-wrap gap-1">
                  {a.subscribed_fields.map((f) => <Badge key={f} tone="info">{f}</Badge>)}
                </div>
              ) : <span className="text-text-muted">لا أحداث مشترَكة.</span>}
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}

function TwoStepPinCard({ session, tenant, action }: { session: AdminSession; tenant: string; action: AdminAction }) {
  const [open, setOpen] = useState(false);
  const [pin, setPin] = useState('');
  const [confirming, setConfirming] = useState(false);
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<{ ok: boolean; text: string } | null>(null);
  const pinValid = /^[0-9]{6}$/.test(pin);

  function openForm() {
    setPin(''); setResult(null); setOpen(true);
  }

  async function submit() {
    setBusy(true);
    try {
      await req(action.path, 'POST', { tenant, pin }, session.access_token);
      setResult({ ok: true, text: 'تم تعيين الرمز بنجاح — لن يُعرَض مرة أخرى هنا، تماماً كما لن يُخزَّن ظاهراً.' });
    } catch (err) {
      // Distinct reasons from the route's own `reason` field, never a generic "فشل" — matches
      // Meta's own classification (WRONG_PIN/RATE_LIMITED/TOKEN_REVOKED/UNREACHABLE/NOT_CONNECTED).
      const raw = err instanceof AdminRefused ? err.reason : '';
      setResult({ ok: false, text: raw ? pinReasonText(raw) : sentenceFor(err, 'تعذّر تعيين الرمز.') });
    } finally {
      setBusy(false); setConfirming(false); setPin('');
    }
  }

  return (
    <div className="flex flex-col gap-2 rounded-card border border-border-subtle p-3">
      <div className="flex items-center justify-between gap-2">
        <span className="flex items-center gap-1.5 font-medium"><Lock size={16} /> رمز التحقّق بخطوتين</span>
        <Button size="sm" variant="outline" onClick={openForm}>تعيين/تدوير</Button>
      </div>
      <p className="text-caption text-text-muted">
        لا يُعرَض الرمز الحالي أبداً — هذي شاشة تعيين فقط. تعيين رمز جديد يستبدل القديم فوراً عند
        ميتا، ويحتاج رقم المحل مربوطاً فعلياً بواتساب.
      </p>

      <ConfirmDialog open={open} onClose={() => setOpen(false)}
                    onConfirm={confirming ? submit : () => { if (pinValid) setConfirming(true); }}
                    title={confirming ? `تأكيد تعيين رمز جديد لهذا المحل؟` : 'تعيين رمز تحقّق بخطوتين جديد'}
                    body={confirming
                      ? 'هذا تغيير حي عند ميتا الآن — الرمز القديم (إن وُجد) يتوقف فوراً، ولن يُعرَض الرمز الجديد بعد هذه اللحظة أبداً.'
                      : 'أدخل 6 أرقام بالضبط. لا يُحفظ ولا يُعرَض بعد الحفظ — واحد فقط لحظة كتابته هنا.'}
                    confirmLabel={confirming ? 'تأكيد التعيين' : 'التالي'}
                    danger={confirming} busy={busy}>
        {!confirming ? (
          <div className="flex flex-col gap-2">
            <label className="flex flex-col gap-1">
              <span className="text-label font-medium text-text-secondary">الرمز (6 أرقام)</span>
              <Input dir="ltr" inputMode="numeric" maxLength={6} value={pin}
                    onChange={(e) => setPin(e.target.value.replace(/\D/g, '').slice(0, 6))}
                    aria-invalid={pin.length > 0 && !pinValid} />
            </label>
            {pin.length > 0 && !pinValid ? (
              <p role="alert" className="text-danger text-label">يجب أن يكون 6 أرقام بالضبط.</p>
            ) : null}
          </div>
        ) : null}
        {result ? (
          <div className={`flex items-center gap-2 rounded-md p-2 text-label ${result.ok ? 'bg-success-soft text-success-on-soft' : 'bg-danger-soft text-danger-on-soft'}`}>
            {result.ok ? <CheckCircle2 size={16} className="shrink-0" /> : <XCircle size={16} className="shrink-0" />}
            {result.text}
          </div>
        ) : null}
      </ConfirmDialog>
    </div>
  );
}

export function StatusBadge({ status }: { status?: string }) {
  if (!status) return null;
  const tone = status === 'sent' || status === 'delivered' ? 'success'
    : status === 'failed' || status === 'suppressed' ? 'danger' : 'neutral';
  return <Badge tone={tone}>{status}</Badge>;
}
