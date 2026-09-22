/**
 * «احتفال المنحة» — the counter's own celebration moment (owner's own explicit requirement): a
 * customer just became eligible for a real gift/discount at a partner shop, right after his visit
 * was recorded. Fires ONLY on that one event (`queue.ts`'s own `subscribeToCelebrations`), never
 * on an ordinary visit — see that file's own note on why a celebration that fires every time stops
 * meaning anything.
 *
 * A BOARDING-PASS CARD, ON PURPOSE — grounded in real 2026 loyalty-UX research: a perforated,
 * torn-edge card with a clear headline, the reward, and an expiry date is the shape people
 * actually screenshot and share (digital-wallet pass design, loyalty-card design guides). The
 * owner's own explicit ask was exactly this: the operator can tell the customer "صوّرها بجوالك" —
 * so the card is built to read perfectly in a photo, not just on this screen.
 *
 * DISMISSES IN ONE TAP, NEVER BLOCKS THE COUNTER — a plain `×`, no confirmation, and it renders
 * ABOVE the visit screen rather than replacing it: the operator's own next visit starts the moment
 * he closes this, exactly like the mobile app's own `GameEffects` overlays never blocking a flow.
 */
import { useEffect, useState } from 'react';
import { createPortal } from 'react-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { Gift, Percent, X } from 'lucide-react';
import { Confetti } from '../rj-ui/Confetti';
import type { ReferralGrantAck } from '../api';
import { useOperatorI18n, tf } from '../operator-i18n';
import './referral-grant-celebration-i18n';

function grantLine(g: ReferralGrantAck, t: (k: string) => string): string {
  if (g.grant_type === 'gift') return tf(t, 'rgc.line.gift', { name: g.gift_service_name });
  if (g.discount_scope === 'item') return tf(t, 'rgc.line.discountItem', { name: g.gift_service_name });
  if (g.discount_scope === 'group') return tf(t, 'rgc.line.discountGroup', { name: g.discount_group_name });
  return t('rgc.line.discountBlanket');
}

function formatDate(ts: number, locale: string): string {
  return new Date(ts * 1000).toLocaleDateString(locale === 'ar' ? 'ar-SA' : locale, {
    day: 'numeric', month: 'long', year: 'numeric',
  });
}

export function ReferralGrantCelebration({ grant, onClose }: {
  grant: ReferralGrantAck; onClose: () => void;
}) {
  const { t, locale } = useOperatorI18n();
  const [showConfetti, setShowConfetti] = useState(true);

  // AUTO-DISMISS NEVER HAPPENS — the owner's own explicit call: the operator closes it himself,
  // when the customer has actually seen/photographed it, not on a timer the counter cannot
  // control. Escape still works, same convenience every other overlay in this console offers.
  useEffect(() => {
    function onKey(e: KeyboardEvent) { if (e.key === 'Escape') onClose(); }
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [onClose]);

  const Icon = grant.grant_type === 'gift' ? Gift : Percent;

  return createPortal(
    <AnimatePresence>
      {showConfetti ? <Confetti onDone={() => setShowConfetti(false)} /> : null}
      <motion.div
        initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
        className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4 backdrop-blur-sm"
        onClick={onClose}
      >
        <motion.div
          initial={{ opacity: 0, scale: 0.9, y: 16 }} animate={{ opacity: 1, scale: 1, y: 0 }}
          exit={{ opacity: 0, scale: 0.95 }} transition={{ type: 'spring', stiffness: 260, damping: 22 }}
          onClick={(e) => e.stopPropagation()}
          className="relative w-full max-w-sm"
        >
          <button type="button" onClick={onClose} aria-label={t('rgc.close')}
                 className="absolute -top-3 end-0 z-10 rounded-full bg-surface-1 p-1.5 text-text-secondary shadow-md transition-colors hover:text-danger focus-ring">
            <X size={18} />
          </button>

          <div className="overflow-hidden rounded-3xl bg-surface-1 shadow-2xl">
            {/* ── the "stub" — the festive header, torn from the details below ─────────────── */}
            <div className="relative overflow-hidden bg-gradient-to-l from-[#6d1a8f] via-[#9c36b5] to-[#c15fd9] px-6 pb-8 pt-7 text-center text-white">
              <motion.span
                aria-hidden="true"
                initial={{ x: '-140%' }} animate={{ x: '340%' }}
                transition={{ duration: 1.4, delay: 0.5, ease: 'easeInOut' }}
                className="pointer-events-none absolute inset-y-0 start-0 w-1/3 -skew-x-12 bg-white/25"
              />
              <p className="text-3xl">🎉</p>
              <p className="mt-1 text-lg font-extrabold">{t('rgc.headline')}</p>
              <p className="mt-1 text-sm text-white/85">{t('rgc.subhead')}</p>
            </div>

            {/* ── the perforated tear line ─────────────────────────────────────────────────── */}
            <div className="relative h-0 border-t-2 border-dashed border-border-subtle">
              <span className="absolute -start-3 -top-3 h-6 w-6 rounded-full bg-surface-0" />
              <span className="absolute -end-3 -top-3 h-6 w-6 rounded-full bg-surface-0" />
            </div>

            {/* ── the stub proper — the real, full details ─────────────────────────────────── */}
            <div className="flex flex-col gap-4 p-6">
              <div className="flex items-center gap-3">
                <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full bg-accent-soft text-accent-on-soft">
                  <Icon size={20} />
                </div>
                <p className="text-base font-bold leading-snug">{grantLine(grant, t)}</p>
              </div>

              {grant.partner_shop_name ? (
                <div className="flex items-center justify-between border-t border-border-subtle pt-3 text-sm">
                  <span className="text-text-secondary">{t('rgc.partner')}</span>
                  <span className="font-semibold">{grant.partner_shop_name}</span>
                </div>
              ) : null}

              <div className="flex items-center justify-between border-t border-border-subtle pt-3 text-sm">
                <span className="text-text-secondary">{t('rgc.validUntil')}</span>
                <span className="font-semibold tabular-nums">{formatDate(grant.expires_at, locale)}</span>
              </div>

              <p className="rounded-xl bg-surface-2 p-3 text-center text-xs text-text-secondary">
                {t('rgc.howTo')}
              </p>
            </div>
          </div>
        </motion.div>
      </motion.div>
    </AnimatePresence>,
    document.body,
  );
}
