/**
 * Our own Toggle — component #9. Same API as @base-ui/design-system/Toggle (checked/onChange/
 * disabled/label/testId), so a call site needs only the import changed. Dependency-free real
 * `<button role="switch">`, RTL-safe thumb travel via `rtl:` variants — a direct port, no scoped-
 * down risk the way rj-ui/Modal had: this one carries no shared state of its own to begin with.
 */
import { cn } from '@base-ui/lib/cn';

export interface RjToggleProps {
  checked: boolean;
  onChange: (checked: boolean) => void;
  disabled?: boolean;
  label?: string;
  testId?: string;
}

export function Toggle({ checked, onChange, disabled, label, testId }: RjToggleProps) {
  const sw = (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      aria-label={label}
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
