/**
 * ONE APP'S SUBSCRIBE FLOW, EXTRACTED SO EVERY LOCKED CARD CAN OFFER IT INLINE — not just نقاط الولاء's
 * own pane.
 *
 * THE DEFECT THIS REPLACES. Every locked card (`Locked.tsx::LockedCard`) sent him to `/store` with
 * a plain link, and «الاشتراك» rebuilt the whole mint-token/3DS-redirect/finish-subscribe sequence
 * for itself. An owner who had just decided to buy the app in front of him was handed a second
 * screen and asked to find it again among every other app — the exact "ten minutes with Meta"
 * mistake `Plans.tsx`'s own header note already diagnoses, now on the buying step itself.
 *
 * NO MORE CARD FORM, NO MORE 3DS REDIRECT (2026-09-24) — this used to mint a `payment_token`
 * straight from the browser against Moyasar (`payment.ts`/`CardForm.tsx`, both retired) and hand
 * it to `subscription.activate`. That never matched TuwaiqPay, the gateway actually live here:
 * TuwaiqPay has no browser-side tokenisation at all, only a hosted checkout link — and worse,
 * `subscription.activate` used to ACTIVATE the subscription the instant any token arrived, never
 * checking whether a charge actually succeeded (fixed at billing-service, base-services v0.25.29,
 * but the console's own card-form path was the thing that could have exploited it). Both retired
 * together: a paid plan now goes through `subscription.checkout_link` (services/operations,
 * `api/v1/subscription.py`'s own docstring), which hands back a real TuwaiqPay pay-link and
 * creates the subscription `incomplete` — billing activates it only once the SAME payment settles
 * through its normal webhook/reconcile seam, never on the strength of a client claim. A free or
 * trial plan skips the link entirely and still goes straight through `subscription.activate` with
 * no token at all — billing-service now creates those directly, no payment question involved.
 *
 * SAME PRODUCT RULES, ONE PLACE. `subscription.activate`/`checkout_link` over billing's own raw
 * routes (WhatsApp-before-paid ordering, enforced only by our own layer) — every one of these was
 * a rule `Plans.tsx` earned from a real incident (see its own header/§ notes) and none of them is
 * repeated here; this hook lifts that logic so a second caller never re-derives it and drifts.
 *
 * A CONSUMER NEEDS THREE THINGS: the plan to buy (`planFor`), whether buying is live at all right
 * now (`live`), and one call to start it (`subscribe`) — free/trial finishes immediately (`notice`
 * carries the receipt), paid navigates the whole page to the real pay-link and never returns here.
 */
import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { action, call, type Catalog } from './catalog';
import { appKey, needsNoPayment, type Plan } from './billingShared';
import type { Session } from './session';
import { useOperatorI18n } from './operator-i18n';
import './subscribe-flow-i18n';

