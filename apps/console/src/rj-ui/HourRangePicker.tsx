/**
 * A whole-hour range picker — component #21, extracted rather than invented.
 *
 * THE PATTERN ALREADY EXISTED THREE TIMES, hand-copied: `BookingSettingsDialog.tsx` (per-weekday
 * open/close), `Team.tsx` (per-staff custom hours), `BookingDialog.tsx` (a single slot). None of
 * them needed a shared component before now because none of them needed WHOLE HOURS ONLY — all
 * three store minute-of-day (`start_minute`/`end_minute`) and render a real `<input type="time">`
 * pair, because a business can open at 09:30. A campaign's own time window (services/campaigns'
 * `window_start_hour`/`window_end_hour`) is deliberately coarser — an integer hour, 0-24 — so this
 * is a NEW, simpler control rather than a fourth copy of the minute-precision one: two `<select>`s
 * naming the hour itself ("08:00", never "08:30"), which also means there is no minute string to
 * parse/round/lose precision on in a domain that never had minutes to begin with.
 *
 * `endHour` MAY BE 24 (midnight, the true end of the calendar day) — `startHour` never is, since a
 * window cannot START at the moment the day ends. Same "24 means midnight, not a wrap" rule
 * `services/campaigns/app/core/models.py::in_window` documents on the backend side.
 */
import { Select } from './Field';

function hourLabel(h: number): string {
  return `${String(h % 24).padStart(2, '0')}:00`;
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
    <div className="flex flex-wrap items-center gap-2" role="group" aria-label={ariaLabel}>
      <label className="flex items-center gap-1.5 text-sm text-text-secondary">
        {fromLabel}
        <Select
          value={String(startHour)}
          onChange={(e) => onChange(Number(e.target.value), endHour)}
          className="w-auto"
        >
          {Array.from({ length: 24 }, (_, h) => (
            <option key={h} value={h}>{hourLabel(h)}</option>
          ))}
        </Select>
      </label>
      <label className="flex items-center gap-1.5 text-sm text-text-secondary">
        {toLabel}
        <Select
          value={String(endHour)}
          onChange={(e) => onChange(startHour, Number(e.target.value))}
          className="w-auto"
        >
          {Array.from({ length: 24 }, (_, h) => h + 1).map((h) => (
            <option key={h} value={h}>{hourLabel(h)}</option>
          ))}
        </Select>
      </label>
    </div>
  );
}
