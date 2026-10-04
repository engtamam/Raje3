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
import { Button } from '../rj-ui/Button';
import { Card } from '../rj-ui/Card';
import { action, call, type Catalog } from '../catalog';
import { hasFailed, isReady, type Loading } from '../loading';
import { STORE_PATH } from '../nav';
import { APP_ROWS, owns, type Owned } from '../apps';
import { missingRequirement } from '../billingShared';
import { useSubscribeFlow } from '../subscribeFlow';
import type { Session } from '../session';
import { useOperatorI18n } from '../operator-i18n';
import './locked-i18n';

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
  const { t } = useOperatorI18n();
  const row = APP_ROWS.find((a) => a.id === appId);
  // ONE FLOW, EVERY LOCKED CARD — `subscribeFlow.ts`'s own header note explains why this is a
  // shared hook and not a second copy of `Plans.tsx`'s own subscribe sequence. Called unconditionally
  // (before the `!row` guard) because hooks must run in the same order on every render.
  const flow = useSubscribeFlow(session, catalog);
  if (!row) return null;
  const Icon = appIcon(row.icon);
  // INLINE FEATURES, WHEN OPERATIONS ITSELF OWNS THIS APP'S ROW (تسجيل زيارة/جهات الاتصال/
  // التقييم) — same lookup `Plans.tsx`'s own `AppCard` makes, so a card reads identically whether
  // it is drawn here or there.
  const ownedRow = owned && isReady(owned) && owned.checked
    ? owned.apps.find((a) => a.key === row.key) : undefined;
  const plan = row.key ? flow.planFor(row.key) : undefined;
  const lockedNote = plan ? missingRequirement(plan, owned ?? null, t) : '';
  // BUY LIVE, INLINE, RIGHT HERE — as soon as the action exists and the plan resolved. NOT
  // gated on whether a payment gateway/card-mint key is actually configured any more
  // (2026-09-20): this card already sits inside the screen whose job is selling this exact
  // app, so a "not ready yet" fallback that points right back at the same screen taught
  // nothing and went nowhere. The card form's own mint step (`payment.ts`) already answers
  // "not ready yet" honestly — `NO_CARD_FORM`, never a charge — at the one moment that
  // sentence is actually true. The store link below is now reserved for the real remaining
  // blockers: the plan itself unresolved, or a genuine prerequisite still missing
  // (`lockedNote`, e.g. تسجيل زيارة/الحجوزات's own `requires_any`) — never a dead button.
  const canBuyHere = Boolean(plan) && !lockedNote && flow.live(plan);
  return (
    <Card className="flex flex-col gap-3 p-4">
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
          if (!a) return Promise.reject(new Error(t('locked.featuresReadDenied')));
          return call(session, a);
        }}
        // SAME COLLAPSE EVERY OTHER CARD NOW HAS (owner's own instruction, 2026-09-11) — an
        // earlier decision held this ONE card exempt ("لا تعتيم على قائمة الميزات") on the theory
        // that a card arguing for a purchase must never hide its argument; a collapse behind one
        // press is not that — the full list is still one tap away, never gone.
        collapseAt={3}
      />

      {lockedNote ? <p className="text-xs text-warning">{lockedNote}</p> : null}
      {flow.error ? <p className="text-xs text-danger">{flow.error}</p> : null}

      {canBuyHere && plan ? (
        // INLINE, RIGHT HERE — same purchase `Plans.tsx` itself calls
        // (`subscription.activate`), not a re-implementation of it, and the store link stays one
        // press away below for the same shop on a screen where this app is not the only thing he
        // came to buy.
        <Button type="button" onClick={() => flow.subscribe(plan)} disabled={flow.busy}
                className="w-full">
          {flow.busy ? t('locked.subscribing') : t('locked.subscribeNow')}
        </Button>
      ) : (
        // THE FALLBACK — no live gateway, no plan resolved yet, or a prerequisite app still
        // missing. Never a dead buy button pretending to work; the store screen still explains
        // and still sells every app, plans and all.
        <Link
          to={STORE_PATH}
          className="rounded-control bg-accent px-3 py-2 text-center text-sm font-medium text-accent-contrast shadow-glow"
        >
          {t('locked.addFromStore')}
        </Link>
      )}
    </Card>
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
  const { t } = useOperatorI18n();
  const row = APP_ROWS.find((a) => a.id === appId);
  const has = owns(owned, row ? row.key : null);
  if (has === null) {
    // «تعذّر التحقق» AND «ما زلنا نقرأ» ARE DIFFERENT SCREENS, and one of them used to swallow the
    // other: a manager holding `loyalty.manage` and not `billing.self` never triggers the
    // entitlement read at all, so this state stayed at its initial value and he met a grey
    // rectangle for ever — no programme, no lock, and no sentence (م · قاطع). `owns` now answers
    // «not yours to ask» with «show him the surface»; what is left here is the honest pair.
    if (isReady(owned) && !owned.checked) {
      return <EmptyState title={t('locked.checkFailedTitle')} description={owned.message} />;
    }
    if (hasFailed(owned)) {
      return <EmptyState title={t('locked.checkFailedTitle')}
                         description={t('locked.checkFailedDescOurFault')} />;
    }
    return <Skeleton height={160} />;
  }
  return has ? <>{children}</> : <LockedCard appId={appId} session={session} catalog={catalog} owned={owned} />;
}
