/**
 * The service grid — big buttons, and an order that moves.
 *
 * Two kinds of intelligence, and they are different (spec 4.4):
 *
 *   BASELINE     what this shop asks for most, so the common work is in the first row before a
 *                finger has moved.
 *   CONTEXTUAL   the moment the first service is chosen, what is usually bought WITH it rises.
 *                This is the part that pays for itself twice — it shortens the reach, and it
 *                reminds the operator of the service he and the customer both forgot.
 *
 * BUT THE ORDER FREEZES THE INSTANT HE STARTS CHOOSING — see `order` below. That was the trap.
 */
import { useMemo, useState } from 'react';
import type { CatalogueService } from './api';

export interface ServiceGridProps {
  services: CatalogueService[];
  selected: string[];
  onToggle: (id: string) => void;
  /** How often each service is chosen here — the baseline order. Supplied by the caller because
   *  it belongs to the establishment, not to this component. */
  weights?: Record<string, number>;
  /** What is usually chosen together, keyed by service id. Empty is a fine answer: a new shop has
   *  no associations yet, and inventing them would be a suggestion made up out of nothing. */
  together?: Record<string, string[]>;
  /** The owner may turn the learning off and arrange the grid himself (spec 4.4). */
  adaptive?: boolean;
}

export function ServiceGrid({
  services, selected, onToggle, weights = {}, together = {}, adaptive = true,
}: ServiceGridProps) {
  /**
   * THE ORDER IS COMPUTED ONCE PER ENTRY, FROM THE FIRST CHOICE ONLY — never from the whole
   * selection as it grows.
   *
   * The obvious implementation re-sorts on every tap. It is also unusable: the operator reaches
   * for the button he can see, and it moves out from under his finger between the decision and the
   * touch. He taps whatever slid into its place, and neither he nor we ever find out — the visit
   * records a service that was not performed, and the reminder for it goes out weeks later.
   *
   * So: sorted before he starts, re-sorted exactly once when the first service tells us what kind
   * of job this is, and then still until the screen clears.
   */
  const [anchor, setAnchor] = useState<string | null>(null);

  const ordered = useMemo(() => {
    const rows = [...services];
    if (!adaptive) return rows;                     // his own drag-and-drop order, untouched
    const lift = new Set(anchor ? together[anchor] ?? [] : []);
    return rows.sort((a, b) => {
      const la = lift.has(a.id) ? 1 : 0;
      const lb = lift.has(b.id) ? 1 : 0;
      if (la !== lb) return lb - la;
      return (weights[b.id] ?? 0) - (weights[a.id] ?? 0);
    });
  }, [services, adaptive, anchor, together, weights]);

  const suggested = new Set(anchor ? together[anchor] ?? [] : []);

  return (
    /* THREE ACROSS ON A PHONE AT 64px, NOT 96. Sixteen tiles at h-24 filled a phone screen
       entirely — the operator could not see the customer field at all without scrolling past
       everything he sells, on the one screen used a hundred times a day. */
    <div className="grid grid-cols-3 gap-2 sm:grid-cols-4 lg:grid-cols-6">
      {ordered.map((s) => {
        const on = selected.includes(s.id);
        return (
          <button
            key={s.id}
            type="button"
            aria-pressed={on}
            onClick={() => {
              if (!anchor && !on) setAnchor(s.id);
              onToggle(s.id);
            }}
            className={[
              'relative flex h-16 flex-col items-center justify-center gap-0.5 rounded-xl',
              'px-2 text-center text-xs font-semibold leading-tight transition-transform sm:text-sm',
              'active:scale-95',
              on
                ? 'bg-accent text-white shadow-md'
                : 'bg-surface-1 text-text-primary shadow-sm',
            ].join(' ')}
          >
            {s.icon ? <span className="text-base leading-none">{s.icon}</span> : null}
            <span className="line-clamp-2">{s.name}</span>
            {/* A CHECK MARK, NOT ONLY A COLOUR. Colour alone is invisible in direct sun on a
                workshop floor, and it says nothing to an operator who cannot distinguish it. */}
            {on ? (
              <span aria-hidden className="absolute top-1 start-2 text-base leading-none">✓</span>
            ) : null}
            {/* The nudge, and only while it is true — a hint that stays after the selection has
                moved on is noise the operator learns to look past. */}
            {!on && suggested.has(s.id) ? (
              <span className="absolute bottom-1 text-[10px] font-normal text-accent">
                يُطلب غالباً معاً
              </span>
            ) : null}
          </button>
        );
      })}
    </div>
  );
}
