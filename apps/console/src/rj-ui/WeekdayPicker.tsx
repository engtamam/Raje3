/**
 * A multi-select weekday chip row — component #22, extracted from `PackagesTab.tsx`'s own
 * `weekdays()`/pill JSX (its recurrence picker), which had this exact shape and no shared
 * component to live in yet. Values are Monday=0..Sunday=6 (Python's own `date.weekday()`,
 * `operations/core/scheduling.py::recurrence_weekdays`, and now campaigns'
 * `Campaign.window_weekdays`) — `PackagesTab.tsx` already orders its OWN labels Saturday-first
 * (the Saudi week) while keeping these same ISO values, and callers here should do the same: this
 * component takes whatever `{value, label}` list the caller already built with its own `t()`,
 * rather than owning day names itself (a shared UI component is not the place to own translated
 * copy — see PackagesTab.tsx/Rating.tsx's own convention of building label lists per screen).
 */
export interface WeekdayOption {
  value: number;
  label: string;
}

export function WeekdayPicker({ options, selected, onChange, ariaLabel }: {
  options: WeekdayOption[];
  selected: number[];
  onChange: (selected: number[]) => void;
  ariaLabel?: string;
}) {
  return (
    <div className="flex flex-wrap gap-1" role="group" aria-label={ariaLabel}>
      {options.map((w) => {
        const checked = selected.includes(w.value);
        return (
          <button
            key={w.value}
            type="button"
            aria-pressed={checked}
            onClick={() => onChange(
              checked ? selected.filter((x) => x !== w.value) : [...selected, w.value],
            )}
            className={
              'rounded-full px-3 py-1 text-xs font-medium transition-colors ' +
              // HOLLOW WHEN UNCHECKED (2026-09-14, the owner's own report): this filled every
              // unselected day with surface-2, and the day it stopped being a barely-there tint
              // (the same colour redesign that widened surface-2 for real contrast elsewhere) it
              // read as a solid tan block — the exact "everything is one colour" complaint, just
              // in a component this pass never found because it lives outside Launch.tsx. Checked
              // stays the SAME ink inversion rj-ui/Segmented.tsx already settled on deliberately
              // (2026-09-07: purple reserved for the one real "press this" action, never for
              // "this is selected") — only the unchecked fill changes, to a bordered white chip.
              (checked ? 'bg-text-primary text-surface-1'
                       : 'bg-surface-1 border border-border-subtle text-text-secondary hover:bg-surface-3')
            }
          >
            {w.label}
          </button>
        );
      })}
    </div>
  );
}
