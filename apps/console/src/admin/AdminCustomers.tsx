/**
 * العملاء والدعم — المرحلة ٣ فقط هنا: أول قائمة حقيقية عبر المحرّك العام
 * (`ActionRenderer.tsx`)، طلبات المسوّقين المعلّقة (`affiliates.list_pending` +
 * `approve_application`/`reject_application`) — نفس نظام الموافقة المبني اليوم بجلسة سابقة.
 *
 * هذا فرع مؤقت من الكتالوج (مجموعة "Affiliates" فقط) — بقية "العملاء والدعم" (جدول العملاء
 * السبعة الأعمدة، ملف العميل الستة تبويبات، تشخيص واتساب) تُبنى كشاشات مصقولة يدوياً بمراحل
 * لاحقة (٧/٩ بالخطة)، لا تُترك للمحرّك العام.
 */
import { useEffect, useState } from 'react';
import { Segmented } from '../rj-ui/Segmented';
import { ActionCatalogPanel } from './ActionRenderer';
import { AdminWhatsAppDiagnostics } from './AdminWhatsAppDiagnostics';
import { allActions, fetchCatalog, type AdminCatalog } from './catalog';
import type { AdminSession } from './api';

type SubTab = 'affiliates' | 'whatsapp';

export function AdminCustomers({ session }: { session: AdminSession }) {
  const [catalog, setCatalog] = useState<AdminCatalog | 'loading' | 'failed'>('loading');
  const [sub, setSub] = useState<SubTab>('affiliates');

  useEffect(() => {
    let cancelled = false;
    fetchCatalog(session)
      .then((c) => { if (!cancelled) setCatalog(c); })
      .catch(() => { if (!cancelled) setCatalog('failed'); });
    return () => { cancelled = true; };
  }, [session]);

  if (catalog === 'loading') {
    return <p className="p-6 text-sm text-text-secondary">جارٍ التحميل…</p>;
  }
  if (catalog === 'failed') {
    return <p role="alert" className="p-6 text-danger">تعذّرت قراءة كتالوج الإدارة.</p>;
  }

  const affiliateActions = allActions(catalog).filter((a) => a.group === 'Affiliates');

  return (
    <div className="flex flex-col gap-4">
      <div className="px-6 pt-6">
        <h1 className="mb-3 text-2xl leading-tight tracking-tight">العملاء والدعم</h1>
        <Segmented
          value={sub}
          onChange={(v) => setSub(v as SubTab)}
          options={[
            { value: 'affiliates', label: 'طلبات المسوّقين' },
            { value: 'whatsapp', label: 'تشخيص واتساب' },
          ]}
        />
      </div>
      {sub === 'affiliates' ? <ActionCatalogPanel session={session} actions={affiliateActions} catalog={catalog} /> : null}
      {sub === 'whatsapp' ? <AdminWhatsAppDiagnostics session={session} /> : null}
    </div>
  );
}
