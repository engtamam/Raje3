/**
 * One app tile — built ON `rj-ui/Card` (the sheen, the surface, the radius all come from there).
 *
 * TWO SEPARATE PRESSES, ON PURPOSE (the owner's own spec): the tile's own face opens the app;
 * "التفاصيل" opens the SAME app's own details in `AppDetailsModal` — a real window with an
 * animated feature showcase, never navigating anywhere by itself and never also firing the
 * tile's own open.
 */
import { useState } from 'react';
import type { LucideIcon } from 'lucide-react';
import { Crown, Lock } from 'lucide-react';
import { motion } from 'framer-motion';
import { Card } from '../rj-ui/Card';
import { AppDetailsModal, AppPriceStrip, type AppBillingProps } from './AppDetailsModal';
import { useOperatorI18n } from '../operator-i18n';
import type { AppFeature } from '../apps';
import './launcher-i18n';

export interface AppTileData {
  id: string;
  label: string;
  what: string;
  icon: LucideIcon;
  accent: string;
  locked: boolean;
  /** Real ownership, same field the old متجر التطبيقات's own `AppCard` badge read
   *  (`owned === true`) — `undefined`/`false` renders no badge at all, same "absence is never
   *  invented" rule every other read here follows. */
  owned?: boolean;
  /** The SAME distinction `Plans.tsx`'s own card still makes (`appSub?.status === 'trialing'`) —
   *  a shop mid-trial reads a different word than one already billed in full. */
  trialing?: boolean;
  inlineFeatures?: AppFeature[];
  featuresAction?: string;
  /** THE ONE ROYAL-GOLD APP — the same identity the old متجر التطبيقات's own `.rj-gold-card` gave
   *  بوت خدمة العملاء الذكي (the one app the owner himself asked to stand out from the shelf),
   *  reinterpreted here as a fresh component rather than reused CSS: a dark gold gradient face, a
   *  VIP ribbon, and a slow mirror-shine sweep, on the tile AND its details window alike. A fixed
   *  identity flag, not data-driven — there is exactly one such app today, the same way the old
   *  card's own `app?.id === 'whatsapp'` check was. */
  vip?: boolean;
}

