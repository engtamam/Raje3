/**
 * تشخيص واتساب لمحل — «ليش ما وصلته الرسالة؟» بحث بمعرّف تينانت أو رقم ميتا (phone_number_id)،
 * مبنية يدوياً لأن نتيجتها ليست صفوفاً بشكل ثابت (استجابة `notification-service`'s الداخلية،
 * تُعرَض كما هي). لا زر "أنشئ تذكرة بهذا الدليل" بعد — `ticket-service` لا يملك إجراء إداري
 * لإنشاء تذكرة نيابةً عن عميل اليوم، فالحدّ حقيقي لا قصور بالواجهة.
 */
import { useEffect, useState } from 'react';
import { Button } from '../rj-ui/Button';
import { Input } from '../rj-ui/Field';
import { Badge } from '../rj-ui/Badge';
import { EmptyState } from '../rj-ui/EmptyState';
import { fetchCatalog, type AdminAction, type AdminCatalog } from './catalog';
import { req, type AdminSession } from './api';
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

  const action = catalog.services.flatMap((s) => s.actions)
    .find((a) => a.id === 'operations.whatsapp_diagnostics');

  if (!action) {
    return <NoActionAvailable catalog={catalog} permissionTitle="لا صلاحية لديك لتشخيص واتساب" />;
  }

  return <DiagnosticsSearch session={session} action={action} />;
}

function DiagnosticsSearch({ session, action }: { session: AdminSession; action: AdminAction }) {
  const [tenant, setTenant] = useState('');
  const [phone, setPhone] = useState('');
  const [rows, setRows] = useState<DeliveryRow[] | 'idle' | 'loading' | 'failed'>('idle');
  const [error, setError] = useState('');

  async function search() {
    const t = tenant.trim();
    const p = phone.trim();
    if (!t && !p) return;
    setRows('loading');
    setError('');
    const qs = t ? `tenant=${encodeURIComponent(t)}` : `phone_number_id=${encodeURIComponent(p)}`;
    try {
      const body = await req<{ deliveries: DeliveryRow[] }>(
        `${action.path}?${qs}`, 'GET', undefined, session.access_token,
      );
      setRows(body.deliveries ?? []);
    } catch (err) {
      setRows('failed');
      setError(err instanceof Error ? err.message : 'تعذّر جلب سجلّ الإرسال.');
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
    </div>
  );
}

export function StatusBadge({ status }: { status?: string }) {
  if (!status) return null;
  const tone = status === 'sent' || status === 'delivered' ? 'success'
    : status === 'failed' || status === 'suppressed' ? 'danger' : 'neutral';
  return <Badge tone={tone}>{status}</Badge>;
}
