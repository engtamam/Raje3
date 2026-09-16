/**
 * Real billing for the launcher's own app-details window — subscribe, cancel, undo-cancel,
 * cross-app discounts. The SAME real logic `screens/Plans.tsx` already has (`choose`/
 * `finishSubscribe`/`cancelApp`/`undoCancel`/`cascadeTargets`), reused rather than reinvented:
 * this is real money moving through a real, tested 3DS card-tokenisation flow
 * (`CardForm`/`payment.ts`/`pendingPayment.ts`), and a second copy of that logic is exactly the
 * kind of drift that ends in a double-charge or a silent refusal.
 *
 * NO BASE — the base subscription concept was retired 2026-09-10 (purged from `Plans.tsx` itself
 * the same day this file was written).
 *
 * CAPACITY IS HERE TOO NOW (2026-09-16, second pass) — seats/branches moved into the launcher's
 * own «كل التطبيقات» shelf (never «تطبيقاتي»: capacity is not a section a role opens, so it has
 * no `AppRow`/nav-section home there). The stepper UI itself (`CapacityAddonCard`) is still
 * `Plans.tsx`'s own component, reused as-is — only the DATA plumbing lives here now, same reuse
 * discipline as `choose`/`cancelApp` above.
 */
import { useEffect, useMemo, useState } from 'react';
import { action, call, type Catalog } from '../catalog';
import { appKey, canBuy, kindOf, type Plan, type Subscription } from '../billingShared';
import { canMintToken, confirmToken } from '../payment';
import { takePending, type PendingPayment } from '../pendingPayment';
import { riyals } from '../money';
import type { Session } from '../session';

/** Halalas → «120 ريال/شهريًا» — the same monthly-or-first-price rule `Plans.tsx`'s own `monthly()`
 *  reads, kept here as a pure read rather than importing an unexported helper. */
export function monthlyPriceOf(plan: Plan): { amount: string; currency: string } | null {
  const price = plan.prices?.find((x) => x.interval === 'month') ?? plan.prices?.[0];
  if (!price?.amount_minor) return null;
  return { amount: riyals(price.amount_minor), currency: price.currency ?? 'SAR' };
}

/** The included-AI-credit halalas on the SAME price row `monthlyPriceOf` reads — `undefined` for
 *  every plan but بوت خدمة العملاء الذكي (billing-service v0.19.24's own `included_credit_minor`,
 *  see `screens/Plans.tsx`'s own `Price` type). Never zero-guessed: absence here means "this plan
 *  carries no such allowance", the exact same posture `Plans.tsx`'s own `AppCard` already takes. */
export function includedAiCreditOf(plan: Plan): number | undefined {
  const price = plan.prices?.find((x) => x.interval === 'month') ?? plan.prices?.[0];
  return price?.included_credit_minor;
}

function renewalDay(epoch: number | null | undefined): string {
  return epoch
    ? new Date(epoch * 1000).toLocaleDateString('ar-SA-u-nu-latn-ca-gregory',
                                                 { day: 'numeric', month: 'long' })
    : '';
}

type DiscountInfo = { percent: number; owning_key: string };

