/**
 * The launcher's own app catalog — a fresh module, not a patch onto `nav.ts`/`apps.ts`.
 *
 * WHY A NEW FILE RATHER THAN A FIELD ON AN EXISTING ONE. The owner's own instruction (2026-09-16,
 * after the first attempt added a `category` field straight onto `nav.ts`'s `Section` interface):
 * a real redesign is a fresh start, not patchwork carrying the old rail's own shape into a screen
 * that no longer works the same way. This file READS `nav.ts` (`SECTIONS`, `visibleSections`) and
 * `apps.ts` (`APP_ROWS`, `owns`) — it does not touch either — and re-derives exactly what the
 * launcher needs: which category shelf each app sits on, and a merged view of "can this person
 * open it" (role, from `nav.ts`) plus "does this shop own it" (billing, from `apps.ts`).
 *
 * CATEGORISED FROM DAY ONE (2026-09-16 decision) — the app count is headed to 80+, where a single
 * flat grid stops being usable long before the sidebar it replaces ever would.
 */
import type { LucideIcon } from 'lucide-react';
import { visibleSections, SECTIONS, type SectionState } from '../nav';
import { APP_ROWS, owns, type AppFeature, type Owned } from '../apps';
import type { Catalog } from '../catalog';
import { isReady, type Loading } from '../loading';

export interface LauncherApp {
  id: string;
  label: string;
  what: string;
  icon: LucideIcon;
  accent: string;
  path: string;
  category: string;
  /** From billing (`apps.ts::owns`) — `null` while unknown, `true`/`false` once billing answered. */
  ownedByShop: boolean | null;
  /** His role cannot reach this section at all (a plain field operator and «الحملات», say) —
   *  distinct from `ownedByShop === false`: one is "buy it", the other is "not yours to open". */
  reachableByRole: boolean;
  unavailable: boolean;
  /** THE REAL FEATURE DATA the details window shows — same two-source split
   *  `AppFeatureList`/`Plans.tsx` already read (see that file's own note): already-known for an
   *  operations-owned app (`Owned.apps[].features`, inline with the same billing read), or
   *  fetched from `featuresAction` at the moment the window opens for every other app. Never
   *  both, and never invented here — a launcher card with no key/action for one of these simply
   *  shows none, same as `AppFeatureList` itself already handles that absence. */
  billingKey: string | null;
  featuresAction?: string;
  inlineFeatures?: AppFeature[];
}

/** ONE SHELF PER SECTION ID — kept here, separate from `nav.ts`, exactly so a rail entry never has
 *  to carry a launcher-only concern. A section absent from this map falls back to `general` rather
 *  than disappearing from the grid — a missing category is a cosmetic gap, never a reason to hide
 *  an app someone is entitled to open.
 *
 *  STABLE IDS, NOT DISPLAY TEXT — `launcher-i18n.ts` translates `launcher.category.<id>`; a screen
 *  reading a literal Arabic label straight out of this map (the pre-i18n version) could never be
 *  anything but Arabic no matter what the account's own language preference said. */
// FOUR SCALABLE SHELVES, NEVER A CATCH-ALL «عام» (2026-09-16, the owner's own instruction) — each
// one names a real, growing family of apps rather than a stage of this redesign:
//   operations — running the shop day to day (visit/bookings/services/محلّي's own dashboard,
//                خدمات متنقلة — moved here 2026-09-22 from growth: a service delivery channel,
//                same as bookings, not a way to reach new customers).
//   customers  — the relationship itself: who they are, what they thought, why they come back
//                (عملائي, التقييم, نقاط الولاء, ولاء الشركاء — moved here 2026-09-22 from growth: the
//                 owner's own framing is that a discount extended to a partner shop is an
//                 indirect LOYALTY mechanic between businesses, not customer acquisition).
//   growth     — reaching NEW attention or NEW revenue from outside the existing relationship
//                (الحملات, تبادل منافع, صفقات).
//   ai         — its own shelf on purpose, not folded into growth: المساعد الذكي is the first of
//                what this product's own roadmap already names as a growing AI line, and a shelf
//                that starts at one app still reads as a real category the day a second AI app
//                joins it, unlike a bucket named for a redesign phase.
// «العمليات اليومية»/«الولاء والتقييم» (the two prior, narrower shelves) are retired — see git
// history for why each specific app moved.
const CATEGORY_OF: Record<string, string> = {
  visit: 'operations',
  shop: 'operations',
  bookings: 'operations',
  services: 'operations',
  'mobile-requests': 'operations',
  customers: 'customers',
  rating: 'customers',
  points: 'customers',
  'partner-loyalty': 'customers',
  messages: 'growth',
  insights: 'growth',
  'mutual-benefit': 'growth',
  whatsapp: 'ai',
  'mobile-ai-assistant': 'ai',
};

