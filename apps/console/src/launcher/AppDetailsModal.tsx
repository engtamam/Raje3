/**
 * The app-details window — a FRESH component built for the app-store redesign, not a reuse of
 * `rj-ui/Modal` (the owner's own direct instruction, 2026-09-16: "modal ماهي جميلة نبغ مكون جديد
 * من تصميمنا") — and its features are shown as an animated, staggered showcase grid, not the
 * plain bulleted `<ul>` `rj-ui/AppFeatureList.tsx` renders everywhere else (the owner's own
 * direct instruction: "مخصص لعرض المميزات بشكل جنوني وجديد وابتكاري"). The DATA is still the
 * same real, cited `AppFeature[]` every other card reads — only the PRESENTATION is new.
 *
 * REAL BILLING NOW LIVES HERE TOO (2026-09-16, second pass, the owner's own instruction: "يصير
 * تفاصيل التطبيق فيها كل شي من تجديد الاشتراك وعرض الخصومات والاسعار") — price, cross-app
 * discount badges, subscribe (through the SAME real `CardForm`/3DS flow `screens/Plans.tsx`
 * already uses, via `useAppBilling.ts` — never reinvented), cancel with an in-place confirm step,
 * and undo-cancel. `billing` is entirely optional: an app with no subscription plan of its own
 * (تسجيل زيارة/جهات الاتصال, always free) renders none of this, only the plain open/features view
 * it always had.
 */
import { useEffect, useState } from 'react';
import { createPortal } from 'react-dom';
import { AnimatePresence, motion } from 'framer-motion';
import { Crown, Sparkles, Tag, X, Zap } from 'lucide-react';
import type { LucideIcon } from 'lucide-react';
import { appIcon, toneClasses } from '../rj-ui/AppFeatureList';
import type { AppFeature } from '../apps';
import type { Plan } from '../billingShared';
import { monthlyPriceOf } from './useAppBilling';
import { unitsLabel } from '../screens/Wallet';
import { useOperatorI18n, tf } from '../operator-i18n';
import './launcher-i18n';

// A REFERENCE COUNT, NOT A SAVED-AND-RESTORED VALUE — every launcher tile mounts its own
// `AppDetailsModal` instance, and "remember what it was before, put it back after" breaks the
// moment a second instance's lock window overlaps the first's even briefly (found live: a scroll
// lock left stuck on the WHOLE page after closing one modal and opening another during testing).
// A shared counter is immune to that ordering — the page unlocks only when the LAST open modal
// closes, never depends on which one opened or closed first.
let lockCount = 0;
function lockScroll(): () => void {
  if (lockCount === 0) document.documentElement.style.overflow = 'hidden';
  lockCount += 1;
  return () => {
    lockCount = Math.max(0, lockCount - 1);
    if (lockCount === 0) document.documentElement.style.overflow = '';
  };
}

export interface AppBillingProps {
  plan: Plan;
  sellable: boolean;
  busy: boolean;
  onSubscribe: () => void;
  cancelPending: boolean;
  renewsOn: string;
  canceling: boolean;
  onCancel?: () => void;
  undoingCancel: boolean;
  onUndoCancel?: () => void;
  discount?: { percent: number; owning_key: string };
  potentialDiscount?: { percent: number; owning_key: string };
  /** The REAL name of the app behind `discount`/`potentialDiscount`'s `owning_key` — resolved by
   *  the caller (`AppLauncher.tsx` already reads `APP_ROWS`), never re-derived here so this
   *  component never needs the app registry itself. */
  discountAppName?: string;
  potentialDiscountAppName?: string;
  /** `included_credit_minor` (billing-service v0.19.24) — present ONLY on بوت خدمة العملاء الذكي's
   *  own plan; `undefined` means "this plan carries no such allowance", never zero. */
  includedCreditMinor?: number;
  /** The live halala→unit rate (`whatsapp_assistant.pricing_current`) — `null` while unread or
   *  unreadable, same fallback-to-riyals posture `Wallet.tsx`'s own `unitsLabel` already takes. */
  unitsPerHalala: number | null;
  /** Real names of the other apps this cancel would take down with it (تسجيل زيارة/الحجوزات's own
   *  dependents) — empty when cancelling this one has no cascade. */
  cascadeNames: string[];
}

