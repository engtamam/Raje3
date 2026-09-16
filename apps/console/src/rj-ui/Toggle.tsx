/**
 * Our own Toggle — component #9. Same API as @base-ui/design-system/Toggle (checked/onChange/
 * disabled/label/testId), so a call site needs only the import changed. Dependency-free real
 * `<button role="switch">`, RTL-safe thumb travel via `rtl:` variants — a direct port, no scoped-
 * down risk the way rj-ui/Modal had: this one carries no shared state of its own to begin with.
 */
import { cn } from '../cn';

export interface RjToggleProps {
  checked: boolean;
  onChange: (checked: boolean) => void;
  disabled?: boolean;
  /** VISIBLE text beside the switch. Only pass this when nothing else on the row already says
   *  what the switch does — a row that already carries its own title/description should use
   *  `ariaLabel` instead, or the switch ends up naming itself twice on screen. */
  label?: string;
  /** The accessible name, said only to a screen reader — for a switch that sits beside a title
   *  and description already visible on the row, so it is not silently nameless to `role="switch"`
   *  without also printing that title a second time next to it. */
  ariaLabel?: string;
  testId?: string;
}

export function Toggle({ checked, onChange, disabled, label, ariaLabel, testId }: RjToggleProps) {
  const sw = (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      aria-label={label ?? ariaLabel}
      disabled={disabled}
      data-state={checked ? 'checked' : 'unchecked'}
      onClick={() => onChange(!checked)}
      data-testid={testId}
      className={cn(
        'relative inline-flex h-5 w-9 shrink-0 items-center rounded-full transition-colors outline-none focus-ring',
        checked ? 'bg-accent' : 'bg-surface-3',
        disabled && 'opacity-50',
      )}
    >
      <span
        className={cn(
          'block h-4 w-4 rounded-full bg-white shadow transition-transform',
          checked ? 'translate-x-[18px] rtl:-translate-x-[18px]' : 'translate-x-0.5 rtl:-translate-x-0.5',
        )}
      />
    </button>
  );
  if (!label) return sw;
  return (
    <label className="inline-flex cursor-pointer items-center gap-2 text-sm text-text-secondary">
      {sw}
      <span>{label}</span>
    </label>
  );
}