export function useSubscribeFlow(session: Session, catalog: Catalog) {
  const { t } = useOperatorI18n();
  const navigate = useNavigate();
  const [plans, setPlans] = useState<Plan[] | null>(null);
  const [pay, setPay] = useState<{ enabled: boolean; message?: string } | undefined>(undefined);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');

  // OUR PATH, NOT BILLING'S RAW ONE — same fallback order, same reasoning, as `Plans.tsx`'s own
  // `canSubscribe` (WhatsApp-before-paid ordering enforced only by our own route).
  const canSubscribe = action(catalog, 'subscription.activate') ?? action(catalog, 'billing.subscribe');
  const canCheckoutLink = action(catalog, 'subscription.checkout_link');

  useEffect(() => {
    const plansAction = action(catalog, 'billing.plans');
    if (plansAction) {
      call<{ plans: Plan[] }>(session, plansAction)
        .then((x) => setPlans(x.plans ?? []))
        .catch(() => setPlans([]));
    } else {
      setPlans([]);
    }
    const payAction = action(catalog, 'subscription.payment_state');
    if (!payAction) { setPay({ enabled: false, message: '' }); return; }
    call<{ enabled: boolean; message?: string }>(session, payAction)
      .then(setPay)
      .catch(() => setPay({ enabled: false, message: '' }));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [session, catalog]);

  /** Refused before any money moved — the server names the exact next screen
   *  (`redirect_screen`, always "connect" today) rather than a dead-end error toast, on both the
   *  free path and the pay-link path alike (`checkout_link` refuses this exactly the same way). */
  const handleWhatsappGate = (e: unknown): boolean => {
    const code = e instanceof Error ? (e as Error & { code?: string }).code : undefined;
    if (code !== 'WHATSAPP_CONNECTION_REQUIRED') return false;
    navigate('/account?tab=whatsapp', { state: { notice: e instanceof Error ? e.message : '' } });
    return true;
  };

  const finishFreeSubscribe = async (planId: string, quantity = 1) => {
    if (!canSubscribe) return;
    setBusy(true); setError('');
    try {
      const out = await call<{ notice?: string }>(session, canSubscribe,
                                                   { plan_id: planId, quantity });
      setNotice(out?.notice ?? '');
    } catch (e) {
      if (!handleWhatsappGate(e)) setError(e instanceof Error ? e.message : t('subscribeFlow.error.activate'));
    } finally {
      setBusy(false);
    }
  };

  /** THE WHOLE PAGE NAVIGATES AWAY — same as every other real pay-link on this screen
   *  (`BillingStatusPane.tsx`'s own `payByLink`), never a fetch-and-stay. TuwaiqPay's own return
   *  URL lands back on this same screen; nothing here needs to remember a pending state across
   *  that redirect (unlike the old card-form's 3DS round trip) because no local claim was ever
   *  made — the subscription's real status is read fresh from the server on return, same as any
   *  other page load. */
  const startPaidCheckout = async (planId: string, quantity = 1) => {
    if (!canCheckoutLink) return;
    setBusy(true); setError('');
    try {
      const out = await call<{ checkout_url?: string; pay_url?: string; checkout_required?: boolean }>(
        session, canCheckoutLink, { plan_id: planId, quantity });
      const url = out.checkout_url || out.pay_url;
      if (out.checkout_required === false || !url) {
        // A plan the server itself decided needs no link after all (e.g. a coupon zeroed it) —
        // reload rather than guess; the subscription already exists on billing's side.
        setNotice(t('subscribeFlow.checkoutLinkSkipped'));
        setBusy(false);
        return;
      }
      window.location.assign(url);
    } catch (e) {
      setBusy(false);
      if (!handleWhatsappGate(e)) setError(e instanceof Error ? e.message : t('subscribeFlow.error.activate'));
    }
  };

  /** The plan row that grants one app key, or `undefined` while plans have not arrived yet. */
  const planFor = (appFeatureKey: string): Plan | undefined =>
    plans?.find((p) => appKey(p) === appFeatureKey);

  /** Is there anything real to call at all — an action that exists, for a plan that resolved.
   *
   * DELIBERATELY DOES NOT ASK `pay.enabled` EITHER (2026-09-20, the owner's own instruction,
   * still true after the 2026-09-24 rewrite): a locked card sits inside the very screen whose
   * whole job is selling this app — falling back to a link that points at the screen already
   * open is a dead end dressed as a way out, not a safeguard. A genuinely unconfigured gateway
   * still answers honestly the instant `subscribe`/`checkout_link` is actually pressed. */
  const live = (plan: Plan | undefined): boolean =>
    Boolean(plan) && (needsNoPayment(plan!) ? Boolean(canSubscribe) : Boolean(canCheckoutLink));

  const subscribe = (plan: Plan, quantity = 1) => {
    setError('');
    if (!live(plan)) return;
    if (needsNoPayment(plan)) void finishFreeSubscribe(plan.id, quantity);
    else void startPaidCheckout(plan.id, quantity);
  };

  return {
    ready: plans !== null && pay !== undefined,
    planFor, live, subscribe,
    busy, error, notice, unreadNote: pay && !pay.enabled ? (pay.message ?? '') : '',
  };
}
