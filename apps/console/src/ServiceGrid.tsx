/**
 * The service grid — real photos, real cards, in a FIXED order.
 *
 * REDESIGNED 2026-09-14 (owner's own words: the old text-only tiles read "غبي" next to the rest
 * of the console, and this is the screen used a hundred times a day). Every card is now a real
 * tile — a photo where the shop has uploaded one, a warm placeholder where it has not — never a
 * bare label in a grey box. Packages are a first-class row of their own above the services, not a
 * feature bolted onto the same tile shape: a package is a bundle at its own price, and looks like
 * one.
 *
 * REMOVED (kept from the previous header, still true): a usage-weighted/contextual reorder was
 * tried and reverted — an operator memorizes WHERE a tile sits after a few days at the counter,
 * the same way he memorizes a keyboard, and a tile that moves breaks that memory on the one
 * screen used a hundred times a day. The order stays exactly what `services`/`packages` arrive
 * in (operations' own `sort` field, ascending).
 */
import { useEffect, useRef, useState } from 'react';
import { Check, Gift, ImageOff, Layers } from 'lucide-react';
import { type CataloguePackage, type CatalogueService, packageImageUrl, serviceImageUrl } from './api';
import type { Session } from './session';
import { riyals } from './money';
import { useOperatorI18n } from './operator-i18n';
import './service-grid-i18n';

export interface ServiceGridProps {
  session: Session;
  services: CatalogueService[];
  selected: string[];
  onToggle: (id: string) => void;
  /** Offerable-right-now packages, already filtered server-side (§9.4) — see `fetchCatalogue`'s
   *  own docstring. Absent/empty renders no package row at all, exactly like a shop with none. */
  packages?: CataloguePackage[];
  /** The package currently applied, or ''. Tapping a package toggles ALL of its own services at
   *  once and sets this; tapping it again clears both. Owned by the caller (Visit.tsx), not here,
   *  because saving the visit needs this id and the grid itself never talks to the server. */
  selectedPackageId?: string;
  onSelectPackage?: (pkg: CataloguePackage) => void;
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
}

/**
 * One photo, loaded once and revoked when it stops being needed — the same object-URL discipline
 * Services.tsx/PackagesTab.tsx already use for the manage-side image, applied here to the two
 * read-only mirrors those screens have no reason to call.
 *
 * KEYED BY (kind, id), NOT JUST id — a service and a package can share nothing about their ids by
 * construction (`svc_…`/`pkg_…`), but nothing here should rely on that prefix holding forever.
 */
