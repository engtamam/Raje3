"""core/scheduling.py::is_offerable — the ONE place a package's schedule is ever decided. Every
booking refusal/acceptance and everything the WhatsApp assistant is or is not shown about a
package's timing traces back to this one function, so it is tested far past the ordinary bar.
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field

import pytest

from app.core.riyadh import RIYADH
from app.core.scheduling import (RECURRENCES, is_offerable, next_offerable_dates, valid_mmdd,
                                 validate_recurrence)


@dataclass
class _Pkg:
    active: bool = True
    starts_at: int = 0
    ends_at: int = 0
    recurrence: str = "none"
    recurrence_weekdays: list[int] = field(default_factory=list)
    recurrence_days_of_month: list[int] = field(default_factory=list)
    recurrence_yearly_from: str = ""
    recurrence_yearly_to: str = ""


def _riyadh(y: int, m: int, d: int, hh: int = 12) -> int:
    return int(dt.datetime(y, m, d, hh, tzinfo=RIYADH).timestamp())


# ── the master switch ─────────────────────────────────────────────────────────────────────────
def test_an_inactive_package_is_never_offerable_regardless_of_schedule():
    p = _Pkg(active=False)
    assert is_offerable(p, _riyadh(2026, 6, 1)) is False


def test_a_plain_active_open_ended_package_is_always_offerable():
    p = _Pkg()
    assert is_offerable(p, _riyadh(2020, 1, 1)) is True
    assert is_offerable(p, _riyadh(2099, 12, 31)) is True


# ── absolute bounds, independent of recurrence ────────────────────────────────────────────────
def test_a_start_date_in_the_future_refuses_until_it_arrives():
    p = _Pkg(starts_at=_riyadh(2026, 6, 1))
    assert is_offerable(p, _riyadh(2026, 5, 31)) is False
    assert is_offerable(p, _riyadh(2026, 6, 1, hh=13)) is True


def test_an_end_date_in_the_past_refuses():
    p = _Pkg(ends_at=_riyadh(2026, 6, 30))
    assert is_offerable(p, _riyadh(2026, 6, 30, hh=1)) is True
    assert is_offerable(p, _riyadh(2026, 7, 1)) is False


def test_only_a_start_with_no_end_never_expires():
    p = _Pkg(starts_at=_riyadh(2026, 1, 1))
    assert is_offerable(p, _riyadh(2099, 1, 1)) is True


def test_only_an_end_with_no_start_has_always_begun():
    p = _Pkg(ends_at=_riyadh(2026, 12, 31))
    assert is_offerable(p, _riyadh(2000, 1, 1)) is True


def test_bounds_still_apply_under_recurrence_none():
    """"none" means no weekly/monthly/yearly PATTERN — not "ignore the dates too"."""
    p = _Pkg(recurrence="none", starts_at=_riyadh(2026, 6, 1), ends_at=_riyadh(2026, 6, 30))
    assert is_offerable(p, _riyadh(2026, 5, 1)) is False
    assert is_offerable(p, _riyadh(2026, 6, 15)) is True
    assert is_offerable(p, _riyadh(2026, 7, 1)) is False


# ── weekly ─────────────────────────────────────────────────────────────────────────────────────
def test_weekly_matches_only_the_chosen_weekdays():
    # 2026-06-06 is a Saturday (weekday() == 5).
    p = _Pkg(recurrence="weekly", recurrence_weekdays=[5])
    assert is_offerable(p, _riyadh(2026, 6, 6)) is True
    assert is_offerable(p, _riyadh(2026, 6, 7)) is False    # Sunday


def test_weekly_accepts_more_than_one_day():
    p = _Pkg(recurrence="weekly", recurrence_weekdays=[4, 5])   # Friday + Saturday
    assert is_offerable(p, _riyadh(2026, 6, 5)) is True
    assert is_offerable(p, _riyadh(2026, 6, 6)) is True
    assert is_offerable(p, _riyadh(2026, 6, 8)) is False


def test_weekly_with_no_days_chosen_offers_nothing():
    p = _Pkg(recurrence="weekly", recurrence_weekdays=[])
    assert is_offerable(p, _riyadh(2026, 6, 6)) is False


def test_weekly_respects_the_riyadh_day_boundary_not_utc():
    """01:00 Riyadh on Saturday is 22:00 UTC Friday — a UTC-boundary bug would read this as Friday."""
    p = _Pkg(recurrence="weekly", recurrence_weekdays=[5])
    at = int(dt.datetime(2026, 6, 6, 1, tzinfo=RIYADH).timestamp())
    assert is_offerable(p, at) is True


# ── monthly ────────────────────────────────────────────────────────────────────────────────────
def test_monthly_matches_only_the_chosen_days_of_month():
    p = _Pkg(recurrence="monthly", recurrence_days_of_month=[1, 15])
    assert is_offerable(p, _riyadh(2026, 3, 1)) is True
    assert is_offerable(p, _riyadh(2026, 3, 15)) is True
    assert is_offerable(p, _riyadh(2026, 3, 16)) is False


def test_monthly_day_31_simply_never_matches_a_shorter_month():
    """Not an error — the same honest "does not recur that month" every real calendar app gives a
    day-31 monthly rule in February or April."""
    p = _Pkg(recurrence="monthly", recurrence_days_of_month=[31])
    assert is_offerable(p, _riyadh(2026, 1, 31)) is True
    assert is_offerable(p, _riyadh(2026, 2, 28)) is False


# ── yearly ─────────────────────────────────────────────────────────────────────────────────────
def test_yearly_ordinary_window_within_one_year():
    p = _Pkg(recurrence="yearly", recurrence_yearly_from="06-01", recurrence_yearly_to="08-31")
    assert is_offerable(p, _riyadh(2026, 5, 31)) is False
    assert is_offerable(p, _riyadh(2026, 6, 1)) is True
    assert is_offerable(p, _riyadh(2026, 7, 15)) is True
    assert is_offerable(p, _riyadh(2026, 8, 31)) is True
    assert is_offerable(p, _riyadh(2026, 9, 1)) is False


def test_yearly_window_wraps_the_new_year():
    p = _Pkg(recurrence="yearly", recurrence_yearly_from="12-20", recurrence_yearly_to="01-10")
    assert is_offerable(p, _riyadh(2026, 12, 19)) is False
    assert is_offerable(p, _riyadh(2026, 12, 25)) is True
    assert is_offerable(p, _riyadh(2027, 1, 1)) is True
    assert is_offerable(p, _riyadh(2027, 1, 10)) is True
    assert is_offerable(p, _riyadh(2027, 1, 11)) is False


def test_yearly_a_single_day_window():
    p = _Pkg(recurrence="yearly", recurrence_yearly_from="09-23", recurrence_yearly_to="09-23")
    assert is_offerable(p, _riyadh(2026, 9, 23)) is True
    assert is_offerable(p, _riyadh(2026, 9, 22)) is False
    assert is_offerable(p, _riyadh(2026, 9, 24)) is False


def test_yearly_a_leap_only_boundary_never_raises_on_a_non_leap_year():
    """A "02-29" boundary must never construct a real invalid date() — the comparison stays on
    bare (month, day) tuples for exactly this reason."""
    p = _Pkg(recurrence="yearly", recurrence_yearly_from="02-25", recurrence_yearly_to="02-29")
    assert is_offerable(p, _riyadh(2026, 2, 27)) is True     # 2026 is not a leap year
    assert is_offerable(p, _riyadh(2026, 3, 1)) is False


def test_yearly_with_a_malformed_boundary_refuses_rather_than_guess():
    p = _Pkg(recurrence="yearly", recurrence_yearly_from="", recurrence_yearly_to="08-31")
    assert is_offerable(p, _riyadh(2026, 7, 1)) is False


# ── the unknown value fails closed ────────────────────────────────────────────────────────────
def test_an_unknown_recurrence_value_refuses_rather_than_defaulting_to_always_on():
    p = _Pkg(recurrence="daily")     # not a real value
    assert is_offerable(p, _riyadh(2026, 6, 1)) is False


# ── next_offerable_dates — the WhatsApp assistant's own precomputed fact ──────────────────────
def test_next_offerable_dates_for_an_open_ended_package_is_every_day_in_the_horizon():
    p = _Pkg()
    dates = next_offerable_dates(p, from_at=_riyadh(2026, 6, 1), horizon_days=3)
    assert dates == ["2026-06-01", "2026-06-02", "2026-06-03"]


def test_next_offerable_dates_for_a_weekly_package_lists_only_matching_days():
    p = _Pkg(recurrence="weekly", recurrence_weekdays=[5])   # Saturday
    dates = next_offerable_dates(p, from_at=_riyadh(2026, 6, 1), horizon_days=14)
    assert dates == ["2026-06-06", "2026-06-13"]


def test_next_offerable_dates_is_empty_for_an_inactive_package():
    p = _Pkg(active=False)
    assert next_offerable_dates(p, from_at=_riyadh(2026, 6, 1), horizon_days=7) == []


def test_next_offerable_dates_respects_an_upcoming_end_date():
    p = _Pkg(ends_at=_riyadh(2026, 6, 3, hh=23))
    dates = next_offerable_dates(p, from_at=_riyadh(2026, 6, 1), horizon_days=7)
    assert dates == ["2026-06-01", "2026-06-02", "2026-06-03"]


# ── input validation (the CRUD routes' own guard) ─────────────────────────────────────────────
def test_valid_mmdd_parses_and_rejects():
    assert valid_mmdd("06-01") == (6, 1)
    assert valid_mmdd("13-01") is None
    assert valid_mmdd("06-32") is None
    assert valid_mmdd("6-1") is None
    assert valid_mmdd("") is None


def test_validate_recurrence_requires_weekdays_for_weekly():
    assert validate_recurrence(recurrence="weekly", weekdays=[], days_of_month=None,
                               yearly_from="", yearly_to="") != ""
    assert validate_recurrence(recurrence="weekly", weekdays=[0], days_of_month=None,
                               yearly_from="", yearly_to="") == ""


def test_validate_recurrence_rejects_an_out_of_range_weekday():
    assert validate_recurrence(recurrence="weekly", weekdays=[7], days_of_month=None,
                               yearly_from="", yearly_to="") != ""


def test_validate_recurrence_requires_days_of_month_for_monthly():
    assert validate_recurrence(recurrence="monthly", weekdays=None, days_of_month=[],
                               yearly_from="", yearly_to="") != ""
    assert validate_recurrence(recurrence="monthly", weekdays=None, days_of_month=[32],
                               yearly_from="", yearly_to="") != ""
    assert validate_recurrence(recurrence="monthly", weekdays=None, days_of_month=[1],
                               yearly_from="", yearly_to="") == ""


def test_validate_recurrence_requires_both_yearly_bounds():
    assert validate_recurrence(recurrence="yearly", weekdays=None, days_of_month=None,
                               yearly_from="06-01", yearly_to="") != ""
    assert validate_recurrence(recurrence="yearly", weekdays=None, days_of_month=None,
                               yearly_from="06-01", yearly_to="08-31") == ""


def test_validate_recurrence_rejects_an_unknown_mode():
    assert validate_recurrence(recurrence="daily", weekdays=None, days_of_month=None,
                               yearly_from="", yearly_to="") != ""


def test_validate_recurrence_none_needs_nothing():
    assert validate_recurrence(recurrence="none", weekdays=None, days_of_month=None,
                               yearly_from="", yearly_to="") == ""


def test_every_recurrence_constant_round_trips_through_validate():
    assert set(RECURRENCES) == {"none", "weekly", "monthly", "yearly"}


# ── deep edge cases (100-test robustness pass) ────────────────────────────────────────────────

def test_start_and_end_on_the_exact_same_second_is_offerable_only_then():
    at = _riyadh(2026, 6, 1, hh=10)
    p = _Pkg(starts_at=at, ends_at=at)
    assert is_offerable(p, at) is True
    assert is_offerable(p, at - 1) is False
    assert is_offerable(p, at + 1) is False


def test_end_date_at_the_very_last_second_of_its_day_still_counts():
    """23:59:59 Riyadh on the end day must still be offerable — a naive comparison against
    midnight of that day would refuse the whole last day."""
    end = int(dt.datetime(2026, 6, 30, 23, 59, 59, tzinfo=RIYADH).timestamp())
    p = _Pkg(ends_at=end)
    assert is_offerable(p, end) is True
    assert is_offerable(p, end + 1) is False


def test_weekly_all_seven_days_chosen_is_equivalent_to_no_restriction():
    p = _Pkg(recurrence="weekly", recurrence_weekdays=[0, 1, 2, 3, 4, 5, 6])
    for d in range(1, 8):
        assert is_offerable(p, _riyadh(2026, 6, d)) is True


def test_weekly_duplicate_weekdays_in_the_list_do_not_break_anything():
    p = _Pkg(recurrence="weekly", recurrence_weekdays=[5, 5, 5])
    assert is_offerable(p, _riyadh(2026, 6, 6)) is True   # a Saturday
    assert is_offerable(p, _riyadh(2026, 6, 7)) is False


def test_monthly_the_1st_and_the_last_plausible_day_together():
    p = _Pkg(recurrence="monthly", recurrence_days_of_month=[1, 30])
    assert is_offerable(p, _riyadh(2026, 4, 1)) is True
    assert is_offerable(p, _riyadh(2026, 4, 30)) is True
    assert is_offerable(p, _riyadh(2026, 4, 15)) is False


def test_monthly_every_day_of_a_31_day_month_chosen():
    p = _Pkg(recurrence="monthly", recurrence_days_of_month=list(range(1, 32)))
    for d in (1, 15, 31):
        assert is_offerable(p, _riyadh(2026, 1, d)) is True


def test_yearly_window_covering_the_whole_year():
    p = _Pkg(recurrence="yearly", recurrence_yearly_from="01-01", recurrence_yearly_to="12-31")
    assert is_offerable(p, _riyadh(2026, 1, 1)) is True
    assert is_offerable(p, _riyadh(2026, 12, 31)) is True
    assert is_offerable(p, _riyadh(2026, 6, 15)) is True


def test_yearly_window_that_wraps_and_covers_almost_the_whole_year():
    """"12-31" to "01-01" wraps and leaves only one day (Jan 2 .. Dec 30 excluded is wrong framing
    — actually this covers everything except nothing, since wrap logic is `>= start or <= end`:
    every day is either >= Dec 31 (only Dec 31) or <= Jan 1 (only Jan 1). So only two days count."""
    p = _Pkg(recurrence="yearly", recurrence_yearly_from="12-31", recurrence_yearly_to="01-01")
    assert is_offerable(p, _riyadh(2026, 12, 31)) is True
    assert is_offerable(p, _riyadh(2026, 1, 1)) is True
    assert is_offerable(p, _riyadh(2026, 6, 15)) is False


def test_yearly_boundary_exactly_on_leap_day_in_a_leap_year():
    p = _Pkg(recurrence="yearly", recurrence_yearly_from="02-25", recurrence_yearly_to="02-29")
    assert is_offerable(p, _riyadh(2028, 2, 29)) is True     # 2028 IS a leap year
    assert is_offerable(p, _riyadh(2028, 3, 1)) is False


def test_riyadh_midnight_boundary_both_directions():
    """23:59:59 Riyadh the day BEFORE a weekly match, and 00:00:00 Riyadh the matching day itself
    — both must read correctly despite being seconds apart in UTC."""
    p = _Pkg(recurrence="weekly", recurrence_weekdays=[5])   # Saturday
    just_before = int(dt.datetime(2026, 6, 5, 23, 59, 59, tzinfo=RIYADH).timestamp())
    just_after = int(dt.datetime(2026, 6, 6, 0, 0, 0, tzinfo=RIYADH).timestamp())
    assert is_offerable(p, just_before) is False
    assert is_offerable(p, just_after) is True


def test_active_false_overrides_a_schedule_that_would_otherwise_match():
    p = _Pkg(active=False, recurrence="none")
    assert is_offerable(p, _riyadh(2026, 6, 1)) is False


def test_recurrence_none_with_start_in_the_future_and_no_end():
    p = _Pkg(recurrence="none", starts_at=_riyadh(2030, 1, 1))
    assert is_offerable(p, _riyadh(2026, 1, 1)) is False
    assert is_offerable(p, _riyadh(2030, 1, 1, hh=13)) is True


def test_weekly_package_also_bounded_by_an_absolute_end_date_expires_on_schedule():
    """Both layers apply together — a Saturday-only package that also has an end date must stop
    on ALL Saturdays once past that end, not just the specific one it happened to end mid-week."""
    p = _Pkg(recurrence="weekly", recurrence_weekdays=[5], ends_at=_riyadh(2026, 6, 10))
    assert is_offerable(p, _riyadh(2026, 6, 6)) is True     # before the end date
    assert is_offerable(p, _riyadh(2026, 6, 13)) is False   # a Saturday, but past the end date


def test_next_offerable_dates_zero_horizon_is_empty():
    p = _Pkg()
    assert next_offerable_dates(p, from_at=_riyadh(2026, 6, 1), horizon_days=0) == []


def test_next_offerable_dates_single_day_horizon():
    p = _Pkg()
    assert next_offerable_dates(p, from_at=_riyadh(2026, 6, 1), horizon_days=1) == ["2026-06-01"]


def test_next_offerable_dates_monthly_across_a_month_boundary():
    p = _Pkg(recurrence="monthly", recurrence_days_of_month=[1])
    dates = next_offerable_dates(p, from_at=_riyadh(2026, 1, 20), horizon_days=15)
    assert dates == ["2026-02-01"]


def test_next_offerable_dates_yearly_wrap_from_late_december():
    p = _Pkg(recurrence="yearly", recurrence_yearly_from="12-20", recurrence_yearly_to="01-10")
    dates = next_offerable_dates(p, from_at=_riyadh(2026, 12, 15), horizon_days=10)
    assert dates == ["2026-12-20", "2026-12-21", "2026-12-22", "2026-12-23", "2026-12-24"]


def test_validate_recurrence_yearly_rejects_a_malformed_month():
    assert validate_recurrence(recurrence="yearly", weekdays=None, days_of_month=None,
                               yearly_from="13-01", yearly_to="12-31") != ""


def test_validate_recurrence_monthly_rejects_zero_as_a_day():
    assert validate_recurrence(recurrence="monthly", weekdays=None, days_of_month=[0],
                               yearly_from="", yearly_to="") != ""


def test_valid_mmdd_rejects_day_zero():
    assert valid_mmdd("06-00") is None
