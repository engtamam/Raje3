/**
 * التطبيقات والأسعار والعروض — المرحلة 6، أُعيد بناؤها كبطاقات مقروءة (PlanCards.tsx/
 * CouponCards.tsx) بدل الجدول العام الخام — عمود إنجليزي، حدود مفكوكة كـJSON بعمود واحد، غير
 * صالحة لمشغّل حقيقي. Plans و Coupons صارا تبويبين فرعيين (Segmented) أعلى نفس الشاشة، لا
 * قسمين مكدَّسين تحت بعض — الشريط الجانبي محدود عمداً بـ5-6 أقسام (طلب سابق)، فتبويب سابع
 * كامل لم يكن خياراً.
 *
 * كوبون مرتبط بتطبيق محدد (`plan_id`) — shipped against billing-service v0.18.0 (submodule pin
 * bumped, digest confirmed carrying plan_id + COUPON_PLAN_MISMATCH). Held for exactly this reason
 * until the bump landed, to avoid the console silently sending `plan_id` to a backend that ignores
 * it — an operator believing a discount was app-scoped while it stayed global.
 *
 * "التطبيقات" (تفعيل/تعطيل تطبيق كامل، لا مجرد سعر تطبيق) و"إنشاء" تطبيق جديد كليّاً — مؤجَّلان،
 * يحتاجان نموذجاً أعقد (أسعار متعددة، حدود من الصفر). تعديل/إنشاء كوبون صار حقيقياً (هذا الملف).
 */
import { useEffect, useState } from 'react';
import { Segmented } from '../rj-ui/Segmented';
import { PlanCards } from './PlanCards';
import { CouponCards } from './CouponCards';
import { DiscountRuleCards } from './DiscountRuleCards';
import { ShopCouponSettings } from './ShopCouponSettings';
import { allActions, fetchCatalog, type AdminAction, type AdminCatalog } from './catalog';
import { req, type AdminSession } from './api';
import { NoActionAvailable } from './NoActionAvailable';

type SubTab = 'plans' | 'coupons' | 'discount_rules' | 'shop_coupons';

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
  const rulesList = byId('billing.list_discount_rules');
  const createRuleAction = byId('billing.create_discount_rule');
  const updateRuleAction = byId('billing.update_discount_rule');
  const deleteRuleAction = byId('billing.delete_discount_rule');
  // SHOP-TO-SHOP COUPONS — a different engine entirely from billing's own ad-hoc coupon codes
  // above (core/coupons.py, operations-service). Kept as its own sub-tab specifically so the two
  // "كوبون" concepts are never mixed on one screen.
  const shopCouponSettingsGet = byId('operations.coupon_settings_get');
  const shopCouponSettingsSet = byId('operations.coupon_settings_set');
  const shopCouponLookup = byId('operations.coupon_tenant_lookup');
  const shopCouponOverrideGet = byId('operations.coupon_override_get');
  const shopCouponOverrideSet = byId('operations.coupon_override_set');
  // SCOPED TO billing-service SPECIFICALLY, not `byId` — `operator.get_config`/`set_config` are
  // declared by EVERY service that carries a runtime-editable setting (see AdminConfig.tsx's own
  // per-service grouping), so the first match across the whole flat catalog could just as easily
  // be reminders' or whatsapp-assistant's own config route. `PLAN_CREDIT_PERCENT` is billing's own
  // knob (deploy/seed/plans.json's own note on it), so this reads billing-service's row by name.
  const billingSvc = catalog.services.find((s) => s.service === 'billing-service');
  const configGetAction = billingSvc?.actions.find((a) => a.id === 'operator.get_config');
  const configSetAction = billingSvc?.actions.find((a) => a.id === 'operator.set_config');

  if (!plansList && !couponsList && !rulesList) {
    return <NoActionAvailable catalog={catalog} permissionTitle="حسابك لا يحمل صلاحية القراءة هنا — لا تطبيقات ولا كوبونات ولا قواعد خصم لعرضها لك." />;
  }

  return (
    <div className="flex flex-col gap-4 p-6">
      <h1 className="text-2xl leading-tight tracking-tight">التطبيقات والأسعار والعروض</h1>

      <Segmented ariaLabel="القسم" value={sub} onChange={setSub}
                options={[
                  { value: 'plans', label: 'التطبيقات والأسعار' },
                  { value: 'coupons', label: 'الخصومات والعروض' },
                  { value: 'discount_rules', label: 'قواعد الخصم المتسلسل' },
                  { value: 'shop_coupons', label: 'كوبونات محل لمحل' },
                ]} />

      {sub === 'plans' ? (
        plansList
          ? <PlansPane session={session} listAction={plansList} availabilityAction={availabilityAction}
                      updateAction={updatePlanAction}
                      configGetAction={configGetAction} configSetAction={configSetAction} />
          : <p className="text-sm text-text-secondary">حسابك لا يحمل صلاحية القراءة هنا.</p>
      ) : null}

      {sub === 'coupons' ? (
        couponsList
          ? <CouponsPane session={session} listAction={couponsList} plansListAction={plansList}
                        createAction={createCouponAction} updateAction={updateCouponAction}
                        deleteAction={deleteCouponAction} />
          : <p className="text-sm text-text-secondary">حسابك لا يحمل صلاحية القراءة هنا.</p>
      ) : null}

      {sub === 'discount_rules' ? (
        rulesList
          ? <DiscountRulesPane session={session} listAction={rulesList}
                               createAction={createRuleAction} updateAction={updateRuleAction}
                               deleteAction={deleteRuleAction} />
          : <p className="text-sm text-text-secondary">حسابك لا يحمل صلاحية القراءة هنا.</p>
      ) : null}

      {sub === 'shop_coupons' ? (
        <ShopCouponSettings session={session}
                            settingsGetAction={shopCouponSettingsGet} settingsSetAction={shopCouponSettingsSet}
                            lookupAction={shopCouponLookup} overrideGetAction={shopCouponOverrideGet}
                            overrideSetAction={shopCouponOverrideSet} />
      ) : null}
    </div>
  );
}

