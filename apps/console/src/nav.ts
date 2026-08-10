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
  { id: 'today', path: '/', label: 'اليوم', requires: [] },
  // The field screen: one action, and it is the one every operator has.
  { id: 'visit', path: '/visit', label: 'تسجيل زيارة', requires: ['operations.record_visit'] },
  { id: 'customers', path: '/customers', label: 'عملائي', requires: ['operations.recent'] },
  // Gated on the insights engine (feature.insights.engine) — a shop without it does not see the
  // section at all. The upgrade LINE lives inside «رسائلي», where he is already thinking about
  // reaching people, and carries a number from his own shop rather than an advert (spec 10.8).
  { id: 'shop', path: '/shop', label: 'محلّي', requires: ['insights.dashboard'] },
  { id: 'services', path: '/services', label: 'خدماتي', requires: ['operations.catalogue'] },
  { id: 'messages', path: '/messages', label: 'رسائلي', requires: ['reminders.get_settings'] },
  { id: 'points', path: '/points', label: 'نقاطي', requires: ['loyalty.settings.read'] },
  { id: 'team', path: '/team', label: 'فريقي', requires: ['operations.list_operators'] },
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
