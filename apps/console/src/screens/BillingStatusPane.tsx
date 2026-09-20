/**
 * «حسابي ← الفوترة» — real, professional, interactive, once (2026-09-20, the owner's own
 * instruction). Two real gaps this redesign closes:
 *
 * 1. A LOCKED APP'S PAY-LINK, MANUAL — TuwaiqPay (the live gateway, `deploy/services/
 *    billing-service.values.yaml`) has no card-on-file/recurring-charge support (see that file's
 *    own note beside `WALLET_RENEWAL_FUND`). A past-due subscription could only be fixed by
 *    updating a card THIS BUILD CANNOT ACTUALLY MINT (`payment.ts`'s own `canMintToken` — no
 *    publishable key set — `NO_CARD_FORM` fires the instant it is tried). `billing.invoice_pay_link`
 *    (already a real, wired action — creates a hosted checkout link for an EXISTING unpaid
 *    invoice) is now offered alongside it, so a past-due shop on TuwaiqPay has a real way to pay
 *    regardless of whether card tokenisation is configured.
 * 2. EVERY SUBSCRIBED APP, SHOWN, WITH ITS OWN STOP-RENEWAL CONTROL — reuses `useAppBilling.ts`
 *    (the SAME hook the launcher's app-details window already runs real money through) and
 *    `AppDetailsModal.tsx`'s own extracted `RenewalControl` (the SAME confirm-step/cascade-warning
 *    component, not a second hand-copied one) — this pane never re-implements cancel/undo-cancel.
 *
 * WHAT THIS DELIBERATELY DOES NOT SHOW YET: a combined "your next renewal totals X" figure.
 * `Subscription.price_snapshot`/the plan's list price is NOT what a shop with an active coupon or
 * cross-app discount rule is actually charged — that computation exists only inside the real
 * invoice-cutting path today, with no side-effect-free preview endpoint to read it from. Showing
 * a total built from list prices alone would be a wrong number dressed as a real one; per-app
 * price is not shown here for the same reason. Flagged to base-services (2026-09-20) for a real
 * `GET .../subscriptions/renewal-preview` endpoint — wire the total in once that lands, never
 * before.
 */
import { useEffect, useState } from 'react';
import { Button } from '../rj-ui/Button';
import { Card } from '../rj-ui/Card';
import { Badge } from '../rj-ui/Badge';
import { action, call, type Catalog } from '../catalog';
import { canMintToken, confirmToken } from '../payment';
import { takePending } from '../pendingPayment';
import type { Subscription } from '../billingShared';
import { useAppBilling } from '../launcher/useAppBilling';
import { RenewalControl } from '../launcher/AppDetailsModal';
import { CardForm } from './CardForm';
import type { Session } from '../session';
import { useOperatorI18n } from '../operator-i18n';
import './billing-status-i18n';

interface OpenInvoice {
  id: string;
  status?: string;
  total_minor?: number;
  currency?: string;
}

