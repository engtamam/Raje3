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
import { Link } from 'react-router-dom';
import { AppFeatureList, appIcon, toneClasses } from '../rj-ui/AppFeatureList';
import { EmptyState } from '../rj-ui/EmptyState';
import { Skeleton } from '../rj-ui/Skeleton';
import { action, call, type Catalog } from '../catalog';
import { hasFailed, isReady, type Loading } from '../loading';
import { STORE_PATH } from '../nav';
import { APP_ROWS, owns, type Owned } from '../apps';
import type { Session } from '../session';

/**
 * NO BLUR, NO DIMMING — the full real feature list, exactly as `شرائي`'s own card shows it. The
 * artifact mockup's own review settled this: a card's whole job here is to convince, so hiding
 * what it says removes information without protecting anything (2026-09-11 design pass). Only the
 * action at the bottom differs from the owned card — a link to the store, never a buy button of
 * its own, since purchasing runs through `subscription.activate`'s own rules (WhatsApp-connect
 * ordering, `plan.requires_any`) that this card has no business re-implementing.
 */
export function LockedCard({ appId, session, catalog, owned }: {
  appId: string; session: Session; catalog: Catalog; owned?: Loading<Owned>;
}) {
  const row = APP_ROWS.find((a) => a.id === appId);
  if (!row) return null;
  const Icon = appIcon(row.icon);
  // INLINE FEATURES, WHEN OPERATIONS ITSELF OWNS THIS APP'S ROW (تسجيل زيارة/جهات الاتصال/
  // التقييم) — same lookup `Plans.tsx`'s own `AppCard` makes, so a card reads identically whether
  // it is drawn here or there.
  const ownedRow = owned && isReady(owned) && owned.checked
    ? owned.apps.find((a) => a.key === row.key) : undefined;
  return (
    <section className="flex flex-col gap-3 rounded-card bg-surface-1 p-4 shadow-sm">
      <header className="flex items-center gap-2.5">
        <span aria-hidden className={['grid h-10 w-10 shrink-0 place-items-center rounded-full', toneClasses(row.tone)].join(' ')}>
          <Icon size={18} />
        </span>
        <div>
          <h2 className="text-sm font-medium">{row.name}</h2>
          <p className="text-xs text-text-secondary">{row.what}</p>
        </div>
      </header>

      <AppFeatureList
        features={ownedRow?.features}
        actionId={row.featuresAction}
        fetcher={(actionId) => {
          const a = action(catalog, actionId);
          if (!a) return Promise.reject(new Error('لا صلاحية لقراءة مميزات هذا التطبيق'));
          return call(session, a);
        }}
      />

      {/* THE BUTTON GOES TO THE PLACE THAT SELLS, and it is a LINK rather than a call: buying
          runs through `subscription.activate`, which is the only path that enforces the rule
          that a paid subscription needs WhatsApp connected first. */}
      <Link
        to={STORE_PATH}
        className="rounded-control bg-accent px-3 py-2 text-center text-sm font-medium text-accent-contrast shadow-glow"
      >
        أضِفه من متجر التطبيقات
      </Link>
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
  { appId, owned, session, catalog, children }:
  { appId: string; owned: Loading<Owned>; session: Session; catalog: Catalog; children: React.ReactNode },
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
  return has ? <>{children}</> : <LockedCard appId={appId} session={session} catalog={catalog} owned={owned} />;
}
