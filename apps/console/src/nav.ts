/**
 * The nine sections — and which of them this person actually gets.
 *
 * THE NAV IS DERIVED, NOT WRITTEN. Each section declares the action ids it cannot exist without,
 * and a section whose actions are absent from the catalogue is not rendered. Since the gateway has
 * already filtered the catalogue by the caller's capabilities, that single rule produces three
 * different applications from one list:
 *
 *   an operator sees «تسجيل زيارة» and nothing else;
 *   a manager sees everything except what the owner keeps (billing, the account, roles);
 *   an owner sees all nine.
 *
 * WITHOUT ONE `if (role === …)` ANYWHERE, which matters more than it sounds. A role check in the
 * client is a second copy of the permission model, and the copy is the one that goes stale — a
 * capability added to a role next month would need a client release to become visible. Here it
 * appears on the next page load.
 *
 * AND A HIDDEN SECTION IS NOT A SECURITY MEASURE. The server refuses regardless; hiding is a
 * courtesy so a person is not offered what they cannot do (spec 10.8: "every element he does not
 * use is a tax he pays a hundred times a day").
 */
import type { LucideIcon } from 'lucide-react';
import {
  Building2, CalendarClock, ClipboardPlus, Gift, HandHeart, Handshake, Headphones, LifeBuoy,
  Megaphone, MessageSquare, Receipt, Share2, Star, TrendingUp, Truck, Users, Wrench,
} from 'lucide-react';
import { NAV_ACCENTS } from '../../../ui/packages/ui/src/theme';
import type { Catalog } from './catalog';
import { hasAll } from './catalog';

export interface Section {
  id: string;
  path: string;
  label: string;
  /**
   * THE ROW'S ONLY FACE WHEN THE RAIL IS COLLAPSED.
   *
   * The shell has taken `icon` since v0.16.x and we passed labels alone, so a collapsed rail — a
   * choice the shell PERSISTS per browser — drew seven blank rows with nothing but a hover target
   * on each. The owner who once collapsed it lost his whole navigation and had no way to know why:
   * the rows were there, sized and clickable, and utterly mute.
   *
   * Not decoration, then. In the collapsed state it IS the label.
   */
  icon: LucideIcon;
  /** Every id must be present for the section to appear. Empty = always available. */
  requires: string[];
  /** WHICH SERVICE PROVIDES ITS ACTIONS. Named so a section can survive its service being down:
   *  without it, a service that is unreachable takes its actions out of the catalogue, the
   *  capability filter below finds nothing, and the row simply vanishes — which the owner reads
   *  as «my subscription changed» or «I lost a permission», and he calls support about neither. */
  service?: string;
  /** THIS SECTION'S OWN ACTIVE-STATE COLOUR (2026-09-13) — one entry from `NAV_ACCENTS`, assigned
   *  by POSITION below so the whole rail reads as ten distinct sections rather than one flat
   *  amber for all of them (the owner's own instruction). */
  accent?: string;
}

/** A section as the shell must draw it: present, and possibly not usable right now. */
export interface SectionState extends Section {
  /** Its service did not answer. NOT «he may not have it» — a different sentence entirely. */
  unavailable: boolean;
}

/**
 * THE ORDER IS THE PRODUCT'S ARGUMENT, not an alphabet.
 *
 * «محلّي» first because it is what the product opens on: it answers «is everything running» at the
 * top and «how is my shop doing» underneath, which is what «اليوم» and «محلّي» each answered half
 * of. «تسجيل زيارة» second because it is the most repeated act in the building.
 *
 * A SHOP IN ITS FIRST WEEK STILL OPENS ON SOMETHING THAT WORKS, which is why the indicators could
 * not simply be promoted to first: they have nothing to show yet, and opening a paid product onto
 * «not enough data yet» is the worst first impression available. The merged page answers that by
 * ORDER rather than by address — what is running today is drawn whatever the snapshot holds.
 *
 * And the names are the thing rather than the system: «عملائي» not "the database", «الحملات» not
 * "templates and campaigns".
 */
