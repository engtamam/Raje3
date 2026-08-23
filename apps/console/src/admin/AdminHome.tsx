/**
 * الرئيسية (لوحة القيادة) — المرحلة ١ فقط هنا: تأكيد أن تسجيل الدخول حقيقي وأن الكتالوج يصل.
 * الـ٣٥ بنداً الحقيقية تُبنى بالمراحل ٤/٥/١١ (مجمّع البيانات الجديد، ثم الاحتفاظ المجمَّع، ثم
 * التنبيهات) — انظر خطة العمل. لا رقم مخترع هنا مؤقتاً.
 */
import { useEffect, useState } from 'react';
import { fetchCatalog, type AdminCatalog } from './catalog';
import type { AdminSession } from './api';

export function AdminHome({ session }: { session: AdminSession }) {
  const [catalog, setCatalog] = useState<AdminCatalog | 'loading' | 'failed'>('loading');

  useEffect(() => {
    let cancelled = false;
    fetchCatalog(session)
      .then((c) => { if (!cancelled) setCatalog(c); })
      .catch(() => { if (!cancelled) setCatalog('failed'); });
    return () => { cancelled = true; };
  }, [session]);

  return (
    <div className="flex flex-col gap-4 p-6">
      <h1 className="text-2xl leading-tight tracking-tight">الرئيسية</h1>
      {catalog === 'loading' ? (
        <p className="text-sm text-text-secondary">جارٍ التحميل…</p>
      ) : catalog === 'failed' ? (
        <p role="alert" className="text-danger">تعذّرت قراءة كتالوج الإدارة. أعد المحاولة بعد قليل.</p>
      ) : (
        <p className="text-sm text-text-secondary">
          {catalog.actions.length} إجراء إداري متاح لصلاحياتك الحالية.
        </p>
      )}
    </div>
  );
}
