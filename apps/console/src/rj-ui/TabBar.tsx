/**
 * Our own TabBar — the PAGE'S OWN top-level section switcher, deliberately a different shape
 * than `Segmented` (rj-ui/Segmented.tsx).
 *
 * WHY IT EXISTS, IN THE OWNER'S OWN WORDS: "التبويب العلوي ما يتم استخدام نوع الفلتر حق
 * التبويبات هذا اساسا ابدا ابدا! صاير كنها مسطرة تحتها مسطرة" — the top-level tab must never be
 * the same pill-on-a-track shape as a filter, because a page nesting a `Segmented` filter row (or
 * a nested sub-tab) under a `Segmented` top tab reads as two identical bars stacked on top of each
 * other, not "a page, and a choice inside it." `Segmented`'s own pill shape stays completely
 * unchanged — it is still correct for filters and for the nested sub-tabs already marked
 * `size="sm"` (Team.tsx under حسابي, AdminProviderSecrets.tsx's provider row, ...); this
 * component only replaces the OUTERMOST section switcher a screen renders.
 *
 * THE SHAPE: an underlined tab strip, not a filled track — no pill background at all. The active
 * tab is bold text over a solid accent underline; an inactive tab is muted text with no fill and
 * no border. This is the one place in the console allowed to look like "real navigation" rather
 * than a control, because it IS navigation — switching to a different section of the same screen.
 */
import { cn } from '../cn';

export interface RjTabBarOption<T extends string> {
  value: T;
  label: string;
}

interface RjTabBarProps<T extends string> {
  options: RjTabBarOption<T>[];
  value: T;
  onChange: (value: T) => void;
  className?: string;
  ariaLabel?: string;
  testId?: string;
  /** Split the strip evenly across the row instead of hugging each label's own width — the same
   *  "never half off the edge" reasoning `Segmented`'s own call sites already settled on, offered
   *  here as a prop instead of a className fight since the underline itself must span each
   *  button's own width exactly. */
  fullWidth?: boolean;
}

export function TabBar<T extends string>({
  options, value, onChange, className, ariaLabel, testId, fullWidth,
}: RjTabBarProps<T>) {
  return (
    <div
      role="tablist"
      aria-label={ariaLabel}
      data-testid={testId}
      // A hairline base rule under the whole strip — without it an inactive tab (no fill, no
      // border of its own) has nothing marking where the row ends, and the active tab's own
      // underline looks like a stray line rather than "this tab, on this strip."
      className={cn(
        'flex items-center gap-5 overflow-x-auto border-b border-border-subtle',
        fullWidth && '[&>button]:flex-1',
        className,
      )}
    >
      {options.map((opt) => {
        const active = opt.value === value;
        return (
          <button
            key={opt.value}
            type="button"
            role="tab"
            aria-selected={active}
            data-testid={testId ? `${testId}-${opt.value}` : undefined}
            onClick={() => onChange(opt.value)}
            className={cn(
              // min-h-11 (44px) — same accessible touch-target floor as every other rj-ui
              // control. -mb-px so the active underline sits exactly ON the strip's own base
              // rule, not a pixel above it.
              'relative -mb-px flex min-h-11 shrink-0 items-center justify-center whitespace-nowrap px-1 pb-3 pt-2 text-sm font-semibold transition-colors focus-ring',
              active ? 'text-accent' : 'text-text-secondary hover:text-text-primary',
            )}
          >
            {opt.label}
            {active ? (
              <span aria-hidden className="absolute inset-x-0 bottom-0 h-0.5 rounded-full bg-accent" />
            ) : null}
          </button>
        );
      })}
    </div>
  );
}
