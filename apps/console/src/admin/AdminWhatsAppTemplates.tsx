/**
 * قوالب واتساب — حالة كل قالب واضحة دائماً، لا "عذر صامت". السبب المباشر لهذي الشاشة: نظام
 * الإرسال (notification-service) يرفض أي رسالة أولى بلا قالب معتمد من ميتا — رفض صحيح ومقصود،
 * لكن كان بلا أي واجهة تعرضه، فيقرأ كخطأ غامض بدل حالة مفهومة. هذي الشاشة تجعل "قيد المراجعة /
 * معتمد / مرفوض / متوقف / مُعطَّل" مرئية دائماً، بألوانها، مع سبب الرفض إن وُجد — لا شي مخفي.
 *
 * التسجيل يصير هنا (نص القالب عندنا، الخدمة لا تعرف معناه — انظر whatsapp_templates.py's own
 * docstring)، والإرسال للمراجعة زر منفصل — القالب يبقى "قيد المراجعة" بدون إرسال فعلي لميتا حتى
 * تضغط "أرسل للمراجعة" صراحة، بلا أي مفاجأة.
 *
 * النطاق (tenant) الفعلي لكل قالب هنا هو منشأة لوحة الإدارة المحجوزة (`_platform`) — نفس المنشأة
 * اللي identity-service المفروض يقرأ منها إعداد OTP_NOTIFY_TENANT وقت إرسال رمز التحقق، بحيث
 * القالب اللي تسجّله وتعتمده هنا هو نفسه اللي الإرسال الحقيقي يجده — لا تعارض منشآت.
 */
import { useEffect, useState } from 'react';
import {
  FileText, Clock, CheckCircle2, XCircle, PauseCircle, Ban, Plus, Send, RefreshCw,
} from 'lucide-react';
import { Button } from '../rj-ui/Button';
import { Field, Input, Select, Textarea } from '../rj-ui/Field';
import { Badge } from '../rj-ui/Badge';
import { Segmented } from '../rj-ui/Segmented';
import { Drawer } from '../rj-ui/Drawer';
import { ConfirmDialog } from '../rj-ui/ConfirmDialog';
import { EmptyState } from '../rj-ui/EmptyState';
import { fetchCatalog, type AdminAction, type AdminCatalog } from './catalog';
import { req, type AdminSession } from './api';
import { NoActionAvailable } from './NoActionAvailable';

type TemplateStatus = 'pending' | 'approved' | 'rejected' | 'paused' | 'disabled';

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
  created: string;
  updated: string;
}

const STATUS_META: Record<TemplateStatus, { label: string; tone: 'warning' | 'success' | 'danger' | 'neutral'; icon: typeof Clock }> = {
  pending: { label: 'قيد المراجعة', tone: 'warning', icon: Clock },
  approved: { label: 'معتمد', tone: 'success', icon: CheckCircle2 },
  rejected: { label: 'مرفوض', tone: 'danger', icon: XCircle },
  paused: { label: 'متوقف مؤقتاً', tone: 'warning', icon: PauseCircle },
  disabled: { label: 'مُعطَّل', tone: 'danger', icon: Ban },
};

const CATEGORY_LABEL: Record<string, string> = {
  UTILITY: 'خدمية', MARKETING: 'تسويقية', AUTHENTICATION: 'تحقّق هوية',
};

const FILTERS: { value: TemplateStatus | 'all'; label: string }[] = [
  { value: 'all', label: 'الكل' },
  { value: 'pending', label: 'قيد المراجعة' },
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
    <div className="flex flex-col gap-6 p-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold leading-tight tracking-tight">قوالب واتساب</h1>
          <p className="mt-1 max-w-xl text-sm text-text-secondary">
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
                         onChanged={reload} />
          ))}
        </div>
      )}

      {registerAction ? (
        <RegisterDrawer session={session} action={registerAction} open={creating}
                       onClose={() => setCreating(false)}
                       onCreated={() => { setCreating(false); reload(); }} />
      ) : null}
    </div>
  );
}

function findAction(catalog: AdminCatalog, id: string): AdminAction | undefined {
  return catalog.services.flatMap((s) => s.actions).find((a) => a.id === id);
}

