/**
 * FilterRail — component #29. A slim, sticky filter column beside a tab's own canvas — the same
 * shape the campaigns create screen's own goal rail already uses (Launch.tsx), extracted here so
 * every tab of «الحملات» that needs "pick one category and see only that" reads as one product,
 * not three screens that each invented their own filter chrome.
 *
 * REAL TOKENS ONLY — `bg-surface-1`/`border-border-subtle`/`bg-accent-soft` etc., never a
 * hand-picked hex. This is what lets the rail repaint itself correctly the moment the theme
 * itself changes (light/dark, a future rebrand) with zero edits here.
 */
import type { ReactNode } from 'react';
import { Card } from './Card';

export interface FilterRailItem {
  id: string;
  label: ReactNode;
  /** A small colour dot naming what this filter groups — e.g. a message class's own semantic
   *  tone, an urgency level, an outcome. Omitted for "الكل". */
  dotClassName?: string;
  /** A count beside the label, when the caller has one worth showing (never a fabricated 0). */
  count?: number;
}

export function FilterRail({ items, active, onChange, ariaLabel }: {
  items: FilterRailItem[];
  active: string;
  onChange: (id: string) => void;
  ariaLabel: string;
}) {
  return (
    <Card
      role="group"
      aria-label={ariaLabel}
      className="sticky top-4 flex h-fit flex-col gap-1 p-3"
    >
      {items.map((it) => (
        <button
          key={it.id}
          type="button"
          aria-pressed={active === it.id}
          onClick={() => onChange(it.id)}
          className={[
            'flex items-center justify-between gap-2 rounded-lg px-3 py-2 text-start text-sm font-medium transition-colors',
            active === it.id
              ? 'bg-accent-soft text-accent-on-soft ring-1 ring-inset ring-accent/30'
              : 'text-text-secondary hover:bg-surface-2',
          ].join(' ')}
        >
          <span className="flex min-w-0 items-center gap-2">
            {it.dotClassName ? (
              <span className={['h-2 w-2 shrink-0 rounded-full', it.dotClassName].join(' ')} aria-hidden />
            ) : null}
            <span className="truncate">{it.label}</span>
          </span>
          {typeof it.count === 'number' ? (
            <span className="shrink-0 text-xs tabular-nums text-text-muted">{it.count}</span>
          ) : null}
        </button>
      ))}
    </Card>
  );
}