export interface AppDetailsModalProps {
  open: boolean;
  onClose: () => void;
  label: string;
  what: string;
  icon: LucideIcon;
  accent: string;
  ctaLabel: string;
  onCta: () => void;
  /** Already-known (operations-owned apps) — skips the fetch entirely, same rule
   *  `AppFeatureList`/`Plans.tsx` already follow. */
  inlineFeatures?: AppFeature[];
  /** `AppRow.featuresAction` — fetched the moment the window opens, when `inlineFeatures` is
   *  absent. */
  featuresAction?: string;
  /** Resolves ONE catalog action id to its real content — the caller's own `action(catalog, id)`
   *  + `call(session, action)` pair, injected so this window never has to know the catalog or
   *  session itself (same seam `AppFeatureList` already uses). */
  fetcher: (actionId: string) => Promise<{ features: AppFeature[] }>;
  /** Absent for a free/bundled app with no subscription plan of its own. */
  billing?: AppBillingProps;
  /** THE ONE ROYAL-GOLD APP — same flag `AppTile.tsx`'s own `AppTileData.vip` carries, forwarded
   *  straight through so the tile and its details window never disagree about which app is the
   *  gold one. */
  vip?: boolean;
}

const CARD_VARIANTS = {
  hidden: { opacity: 0, y: 18, scale: 0.92 },
  show: (i: number) => ({
    opacity: 1, y: 0, scale: 1,
    transition: { type: 'spring' as const, stiffness: 340, damping: 26, delay: i * 0.055 },
  }),
};

function FeatureTile({ feature, index }: { feature: AppFeature; index: number }) {
  const Icon = appIcon(feature.icon);
  return (
    <motion.div
      custom={index}
      variants={CARD_VARIANTS}
      initial="hidden"
      animate="show"
      whileHover={{ y: -3, rotate: index % 2 === 0 ? -0.6 : 0.6 }}
      className={`flex flex-col gap-2 rounded-2xl border border-border-subtle p-3.5 ${toneClasses(feature.tone)}`}
    >
      <span aria-hidden className="grid h-8 w-8 shrink-0 place-items-center rounded-xl bg-white/60 shadow-sm dark:bg-black/20">
        <Icon size={16} />
      </span>
      <span className="text-[.83rem] font-bold leading-snug">{feature.title}</span>
      <span className="text-xs leading-relaxed opacity-80">{feature.detail}</span>
    </motion.div>
  );
}

function FeatureTileSkeleton({ index }: { index: number }) {
  return (
    <motion.div
      custom={index}
      variants={CARD_VARIANTS}
      initial="hidden"
      animate="show"
      className="flex h-[92px] flex-col gap-2 rounded-2xl border border-border-subtle bg-surface-2/60 p-3.5"
    >
      <span className="h-8 w-8 animate-pulse rounded-xl bg-surface-2" />
      <span className="h-3 w-3/4 animate-pulse rounded bg-surface-2" />
    </motion.div>
  );
}

/** THE INCLUDED-AI-UNITS CHIP — its own "royal" gradient (violet→indigo, a shimmer sweeping
 *  across it on a loop), never the plain purple box the old متجر التطبيقات screen used. This is a
 *  GIFT riding on top of the plan, not a fact about the price above it — it earns its own weight,
 *  not a badge stamped in the corner of the price. Shared between the full modal row and the
 *  compact tile-face preview (`AppPriceStrip` below) so the two never drift into two different
 *  numbers for the same halala. */