function PlansPane({ session, listAction, availabilityAction, updateAction, configGetAction, configSetAction }: {
  session: AdminSession; listAction: AdminAction; availabilityAction?: AdminAction;
  updateAction?: AdminAction; configGetAction?: AdminAction; configSetAction?: AdminAction;
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
  if (rows === 'failed') return <p role="alert" className="text-danger text-sm">تعذّرت قراءة التطبيقات.</p>;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any -- the catalog's own AdminAction
  // carries no response schema (only request params) — see catalog.ts's own note on why.
  return <PlanCards session={session} listAction={listAction} availabilityAction={availabilityAction}
                    updateAction={updateAction} plans={rows as any} onReload={reload}
                    configGetAction={configGetAction} configSetAction={configSetAction} />;
}

function CouponsPane({ session, listAction, plansListAction, createAction, updateAction, deleteAction }: {
  session: AdminSession; listAction: AdminAction; plansListAction?: AdminAction;
  createAction?: AdminAction; updateAction?: AdminAction; deleteAction?: AdminAction;
}) {
  const [rows, setRows] = useState<unknown[] | 'loading' | 'failed'>('loading');
  // Plans are fetched here too, independently of PlansPane's own copy — this pane needs only
  // {id, name} for the coupon form's plan picker and the card's own plan-name lookup, and the two
  // sub-tabs are never both mounted at once (Segmented), so there is nothing to keep in sync.
  const [plans, setPlans] = useState<{ id: string; name: string }[] | 'loading' | 'failed'>('loading');

  const reload = () => {
    setRows('loading');
    req<{ coupons: unknown[] }>(listAction.path, 'GET', undefined, session.access_token)
      .then((body) => setRows(body.coupons))
      .catch(() => setRows('failed'));
  };

  useEffect(reload, [listAction, session]);
  useEffect(() => {
    if (!plansListAction) return;
    setPlans('loading');
    req<{ plans: { id: string; name: string }[] }>(
      `${plansListAction.path}?include_hidden=true`, 'GET', undefined, session.access_token,
    ).then((body) => setPlans(body.plans.map((p) => ({ id: p.id, name: p.name }))))
      .catch(() => setPlans('failed'));
  }, [plansListAction, session]);

  if (rows === 'loading') return <p className="text-sm text-text-secondary">جارٍ التحميل…</p>;
  if (rows === 'failed') return <p role="alert" className="text-danger text-sm">تعذّرت قراءة الكوبونات.</p>;
  if (plans === 'failed') return <p role="alert" className="text-danger text-sm">تعذّرت قراءة الخطط.</p>;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any -- same reason as PlansPane above.
  return <CouponCards session={session} createAction={createAction} updateAction={updateAction}
                      deleteAction={deleteAction} coupons={rows as any}
                      plans={plans === 'loading' ? [] : plans} onReload={reload} />;
}

function DiscountRulesPane({ session, listAction, createAction, updateAction, deleteAction }: {
  session: AdminSession; listAction: AdminAction;
  createAction?: AdminAction; updateAction?: AdminAction; deleteAction?: AdminAction;
}) {
  const [rows, setRows] = useState<unknown[] | 'loading' | 'failed'>('loading');

  const reload = () => {
    setRows('loading');
    req<{ discount_rules: unknown[] }>(listAction.path, 'GET', undefined, session.access_token)
      .then((body) => setRows(body.discount_rules))
      .catch(() => setRows('failed'));
  };

  useEffect(reload, [listAction, session]);

  if (rows === 'loading') return <p className="text-sm text-text-secondary">جارٍ التحميل…</p>;
  if (rows === 'failed') return <p role="alert" className="text-danger text-sm">تعذّرت قراءة قواعد الخصم.</p>;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any -- same reason as PlansPane above.
  return <DiscountRuleCards session={session} createAction={createAction} updateAction={updateAction}
                            deleteAction={deleteAction} rules={rows as any} onReload={reload} />;
}
