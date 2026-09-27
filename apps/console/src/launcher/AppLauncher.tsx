/**
 * «متجر التطبيقات» الرئيسي — the launcher screen, phase 2 of the app-store redesign
 * (2026-09-16). Reads `nav.ts`/`apps.ts` through `launcherCatalog.ts` alone — neither file is
 * touched by this screen (the owner's own instruction: a fresh start, not a patch).
 *
 * TWO SHELVES, ONE SEARCH. «تطبيقاتي» is exactly `visibleSections` — the same list the rail
 * derives, so a role that cannot open a section never sees it offered here either. «كل التطبيقات
 * (المتجر)» is the full catalog, locked cards included — the same thing متجر التطبيقات/Plans.tsx
 * already sell, just browsable from the front door instead of a rail row away.
 */
import { useMemo, useRef, useState } from 'react';
import { useNavigate, useOutletContext } from 'react-router-dom';
import { Search } from 'lucide-react';
import Fuse from 'fuse.js';
import type { ShellContext } from '../shell-context';
import { APP_ROWS, type AppFeature } from '../apps';
import { action, call } from '../catalog';
import { useOperatorI18n, tf } from '../operator-i18n';
import { HeroBanner, type HeroSlide } from './HeroBanner';
import { AppTile } from './AppTile';
import { CartBar } from './CartBar';
import { myApps, allApps, type LauncherApp } from './launcherCatalog';
import { useAppBilling, includedAiCreditOf } from './useAppBilling';
import { appDisplayName, CapacityAddonCard, requiresAny, type Plan, type Subscription } from '../billingShared';
import { isDenied, isReady } from '../loading';
import './launcher-i18n';

/** ONE CAPACITY TILE — `Plans.tsx`'s own `CapacityAddonCard` stepper, plus the same in-place
 *  confirm step `AppDetailsModal.tsx`'s `BillingRow` already uses for "remove the last unit",
 *  reached through the SAME `billing.cancelApp` real action apps themselves cancel through
 *  (removing the last seat/branch unsubscribes the row entirely, same as any other app). */
function CapacityTile({ plan, sub, billing }: {
  plan: Plan; sub: Subscription | undefined;
  billing: ReturnType<typeof useAppBilling>;
}) {
  const { t } = useOperatorI18n();
  const [confirming, setConfirming] = useState(false);
  if (confirming && sub) {
    return (
      <div className="flex flex-col gap-2.5 rounded-card border border-danger/30 bg-danger-soft p-3">
        <p className="text-xs font-bold text-danger-on-soft">
          {tf(t, 'launcher.capacity.confirmRemoveTitle', { name: appDisplayName(plan) })}
        </p>
        <div className="flex gap-2">
          <button type="button" disabled={billing.cancelingAppId === sub.id}
                  onClick={() => { void billing.cancelApp(sub.id); setConfirming(false); }}
                  className="flex-1 rounded-full bg-danger py-2 text-xs font-bold text-danger-contrast disabled:opacity-60">
            {billing.cancelingAppId === sub.id ? t('launcher.billing.stopping') : t('launcher.billing.confirmCancelConfirm')}
          </button>
          <button type="button" onClick={() => setConfirming(false)}
                  className="rounded-full border border-border-subtle px-3 py-2 text-xs font-bold text-text-secondary">
            {t('launcher.billing.confirmCancelBack')}
          </button>
        </div>
      </div>
    );
  }
  return (
    <CapacityAddonCard
      plan={plan}
      sub={sub}
      busy={billing.capacityBusyPlanId === plan.id}
      sellable={billing.sellableBase}
      onBuyFirst={() => billing.choose(plan)}
      onChangeQuantity={(quantity) => sub && void billing.changeCapacityQuantity(plan, sub, quantity)}
      onRemoveLast={() => setConfirming(true)}
    />
  );
}

type Tab = 'mine' | 'all';

// THREE REAL APPS, THE SAME SENTENCES apps.ts ALREADY CARRIES — never copy invented for this one
// banner. Picked for variety (an assistant, a loyalty app, a rating app), not by any live ranking;
// a future pass could rotate these from real usage stats once that read exists. تحالف استراتيجي
// (coupons) DROPPED (2026-09-16, the owner's own instruction), replaced by التقييم — never a slide
// featuring an app already on a shelf together with two apps that are not, which is exactly the
// mismatch a cross-shop discount pitch made here.
const HERO_APP_IDS = ['whatsapp', 'rating', 'loyalty'] as const;
const HERO_GRADIENTS: Record<string, string> = {
  whatsapp: 'linear-gradient(120deg,#4c34c4,#8a4cf5 55%,#c084fc)',
  rating: 'linear-gradient(120deg,#0a8871,#00c2a8 55%,#5eead4)',
  loyalty: 'linear-gradient(120deg,#b8862b,#e8a13a 55%,#ffd27a)',
};