export function AiUnitsChip({ includedCreditMinor, unitsPerHalala, compact }: {
  includedCreditMinor: number; unitsPerHalala: number | null; compact?: boolean;
}) {
  const { t } = useOperatorI18n();
  // ABSENCE, NEVER ZERO — same rule `includedAiCreditOf`'s own header already states. A plan that
  // has not (yet) opted into any allowance sends 0, and rendering "0 ريال" as if it were a gift
  // reads as a broken promise, not an offer (found live: exactly this — a shimmering purple box
  // proudly announcing zero). `w-fit` here too — this is a CHIP, not a full-width button; the
  // compact tile-face preview otherwise stretched to the card's own width as a block element.
  if (!includedCreditMinor) return null;
  return (
    <div
      className={`relative flex w-fit items-center gap-2.5 overflow-hidden rounded-2xl bg-gradient-to-l from-[#4c1d95] via-[#6d28d9] to-[#7c3aed] shadow-[0_4px_20px_-4px_rgba(109,40,217,0.55)] ${compact ? 'px-2.5 py-1.5' : 'p-3.5'}`}
    >
      <motion.span
        aria-hidden
        className="pointer-events-none absolute inset-y-0 w-1/3 -skew-x-12 bg-white/20"
        initial={{ x: '-120%' }}
        animate={{ x: '260%' }}
        transition={{ duration: 2.4, repeat: Infinity, repeatDelay: 1.6, ease: 'easeInOut' }}
      />
      <span aria-hidden className={`relative grid shrink-0 place-items-center rounded-full bg-white/15 text-white ${compact ? 'h-6 w-6' : 'h-9 w-9'}`}>
        <Zap size={compact ? 12 : 18} />
      </span>
      <div className="relative flex min-w-0 flex-col">
        <span className={`font-extrabold leading-tight text-white ${compact ? 'text-[.72rem]' : 'text-base'}`}>
          {unitsLabel(includedCreditMinor, unitsPerHalala, t)}
        </span>
        {compact ? null : (
          <span className="text-xs font-medium leading-snug text-white/80">
            {t('launcher.billing.aiUnitsIncluded')}
          </span>
        )}
      </div>
    </div>
  );
}

/** THE OFFER CARD — "خصم محتمل" reimagined: a real royal-gold pitch (border glow + a slow shimmer
 *  sweep), never the plain warning-tinted pill the first pass shipped with. Deliberately
 *  THEME-INVARIANT, same reasoning the old store's own gold box had: an offer this good reads the
 *  same in light or dark. Names the OTHER app by its real name — a percentage with no target is a
 *  fact nobody can act on. */
export function OfferChip({ percent, appName, compact }: { percent: number; appName: string; compact?: boolean }) {
  const { t } = useOperatorI18n();
  return (
    <div
      className={`relative flex items-center gap-2.5 overflow-hidden rounded-2xl border border-[#d4af37]/50 bg-gradient-to-l from-[#1a1207] via-[#2f210c] to-[#4a3512] shadow-[0_4px_20px_-4px_rgba(212,175,55,0.4)] ${compact ? 'px-2.5 py-1.5' : 'p-3.5'}`}
    >
      <motion.span
        aria-hidden
        className="pointer-events-none absolute inset-y-0 w-1/4 -skew-x-12 bg-[#f4e2a4]/25"
        initial={{ x: '-140%' }}
        animate={{ x: '340%' }}
        transition={{ duration: 2.8, repeat: Infinity, repeatDelay: 1.2, ease: 'easeInOut' }}
      />
      <span aria-hidden className={`relative grid shrink-0 place-items-center rounded-full bg-[#d4af37]/20 text-[#f4e2a4] ${compact ? 'h-6 w-6' : 'h-9 w-9'}`}>
        <Sparkles size={compact ? 12 : 18} />
      </span>
      <div className="relative flex min-w-0 flex-col">
        <span className={`font-extrabold leading-tight text-[#f4e2a4] ${compact ? 'text-[.72rem]' : 'text-sm'}`}>
          {tf(t, 'launcher.billing.offerTitle', { percent })}
        </span>
        {compact ? null : (
          <span className="text-xs font-medium leading-snug text-[#d4af37]/85">
            {tf(t, 'launcher.billing.offerDesc', { app: appName })}
          </span>
        )}
      </div>
    </div>
  );
}

/** THE CANCEL/RENEW CONTROL — extracted (2026-09-20) so `BillingStatusPane.tsx`'s own app list
 *  can show the exact same stop-renewal/undo-cancel behaviour, wording, and confirm step as this
 *  modal, instead of a second hand-copied version that could quietly drift from this one. Only
 *  the price/discount half of the old `BillingRow` stays here — a subscribe button and discount
 *  badges belong to buying, which the billing screen never does. */
