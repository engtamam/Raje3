/**
 * قوالب واتساب — حالة كل قالب واضحة دائماً، لا "عذر صامت". السبب المباشر لهذي الشاشة: نظام
 * الإرسال (notification-service) يرفض أي رسالة أولى بلا قالب معتمد من ميتا — رفض صحيح ومقصود،
 * لكن كان بلا أي واجهة تعرضه، فيقرأ كخطأ غامض بدل حالة مفهومة. هذي الشاشة تجعل "قيد الإعداد /
 * معتمد / مرفوض / متوقف / مُعطَّل" مرئية دائماً، بألوانها، مع سبب الرفض إن وُجد — لا شي مخفي.
 *
 * التسجيل يصير هنا (نص القالب عندنا، الخدمة لا تعرف معناه — انظر whatsapp_templates.py's own
 * docstring)، والإرسال للمراجعة زر منفصل — القالب يبقى "قيد الإعداد" بدون إرسال فعلي لميتا حتى
 * تضغط "أرسل للمراجعة" صراحة، بلا أي مفاجأة. "قيد الإعداد" لا "قيد المراجعة" عمداً: الخادم لا
 * يفرّق بين "لم يُرسَل قط" و"اتعدّل بعد رفضٍ ولسه ما أُعيد إرساله" — كلاهما نفس status=pending
 * بلا حقل يميّزهما (انظر تعليق displayMeta أدناه)، فأي تسمية تدّعي "أُرسل" ليست مضمونة الصحة.
 *
 * النطاق (tenant) الفعلي لكل قالب هنا هو منشأة لوحة الإدارة المحجوزة (`_platform`) — نفس المنشأة
 * اللي identity-service المفروض يقرأ منها إعداد OTP_NOTIFY_TENANT وقت إرسال رمز التحقق، بحيث
 * القالب اللي تسجّله وتعتمده هنا هو نفسه اللي الإرسال الحقيقي يجده — لا تعارض منشآت.
 */
import { Fragment, useEffect, useState } from 'react';
import {
  FileText, Clock, CheckCircle2, XCircle, PauseCircle, Ban, Plus, Send, RefreshCw, FlaskConical,
  Eye,
} from 'lucide-react';
import { Button } from '../rj-ui/Button';
import { Card } from '../rj-ui/Card';
import { Field, Input, Select, Textarea } from '../rj-ui/Field';
import { Badge } from '../rj-ui/Badge';
import { KpiCard } from '../rj-ui/KpiCard';
import { Segmented } from '../rj-ui/Segmented';
import { Drawer } from '../rj-ui/Drawer';
import { Toggle } from '../rj-ui/Toggle';
import { ConfirmDialog } from '../rj-ui/ConfirmDialog';
import { EmptyState } from '../rj-ui/EmptyState';
import { Modal } from '../rj-ui/Modal';
import { WhatsAppTemplatePreview, type FlowJson } from '../rj-ui/WhatsAppPreview';
import { fetchCatalog, type AdminAction, type AdminCatalog } from './catalog';
import { AdminRefused, req, type AdminSession } from './api';
import { sentenceFor } from '../api';
import { NoActionAvailable } from './NoActionAvailable';

type TemplateStatus = 'pending' | 'approved' | 'rejected' | 'paused' | 'disabled';

interface FlowButton {
  flow_name?: string;
  text?: string;
}

interface Template {
  id: string;
  tenant: string;
  name: string;
  language: string;
  category: string;
  body: string;
  variables: string[];
  examples: string[];
  status: TemplateStatus;
  provider_template_id: string;
  rejection_reason: string;
  flow_button?: FlowButton;
  created: string;
  updated: string;
}

const STATUS_META: Record<TemplateStatus, { label: string; tone: 'warning' | 'success' | 'danger' | 'neutral'; icon: typeof Clock }> = {
  pending: { label: 'قيد الإعداد', tone: 'warning', icon: Clock },
  approved: { label: 'معتمد', tone: 'success', icon: CheckCircle2 },
  rejected: { label: 'مرفوض', tone: 'danger', icon: XCircle },
  paused: { label: 'متوقف مؤقتاً', tone: 'warning', icon: PauseCircle },
  disabled: { label: 'مُعطَّل', tone: 'danger', icon: Ban },
};

// جُرِّب هنا فعلياً تمييز pending إلى "مسوّدة" (بلا provider_template_id) مقابل "قيد المراجعة"
// (معه) — وتبيّن غلطاً: register() بـcore/whatsapp_templates.py يُبقي provider_template_id كما هو
// عند تعديل قالب مُرسَل سابقاً (لا يصفّره)، فقالب اتعدّل بعد رفضٍ يحمل status=pending WITH
// provider_template_id — نفس شكل قالب فعلاً قيد المراجعة عند ميتا، بلا أي حقل يفرّق بينهما. وسم
// أحدهما "مسوّدة" والآخر "قيد المراجعة" كان يخمّن يقيناً لا نملكه. "قيد الإعداد" وحدها — صحيحة
// بكل الحالات الثلاث (جديد لم يُرسَل / اتعدّل بعد رفض / فعلاً عند ميتا) بلا ادّعاء زائد.
function displayMeta(t: Template) {
  return STATUS_META[t.status] ?? STATUS_META.pending;
}

