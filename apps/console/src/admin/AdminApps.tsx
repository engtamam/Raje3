/**
 * التطبيقات والأسعار والعروض — المرحلة ٦، أُعيد بناؤها لاحقاً كبطاقات مقروءة (PlanCards.tsx/
 * CouponCards.tsx) بدل الجدول العام الخام — عمود إنجليزي، حدود مفكوكة كـJSON بعمود واحد، غير
 * صالحة لمشغّل حقيقي. Plans و Coupons صارا تبويبين فرعيين (Segmented) أعلى نفس الشاشة، لا
 * قسمين مكدَّسين تحت بعض — الشريط الجانبي محدود عمداً بـ٥-٦ أقسام (طلب سابق)، فتبويب سابع
 * كامل لم يكن خياراً.
 *
 * "التطبيقات" (تفعيل/تعطيل تطبيق كامل، لا مجرد سعر باقة) و"إنشاء" كوبون/باقة جديدة — نموذج ملء
 * حقول من الصفر — مؤجَّلان: يحتاجان نموذجاً حقيقياً بحقول متعددة (أسعار، حدود، مواعيد)، لا يلائم
 * التوليد التلقائي. تُبنى لاحقاً كشاشة نموذج مخصّصة.
 */
import { useEffect, useState } from 'react';
import { Segmented } from '../rj-ui/Segmented';
import { PlanCards } from './PlanCards';
import { CouponCards } from './CouponCards';
import { allActions, fetchCatalog, type AdminAction, type AdminCatalog } from './catalog';
import { req, type AdminSession } from './api';
import { NoActionAvailable } from './NoActionAvailable';

type SubTab = 'plans' | 'coupons';

export function AdminApps({ session }: { session: AdminSession }) {
  const [catalog, setCatalog] = useState<AdminCatalog | 'loading' | 'failed'>('loading');
  const [sub, setSub] = useState<SubTab>('plans');

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

  const flat = allActions(catalog);
  const byId = (id: string) => flat.find((a) => a.id === id);
  const plansList = byId('billing.list_plans');
  const couponsList = byId('billing.list_coupons');
  const availabilityAction = byId('billing.plan_availability');
  const deleteCouponAction = byId('billing.delete_coupon');

  if (!plansList && !couponsList) {
    return <NoActionAvailable catalog={catalog} permissionTitle="حسابك لا يحمل صلاحية القراءة هنا — لا باقات ولا كوبونات لعرضها لك." />;
  }

  return (
    <div className="flex flex-col gap-4 p-6">
      <h1 className="text-2xl leading-tight tracking-tight">التطبيقات والأسعار والعروض</h1>

      <Segmented ariaLabel="القسم" value={sub} onChange={setSub}
                options={[
                  { value: 'plans', label: 'الباقات والأسعار' },
                  { value: 'coupons', label: 'الخصومات والعروض' },
                ]} />

      {sub === 'plans' ? (
        plansList
          ? <PlansPane session={session} listAction={plansList} availabilityAction={availabilityAction} />
          : <p className="text-sm text-text-secondary">حسابك لا يحمل صلاحية القراءة هنا.</p>
      ) : null}

      {sub === 'coupons' ? (
        couponsList
          ? <CouponsPane session={session} listAction={couponsList} deleteAction={deleteCouponAction} />
          : <p className="text-sm text-text-secondary">حسابك لا يحمل صلاحية القراءة هنا.</p>
      ) : null}
    </div>
  );
}

function PlansPane({ session, listAction, availabilityAction }: {
  session: AdminSession; listAction: AdminAction; availabilityAction?: AdminAction;
}) {
  const [rows, setRows] = useState<unknown[] | 'loading' | 'failed'>('loading');

  const reload = () => {
    setRows('loading');
    req<{ plans: unknown[] }>(`${listAction.path}?include_hidden=true`, 'GET', undefined, session.access_token)
      .then((body) => setRows(body.plans))
      .catch(() => setRows('failed'));
  };

  useEffect(reload, [listAction, session]);

  if (rows === 'loading') return <p className="text-sm text-text-secondary">جارٍ التحميل…</p>;
  if (rows === 'failed') return <p role="alert" className="text-danger text-sm">تعذّرت قراءة الباقات.</p>;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any -- the catalog's own AdminAction
  // carries no response schema (only request params) — see catalog.ts's own note on why.
  return <PlanCards session={session} listAction={listAction} availabilityAction={availabilityAction}
                    plans={rows as any} onReload={reload} />;
}

function CouponsPane({ session, listAction, deleteAction }: {
  session: AdminSession; listAction: AdminAction; deleteAction?: AdminAction;
}) {
  const [rows, setRows] = useState<unknown[] | 'loading' | 'failed'>('loading');

  const reload = () => {
    setRows('loading');
    req<{ coupons: unknown[] }>(listAction.path, 'GET', undefined, session.access_token)
      .then((body) => setRows(body.coupons))
      .catch(() => setRows('failed'));
  };

  useEffect(reload, [listAction, session]);

  if (rows === 'loading') return <p className="text-sm text-text-secondary">جارٍ التحميل…</p>;
  if (rows === 'failed') return <p role="alert" className="text-danger text-sm">تعذّرت قراءة الكوبونات.</p>;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any -- same reason as PlansPane above.
  return <CouponCards session={session} deleteAction={deleteAction} coupons={rows as any} onReload={reload} />;
}