// THE REAL APP NAME BEHIND A DISCOUNT'S `owning_key` — a percentage with no target names nobody
// can act on it, exactly the gap the launcher's own discount/offer chips fill (see
// `AppDetailsModal.tsx`'s `OfferChip`/`AiUnitsChip` header notes).
function appNameOf(key: string): string {
  return APP_ROWS.find((a) => a.key === key)?.name ?? key;
}

function groupByCategory(apps: LauncherApp[]): Map<string, LauncherApp[]> {
  const map = new Map<string, LauncherApp[]>();
  for (const app of apps) {
    const list = map.get(app.category) ?? [];
    list.push(app);
    map.set(app.category, list);
  }
  return map;
}

export function AppLauncher() {
  const navigate = useNavigate();
  const { t } = useOperatorI18n();
  const { session, catalog, owned } = useOutletContext<ShellContext>();
  const [tabState, setTab] = useState<Tab>('mine');
  const [query, setQuery] = useState('');

  // «كل التطبيقات» (the store/browse tab) IS THE PURCHASE SURFACE — same principle the sidebar
  // itself already follows (`visibleSections`' own `requires` filter, read below by `myApps`).
  // `operations.manage` is the one capability owner AND manager both hold and every other real
  // role (field operator, shift supervisor, marketer) does not (roles.seed.json) — a field
  // operator has no `billing.self` either way, so browsing a shelf of apps he can never buy and
  // was never granted is not a feature for him, it is noise (and per-app locked-card upsell text
  // that names a price he cannot act on). He still gets «تطبيقاتي», already narrowed to exactly
  // what his own role reaches — nothing here changes that half.
  // GATED ON A REAL ACTION, NOT A BARE CAPABILITY STRING — `action(catalog, id)` looks up an
  // action BY ITS ID; `operations.manage` is only ever a `capability` FIELD on other actions,
  // never an action id of its own, so checking it directly always resolved to `undefined` for
  // everyone, owner and manager included (found live: the banner/store tab vanished for them
  // too). `operations.create_operator` is a real action id gated on exactly that capability
  // (services/operations/app/user_actions.py), and owner+manager are the only two roles that
  // hold it (roles.seed.json).
  const canBrowseStore = Boolean(action(catalog, 'operations.create_operator'));
  const tab: Tab = canBrowseStore ? tabState : 'mine';

  // SWIPE BETWEEN THE TWO TABS — the owner's own report: on a phone, reaching up to tap the tab
  // pill every time is friction a small horizontal drag removes. `touchStartX/Y` are refs, not
  // state — they change on every touchmove and must never trigger a re-render. RTL-correct: the
  // tab strip renders «تطبيقاتي» first (so it sits on the visual RIGHT in RTL) then «كل
  // التطبيقات» to its LEFT — a left-swipe (finger moving left, content "advancing" the same
  // direction the tabs are laid out) goes مين->all; a right-swipe reverses it. A vertical drag
  // (scrolling the page) is deliberately never mistaken for a swipe: `SWIPE_MIN_PX` alone would
  // fire on a diagonal scroll, so this also requires the horizontal move to dominate the vertical
  // one, not just clear a minimum.
  const touchStartX = useRef(0);
  const touchStartY = useRef(0);
  const SWIPE_MIN_PX = 60;
  const onTouchStart = (e: React.TouchEvent) => {
    touchStartX.current = e.touches[0].clientX;
    touchStartY.current = e.touches[0].clientY;
  };
  const onTouchEnd = (e: React.TouchEvent) => {
    if (!canBrowseStore) return;
    const dx = e.changedTouches[0].clientX - touchStartX.current;
    const dy = e.changedTouches[0].clientY - touchStartY.current;
    if (Math.abs(dx) < SWIPE_MIN_PX || Math.abs(dx) < Math.abs(dy) * 1.5) return;
    setTab(dx < 0 ? 'all' : 'mine');
  };

  // REAL SUBSCRIBE/CANCEL — the same logic `screens/Plans.tsx` already has, not a second copy
  // (see useAppBilling.ts's own header on why reuse matters here specifically: real money, a real
  // 3DS card flow). Computed here, ABOVE `everything` below, because `allApps` now needs
  // `planByKey` to know which rows are unlisted.
  const billing = useAppBilling(session, catalog);

  const mine = useMemo(() => myApps(catalog, owned), [catalog, owned]);
  // AN UNLISTED PLAN'S APP HAS EXACTLY ONE HOME: نفس تطبيقاتي، لمن يملكه فعلاً — never «كل
  // التطبيقات» too (found live, owner's own report: a plan marked `listed: false` — a negotiated,
  // invite-only deal, deploy/seed/plans.json's own convention — still rendered a full tile here
  // for every shop, plan-less and unpriced but visible, because `allApps` never checked listing at
  // all; only `useAppBilling`'s own `planByKey` silently dropped the PLAN, not the TILE).
  // `billing.planByKey` already excludes `listed === false` rows (useAppBilling.ts), so "does this
  // billingKey resolve to a real, listed plan" is the same read `AppTile`'s own `plan` lookup below
  // uses — one source of truth, not a second filter that could disagree with it.
  const everything = useMemo(
    () => (canBrowseStore
      ? allApps(owned).filter((a) => !a.billingKey || a.ownedByShop === true || billing.planByKey[a.billingKey])
      : []),
    [owned, canBrowseStore, billing.planByKey],
  );
  const active = tab === 'mine' ? mine : everything;

  // A DEPENDENCY IS RESOLVED BY billingKey ONLY, NEVER BY NAME — the same discipline every other
  // billing read in this file follows. `everything` (not `active`/the search-filtered list) so a
  // required app still resolves to a real, clickable tile even while a search term hides it from
  // the grid itself.
  const byBillingKey = useMemo(
    () => new Map(everything.filter((a) => a.billingKey).map((a) => [a.billingKey as string, a])),
    [everything],
  );

  // FUZZY, NOT SUBSTRING — a shop owner typing "الحجزت" (a real one-letter slip on "الحجوزات")
  // used to get zero results from plain `.includes()`; Fuse tolerates that without us hand-rolling
  // Arabic-aware Levenshtein matching ourselves. Re-created per `active` list (not per keystroke) —
  // building the index is the only expensive part, and `active` only changes on tab switch.
  const fuse = useMemo(
    () => new Fuse(active, { keys: ['label', 'what'], threshold: 0.35, ignoreLocation: true }),
    [active],
  );
  const filtered = useMemo(() => {
    const q = query.trim();
    if (!q) return active;
    return fuse.search(q).map((r) => r.item);
  }, [active, fuse, query]);

  const grouped = useMemo(() => groupByCategory(filtered), [filtered]);

  // THE SAME SEAM `Plans.tsx`'s OWN `AppFeatureList` CALLER ALREADY USES — `action(catalog, id)`
  // resolves the id against what THIS role may actually do (a locked/role-denied feature action
  // rejects here, never a silent empty list), then `call()` is the one real request.
  const fetchFeatures = useMemo(() => (actionId: string) => {
    const a = action(catalog, actionId);
    if (!a) return Promise.reject(new Error(t('launcher.tile.noFeaturesPermission')));
    return call<{ features: AppFeature[] }>(session, a);
  }, [catalog, session, t]);

  const heroSlides: HeroSlide[] = useMemo(() => (
    HERO_APP_IDS
      .map((id) => APP_ROWS.find((a) => a.id === id))
      .filter((row): row is NonNullable<typeof row> => Boolean(row))
      .map((row) => ({
        id: row.id,
        eyebrow: t('launcher.hero.eyebrow'),
        title: row.name,
        desc: row.what,
        gradient: HERO_GRADIENTS[row.id] ?? HERO_GRADIENTS.whatsapp,
        cta: row.section ? t('launcher.hero.ctaOpen') : t('launcher.hero.ctaDiscover'),
        onOpen: () => { if (row.section) navigate(`/${row.section}`); },
      }))
  ), [navigate, t]);

  // `mx-auto max-w-[1800px]` — ONE SHARED WIDTH, on every row except the hero. Found live on the
  // owner's own real 5120px-wide monitor: this whole column used to carry only side PADDING
  // (`px-4 sm:px-6`), never a ceiling, so on a genuinely huge screen every row just kept its
  // padding and grew to the full width regardless — the search box stayed a fixed `max-w-md`, but
  // the surrounding flex rows (and the tile GRID's own `minmax(200px,…)` tracks) stretched across
  // thousands of spare pixels, reading as "everything shoved to one side with a wall of empty
  // space beside it" once RTL's own block-start alignment put the real content on the right and
  // left the leftover width sitting empty and unclaimed. Centering ONE shared column fixes the
  // search bar, the tabs and the grid all at once, in the one place they actually share a
  // parent — the hero directly below still escapes it via its own negative margin, same as always.
  const CONTENT_WIDTH = 'mx-auto w-full max-w-[1800px] px-4 sm:px-6';

  return (
    <div
      className="flex flex-col gap-6 py-4 sm:py-6"
      onTouchStart={onTouchStart}
      onTouchEnd={onTouchEnd}
    >
      <div className={`flex flex-wrap items-center gap-3 ${CONTENT_WIDTH}`}>
        <div className="flex min-w-[200px] max-w-md flex-1 items-center gap-2 rounded-full border border-border-subtle bg-surface-1 px-4 py-2.5 shadow-sm">
          <Search size={16} className="shrink-0 text-text-muted" />
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder={t('launcher.search.placeholder')}
            className="w-full bg-transparent text-sm outline-none placeholder:text-text-muted"
          />
        </div>
      </div>

      {/* THE TAB SWITCH ITSELF ONLY EXISTS FOR OWNER/MANAGER — a field operator/shift supervisor
          has exactly one shelf that was ever his (`تطبيقاتي`, already narrowed to his own role by
          `myApps`/`visibleSections` below), so a control offering him a second, empty-of-purpose
          tab would be exactly the kind of "why does this exist" chrome the rail itself never
          shows him either (same principle, the owner's own words: "نفس مبدأ الشريط الجانبي"). */}
      {canBrowseStore ? (
        <div className={`flex gap-2 ${CONTENT_WIDTH}`}>
          <button
            type="button"
            onClick={() => setTab('mine')}
            className={`rounded-full px-5 py-2 text-sm font-bold transition ${tab === 'mine' ? 'bg-accent text-accent-contrast shadow-md' : 'border border-border-subtle bg-surface-1 text-text-secondary'}`}
          >
            {t('launcher.tab.mine')}
          </button>
          <button
            type="button"
            onClick={() => setTab('all')}
            className={`rounded-full px-5 py-2 text-sm font-bold transition ${tab === 'all' ? 'bg-accent text-accent-contrast shadow-md' : 'border border-border-subtle bg-surface-1 text-text-secondary'}`}
          >
            {t('launcher.tab.all')}
          </button>
        </div>
      ) : null}

      {/* FULL-BLEED, THE OWNER'S OWN INSTRUCTION — edge to edge with no side gutter, unlike every
          other row here which keeps the page's own padding. The negative margin isn't only
          cancelling THIS screen's own `px-4 sm:px-6` below — `AppShell`'s own content column
          (ui/'s shell, wraps every routed screen) carries its own `p-4 sm:p-6 md:p-8`, so without
          matching that scale here too the banner still sat inside a visible gutter one level up,
          never actually touching the rail. `HeroBanner` owns its own rounding; full-bleed reads
          wrong with a curved edge sitting flush against the viewport, so the radius is dropped
          here rather than inside the component itself (which still wants it for any OTHER caller
          that is not full width). */}
      {/* OWNER/MANAGER ONLY, SAME PRINCIPLE AS «كل التطبيقات» — the hero is a purchase pitch
          (every slide's own CTA either opens an owned app or, per its `HERO_APP_IDS`, invites
          buying one); a field operator/shift supervisor can act on neither, so it is only ever
          noise for a role that holds no `operations.manage` either way. */}
      {tab === 'mine' && !query && canBrowseStore ? (
        <div className="-mx-4 sm:-mx-6 md:-mx-8 [&>div]:rounded-none">
          <HeroBanner slides={heroSlides} />
        </div>
      ) : null}

      {/* `max-w-[1800px]` HERE, ON THE TILE GRID ONLY — never on the banner above (full-bleed
          stays full-bleed, the owner's own repeated instruction) and never on the page itself
          (`AppShell`'s own cap was removed platform-wide, on purpose, and stays removed). Found
          live on the owner's own real 5120px-wide monitor: a `minmax(200px, …)` grid with no
          ceiling of its own creates ~25 column TRACKS at that width; with only 5 real tiles, the
          other ~20 stay real (if empty) tracks under `auto-fill` and share the row's width
          equally, so the 5 real tiles were squeezed to the grid's own minimum (200px) while a
          huge span of genuinely-existing-but-invisible columns sat beside them — reading exactly
          like "everything moved to one side". Capping the ROW itself means there are only ~9
          tracks to begin with at that width, not 25 — the same handful of empty ones cost far
          less visible space, and normal 1280–1920px screens never even reach this cap. */}
      <div className="flex w-full max-w-[1800px] flex-col gap-6 px-4 sm:px-6">
      {filtered.length === 0 ? (
        <p className="py-10 text-center text-sm text-text-secondary">{t('launcher.noResults')}</p>
      ) : (
        [...grouped.entries()].map(([category, apps]) => (
          <div key={category} className="flex flex-col gap-3.5">
            <div className="flex items-center justify-between">
              <h2 className="flex items-center gap-2 text-[1.1rem] font-extrabold">
                <span className="h-2.5 w-2.5 rounded-[3px]" style={{ background: apps[0]?.accent }} />
                {t(`launcher.category.${category}`)}
              </h2>
              <span className="text-xs font-semibold text-text-muted">
                {apps.length === 1 ? t('launcher.appsCount.one') : tf(t, 'launcher.appsCount.many', { n: apps.length })}
              </span>
            </div>
            <div className="grid grid-cols-[repeat(auto-fill,minmax(200px,1fr))] gap-5">
              {apps.map((app) => {
                // MATCHED BY THE SAME `feature.*` KEY `launcherCatalog.ts` already carries as
                // `billingKey` — never by name, same discipline every other billing read in this
                // product follows.
                const plan = app.billingKey ? billing.planByKey[app.billingKey] : undefined;
                const sub = plan ? billing.subByPlanId[plan.id] : undefined;
                // «تطبيقاتي» IS PURE NAVIGATION NOW (the owner's own instruction, 2026-09-20) —
                // no price, no "التفاصيل" window, nothing renewal-related at all belongs there
                // any more; that shelf shows only the app itself, exactly like the sidebar rail
                // it mirrors. Every price/subscribe/cancel/feature-showcase behaviour stays
                // unchanged on «متجر التطبيقات» — the ONLY tab that ever sells anything.
                const showBilling = tab === 'all';
                // ONLY WHEN GENUINELY UNMET — a shop that already holds one of the required keys
                // (or whose ownership read has not settled/was denied) sees no badges at all, the
                // same posture `missingRequirement`'s own sentence already takes.
                const needsAny = showBilling && plan && app.ownedByShop !== true
                    && isReady(owned) && !isDenied(owned) && owned.checked
                    && !requiresAny(plan).some((k) => owned.keys.includes(k))
                  ? requiresAny(plan)
                  : [];
                const requiresAnyTiles = needsAny
                  .map((k) => byBillingKey.get(k))
                  .filter((a): a is LauncherApp => Boolean(a))
                  .map((a) => ({ label: a.label, icon: a.icon, accent: a.accent, onClick: () => navigate(a.path) }));
                return (
                  <AppTile
                    key={app.id}
                    hideDetails={!showBilling}
                    app={{
                      id: app.id, label: app.label, what: app.what, icon: app.icon, accent: app.accent,
                      locked: app.ownedByShop === false,
                      // A FREE/UNPRICED SECTION (no `plan` at all, e.g. «محلّي») IS ALWAYS
                      // "مفعّل" — it was never sold, so there is no ownership question to answer;
                      // the owner's own instruction (2026-09-16). A REAL PRICED APP instead reads
                      // its actual ownership off `plan`/`sub`, same classification the old متجر
                      // التطبيقات used (only real `Plan`s ever got a status badge there).
                      owned: plan ? app.ownedByShop === true : true,
                      trialing: Boolean(plan) && sub?.status === 'trialing',
                      vip: app.id === 'whatsapp',
                      inlineFeatures: app.inlineFeatures,
                      featuresAction: app.featuresAction,
                      requiresAny: requiresAnyTiles,
                    }}
                    onOpen={() => navigate(app.path)}
                    fetchFeatures={fetchFeatures}
                    inCart={showBilling && plan && app.ownedByShop === false
                      ? billing.cart.includes(plan.id) : undefined}
                    onToggleCart={showBilling && plan && app.ownedByShop === false
                      ? () => billing.toggleCart(plan) : undefined}
                    billing={showBilling && plan ? {
                      plan,
                      sellable: billing.sellableBase,
                      busy: billing.busy,
                      onSubscribe: () => billing.choose(plan),
                      cancelPending: Boolean(sub?.cancel_at_period_end),
                      renewsOn: billing.renewalDay(sub?.current_period_end),
                      canceling: billing.cancelingAppId === sub?.id,
                      onCancel: sub ? () => void billing.cancelApp(sub.id) : undefined,
                      undoingCancel: billing.undoingAppCancelId === sub?.id,
                      onUndoCancel: sub?.cancel_at_period_end ? () => void billing.undoCancel(sub.id) : undefined,
                      discount: billing.discountPreviews[plan.id],
                      potentialDiscount: billing.potentialDiscounts[plan.id],
                      discountAppName: billing.discountPreviews[plan.id]
                        ? appNameOf(billing.discountPreviews[plan.id].owning_key) : undefined,
                      potentialDiscountAppName: billing.potentialDiscounts[plan.id]
                        ? appNameOf(billing.potentialDiscounts[plan.id].owning_key) : undefined,
                      // THE PLATFORM-WIDE SWITCH (2026-09-19) — `undefined` (not 0) so the chip's
                      // own `!includedCreditMinor` guard drops it, same as a plan with no
                      // included allowance at all. Never shows an "included AI" promise for a
                      // feature answering nothing right now.
                      includedCreditMinor: billing.aiEnabled ? includedAiCreditOf(plan) : undefined,
                      unitsPerHalala: billing.unitsPerHalala,
                      cascadeNames: sub ? billing.cascadeTargets(sub.id).map((p) => appDisplayName(p)) : [],
                    } : undefined}
                  />
                );
              })}
            </div>
          </div>
        ))
      )}
      </div>

      {/* «السعة» — ONLY under «كل التطبيقات», NEVER «تطبيقاتي» (the owner's own instruction,
          2026-09-16): a seat/branch add-on is not a section a role opens, so it has no home on
          the "my apps" shelf at all — it belongs where every other purchasable thing does.
          ALWAYS shown here regardless of search, same as the hero banner's own "mine, no query"
          condition mirrors for the opposite tab — capacity is not part of the fuzzy app search
          either (it is not an `AppRow`), so it would never itself match a query anyway. */}
      {tab === 'all' && !query && billing.capacity.length > 0 ? (
        <div className="flex w-full max-w-[1800px] flex-col gap-3.5 px-4 sm:px-6">
          <div className="flex items-center justify-between">
            <h2 className="text-[1.1rem] font-extrabold">{t('launcher.category.capacity')}</h2>
          </div>
          {billing.capacityError ? <p className="text-sm text-danger">{billing.capacityError}</p> : null}
          <div className="grid grid-cols-[repeat(auto-fill,minmax(200px,1fr))] gap-5">
            {billing.capacity.map((plan) => (
              <CapacityTile
                key={plan.id}
                plan={plan}
                sub={billing.capacitySubs.find((s) => s.plan_id === plan.id)}
                billing={billing}
              />
            ))}
          </div>
        </div>
      ) : null}

      {tab === 'all' ? (
        <CartBar
          plans={billing.cartPlans}
          totalMinor={billing.cartTotalMinor}
          preview={billing.cartPreview}
          previewBusy={billing.cartPreviewBusy}
          previewError={billing.cartPreviewError}
          discounts={billing.discountPreviews}
          notice={billing.cartNotice}
          error={billing.cartError}
          busy={billing.cartBusy}
          onRemove={(planId) => {
            const plan = billing.cartPlans.find((p) => p.id === planId);
            if (plan) billing.toggleCart(plan);
          }}
          onCheckout={billing.checkout}
        />
      ) : null}

      {billing.notice ? (
        <p className="px-4 text-sm text-success sm:px-6">{billing.notice}</p>
      ) : null}
      {billing.error || billing.appCancelError || billing.undoCancelError ? (
        <p role="alert" className="px-4 text-sm text-danger sm:px-6">
          {billing.error || billing.appCancelError || billing.undoCancelError}
        </p>
      ) : null}
    </div>
  );
}
