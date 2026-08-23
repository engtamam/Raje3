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
import { ActionCatalogPanel } from './ActionRenderer';
import { fetchCatalog, type AdminCatalog } from './catalog';
import type { AdminSession } from './api';

export function AdminCustomers({ session }: { session: AdminSession }) {
  const [catalog, setCatalog] = useState<AdminCatalog | 'loading' | 'failed'>('loading');

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

  const affiliateActions = catalog.actions.filter((a) => a.group === 'Affiliates');

  return (
    <div>
      <h1 className="px-6 pt-6 text-2xl leading-tight tracking-tight">العملاء والدعم</h1>
      <ActionCatalogPanel session={session} actions={affiliateActions} />
    </div>
  );
}
