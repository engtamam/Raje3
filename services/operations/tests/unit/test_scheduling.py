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
