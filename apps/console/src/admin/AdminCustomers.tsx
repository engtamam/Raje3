/**
 * العملاء والدعم — الشاشة الأهم بلوحة الإدارة (بتصريح المستخدم صراحة). جدول العملاء (`CustomerList.tsx`)
 * هو التبويب الافتراضي الآن — قائمة حقيقية بخصائصها الخاصة (بحث، فلاتر حالة، KPIs، ملف عميل بستة
 * تبويبات)، لا محرّك عام. طلبات المسوّقين (المحرّك العام، مجموعة "Affiliates" فقط) وتشخيص واتساب
 * يبقيان تبويبين منفصلين كما كانا.
 *
 * المرحلة الحالية (١): جدول العملاء + تبويبَي "نظرة عامة" و"الاشتراك والفوترة" ببيانات حقيقية.
 * البقية (فروع/مستخدمين، تذاكر، واتساب لكل عميل، سجل تدقيق) ظاهرة كتبويبات بمحتوى "قريباً" صريح
 * يشرح بالضبط الفجوة — انظر CustomerDetail.tsx's own header.
 */
import { useEffect, useState } from 'react';
import { Segmented } from '../rj-ui/Segmented';
import { ActionCatalogPanel } from './ActionRenderer';
import { AdminWhatsAppDiagnostics } from './AdminWhatsAppDiagnostics';
import { CustomerList } from './CustomerList';
import { allActions, fetchCatalog, type AdminCatalog } from './catalog';
import type { AdminSession } from './api';

type SubTab = 'customers' | 'affiliates' | 'whatsapp';

export function AdminCustomers({ session }: { session: AdminSession }) {
  const [catalog, setCatalog] = useState<AdminCatalog | 'loading' | 'failed'>('loading');
  const [sub, setSub] = useState<SubTab>('customers');

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
            { value: 'customers', label: 'العملاء' },
            { value: 'affiliates', label: 'طلبات المسوّقين' },
            { value: 'whatsapp', label: 'تشخيص واتساب' },
          ]}
        />
      </div>
      {sub === 'customers' ? <CustomerList session={session} /> : null}
      {sub === 'affiliates' ? <ActionCatalogPanel session={session} actions={affiliateActions} catalog={catalog} /> : null}
      {sub === 'whatsapp' ? <AdminWhatsAppDiagnostics session={session} /> : null}
    </div>
  );
}