export function BillingStatusPane({ session, catalog }: { session: Session; catalog: Catalog }) {
  const { t } = useOperatorI18n();
  const billing = useAppBilling(session, catalog);

  const [subs, setSubs] = useState<Subscription[] | null | undefined>(undefined);
  const [openInvoice, setOpenInvoice] = useState<OpenInvoice | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [cardFormOpen, setCardFormOpen] = useState<string | null>(null);
  const [resolvingReturn, setResolvingReturn] = useState(false);
  const [payLinkBusy, setPayLinkBusy] = useState(false);
  const [renewingSubId, setRenewingSubId] = useState('');
  const [renewError, setRenewError] = useState('');

  const load = () => {
    const a = action(catalog, 'billing.my_subscriptions');
    if (!a) { setSubs(null); return; }
    call<{ subscriptions: Subscription[] }>(session, a)
      .then((x) => setSubs(x.subscriptions ?? []))
      .catch(() => setSubs(null));
  };
  useEffect(load, [session, catalog]); // eslint-disable-line react-hooks/exhaustive-deps

  const pastDueSub = (subs ?? []).find((s) => s.status === 'past_due');

  // THE ONE INVOICE A PAY-LINK CAN ACTUALLY TARGET — `billing.invoice_pay_link` refuses (409
  // INVOICE_NOT_PAYABLE) against anything but a real open/partially-paid invoice, so this reads
  // exactly that before ever offering the button, never guessed from the subscription alone.
  useEffect(() => {
    if (!pastDueSub) { setOpenInvoice(null); return; }
    const a = action(catalog, 'billing.my_invoices');
    if (!a) { setOpenInvoice(null); return; }
    call<{ invoices: OpenInvoice[] }>(session, a, { subscription_id: pastDueSub.id })
      .then((x) => {
        const open = (x.invoices ?? []).find((i) => i.status === 'open' || i.status === 'partially_paid');
        setOpenInvoice(open ?? null);
      })
      .catch(() => setOpenInvoice(null));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pastDueSub?.id, session, catalog]);

  const payByLink = async () => {
    const a = action(catalog, 'billing.invoice_pay_link');
    if (!a || !openInvoice) return;
    setPayLinkBusy(true); setError('');
    try {
      const res = await call<{ checkout_url?: string; pay_url?: string }>(
        session, a, { id: openInvoice.id, return_url: window.location.href });
      const url = res.pay_url || res.checkout_url;
      if (url) window.location.assign(url);
    } catch (e) {
      setError(e instanceof Error ? e.message : t('billingStatus.payLinkFailed'));
    } finally {
      setPayLinkBusy(false);
    }
  };

  /** «جدّد الآن» — the SAME real early-renewal mechanism the WhatsApp renewal Flow's own "جدد
   *  الآن" button already calls (`adapters/renewal_provider.py::renew_now`), reached here through
   *  `subscription.renew_now` (operations' own route, added 2026-09-20 — this action never
   *  existed on the console before). Forces THIS ONE subscription's billing cycle right now and
   *  opens the resulting pay-link — never the automatic sweep, which fires on its own schedule
   *  regardless. Exists because TuwaiqPay has no card-on-file/recurring-charge support: a shop on
   *  it has no other way to pay a cycle before its sweep-scheduled date. */
  const renewNow = async (subId: string) => {
    const a = action(catalog, 'subscription.renew_now');
    if (!a) return;
    setRenewingSubId(subId); setRenewError('');
    try {
      const res = await call<{ pay_url?: string }>(session, a, { sub_id: subId });
      if (res.pay_url) window.location.assign(res.pay_url);
    } catch (e) {
      setRenewError(e instanceof Error ? e.message : t('billingStatus.renewNowFailed'));
    } finally {
      setRenewingSubId('');
    }
  };

  /** «تحديث بطاقة الدفع» — the one control that closes the involuntary-churn loop: the
   *  subscription's own dunning sweep keeps retrying the SAME stored token forever, and this is
   *  the only way that token can ever change. */
  const finishUpdatePaymentMethod = async (subscriptionId: string, payment_token: string) => {
    const a = action(catalog, 'billing.update_payment_method');
    if (!a) return;
    setBusy(true); setError('');
    try {
      await call(session, a, { id: subscriptionId, payment_token });
      setCardFormOpen(null);
      setNotice(t('billingStatus.updated'));
      load();
    } catch (e) {
      setError(e instanceof Error ? e.message : t('billingStatus.updateFailed'));
    } finally {
      setBusy(false);
    }
  };

  // THE RETURN FROM 3DS — same guard `AppLauncher.tsx`'s own `useAppBilling` uses: no pending
  // payment, nothing to do, so a bookmarked or refreshed URL replays nothing.
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const tokenId = params.get('id');
    const pending = takePending();
    if (!tokenId || !pending || pending.kind !== 'update_payment_method') return;
    setResolvingReturn(true);
    confirmToken(tokenId)
      .then((result) => {
        if (result.kind === 'error') { setError(result.message); return; }
        if (result.kind !== 'token') return;
        return finishUpdatePaymentMethod(pending.subscriptionId, result.token);
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

  if (cardFormOpen) {
    return (
      <CardForm
        pending={{ kind: 'update_payment_method', subscriptionId: cardFormOpen }}
        onCancel={() => setCardFormOpen(null)}
        onToken={(token) => void finishUpdatePaymentMethod(cardFormOpen, token)}
      />
    );
  }

  // EVERY REAL APP-PLAN, CROSSED WITH ITS SUBSCRIPTION — `planByKey`/`subByPlanId` are the same
  // real, live-loaded maps the launcher's own tiles read; nothing here re-fetches or re-derives
  // the catalogue a second time.
  const rows = Object.values(billing.planByKey)
    .map((plan) => ({ plan, sub: billing.subByPlanId[plan.id] }))
    .filter((r): r is { plan: typeof r.plan; sub: Subscription } =>
      Boolean(r.sub) && r.sub.status !== 'canceled');

  return (
    <div className="flex flex-col gap-5">
      {resolvingReturn ? <p className="text-sm text-text-secondary">{t('billingStatus.verifyingCard')}</p> : null}
      {notice ? <p className="text-sm text-success">{notice}</p> : null}
      {error ? <p role="alert" className="text-sm text-danger">{error}</p> : null}

      {pastDueSub ? (
        <Card className="flex flex-col gap-3 border-danger/30 bg-danger-soft p-4">
          <p className="text-sm text-danger-on-soft">{t('billingStatus.pastDue')}</p>
          <div className="flex flex-wrap gap-2">
            {openInvoice ? (
              <Button type="button" variant="danger" size="sm" disabled={payLinkBusy} onClick={() => void payByLink()}>
                {payLinkBusy ? t('billingStatus.openingPayLink') : t('billingStatus.payNow')}
              </Button>
            ) : null}
            {action(catalog, 'billing.update_payment_method') && canMintToken ? (
              <Button type="button" variant="outline" size="sm" disabled={busy}
                      onClick={() => setCardFormOpen(pastDueSub.id)}>
                {t('billingStatus.updatePaymentMethod')}
              </Button>
            ) : null}
          </div>
        </Card>
      ) : subs === undefined ? null : (
        <p className="text-sm text-text-secondary">{t('billingStatus.allGood')}</p>
      )}

      {rows.length > 0 ? (
        <div className="flex flex-col gap-3">
          <h3 className="text-sm font-bold text-text-primary">{t('billingStatus.myApps.title')}</h3>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            {rows.map(({ plan, sub }) => (
              <Card key={sub.id} className="flex flex-col gap-3 p-4">
                <div className="flex items-center justify-between gap-2">
                  <span className="text-sm font-bold text-text-primary">{sub.plan_name || plan.name}</span>
                  {sub.cancel_at_period_end ? (
                    <Badge tone="warning">{t('billingStatus.myApps.stopping')}</Badge>
                  ) : (
                    <Badge tone="success">{t('billingStatus.myApps.active')}</Badge>
                  )}
                </div>
                <RenewalControl
                  cancelPending={Boolean(sub.cancel_at_period_end)}
                  renewsOn={billing.renewalDay(sub.current_period_end)}
                  canceling={billing.cancelingAppId === sub.id}
                  onCancel={() => void billing.cancelApp(sub.id)}
                  undoingCancel={billing.undoingAppCancelId === sub.id}
                  onUndoCancel={() => void billing.undoCancel(sub.id)}
                  cascadeNames={billing.cascadeTargets(sub.id).map((p) => p.name)}
                  label={sub.plan_name || plan.name}
                />
                {!sub.cancel_at_period_end && action(catalog, 'subscription.renew_now') ? (
                  <Button type="button" variant="outline" size="sm"
                          disabled={renewingSubId === sub.id}
                          onClick={() => void renewNow(sub.id)}>
                    {renewingSubId === sub.id ? t('billingStatus.renewingNow') : t('billingStatus.renewNow')}
                  </Button>
                ) : null}
              </Card>
            ))}
          </div>
          {billing.appCancelError ? <p className="text-xs text-danger">{billing.appCancelError}</p> : null}
          {billing.undoCancelError ? <p className="text-xs text-danger">{billing.undoCancelError}</p> : null}
          {renewError ? <p className="text-xs text-danger">{renewError}</p> : null}
        </div>
      ) : null}
    </div>
  );
}