const FALLBACK_CATEGORY = 'general';

function whatFor(id: string): string {
  // THE ONE REAL SENTENCE PER APP already exists in `apps.ts::APP_ROWS` — reused as-is rather than
  // invented again here, so a launcher card never says something Locked.tsx/Plans.tsx do not.
  return APP_ROWS.find((a) => a.section === id)?.what ?? '';
}

/** «تطبيقاتي» — only what this role may open at all, from the SAME derivation the rail itself
 *  uses (`visibleSections`), merged with billing's own owned/locked answer per app. */
export function myApps(catalog: Catalog, owned: Loading<Owned>): LauncherApp[] {
  const sections: SectionState[] = visibleSections(catalog).filter((s) => s.id !== 'support');
  const ownedApps = isReady(owned) ? owned.apps : [];
  const bySection = sections.map((s) => {
    // SECTION MATCH FIRST, ID AS FALLBACK — most rows tie to their nav section by `section`
    // (loyalty's row `id` is `loyalty` but its nav section is `points`, matched by `section`
    // alone). A few rows (تسجيل زيارة/التقييم) deliberately leave `section` blank in apps.ts —
    // that nav page is reachable by every shop server-side, not gated by a section match — so
    // for THOSE the nav section id and the row's own `id` are the same string instead. Matching
    // `section` only left «تسجيل زيارة» with no row at all here (found live: its details window
    // showed no features and no billing row, since `billingKey`/`inlineFeatures` below both read
    // straight off `row`).
    const row = APP_ROWS.find((a) => a.section === s.id) ?? APP_ROWS.find((a) => a.id === s.id);
    return {
      id: s.id,
      label: s.label,
      what: whatFor(s.id),
      icon: s.icon,
      accent: s.accent ?? '#6a4cf5',
      path: s.path,
      category: CATEGORY_OF[s.id] ?? FALLBACK_CATEGORY,
      ownedByShop: row ? owns(owned, row.key) : true,
      reachableByRole: true,
      unavailable: s.unavailable,
      billingKey: row?.key ?? null,
      featuresAction: row?.featuresAction,
      inlineFeatures: row ? ownedApps.find((a) => a.key === row.key)?.features : undefined,
    };
  });

  // SECTION-LESS BUT OWNED — `openPath` rows (no `section`, by definition) that this shop
  // actually bought (صفقات/المساعد الذكي — no rail row, their own config lives inside «محلّي»/
  // «حسابي»). Found live: المساعد الذكي showed «تجريبي» in «كل التطبيقات» yet never appeared
  // here at all, because this whole function only ever read "has a rail section" as if it meant
  // "is my app". `owns()` alone decides it here (never a bare `true` fallback the section branch
  // above uses) — a section-less app this shop has NOT bought belongs in «كل التطبيقات», not here.
  const byOwnership = APP_ROWS
    .filter((a) => !a.section && a.openPath && owns(owned, a.key) === true)
    .map((a) => ({
      id: a.id,
      label: a.name,
      what: a.what,
      icon: iconFor(a.icon),
      accent: accentFor(a.icon),
      path: a.openPath!,
      category: CATEGORY_OF[a.id] ?? FALLBACK_CATEGORY,
      ownedByShop: true,
      reachableByRole: true,
      unavailable: false,
      billingKey: a.key,
      featuresAction: a.featuresAction,
      inlineFeatures: ownedApps.find((o) => o.key === a.key)?.features,
    }));

  // NOT-YET-BOUGHT SECTIONS DO NOT BELONG HERE (found live, owner's own report): a section this
  // role may in principle SEE (`visibleSections`, same list the rail draws its own locked-upsell
  // rows from) is not the same question as "did this shop actually buy it" — and «تطبيقاتي»'s
  // whole reason to exist is answering the second one. `ownedByShop === false` is the one
  // definitive "no" (confirmed unowned, catalogue already answered); `true` and `null`/loading
  // both still belong here, so nothing flickers out mid-load only to vanish once billing answers.
  // A locked, unbought app's one and only home is «كل التطبيقات», right below.
  const bought = bySection.filter((a) => a.ownedByShop !== false);

  return [...bought, ...byOwnership];
}

