/**
 * The service grid — big buttons, in a FIXED order.
 *
 * REMOVED (2026-09-04): a usage-weighted/contextual reorder ("what this shop asks for most rises
 * to the top; the moment a service is chosen, what is usually bought with it rises further").
 * The idea was sound but the effect was not: an operator memorizes WHERE a service sits after a
 * few days at the counter, the same way he memorizes a keyboard — and a tile that can move breaks
 * that memory every time, on the one screen used a hundred times a day. Worse, neither caller
 * (Visit.tsx, BookingDialog.tsx) ever actually supplied real `weights`/`together` data, so this
 * was a live trap: the day someone wired real usage numbers in, tiles would start sliding under
 * operators' fingers with no warning, exactly the failure this file's own PREVIOUS header called
 * out as "the trap" and thought it had closed by freezing the order per-visit. Freezing per-visit
 * was not enough — the fix is FIXED, period: the same order `services` already arrives in
 * (operations' own `Service.sort` field, ascending — the same field the owner's «خدماتي
 * ومنتجاتي» screen displays by), never recomputed here.
 */
import type { CatalogueService } from './api';

export interface ServiceGridProps {
  services: CatalogueService[];
  selected: string[];
  /** Services his live offer applies to — empty means the offer is shop-wide, not per service. */
  offered?: Set<string>;
  /** Services he could take with the points he holds right now. */
  redeemable?: Set<string>;
  /**
   * What each service EARNS him, by service id — the third thing the tile was missing.
   *
   * WHY ON THE TILE AND NOT ON A SETTINGS PAGE. The operator is the one person who can say it out
   * loud at the right moment: «هذي تجيب لك 5 نقاط». He cannot say it if the number lives two
   * screens away, and a loyalty programme nobody mentions at the counter is a line in a database.
   *
   * ABSENT MEANS ABSENT. A service with no number shows nothing rather than a zero — zero is a
   * decision the shop made about that service, and printing it on every tile of a shop that has
   * not set points up yet is sixteen zeros telling him the feature is broken.
   */
  points?: Record<string, number>;
  onToggle: (id: string) => void;
}

export function ServiceGrid({
  services, selected, onToggle, offered, redeemable, points = {},
}: ServiceGridProps) {
  return (
    /* THREE ACROSS ON A PHONE AT 64px, NOT 96. Sixteen tiles at h-24 filled a phone screen
       entirely — the operator could not see the customer field at all without scrolling past
       everything he sells, on the one screen used a hundred times a day. */
    <div className="grid grid-cols-3 gap-2 sm:grid-cols-4 lg:grid-cols-6">
      {services.map((s) => {
        const on = selected.includes(s.id);
        return (
          <button
            key={s.id}
            type="button"
            aria-pressed={on}
            onClick={() => onToggle(s.id)}
            className={[
              'relative flex h-16 flex-col items-center justify-center gap-0.5 rounded-xl',
              'px-2 text-center text-xs font-semibold leading-tight transition-transform sm:text-sm',
              'active:scale-95',
              on
                ? 'bg-accent text-white shadow-md'
                : 'bg-surface-1 text-text-primary shadow-sm',
            ].join(' ')}
          >
            {/* WHAT THIS SERVICE CARRIES FOR HIM, ON THE SERVICE ITSELF. An offer and a
                redeemable reward used to live on a page of their own, one swipe away — so the
                operator had to remember, while looking at «تغيير زيت», that something applied to
                it. The mark belongs where the decision is.
                A MARK IS NOT A SPEND (§5.6.2). These say what is available; applying it is a
                second, deliberate tap — «الصمت لا يصرف». */}
            {(offered?.has(s.id) || redeemable?.has(s.id)) ? (
              <span className="absolute end-1 top-1 flex gap-0.5 text-xs leading-none">
                {offered?.has(s.id) ? <span title="عليه عرض">🏷</span> : null}
                {redeemable?.has(s.id) ? <span title="يمكن استبداله بنقاطه">⭐</span> : null}
              </span>
            ) : null}
            {s.icon ? <span className="text-base leading-none">{s.icon}</span> : null}
            <span className="line-clamp-2 px-1">{s.name}</span>
            {/* A CHECK MARK, NOT ONLY A COLOUR. Colour alone is invisible in direct sun on a
                workshop floor, and it says nothing to an operator who cannot distinguish it. */}
            {on ? (
              <span aria-hidden className="absolute top-1 start-2 text-base leading-none">✓</span>
            ) : null}
            {/* WHAT IT EARNS HIM. Bottom-start, opposite the badges, and only when the shop has
                actually set a number above zero for it. */}
            {(points[s.id] ?? 0) > 0 ? (
              // `dir="ltr"` OR THE SIGN JUMPS SIDES. In a right-to-left run the bidi algorithm
              // moves a leading «+» to the other end of the number, so «+100» rendered as «100+»
              // — read as "100 or more" rather than "earns 100".
              //
              // A PILL, NOT LOOSE TEXT. Sixteen bare numbers floating under sixteen names read as
              // debris on the tile; the same numbers in a soft chip read as one repeated fact.
              <span
                dir="ltr"
                className={`absolute bottom-1 start-1 rounded-full px-1.5 py-px text-[10px] font-medium leading-none ${
                  on ? 'bg-white/20 text-white' : 'bg-accent-soft text-accent-on-soft'
                }`}
              >
                +{points[s.id]}
              </span>
            ) : null}
          </button>
        );
      })}
    </div>
  );
}