/**
 * يعزل كل رمز {{متغيّر}} بـ<bdi dir="ltr"> بدل فرض اتجاه على الفقرة كاملة. فرق حاسم: dir="ltr"
 * على الفقرة كلها يقلب ترتيب المقاطع العربية المتعددة حول الرمز (جُرِّب حياً هنا وانقلبت الجملة
 * كاملة — "صالح لمدة 5 دقائق {{code}} رمز التحقق هو" بدل ترتيبها الصحيح)، بينما <bdi> يعزل الرمز
 * فقط عن سياق bidi المحيط به (يمنع انعكاس شكل الأقواس) ويترك بقية الجملة العربية بترتيبها الطبيعي
 * تماماً — لا تأثير خارج حدود الرمز نفسه.
 */
function renderBidiSafe(text: string) {
  const parts = text.split(/(\{\{[^{}]+\}\})/g);
  return parts.map((part, i) => (
    /^\{\{[^{}]+\}\}$/.test(part)
      ? <bdi key={i} dir="ltr">{part}</bdi>
      : <Fragment key={i}>{part}</Fragment>
  ));
}

const CATEGORY_LABEL: Record<string, string> = {
  UTILITY: 'خدمية', MARKETING: 'تسويقية', AUTHENTICATION: 'تحقّق هوية',
};

const FILTERS: { value: TemplateStatus | 'all'; label: string }[] = [
  { value: 'all', label: 'الكل' },
  { value: 'pending', label: 'قيد الإعداد' },
  { value: 'approved', label: 'معتمد' },
  { value: 'rejected', label: 'مرفوض' },
];

export function AdminWhatsAppTemplates({ session }: { session: AdminSession }) {
  const [catalog, setCatalog] = useState<AdminCatalog | 'loading' | 'failed'>('loading');
  const [templates, setTemplates] = useState<Template[] | 'loading' | 'failed'>('loading');
  const [filter, setFilter] = useState<TemplateStatus | 'all'>('all');
  const [creating, setCreating] = useState(false);

  useEffect(() => {
    fetchCatalog(session).then(setCatalog).catch(() => setCatalog('failed'));
  }, [session]);

  const listAction = catalog !== 'loading' && catalog !== 'failed'
    ? findAction(catalog, 'notifications.list_wa_templates') : undefined;
  const registerAction = catalog !== 'loading' && catalog !== 'failed'
    ? findAction(catalog, 'notifications.register_wa_template') : undefined;
  const submitAction = catalog !== 'loading' && catalog !== 'failed'
    ? findAction(catalog, 'notifications.submit_wa_template') : undefined;
  const testSendAction = catalog !== 'loading' && catalog !== 'failed'
    ? findAction(catalog, 'notifications.test_send_wa') : undefined;
  const seedRenewalFlowAction = catalog !== 'loading' && catalog !== 'failed'
    ? findAction(catalog, 'operations.seed_subscription_renewal_flow') : undefined;
  const flowJsonAction = catalog !== 'loading' && catalog !== 'failed'
    ? findAction(catalog, 'operations.whatsapp_flow_json') : undefined;

  function reload() {
    if (!listAction) return;
    setTemplates('loading');
    req<{ templates: Template[] }>(listAction.path, 'GET', undefined, session.access_token)
      .then((r) => setTemplates(r.templates))
      .catch(() => setTemplates('failed'));
  }

  useEffect(() => {
    if (listAction) reload();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [listAction]);

  if (catalog === 'loading') return <p className="p-6 text-sm text-text-secondary">جارٍ التحميل…</p>;
  if (catalog === 'failed') return <p role="alert" className="p-6 text-danger">تعذّرت قراءة كتالوج الإدارة.</p>;
  if (!listAction) {
    return <NoActionAvailable catalog={catalog} permissionTitle="هذه الشاشة ليست ضمن صلاحياتك" />;
  }

  const shown = Array.isArray(templates)
    ? templates.filter((t) => filter === 'all' || t.status === filter)
    : [];
  const counts = Array.isArray(templates)
    ? templates.reduce<Record<string, number>>((acc, t) => { acc[t.status] = (acc[t.status] ?? 0) + 1; return acc; }, {})
    : {};

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="font-medium">قوالب واتساب</h2>
          <p className="mt-1 max-w-xl text-label text-text-secondary">
            أي رسالة نبدأها نحن (مثل رمز تحقق التسجيل) تحتاج قالباً معتمَداً من ميتا مسبقاً — بدونه
            الإرسال يُرفض. حالة كل قالب هنا واضحة دائماً، وسبب الرفض إن وُجد، بلا أي غموض.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" onClick={reload} className="gap-2">
            <RefreshCw size={14} /> تحديث
          </Button>
          {registerAction ? (
            <Button size="sm" onClick={() => setCreating(true)} className="gap-2">
              <Plus size={16} /> قالب جديد
            </Button>
          ) : null}
        </div>
      </div>

      {/* KpiCard summary by status — same tones as STATUS_META (Badge), so a colour reads the
         same whether it is on the card here, the filter strip below, or a template's own badge. */}
      {Array.isArray(templates) && templates.length > 0 ? (
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
          {(Object.keys(STATUS_META) as TemplateStatus[]).map((status) => {
            const meta = STATUS_META[status];
            const Icon = meta.icon;
            return (
              <KpiCard key={status} icon={<Icon size={18} />} label={meta.label}
                      value={counts[status] ?? 0} tone={(counts[status] ?? 0) > 0 ? meta.tone : 'neutral'}
                      testId={`kpi-wa-tpl-${status}`} />
            );
          })}
        </div>
      ) : null}

      {testSendAction ? (
        <TestSendPanel session={session} action={testSendAction}
                      templates={Array.isArray(templates) ? templates : []} />
      ) : null}

      {seedRenewalFlowAction ? (
        <SeedRenewalFlowPanel session={session} action={seedRenewalFlowAction} />
      ) : null}

      {Array.isArray(templates) && templates.length > 0 ? (
        <Segmented value={filter} onChange={(v) => setFilter(v as TemplateStatus | 'all')}
                  options={FILTERS.map((f) => ({
                    value: f.value,
                    label: f.value === 'all' ? `${f.label} (${templates.length})` : `${f.label} (${counts[f.value] ?? 0})`,
                  }))} />
      ) : null}

      {templates === 'loading' ? (
        <p className="text-sm text-text-secondary">جارٍ التحميل…</p>
      ) : templates === 'failed' ? (
        <p role="alert" className="text-danger text-sm">تعذّرت قراءة القوالب.</p>
      ) : templates.length === 0 ? (
        <EmptyState title="لا قوالب مسجَّلة بعد" description='ابدأ بـ"قالب جديد" — رمز التحقق يحتاج واحداً باسم "auth_otp" ليعمل.' />
      ) : shown.length === 0 ? (
        <p className="text-sm text-text-secondary">لا قوالب بهذي الحالة.</p>
      ) : (
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          {shown.map((t) => (
            <TemplateCard key={t.id} template={t} session={session} submitAction={submitAction}
                         registerAction={registerAction} flowJsonAction={flowJsonAction} onChanged={reload} />
          ))}
        </div>
      )}

      {registerAction ? (
        <RegisterDrawer session={session} action={registerAction} flowJsonAction={flowJsonAction} open={creating}
                       onClose={() => setCreating(false)}
                       onCreated={() => { setCreating(false); reload(); }} />
      ) : null}
    </div>
  );
}

