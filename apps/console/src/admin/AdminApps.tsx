/**
 * التطبيقات والأسعار والعروض — المرحلة ٦: الباقات والكوبونات كلاهما موجود بالخلفية فعلاً
 * (`billing.list_plans`/`update_plan`/`plan_availability`، `billing.list_coupons`/
 * `update_coupon`/`delete_coupon` — كلها معلَنة بالفعل، لا حاجة لأي تصعيد كان مفترضاً بالخطة
 * للفجوة H). قسمان يشتركان بنفس `group` الخلفي ("Catalogue")، فعُرضا هنا صراحة كل واحد بقائمته
 * الخاصة بدل الاعتماد على المُفسِّر التلقائي بقسم واحد لكل مجموعة — انظر `ActionRenderer.tsx`'s
 * `ActionListGroup` نفسها، تُستدعى هنا مرتين.
 *
 * "التطبيقات" (تفعيل/تعطيل تطبيق كامل، لا مجرد سعر باقة) و"إنشاء" كوبون/باقة جديدة — نموذج ملء
 * حقول من الصفر — مؤجَّلان: `ActionRenderer` اليوم يُشغِّل فقط أفعالاً معاملُها الوحيد مسار
 * (path) يُحل من صفّ قائمة، لا نموذج إنشاء حر. تُبنى لاحقاً كشاشة نموذج مخصّصة.
 */
import { useEffect, useState } from 'react';
import { ActionListGroup } from './ActionRenderer';
import { allActions, fetchCatalog, type AdminAction, type AdminCatalog } from './catalog';
import type { AdminSession } from './api';

export function AdminApps({ session }: { session: AdminSession }) {
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

  const flat = allActions(catalog);
  const byId = (id: string) => flat.find((a) => a.id === id);
  const plansList = byId('billing.list_plans');
  const couponsList = byId('billing.list_coupons');
  const rowActionsFor = (ids: string[]): AdminAction[] =>
    ids.map(byId).filter((a): a is AdminAction => a !== undefined);

  const nothingAvailable = !plansList && !couponsList;

  return (
    <div className="flex flex-col gap-6 p-6">
      <h1 className="text-2xl leading-tight tracking-tight">التطبيقات والأسعار والعروض</h1>

      {nothingAvailable ? (
        <p className="text-sm text-text-secondary">
          حسابك لا يحمل صلاحية القراءة هنا — لا باقات ولا كوبونات لعرضها لك.
        </p>
      ) : null}

      {plansList ? (
        <section className="flex flex-col gap-2">
          <h2 className="text-lg font-semibold">الباقات والأسعار</h2>
          <ActionListGroup session={session} listAction={plansList}
                           rowActions={rowActionsFor(['billing.update_plan', 'billing.plan_availability'])} />
        </section>
      ) : null}

      {couponsList ? (
        <section className="flex flex-col gap-2">
          <h2 className="text-lg font-semibold">الخصومات والعروض (كوبونات)</h2>
          <ActionListGroup session={session} listAction={couponsList}
                           rowActions={rowActionsFor(['billing.update_coupon', 'billing.delete_coupon'])} />
        </section>
      ) : null}
    </div>
  );
}