function TemplateCard({ template, session, submitAction, onChanged }: {
  template: Template; session: AdminSession; submitAction?: AdminAction; onChanged: () => void;
}) {
  const [busy, setBusy] = useState(false);
  const [arm, setArm] = useState(false);
  const [error, setError] = useState('');
  const meta = STATUS_META[template.status] ?? STATUS_META.pending;
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
      setError(err instanceof Error ? err.message : 'تعذّر الإرسال للمراجعة.');
    } finally {
      setBusy(false);
      setArm(false);
    }
  }

  return (
    <section className="flex flex-col gap-3 rounded-card border border-border-subtle bg-surface-1 p-4 shadow-sm">
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-start gap-2.5">
          <span className="mt-0.5 inline-flex rounded-lg bg-accent-soft p-2 text-accent-on-soft">
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
        <p className="whitespace-pre-wrap rounded-lg bg-surface-2 p-3 text-sm text-text-secondary">
          {template.body}
        </p>
      ) : null}

      {template.variables.length > 0 ? (
        <p className="text-label text-text-secondary">
          المتغيّرات: {template.variables.map((v) => `{{${v}}}`).join('  ')}
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

      {template.status === 'pending' && !template.provider_template_id && submitAction ? (
        <Button size="sm" onClick={() => setArm(true)} disabled={busy} className="w-fit gap-2">
          <Send size={14} /> أرسل للمراجعة
        </Button>
      ) : template.status === 'pending' && template.provider_template_id ? (
        <p className="text-label text-text-secondary">أُرسل لميتا — بانتظار القرار.</p>
      ) : null}

      <ConfirmDialog open={arm} onClose={() => setArm(false)} onConfirm={doSubmit} busy={busy}
                    title={`إرسال "${template.name}" لمراجعة ميتا؟`}
                    body="لا يمكن التراجع بعد الإرسال — المراجعة تصير عند ميتا نفسها، قد تأخذ ساعات لأيام." />
    </section>
  );
}

function RegisterDrawer({ session, action, open, onClose, onCreated }: {
  session: AdminSession; action: AdminAction; open: boolean; onClose: () => void; onCreated: () => void;
}) {
  const [name, setName] = useState('');
  const [language, setLanguage] = useState('ar');
  const [category, setCategory] = useState('AUTHENTICATION');
  const [body, setBody] = useState('');
  const [variablesText, setVariablesText] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  const variables = variablesText.split(',').map((v) => v.trim()).filter(Boolean);
  const canSave = /^[a-z0-9_]+$/.test(name) && body.trim().length > 0;

  async function save() {
    if (!canSave) return;
    setBusy(true);
    setError('');
    try {
      await req(action.path, 'POST',
        { name, language, category, body, variables }, session.access_token);
      setName(''); setBody(''); setVariablesText(''); setCategory('AUTHENTICATION'); setLanguage('ar');
      onCreated();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'تعذّر التسجيل.');
    } finally {
      setBusy(false);
    }
  }

  return (
    <Drawer open={open} onClose={onClose} title="قالب واتساب جديد"
           subtitle='النص من عندنا — الخدمة تخزّنه بلا فهم معناه، وترسله لميتا فقط عند "إرسال للمراجعة".'
           footer={
             <>
               <Button type="button" variant="ghost" onClick={onClose}>إلغاء</Button>
               <Button type="button" disabled={!canSave || busy} onClick={save}>
                 {busy ? 'جارٍ الحفظ…' : 'حفظ كمسوّدة'}
               </Button>
             </>
           }>
      <div className="flex flex-col gap-4">
        <Field label="الاسم (بالإنجليزية، أحرف صغيرة وأرقام و_ فقط)" required htmlFor="wa-tpl-name">
          <Input id="wa-tpl-name" dir="ltr" value={name}
                onChange={(e) => setName(e.target.value.toLowerCase())} placeholder="auth_otp" />
        </Field>
        <div className="grid grid-cols-2 gap-3">
          <Field label="اللغة" htmlFor="wa-tpl-lang">
            <Select id="wa-tpl-lang" value={language} onChange={(e) => setLanguage(e.target.value)}>
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
          <Textarea id="wa-tpl-body" rows={5} value={body} onChange={(e) => setBody(e.target.value)}
                    placeholder="رمز التحقق الخاص بك هو {{code}}. صالح لمدة 5 دقائق." />
        </Field>
        <Field label="أسماء المتغيّرات (مفصولة بفاصلة، بنفس ترتيب ظهورها بالنص)" htmlFor="wa-tpl-vars">
          <Input id="wa-tpl-vars" dir="ltr" value={variablesText}
                onChange={(e) => setVariablesText(e.target.value)} placeholder="code" />
        </Field>
        {error ? <p role="alert" className="text-danger text-sm">{error}</p> : null}
      </div>
    </Drawer>
  );
}