function findAction(catalog: AdminCatalog, id: string): AdminAction | undefined {
  return catalog.services.flatMap((s) => s.actions).find((a) => a.id === id);
}

/** The one injection point `WhatsAppTemplatePreview` needs — built once per action, not per
 *  render, so `useEffect` deps in the preview engine that reference it stay stable. */
function makeFlowJsonFetcher(session: AdminSession, action?: AdminAction) {
  if (!action) return undefined;
  return (flowName: string) =>
    req<FlowJson>(`${action.path}?name=${encodeURIComponent(flowName)}`, 'GET', undefined, session.access_token);
}

function TemplateCard({ template, session, submitAction, registerAction, flowJsonAction, onChanged }: {
  template: Template; session: AdminSession; submitAction?: AdminAction; registerAction?: AdminAction;
  flowJsonAction?: AdminAction; onChanged: () => void;
}) {
  const [busy, setBusy] = useState(false);
  const [arm, setArm] = useState(false);
  const [editing, setEditing] = useState(false);
  const [previewing, setPreviewing] = useState(false);
  const [error, setError] = useState('');
  const meta = displayMeta(template);
  const Icon = meta.icon;

  async function doSubmit() {
    if (!submitAction) return;
    setBusy(true);
    setError('');
    try {
      await req(
        submitAction.path.replace('{name}', encodeURIComponent(template.name))
                         .replace('{language}', encodeURIComponent(template.language)),
        'POST', undefined, session.access_token);
      onChanged();
    } catch (err) {
      setError(sentenceFor(err, 'تعذّر الإرسال للمراجعة.'));
    } finally {
      setBusy(false);
      setArm(false);
    }
  }

  return (
    <Card className="flex flex-col gap-3 p-4">
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-start gap-2.5">
          <span className="mt-0.5 inline-flex rounded-lg border border-border-subtle bg-surface-1 p-2 text-text-secondary">
            <FileText size={16} />
          </span>
          <div>
            <p dir="ltr" className="font-mono text-sm font-semibold">{template.name}</p>
            <p className="text-label text-text-secondary">
              {CATEGORY_LABEL[template.category] ?? template.category} · <span dir="ltr">{template.language}</span>
            </p>
          </div>
        </div>
        <Badge tone={meta.tone} className="shrink-0 gap-1"><Icon size={12} /> {meta.label}</Badge>
      </div>

      {template.body ? (
        <p className="whitespace-pre-wrap rounded-lg border border-border-subtle bg-surface-1 p-3 text-sm text-text-secondary">
          {renderBidiSafe(template.body)}
        </p>
      ) : null}

      {template.variables.length > 0 ? (
        <p className="text-label text-text-secondary">
          {renderBidiSafe(`المتغيّرات: ${template.variables.map((v) => `{{${v}}}`).join('  ')}`)}
        </p>
      ) : null}

      {template.flow_button?.flow_name ? (
        <p className="text-label text-text-secondary">
          زر يفتح فلو تفاعلي: <span dir="ltr" className="font-mono">{template.flow_button.flow_name}</span>
          {template.flow_button.text ? ` — "${template.flow_button.text}"` : ''}
        </p>
      ) : null}

      {template.status === 'rejected' || template.status === 'paused' || template.status === 'disabled' ? (
        template.rejection_reason ? (
          <p role="alert" className="rounded-lg border border-danger/30 bg-danger/5 p-2.5 text-label text-danger">
            سبب {meta.label}: {template.rejection_reason}
          </p>
        ) : null
      ) : null}

      {error ? <p role="alert" className="text-danger text-sm">{error}</p> : null}

      {/* الزر يظهر بأي حالة "قيد الإعداد" بلا استثناء — لا شرط على provider_template_id. كان
         الشرط القديم يخفي الزر لأي قالب سبق إرساله، فقالب اتعدّل بعد رفضٍ (يحمل status=pending
         WITH provider_template_id، انظر تعليق displayMeta أعلاه) يعلَق بلا طريقة لإرساله من
         جديد — نفس مشكلة التسمية بالضبط، لكن بالوظيفة هذي المرة لا العرض فقط. */}
      {template.status === 'pending' && template.provider_template_id ? (
        <p className="text-label text-text-secondary">
          له نسخة سابقة عند ميتا — الإرسال الآن يحدّثها بالمحتوى الحالي.
        </p>
      ) : null}
      <div className="flex flex-wrap items-center gap-2">
        {template.status === 'pending' && submitAction ? (
          <Button size="sm" onClick={() => setArm(true)} disabled={busy} className="w-fit gap-2">
            <Send size={14} /> أرسل للمراجعة
          </Button>
        ) : null}
        {registerAction ? (
          <Button size="sm" variant="outline" onClick={() => setEditing(true)}>تعديل</Button>
        ) : null}
        <Button size="sm" variant="ghost" onClick={() => setPreviewing(true)} className="gap-2">
          <Eye size={14} /> معاينة على واتساب
        </Button>
      </div>

      <ConfirmDialog open={arm} onClose={() => setArm(false)} onConfirm={doSubmit} busy={busy}
                    title={`إرسال "${template.name}" لمراجعة ميتا؟`}
                    body="لا يمكن التراجع بعد الإرسال — المراجعة تصير عند ميتا نفسها، قد تأخذ ساعات لأيام." />

      {registerAction ? (
        <RegisterDrawer session={session} action={registerAction} flowJsonAction={flowJsonAction} open={editing}
                       initial={template} onClose={() => setEditing(false)}
                       onCreated={() => { setEditing(false); onChanged(); }} />
      ) : null}

      {previewing ? (
        <Modal open={previewing} onClose={() => setPreviewing(false)} title="معاينة على واتساب"
              subtitle="بالضبط ما يستلمه العميل — الفلو الحقيقي، لا نسخة مقلَّدة.">
          <WhatsAppTemplatePreview
            data={{
              body: template.body,
              examples: template.examples,
              flowButton: template.flow_button?.flow_name
                ? { flowName: template.flow_button.flow_name, text: template.flow_button.text || 'فتح' }
                : undefined,
            }}
            fetchFlowJson={makeFlowJsonFetcher(session, flowJsonAction)}
          />
        </Modal>
      ) : null}
    </Card>
  );
}

