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
import type { Catalog } from './catalog';
import { hasAll } from './catalog';

export interface Section {
  id: string;
  path: string;
  label: string;
  /** Every id must be present for the section to appear. Empty = always available. */
  requires: string[];
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
  { id: 'today', path: '/', label: 'اليوم', requires: ['reminders.today'] },
  // The field screen: one action, and it is the one every operator has.
  { id: 'visit', path: '/visit', label: 'تسجيل زيارة', requires: ['operations.record_visit'] },
  { id: 'customers', path: '/customers', label: 'عملائي', requires: ['operations.recent'] },
  // Gated on the insights engine (feature.insights.engine) — a shop without it does not see the
  // section at all. The upgrade LINE lives inside «رسائلي», where he is already thinking about
  // reaching people, and carries a number from his own shop rather than an advert (spec 10.8).
  { id: 'shop', path: '/shop', label: 'محلّي', requires: ['insights.dashboard'] },
  // ON THE WRITE. `operations.catalogue` is `operations.read`, which the SUPERVISOR and the
  // MARKETER both hold — and neither may change a price. A section whose every control is inert
  // is worse than an absent one: the person tries, is refused, and learns to distrust the screen.
  // «خدماتي ومنتجاتي», NOT «خدماتي» — the label is longer on purpose.
  //
  // This platform makes no distinction between the two: both are a line the owner configured, and
  // nothing downstream reads which noun he used. But the NAME did make one, and it excluded half
  // the market — a coffee shop or a spare-parts counter opening «خدماتي» reads a section that
  // apparently is not for them and does not open it again. The rail pays two extra words for a
  // sector that would otherwise think the product was not built for it.
  { id: 'services', path: '/services', label: 'خدماتي ومنتجاتي', requires: ['operations.update_service'] },
  { id: 'messages', path: '/messages', label: 'رسائلي', requires: ['reminders.get_settings'] },
  // ON THE EDIT, NOT THE READ. `loyalty.settings.read` is `loyalty.read`, which the OPERATOR
  // holds — he has to see a customer's balance to say it out loud at the counter. Gating on it
  // would put a settings section in the nav of a man whose screen is one screen. The section
  // exists to change the programme, so it is gated on being able to.
  { id: 'points', path: '/points', label: 'نقاطي', requires: ['loyalty.rewards.update'] },
  // Same reasoning as «خدماتي»: listing employees is a read half the roles hold, and adding one
  // is the reason the section exists.
  { id: 'team', path: '/team', label: 'فريقي', requires: ['operations.create_operator'] },
  // `requires: []` IS CORRECT HERE AND NOWHERE ELSE. «حسابي» holds the things every person has
  // regardless of role — his password, his language, signing out — and the rows that are not his
  // (billing, the WhatsApp connection) are already hidden one by one inside the screen, from the
  // same catalogue. An operator opening it sees a short page rather than a broken one.
  { id: 'account', path: '/account', label: 'حسابي', requires: [] },
];

export function visibleSections(catalog: Catalog): Section[] {
  return SECTIONS.filter((s) => s.requires.length === 0 || hasAll(catalog, ...s.requires));
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