export function RenewalControl({
  cancelPending, renewsOn, canceling, onCancel, undoingCancel, onUndoCancel, cascadeNames, label,
}: {
  cancelPending: boolean;
  renewsOn: string;
  canceling: boolean;
  onCancel?: () => void;
  undoingCancel: boolean;
  onUndoCancel?: () => void;
  cascadeNames: string[];
  label: string;
}) {
  const { t } = useOperatorI18n();
  const [confirming, setConfirming] = useState(false);

  if (confirming) {
    return (
      <div className="flex flex-col gap-3 rounded-2xl border border-danger/30 bg-danger-soft p-4">
        <p className="text-sm font-bold text-danger-on-soft">
          {tf(t, 'launcher.billing.confirmCancelTitle', { name: label })}
        </p>
        <p className="text-xs leading-relaxed text-danger-on-soft/90">{t('launcher.billing.confirmCancelBody')}</p>
        {cascadeNames.length > 0 ? (
          <p className="rounded-xl bg-white/40 p-2.5 text-xs text-danger-on-soft dark:bg-black/20">
            {tf(t, 'launcher.billing.cascadeWarning', { names: cascadeNames.join(t('launcher.listSeparator')) })}
          </p>
        ) : null}
        <div className="flex gap-2">
          <button
            type="button"
            disabled={canceling}
            onClick={() => { onCancel?.(); setConfirming(false); }}
            className="flex-1 rounded-full bg-danger py-2.5 text-sm font-bold text-danger-contrast disabled:opacity-60"
          >
            {canceling ? t('launcher.billing.stopping') : t('launcher.billing.confirmCancelConfirm')}
          </button>
          <button
            type="button"
            onClick={() => setConfirming(false)}
            className="rounded-full border border-border-subtle px-4 py-2.5 text-sm font-bold text-text-secondary"
          >
            {t('launcher.billing.confirmCancelBack')}
          </button>
        </div>
      </div>
    );
  }

  if (cancelPending) {
    return (
      <div className="flex flex-col gap-2">
        <p className="text-xs text-text-secondary">
          {renewsOn
            ? tf(t, 'launcher.billing.cancelPendingWithDate', { date: renewsOn })
            : t('launcher.billing.cancelPendingNoDate')}
        </p>
        {onUndoCancel ? (
          <button
            type="button"
            disabled={undoingCancel}
            onClick={onUndoCancel}
            className="rounded-full border border-border-subtle py-2.5 text-sm font-bold text-text-primary disabled:opacity-60"
          >
            {undoingCancel ? t('launcher.billing.undoing') : t('launcher.billing.undoCancel')}
          </button>
        ) : null}
      </div>
    );
  }

  if (onCancel) {
    return (
      <div className="flex flex-col gap-1.5">
        {renewsOn ? (
          <p className="text-xs text-text-secondary">{tf(t, 'launcher.billing.renewsOn', { date: renewsOn })}</p>
        ) : null}
        <button
          type="button"
          onClick={() => setConfirming(true)}
          className="rounded-full border border-danger/40 py-2.5 text-sm font-bold text-danger"
        >
          {t('launcher.billing.cancelRenewal')}
        </button>
      </div>
    );
  }

  return null;
}

/** THE PRICE/BILLING ROW — its own real element, not folded into the generic `onCta` this window
 *  already had, because owned/cancel-pending/not-yet-bought are three genuinely different rows,
 * never one button relabelled. */
