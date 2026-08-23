/**
 * أسرار المشغّل — المرحلة ٩، شاشة مصقولة يدوياً. لا قراءة قيمة أبداً بأي حال — فقط تلميح ٤
 * خانات (`hint`) يرجعه الخادم نفسه؛ الشاشة لا تملك ولا تطلب القيمة الفعلية إطلاقاً، فقط تضبطها
 * كتابةً بلا قراءة رجوع (نفس سياج `operator.py`'s الخلفي تماماً).
 */
import { useEffect, useState } from 'react';
import { Button } from '../rj-ui/Button';
import { Input } from '../rj-ui/Field';
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

export function AdminSecrets({ session }: { session: AdminSession }) {
  const [catalog, setCatalog] = useState<AdminCatalog | 'loading' | 'failed'>('loading');
  const [byService, setByService] = useState<Record<string, ServiceSecrets['rows']>>({});

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

  return (
    <div className="flex flex-col gap-6 p-6">
      <h1 className="text-2xl leading-tight tracking-tight">أسرار المشغّل</h1>
      {services.map((svc) => (
        <ServiceSecretsCard key={svc.service} session={session} svc={svc}
                            onReload={(rows) => setByService((p) => ({ ...p, [svc.service]: rows }))} />
      ))}
    </div>
  );
}

function ServiceSecretsCard({ session, svc, onReload }: {
  session: AdminSession; svc: ServiceSecrets;
  onReload: (rows: ServiceSecrets['rows']) => void;
}) {
  const [newName, setNewName] = useState('');
  const [newValue, setNewValue] = useState('');
  const [armSet, setArmSet] = useState(false);
  const [armClear, setArmClear] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

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
      setNewName('');
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
          {svc.rows.map((s) => (
            <li key={s.name} className="flex items-center justify-between gap-2 rounded-input border border-border-subtle p-2">
              <div className="flex flex-col">
                <span className="font-medium">{s.name}</span>
                <span dir="ltr" className="text-label text-text-secondary">····{s.hint}</span>
              </div>
              <div className="flex items-center gap-2">
                {s.rotating ? <Badge tone="warning">تدوير جارٍ</Badge> : null}
                {svc.clearAction ? (
                  <Button type="button" size="sm" variant="ghost" onClick={() => setArmClear(s.name)}>مسح</Button>
                ) : null}
              </div>
            </li>
          ))}
        </ul>
      )}

      {svc.setAction ? (
        <form className="flex flex-col gap-1.5 border-t border-border-subtle pt-3 sm:flex-row sm:items-end sm:gap-2"
              onSubmit={(e) => { e.preventDefault(); setArmSet(true); }}>
          <div className="flex-1">
            <label className="text-label font-medium text-text-secondary" htmlFor={`sec-name-${svc.service}`}>اسم السرّ</label>
            <Input id={`sec-name-${svc.service}`} dir="ltr" value={newName} onChange={(e) => setNewName(e.target.value)} />
          </div>
          <div className="flex-1">
            <label className="text-label font-medium text-text-secondary" htmlFor={`sec-val-${svc.service}`}>القيمة</label>
            <Input id={`sec-val-${svc.service}`} dir="ltr" type="password" value={newValue}
                  onChange={(e) => setNewValue(e.target.value)} />
          </div>
          <Button type="submit" size="sm" disabled={!newName.trim() || !newValue}>ضبط / تدوير</Button>
        </form>
      ) : null}

      {error ? <p role="alert" className="text-danger text-sm">{error}</p> : null}

      <ConfirmDialog open={armSet} onClose={() => setArmSet(false)} onConfirm={doSet} busy={busy}
                    danger title={`ضبط السرّ "${newName}"؟`}
                    body="سيُستبدل أي سرّ سابق بنفس الاسم فوراً بكل خدمات هذي المنصّة." />
      <ConfirmDialog open={armClear !== null} onClose={() => setArmClear(null)}
                    onConfirm={() => armClear && doClear(armClear)} busy={busy} danger
                    title={`مسح السرّ "${armClear}"؟`}
                    body="أي اتصال يعتمد عليه سيتوقف فوراً حتى يُضبَط سرّ بديل." />
    </section>
  );
}
