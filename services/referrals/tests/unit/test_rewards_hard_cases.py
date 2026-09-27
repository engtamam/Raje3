"""Deeper adversarial coverage for app/core/rewards.py — type confusion, boundary values, and
malformed shapes a naive `int()`/`float()` cast would otherwise accept or crash on."""
from __future__ import annotations

import pytest

from app.core.rewards import RewardError, validate_new_customer_reward, validate_reward
from app.core.models import (
    NEW_CUSTOMER_DISCOUNT_PERCENT, NEW_CUSTOMER_WELCOME_POINTS,
    REWARD_FIXED_POINTS, REWARD_INVOICE_PERCENTAGE, REWARD_MYSTERY_BOX,
    REWARD_STATUS_MULTIPLIER, REWARD_TIME_BOOST,
)


# ── bool is an int subclass in Python — must never be silently accepted as a count ────────────
def test_bool_is_refused_everywhere_an_int_is_expected():
    with pytest.raises(RewardError):
        validate_reward(REWARD_FIXED_POINTS, {"points": True})
    with pytest.raises(RewardError):
        validate_reward(REWARD_INVOICE_PERCENTAGE, {"percent": False})
    with pytest.raises(RewardError):
        validate_reward(REWARD_STATUS_MULTIPLIER,
                        {"referrals_required": True, "multiplier": 2.0})


def test_bool_is_refused_as_a_multiplier():
    with pytest.raises(RewardError):
        validate_reward(REWARD_STATUS_MULTIPLIER, {"referrals_required": 5, "multiplier": True})


def test_bool_is_refused_inside_a_time_boost_window():
    with pytest.raises(RewardError):
        validate_reward(REWARD_TIME_BOOST, {
            "multiplier": 2.0,
            "windows": [{"weekday": True, "start_minute": 0, "end_minute": 60}],
        })


def test_bool_is_refused_inside_a_mystery_box_outcome():
    with pytest.raises(RewardError):
        validate_reward(REWARD_MYSTERY_BOX, {"outcomes": [
            {"points": True, "weight": 1}, {"points": 10, "weight": 1},
        ]})


# ── fractional floats truncating silently would be data loss, not normalization ───────────────
def test_non_integer_float_points_is_refused_not_truncated():
    with pytest.raises(RewardError):
        validate_reward(REWARD_FIXED_POINTS, {"points": 50.9})


def test_whole_number_float_is_accepted():
    c = validate_reward(REWARD_FIXED_POINTS, {"points": 50.0})
    assert c == {"points": 50}


# ── NaN / Infinity must never slip through float() parsing ────────────────────────────────────
def test_nan_multiplier_is_refused():
    with pytest.raises(RewardError):
        validate_reward(REWARD_STATUS_MULTIPLIER,
                        {"referrals_required": 5, "multiplier": float("nan")})


def test_infinite_multiplier_is_refused():
    with pytest.raises(RewardError):
        validate_reward(REWARD_STATUS_MULTIPLIER,
                        {"referrals_required": 5, "multiplier": float("inf")})


def test_infinite_points_is_refused_not_a_500():
    # int(float("inf")) raises OverflowError, not TypeError/ValueError — json accepts the
    # non-standard `Infinity` literal by default, so a crafted admin POST can reach this.
    with pytest.raises(RewardError):
        validate_reward(REWARD_FIXED_POINTS, {"points": float("inf")})
    with pytest.raises(RewardError):
        validate_reward(REWARD_FIXED_POINTS, {"points": float("-inf")})


def test_nan_points_is_refused_not_a_500():
    with pytest.raises(RewardError):
        validate_reward(REWARD_FIXED_POINTS, {"points": float("nan")})


def test_infinite_and_nan_points_refused_through_a_second_positive_int_field():
    # `referrals_required` (status_multiplier) goes through the same `_positive_int` — proving the
    # fix is in the shared helper, not a one-off patch on `fixed_points` alone.
    with pytest.raises(RewardError):
        validate_reward(REWARD_STATUS_MULTIPLIER,
                        {"referrals_required": float("inf"), "multiplier": 2.0})
    with pytest.raises(RewardError):
        validate_reward(REWARD_STATUS_MULTIPLIER,
                        {"referrals_required": float("nan"), "multiplier": 2.0})


