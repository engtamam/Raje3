"""`app/core/availability.py` — pure, clock-free, store-free (docs/خطة-تنفيذ-الحجوزات.md §2).

Table-driven over the edge cases the plan named explicitly: a staff exception day, a closed
branch, a service spanning a working-hours boundary, back-to-back bookings with zero gap — plus
the "duration not configured" refusal (the same defect family as Stage 0's
test_a_service_with_no_duration_is_not_configured.py, one layer up).
"""
from __future__ import annotations

import datetime as _dt

import pytest

from app.core.availability import (Busy, DayException, DurationNotConfigured, RIYADH, Schedule,
                                   Slot, Window, free_slots, is_free, nearest_slot)


def _riyadh_epoch(y, mo, d, h=0, mi=0) -> int:
    return int(_dt.datetime(y, mo, d, h, mi, tzinfo=RIYADH).timestamp())


# A Sunday 09:00-13:00, 14:00-17:00 branch, matching a real salon's split shift.
# 2026-08-16 is a Sunday.
SUNDAY = _dt.date(2026, 8, 16)
BASIC = Schedule(weekly={
    6: (Window(540, 780), Window(840, 1020)),   # Sunday: 09:00-13:00, 14:00-17:00
})


def test_no_duration_configured_refuses_not_guesses():
    """0 must raise, never silently return an empty (= "fully booked") list — the exact
    distinction Stage 0 drew for the catalogue itself, held here too."""
    with pytest.raises(DurationNotConfigured):
        free_slots(BASIC, [], duration_minutes=0,
                  window_start=_riyadh_epoch(2026, 8, 16),
                  window_end=_riyadh_epoch(2026, 8, 17))


def test_a_closed_day_offers_nothing():
    monday = _dt.date(2026, 8, 17)  # not in `weekly` at all -> closed
    slots = free_slots(BASIC, [], duration_minutes=30,
                       window_start=_riyadh_epoch(2026, 8, 17),
                       window_end=_riyadh_epoch(2026, 8, 18))
    assert slots == []


def test_a_normal_open_day_offers_the_first_and_last_slot_of_each_window():
    slots = free_slots(BASIC, [], duration_minutes=30,
                       window_start=_riyadh_epoch(2026, 8, 16),
                       window_end=_riyadh_epoch(2026, 8, 17))
    starts = {s.starts_at for s in slots}
    assert _riyadh_epoch(2026, 8, 16, 9, 0) in starts        # window opens
    assert _riyadh_epoch(2026, 8, 16, 12, 30) in starts       # last 30-min slot before 13:00
    assert _riyadh_epoch(2026, 8, 16, 12, 45) not in starts   # would spill past 13:00
    assert _riyadh_epoch(2026, 8, 16, 14, 0) in starts        # afternoon window opens


def test_a_service_spanning_the_boundary_between_two_windows_is_never_offered():
    """12:45 + 30min would straddle the 13:00-14:00 gap — must not appear even though both
    windows individually have room."""
    slots = free_slots(BASIC, [], duration_minutes=30,
                       window_start=_riyadh_epoch(2026, 8, 16),
                       window_end=_riyadh_epoch(2026, 8, 17))
    starts = {s.starts_at for s in slots}
    assert _riyadh_epoch(2026, 8, 16, 12, 45) not in starts
    assert _riyadh_epoch(2026, 8, 16, 13, 0) not in starts   # inside the gap entirely


def test_a_staff_exception_day_overrides_the_weekly_default():
    """A staff member off on a normally-open Sunday: the weekly default says open, the
    exception says closed, and the exception must win."""
    off = Schedule(weekly=BASIC.weekly,
                   exceptions={SUNDAY.isoformat(): DayException(closed=True)})
    slots = free_slots(off, [], duration_minutes=30,
                       window_start=_riyadh_epoch(2026, 8, 16),
                       window_end=_riyadh_epoch(2026, 8, 17))
    assert slots == []


