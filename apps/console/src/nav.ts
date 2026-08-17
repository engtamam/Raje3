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
  CalendarCheck, ClipboardPlus, Gift, MessageSquare, TrendingUp, Users, Wrench,
} from 'lucide-react';
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
}

/** A section as the shell must draw it: present, and possibly not usable right now. */
export interface SectionState extends Section {
  /** Its service did not answer. NOT «he may not have it» — a different sentence entirely. */
  unavailable: boolean;
}

/**
 * THE ORDER IS THE PRODUCT'S ARGUMENT, not an alphabet.
 *
 * «اليوم» first because it is what the product opens on and what answers "is everything running".
 * «تسجيل زيارة» second because it is the most repeated act in the building. «محلّي» — the
 * indicators — sits fourth rather than second despite being what the top plan is bought for: it is
 * read once a week, and a shop in its first week has nothing to show there. Opening a product onto
 * "not enough data yet" is the worst first impression available.
 *
 * And the names are the thing rather than the system: «عملائي» not "the database", «رسائلي» not
 * "templates and campaigns".
 */
export const SECTIONS: Section[] = [
  // NOT `requires: []`. It was, and an OPERATOR would have landed here first: he has
  // `operations.record` and nothing else, so every read this screen makes 403s and the product
  // opens on a broken page for the person who uses it most. The section needs the read it is
  // built out of, exactly like every other one.
  { service: 'reminders', id: 'today', path: '/', label: 'اليوم', icon: CalendarCheck, requires: ['reminders.today'] },
  // The field screen: one action, and it is the one every operator has.
  { service: 'operations', id: 'visit', path: '/visit', label: 'تسجيل زيارة', icon: ClipboardPlus, requires: ['operations.record_visit'] },
  { service: 'operations', id: 'customers', path: '/customers', label: 'عملائي', icon: Users, requires: ['operations.recent'] },
  // OPEN TO ALL FOUR PLANS, and this comment used to say the opposite — it repeated a sentence
  // the spec has since corrected. The indicators are FREE (16.1): they are the demand engine, not
  // a feature to withhold. What `feature.insights.engine` locks is three of the twenty — the
  // association engine, the missed opportunities and the suggested bundles — and those are shown
  // LOCKED inside the section, never by hiding the section.
  //
  // Hiding it would break the sale it exists to make: «42 عميلاً معرّضون للضياع» is what sells the
  // messages that reach them, so an owner who cannot see it cannot see why he would pay. The
  // upgrade LINE lives inside «رسائلي», where he is already thinking about reaching people, and
  // carries a number from his own shop rather than an advert (spec 10.8).
  //
  // The gate here is the CAPABILITY — a role that may read indicators — which is a different
  // question from which plan he bought.
  { service: 'insights', id: 'shop', path: '/shop', label: 'محلّي', icon: TrendingUp, requires: ['insights.dashboard'] },
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
  { service: 'operations', id: 'services', path: '/services', label: 'خدماتي ومنتجاتي', icon: Wrench, requires: ['operations.update_service'] },
  { service: 'reminders', id: 'messages', path: '/messages', label: 'رسائلي', icon: MessageSquare, requires: ['reminders.get_settings'] },
  // ON THE EDIT, NOT THE READ. `loyalty.settings.read` is `loyalty.read`, which the OPERATOR
  // holds — he has to see a customer's balance to say it out loud at the counter. Gating on it
  // would put a settings section in the nav of a man whose screen is one screen. The section
  // exists to change the programme, so it is gated on being able to.
  { service: 'loyalty', id: 'points', path: '/points', label: 'نقاطي', icon: Gift, requires: ['loyalty.rewards.update'] },
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

export function visibleSections(catalog: Catalog): SectionState[] {
  const down = new Set(catalog.unreachable);
  return SECTIONS
    // A SECTION WHOSE SERVICE IS DOWN STAYS IN THE RAIL (م · النمط 3). `unreachable` was declared
    // for exactly this and read by `isOutage` alone — which only fires when EVERY service is down.
    // So loyalty falling over by itself deleted «نقاطي» from the rail without a word, and the
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
