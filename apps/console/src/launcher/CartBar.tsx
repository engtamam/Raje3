/**
 * THE CART — a floating bar, never a page navigation. Several apps chosen from «متجر
 * التطبيقات» sit here until one checkout buys them all together (services/operations's own
 * `may_add_bundle` validates the whole set — a dependency and the app that needs it may now
 * travel in the same purchase). Built fresh for this pass, on `rj-ui/Card`'s own surface/shadow
 * language so it reads as part of the same product, never a bolted-on widget.
 */
import { AnimatePresence, motion } from 'framer-motion';
import { ShoppingBag, X } from 'lucide-react';
import { Button } from '../rj-ui/Button';
import { riyals } from '../money';
import type { Plan } from '../billingShared';
import { useOperatorI18n, tf } from '../operator-i18n';
import './launcher-i18n';

export function CartBar({
  plans, totalMinor, discounts, notice, error, busy, onRemove, onCheckout,
}: {
  plans: Plan[];
  /** THE LIST TOTAL — every item's own posted price, summed. A REAL number, not a guess; see
   *  `useAppBilling`'s own `cartTotalMinor` for why no "after discount/tax" figure is computed
   *  here — only billing itself can produce that number correctly. */
  totalMinor: number;
  /** Known discounts, keyed by plan id — shown per item as a badge ("X% off"), never folded into
   *  a computed total: the badge names a fact billing already told us; a total built from it would
   *  be an amount billing never confirmed. */
  discounts: Record<string, { percent: number; owning_key: string }>;
  notice: string;
  error: string;
  busy: boolean;
  onRemove: (planId: string) => void;
  onCheckout: () => void;
}) {
  const { t } = useOperatorI18n();
  const hasDiscount = plans.some((p) => discounts[p.id]);

  return (
    <AnimatePresence>
      {plans.length > 0 ? (
        <motion.div
          initial={{ y: 32, opacity: 0 }}
          animate={{ y: 0, opacity: 1 }}
          exit={{ y: 32, opacity: 0 }}
          transition={{ type: 'spring', stiffness: 340, damping: 32 }}
          // FIXED, BOTTOM, ABOVE EVERYTHING — a shop keeps browsing the shelf underneath while
          // the cart stays visible; `env(safe-area-inset-bottom)` clears a phone's own home bar.
          className="fixed inset-x-0 bottom-0 z-40 flex justify-center px-4"
          style={{ paddingBottom: 'max(1rem, env(safe-area-inset-bottom, 0px))' }}
        >
          <div className="flex w-full max-w-2xl flex-col gap-3 rounded-[22px] border border-border-subtle bg-surface-1 p-4 shadow-pop">
            <div className="flex flex-wrap items-center gap-3">
              <span className="grid size-10 shrink-0 place-items-center rounded-full bg-accent-soft text-accent">
                <ShoppingBag size={18} />
              </span>
              <div className="flex min-w-0 flex-1 flex-col">
                <span className="text-sm font-extrabold">
                  {plans.length === 1 ? t('launcher.cart.itemsCount.one') : tf(t, 'launcher.cart.itemsCount.many', { n: plans.length })}
                </span>
                <span className="truncate text-xs text-text-secondary">
                  {plans.map((p) => p.name).join(t('launcher.listSeparator'))}
                </span>
              </div>
              <div className="flex flex-col items-end">
                <span className="text-xs font-semibold text-text-muted">{t('launcher.cart.total')}</span>
                <span className="text-lg font-extrabold">{riyals(totalMinor)}</span>
              </div>
            </div>

            {hasDiscount ? <p className="text-xs text-text-secondary">{t('launcher.cart.discountCaveat')}</p> : null}

            <div className="flex flex-wrap gap-1.5">
              {plans.map((p) => (
                <span key={p.id} className="flex items-center gap-1 rounded-full bg-surface-2 py-1 ps-3 pe-1.5 text-xs font-semibold">
                  {p.name}
                  {discounts[p.id] ? (
                    <span className="text-success">{tf(t, 'launcher.cart.itemDiscount', { percent: discounts[p.id].percent })}</span>
                  ) : null}
                  <button
                    type="button"
                    onClick={() => onRemove(p.id)}
                    aria-label={tf(t, 'launcher.cart.removeItem', { name: p.name })}
                    className="grid size-5 place-items-center rounded-full text-text-muted hover:bg-surface-3 hover:text-text-primary"
                  >
                    <X size={12} />
                  </button>
                </span>
              ))}
            </div>

            {notice ? <p className="text-xs text-success">{notice}</p> : null}
            {error ? <p role="alert" className="text-xs text-danger">{error}</p> : null}

            <Button type="button" onClick={onCheckout} disabled={busy} className="w-full">
              {busy ? t('launcher.cart.checkingOut') : t('launcher.cart.checkout')}
            </Button>
          </div>
        </motion.div>
      ) : null}
    </AnimatePresence>
  );
}