/**
 * إرسال تجريبي — يتجاوز خط الإرسال العادي عمداً (نفس تجاوز /whatsapp/register و/whatsapp/status
 * لخط الإرسال العادي) عشان يجاوب سؤال "هل الاتصال شغّال فعلاً" بلا انتظار WHATSAPP_CHAIN. رسالة
 * واحدة، بلا طابور، بلا تكرار — تُسجَّل بالتدقيق تلقائياً من طرف الخادم نفسه.
 *
 * شكل الطلب/الرد مطابق تماماً لما شحنته base-services-de (v0.18.17، بُني من نفس تصميم الطلب
 * المُرسَل لها): {to, phone_number_id, mode, body|template_name+language+variables} —
 * 200 {ok, message_id}, 409 {ok:false, reason:"NOT_CONNECTED"}, 502 {ok:false,
 * reason:"SEND_FAILED"}. req() بـapi.ts يرمي AdminRefused على أي رد غير 2xx حاملاً `.reason` —
 * لذا NOT_CONNECTED/SEND_FAILED تُمسَك بـcatch، لا بقراءة جسم رد ناجح؛ لا حالة "نجح لكنه فشل".
 */
function TestSendPanel({ session, action, templates }: {
  session: AdminSession; action: AdminAction; templates: Template[];
}) {
  const [open, setOpen] = useState(false);
  const [mode, setMode] = useState<'text' | 'template'>('text');
  const [to, setTo] = useState('');
  const [phoneNumberId, setPhoneNumberId] = useState('');
  const [message, setMessage] = useState('');
  const [templateKey, setTemplateKey] = useState('');
  const [values, setValues] = useState<Record<string, string>>({});
  const [arm, setArm] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [result, setResult] = useState<{ ok: boolean; messageId?: string; reason?: string } | null>(null);

  const selected = templates.find((t) => `${t.name}::${t.language}` === templateKey);
  // قالب غير معتمد يُمنَع من عندنا، لا يُترَك لميتا ترفضه — الاعتماد على رفض ميتا وحده ثبت غير
  // كافٍ حياً: طلب فعلي بقالب "قيد الإعداد" رجع {ok:true} بلا أي استدعاء حقيقي لميتا أصلاً
  // (مسار مشكوك فيه قيد التحقيق مع الفريق الآخر) — منع الإرسال هنا طبقة دفاع لا تعتمد على صحة
  // ذلك المسار إطلاقاً.
  const canSend = to.trim().length > 0 && phoneNumberId.trim().length > 0
    && (mode === 'text' ? message.trim().length > 0 : !!selected && selected.status === 'approved');

  function onSelectTemplate(key: string) {
    setTemplateKey(key);
    const t = templates.find((x) => `${x.name}::${x.language}` === key);
    setValues(Object.fromEntries((t?.variables ?? []).map((v) => [v, ''])));
  }

  async function doSend() {
    if (!canSend) return;
    setBusy(true);
    setError('');
    setResult(null);
    try {
      const body = mode === 'text'
        ? { to, phone_number_id: phoneNumberId, mode: 'text', body: message }
        : { to, phone_number_id: phoneNumberId, mode: 'template', template_name: selected!.name,
           language: selected!.language,
           variables: (selected!.variables ?? []).map((v) => values[v] ?? '') };
      const out = await req<{ ok: boolean; message_id?: string }>(
        action.path, 'POST', body, session.access_token);
      setResult({ ok: true, messageId: out.message_id });
    } catch (err) {
      if (err instanceof AdminRefused && err.reason) {
        // 409 NOT_CONNECTED / 502 SEND_FAILED — refusals the server names explicitly, not a
        // generic network/programming error. Shown as a result, not `error`, same tone as success.
        setResult({ ok: false, reason: err.reason });
      } else {
        setError(sentenceFor(err, 'تعذّر الإرسال.'));
      }
    } finally {
      setBusy(false);
      setArm(false);
    }
  }

  return (
    <Card className="flex flex-col gap-3 p-4">
      <button type="button" onClick={() => setOpen((v) => !v)} aria-expanded={open}
             className="flex w-full items-center gap-2.5 text-start">
        <span className="inline-flex rounded-lg border border-border-subtle bg-surface-1 p-2 text-text-secondary">
          <FlaskConical size={16} />
        </span>
        <span className="flex-1">
          <span className="block font-medium">إرسال تجريبي</span>
          <span className="text-label text-text-secondary">
            رسالة واحدة، مباشرة عبر ميتا — يتجاوز إعدادات خط الإرسال العادي، للتأكد إن الاتصال شغّال
          </span>
        </span>
      </button>

      {open ? (
        <div className="flex flex-col gap-3 border-t border-border-subtle pt-3">
          <Segmented value={mode} onChange={(v) => { setMode(v as 'text' | 'template'); setResult(null); }}
                    options={[
                      { value: 'text', label: 'نص حر (يحتاج نافذة 24 ساعة مفتوحة)' },
                      { value: 'template', label: 'بقالب معتمد' },
                    ]} />

          <Field label="رقم المستقبل (بالصيغة الدولية، بدون +)" required htmlFor="wa-test-to">
            <Input id="wa-test-to" dir="ltr" value={to} onChange={(e) => setTo(e.target.value)}
                  placeholder="9665xxxxxxxx" />
          </Field>

          <Field label="معرّف رقم هاتف المنصة (Phone Number ID)" required htmlFor="wa-test-phone-id"
                hint="نفس WHATSAPP_PHONE_NUMBER_ID المُعدّ ببطاقة ميتا بشاشة مفاتيح المزوّدين.">
            <Input id="wa-test-phone-id" dir="ltr" value={phoneNumberId}
                  onChange={(e) => setPhoneNumberId(e.target.value)} />
          </Field>

          {mode === 'text' ? (
            <Field label="نص الرسالة" required htmlFor="wa-test-msg">
              <Textarea id="wa-test-msg" rows={3} value={message}
                       onChange={(e) => setMessage(e.target.value)} />
            </Field>
          ) : (
            <>
              <Field label="القالب" required htmlFor="wa-test-tpl">
                <Select id="wa-test-tpl" value={templateKey} onChange={(e) => onSelectTemplate(e.target.value)}>
                  <option value="">اختر قالباً…</option>
                  {templates.map((t) => (
                    <option key={`${t.name}::${t.language}`} value={`${t.name}::${t.language}`}>
                      {t.name} ({t.language}) — {STATUS_META[t.status]?.label ?? t.status}
                    </option>
                  ))}
                </Select>
              </Field>
              {selected && selected.status !== 'approved' ? (
                <p role="alert" className="text-label text-danger">
                  هذا القالب ليس معتمداً بعد — الإرسال معطَّل حتى يُعتمد من ميتا.
                </p>
              ) : null}
              {selected?.variables.map((v) => (
                <Field key={v} label={`{{${v}}}`} htmlFor={`wa-test-var-${v}`}>
                  <Input id={`wa-test-var-${v}`} value={values[v] ?? ''}
                        onChange={(e) => setValues((prev) => ({ ...prev, [v]: e.target.value }))} />
                </Field>
              ))}
            </>
          )}

          {result ? (
            result.ok ? (
              <p className="text-label text-success">أُرسلت. message_id: <span dir="ltr">{result.messageId}</span></p>
            ) : (
              <p role="alert" className="text-label text-danger">
                لم تُرسل — {result.reason === 'NOT_CONNECTED' ? 'الرقم غير مربوط بعد'
                  : result.reason === 'SEND_FAILED' ? 'رفضته ميتا (تحقق من النافذة الزمنية أو اعتماد القالب)'
                  : result.reason}
              </p>
            )
          ) : null}
          {error ? <p role="alert" className="text-danger text-sm">{error}</p> : null}

          <Button size="sm" onClick={() => setArm(true)} disabled={!canSend || busy} className="w-fit gap-2">
            <Send size={14} /> إرسال
          </Button>
        </div>
      ) : null}

      <ConfirmDialog open={arm} onClose={() => setArm(false)} onConfirm={doSend} busy={busy}
                    title="إرسال رسالة تجريبية حقيقية؟"
                    body={`ستصل رقم ${to} فعلياً الآن، مباشرة عبر ميتا.`} />
    </Card>
  );
}

