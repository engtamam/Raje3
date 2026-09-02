/**
 * أسرار المشغّل — المرحلة ٩، شاشة مصقولة يدوياً. لا قراءة قيمة أبداً بأي حال — فقط تلميح ٤
 * خانات (`hint`) يرجعه الخادم نفسه؛ الشاشة لا تملك ولا تطلب القيمة الفعلية إطلاقاً، فقط تضبطها
 * كتابةً بلا قراءة رجوع (نفس سياج `operator.py`'s الخلفي تماماً).
 *
 * مجمّعة بـ«تطبيقات» لا بأسماء الخدمات الخام — عملياً «واتساب» شي واحد لمن يديره، حتى لو
 * تقنياً موزّع على خدمتين (notification-service لتوكن الإرسال، whatsapp-assistant لمفتاح
 * الذكاء الاصطناعي). قائمة تطبيقات أولاً، ضغطة تفتح إعدادات ذاك التطبيق فقط — لا شاشة واحدة
 * طويلة بكل الخدمات مبعثرة. خدمة غير معروفة بـ`APP_GROUPS` تصير تطبيقها الخاص باسمها هي.
 */
import { useEffect, useState } from 'react';
import { Button } from '../rj-ui/Button';
import { Input, Select } from '../rj-ui/Field';
import { Badge } from '../rj-ui/Badge';
import { EmptyState } from '../rj-ui/EmptyState';
import { ConfirmDialog } from '../rj-ui/ConfirmDialog';
import { fetchCatalog, type AdminAction, type AdminCatalog } from './catalog';
import { req, type AdminSession } from './api';

interface SecretRow { name: string; hint: string; set_at: string; rotating: boolean }
interface ServiceSecrets {
  service: string;
  listAction: AdminAction;
  setAction?: AdminAction;
  clearAction?: AdminAction;
  rows: SecretRow[] | 'loading' | 'failed';
}

// SERVICE -> APP. Only services that actually need grouping under a shared, user-facing name are
// listed — everything else falls back to its own service name as its own app (see `appOf` below).
// Extend this the day a THIRD service joins an existing app, not speculatively.
const APP_GROUPS: Record<string, { id: string; label: string }> = {
  'notification-service': { id: 'whatsapp', label: 'واتساب' },
  'whatsapp-assistant': { id: 'whatsapp', label: 'واتساب' },
};

function appOf(service: string): { id: string; label: string } {
  return APP_GROUPS[service] ?? { id: service, label: service };
}

