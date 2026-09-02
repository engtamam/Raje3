/**
 * الإعدادات الحيّة — المرحلة ٩، شاشة مصقولة يدوياً لا مُولَّدة (Config's own `GET /operator/
 * config` يرجع كائن `{config: {...}}`، لا مصفوفة — لا يلائم `ActionListGroup`'s جدول الصفوف
 * أصلاً). تُجمِّع `RUNTIME_POLICY` الفعلية من كل خدمة أعلنت `operator.get_config`/`set_config`/
 * `clear_config` بكتالوجها الخاص — بنية الكتالوج الجديدة (services[].actions[]) تُعطي هذا
 * التجميع مجاناً، كل خدمة قسمها الخاص.
 */
import { useEffect, useState } from 'react';
import { Button } from '../rj-ui/Button';
import { Input } from '../rj-ui/Field';
import { fetchCatalog, type AdminAction, type AdminCatalog } from './catalog';
import { req, type AdminSession } from './api';
import { NoActionAvailable } from './NoActionAvailable';

interface ServiceConfig {
  service: string;
  getAction: AdminAction;
  setAction?: AdminAction;
  clearAction?: AdminAction;
  values: Record<string, string | number | boolean> | 'loading' | 'failed';
}

export function AdminConfig({ session }: { session: AdminSession }) {
  const [catalog, setCatalog] = useState<AdminCatalog | 'loading' | 'failed'>('loading');
  const [byService, setByService] = useState<Record<string, ServiceConfig['values']>>({});

  useEffect(() => {
    let cancelled = false;
    fetchCatalog(session)
      .then((c) => { if (!cancelled) setCatalog(c); })
      .catch(() => { if (!cancelled) setCatalog('failed'); });
    return () => { cancelled = true; };
  }, [session]);

  const services: ServiceConfig[] = catalog !== 'loading' && catalog !== 'failed'
    ? catalog.services
        .map((s): ServiceConfig | null => {
          const getAction = s.actions.find((a) => a.id === 'operator.get_config');
          if (!getAction) return null;
          return {
            service: s.service, getAction,
            setAction: s.actions.find((a) => a.id === 'operator.set_config'),
            clearAction: s.actions.find((a) => a.id === 'operator.clear_config'),
            values: byService[s.service] ?? 'loading',
          };
        })
        .filter((s): s is ServiceConfig => s !== null)
    : [];

  useEffect(() => {
    if (catalog === 'loading' || catalog === 'failed') return;
    for (const svc of catalog.services) {
      const getAction = svc.actions.find((a) => a.id === 'operator.get_config');
      if (!getAction || byService[svc.service] !== undefined) continue;
      req<{ config: Record<string, string | number | boolean> }>(
        getAction.path, 'GET', undefined, session.access_token,
      ).then((body) => setByService((p) => ({ ...p, [svc.service]: body.config })))
        .catch(() => setByService((p) => ({ ...p, [svc.service]: 'failed' })));
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps -- byService is read, not a dependency
    // that should re-trigger the fetch (it is what this effect itself writes to).
  }, [catalog, session]);

  if (catalog === 'loading') return <p className="p-6 text-sm text-text-secondary">جارٍ التحميل…</p>;
  if (catalog === 'failed') return <p role="alert" className="p-6 text-danger">تعذّرت قراءة كتالوج الإدارة.</p>;
  if (services.length === 0) {
    return <NoActionAvailable catalog={catalog} permissionTitle="لا إعدادات حيّة متاحة لصلاحياتك" />;
  }

  return (
    <div className="flex flex-col gap-6 p-6">
      <h1 className="text-2xl leading-tight tracking-tight">الإعدادات الحيّة</h1>
      {services.map((svc) => (
        <ServiceConfigCard key={svc.service} session={session} svc={svc}
                           onReload={(vals) => setByService((p) => ({ ...p, [svc.service]: vals }))} />
      ))}
    </div>
  );
}

function ServiceConfigCard({ session, svc, onReload }: {
  session: AdminSession; svc: ServiceConfig;
  onReload: (values: ServiceConfig['values']) => void;
}) {
  const [drafts, setDrafts] = useState<Record<string, string>>({});
  const [busyKey, setBusyKey] = useState<string | null>(null);
  const [error, setError] = useState('');

  const reload = () => {
    req<{ config: Record<string, string | number | boolean> }>(
      svc.getAction.path, 'GET', undefined, session.access_token,
    ).then((body) => onReload(body.config)).catch(() => onReload('failed'));
  };

  async function save(key: string) {
    if (!svc.setAction) return;
    setBusyKey(key);
    setError('');
    try {
      await req(svc.setAction.path, 'PUT', { key, value: drafts[key] }, session.access_token);
      reload();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'تعذّر حفظ القيمة.');
    } finally {
      setBusyKey(null);
    }
  }

  async function reset(key: string) {
    if (!svc.clearAction) return;
    setBusyKey(key);
    setError('');
    try {
      await req(svc.clearAction.path.replace('{key}', encodeURIComponent(key)),
                'DELETE', undefined, session.access_token);
      reload();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'تعذّر إعادة الضبط.');
    } finally {
      setBusyKey(null);
    }
  }

  return (
    <section className="flex flex-col gap-3 rounded-card border border-border-subtle bg-surface-1 p-4">
      <h2 className="text-lg font-semibold">{svc.service}</h2>
      {svc.values === 'loading' ? (
        <p className="text-sm text-text-secondary">جارٍ التحميل…</p>
      ) : svc.values === 'failed' ? (
        <p role="alert" className="text-danger text-sm">تعذّرت قراءة إعدادات {svc.service}.</p>
      ) : Object.keys(svc.values).length === 0 ? (
        <p className="text-sm text-text-secondary">لا مفاتيح قابلة للتعديل بهذي الخدمة.</p>
      ) : (
        <div className="flex flex-col gap-3">
          {Object.entries(svc.values).map(([key, val]) => (
            <div key={key} className="flex flex-col gap-1.5 sm:flex-row sm:items-end sm:gap-2">
              <div className="flex-1">
                <label htmlFor={`cfg-${svc.service}-${key}`}
                      className="text-label font-medium text-text-secondary">{key}</label>
                <Input id={`cfg-${svc.service}-${key}`} dir="ltr"
                      defaultValue={drafts[key] ?? String(val)}
                      onChange={(e) => setDrafts((p) => ({ ...p, [key]: e.target.value }))} />
              </div>
              <div className="flex gap-1.5">
                {svc.setAction ? (
                  <Button type="button" size="sm" disabled={busyKey === key}
                         onClick={() => save(key)}>حفظ</Button>
                ) : null}
                {svc.clearAction ? (
                  <Button type="button" size="sm" variant="ghost" disabled={busyKey === key}
                         onClick={() => reset(key)}>إعادة للافتراضي</Button>
                ) : null}
              </div>
            </div>
          ))}
        </div>
      )}
      {error ? <p role="alert" className="text-danger text-sm">{error}</p> : null}
    </section>
  );
}
