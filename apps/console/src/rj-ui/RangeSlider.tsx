/**
 * A single-value draggable range control — component #23. Built for «كافئ المخلصين»'s own
 * audience thresholds (services/campaigns, 2026-09-13 — the owner's own instruction: "خط يسحبه
 * ويحركه يمين ويسار... يجيه مع التعديل عدد الأشخاص"), never a typed number box: the whole point
 * is seeing the audience count move AS he drags, which a plain `<input type="number">` cannot
 * give him without an extra press first.
 *
 * A NATIVE `<input type="range">` UNDER THE PAINT, deliberately, same reasoning `rj-ui/Field.tsx`'s
 * own `Select` gives for staying native: full keyboard support (arrow keys nudge the value) and
 * the OS's own touch-drag handling for free — only the track/thumb colours are ours.
 */
export interface RjRangeSliderProps {
  value: number;
  min: number;
  max: number;
  step?: number;
  onChange: (value: number) => void;
  label: string;
  /** How the current value reads out loud — e.g. "90 يوماً" instead of a bare "90". Defaults to
   *  the plain number. */
  valueLabel?: string;
  ariaLabel?: string;
  testId?: string;
}

export function RangeSlider({
  value, min, max, step = 1, onChange, label, valueLabel, ariaLabel, testId,
}: RjRangeSliderProps) {
  return (
    <label className="flex flex-col gap-1.5">
      <span className="flex items-center justify-between gap-2">
        <span className="text-sm text-text-secondary">{label}</span>
        <span className="text-sm font-semibold tabular-nums text-text-primary">
          {valueLabel ?? value}
        </span>
      </span>
      <input
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
        aria-label={ariaLabel ?? label}
        data-testid={testId}
        className="h-2 w-full cursor-pointer appearance-none rounded-full bg-surface-2 accent-accent"
      />
    </label>
  );
}