def test_string_nan_and_inf_are_refused():
    with pytest.raises(RewardError):
        validate_reward(REWARD_STATUS_MULTIPLIER,
                        {"referrals_required": 5, "multiplier": "nan"})
    with pytest.raises(RewardError):
        validate_reward(REWARD_STATUS_MULTIPLIER,
                        {"referrals_required": 5, "multiplier": "inf"})


# ── percent boundaries ──────────────────────────────────────────────────────────────────────────
def test_percent_boundary_values():
    assert validate_reward(REWARD_INVOICE_PERCENTAGE, {"percent": 99}) == {"percent": 99}
    with pytest.raises(RewardError):
        validate_reward(REWARD_INVOICE_PERCENTAGE, {"percent": 100})
    with pytest.raises(RewardError):
        validate_reward(REWARD_INVOICE_PERCENTAGE, {"percent": 0})
    with pytest.raises(RewardError):
        validate_reward(REWARD_INVOICE_PERCENTAGE, {"percent": -1})


def test_multiplier_boundary_values():
    with pytest.raises(RewardError):
        # exactly 1.0 is refused — a "multiplier" of 1x multiplies nothing
        validate_reward(REWARD_STATUS_MULTIPLIER, {"referrals_required": 1, "multiplier": 1.0})
    assert validate_reward(REWARD_STATUS_MULTIPLIER,
                           {"referrals_required": 1, "multiplier": 10.0}
                           )["multiplier"] == 10.0
    with pytest.raises(RewardError):
        validate_reward(REWARD_STATUS_MULTIPLIER,
                        {"referrals_required": 1, "multiplier": 10.01})


# ── malformed shapes must refuse cleanly, never crash with a raw TypeError/AttributeError ──────
def test_reward_params_that_is_not_a_dict_is_refused_not_crashed():
    for bad in (None, [], ["points", 50], "points=50", 12345):
        # None is normalized to {} upstream and fails its own required-field check instead;
        # every other non-dict shape must be refused explicitly.
        if bad is None:
            with pytest.raises(RewardError):
                validate_reward(REWARD_FIXED_POINTS, bad)
            continue
        with pytest.raises(RewardError):
            validate_reward(REWARD_FIXED_POINTS, bad)


def test_mystery_box_outcome_that_is_not_a_dict_is_refused_not_crashed():
    with pytest.raises(RewardError):
        validate_reward(REWARD_MYSTERY_BOX, {"outcomes": ["not-a-dict", {"points": 1, "weight": 1}]})


def test_time_boost_window_that_is_not_a_dict_is_refused_not_crashed():
    with pytest.raises(RewardError):
        validate_reward(REWARD_TIME_BOOST, {"multiplier": 2.0, "windows": ["not-a-dict"]})


def test_time_boost_windows_as_a_string_iterates_characters_but_still_refuses_cleanly():
    # A caller sending "windows": "ab" (a string, not a list) would otherwise silently iterate
    # over two 1-character "windows" ('a', 'b') instead of refusing the wrong shape outright.
    with pytest.raises(RewardError):
        validate_reward(REWARD_TIME_BOOST, {"multiplier": 2.0, "windows": "ab"})


# ── new-customer reward gets the exact same hardening, not a second weaker copy ────────────────
def test_new_customer_reward_rejects_bool_and_bad_shapes():
    with pytest.raises(RewardError):
        validate_new_customer_reward(NEW_CUSTOMER_DISCOUNT_PERCENT, {"percent": True})
    with pytest.raises(RewardError):
        validate_new_customer_reward(NEW_CUSTOMER_WELCOME_POINTS, {"points": 20.5})
    with pytest.raises(RewardError):
        validate_new_customer_reward(NEW_CUSTOMER_WELCOME_POINTS, ["points", 20])
