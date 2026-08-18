"""Where a booking can go — derived, never stored (docs/وصف-تطبيق-الحجوزات.md §4).

WHY DERIVED. Storing every open slot is the classic mistake in a booking system: a table of
millions of rows that must be regenerated and cleaned, and that disagrees with reality the first
time anyone changes a working hour. Three inputs, and no fourth in this version: working hours
(per branch, per staff, with day exceptions), the service's duration, and the staff member as the
one resource being scheduled. Everything a screen shows is computed from these at read time.

PURE ON PURPOSE, LIKE `reminders/app/core/merge.py`. Nothing here reads a store or a clock — the
caller passes the schedule, the busy intervals, and the window to search, so the whole decision
space (an exception day, a booking that touches the edge of a working window, back-to-back
bookings with no gap) is testable without a datastore, and the same function serves the grid, the
"nearest slot" button, and any preview that ever needs one.

DURATION IS NEVER GUESSED. A service with `Service.duration_minutes == 0` (docs/خطة-تنفيذ-
الحجوزات.md §0 — "not configured", not "instant") makes `free_slots` refuse outright rather than
silently compute a slot nobody's length actually is. This is the same defect family as a default
cycle_days of 30 for a puncture repair: an invented number a screen then treats as real.

TIME IS RIYADH TIME, IMPORTED FROM THIS SERVICE'S OWN `app/core/riyadh.py` — the one place this
product writes the offset, per `ci/check_the_products_clock_is_not_written_by_hand.py`. A working
"day" is a Riyadh calendar day; a schedule keyed by UTC weekday would put Wednesday evening's
hours under Thursday for three hours every night.
"""
from __future__ import annotations

import datetime as _dt
from dataclasses import dataclass, field
from typing import Sequence

from app.core.riyadh import RIYADH

# The grid's own grain (docs' §2, the double-booking lock uses the same bucket). Two requested
# times inside one bucket contend for the same lane; free_slots reports candidates on this grid so
# what the lock protects and what the screen offers are never two different geometries.
DEFAULT_GRANULARITY_MINUTES = 15


class DurationNotConfigured(Exception):
    """Raised, never swallowed into an empty result — an empty list of slots reads as "fully
    booked", which is a different sentence from "we don't know how long this takes yet"."""


@dataclass(frozen=True)
class Window:
    """One open stretch on one day, in minutes since Riyadh midnight. 09:00-13:00 is (540, 780)."""
    start_minute: int
    end_minute: int

    def __post_init__(self) -> None:
        if not (0 <= self.start_minute < self.end_minute <= 24 * 60):
            raise ValueError(f"not a real window: {self.start_minute}-{self.end_minute}")


@dataclass(frozen=True)
class DayException:
    """An override for one Riyadh calendar date («date» as YYYY-MM-DD). `windows=()` with
    `closed=True` is a full day off (Eid, a branch holiday); non-empty `windows` overrides the
    weekly default for that one date without touching any other day (a Ramadan short day, a staff
    member's half-day)."""
    closed: bool = True
    windows: tuple[Window, ...] = ()


@dataclass(frozen=True)
class Schedule:
    """Working hours for ONE resource (a branch, or a staff member if theirs differ from the
    branch's own). `weekly` keys 0=Monday..6=Sunday (`date.weekday()`'s own numbering — no second
    convention invented here); a weekday absent or mapped to `()` is closed that day by default.
    `exceptions` overrides one specific date over whatever `weekly` would have said."""
    weekly: dict[int, tuple[Window, ...]] = field(default_factory=dict)
    exceptions: dict[str, DayException] = field(default_factory=dict)

    def windows_on(self, day: _dt.date) -> tuple[Window, ...]:
        exc = self.exceptions.get(day.isoformat())
        if exc is not None:
            return () if exc.closed and not exc.windows else exc.windows
        return self.weekly.get(day.weekday(), ())


@dataclass(frozen=True)
class Busy:
    """One occupied stretch for the resource being scheduled — an existing booking, epoch
    seconds. The caller supplies these already narrowed to one staff member; this module does not
    know what a booking is, only that a stretch of time is taken."""
    starts_at: int
    ends_at: int


@dataclass(frozen=True)
class Slot:
    """One candidate the grid or the "nearest slot" button can offer, epoch seconds."""
    starts_at: int
    ends_at: int


