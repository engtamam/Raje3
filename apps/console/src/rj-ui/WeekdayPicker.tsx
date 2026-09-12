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
              (checked ? 'bg-text-primary text-surface-1' : 'bg-surface-2 text-text-secondary hover:bg-surface-3')
            }
          >
            {w.label}
          </button>
        );
      })}
    </div>
  );
}