function useCatalogueImages(
  session: Session,
  items: { kind: 'service' | 'package'; id: string; hasImage?: boolean }[],
): Record<string, string> {
  const [urls, setUrls] = useState<Record<string, string>>({});
  const loaded = useRef(new Set<string>());

  useEffect(() => {
    let stale = false;
    const wanted = items.filter((i) => i.hasImage && !loaded.current.has(`${i.kind}:${i.id}`));
    for (const item of wanted) {
      const key = `${item.kind}:${item.id}`;
      loaded.current.add(key);
      const fetcher = item.kind === 'service' ? serviceImageUrl : packageImageUrl;
      fetcher(session, item.id)
        .then((url) => { if (!stale) setUrls((cur) => ({ ...cur, [key]: url })); })
        // A PHOTO THAT FAILS TO LOAD SHOWS THE PLACEHOLDER, NOT A BROKEN SCREEN — the visit is
        // still recordable with no photo at all; a missing image is never a reason to block it.
        .catch(() => undefined);
    }
    return () => { stale = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [session, items.map((i) => `${i.kind}:${i.id}:${i.hasImage ? 1 : 0}`).join(',')]);

  useEffect(() => () => {
    for (const url of Object.values(urls)) URL.revokeObjectURL(url);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return urls;
}

/** A warm gradient standing in for a photo the shop has not uploaded yet — never a broken-image
 *  icon on a screen a customer can see over the operator's shoulder.
 *
 *  NO TEXT OF ITS OWN. The tile's own name label already says what this is — a second, hidden
 *  copy of the same name here duplicated the accessible name and broke `findByText` for every
 *  caller (booking_dialog.test.tsx caught this the first time it existed). */
function Placeholder() {
  return (
    <div
      aria-hidden
      className="grid h-full w-full place-items-center bg-gradient-to-br from-accent-soft to-surface-2 text-accent-on-soft"
    >
      <ImageOff size={22} strokeWidth={1.5} className="opacity-40" />
    </div>
  );
}

export function ServiceGrid({
  session, services, selected, onToggle, packages = [], selectedPackageId = '',
  onSelectPackage, offered, redeemable, points = {},
}: ServiceGridProps) {
  const { t } = useOperatorI18n();
  const items = [
    ...services.map((s) => ({ kind: 'service' as const, id: s.id, hasImage: s.has_image })),
    ...packages.map((p) => ({ kind: 'package' as const, id: p.id, hasImage: p.has_image })),
  ];
  const images = useCatalogueImages(session, items);

  return (
    <div className="flex flex-col gap-3">
      {/* THE PACKAGES, AS THEIR OWN ROW — wider cards, because a bundle carries a name, a price
          and a component count that a 3-across service tile has no room for. */}
      {packages.length > 0 ? (
        <div className="-mx-1 flex snap-x gap-2 overflow-x-auto px-1 pb-1">
          {packages.map((p) => {
            const on = selectedPackageId === p.id;
            const url = images[`package:${p.id}`];
            return (
              <button
                key={p.id}
                type="button"
                aria-pressed={on}
                onClick={() => onSelectPackage?.(p)}
                className={[
                  'relative flex h-28 w-48 shrink-0 snap-start flex-col justify-end overflow-hidden rounded-card text-start shadow-md transition-transform active:scale-[0.97]',
                  on ? 'ring-2 ring-accent ring-offset-2 ring-offset-surface-0' : '',
                ].join(' ')}
              >
                <div className="absolute inset-0">
                  {url ? (
                    <img src={url} alt="" className="h-full w-full object-cover" />
                  ) : (
                    <Placeholder />
                  )}
                </div>
                {/* A GRADIENT, NOT A FLAT SCRIM — legible text over ANY photo, bright or dark,
                    while still showing enough of the image to be worth having one. */}
                <div className="absolute inset-0 bg-gradient-to-t from-black/75 via-black/10 to-transparent" />
                <span className="relative m-2 inline-flex w-fit items-center gap-1 rounded-full bg-white/90 px-2 py-0.5 text-[10px] font-bold text-accent-on-soft backdrop-blur-sm">
                  <Layers size={11} aria-hidden />
                  {t('serviceGrid.package')}
                </span>
                <div className="relative flex flex-col gap-0.5 p-2.5 pt-0 text-white">
                  <span className="line-clamp-1 text-sm font-bold drop-shadow-sm">{p.name}</span>
                  <span dir="ltr" className="text-end text-xs font-semibold tabular-nums opacity-95">
                    {riyals(p.price_minor)} {t('serviceGrid.currency')}
                  </span>
                </div>
                {on ? (
                  <span
                    aria-hidden
                    className="absolute end-2 top-2 grid h-6 w-6 place-items-center rounded-full bg-accent text-white shadow-sm"
                  >
                    <Check size={14} strokeWidth={3} />
                  </span>
                ) : null}
              </button>
            );
          })}
        </div>
      ) : null}

      {/* THREE ACROSS ON A PHONE, NOT SIX. A photo tile needs real height to read as a photo
          rather than a stamp — the old h-16 text-only tile fit six across because it had nothing
          to show; a tile with a picture on it earns its own width. */}
      <div className="grid grid-cols-3 gap-2 sm:grid-cols-4 lg:grid-cols-5">
        {services.map((s) => {
          const on = selected.includes(s.id);
          const url = images[`service:${s.id}`];
          return (
            <button
              key={s.id}
              type="button"
              aria-pressed={on}
              onClick={() => onToggle(s.id)}
              className={[
                'group relative flex aspect-square flex-col overflow-hidden rounded-card text-start shadow-sm transition-transform active:scale-95',
                on ? 'shadow-md ring-2 ring-accent ring-offset-2 ring-offset-surface-0' : '',
              ].join(' ')}
            >
              <div className="absolute inset-0 bg-surface-2">
                {s.icon && !s.has_image ? (
                  // AN EMOJI ICON, WHEN THE SHOP SET ONE AND UPLOADED NO PHOTO — still better than
                  // the plain gradient, and free: every catalogue entry already carries one.
                  <div className="grid h-full w-full place-items-center bg-gradient-to-br from-accent-soft to-surface-2 text-4xl">
                    {s.icon}
                  </div>
                ) : url ? (
                  <img src={url} alt="" className="h-full w-full object-cover" />
                ) : (
                  <Placeholder />
                )}
              </div>
              <div className="absolute inset-0 bg-gradient-to-t from-black/70 via-black/0 to-transparent" />

              {/* WHAT THIS SERVICE CARRIES FOR HIM, ON THE SERVICE ITSELF. An offer and a
                  redeemable reward used to live on a page of their own, one swipe away — so the
                  operator had to remember, while looking at «تغيير زيت», that something applied
                  to it. The mark belongs where the decision is.
                  A MARK IS NOT A SPEND (§5.6.2). These say what is available; applying it is a
                  second, deliberate tap — «الصمت لا يصرف». */}
              {(offered?.has(s.id) || redeemable?.has(s.id)) ? (
                <span className="absolute end-1.5 top-1.5 flex gap-0.5 text-xs leading-none drop-shadow">
                  {offered?.has(s.id) ? <span title={t('serviceGrid.offered')}>🏷</span> : null}
                  {redeemable?.has(s.id) ? <span title={t('serviceGrid.redeemable')}>⭐</span> : null}
                </span>
              ) : null}

              {/* A CHECK MARK, NOT ONLY A COLOUR. Colour alone is invisible in direct sun on a
                  workshop floor, and it says nothing to an operator who cannot distinguish it. */}
              {on ? (
                <span
                  aria-hidden
                  className="absolute start-1.5 top-1.5 grid h-6 w-6 place-items-center rounded-full bg-accent text-white shadow-sm"
                >
                  <Check size={14} strokeWidth={3} />
                </span>
              ) : null}

              <span className="relative mt-auto line-clamp-2 px-1.5 pb-1 text-xs font-semibold leading-tight text-white drop-shadow-sm sm:text-sm">
                {s.name}
              </span>

              {/* WHAT IT EARNS HIM — bottom-start, only when the shop has actually set a number
                  above zero for it. */}
              {(points[s.id] ?? 0) > 0 ? (
                // `dir="ltr"` OR THE SIGN JUMPS SIDES. In a right-to-left run the bidi algorithm
                // moves a leading «+» to the other end of the number, so «+100» rendered as
                // «100+» — read as "100 or more" rather than "earns 100".
                <span
                  dir="ltr"
                  className="relative mx-1.5 mb-1.5 inline-flex w-fit items-center gap-0.5 rounded-full bg-white/90 px-1.5 py-px text-[10px] font-bold leading-none text-accent-on-soft"
                >
                  <Gift size={9} aria-hidden />
                  +{points[s.id]}
                </span>
              ) : null}
            </button>
          );
        })}
      </div>
    </div>
  );
}
