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
 * 3. THE NEXT RENEWAL, TOTALLED FOR REAL — `billing.renewal_preview` (base-services v0.25.20)
 *    reuses the exact same `_compute_renewal` the real invoice cut calls, so the total shown here
 *    already has any coupon/cross-app discount applied — never a list-price guess. Grouped by
 *    (gateway, currency) exactly as a consolidated invoice would cut, so two currencies are never
 *    summed into one wrong number.
 */
import { useEffect, useState } from 'react';
import { Button } from '../rj-ui/Button';
import { Card } from '../rj-ui/Card';
import { Badge } from '../rj-ui/Badge';
import { action, call, type Catalog } from '../catalog';
import { canMintToken, confirmToken } from '../payment';
import { takePending } from '../pendingPayment';
import { appDisplayName, type Subscription } from '../billingShared';
import { useAppBilling } from '../launcher/useAppBilling';
import { RenewalControl } from '../launcher/AppDetailsModal';
import { CardForm } from './CardForm';
import { riyalsLabel } from '../money';
import type { Session } from '../session';
import { useOperatorI18n } from '../operator-i18n';
import './billing-status-i18n';

interface OpenInvoice {
  id: string;
  status?: string;
  total_minor?: number;
  currency?: string;
}

interface RenewalPreviewLine {
  subscription_id: string;
  plan_name?: string;
  interval?: string;
  subtotal_minor: number;
  discount_minor: number;
  tax_minor: number;
  total_minor: number;
}

interface RenewalPreviewGroup {
  gateway: string;
  currency: string;
  next_charge_at: number | null;
  lines: RenewalPreviewLine[];
  subtotal_minor: number;
  discount_minor: number;
  tax_minor: number;
  total_minor: number;
}

export function BillingStatusPane({ session, catalog }: { session: Session; catalog: Catalog }) {
  const { t } = useOperatorI18n();
  const billing = useAppBilling(session, catalog);

  const [subs, setSubs] = useState<Subscription[] | null | undefined>(undefined);
  const [renewalPreview, setRenewalPreview] = useState<RenewalPreviewGroup[] | null>(null);
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

  // THE NEXT RENEWAL'S REAL TOTAL — read-only, never touches money; absent (no action, or a
  // service down) simply means the section does not render, same posture as the rest of this pane.
  useEffect(() => {
    const a = action(catalog, 'billing.renewal_preview');
    if (!a) { setRenewalPreview(null); return; }
    call<{ groups: RenewalPreviewGroup[] }>(session, a)
      .then((x) => setRenewalPreview(x.groups ?? []))
      .catch(() => setRenewalPreview(null));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [session, catalog]);

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

  /** THE OWNER-FACING NAME FOR A RENEWAL LINE — `line.plan_name` is the server's own snapshot
   *  (billing's stored name, same "كوبونات" the plan row was created with), so this resolves the
   *  same way every other surface on this screen does: subscription -> its plan -> apps.ts's own
   *  name. Falls back to the server's snapshot only when the plan cannot be matched at all (e.g.
   *  a plan since delisted from the catalogue), never the other way around. */
  const lineDisplayName = (line: RenewalPreviewLine): string => {
    const sub = (subs ?? []).find((s) => s.id === line.subscription_id);
    const plan = sub ? Object.values(billing.planByKey).find((p) => p.id === sub.plan_id) : undefined;
    return plan ? appDisplayName(plan) : (line.plan_name || '—');
  };

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

      {renewalPreview && renewalPreview.length > 0 ? (
        <div className="flex flex-col gap-3">
          <h3 className="text-sm font-bold text-text-primary">{t('billingStatus.renewalPreview.title')}</h3>
          {renewalPreview.map((g) => (
            <Card key={`${g.gateway}-${g.currency}`} className="flex flex-col gap-3 p-4">
              <span className="text-sm text-text-secondary">
                {g.next_charge_at
                  ? t('billingStatus.renewalPreview.nextChargeOn').replace(
                      '{date}', billing.renewalDay(g.next_charge_at))
                  : t('billingStatus.renewalPreview.noDate')}
              </span>
              <ul className="flex flex-col gap-1">
                {g.lines.map((line) => (
                  <li key={line.subscription_id}
                      className="flex items-center justify-between gap-2 text-xs text-text-secondary">
                    <span>{lineDisplayName(line)}</span>
                    <span>{riyalsLabel(line.total_minor, t)}</span>
                  </li>
                ))}
              </ul>
              {/* THE FULL BREAKDOWN — every figure straight from `billing.renewal_preview`
                  (`_compute_renewal`, the same function the real invoice runs), so a shop
                  understands exactly what it will pay: list price, what it saves, and tax
                  only when this establishment's own configuration actually applies one. */}
              <div className="flex flex-col gap-1 rounded-2xl bg-surface-2 p-3 text-xs">
                <div className="flex items-center justify-between text-text-secondary">
                  <span>{t('billingStatus.renewalPreview.subtotal')}</span>
                  <span className="tabular-nums">{riyalsLabel(g.subtotal_minor, t)}</span>
                </div>
                {g.discount_minor > 0 ? (
                  <div className="flex items-center justify-between text-success">
                    <span>{t('billingStatus.renewalPreview.savings')}</span>
                    <span className="tabular-nums">-{riyalsLabel(g.discount_minor, t)}</span>
                  </div>
                ) : null}
                {g.tax_minor > 0 ? (
                  <div className="flex items-center justify-between text-text-secondary">
                    <span>{t('billingStatus.renewalPreview.tax')}</span>
                    <span className="tabular-nums">{riyalsLabel(g.tax_minor, t)}</span>
                  </div>
                ) : null}
                <div className="mt-1 flex items-center justify-between border-t border-border-subtle pt-1 font-bold text-text-primary">
                  <span>{t('billingStatus.renewalPreview.total')}</span>
                  <span className="tabular-nums">{riyalsLabel(g.total_minor, t)}</span>
                </div>
              </div>
            </Card>
          ))}
        </div>
      ) : null}

      {rows.length > 0 ? (
        <div className="flex flex-col gap-3">
          <h3 className="text-sm font-bold text-text-primary">{t('billingStatus.myApps.title')}</h3>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            {rows.map(({ plan, sub }) => (
              <Card key={sub.id} className="flex flex-col gap-3 p-4">
                <div className="flex items-center justify-between gap-2">
                  <span className="text-sm font-bold text-text-primary">{appDisplayName(plan)}</span>
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
                  cascadeNames={billing.cascadeTargets(sub.id).map((p) => appDisplayName(p))}
                  label={appDisplayName(plan)}
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