def _riyadh_date(epoch: int) -> _dt.date:
    return _dt.datetime.fromtimestamp(epoch, tz=RIYADH).date()


def _day_start_epoch(day: _dt.date) -> int:
    return int(_dt.datetime.combine(day, _dt.time(0, 0), tzinfo=RIYADH).timestamp())


def _overlaps(a_start: int, a_end: int, b_start: int, b_end: int) -> bool:
    return a_start < b_end and b_start < a_end


def free_slots(schedule: Schedule, busy: Sequence[Busy], *, duration_minutes: int,
               window_start: int, window_end: int,
               granularity_minutes: int = DEFAULT_GRANULARITY_MINUTES) -> list[Slot]:
    """Every candidate start time, on the grid, where a `duration_minutes`-long booking fits
    inside a working window and touches none of `busy`.

    `window_start`/`window_end` bound the SEARCH (typically "today" or "this week" in epoch
    seconds) — not the working hours themselves, which come entirely from `schedule`.

    REFUSES RATHER THAN GUESSES (see module docstring): `duration_minutes <= 0` raises
    `DurationNotConfigured`. Every other input producing zero candidates (a closed day, a fully
    booked window) is a normal, correct empty list — "not configured" and "not available" must
    never collapse into the same shape, or a shop reads a config gap as a fully-booked day.
    """
    if duration_minutes <= 0:
        raise DurationNotConfigured(
            "duration_minutes is 0 or unset — this service's booking length was never "
            "configured, not merely fully booked")
    if window_end <= window_start:
        return []

    duration_seconds = duration_minutes * 60
    step_seconds = granularity_minutes * 60
    slots: list[Slot] = []

    day = _riyadh_date(window_start)
    last_day = _riyadh_date(window_end - 1) if window_end > window_start else day
    while day <= last_day:
        day_epoch = _day_start_epoch(day)
        for w in schedule.windows_on(day):
            win_start = max(day_epoch + w.start_minute * 60, window_start)
            win_end = min(day_epoch + w.end_minute * 60, window_end)
            cand = win_start
            while cand + duration_seconds <= win_end:
                cand_end = cand + duration_seconds
                if not any(_overlaps(cand, cand_end, b.starts_at, b.ends_at) for b in busy):
                    slots.append(Slot(starts_at=cand, ends_at=cand_end))
                cand += step_seconds
        day = day + _dt.timedelta(days=1)
    return slots


def is_free(schedule: Schedule, busy: Sequence[Busy], *, starts_at: int, duration_minutes: int) -> bool:
    """The authoritative check for one exact, already-chosen time — what the claim (docs/خطة-
    تنفيذ-الحجوزات.md §2/§3) re-checks inside the lock. `free_slots` is the advisory, grid-shaped
    view; this is the precise yes/no for the one candidate a drop or a confirm actually commits to,
    which need not land on the grid's own granularity."""
    if duration_minutes <= 0:
        raise DurationNotConfigured(
            "duration_minutes is 0 or unset — this service's booking length was never "
            "configured, not merely fully booked")
    ends_at = starts_at + duration_minutes * 60
    day = _riyadh_date(starts_at)
    windows = schedule.windows_on(day)
    day_epoch = _day_start_epoch(day)
    within_a_window = any(
        day_epoch + w.start_minute * 60 <= starts_at and ends_at <= day_epoch + w.end_minute * 60
        for w in windows)
    if not within_a_window:
        return False
    return not any(_overlaps(starts_at, ends_at, b.starts_at, b.ends_at) for b in busy)


def nearest_slot(schedule: Schedule, busy: Sequence[Busy], *, duration_minutes: int,
                 after: int, search_days: int = 14) -> Slot | None:
    """The "أقرب فتحة" button (docs/وصف-تطبيق-الحجوزات.md §6.2) — the first candidate at or after
    `after`, searching forward up to `search_days`. `None` when nothing is free in that horizon,
    which the caller renders as "no opening in the next two weeks", never as a silent empty grid.
    """
    window_end = after + search_days * 86400
    found = free_slots(schedule, busy, duration_minutes=duration_minutes,
                       window_start=after, window_end=window_end)
    return found[0] if found else None
