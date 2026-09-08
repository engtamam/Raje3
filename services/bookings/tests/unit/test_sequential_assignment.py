"""`app/core/assignment.py`'s sequential (package) search — several services back-to-back, zero
gap. Pure, clock-free, store-free, same discipline as `test_assignment.py` beside it.

The property under test throughout: every returned chain is CONTIGUOUS (each leg's start equals
the previous leg's start + duration) and every leg's operator is genuinely free for its own
duration at that exact position — never a later real opening traded away to satisfy the algorithm.
"""
from __future__ import annotations

import datetime as _dt

import pytest

from app.core.assignment import (Candidate, DurationNotOnGrid, Leg, nearest_sequential_slot)
from app.core.availability import DurationNotConfigured, RIYADH, Busy, Schedule, Window

# A Sunday 09:00-17:00 branch, all week — mirrors test_assignment.py's own fixture shape.
HOURS = Schedule(weekly={i: (Window(540, 1020),) for i in range(7)})


def _riyadh_epoch(y, mo, d, h=0, mi=0) -> int:
    return int(_dt.datetime(y, mo, d, h, mi, tzinfo=RIYADH).timestamp())


def _day_epoch(y, mo, d) -> int:
    return _riyadh_epoch(y, mo, d, 0, 0)


# 2026-09-07 is a Monday (weekday()==0) — matches HOURS' weekly keys directly.
AFTER = _riyadh_epoch(2026, 9, 7, 9, 0)          # Monday, right at opening
DAY0 = _day_epoch(2026, 9, 7)


def test_no_legs_is_none_not_an_error():
    assert nearest_sequential_slot([], after=AFTER) is None


def test_a_leg_duration_off_the_grid_is_refused_before_any_search():
    op1 = Candidate('op1', HOURS, ())
    with pytest.raises(DurationNotOnGrid):
        Leg(20, (op1,))


def test_a_zero_or_unset_duration_is_refused_same_as_free_slots():
    op1 = Candidate('op1', HOURS, ())
    with pytest.raises(DurationNotConfigured):
        Leg(0, (op1,))


def test_single_operator_covers_the_whole_chain_when_free_all_day():
    """One eligible operator, free all day — the chain must sit back-to-back starting at opening,
    all three legs under that one operator."""
    op1 = Candidate('op1', HOURS, ())
    legs = [Leg(15, (op1,)), Leg(30, (op1,)), Leg(15, (op1,))]
    r = nearest_sequential_slot(legs, after=AFTER)
    assert r is not None
    assert r.single_operator == 'op1'
    starts = [leg.starts_at for leg in r.legs]
    assert starts == [AFTER, AFTER + 900, AFTER + 900 + 1800]
    assert all(leg.operator_id == 'op1' for leg in r.legs)


def test_prefers_one_operator_over_a_split_chain_on_a_same_time_tie():
    """op1 and op2 are BOTH free for the whole span — the single-operator chain must win even
    though a split chain starting at the same instant is also technically feasible."""
    op1 = Candidate('op1', HOURS, ())
    op2 = Candidate('op2', HOURS, ())
    legs = [Leg(15, (op1, op2)), Leg(30, (op1, op2)), Leg(15, (op1, op2))]
    r = nearest_sequential_slot(legs, after=AFTER)
    assert r.single_operator is not None
    assert len({leg.operator_id for leg in r.legs}) == 1


def test_falls_back_to_a_chain_across_different_operators_when_nobody_covers_it_alone():
    """op1 is busy for the middle leg's own window; op2 is busy for the first leg's own window.
    Neither can do the whole chain alone, but op1-then-op2-then-op1 fits with zero gap."""
    op1 = Candidate('op1', HOURS, (Busy(DAY0 + 9 * 3600 + 900, DAY0 + 9 * 3600 + 2700),))
    op2 = Candidate('op2', HOURS, (Busy(DAY0 + 9 * 3600, DAY0 + 9 * 3600 + 900),))
    legs = [Leg(15, (op1, op2)), Leg(30, (op1, op2)), Leg(15, (op1, op2))]
    r = nearest_sequential_slot(legs, after=AFTER)
    assert r is not None
    assert r.single_operator is None
    starts = [leg.starts_at for leg in r.legs]
    assert starts == [AFTER, AFTER + 900, AFTER + 900 + 1800]
    assert [leg.operator_id for leg in r.legs] == ['op1', 'op2', 'op1']


def test_named_leg_with_one_candidate_still_chains_around_auto_legs():
    """A `named` leg's candidate list is exactly one operator (the customer's pick); the rest are
    ordinary `auto` legs with a wider pool. The chain must still respect the named leg's own
    operator without needing to know that distinction exists."""
    named_op = Candidate('chosen_one', HOURS, ())
    other = Candidate('op2', HOURS, ())
    legs = [Leg(15, (other, named_op)), Leg(30, (named_op,)), Leg(15, (other, named_op))]
    r = nearest_sequential_slot(legs, after=AFTER)
    assert r is not None
    assert r.legs[1].operator_id == 'chosen_one'


def test_nobody_can_fit_the_chain_today_rolls_to_the_next_day():
    """Everyone is fully booked today for the span the chain needs, but free tomorrow — the search
    must roll forward a day, not report failure just because today is full."""
    full_day_busy = (Busy(DAY0, DAY0 + 86400),)
    op1 = Candidate('op1', HOURS, full_day_busy)
    legs = [Leg(15, (op1,)), Leg(15, (op1,))]
    r = nearest_sequential_slot(legs, after=AFTER, search_days=3)
    assert r is not None
    tomorrow = DAY0 + 86400
    assert r.starts_at >= tomorrow + 9 * 3600
    assert r.starts_at < tomorrow + 86400


def test_nothing_fits_within_the_search_horizon_is_none_not_an_empty_chain():
    op1 = Candidate('op1', HOURS, (Busy(DAY0, DAY0 + 30 * 86400),))
    legs = [Leg(15, (op1,))]
    assert nearest_sequential_slot(legs, after=AFTER, search_days=3) is None


def test_chain_never_crosses_midnight_even_if_the_working_window_would_allow_the_bits():
    """Monday's window only fits ONE 15-minute leg (09:00-09:15); the chain needs two, back-to-back,
    so it must be refused for Monday and rolled to Tuesday's wider window — never silently offered
    spilling past 09:15."""
    mixed = Schedule(weekly={0: (Window(540, 555),),          # Monday: 09:00-09:15 only
                             1: (Window(540, 1020),)})         # Tuesday: 09:00-17:00
    op1 = Candidate('op1', mixed, ())
    legs = [Leg(15, (op1,)), Leg(15, (op1,))]   # needs 30 minutes; Monday's window is only 15
    r = nearest_sequential_slot(legs, after=AFTER, search_days=3)
    assert r is not None
    assert r.starts_at == DAY0 + 86400 + 9 * 3600   # Tuesday 09:00, not Monday at all