export const SECTIONS: Section[] = [
  // ONE ROW WHERE THERE WERE TWO. «اليوم» and «محلّي» were the same visit split in half: he read
  // three tiles here and pressed «محلّي» to see the number he pays us for, every time. They are
  // now one page (Shop.tsx), and the rail is one row shorter — which on a phone is a row the eight
  // sections about the work get back.
  //
  // NOT `requires: []`. It was, on the old «اليوم», and an OPERATOR would have landed here first:
  // he has `operations.record` and nothing else, so every read this page makes 403s and the
  // product opens broken for the person who uses it most. It needs BOTH reads it is built out of,
  // and that costs nobody anything: the four office roles hold `reminders.read` and
  // `insights.read` together, and the two who hold neither (operator, partner) never saw either
  // half of this page.
  // The field screen: one action, and it is the one every operator has. FIRST IN THE RAIL
  // (2026-09-14, owner's own call) — «محلّي» moved below it: the counter screen is what most
  // sign-ins are actually for, and «محلّي» is a real dashboard nobody needs open by reflex.
  { service: 'operations', id: 'visit', path: '/visit', label: 'تسجيل زيارة', icon: ClipboardPlus, requires: ['operations.record_visit'], accent: NAV_ACCENTS[1] },
  // «محلّي» — MOVED DOWN, NOT REDEFINED. Its own path is `/shop` now, deliberately separate from
  // the INDEX route (`/`, Home.tsx) it used to double as: when both shared `/`, reordering this
  // array also silently changed what pressing «محلّي» itself showed — the exact bug the owner
  // caught live (clicking «محلّي» opened «تسجيل زيارة»'s content, because Home.tsx's own "first
  // available section" logic and this row's own link were answering the SAME route). Two
  // concerns, two routes now: this list's order is purely what the rail displays and in what
  // order; Home.tsx alone decides what `/` shows by default, and reads this same order to do it
  // — so moving a row here still affects the default landing screen, exactly as intended, without
  // ever breaking the row's own click target.
  {
    service: 'insights', id: 'shop', path: '/shop', label: 'محلّي', icon: TrendingUp,
    requires: ['reminders.today', 'insights.dashboard'], accent: NAV_ACCENTS[0],
  },
  // الحجوزات: نفس الباب الذي يفتح الزيارة (docs/وصف-تطبيق-الحجوزات.md §2.5) — من يحجز لعميلةٍ
  // هو نفسه من يفتح زيارتها حين تحضر، فالقسم يظهر بجانب «تسجيل زيارة» مباشرة، لا بعيداً عنه.
  { service: 'bookings', id: 'bookings', path: '/bookings', label: 'الحجوزات', icon: CalendarClock, requires: ['bookings.list'], accent: NAV_ACCENTS[2] },
  { service: 'coworking', id: 'coworking', path: '/coworking', label: 'مساحة عمل مشتركة', icon: Building2, requires: ['coworking.list_resources'], accent: NAV_ACCENTS[8] },
  { service: 'operations', id: 'customers', path: '/customers', label: 'جهات الاتصال', icon: Users, requires: ['operations.recent'], accent: NAV_ACCENTS[3] },
  // «التقييم» — WAS A TAB UNDER «عملائي» (رأي عميل هو حقيقة عن زيارته، نفس نطاق «عملائي»)، صار
  // قسماً قائماً بذاته لأن ما بناه هذا الإصدار (مقارنة الفريق، لوحة الصدارة، مصفوفة الأداء) صار
  // أداة إدارة قائمة بحد ذاتها، لا مجرد قائمة تقييمات. نفس بوابة `operations.ratings` التي كانت
  // تُظهر التبويب القديم.
  { service: 'operations', id: 'rating', path: '/rating', label: 'التقييم', icon: Star, requires: ['operations.ratings'], accent: NAV_ACCENTS[4] },
  // «ولاء الشركاء» — RENAMED 2026-09-22 from `coupons`/«تحالف استراتيجي» (id/path/label all moved
  // together, no live data existed yet). Backend capability names (`operations.coupons_page`,
  // `operations.grant_coupon*`) are left as-is on purpose — an internal permission id, never
  // shown to anyone, not part of this app's own identity the way id/path/label are. Gated on
  // `operations.coupons_page` (owner decision, 2026-09-19: two separate tiers now exist —
  // `operations.grant_coupon_direct` reaches this standalone page AND everything below, while the
  // weaker `operations.grant_coupon` alone reaches ONLY the visit-recording screen's own shortcut
  // checkbox, never this page). That split required decoupling: the actual grant action
  // (`operations.grant_coupon`, POST /coupons/grant) now accepts the WEAK capability too, so a
  // supervisor/operator/marketer can really submit a grant from the visit screen rather than see a
  // button that 403s — which means `operations.grant_coupon`'s presence in the catalogue can no
  // longer be used to gate THIS page. `operations.coupons_page` is a nav-only action id with no
  // route of its own, declared purely to still require the strong capability (user_actions.py has
  // the full note).
  { service: 'operations', id: 'partner-loyalty', path: '/partner-loyalty', label: 'ولاء الشركاء',
   icon: Handshake, requires: ['operations.coupons_page'], accent: NAV_ACCENTS[10] },
  // «تبادل منافع» — cross-tenant CUSTOMER referral (core/mutual_benefit.py's own
  // module docstring), never to be confused with the row above: «ولاء الشركاء» discounts OUR
  // OWN subscription price between two shops; this one moves real customers, backed by real
  // catalogue items, mutual-consent only. Gated on the plain list action — every holder of
  // `operations.manage` may propose, view and act on a partnership.
  { service: 'operations', id: 'mutual-benefit', path: '/mutual-benefit',
   label: 'تبادل منافع', icon: HandHeart,
   requires: ['operations.mutual_benefit_list'], accent: NAV_ACCENTS[12] },
  // «خدمات متنقلة» — a real sold app now (Phase 4, feature.mobile_requests); the row itself still
  // gates on the review queue's own list action (real per ci/check_ui_actions.py — an action id
  // the catalogue actually declares, never the bare capability string), and MobileRequestsRoute's
  // own AppGate is what draws the locked upgrade card for a shop that has not bought it yet.
  { service: 'operations', id: 'mobile-requests', path: '/mobile-requests', label: 'خدمات متنقلة',
   icon: Truck, requires: ['operations.mobile_requests_list'], accent: NAV_ACCENTS[11] },
  // «الإحالة والمسوّقين» — the ordinary CUSTOMER-to-CUSTOMER referral program (services/referrals'
  // campaigns + services/operations' redemption/reports), never to be confused with «شراكة
  // استراتيجية» (cross-TENANT) above. No entry in apps.ts: this is not a purchasable app tier,
  // just a capability every section inside the screen already checks — gated here on the plain
  // list action, same reasoning as «خدماتي ومنتجاتي».
  { service: 'referrals', id: 'referrals', path: '/referrals', label: 'الإحالة والمسوّقين',
   icon: Share2, requires: ['referrals.list_campaigns'], accent: NAV_ACCENTS[13] },
  // «طلبات التوصيل عبر الواتساب» — standalone delivery product (apps.ts's own note: never
  // confused with «خدمات متنقلة»). Gated on the list action, same shape as every other app row;
  // WhatsAppOrdersRoute's own AppGate draws the locked upgrade card for a shop that has not
  // bought it yet.
  { service: 'operations', id: 'whatsapp-orders', path: '/whatsapp-orders',
   label: 'طلبات التوصيل عبر الواتساب', icon: Receipt,
   requires: ['whatsapp_order.list'], accent: NAV_ACCENTS[14] },
  // «خدمات ما بعد البيع» — gated on the plain roster list action, same posture as every other
  // app row; FreelancersRoute's own AppGate draws the locked upgrade card for a shop that has not
  // bought it yet (and for one that has no touchpoint app to satisfy `plan.requires_any` with).
  { service: 'operations', id: 'freelancers', path: '/freelancers',
   label: 'خدمات ما بعد البيع', icon: Headphones,
   requires: ['operations.freelancer_list'], accent: NAV_ACCENTS[15] },
  // OPEN WHATEVER APPS THE SHOP HAS BOUGHT, and this comment used to say the opposite — it repeated a sentence
  // the spec has since corrected. The indicators are FREE (16.1): they are the demand engine, not
  // a feature to withhold. What `feature.insights.engine` locks is three of the twenty — the
  // association engine, the missed opportunities and the suggested bundles — and those are shown
  // LOCKED inside the section, never by hiding the section.
  //
  // Hiding it would break the sale it exists to make: «42 عميلاً معرّضون للضياع» is what sells the
  // messages that reach them, so an owner who cannot see it cannot see why he would pay. The
  // upgrade LINE lives inside «الحملات», where he is already thinking about reaching people, and
  // carries a number from his own shop rather than an advert (spec 10.8).
  //
  // The gate here is the CAPABILITY — a role that may read indicators — which is a different
  // question from which apps he bought.

  // ON THE WRITE. `operations.catalogue` is `operations.read`, which the SUPERVISOR and the
  // MARKETER both hold — and neither may change a price. A section whose every control is inert
  // is worse than an absent one: the person tries, is refused, and learns to distrust the screen.
  // «خدماتي ومنتجاتي», NOT «خدماتي» — the label is longer on purpose.
  //
  // This platform makes no distinction between the two: both are a line the owner configured, and
  // nothing downstream reads which noun he used. But the NAME did make one, and it excluded half
  // the market — a coffee shop or a spare-parts counter opening «خدماتي» reads a section that
  // apparently is not for them and does not open it again. The rail pays two extra words for a
  // trade that would otherwise think the product was not built for it.
  { service: 'operations', id: 'services', path: '/services', label: 'خدماتي ومنتجاتي', icon: Wrench, requires: ['operations.update_service'], accent: NAV_ACCENTS[5] },
  // `Megaphone`, NOT `MessageSquare` (2026-09-16, the owner's own instruction) — a chat-bubble
  // read as "a send/message icon", which is exactly the wrong metaphor for a campaign: this row
  // broadcasts an offer to many customers at once, closer to a megaphone than a single message.
  { service: 'reminders', id: 'messages', path: '/messages', label: 'الحملات', icon: Megaphone, requires: ['reminders.get_settings'], accent: NAV_ACCENTS[6] },
  // ON THE EDIT, NOT THE READ. `loyalty.settings.read` is `loyalty.read`, which the OPERATOR
  // holds — he has to see a customer's balance to say it out loud at the counter. Gating on it
  // would put a settings section in the nav of a man whose screen is one screen. The section
  // exists to change the programme, so it is gated on being able to.
  { service: 'loyalty', id: 'points', path: '/points', label: 'نقاط الولاء', icon: Gift, requires: ['loyalty.rewards.update'], accent: NAV_ACCENTS[7] },
  // «الدعم الفني» — the shop's own half of the support loop, the affiliate portal's
  // TicketCarousel being the other. `tickets.open` is ticket-service's own user action
  // (platform/services/ticket-service/app/user_actions.py) — `tickets.self`, granted to owner and
  // manager alike, same reasoning as every other row here: anyone who runs the shop day to day
  // may raise a problem, not the owner alone.
  //
  // NO LONGER A RAIL ROW OF ITS OWN — App.tsx filters this entry out of `navItems` and renders it
  // as a second icon beside «حسابي» in the shell's user block instead (SUPPORT_PATH above), same
  // move «حسابي» itself made and for the same reason: raising a problem is about the person
  // asking, not about the shop's own work the rest of the rail lists. The entry stays HERE,
  // unfiltered, so `tickets.open`'s gating and `check_roles.py`'s reachability check are both
  // still driven by one row, not two definitions of what "can this person reach support" means.
  { service: 'ticket-service', id: 'support', path: '/support', label: 'الدعم الفني', icon: LifeBuoy, requires: ['tickets.open'], accent: NAV_ACCENTS[9] },
  // «فريقي» IS NOT HERE EITHER — it is a tab inside «حسابي», beside «منشأتي» and «مفاتيح الربط».
  // The three answer one question, WHO AND WHAT MAY ACT IN THIS SHOP, and hiring is an errand done
  // once rather than a place to stand. The rail keeps the eight rows that are about the work.
  //
  // THE ROUTE STAYS. /team is still reachable and still rendered — a bookmark, a link in a message,
  // and the e2e suite all use it. Moving a section out of the rail is not deleting it.
  // «حسابي» IS NOT IN THIS LIST — it is the icon beside sign-out, and ACCOUNT_PATH below is where
  // it goes. It earned its place in the rail the way every other section does and then lost it for
  // a different reason: the rail is nine labels tall on a phone, and the one section that is not
  // about the shop was taking a full row from the eight that are.
  //
  // AND IT IS THE ONE SECTION THAT SURVIVES THE MOVE. `requires: []` — everybody has it whatever
  // their role — so it needs no filtering, which is exactly what makes it safe as a fixed control
  // rather than a derived row. The shell already draws it next to sign-out, in the same block, for
  // the same reason: both are about the person rather than about the work.
];