export function useAppBilling(session: Session, catalog: Catalog) {
  const [plans, setPlans] = useState<Plan[] | null | undefined>(undefined);
  const [subs, setSubs] = useState<Subscription[] | null | undefined>(undefined);
  const [discountPreviews, setDiscountPreviews] = useState<Record<string, DiscountInfo>>({});
  const [potentialDiscounts, setPotentialDiscounts] = useState<Record<string, DiscountInfo>>({});
  const [pay, setPay] = useState<{ enabled: boolean } | undefined>(undefined);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [cancelingAppId, setCancelingAppId] = useState('');
  const [appCancelError, setAppCancelError] = useState('');
  const [undoingAppCancelId, setUndoingAppCancelId] = useState('');
  const [undoCancelError, setUndoCancelError] = useState('');
  const [cardFormPending, setCardFormPending] = useState<PendingPayment | null>(null);
  const [resolvingReturn, setResolvingReturn] = useState(false);
  const [capacityBusyPlanId, setCapacityBusyPlanId] = useState('');
  const [capacityError, setCapacityError] = useState('');

  const canBrowse = action(catalog, 'billing.plans');
  const canSubscribe = action(catalog, 'subscription.activate') ?? action(catalog, 'billing.subscribe');

  const load = () => {
    if (canBrowse) {
      call<{ plans: Plan[] }>(session, canBrowse)
        .then((x) => setPlans((x.plans ?? []).filter((p) => p.active !== false && p.listed !== false)))
        .catch(() => setPlans(null));
    } else {
      setPlans([]);
    }
    const mine = action(catalog, 'billing.my_subscriptions');
    if (mine) {
      call<{ subscriptions: Subscription[] }>(session, mine)
        .then((x) => setSubs(x.subscriptions ?? []))
        .catch(() => setSubs(null));
    } else {
      setSubs(null);
    }
    const preview = action(catalog, 'billing.discount_preview');
    if (preview) {
      call<{ previews: Record<string, DiscountInfo>; potential?: Record<string, DiscountInfo> }>(session, preview)
        .then((x) => { setDiscountPreviews(x.previews ?? {}); setPotentialDiscounts(x.potential ?? {}); })
        .catch(() => { setDiscountPreviews({}); setPotentialDiscounts({}); });
    }
  };

  useEffect(load, [session, catalog]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    const a = action(catalog, 'subscription.payment_state');
    if (!a) { setPay({ enabled: false }); return; }
    call<{ enabled: boolean }>(session, a).then(setPay).catch(() => setPay({ enabled: false }));
  }, [session, catalog]);

  // THE SAME FIXED SCALE `Wallet.tsx`'s OWN `unitsLabel` READS — one live rate, read once here
  // rather than once per app tile, so a shop scrolling the launcher never sees two different
  // "unit" conversions for the same halala mid-scroll.
  const [unitsPerHalala, setUnitsPerHalala] = useState<number | null>(null);
  useEffect(() => {
    const a = action(catalog, 'whatsapp_assistant.pricing_current');
    if (!a) return;
    call<{ ai_unit_units_per_halala: number }>(session, a)
      .then((x) => setUnitsPerHalala(x.ai_unit_units_per_halala))
      .catch(() => {});
  }, [session, catalog]);

  const apps = useMemo(() => (plans ?? []).filter((p) => kindOf(p) === 'app'), [plans]);
  const appSubs = useMemo(() => (subs ?? []).filter((s) => apps.some((p) => p.id === s.plan_id)), [subs, apps]);
  const activeAppSubs = useMemo(
    () => appSubs.filter((s) => s.status !== 'canceled' && !s.cancel_at_period_end), [appSubs],
  );

  const PREREQ_KEYS = ['feature.visit', 'feature.bookings'];
  const DEPENDENT_KEYS = ['feature.loyalty', 'feature.rating', 'feature.insights.engine', 'feature.campaigns'];

  const cascadeTargets = (subId: string): Plan[] => {
    const cancelledPlan = apps.find((p) => appSubs.some((s) => s.id === subId && s.plan_id === p.id));
    const cancelledKey = cancelledPlan ? appKey(cancelledPlan) : '';
    if (!PREREQ_KEYS.includes(cancelledKey)) return [];
    const stillHasPrereq = PREREQ_KEYS.some((k) => {
      if (k === cancelledKey) return false;
      const p = apps.find((pp) => appKey(pp) === k);
      return p ? activeAppSubs.some((s) => s.plan_id === p.id && s.id !== subId) : false;
    });
    if (stillHasPrereq) return [];
    return activeAppSubs
      .filter((s) => s.id !== subId)
      .map((s) => apps.find((p) => p.id === s.plan_id))
      .filter((p): p is Plan => p != null && DEPENDENT_KEYS.includes(appKey(p)));
  };

  const cancelApp = async (subId: string) => {
    const a = action(catalog, 'billing.cancel');
    if (!a) return;
    setCancelingAppId(subId); setAppCancelError('');
    try {
      const targets = cascadeTargets(subId);
      await call(session, a, { id: subId });
      await Promise.all(targets.map((p) => {
        const s = appSubs.find((x) => x.plan_id === p.id);
        return s ? call(session, a, { id: s.id }) : Promise.resolve();
      }));
      load();
    } catch (e) {
      setAppCancelError(e instanceof Error ? e.message : 'تعذّر إيقاف تجديد هذا التطبيق.');
    } finally {
      setCancelingAppId('');
    }
  };

  const capacity = useMemo(() => (plans ?? []).filter((p) => kindOf(p) === 'capacity'), [plans]);
  const capacitySubs = useMemo(
    () => (subs ?? []).filter((s) => capacity.some((p) => p.id === s.plan_id))
      .filter((s) => s.status !== 'canceled' && !s.cancel_at_period_end),
    [subs, capacity],
  );

  /** THE CAPACITY STEPPER'S +/- — same real action `Plans.tsx`'s own `changeCapacityQuantity`
   *  calls (`billing.change_plan`), never re-derived: raising it charges the prorated difference
   *  now, lowering it schedules the smaller amount for the next renewal. */
  const changeCapacityQuantity = async (plan: Plan, sub: Subscription, quantity: number) => {
    const a = action(catalog, 'billing.change_plan');
    if (!a || quantity < 1) return;
    setCapacityBusyPlanId(plan.id); setCapacityError('');
    try {
      await call(session, a, { id: sub.id, plan_id: plan.id, quantity });
      load();
    } catch (e) {
      setCapacityError(e instanceof Error ? e.message : 'تعذّر تغيير الكمية.');
    } finally {
      setCapacityBusyPlanId('');
    }
  };

  const undoCancel = async (subId: string) => {
    const a = action(catalog, 'billing.undo_cancel');
    if (!a) return;
    setUndoingAppCancelId(subId); setUndoCancelError('');
    try {
      await call(session, a, { id: subId });
      load();
    } catch (e) {
      setUndoCancelError(e instanceof Error ? e.message : 'تعذّر التراجع عن إيقاف التجديد.');
    } finally {
      setUndoingAppCancelId('');
    }
  };

  const choose = (p: Plan) => {
    setError('');
    if (!canSubscribe) return;
    if (!canBuy({ hasAction: true, gatewayEnabled: Boolean(pay?.enabled), canMint: canMintToken })) return;
    setCardFormPending({ kind: 'subscribe', planId: p.id, quantity: 1 });
  };

  const finishSubscribe = async (planId: string, payment_token: string, quantity = 1) => {
    if (!canSubscribe) return;
    setBusy(true); setError('');
    try {
      const out = await call<{ notice?: string }>(session, canSubscribe, { plan_id: planId, payment_token, quantity });
      setNotice(out?.notice ?? '');
      setCardFormPending(null);
      load();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'تعذّر تفعيل الاشتراك.');
    } finally {
      setBusy(false);
    }
  };

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const tokenId = params.get('id');
    const pending = takePending();
    if (!tokenId || !pending || pending.kind !== 'subscribe') return;
    setResolvingReturn(true);
    confirmToken(tokenId)
      .then((result) => {
        if (result.kind === 'error') { setError(result.message); return; }
        if (result.kind !== 'token') return;
        return finishSubscribe(pending.planId, result.token, pending.quantity ?? 1);
      })
      .finally(() => {
        setResolvingReturn(false);
        const url = new URL(window.location.href);
        for (const k of ['id', 'status', 'message']) url.searchParams.delete(k);
        window.history.replaceState({}, '', url.toString());
      });
    // Runs once, on mount only.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // ONE LOOKUP, BY THE SAME `feature.*` KEY `launcherCatalog.ts`'s `billingKey` already carries —
  // so a tile never has to re-derive `appKey(plan)` itself, and can never disagree with the hook
  // about which plan/subscription is "its own".
  const planByKey = useMemo(() => {
    const m: Record<string, Plan> = {};
    for (const p of apps) { const k = appKey(p); if (k) m[k] = p; }
    return m;
  }, [apps]);
  const subByPlanId = useMemo(() => {
    const m: Record<string, Subscription> = {};
    for (const s of appSubs) if (s.plan_id) m[s.plan_id] = s;
    return m;
  }, [appSubs]);

  return {
    subs, discountPreviews, potentialDiscounts, pay, busy, error, notice,
    cancelingAppId, appCancelError, undoingAppCancelId, undoCancelError,
    cardFormPending, setCardFormPending, resolvingReturn,
    canSubscribe: Boolean(canSubscribe), sellableBase: Boolean(canSubscribe && pay?.enabled && canMintToken),
    choose, finishSubscribe, cancelApp, undoCancel, cascadeTargets, renewalDay,
    planByKey, subByPlanId, unitsPerHalala,
    capacity, capacitySubs, capacityBusyPlanId, capacityError, changeCapacityQuantity,
  };
}
