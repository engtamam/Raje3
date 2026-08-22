/**
 * Our own Segmented — component #7. Same API as @base-ui/design-system/Segmented (options/value/
 * onChange/className/ariaLabel/testId/disabled — `help` omitted, nothing in this app used it), so
 * a call site needs only the import changed. The kit's own call-site override in Customers.tsx
 * (`className="flex w-full [&>button]:flex-1 ..."`, to stop two long Arabic labels wrapping
 * ragged on a phone) still works unchanged — same base classes, merged the same way via `cn`.
 */
import { cn } from '@base-ui/lib/cn';

export interface RjSegmentedOption<T extends string> {
  value: T;
  label: string;
  hint?: string;
}

interface RjSegmentedProps<T extends string> {
  options: RjSegmentedOption<T>[];
  value: T | null;
  onChange: (value: T) => void;
  className?: string;
  ariaLabel?: string;
  testId?: string;
  disabled?: boolean;
}

export function Segmented<T extends string>({
  options, value, onChange, className, ariaLabel, testId, disabled,
}: RjSegmentedProps<T>) {
  return (
    <div
      role="radiogroup"
      aria-label={ariaLabel}
      aria-disabled={disabled || undefined}
      data-testid={testId}
      className={cn(
        'inline-flex flex-wrap gap-1 rounded-lg border border-border-subtle bg-surface-2 p-1',
        disabled && 'opacity-60',
        className,
      )}
    >
      {options.map((opt) => {
        const active = opt.value === value;
        return (
          <button
            key={opt.value}
            type="button"
            role="radio"
            aria-checked={active}
            disabled={disabled}
            title={opt.hint}
            data-testid={testId ? `${testId}-${opt.value}` : undefined}
            onClick={() => onChange(opt.value)}
            className={cn(
              // min-h-11 (44px) — the accessible touch-target floor, same reasoning platform/ui's
              // own AppShell nav rows and rj-ui/Button's `lg` size already settled on.
              'inline-flex min-h-11 items-center justify-center rounded-md px-3 py-1.5 text-sm font-medium transition-colors focus-ring',
              disabled && 'cursor-not-allowed',
              active
                ? 'bg-accent text-accent-contrast shadow-sm'
                : 'text-text-secondary hover:bg-surface-3 hover:text-text-primary',
            )}
          >
            {opt.label}
          </button>
        );
      })}
    </div>
  );
}
