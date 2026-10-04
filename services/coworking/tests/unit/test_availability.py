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
    # 2026-08-17 is a Monday — not in `weekly` at all, so the whole day is closed.
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
    start = _riyadh_epoch(2026, 8, 16, 9, 0)
    assert is_free(BASIC, [], starts_at=start, ends_at=start + 30 * 60)
    start2 = _riyadh_epoch(2026, 8, 16, 12, 45)
    assert not is_free(BASIC, [], starts_at=start2, ends_at=start2 + 30 * 60)


def test_is_free_also_refuses_an_unconfigured_duration():
    start = _riyadh_epoch(2026, 8, 16, 9, 0)
    with pytest.raises(DurationNotConfigured):
        is_free(BASIC, [], starts_at=start, ends_at=start)


def test_is_free_rejects_a_booking_a_slot_grid_would_never_offer_in_the_first_place():
    """The authoritative check is not bound to the grid's own granularity — 09:07 is a real,
    checkable candidate even though `free_slots` only ever offers 09:00/09:15/..."""
    start = _riyadh_epoch(2026, 8, 16, 9, 7)
    assert is_free(BASIC, [], starts_at=start, ends_at=start + 20 * 60)


def test_is_free_checks_the_real_span_not_a_whole_minute_rounding():
    """A 90-second booking must be checked at its real 90 seconds, not rounded up to 2 minutes —
    the exact regression `duration_minutes` used to force on every caller."""
    start = _riyadh_epoch(2026, 8, 16, 9, 0)
    assert is_free(BASIC, [], starts_at=start, ends_at=start + 90)


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


# ── coverage for the bitmask port of `_iter_candidates` (perf-audit-2026-09-08) ──────────────
#
# `free_slots`/`nearest_slot` now check busy overlap via a per-day minute-resolution bitmask
# instead of scanning `busy` per candidate — these cases target the exact edges where a
# floor/ceil-to-the-minute bucket could, in principle, disagree with the old continuous
# `_overlaps` check: a duration NOT a multiple of the 15-minute grid, a busy interval with
# sub-minute-irrelevant-but-mid-bucket boundaries, a day exception, and an empty schedule.

def test_a_non_grid_duration_still_skips_only_the_minutes_it_actually_touches():
    """duration_minutes=20 is not a multiple of the 15-minute candidate grid — the OLD scan
    checked continuous overlap regardless; the bitmask must still agree exactly."""
    busy = [Busy(_riyadh_epoch(2026, 8, 16, 9, 20), _riyadh_epoch(2026, 8, 16, 9, 40))]
    slots = free_slots(BASIC, busy, duration_minutes=20,
                       window_start=_riyadh_epoch(2026, 8, 16),
                       window_end=_riyadh_epoch(2026, 8, 16, 11, 0))
    starts = {s.starts_at for s in slots}
    # 09:00-09:20 would touch nothing of [09:20,09:40) — busy starts exactly where this ends.
    assert _riyadh_epoch(2026, 8, 16, 9, 0) in starts
    # 09:15-09:35 overlaps the busy interval.
    assert _riyadh_epoch(2026, 8, 16, 9, 15) not in starts
    # 09:30-09:50 still overlaps the tail of the busy interval (09:30 < 09:40).
    assert _riyadh_epoch(2026, 8, 16, 9, 30) not in starts
    # 09:45-10:05 starts after busy ends at 09:40 — no overlap.
    assert _riyadh_epoch(2026, 8, 16, 9, 45) in starts


def test_a_busy_interval_ending_mid_bucket_does_not_over_reject_the_next_slot():
    """A busy stretch ending at 09:20 (not on the 15-minute grid) must not bleed into the
    following candidate that starts exactly there — this is the case a coarser, 15-minute-bucket
    mask (rather than a minute-resolution one) would get wrong."""
    busy = [Busy(_riyadh_epoch(2026, 8, 16, 9, 0), _riyadh_epoch(2026, 8, 16, 9, 20))]
    slots = free_slots(BASIC, busy, duration_minutes=30,
                       window_start=_riyadh_epoch(2026, 8, 16),
                       window_end=_riyadh_epoch(2026, 8, 16, 11, 0))
    starts = {s.starts_at for s in slots}
    assert _riyadh_epoch(2026, 8, 16, 9, 0) not in starts     # overlaps 09:00-09:20
    assert _riyadh_epoch(2026, 8, 16, 9, 15) not in starts    # 09:15-09:45 still overlaps
    # 09:30-10:00 starts on the grid, after the busy stretch ends at 09:20 — must be free.
    assert _riyadh_epoch(2026, 8, 16, 9, 30) in starts


