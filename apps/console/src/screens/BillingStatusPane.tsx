/**
 * «حسابي ← الفوترة» — what the old شاشة الاشتراك's billing tab still had a real reason to exist
 * for, once every app purchase (subscribe/cancel/discounts) and every capacity add-on had already
 * moved to the launcher (`AppLauncher.tsx`'s own tiles + capacity shelf,
 * [[task-app-store-redesign-7-phases]]): a failing charge, and the one control that fixes it.
 *
 * `screens/Plans.tsx` IS DELETED (2026-09-16) — this is a fresh component, not a trimmed copy of
 * its `PlansPane`. The shared TYPES/PURE LOGIC that file also carried (`Plan`/`Subscription`,
 * `kindOf`, `canBuy`, `CapacityAddonCard`, …) live on in `../billingShared.tsx`, read by the
 * launcher and `admin/PlanCards.tsx` alike — this pane only needs `Subscription` from there.
 */
import { useEffect, useState } from 'react';
import { Button } from '../rj-ui/Button';
import { action, call, type Catalog } from '../catalog';
import { canMintToken, confirmToken } from '../payment';
import { takePending } from '../pendingPayment';
import type { Subscription } from '../billingShared';
import { CardForm } from './CardForm';
import type { Session } from '../session';
import { useOperatorI18n } from '../operator-i18n';
import './billing-status-i18n';

export function BillingStatusPane({ session, catalog }: { session: Session; catalog: Catalog }) {
  const { t } = useOperatorI18n();
  const [subs, setSubs] = useState<Subscription[] | null | undefined>(undefined);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [cardFormOpen, setCardFormOpen] = useState<string | null>(null);
  const [resolvingReturn, setResolvingReturn] = useState(false);

  const load = () => {
    const a = action(catalog, 'billing.my_subscriptions');
    if (!a) { setSubs(null); return; }
    call<{ subscriptions: Subscription[] }>(session, a)
      .then((x) => setSubs(x.subscriptions ?? []))
      .catch(() => setSubs(null));
  };
  useEffect(load, [session, catalog]); // eslint-disable-line react-hooks/exhaustive-deps

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

  const pastDueSub = (subs ?? []).find((s) => s.status === 'past_due');

  if (cardFormOpen) {
    return (
      <CardForm
        pending={{ kind: 'update_payment_method', subscriptionId: cardFormOpen }}
        onCancel={() => setCardFormOpen(null)}
        onToken={(token) => void finishUpdatePaymentMethod(cardFormOpen, token)}
      />
    );
  }

  return (
    <div className="flex flex-col gap-4">
      {resolvingReturn ? <p className="text-sm text-text-secondary">{t('billingStatus.verifyingCard')}</p> : null}
      {notice ? <p className="text-sm text-success">{notice}</p> : null}
      {error ? <p role="alert" className="text-sm text-danger">{error}</p> : null}

      {pastDueSub ? (
        <div className="flex flex-col gap-2 rounded-card border border-danger/30 bg-danger-soft p-4">
          <p className="text-sm text-danger">{t('billingStatus.pastDue')}</p>
          {action(catalog, 'billing.update_payment_method') && canMintToken ? (
            <div>
              <Button type="button" variant="danger" size="sm" disabled={busy}
                      onClick={() => setCardFormOpen(pastDueSub.id)}>
                {t('billingStatus.updatePaymentMethod')}
              </Button>
            </div>
          ) : null}
        </div>
      ) : subs === undefined ? null : (
        <p className="text-sm text-text-secondary">{t('billingStatus.allGood')}</p>
      )}
    </div>
  );
}
