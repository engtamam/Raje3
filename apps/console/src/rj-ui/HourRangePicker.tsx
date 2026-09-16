/**
 * A whole-hour range picker — component #21, extracted rather than invented.
 *
 * THE PATTERN ALREADY EXISTED THREE TIMES, hand-copied: `BookingSettingsDialog.tsx` (per-weekday
 * open/close), `Team.tsx` (per-staff custom hours), `BookingDialog.tsx` (a single slot). None of
 * them needed a shared component before now because none of them needed WHOLE HOURS ONLY — all
 * three store minute-of-day (`start_minute`/`end_minute`) and render a real `<input type="time">`
 * pair, because a business can open at 09:30. A campaign's own time window (services/campaigns'
 * `window_start_hour`/`window_end_hour`) is deliberately coarser — an integer hour, 0-24 — so this
 * is a NEW, simpler control rather than a fourth copy of the minute-precision one.
 *
 * `endHour` MAY BE 24 (midnight, the true end of the calendar day) — `startHour` never is, since a
 * window cannot START at the moment the day ends. Same "24 means midnight, not a wrap" rule
 * `services/campaigns/app/core/models.py::in_window` documents on the backend side.
 *
 * A CUSTOM LIST, NOT `rj-ui/Field`'s `Select` — found live, reported directly against the mockup:
 * a real `<select>`'s OPEN list is the browser's own native popover (a plain white box, the OS's
 * default font/scrollbar/highlight colours), which every desktop and mobile browser renders
 * differently and NONE of them lets a page restyle — the exact "غير احترافي" the owner flagged
 * with a screenshot of it sitting over the whole page. `rj-ui/Field`'s own docstring accepts that
 * trade-off deliberately for an ordinary form select (free keyboard nav, the OS's own mobile
 * picker) across dozens of screens; this one has only 24-25 whole-hour rows, small enough that a
 * hand-built listbox — same visual language as everything else in this kit, closes on an outside
 * click or Escape, arrow-key/Home/End navigable — is worth the extra code for the one control the
 * owner is looking at up close on the mockup's own screen.
 */
import { useEffect, useRef, useState } from 'react';
import { ChevronDown } from 'lucide-react';
import { cn } from '../cn';

function hourLabel(h: number): string {
  return `${String(h % 24).padStart(2, '0')}:00`;
}

function HourDropdown({ value, options, onChange, label, ariaLabel }: {
  value: number;
  options: number[];
  onChange: (v: number) => void;
  label: string;
  ariaLabel: string;
}) {
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);
  const listRef = useRef<HTMLUListElement>(null);

  useEffect(() => {
    if (!open) return;
    function onDocPointer(e: PointerEvent) {
      if (rootRef.current && !rootRef.current.contains(e.target as Node)) setOpen(false);
    }
    function onKey(e: KeyboardEvent) {
      if (e.key === 'Escape') setOpen(false);
    }
    document.addEventListener('pointerdown', onDocPointer);
    document.addEventListener('keydown', onKey);
    // FOCUS THE CURRENT HOUR'S OWN ROW ON OPEN — so arrow keys move from where the value already
    // is, not from the top of a 24-row list every time.
    const current = listRef.current?.querySelector<HTMLElement>('[data-current="true"]');
    current?.focus();
    return () => {
      document.removeEventListener('pointerdown', onDocPointer);
      document.removeEventListener('keydown', onKey);
    };
  }, [open]);

  function moveFocus(delta: number) {
    const items = Array.from(listRef.current?.querySelectorAll<HTMLElement>('[role="option"]') ?? []);
    const i = items.findIndex((el) => el === document.activeElement);
    const next = items[Math.min(items.length - 1, Math.max(0, (i < 0 ? 0 : i) + delta))];
    next?.focus();
  }

  return (
    <div ref={rootRef} className="relative">
      <button
        type="button"
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-label={ariaLabel}
        onClick={() => setOpen((v) => !v)}
        className="flex h-10 items-center gap-1.5 rounded-lg border border-border-strong bg-surface-1 px-3 text-sm font-medium tabular-nums text-text-primary transition-colors hover:border-accent/50 focus-ring"
      >
        {hourLabel(value)}
        <ChevronDown size={14} className={cn('text-text-muted transition-transform', open && 'rotate-180')} aria-hidden />
      </button>
      {open ? (
        <ul
          ref={listRef}
          role="listbox"
          aria-label={label}
          className="absolute z-20 mt-1.5 max-h-64 w-24 overflow-y-auto rounded-lg border border-border-subtle bg-surface-1 p-1 shadow-lg"
        >
          {options.map((h) => {
            const selected = h === value;
            return (
              <li key={h}>
                <button
                  type="button"
                  role="option"
                  aria-selected={selected}
                  data-current={selected}
                  tabIndex={0}
                  onClick={() => { onChange(h); setOpen(false); }}
                  onKeyDown={(e) => {
                    if (e.key === 'ArrowDown') { e.preventDefault(); moveFocus(1); }
                    else if (e.key === 'ArrowUp') { e.preventDefault(); moveFocus(-1); }
                    else if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onChange(h); setOpen(false); }
                  }}
                  className={cn(
                    'flex w-full items-center rounded-md px-2.5 py-1.5 text-sm tabular-nums transition-colors focus-ring',
                    selected ? 'bg-accent text-accent-contrast font-semibold' : 'text-text-primary hover:bg-surface-2',
                  )}
                >
                  {hourLabel(h)}
                </button>
              </li>
            );
          })}
        </ul>
      ) : null}
    </div>
  );
}

export function HourRangePicker({ startHour, endHour, onChange, fromLabel, toLabel, ariaLabel }: {
  startHour: number;
  endHour: number;
  onChange: (startHour: number, endHour: number) => void;
  fromLabel: string;
  toLabel: string;
  ariaLabel?: string;
}) {
  return (
    <div className="flex flex-wrap items-center gap-3" role="group" aria-label={ariaLabel}>
      <label className="flex items-center gap-1.5 text-sm text-text-secondary">
        {fromLabel}
        <HourDropdown
          value={startHour}
          options={Array.from({ length: 24 }, (_, h) => h)}
          onChange={(h) => onChange(h, endHour)}
          label={fromLabel}
          ariaLabel={fromLabel}
        />
      </label>
      <label className="flex items-center gap-1.5 text-sm text-text-secondary">
        {toLabel}
        <HourDropdown
          value={endHour}
          options={Array.from({ length: 24 }, (_, h) => h + 1)}
          onChange={(h) => onChange(startHour, h)}
          label={toLabel}
          ariaLabel={toLabel}
        />
      </label>
    </div>
  );
}