/**
 * فلو التجديد — منفصل تماماً عن تسجيل القوالب أعلاه، لكنه يقود إلى نفس المكان: قالب
 * "subscription_renewal_flow" يحتاج فلواً حقيقياً بالاسم "subscription_renewal" موجوداً على
 * حساب المنصة قبل ما نقدر نرسله للمراجعة أصلاً. يدوي بالكامل ومرة واحدة بالعمر كله — لا يتكرر
 * لكل محل (خلافاً لفلوهات الحجز والتقييم)، ولا يصير تلقائياً عند أي تثبيت (قرار صاحب المنصة،
 * 2026-09-10): لا اتصال بميتا وقت التثبيت أصلاً، ولا شيء يصل ميتا بدون ضغطة زر هنا.
 */
function SeedRenewalFlowPanel({ session, action }: { session: AdminSession; action: AdminAction }) {
  const [arm, setArm] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [result, setResult] = useState<
    { ok: true; flowId: string; alreadySeeded: boolean } | { ok: false; reason: string } | null
  >(null);

  async function doSeed() {
    setBusy(true);
    setError('');
    setResult(null);
    try {
      const out = await req<{ ok: boolean; flow_id?: string; already_seeded?: boolean }>(
        action.path, 'POST', undefined, session.access_token);
      setResult({ ok: true, flowId: out.flow_id ?? '', alreadySeeded: !!out.already_seeded });
    } catch (err) {
      if (err instanceof AdminRefused && err.reason) {
        setResult({ ok: false, reason: err.reason });
      } else {
        setError(sentenceFor(err, 'تعذّر تجهيز الفلو.'));
      }
    } finally {
      setBusy(false);
      setArm(false);
    }
  }

  return (
    <Card className="flex flex-col gap-3 p-4">
      <div className="flex items-start gap-2.5">
        <span className="inline-flex rounded-lg border border-border-subtle bg-surface-1 p-2 text-text-secondary">
          <FlaskConical size={16} />
        </span>
        <div className="flex-1">
          <p className="font-medium">فلو تجديد الاشتراك</p>
          <p className="text-label text-text-secondary">
            شاشة تفاعلية على واتساب لتجديد اشتراك المحل — مرة واحدة بالعمر كله، على حساب المنصة.
            آمن لإعادة الضغط: لو موجودة أصلاً، تقول ذلك ولا تُنشئ نسخة ثانية.
          </p>
        </div>
      </div>

      {result ? (
        result.ok ? (
          <p className="text-label text-success">
            {result.alreadySeeded ? 'موجودة أصلاً — لم يُنشأ شيء جديد.' : 'تم تجهيزها الآن.'}{' '}
            <span dir="ltr" className="font-mono">{result.flowId}</span>
          </p>
        ) : (
          <p role="alert" className="text-label text-danger">تعذّر التجهيز — {result.reason}</p>
        )
      ) : null}
      {error ? <p role="alert" className="text-danger text-sm">{error}</p> : null}

      <Button size="sm" variant="outline" onClick={() => setArm(true)} disabled={busy}
             className="w-fit gap-2">
        <Send size={14} /> تجهيز الفلو
      </Button>

      <ConfirmDialog open={arm} onClose={() => setArm(false)} onConfirm={doSeed} busy={busy}
                    title="تجهيز فلو تجديد الاشتراك على ميتا؟"
                    body="ينشئ شاشة تفاعلية حقيقية على حساب المنصة عند ميتا — مرة واحدة فقط." />
    </Card>
  );
}

