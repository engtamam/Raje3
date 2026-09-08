"""`app/core/assignment.py` — the «أي متاح» merge (Phase 0). Pure, clock-free, store-free, same
discipline as `test_availability.py` beside it.

BEHAVIOUR-PRESERVING BY CONSTRUCTION is the thing under test here: `nearest_slots_any` must find
the SAME answer BookingDialog.tsx's own former loop would have — the earliest slot across every
candidate each round, cursor advanced past it, repeated until `max_slots` or nobody has anything
left in the window.
"""
from __future__ import annotations

import datetime as _dt

from app.core.assignment import Candidate, nearest_slots_any
from app.core.availability import RIYADH, Busy, Schedule, Window


def _riyadh_epoch(y, mo, d, h=0, mi=0) -> int:
    return int(_dt.datetime(y, mo, d, h, mi, tzinfo=RIYADH).timestamp())


# A Sunday 09:00-17:00 branch — 2026-08-16 is a Sunday, same fixture date test_availability.py uses.
SUNDAY = _dt.date(2026, 8, 16)
HOURS = Schedule(weekly={6: (Window(540, 1020),)})   # Sunday 09:00-17:00
AFTER = _riyadh_epoch(2026, 8, 16, 9, 0)
DAY_END = _riyadh_epoch(2026, 8, 16, 17, 0)


def test_no_candidates_is_an_empty_list_not_an_error():
    assert nearest_slots_any([], duration_minutes=30, after=AFTER,
                             window_end=DAY_END, max_slots=6) == []


def test_one_candidate_matches_the_single_operator_search_exactly():
    """The degenerate case — one eligible operator — must behave identically to `nearest_slot`
    called directly, since Phase 0 promises zero behaviour change for a shop that never turns on
    auto-assign (every service still has exactly one eligible operator today)."""
    cand = Candidate(operator_id='op1', schedule=HOURS, busy=())
    found = nearest_slots_any([cand], duration_minutes=30, after=AFTER,
                              window_end=DAY_END, max_slots=3)
    assert [s.starts_at for s in found] == [AFTER, AFTER + 1800, AFTER + 3600]
    assert all(s.operator_id == 'op1' for s in found)


def test_picks_whichever_operator_answers_soonest_each_round():
    """op1 is busy at 09:00 but free at 09:30; op2 is free at 09:00. The very first chip must
    belong to op2 (soonest overall), not op1 — the merge compares across candidates, not within
    one operator's own list first."""
    op1 = Candidate(operator_id='op1', schedule=HOURS,
                    busy=(Busy(AFTER, AFTER + 1800),))
    op2 = Candidate(operator_id='op2', schedule=HOURS, busy=())
    found = nearest_slots_any([op1, op2], duration_minutes=30, after=AFTER,
                              window_end=DAY_END, max_slots=1)
    assert len(found) == 1
    assert found[0].operator_id == 'op2'
    assert found[0].starts_at == AFTER


def test_cursor_advances_past_the_chosen_slot_for_the_next_round_globally():
    """After the first (soonest) slot is taken, the SECOND round's search starts from the end of
    that slot, not from each operator's own next opening independently — so two consecutive
    chips never overlap in wall-clock time, whichever operator each actually belongs to."""
    op1 = Candidate(operator_id='op1', schedule=HOURS, busy=())
    op2 = Candidate(operator_id='op2', schedule=HOURS, busy=())
    found = nearest_slots_any([op1, op2], duration_minutes=30, after=AFTER,
                              window_end=DAY_END, max_slots=2)
    assert len(found) == 2
    assert found[0].starts_at == AFTER
    # both operators are free at AFTER; the tie is broken by iteration order (op1 first) — real,
    # not incidental, since the whole point is "one merged chip row", not "one per operator".
    assert found[1].starts_at == AFTER + 1800


def test_stops_at_window_end_even_with_room_left_in_max_slots():
    """A one-hour window with a 30-minute service fits exactly two candidates; asking for six
    must not run past the window pretending more exist."""
    cand = Candidate(operator_id='op1', schedule=HOURS, busy=())
    found = nearest_slots_any([cand], duration_minutes=30, after=AFTER,
                              window_end=AFTER + 3600, max_slots=6)
    assert [s.starts_at for s in found] == [AFTER, AFTER + 1800]


def test_nobody_free_in_the_window_is_an_empty_list():
    op1 = Candidate(operator_id='op1', schedule=HOURS,
                    busy=(Busy(AFTER, DAY_END),))
    found = nearest_slots_any([op1], duration_minutes=30, after=AFTER,
                              window_end=DAY_END, max_slots=3)
    assert found == []