/** Where the account icon in the shell's user block leads. Not a Section: it is never filtered. */
export const ACCOUNT_PATH = '/account';

/** «الدعم الفني»'s own path, IN ADDITION TO its `SECTIONS` entry above — App.tsx still filters
 *  the row out of the rail itself and renders it as a second icon beside «حسابي» instead (same
 *  "about the person, not about the shop's own work" grouping the account icon already earned),
 *  but the entry stays in `SECTIONS` so `tickets.open`'s gating and `check_roles.py`'s own
 *  reachability check both still see it. This constant is only the route the icon navigates to,
 *  named once rather than re-typed at the one call site that needs it. */
export const SUPPORT_PATH = '/support';

/** «الدعم الفني» icon opens WHATSAPP DIRECTLY now, not `SUPPORT_PATH` — the owner's own
 *  instruction (2026-09-16): "خلي الايقونة معد تفك شاشة الدعم الفني، مستقبلا نرجع نربطها". The
 *  route/screen itself, and `SUPPORT_PATH` above, are left exactly as they are — only the icon's
 *  own handler in `App.tsx` was repointed — so relinking it later is a one-line revert, not a
 *  rebuild. `product.json`'s `support.phone` is a placeholder pending the owner's real number.
 *  `declare` matches `brand/theme.ts`'s own `__PRODUCT_ACCENT__` pattern — injected at build time
 *  by `vite.config.ts`, undefined under vitest, hence the same typeof guard. */