export function AppTile({
  app, onOpen, fetchFeatures, billing, hideDetails,
}: {
  app: AppTileData;
  onOpen: () => void;
  /** Same seam `AppDetailsModal` forwards straight to its own fetch — see that file's own note. */
  fetchFeatures: (actionId: string) => Promise<{ features: AppFeature[] }>;
  /** Absent for an app with no billing plan of its own (تسجيل زيارة/جهات الاتصال, always free/
   *  bundled) — the details window then shows no price/subscribe row at all, same "absence is
   *  never invented" rule every other read here follows. */
  billing?: AppBillingProps;
  /** «تطبيقاتي» ONLY (the owner's own instruction, 2026-09-20) — that shelf is pure navigation
   *  now, never a second storefront: no price strip on the face, no "التفاصيل" button/window at
   *  all. «متجر التطبيقات» is unchanged — every price/subscribe/cancel/feature-showcase
   *  behaviour this tile always had stays exactly there. `AppLauncher.tsx` also withholds the
   *  `billing` prop itself on «تطبيقاتي», so this flag only needs to additionally suppress the
   *  "التفاصيل" entry point (a free/bundled app with no `billing` still had one, showing its
   *  plain feature list — that must vanish too on this shelf). */
  hideDetails?: boolean;
}) {
  const { t } = useOperatorI18n();
  const [open, setOpen] = useState(false);
  const Icon = app.icon;

  return (
    <>
      <Card
        role="button"
        tabIndex={0}
        aria-label={app.label}
        sheen={!app.vip}
        onClick={() => { if (!open) onOpen(); }}
        onKeyDown={(e) => { if ((e.key === 'Enter' || e.key === ' ') && !open) { e.preventDefault(); onOpen(); } }}
        className={`relative flex min-h-[212px] cursor-pointer flex-col gap-3 overflow-hidden p-6 transition-transform duration-200 ease-[cubic-bezier(.22,1,.36,1)] hover:-translate-y-1 hover:shadow-lg focus-ring ${
          app.vip
            ? 'border-[#d4af37]/40 bg-gradient-to-br from-[#1a1207] via-[#2f210c] to-[#4a3512] text-white shadow-[0_8px_28px_-8px_rgba(212,175,55,0.5)]'
            : ''
        }`}
      >
        {/* `relative` ABOVE, ALWAYS — NOT CONDITIONAL ON `sheen` (found live: with `sheen={false}`
            for a VIP tile, the card lost the positioning context `card-sheen` itself supplies, so
            every `absolute` child inside only rendered once `hover:-translate-y-1`'s own
            `transform` incidentally created one — invisible at rest, appearing only on hover). */}
        {app.vip ? (
          <>
            {/* THE MIRROR-SHINE SWEEP — a slow diagonal band of light drifting across the whole
                tile, the "انعكاس مرايا" the owner asked for, never a static gradient alone. */}
            <motion.span
              aria-hidden
              className="pointer-events-none absolute inset-y-0 z-[1] w-1/4 -skew-x-12 bg-white/10"
              initial={{ x: '-160%' }}
              animate={{ x: '440%' }}
              transition={{ duration: 3.2, repeat: Infinity, repeatDelay: 1.4, ease: 'easeInOut' }}
            />
            {/* `-start-8`, NOT `-end-8` — found live: `-end` is the SAME corner the owned/locked
                status badge below already anchors to (`end-3.5 top-3.5`), so the ribbon sat right
                on top of it. The ribbon's own corner is the opposite one, never shared. AND
                `rotate-45`, NOT `-rotate-45` — a corner ribbon's slope MIRRORS with the corner:
                the old store's own `-left-8 -rotate-45` was tuned for the LEFT corner only; kept
                on the RIGHT corner it slopes the wrong way. `top-3` STAYS POSITIVE (a stray
                `-top-1` in an earlier pass pushed the whole band mostly outside the card's own
                `overflow-hidden`, clipping it to a sliver — found live). */}
            <span className="pointer-events-none absolute -start-8 top-3 z-[2] flex w-32 rotate-45 items-center justify-center gap-1 bg-gradient-to-r from-[#d4af37] to-[#f0d98c] py-0.5 text-[11px] font-extrabold text-[#241a09] shadow-sm">
              <Crown size={11} /> VIP
            </span>
          </>
        ) : null}

        {app.locked ? (
          <span className="absolute end-3.5 top-3.5 z-[2] flex items-center gap-1 rounded-full bg-surface-2 px-2.5 py-1 text-xs font-bold text-text-secondary">
            <Lock size={12} /> {t('launcher.tile.locked')}
          </span>
        ) : app.owned ? (
          <span className={`absolute end-3.5 top-3.5 z-[2] rounded-full px-2.5 py-1 text-xs font-bold ${app.vip ? 'bg-[#d4af37]/20 text-[#f4e2a4]' : 'bg-success-soft text-success-on-soft'}`}>
            {app.trialing ? t('launcher.tile.trialing') : t('launcher.tile.active')}
          </span>
        ) : null}

        <span
          className={`relative z-[1] grid h-[58px] w-[58px] shrink-0 place-items-center rounded-2xl text-white shadow-sm ${app.vip ? 'ring-2 ring-[#f0d98c]/60' : ''}`}
          style={{ background: app.vip ? 'linear-gradient(135deg,#d4af37,#8a6a1a)' : app.accent }}
        >
          <Icon size={26} />
        </span>
        <span className={`relative z-[1] text-[1.05rem] font-extrabold ${app.vip ? '[text-shadow:0_1px_3px_rgba(0,0,0,0.55)]' : ''}`}>
          {app.label}
        </span>

        {billing ? <AppPriceStrip billing={billing} /> : null}

        {hideDetails ? null : (
          <button
            type="button"
            onClick={(e) => { e.stopPropagation(); setOpen(true); }}
            className={`relative z-[2] mt-auto w-fit self-start py-1 text-sm font-bold ${app.vip ? 'text-[#f4e2a4]' : 'text-accent'}`}
          >
            {t('launcher.tile.details')}
          </button>
        )}
      </Card>

      {hideDetails ? null : (
        <AppDetailsModal
          open={open}
          onClose={() => setOpen(false)}
          label={app.label}
          what={app.what}
          icon={Icon}
          accent={app.accent}
          ctaLabel={app.locked ? t('launcher.tile.addToPlan') : t('launcher.tile.open')}
          onCta={() => { setOpen(false); onOpen(); }}
          inlineFeatures={app.inlineFeatures}
          featuresAction={app.featuresAction}
          fetcher={fetchFeatures}
          billing={billing}
          vip={app.vip}
        />
      )}
    </>
  );
}
