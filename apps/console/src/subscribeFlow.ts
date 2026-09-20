/**
 * ONE APP'S SUBSCRIBE FLOW, EXTRACTED SO EVERY LOCKED CARD CAN OFFER IT INLINE — not just نقاطي's
 * own pane.
 *
 * THE DEFECT THIS REPLACES. Every locked card (`Locked.tsx::LockedCard`) sent him to `/store` with
 * a plain link, and «الاشتراك» rebuilt the whole mint-token/3DS-redirect/finish-subscribe sequence
 * for itself. An owner who had just decided to buy the app in front of him was handed a second
 * screen and asked to find it again among every other app — the exact "ten minutes with Meta"
 * mistake `Plans.tsx`'s own header note already diagnoses, now on the buying step itself.
 *
 * SAME RULES, ONE PLACE. `subscription.activate` over `billing.subscribe` (WhatsApp-before-paid
 * ordering), `subscription.payment_state` before ever drawing a live buy button, `pendingPayment`'s
 * remember/take pair across the 3DS redirect, `finishSubscribe`'s own server-sentence handling —
 * every one of these was a rule `Plans.tsx` earned from a real incident (see its own header/§ notes)
 * and none of them is repeated here; this hook is `Plans.tsx`'s own subscribe half, unchanged,
 * lifted so a second caller never re-derives it and quietly drifts from it.
 *
 * A CONSUMER NEEDS FOUR THINGS: the plan to buy (`planFor`), whether buying is live at all right
 * now (`live`), one call to start it (`subscribe`), and the form to render while it is open
 * (`cardForm`) — everything else (tokenising, the redirect return, the notice) this hook owns.
 */
import { useEffect, useState } from 'react';
import { confirmToken } from './payment';
import { takePending, type PendingPayment } from './pendingPayment';
import { action, call, type Catalog } from './catalog';
import { appKey, type Plan } from './billingShared';
import type { Session } from './session';
import { useOperatorI18n } from './operator-i18n';
import './subscribe-flow-i18n';

export function useSubscribeFlow(session: Session, catalog: Catalog) {
  const { t } = useOperatorI18n();
  const [plans, setPlans] = useState<Plan[] | null>(null);
  const [pay, setPay] = useState<{ enabled: boolean; message?: string } | undefined>(undefined);
  const [cardFormPending, setCardFormPending] = useState<PendingPayment | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');

  // OUR PATH, NOT BILLING'S RAW ONE — same fallback order, same reasoning, as `Plans.tsx`'s own
  // `canSubscribe` (WhatsApp-before-paid ordering enforced only by our own route).
  const canSubscribe = action(catalog, 'subscription.activate') ?? action(catalog, 'billing.subscribe');

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

  const finishSubscribe = async (planId: string, payment_token: string, quantity = 1) => {
    if (!canSubscribe) return;
    setBusy(true); setError('');
    try {
      const out = await call<{ notice?: string }>(session, canSubscribe,
                                                   { plan_id: planId, payment_token, quantity });
      setNotice(out?.notice ?? '');
      setCardFormPending(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : t('subscribeFlow.error.activate'));
    } finally {
      setBusy(false);
    }
  };

  // THE RETURN FROM 3DS — same guard as `Plans.tsx`'s own effect: no pending payment, nothing to
  // do, so a bookmark or refresh of this URL replays nothing.
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const tokenId = params.get('id');
    const pending = takePending();
    if (!tokenId || !pending || pending.kind !== 'subscribe') return;
    confirmToken(tokenId)
      .then((result) => {
        if (result.kind === 'error') { setError(result.message); return; }
        if (result.kind !== 'token') return;
        return finishSubscribe(pending.planId, result.token, pending.quantity ?? 1);
      })
      .finally(() => {
        const url = new URL(window.location.href);
        for (const k of ['id', 'status', 'message']) url.searchParams.delete(k);
        window.history.replaceState({}, '', url.toString());
      });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  /** The plan row that grants one app key, or `undefined` while plans have not arrived yet. */
  const planFor = (appFeatureKey: string): Plan | undefined =>
    plans?.find((p) => appKey(p) === appFeatureKey);

  /** Is there anything real to call at all — an action that exists, for a plan that resolved.
   *
   * DELIBERATELY DOES NOT ASK `canBuy`'s payment-readiness half (gatewayEnabled/canMintToken)
   * ANY MORE (2026-09-20, the owner's own instruction). A locked card sits inside the very
   * screen whose whole job is selling this app — falling back to a link that points at the
   * screen already open is a dead end dressed as a way out, not a safeguard. The card form
   * ALREADY handles an unready gateway gracefully: `mintPaymentToken`/`confirmToken`
   * (`payment.ts`) return `NO_CARD_FORM` — "لن تُحسب عليك أي رسوم حتى ذلك الحين" — the instant
   * minting is attempted, so a shop that presses "اشترك الآن" with no live gateway sees that
   * respectful sentence at the one moment it is actually true (trying to pay), not a redirect
   * that says nothing about why. */
  const live = (plan: Plan | undefined): boolean =>
    Boolean(canSubscribe) && Boolean(plan);

  const subscribe = (plan: Plan, quantity = 1) => {
    setError('');
    if (!live(plan)) return;
    setCardFormPending({ kind: 'subscribe', planId: plan.id, quantity });
  };

  return {
    ready: plans !== null && pay !== undefined,
    planFor, live, subscribe,
    cardFormPending, setCardFormPending, finishSubscribe,
    busy, error, notice, unreadNote: pay && !pay.enabled ? (pay.message ?? '') : '',
  };
}