declare const __SUPPORT_WHATSAPP_PHONE__: string;
export const SUPPORT_WHATSAPP_URL =
  `https://wa.me/${typeof __SUPPORT_WHATSAPP_PHONE__ !== 'undefined' ? __SUPPORT_WHATSAPP_PHONE__ : '966500000000'}`;

/**
 * «فريقي», which left the rail and stayed a screen — and was named in a COMMENT alone.
 *
 * That is the whole of this constant's job. `check_roles.py` asks whether every screen a person
 * can open is reachable by some role, and it learns what the screens are from this file. A route
 * the router serves and this file mentions only in prose is a screen the gate does not know
 * exists: if no role held the hiring capability, `/team` would answer 403 to everybody and the
 * check written to catch exactly that would stay green.
 *
 * `ACCOUNT_PATH` above was already right for the same reason. This is its pair.
 */
export const TEAM_PATH = '/team';

/** «محلّي»'s OWN route (2026-09-14) — separate from `/`, the index route, on purpose now: the two
 *  used to be the same path, and reordering SECTIONS silently changed what pressing «محلّي»
 *  itself showed (see that row's own comment above for the bug this caused). `/` still exists and
 *  still opens on whichever section Home.tsx picks — normally «تسجيل زيارة» now — which may or
 *  may not be this one; `/shop` always, unambiguously, opens «محلّي». Named here IN CODE for the
 *  same reason TEAM_PATH is: a path the router serves and this file mentions only in prose is a
 *  screen `check_roles.py` cannot ask about. */