def test_a_staff_exception_day_can_also_open_a_normally_closed_day():
    monday = _dt.date(2026, 8, 17)
    extra = Schedule(weekly=BASIC.weekly,
                      exceptions={monday.isoformat(): DayException(
                          closed=False, windows=(Window(600, 630),))})   # 10:00-10:30 only
    slots = free_slots(extra, [], duration_minutes=30,
                       window_start=_riyadh_epoch(2026, 8, 17),
                       window_end=_riyadh_epoch(2026, 8, 18))
    # A single 30-minute window fits exactly one 30-minute booking, so this also proves the
    # search does not spill a candidate past the window it was offered inside.
    assert {s.starts_at for s in slots} == {_riyadh_epoch(2026, 8, 17, 10, 0)}


def test_back_to_back_bookings_with_zero_gap_leave_no_slot_between_them():
    """09:00-09:30 and 09:30-10:00 booked, back to back — nothing must be offered starting at
    09:00 through 09:59, and the very next real gap starts at 10:00."""
    busy = [Busy(_riyadh_epoch(2026, 8, 16, 9, 0), _riyadh_epoch(2026, 8, 16, 9, 30)),
            Busy(_riyadh_epoch(2026, 8, 16, 9, 30), _riyadh_epoch(2026, 8, 16, 10, 0))]
    slots = free_slots(BASIC, busy, duration_minutes=30,
                       window_start=_riyadh_epoch(2026, 8, 16),
                       window_end=_riyadh_epoch(2026, 8, 16, 11, 0))
    starts = {s.starts_at for s in slots}
    assert _riyadh_epoch(2026, 8, 16, 9, 0) not in starts
    assert _riyadh_epoch(2026, 8, 16, 9, 15) not in starts   # overlaps the second booking too
    assert _riyadh_epoch(2026, 8, 16, 10, 0) in starts


def test_is_free_matches_free_slots_for_the_same_candidate():
    assert is_free(BASIC, [], starts_at=_riyadh_epoch(2026, 8, 16, 9, 0), duration_minutes=30)
    assert not is_free(BASIC, [], starts_at=_riyadh_epoch(2026, 8, 16, 12, 45), duration_minutes=30)


def test_is_free_also_refuses_an_unconfigured_duration():
    with pytest.raises(DurationNotConfigured):
        is_free(BASIC, [], starts_at=_riyadh_epoch(2026, 8, 16, 9, 0), duration_minutes=0)


def test_is_free_rejects_a_booking_a_slot_grid_would_never_offer_in_the_first_place():
    """The authoritative check is not bound to the grid's own granularity — 09:07 is a real,
    checkable candidate even though `free_slots` only ever offers 09:00/09:15/..."""
    assert is_free(BASIC, [], starts_at=_riyadh_epoch(2026, 8, 16, 9, 7), duration_minutes=20)


def test_nearest_slot_finds_the_first_opening_after_a_fully_booked_morning():
    busy = [Busy(_riyadh_epoch(2026, 8, 16, 9, 0), _riyadh_epoch(2026, 8, 16, 13, 0))]
    found = nearest_slot(BASIC, busy, duration_minutes=30, after=_riyadh_epoch(2026, 8, 16, 9, 0))
    assert found == Slot(_riyadh_epoch(2026, 8, 16, 14, 0), _riyadh_epoch(2026, 8, 16, 14, 30))


def test_nearest_slot_returns_none_when_nothing_is_free_in_the_horizon():
    empty = Schedule(weekly={})   # every day closed
    assert nearest_slot(empty, [], duration_minutes=30,
                        after=_riyadh_epoch(2026, 8, 16), search_days=3) is None


def test_a_window_with_start_not_before_end_is_rejected_at_construction():
    with pytest.raises(ValueError):
        Window(700, 700)
    with pytest.raises(ValueError):
        Window(800, 700)
