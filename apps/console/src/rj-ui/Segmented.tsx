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
import type { LucideIcon } from 'lucide-react';
import { cn } from '@base-ui/lib/cn';

export interface RjSegmentedOption<T extends string> {
  value: T;
  label: string;
  hint?: string;
  /** A LEADING ICON, before the label — for a screen's own top-level tab strip where each tab
   *  names a whole section (e.g. «الحملات»'s four), never for a nested/secondary strip where an
   *  icon per option would be one more thing competing with the label at a smaller size. */
  icon?: LucideIcon;
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
        // `self-start` — WITHOUT IT, a bare Segmented element dropped into any plain
        // `flex flex-col` parent (no `items-start` set on that parent — most of the console
        // never sets it) gets STRETCHED to the parent's full cross-axis width by the flex
        // default (`align-items: stretch`), even though the track itself is `inline-flex`.
        // The buttons stay their natural size and hug one side, so the track balloons into a
        // long empty pill with two cramped buttons at one end — exactly the "شريط فاضي" bug.
        // A caller that explicitly wants full width (e.g. Messages.tsx's own top-level tabs,
        // `className="flex w-full ..."`) still gets it — an explicit `w-full` wins regardless
        // of `self-start`, they are not the same CSS property.
        'inline-flex flex-wrap gap-1 self-start rounded-full p-1',
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
        const Icon = opt.icon;
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
              'relative inline-flex min-h-11 items-center justify-center gap-1.5 rounded-full font-semibold transition-all duration-200 focus-ring',
              sm ? 'px-2.5 py-1 text-[12.5px]' : 'px-3.5 py-2 text-sm',
              disabled && 'cursor-not-allowed',
              active
                // THE ONLY FILLED SHAPE ON THE TRACK — a real shadow lifting it off the recessed
                // track, and a hair of scale so it visibly "arrives" rather than just recolouring
                // in place. DELIBERATELY NOT THE BRAND ACCENT — "this tab is selected" is not the
                // same signal as "press this button", and painting both in the same purple is
                // what made every filled shape on the page read as one repeated colour rather
                // than a real hierarchy (the 60-30-10 audit's own category #2: "محدد/مفعّل" gets
                // its own neutral ink fill everywhere, purple stays reserved for the one true
                // primary action). `bg-text-primary`/`text-surface-1` is a plain themed INVERSION
                // — near-black on white in light mode, near-white on near-black in dark mode —
                // so it needs no separate dark-mode override.
                ? cn('scale-[1.03] bg-text-primary text-surface-1', sm ? 'shadow-sm' : 'shadow-md')
                // NO FILL AT ALL when inactive — the active/inactive read is a shape appearing,
                // not two shades of the same colour block.
                : 'text-text-secondary hover:text-text-primary',
            )}
          >
            {Icon ? <Icon size={sm ? 13 : 15} aria-hidden /> : null}
            {opt.label}
            {opt.badge ? (
              <span className={cn(
                'ms-1.5 rounded-full px-1.5 py-0.5 text-[10px] font-bold tabular-nums',
                active
                  // `bg-surface-1/20` NOT `bg-white/20` — the active pill is now a themed
                  // inversion (`bg-text-primary`), near-black in light mode but near-WHITE in
                  // dark mode, so a hardcoded white overlay would sit invisibly on white-on-white
                  // there. `surface-1` inverts the same way `text-primary` does, so the overlay
                  // stays legible against whichever ink colour the pill resolves to.
                  ? 'bg-surface-1/20'
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