export const SHOP_PATH = '/shop';

/** Where an owner goes to buy — the launcher (`AppLauncher.tsx`, mounted at the index route in
 *  `main.tsx`), every app's own tile and the capacity shelf, all in one place.
 *
 *  WAS `/account?tab=billing` UNTIL 2026-09-19 — true the day it was written (that pane WAS the
 *  store then), and stayed wrong silently once the store moved to the launcher and
 *  `BillingStatusPane.tsx` replaced it with a payment-method fix and nothing else. Found live:
 *  every «أضِفه إلى اشتراكي» button in the product (`Locked.tsx`, `Team.tsx`,
 *  `SubscriptionBar.tsx`) sent an owner to a screen that could no longer sell him anything —
 *  Locked.tsx's own comment even still says "the store screen still explains and still sells
 *  every app", describing a screen this address had stopped opening.
 *
 *  Named once, so no screen builds the address out of a literal — every «أضِفه» button in the
 *  product points here. */
export const STORE_PATH = '/';

/** «مساعد واتساب» — never a rail row, reached from the app launcher tile (`apps.ts`'s own
 *  `openPath`) and from the AI-units gauge in the chrome (`AiUnitsGauge.tsx`), the same "opened
 *  from elsewhere, not chosen from the rail" shape TEAM_PATH describes. Gated by its own AppGate
 *  on owning `feature.whatsapp`, not by a `requires:` capability list, so `sections()` never sees
 *  it either way — named here, in code, for the same reason TEAM_PATH and ACCOUNT_PATH are:
 *  `check_roles.py` learns the screens a person can open from this file, and a route the router
 *  serves and this file mentions only in prose is a route the gate cannot ask any role about. */
