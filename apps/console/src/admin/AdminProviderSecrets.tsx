/**
 * مفاتيح المزوّدين الخارجيين — secrets-admin's own screen. NOT `AdminSecrets.tsx` (that one is
 * every OURS service's own `platform.secrets` operator/secrets route — a shop's payment key, a
 * delivery driver's token). This is a DIFFERENT, unrelated capability
 * (`platform.secrets_manage`): rewriting the credential Meta/Gemini/etc. secrets that are sealed
 * into OTHER services' own K8s Secret objects — see services/secrets-admin/app/admin_actions.py's
 * own header for why there is, and will never be, a third action of the obvious kind.
 *
 * WRITE-ONLY, STRUCTURALLY, NOT BY DISCIPLINE. `secrets.list`'s own response cannot carry a value
 * — the backend route never even reads `data`, only annotations (see that service's own
 * api/v1/secrets.py). This component holds no state that could ever contain one either: `newValue`
 * is cleared the instant a save resolves, success or failure, and there is no "show" affordance
 * anywhere below — not behind a second click, not behind a second capability. A future edit that
 * wants to add one should read the backend module's own docstring first.
 */
import { useEffect, useState } from 'react';
import { CircleHelp } from 'lucide-react';
import { Button } from '../rj-ui/Button';
import { Input } from '../rj-ui/Field';
import { Badge } from '../rj-ui/Badge';
import { EmptyState } from '../rj-ui/EmptyState';
import { ConfirmDialog } from '../rj-ui/ConfirmDialog';
import { fetchCatalog, type AdminAction, type AdminCatalog } from './catalog';
import { req, type AdminSession } from './api';
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
// secret_registry.py's own SECRETS tuple exactly (same 5 keys, same order); that file is the
// real source of truth for WHICH keys exist, this is only the console's own explanatory text for
// them, since the backend route never sends more than {key, label, ...}. An unknown key (a sixth
// added there but not here) still shows fine — just without the "؟" hint, never hidden.
const SECRET_HELP: Record<string, string> = {
  META_APP_ID: 'من لوحة مطوّري Meta (developers.facebook.com) — تطبيقك ← إعدادات أساسية ← "معرّف التطبيق".',
  META_APP_SECRET: 'من نفس صفحة إعدادات التطبيق بلوحة مطوّري Meta — "سر التطبيق" (يحتاج تأكيد كلمة مرور حسابك لإظهاره).',
  WHATSAPP_WEBHOOK_VERIFY_TOKEN: 'نص تختاره أنت بنفسك (أي نص عشوائي قوي) وتُدخِله هنا وبنفس الوقت بإعدادات الـwebhook بلوحة Meta — يجب أن يتطابق النصّان بالضبط.',
  WHATSAPP_360DIALOG_API_KEY: 'من لوحة 360dialog (hub.360dialog.com) — قسم API Keys الخاص برقم واتساب التجاري.',
  GEMINI_API_KEY: 'من Google AI Studio (aistudio.google.com/apikey) — الأسهل، بلا مشروع GCP. أو من GCP نفسه (console.cloud.google.com): فعّل "Generative Language API" وأنشئ مفتاحاً من Credentials، لو تبي تربطه بمشروع/فوترة محددة.',
};

export function AdminProviderSecrets({ session }: { session: AdminSession }) {
  const [catalog, setCatalog] = useState<AdminCatalog | 'loading' | 'failed'>('loading');
  const [rows, setRows] = useState<SecretRow[] | 'loading' | 'failed'>('loading');

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
          {rows.map((row) => (
            <SecretRowCard key={row.key} row={row} session={session}
                           updateAction={updateAction}
                           onSaved={() => listAction && reload(listAction)} />
          ))}
        </div>
      )}
    </div>
  );
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
  const inputId = `provider-secret-${row.key}`;
  const help = SECRET_HELP[row.key];

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
      setError(err instanceof Error ? err.message : 'تعذّر حفظ المفتاح.');
    } finally {
      // THE FIELD CLEARS EITHER WAY — success or failure, nothing typed here survives the
      // request. A failed save is retried by typing again, never by re-submitting what is
      // already gone from this component's own state.
      setValue('');
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
            {/* type="password" + autoComplete="off" — masked as it is typed, never stored anywhere
               but this one field, and cleared the instant the request settles either way. */}
            <Input id={inputId} dir="ltr" type="password" autoComplete="off" value={value}
                  onChange={(e) => setValue(e.target.value)} />
          </div>
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