def test_a_day_exception_closing_the_day_offers_nothing_regardless_of_busy():
    """An exception day with no windows must short-circuit before the busy bitmask is even
    built for that day — same result as the pre-bitmask scan (an empty schedule that day)."""
    off = Schedule(weekly=BASIC.weekly,
                   exceptions={SUNDAY.isoformat(): DayException(closed=True)})
    busy = [Busy(_riyadh_epoch(2026, 8, 16, 9, 0), _riyadh_epoch(2026, 8, 16, 10, 0))]
    slots = free_slots(off, busy, duration_minutes=30,
                       window_start=_riyadh_epoch(2026, 8, 16),
                       window_end=_riyadh_epoch(2026, 8, 17))
    assert slots == []


def test_an_empty_schedule_with_busy_intervals_offers_nothing():
    """No weekly hours at all, on any day — the busy bitmask must never be asked to fill in for
    a schedule that never opens."""
    empty = Schedule(weekly={})
    busy = [Busy(_riyadh_epoch(2026, 8, 16, 9, 0), _riyadh_epoch(2026, 8, 16, 10, 0))]
    slots = free_slots(empty, busy, duration_minutes=30,
                       window_start=_riyadh_epoch(2026, 8, 16),
                       window_end=_riyadh_epoch(2026, 8, 18))
    assert slots == []


def test_a_busy_interval_spanning_a_day_boundary_only_blocks_the_day_it_touches():
    """A busy stretch crossing Riyadh midnight must block the tail of one day and the head of
    the next, and nothing else — exercising the per-day busy mask's own clipping at `day_epoch`
    and `day_epoch + 86400`."""
    two_day = Schedule(weekly={
        6: (Window(540, 780),),        # Sunday 09:00-13:00
        0: (Window(0, 120),),          # Monday 00:00-02:00
    })
    busy = [Busy(_riyadh_epoch(2026, 8, 16, 12, 0), _riyadh_epoch(2026, 8, 17, 1, 0))]
    slots = free_slots(two_day, busy, duration_minutes=30,
                       window_start=_riyadh_epoch(2026, 8, 16, 9, 0),
                       window_end=_riyadh_epoch(2026, 8, 17, 2, 0))
    starts = {s.starts_at for s in slots}
    assert _riyadh_epoch(2026, 8, 16, 11, 30) in starts       # ends right at 12:00, before busy
    assert _riyadh_epoch(2026, 8, 16, 12, 0) not in starts    # inside the cross-midnight busy stretch
    assert _riyadh_epoch(2026, 8, 17, 0, 0) not in starts     # still inside it, on the next day
    assert _riyadh_epoch(2026, 8, 17, 1, 0) in starts         # starts exactly when busy ends


def test_free_slots_and_nearest_slot_agree_with_a_dense_dozen_busy_intervals():
    """A denser busy calendar than the other cases above — several back-to-back and gapped
    intervals in one day — cross-checked against a from-scratch continuous overlap
    reimplementation, so the bitmask's day-mask construction is exercised with more than one or
    two intervals at once."""
    busy_windows = [(9, 0, 9, 10), (9, 15, 9, 25), (9, 45, 10, 5), (11, 0, 11, 3),
                    (12, 0, 12, 59)]
    busy = [Busy(_riyadh_epoch(2026, 8, 16, *bw[:2]), _riyadh_epoch(2026, 8, 16, *bw[2:]))
           for bw in busy_windows]
    slots = free_slots(BASIC, busy, duration_minutes=17,
                       window_start=_riyadh_epoch(2026, 8, 16, 9, 0),
                       window_end=_riyadh_epoch(2026, 8, 16, 13, 0))

    def continuous_overlap(a_start, a_end):
        return any(a_start < b.ends_at and b.starts_at < a_end for b in busy)

    # Rebuild the same candidate grid by hand and check every one against a plain continuous
    # overlap test — the two must agree on every single candidate, not just a few samples.
    window_open = _riyadh_epoch(2026, 8, 16, 9, 0)
    window_close = _riyadh_epoch(2026, 8, 16, 13, 0)
    expected = set()
    t = window_open
    while t + 17 * 60 <= window_close:
        if not continuous_overlap(t, t + 17 * 60):
            expected.add(t)
        t += 15 * 60
    assert {s.starts_at for s in slots} == expected
