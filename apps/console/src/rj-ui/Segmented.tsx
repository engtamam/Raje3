/**
 * Our own Segmented — component #7, REDESIGNED 2026-09-07.
 *
 * WHAT WAS WRONG, IN THE OWNER'S OWN WORDS: "بالله في موقع زي كذا انت بعقلك؟" — a screenshot of
 * this component nested two/three levels deep (Account.tsx's top-level tabs, then its own
 * `SHOP_SUBTABS` one level under, then AdminProviderSecrets.tsx's provider/المسار/الإدارة rows a
 * third level under that) where every level read as visually IDENTICAL: same solid fill, same
 * size, same weight, active vs inactive barely distinguishable, and a plain-text "(2/6)" progress
 * count with zero colour coding sitting inside a tab label. Nested identical bars is precisely
 * what makes a hierarchy unreadable at a glance.
 *
 * THE FIX HAS TWO PARTS:
 *
 *  1. A real "floating pill on a track" treatment — the container is now a visibly recessed track
 *     (`bg-surface-2/70` inside a soft inset border), and the ACTIVE segment is the only filled
 *     shape on it: solid accent, real elevation (`shadow-md`), a hair of scale. An inactive
 *     segment carries NO fill at all — just muted text — so the active/inactive read is a shape
 *     appearing/disappearing, not a shade of the same colour.
 *
 *  2. `size` — `"md"` (the default, for a screen's own TOP-level tabs) is larger, bolder, and
 *     sits on the more visible track; `"sm"` (for anything nested under a `md` row — pass it
 *     explicitly at the call site, e.g. Account.tsx's own `SHOP_SUBTABS`) is smaller, lighter, and
 *     its track is one shade closer to the page background — so two stacked Segmented rows read as
 *     "a page, and a sub-choice inside it," not two copies of the same control.
 *
 * Same API as @base-ui/design-system/Segmented (options/value/onChange/className/ariaLabel/
 * testId/disabled — `help` omitted, nothing in this app used it) plus the new optional `size`, so
 * every existing call site keeps compiling unchanged and only opts into the smaller variant where
 * it explicitly asks for it.
 */
import { cn } from '@base-ui/lib/cn';

export interface RjSegmentedOption<T extends string> {
  value: T;
  label: string;
  hint?: string;
  /** A trailing count/progress pill (e.g. "2/6") — colour-coded via `badgeTone`, NEVER baked into
   *  `label` as plain text (the exact "(2/6)" with zero colour the owner flagged directly). */
  badge?: string;
  badgeTone?: 'complete' | 'partial' | 'empty';
}

interface RjSegmentedProps<T extends string> {
  options: RjSegmentedOption<T>[];
  value: T | null;
  onChange: (value: T) => void;
  className?: string;
  ariaLabel?: string;
  testId?: string;
  disabled?: boolean;
  /** `"md"` (default) for a screen's own top-level tabs; `"sm"` for a row NESTED under one —
   *  see the module docstring for why this is what makes stacked rows read as a hierarchy. */
  size?: 'md' | 'sm';
}

export function Segmented<T extends string>({
  options, value, onChange, className, ariaLabel, testId, disabled, size = 'md',
}: RjSegmentedProps<T>) {
  const sm = size === 'sm';
  return (
    <div
      role="radiogroup"
      aria-label={ariaLabel}
      aria-disabled={disabled || undefined}
      data-testid={testId}
      className={cn(
        'inline-flex flex-wrap gap-1 rounded-full p-1',
        // THE TRACK ITSELF IS A STEP DARKER THAN THE PAGE, WITH AN INSET SHADOW — a real recess,
        // not a flat rectangle the same colour as everything around it. `sm` sits one notch
        // closer to the page background so a nested row reads as "inside" its parent, not a
        // second copy of the same control.
        sm ? 'bg-surface-2/60' : 'bg-surface-2 shadow-[inset_0_1px_2px_rgba(19,18,38,.06)]',
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
              // own AppShell nav rows and rj-ui/Button's `lg` size already settled on. `sm` still
              // clears it (44px is the hit target, not the visual height) via padding alone.
              'relative inline-flex min-h-11 items-center justify-center rounded-full font-semibold transition-all duration-200 focus-ring',
              sm ? 'px-2.5 py-1 text-[12.5px]' : 'px-3.5 py-2 text-sm',
              disabled && 'cursor-not-allowed',
              active
                // THE ONLY FILLED SHAPE ON THE TRACK — solid accent, a real shadow lifting it off
                // the recessed track, and a hair of scale so it visibly "arrives" rather than just
                // recolouring in place.
                ? cn('scale-[1.03] bg-accent text-accent-contrast', sm ? 'shadow-sm' : 'shadow-md')
                // NO FILL AT ALL when inactive — the active/inactive read is a shape appearing,
                // not two shades of the same colour block.
                : 'text-text-secondary hover:text-text-primary',
            )}
          >
            {opt.label}
            {opt.badge ? (
              <span className={cn(
                'ms-1.5 rounded-full px-1.5 py-0.5 text-[10px] font-bold tabular-nums',
                active
                  ? 'bg-white/20'
                  : opt.badgeTone === 'complete' ? 'bg-success-soft text-success-on-soft'
                  : opt.badgeTone === 'partial' ? 'bg-warning-soft text-warning-on-soft'
                  : 'bg-surface-3 text-text-secondary',
              )}>
                {opt.badge}
              </span>
            ) : null}
          </button>
        );
      })}
    </div>
  );
}
