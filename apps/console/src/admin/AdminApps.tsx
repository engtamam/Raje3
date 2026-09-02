/**
 * التطبيقات والأسعار والعروض — المرحلة ٦، أُعيد بناؤها كبطاقات مقروءة (PlanCards.tsx/
 * CouponCards.tsx) بدل الجدول العام الخام — عمود إنجليزي، حدود مفكوكة كـJSON بعمود واحد، غير
 * صالحة لمشغّل حقيقي. Plans و Coupons صارا تبويبين فرعيين (Segmented) أعلى نفس الشاشة، لا
 * قسمين مكدَّسين تحت بعض — الشريط الجانبي محدود عمداً بـ٥-٦ أقسام (طلب سابق)، فتبويب سابع
 * كامل لم يكن خياراً.
 *
 * كوبون مرتبط بباقة محددة (`plan_id`) — WIRED AGAINST A CONTRACT, NOT A SHIPPED BACKEND YET.
 * base-services confirmed the shape (plan_id on create/update coupon; subscribe() refuses with
 * COUPON_PLAN_MISMATCH on a mismatch, checked before redeem) but it lands in v0.18.0, not yet
 * tagged as this comment is written. Shipping this console build against the CURRENT live
 * billing-service would silently ignore `plan_id` — an operator would believe a discount was
 * scoped to one plan while it stayed global, the exact silent-money-lie the REFUSE design exists
 * to prevent, one layer up. DO NOT `deploy_ship console` past this point until
 * `platform/`'s submodule pin is bumped to v0.18.0 — see this repo's own commit history for when
 * that lands; ship immediately after, not before.
 *
 * "التطبيقات" (تفعيل/تعطيل تطبيق كامل، لا مجرد سعر باقة) و"إنشاء" باقة جديدة كليّاً — مؤجَّلان،
 * يحتاجان نموذجاً أعقد (أسعار متعددة، حدود من الصفر). تعديل/إنشاء كوبون صار حقيقياً (هذا الملف).
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
  const updatePlanAction = byId('billing.update_plan');
  const createCouponAction = byId('billing.create_coupon');
  const updateCouponAction = byId('billing.update_coupon');
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
          ? <PlansPane session={session} listAction={plansList} availabilityAction={availabilityAction}
                      updateAction={updatePlanAction} />
          : <p className="text-sm text-text-secondary">حسابك لا يحمل صلاحية القراءة هنا.</p>
      ) : null}

      {sub === 'coupons' ? (
        couponsList
          ? <CouponsPane session={session} listAction={couponsList} plansListAction={plansList}
                        createAction={createCouponAction} updateAction={updateCouponAction}
                        deleteAction={deleteCouponAction} />
          : <p className="text-sm text-text-secondary">حسابك لا يحمل صلاحية القراءة هنا.</p>
      ) : null}
    </div>
  );
}

function PlansPane({ session, listAction, availabilityAction, updateAction }: {
  session: AdminSession; listAction: AdminAction; availabilityAction?: AdminAction;
  updateAction?: AdminAction;
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
                    updateAction={updateAction} plans={rows as any} onReload={reload} />;
}

function CouponsPane({ session, listAction, plansListAction, createAction, updateAction, deleteAction }: {
  session: AdminSession; listAction: AdminAction; plansListAction?: AdminAction;
  createAction?: AdminAction; updateAction?: AdminAction; deleteAction?: AdminAction;
}) {
  const [rows, setRows] = useState<unknown[] | 'loading' | 'failed'>('loading');
  // Plans are fetched here too, independently of PlansPane's own copy — this pane needs only
  // {id, name} for the coupon form's plan picker and the card's own plan-name lookup, and the two
  // sub-tabs are never both mounted at once (Segmented), so there is nothing to keep in sync.
  const [plans, setPlans] = useState<{ id: string; name: string }[]>([]);

  const reload = () => {
    setRows('loading');
    req<{ coupons: unknown[] }>(listAction.path, 'GET', undefined, session.access_token)
      .then((body) => setRows(body.coupons))
      .catch(() => setRows('failed'));
  };

  useEffect(reload, [listAction, session]);
  useEffect(() => {
    if (!plansListAction) return;
    req<{ plans: { id: string; name: string }[] }>(
      `${plansListAction.path}?include_hidden=true`, 'GET', undefined, session.access_token,
    ).then((body) => setPlans(body.plans.map((p) => ({ id: p.id, name: p.name })))).catch(() => setPlans([]));
  }, [plansListAction, session]);

  if (rows === 'loading') return <p className="text-sm text-text-secondary">جارٍ التحميل…</p>;
  if (rows === 'failed') return <p role="alert" className="text-danger text-sm">تعذّرت قراءة الكوبونات.</p>;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any -- same reason as PlansPane above.
  return <CouponCards session={session} createAction={createAction} updateAction={updateAction}
                      deleteAction={deleteAction} coupons={rows as any} plans={plans} onReload={reload} />;
}