export function AdminSecrets({ session }: { session: AdminSession }) {
  const [catalog, setCatalog] = useState<AdminCatalog | 'loading' | 'failed'>('loading');
  const [byService, setByService] = useState<Record<string, ServiceSecrets['rows']>>({});
  const [openApp, setOpenApp] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetchCatalog(session).then((c) => { if (!cancelled) setCatalog(c); })
      .catch(() => { if (!cancelled) setCatalog('failed'); });
    return () => { cancelled = true; };
  }, [session]);

  useEffect(() => {
    if (catalog === 'loading' || catalog === 'failed') return;
    for (const svc of catalog.services) {
      const listAction = svc.actions.find((a) => a.id === 'operator.list_secrets');
      if (!listAction || byService[svc.service] !== undefined) continue;
      req<{ secrets: SecretRow[] }>(listAction.path, 'GET', undefined, session.access_token)
        .then((body) => setByService((p) => ({ ...p, [svc.service]: body.secrets })))
        .catch(() => setByService((p) => ({ ...p, [svc.service]: 'failed' })));
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps -- byService is written by this same
    // effect; including it would loop, not re-fetch anything new.
  }, [catalog, session]);

  if (catalog === 'loading') return <p className="p-6 text-sm text-text-secondary">جارٍ التحميل…</p>;
  if (catalog === 'failed') return <p role="alert" className="p-6 text-danger">تعذّرت قراءة كتالوج الإدارة.</p>;

  const services: ServiceSecrets[] = catalog.services
    .map((s): ServiceSecrets | null => {
      const listAction = s.actions.find((a) => a.id === 'operator.list_secrets');
      if (!listAction) return null;
      return {
        service: s.service, listAction,
        setAction: s.actions.find((a) => a.id === 'operator.set_secret'),
        clearAction: s.actions.find((a) => a.id === 'operator.clear_secret'),
        rows: byService[s.service] ?? 'loading',
      };
    })
    .filter((s): s is ServiceSecrets => s !== null);

  if (services.length === 0) {
    return <div className="p-6"><EmptyState title="لا أسرار متاحة لصلاحياتك" /></div>;
  }

  // Group services into apps, preserving first-seen order.
  const apps: { id: string; label: string; services: ServiceSecrets[] }[] = [];
  for (const svc of services) {
    const app = appOf(svc.service);
    let bucket = apps.find((a) => a.id === app.id);
    if (!bucket) { bucket = { ...app, services: [] }; apps.push(bucket); }
    bucket.services.push(svc);
  }

  const current = openApp ? apps.find((a) => a.id === openApp) : undefined;

  if (current) {
    return (
      <div className="flex flex-col gap-6 p-6">
        <div className="flex items-center gap-2">
          <Button type="button" size="sm" variant="ghost" onClick={() => setOpenApp(null)}>
            ← كل التطبيقات
          </Button>
          <h1 className="text-2xl leading-tight tracking-tight">{current.label}</h1>
        </div>
        {current.services.map((svc) => (
          <ServiceSecretsCard key={svc.service} session={session} svc={svc}
                              onReload={(rows) => setByService((p) => ({ ...p, [svc.service]: rows }))} />
        ))}
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-6 p-6">
      <h1 className="text-2xl leading-tight tracking-tight">أسرار المشغّل</h1>
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {apps.map((app) => {
          const rowCounts = app.services.map((s) => (Array.isArray(s.rows) ? s.rows.length : 0));
          const total = rowCounts.reduce((a, b) => a + b, 0);
          const anyFailed = app.services.some((s) => s.rows === 'failed');
          return (
            <button key={app.id} type="button" onClick={() => setOpenApp(app.id)}
                    className="flex flex-col gap-1 rounded-card border border-border-subtle bg-surface-1 p-4 text-start transition hover:border-border-strong">
              <span className="text-lg font-semibold">{app.label}</span>
              <span className="text-label text-text-secondary">
                {anyFailed ? 'تعذّرت قراءة بعض الاعتمادات' : `${total} اعتماد مضبوط`}
              </span>
            </button>
          );
        })}
      </div>
    </div>
  );
}

function ServiceSecretsCard({ session, svc, onReload }: {
  session: AdminSession; svc: ServiceSecrets;
  onReload: (rows: ServiceSecrets['rows']) => void;
}) {
  // `nameChoices` is the FIRST body param named "name" on setAction, if the service declared
  // `choices` on it (see catalog.ts's own note) — a service that knows its exact expected
  // credential names lists them here instead of leaving an operator to type one by hand. Falls
  // back to free text when a service declares none, so nothing breaks for a service that has not
  // adopted this yet.
  const nameChoices = svc.setAction?.params?.find((p) => p.name === 'name')?.choices;

  const [newName, setNewName] = useState(nameChoices?.[0]?.value ?? '');
  const [newValue, setNewValue] = useState('');
  const [armSet, setArmSet] = useState(false);
  const [armClear, setArmClear] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  const chosen = nameChoices?.find((c) => c.value === newName);

  const reload = () => {
    req<{ secrets: SecretRow[] }>(svc.listAction.path, 'GET', undefined, session.access_token)
      .then((body) => onReload(body.secrets)).catch(() => onReload('failed'));
  };

  async function doSet() {
    if (!svc.setAction || !newName.trim() || !newValue) return;
    setBusy(true);
    setError('');
    try {
      await req(svc.setAction.path, 'PUT', { name: newName.trim(), value: newValue }, session.access_token);
      setNewValue('');
      reload();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'تعذّر ضبط السرّ.');
    } finally {
      setBusy(false);
      setArmSet(false);
    }
  }

  async function doClear(name: string) {
    if (!svc.clearAction) return;
    setBusy(true);
    setError('');
    try {
      await req(svc.clearAction.path.replace('{name}', encodeURIComponent(name)),
                'DELETE', undefined, session.access_token);
      reload();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'تعذّر مسح السرّ.');
    } finally {
      setBusy(false);
      setArmClear(null);
    }
  }

  return (
    <section className="flex flex-col gap-3 rounded-card border border-border-subtle bg-surface-1 p-4">
      <h2 className="text-lg font-semibold">{svc.service}</h2>
      {svc.rows === 'loading' ? (
        <p className="text-sm text-text-secondary">جارٍ التحميل…</p>
      ) : svc.rows === 'failed' ? (
        <p role="alert" className="text-danger text-sm">تعذّرت قراءة أسرار {svc.service}.</p>
      ) : svc.rows.length === 0 ? (
        <p className="text-sm text-text-secondary">لا أسرار مضبوطة بهذي الخدمة.</p>
      ) : (
        <ul className="flex flex-col gap-2">
          {svc.rows.map((s) => {
            const known = nameChoices?.find((c) => c.value === s.name);
            return (
              <li key={s.name} className="flex items-center justify-between gap-2 rounded-input border border-border-subtle p-2">
                <div className="flex flex-col">
                  <span className="font-medium">{known?.label ?? s.name}</span>
                  <span dir="ltr" className="text-label text-text-secondary">····{s.hint}</span>
                </div>
                <div className="flex items-center gap-2">
                  {s.rotating ? <Badge tone="warning">تدوير جارٍ</Badge> : null}
                  {svc.setAction ? (
                    <Button type="button" size="sm" variant="ghost"
                            onClick={() => { setNewName(s.name); setNewValue(''); }}>تحرير</Button>
                  ) : null}
                  {svc.clearAction ? (
                    <Button type="button" size="sm" variant="ghost" onClick={() => setArmClear(s.name)}>مسح</Button>
                  ) : null}
                </div>
              </li>
            );
          })}
        </ul>
      )}

      {svc.setAction ? (
        <form className="flex flex-col gap-1.5 border-t border-border-subtle pt-3 sm:flex-row sm:items-end sm:gap-2"
              onSubmit={(e) => { e.preventDefault(); setArmSet(true); }}>
          <div className="flex-1">
            <label className="text-label font-medium text-text-secondary" htmlFor={`sec-name-${svc.service}`}>الاعتماد</label>
            {nameChoices ? (
              <Select id={`sec-name-${svc.service}`} value={newName} onChange={(e) => setNewName(e.target.value)}>
                {nameChoices.map((c) => <option key={c.value} value={c.value}>{c.label}</option>)}
              </Select>
            ) : (
              <Input id={`sec-name-${svc.service}`} dir="ltr" value={newName}
                    onChange={(e) => setNewName(e.target.value)} />
            )}
          </div>
          <div className="flex-1">
            <label className="text-label font-medium text-text-secondary" htmlFor={`sec-val-${svc.service}`}>القيمة الجديدة</label>
            <Input id={`sec-val-${svc.service}`} dir="ltr" type="password" value={newValue}
                  onChange={(e) => setNewValue(e.target.value)} />
          </div>
          <Button type="submit" size="sm" disabled={!newName.trim() || !newValue}>ضبط / تدوير</Button>
        </form>
      ) : null}

      {error ? <p role="alert" className="text-danger text-sm">{error}</p> : null}

      <ConfirmDialog open={armSet} onClose={() => setArmSet(false)} onConfirm={doSet} busy={busy}
                    danger title={`ضبط "${chosen?.label ?? newName}"؟`}
                    body={chosen?.impact ??
                          'سيُستبدل أي سرّ سابق بنفس الاسم فوراً بكل خدمات هذي المنصّة.'} />
      <ConfirmDialog open={armClear !== null} onClose={() => setArmClear(null)}
                    onConfirm={() => armClear && doClear(armClear)} busy={busy} danger
                    title={`مسح "${nameChoices?.find((c) => c.value === armClear)?.label ?? armClear}"؟`}
                    body={nameChoices?.find((c) => c.value === armClear)?.impact ??
                          'أي اتصال يعتمد عليه سيتوقف فوراً حتى يُضبَط سرّ بديل.'} />
    </section>
  );
}