/** «متجر التطبيقات» — the FULL catalog, whether or not this role may open it yet; the same
 *  data StoreRoute/PlanCards already sell from. A row with neither `section` NOR `openPath` (only
 *  الأساس, dead code) has nowhere to navigate at all and is skipped — صفقات/المساعد الذكي, whose
 *  own config lives inside an EXISTING screen rather than a rail row of its own, still get a real
 *  tile via `openPath` (found live: the launcher silently dropped these two against the owner's
 *  own comparison with the old متجر التطبيقات screen, which sold every row here regardless of
 *  whether it owned a page). */
export function allApps(owned: Loading<Owned>): LauncherApp[] {
  const ownedApps = isReady(owned) ? owned.apps : [];
  return APP_ROWS.filter((a) => a.section || a.openPath).map((a) => {
    const id = a.section || a.id;
    // THE RAIL'S OWN LABEL WINS when this row owns a real nav section — found live: جهات الاتصال
    // tied to «عملائي» (`section: 'customers'`) still showed as a SECOND, differently-named tile
    // next to «عملائي» itself, because this list kept reading the row's own `name` regardless.
    // One app, one name, in both «تطبيقاتي» and «كل التطبيقات» — never `a.name` for a row that
    // owns a section a person can also reach from «تطبيقاتي».
    const navSection = a.section ? SECTIONS.find((s) => s.id === a.section) : undefined;
    // THE RAIL'S OWN ACCENT WINS TOO, same reasoning as the label right above — found live: a row
    // that owns a real section showed one colour in «تطبيقاتي» (`nav.ts`'s own `NAV_ACCENTS`) and
    // a DIFFERENT one here (this file's own icon-keyed `ACCENTS` map, entirely unrelated). One
    // app, one colour, in both tabs — `accentFor(a.icon)` only still applies to a section-less
    // row (صفقات/المساعد الذكي), which has no rail accent to inherit at all.
    return {
      id,
      label: navSection?.label ?? a.name,
      what: a.what,
      icon: iconFor(a.icon),
      accent: navSection?.accent ?? accentFor(a.icon),
      path: a.section ? `/${a.section}` : a.openPath!,
      category: CATEGORY_OF[id] ?? FALLBACK_CATEGORY,
      ownedByShop: owns(owned, a.key),
      reachableByRole: true,
      unavailable: false,
      billingKey: a.key,
      featuresAction: a.featuresAction,
      inlineFeatures: ownedApps.find((o) => o.key === a.key)?.features,
    };
  });
}

// A SMALL ICON/ACCENT MAP OF ITS OWN — `apps.ts`'s `icon`/`tone` are keys meant for
// `rj-ui/AppFeatureList.tsx`'s own resolver (badge-scale icons), not this launcher's larger tiles;
// re-deriving here keeps this module independent rather than reaching into that resolver's
// internals for a shape it was never built to serve.
import {
  CalendarClock, ClipboardPlus, Gift, Handshake, Megaphone, MessageCircle, Star, Truck, Users,
  LayoutGrid,
} from 'lucide-react';

function iconFor(key: string): LucideIcon {
  switch (key) {
    case 'calendar': return CalendarClock;
    case 'check-circle': return ClipboardPlus;
    case 'gift': return Gift;
    case 'users': return Handshake;
    case 'megaphone': return Megaphone;
    // «المساعد الذكي عبر واتساب» — a real chat bubble, not the generic grid `default` was
    // silently falling back to (found live: apps.ts's own `icon: 'message-circle'` had no case
    // here at all). The owner's own instruction: it should read as WhatsApp chat, not "an app".
    case 'message-circle': return MessageCircle;
    case 'star': return Star;
    case 'truck': return Truck;
    case 'user-plus': return Users;
    default: return LayoutGrid;
  }
}
const ACCENTS: Record<string, string> = {
  calendar: '#5C7CFA', 'check-circle': '#2F9E44', gift: '#F08C00', users: '#7048E8',
  megaphone: '#E64980', star: '#0C8599', truck: '#D9480F', 'user-plus': '#495057',
};
function accentFor(key: string): string {
  return ACCENTS[key] ?? '#6a4cf5';
}