/**
 * التسجيل والتعديل نفس النموذج، نفس المسار. لكن الحفظ وحده لا يُرسل شيئاً لميتا — register() بـ
 * core/whatsapp_templates.py يكتب المحتوى الجديد محلياً فقط ويعيد الحالة "قيد الإعداد"، والإرسال
 * الفعلي زر منفصل ("أرسل للمراجعة") يضغطه المستخدم صراحة، بلا مفاجأة — بالضبط نفس مبدأ التسجيل
 * الأول. بوضع التعديل، الاسم واللغة مقفلان: هما مفتاح هوية القالب عند ميتا، وتغييرهما يسجّل قالباً
 * جديداً منفصلاً بدل تعديل هذا.
 */
function RegisterDrawer({ session, action, flowJsonAction, open, initial, onClose, onCreated }: {
  session: AdminSession; action: AdminAction; flowJsonAction?: AdminAction; open: boolean; initial?: Template;
  onClose: () => void; onCreated: () => void;
}) {
  const editingExisting = !!initial;
  const [name, setName] = useState(initial?.name ?? '');
  const [language, setLanguage] = useState(initial?.language ?? 'ar');
  const [category, setCategory] = useState(initial?.category ?? 'AUTHENTICATION');
  const [body, setBody] = useState(initial?.body ?? '');
  const [variablesText, setVariablesText] = useState((initial?.variables ?? []).join(', '));
  const [flowEnabled, setFlowEnabled] = useState(!!initial?.flow_button?.flow_name);
  const [flowName, setFlowName] = useState(initial?.flow_button?.flow_name ?? '');
  const [flowButtonText, setFlowButtonText] = useState(initial?.flow_button?.text ?? '');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  // كل فتحة للمحرّر تبدأ من قيم ذلك القالب بالضبط — لا قيم متسربة من فتحة سابقة لقالب آخر.
  useEffect(() => {
    if (!open) return;
    setName(initial?.name ?? ''); setLanguage(initial?.language ?? 'ar');
    setCategory(initial?.category ?? 'AUTHENTICATION'); setBody(initial?.body ?? '');
    setVariablesText((initial?.variables ?? []).join(', ')); setError('');
    setFlowEnabled(!!initial?.flow_button?.flow_name);
    setFlowName(initial?.flow_button?.flow_name ?? '');
    setFlowButtonText(initial?.flow_button?.text ?? '');
    // eslint-disable-next-line react-hooks/exhaustive-deps -- re-seed only when the drawer (re)opens
  }, [open]);

  const variables = variablesText.split(',').map((v) => v.trim()).filter(Boolean);
  // في وضع التعديل الاسم مقفل — أي قيمة موجودة أصلاً صالحة بحكم أنها مسجّلة فعلاً، حتى لو لا
  // تطابق قاعدة التسجيل الجديدة (اسم قديم بنقطة، مثلاً)؛ إعادة فرض القاعدة هنا كانت تقفل زر
  // الحفظ نهائياً على أي قالب موجود مسبقاً لا يطابقها — عكس الهدف كاملاً.
  const canSave = (editingExisting || /^[a-z0-9_]+$/.test(name)) && body.trim().length > 0
    && (!flowEnabled || flowName.trim().length > 0);

  async function save() {
    if (!canSave) return;
    setBusy(true);
    setError('');
    try {
      // flow_button فاضي (لا flow_name فيه) يعني "بلا زر فلو" للخادم (whatsapp_templates.py's
      // own register()) — نرسل {} صراحة لا كائناً جزئياً، حتى إلغاء التفعيل يمسح زراً سابقاً
      // بدل أن يُبقيه معلَّقاً.
      const flow_button = flowEnabled && flowName.trim()
        ? { flow_name: flowName.trim(), ...(flowButtonText.trim() ? { text: flowButtonText.trim() } : {}) }
        : {};
      await req(action.path, 'POST',
        { name, language, category, body, variables, flow_button }, session.access_token);
      if (!editingExisting) {
        setName(''); setBody(''); setVariablesText(''); setCategory('AUTHENTICATION'); setLanguage('ar');
        setFlowEnabled(false); setFlowName(''); setFlowButtonText('');
      }
      onCreated();
    } catch (err) {
      setError(sentenceFor(err, 'تعذّر حفظ القالب.'));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Drawer open={open} onClose={onClose} title={editingExisting ? `تعديل "${initial!.name}"` : 'قالب واتساب جديد'}
           subtitle={editingExisting
             ? 'الحفظ وحده لا يُرسل شيئاً لميتا — يحفظ المحتوى الجديد بحالة "قيد الإعداد" فقط. اضغط "أرسل للمراجعة" بعده لإرسال هذا المحتوى فعلياً.'
             : 'النص من عندنا — الخدمة تخزّنه بلا فهم معناه، وترسله لميتا فقط عند "إرسال للمراجعة".'}
           footer={
             <>
               <Button type="button" variant="ghost" onClick={onClose}>إلغاء</Button>
               <Button type="button" disabled={!canSave || busy} onClick={save}>
                 {busy ? 'جارٍ الحفظ…' : editingExisting ? 'حفظ التعديل' : 'حفظ كمسوّدة'}
               </Button>
             </>
           }>
      <div className="flex flex-col gap-4">
        <Field label="الاسم (بالإنجليزية، أحرف صغيرة وأرقام و_ فقط)" required htmlFor="wa-tpl-name">
          <Input id="wa-tpl-name" dir="ltr" value={name} disabled={editingExisting}
                onChange={(e) => setName(e.target.value.toLowerCase())} placeholder="auth_otp" />
        </Field>
        <div className="grid grid-cols-2 gap-3">
          <Field label="اللغة" htmlFor="wa-tpl-lang">
            <Select id="wa-tpl-lang" value={language} disabled={editingExisting}
                   onChange={(e) => setLanguage(e.target.value)}>
              <option value="ar">العربية</option>
              <option value="en">English</option>
            </Select>
          </Field>
          <Field label="التصنيف عند ميتا" htmlFor="wa-tpl-cat">
            <Select id="wa-tpl-cat" value={category} onChange={(e) => setCategory(e.target.value)}>
              <option value="AUTHENTICATION">تحقّق هوية</option>
              <option value="UTILITY">خدمية</option>
              <option value="MARKETING">تسويقية</option>
            </Select>
          </Field>
        </div>
        <Field label="نص القالب" required htmlFor="wa-tpl-body">
          {/* لا dir هنا عمداً — جُرِّب dir="ltr" هنا فعلياً وقلب ترتيب الجُمل العربية كاملاً (كل
             جملة عربية تصير بموضع الجملة المقابلة لها بدل مكانها، لا مجرد أقواس معكوسة)، لأن
             textarea الأصلي متعدد المقاطع (عربي + {{code}} + عربي) لا فقرة عربية واحدة بسيطة.
             هذا خانة تحرير نصية بلا تحكّم عنصر-بعنصر (بخلاف المعاينة أسفل، انظر renderBidiSafe) —
             فرض أي dir واحد يكسر جهة كاملة؛ العرض الافتراضي (بلا فرض) هو الأقل ضرراً المتاح هنا. */}
          <Textarea id="wa-tpl-body" rows={5} value={body}
                    onChange={(e) => setBody(e.target.value)}
                    placeholder="رمز التحقق الخاص بك هو {{code}}. صالح لمدة 5 دقائق." />
        </Field>
        <Field label="أسماء المتغيّرات (مفصولة بفاصلة، بنفس ترتيب ظهورها بالنص)" htmlFor="wa-tpl-vars">
          <Input id="wa-tpl-vars" dir="ltr" value={variablesText}
                onChange={(e) => setVariablesText(e.target.value)} placeholder="code" />
        </Field>

        {/* زر يفتح فلو تفاعلي (Meta FLOW button) — منفصل عن القالب النصي البسيط. الحقل موجود
           بالخادم من قبل (register()'s own flow_button)، بس ما كان له واجهة هنا؛ القالب لسه
           يُبنى بنفس مسار "حفظ كمسوّدة ثم أرسل للمراجعة" — الفرق الوحيد إن ميتا تُنشئ زر FLOW
           بالقالب نفسه، لا رسالة تفاعلية منفصلة. */}
        <div className="flex flex-col gap-3 rounded-lg border border-border-subtle p-3">
          <div className="flex items-center justify-between gap-3">
            <div>
              <p className="text-sm font-medium">زر يفتح فلو تفاعلي</p>
              <p className="text-label text-text-secondary">
                بدل رابط أو رد سريع، القالب يحمل زراً يفتح شاشات تفاعلية (فلو) مباشرة.
              </p>
            </div>
            <Toggle checked={flowEnabled} onChange={setFlowEnabled} ariaLabel="زر يفتح فلو تفاعلي"
                   testId="wa-tpl-flow-toggle" />
          </div>
          {flowEnabled ? (
            <>
              <Field label="اسم الفلو (flow_name)" required htmlFor="wa-tpl-flow-name"
                    hint="نفس الاسم المسجَّل به الفلو عند التزويد — مثال: booking_flow">
                <Input id="wa-tpl-flow-name" dir="ltr" value={flowName}
                      onChange={(e) => setFlowName(e.target.value)} placeholder="subscription_renewal" />
              </Field>
              <Field label="نص الزر" htmlFor="wa-tpl-flow-text"
                    hint='يظهر للعميل على الزر نفسه — افتراضياً "Open" إن تُرك فارغاً.'>
                <Input id="wa-tpl-flow-text" value={flowButtonText}
                      onChange={(e) => setFlowButtonText(e.target.value)} placeholder="جدّد الآن" />
              </Field>
            </>
          ) : null}
        </div>

        {/* المعاينة حيّة — تتحدّث مع كل حرف. نفس المحرك (WhatsAppTemplatePreview) يقرأ الفلو
           الحقيقي المُولَّد لحظياً من notification-service، لا تخيّلاً محلياً لشكله. */}
        <div className="rounded-lg border border-border-subtle bg-surface-2/50 p-3">
          <p className="mb-2 text-label font-medium text-text-secondary">معاينة حيّة</p>
          <WhatsAppTemplatePreview
            data={{
              body,
              examples: variables.map((_v, i) => `مثال ${i + 1}`),
              flowButton: flowEnabled && flowName.trim()
                ? { flowName: flowName.trim(), text: flowButtonText.trim() || 'فتح' }
                : undefined,
            }}
            fetchFlowJson={makeFlowJsonFetcher(session, flowJsonAction)}
          />
        </div>

        {error ? <p role="alert" className="text-danger text-sm">{error}</p> : null}
      </div>
    </Drawer>
  );
}