function BillingRow({ billing, label, accent }: { billing: AppBillingProps; label: string; accent: string }) {
  const { t } = useOperatorI18n();
  const price = monthlyPriceOf(billing.plan);

  return (
    <div className="flex flex-col gap-2.5">
      {price ? (
        <div className="flex items-baseline gap-1.5">
          <span className="text-2xl font-extrabold">{price.amount}</span>
          <span className="text-sm font-semibold text-text-muted">{t('launcher.billing.perMonth')}</span>
        </div>
      ) : null}

      {billing.includedCreditMinor != null ? (
        <AiUnitsChip includedCreditMinor={billing.includedCreditMinor} unitsPerHalala={billing.unitsPerHalala} />
      ) : null}

      {billing.discount ? (
        <span className="flex w-fit items-center gap-1.5 rounded-full bg-success-soft px-3 py-1 text-xs font-bold text-success-on-soft">
          <Tag size={12} />
          {billing.discountAppName
            ? tf(t, 'launcher.billing.discountBadgeWithApp', { percent: billing.discount.percent, app: billing.discountAppName })
            : tf(t, 'launcher.billing.discountBadge', { percent: billing.discount.percent })}
        </span>
      ) : billing.potentialDiscount ? (
        <OfferChip
          percent={billing.potentialDiscount.percent}
          appName={billing.potentialDiscountAppName ?? billing.potentialDiscount.owning_key}
        />
      ) : null}

      {billing.cancelPending || billing.onCancel ? (
        <RenewalControl
          cancelPending={billing.cancelPending}
          renewsOn={billing.renewsOn}
          canceling={billing.canceling}
          onCancel={billing.onCancel}
          undoingCancel={billing.undoingCancel}
          onUndoCancel={billing.onUndoCancel}
          cascadeNames={billing.cascadeNames}
          label={label}
        />
      ) : (
        <button
          type="button"
          disabled={billing.busy || !billing.sellable}
          onClick={billing.onSubscribe}
          className="rounded-full py-2.5 text-sm font-bold text-accent-contrast shadow-sm transition hover:brightness-95 disabled:opacity-60"
          style={{ background: accent }}
        >
          {billing.busy ? t('launcher.billing.subscribing') : t('launcher.billing.subscribe')}
        </button>
      )}
    </div>
  );
}

/** THE FACE-OF-THE-CARD PREVIEW — "نفس الشي يظهر بالتفاصيل لكن على البطاقة من الخارج" (the owner's
 *  own instruction): a shop scanning the grid should read price, an included-AI gift, or a pending
 *  offer WITHOUT opening the details window first — the window stays the place for the full pitch
 *  (app name spelled out, subscribe/cancel), this is the teaser. Never rendered for an app with no
 *  billing plan at all (an `AppTile` with no `billing` prop skips this whole strip). */
export function AppPriceStrip({ billing }: { billing: AppBillingProps }) {
  const { t } = useOperatorI18n();
  const price = monthlyPriceOf(billing.plan);
  if (!price && billing.includedCreditMinor == null && !billing.discount && !billing.potentialDiscount) return null;
  return (
    <div className="flex flex-col gap-1.5">
      {price ? (
        billing.discount ? (
          <div className="flex items-baseline gap-1.5">
            <span className="text-xs text-text-muted line-through">{price.amount}</span>
            <span className="text-sm font-extrabold text-success">
              {tf(t, 'launcher.billing.discountedShort', { percent: billing.discount.percent })}
            </span>
          </div>
        ) : (
          <div className="flex items-baseline gap-1">
            <span className="text-sm font-extrabold">{price.amount}</span>
            <span className="text-[.7rem] font-semibold text-text-muted">{t('launcher.billing.perMonth')}</span>
          </div>
        )
      ) : null}
      {billing.includedCreditMinor != null ? (
        <AiUnitsChip compact includedCreditMinor={billing.includedCreditMinor} unitsPerHalala={billing.unitsPerHalala} />
      ) : null}
      {!billing.discount && billing.potentialDiscount ? (
        <OfferChip compact percent={billing.potentialDiscount.percent} appName={billing.potentialDiscountAppName ?? ''} />
      ) : null}
    </div>
  );
}

