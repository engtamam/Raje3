/**
 * One locked card, for every app the shop has not bought.
 *
 * THE DEFECT IT REPLACES. Each screen decided for itself whether to lock, and it decided from the
 * CAPABILITY — which is about the person's role. An owner holds `campaigns.manage` regardless of
 * which app is enabled, so the lock never appeared for the one person who would have paid to
 * remove it: he pressed «أطلق الحملة» and it went out, with no campaigns app enabled at all, for
 * as long as the product existed.
 *
 * SHOWN, NEVER HIDDEN (§16.4.2). A section that vanishes is a feature the owner cannot discover,
 * cannot want, and cannot buy. He sees what it would do for HIS shop, and one button.
 *
 * IT NAMES WHAT IT DOES, NOT WHAT HE DID NOT PAY. «نقاطٌ على كل زيارة» is a fact about his shop;
 * «هذا تطبيق إضافي» is a fact about our price list, and only one of those makes anybody buy.
 *
 * AND IT NEVER LOCKS WHAT HE ALREADY EARNED. A lapsed subscription stops the app from GROWING —
 * new campaigns, new points — and the balances and history his customers already hold stay
 * readable, because they are his data and not our feature (the services enforce the same split).
 */
import { Lock } from 'lucide-react';
import { Link } from 'react-router-dom';
import { EmptyState } from '../rj-ui/EmptyState';
import { Skeleton } from '../rj-ui/Skeleton';
import { hasFailed, isReady, type Loading } from '../loading';
import { STORE_PATH } from '../nav';
import { APP_ROWS, owns, type Owned } from '../apps';

export function LockedCard({ appId }: { appId: string }) {
  const row = APP_ROWS.find((a) => a.id === appId);
  if (!row) return null;
  return (
    <section className="flex items-start gap-3 rounded-card bg-surface-1 p-4 shadow-sm">
      <Lock size={18} className="mt-0.5 shrink-0 text-text-secondary" aria-hidden />
      <div className="flex flex-col items-start gap-2">
        <h2 className="text-sm font-medium">{row.name}</h2>
        <p className="text-sm text-text-secondary">{row.what}</p>
        {/* THE BUTTON GOES TO THE PLACE THAT SELLS, and it is a LINK rather than a call: buying
            runs through `subscription.activate`, which is the only path that enforces the rule
            that a paid subscription needs WhatsApp connected first. */}
        <Link
          to={STORE_PATH}
          className="rounded-control bg-accent px-3 py-1.5 text-sm text-accent-contrast shadow-glow"
        >
          أضِفه من متجر التطبيقات
        </Link>
      </div>
    </section>
  );
}

/**
 * The whole screen an app owns, when the shop has not bought that app.
 *
 * THREE STATES, NOT TWO. While the answer has not arrived — or when billing could not be asked —
 * neither the surface nor the lock is drawn. Telling a paying shop it has not paid is the worst
 * sentence in the product, and an outage must never be the thing that says it.
 */
export function AppGate(
  { appId, owned, children }:
  { appId: string; owned: Loading<Owned>; children: React.ReactNode },
) {
  const row = APP_ROWS.find((a) => a.id === appId);
  const has = owns(owned, row ? row.key : null);
  if (has === null) {
    // «تعذّر التحقق» AND «ما زلنا نقرأ» ARE DIFFERENT SCREENS, and one of them used to swallow the
    // other: a manager holding `loyalty.manage` and not `billing.self` never triggers the
    // entitlement read at all, so this state stayed at its initial value and he met a grey
    // rectangle for ever — no programme, no lock, and no sentence (م · قاطع). `owns` now answers
    // «not yours to ask» with «show him the surface»; what is left here is the honest pair.
    if (isReady(owned) && !owned.checked) {
      return <EmptyState title="تعذّر التحقق من اشتراكك" description={owned.message} />;
    }
    if (hasFailed(owned)) {
      return <EmptyState title="تعذّر التحقق من اشتراكك"
                         description="والخلل عندنا. أعد المحاولة بعد قليل." />;
    }
    return <Skeleton height={160} />;
  }
  return has ? <>{children}</> : <LockedCard appId={appId} />;
}