export const WHATSAPP_ASSISTANT_PATH = '/whatsapp-assistant';

/** A sibling of `/`, outside `<App/>` on purpose (see main.tsx) — a legal document has to render
 *  for someone who has never signed up, so it carries no `requires:` and no section row. Named
 *  here, in code, for the same reason ACCOUNT_PATH and TEAM_PATH are: `check_roles.py` learns the
 *  screens a person can open from this file, and a route it never names in code is a route it
 *  cannot ask any role about. */
export const LEGAL_PATH = '/legal';

/** THE AFFILIATE PORTAL AND THE ADMIN PANEL ARE NOT SECTIONS OF THIS SHOP — they are their own
 *  products (their own session store, their own audience: a marketer or a platform operator, never
 *  a shop role), still registered on this router too for a link sent before their own subdomain
 *  existed (see main.tsx). `check_roles.py` measures shop roles against shop sections; neither of
 *  these is one, and naming them here — instead of leaving them for the gate to discover as an
 *  unexplained gap — is the honest exemption, not an omission. */
export const AFFILIATES_PATH = '/affiliates';
export const ADMIN_PATH = '/admin';

/** THE CATCH-ALL, on the affiliate and admin routers alone (main.tsx) — a 404/legacy fallback that
 *  renders one of the two portals above for any path their own router does not otherwise match.
 *  Never a screen a shop role could be asked to reach, so it earns the same named exemption. */
export const CATCH_ALL_PATH = '/*';

export function visibleSections(catalog: Catalog): SectionState[] {
  const down = new Set(catalog.unreachable);
  return SECTIONS
    // A SECTION WHOSE SERVICE IS DOWN STAYS IN THE RAIL (م · النمط 3). `unreachable` was declared
    // for exactly this and read by `isOutage` alone — which only fires when EVERY service is down.
    // So loyalty falling over by itself deleted «نقاط الولاء» from the rail without a word, and the
    // owner who pays for it phoned support about his permissions.
    .filter((s) => (s.service && down.has(s.service))
      || s.requires.length === 0 || hasAll(catalog, ...s.requires))
    .map((s) => ({ ...s, unavailable: Boolean(s.service && down.has(s.service)) }));
}

/**
 * The one case where an empty nav is not a permission answer.
 *
 * If every service the gateway asked was unreachable, the catalogue is empty for a reason that has
 * nothing to do with this person — and showing him a bare shell would tell him he has no access to
 * a product he pays for. The shell says the platform is unreachable instead, which is true and
 * which he can act on by waiting rather than by calling support about his account.
 */
export function isOutage(catalog: Catalog): boolean {
  return catalog.services.length === 0 && catalog.unreachable.length > 0;
}