export function AppDetailsModal({
  open, onClose, label, what, icon: Icon, accent, ctaLabel, onCta,
  inlineFeatures, featuresAction, fetcher, billing, vip,
}: AppDetailsModalProps) {
  const { t } = useOperatorI18n();
  const [fetched, setFetched] = useState<AppFeature[] | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    if (!open || inlineFeatures || !featuresAction) return;
    let live = true;
    setFetched(null);
    setFailed(false);
    fetcher(featuresAction)
      .then((res) => { if (live) setFetched(res.features); })
      .catch(() => { if (live) setFailed(true); });
    return () => { live = false; };
  }, [open, inlineFeatures, featuresAction, fetcher]);

  useEffect(() => {
    if (!open) return;
    const unlock = lockScroll();
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose(); };
    document.addEventListener('keydown', onKey);
    return () => {
      unlock();
      document.removeEventListener('keydown', onKey);
    };
  }, [open, onClose]);

  const features = inlineFeatures ?? fetched;
  const loadingFeatures = !inlineFeatures && featuresAction && !fetched && !failed;

  return createPortal(
    <AnimatePresence>
      {open ? (
        // `pt-[6vh]` ON THE FLEX CONTAINER, NOT ON THE CARD ITSELF — with `items-center`, padding
        // on the CENTERING container shifts where "centered" sits.
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 pt-[6vh]" role="dialog" aria-modal="true">
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.18 }}
            className="absolute inset-0 bg-black/55 backdrop-blur-md"
            onClick={onClose}
            aria-hidden
          />
          <motion.div
            initial={{ opacity: 0, y: 24, scale: 0.97 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 16, scale: 0.98 }}
            transition={{ type: 'spring', stiffness: 340, damping: 30 }}
            className="relative z-10 flex max-h-[88vh] w-full max-w-lg flex-col overflow-hidden rounded-[26px] bg-surface-1 shadow-pop"
          >
            <div
              className={`relative flex shrink-0 items-center justify-between overflow-hidden p-6 ${vip ? 'border-b border-[#d4af37]/40' : ''}`}
              style={{
                background: vip
                  ? 'linear-gradient(135deg,#1a1207,#2f210c 55%,#4a3512)'
                  : `linear-gradient(135deg, ${accent}, color-mix(in srgb, ${accent} 55%, black))`,
              }}
            >
              {vip ? (
                <>
                  <motion.span
                    aria-hidden
                    className="pointer-events-none absolute inset-y-0 z-[1] w-1/4 -skew-x-12 bg-white/10"
                    initial={{ x: '-160%' }}
                    animate={{ x: '440%' }}
                    transition={{ duration: 3.2, repeat: Infinity, repeatDelay: 1.4, ease: 'easeInOut' }}
                  />
                  {/* `rotate-45`, NOT `-rotate-45` — same corner-mirrors-the-slope fix
                      `AppTile.tsx`'s own ribbon just got: this corner is the mirror image of the
                      one the old store's ribbon was tuned for. `top-4` stays positive — same
                      clipping mistake as the tile's own ribbon, fixed the same way. */}
                  <span className="pointer-events-none absolute -start-9 top-4 z-[2] flex w-36 rotate-45 items-center justify-center gap-1 bg-gradient-to-r from-[#d4af37] to-[#f0d98c] py-1 text-xs font-extrabold text-[#241a09] shadow-sm">
                    <Crown size={12} /> VIP
                  </span>
                </>
              ) : null}
              <span className={`relative z-[1] grid h-14 w-14 shrink-0 place-items-center rounded-2xl text-white ring-1 backdrop-blur-sm ${vip ? 'bg-[#d4af37]/20 ring-[#f0d98c]/50' : 'bg-white/20 ring-white/30'}`}>
                <Icon size={28} />
              </span>
              <button
                type="button"
                onClick={onClose}
                aria-label={t('launcher.tile.close')}
                className="relative z-[1] grid size-9 shrink-0 place-items-center rounded-full bg-white/15 text-white transition hover:bg-white/25 focus-ring"
              >
                <X size={18} />
              </button>
            </div>

            <div className="flex min-h-0 flex-1 flex-col gap-4 overflow-y-auto rounded-t-[22px] bg-surface-1 p-6">
              <div className="flex flex-col gap-1.5">
                <h2 className="text-xl font-extrabold">{label}</h2>
                <p className="text-sm leading-relaxed text-text-secondary">{what}</p>
              </div>

              {loadingFeatures ? (
                <div className="grid grid-cols-2 gap-2.5">
                  {[0, 1, 2, 3].map((i) => <FeatureTileSkeleton key={i} index={i} />)}
                </div>
              ) : features && features.length > 0 ? (
                <div className="grid grid-cols-2 gap-2.5">
                  {features.map((f, i) => <FeatureTile key={f.id} feature={f} index={i} />)}
                </div>
              ) : null}

              {billing ? (
                <BillingRow billing={billing} label={label} accent={accent} />
              ) : (
                <button
                  type="button"
                  onClick={onCta}
                  className="mt-1 rounded-full py-2.5 text-sm font-bold text-accent-contrast shadow-sm transition hover:brightness-95"
                  style={{ background: accent }}
                >
                  {ctaLabel}
                </button>
              )}
            </div>
          </motion.div>
        </div>
      ) : null}
    </AnimatePresence>,
    document.body,
  );
}
