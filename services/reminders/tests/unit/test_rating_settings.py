"""One establishment's answers about the rating app — enabled, delay, points. Foundation phase:
this store has no opinion on whether the app is owned, and nothing reads these numbers yet."""
from __future__ import annotations

import asyncio

import pytest

from app.adapters.datastore.memory import MemoryDataStore
from app.core.rating_settings import (
    DEFAULT_DELAY_MINUTES, DEFAULT_ENABLED, DEFAULT_POINTS,
    MAX_DELAY_MINUTES, MAX_POINTS, MIN_DELAY_MINUTES, RatingSettingsStore,
)


def run(c):
    return asyncio.run(c)


@pytest.fixture
def store():
    return RatingSettingsStore(MemoryDataStore())


# ── defaults, never a stored zero mistaken for one ───────────────────────────────────────────
def test_a_tenant_who_never_touched_this_reads_the_products_own_defaults(store):
    s = run(store.load("t1"))
    assert s.enabled is DEFAULT_ENABLED
    assert s.delay_minutes == DEFAULT_DELAY_MINUTES
    assert s.points == DEFAULT_POINTS


def test_the_default_delay_matches_the_platforms_own_visit_confirm_default():
    # 600 seconds, the pre-existing VISIT_CONFIRM_DELAY_SECONDS — a shop that never touches this
    # setting must see no change in timing, only in wording, once a later phase wires it.
    assert DEFAULT_DELAY_MINUTES == 10


def test_public_carries_exactly_the_three_fields(store):
    s = run(store.load("t1"))
    assert set(s.public()) == {"enabled", "delay_minutes", "points"}


# ── round-trip ────────────────────────────────────────────────────────────────────────────────
def test_set_enabled_false_survives_a_reload(store):
    run(store.set("t1", enabled=False))
    assert run(store.load("t1")).enabled is False


def test_set_enabled_true_survives_a_reload(store):
    run(store.set("t1", enabled=False))
    run(store.set("t1", enabled=True))
    assert run(store.load("t1")).enabled is True


def test_set_delay_minutes_survives_a_reload(store):
    run(store.set("t1", delay_minutes=120))
    assert run(store.load("t1")).delay_minutes == 120


def test_set_points_survives_a_reload(store):
    run(store.set("t1", points=5))
    assert run(store.load("t1")).points == 5


def test_zero_points_is_a_real_stored_value_not_the_default_sentinel(store):
    run(store.set("t1", points=7))
    run(store.set("t1", points=0))
    assert run(store.load("t1")).points == 0


def test_the_minimum_allowed_delay_is_accepted(store):
    run(store.set("t1", delay_minutes=MIN_DELAY_MINUTES))
    assert run(store.load("t1")).delay_minutes == MIN_DELAY_MINUTES


def test_the_maximum_allowed_delay_is_accepted(store):
    run(store.set("t1", delay_minutes=MAX_DELAY_MINUTES))
    assert run(store.load("t1")).delay_minutes == MAX_DELAY_MINUTES


def test_the_maximum_allowed_points_is_accepted(store):
    run(store.set("t1", points=MAX_POINTS))
    assert run(store.load("t1")).points == MAX_POINTS


# ── `None` means "leave it" — same rule ReasonIn uses ────────────────────────────────────────
def test_setting_only_delay_does_not_disturb_points_or_enabled(store):
    run(store.set("t1", enabled=False, points=3))
    run(store.set("t1", delay_minutes=90))
    s = run(store.load("t1"))
    assert s.delay_minutes == 90
    assert s.points == 3
    assert s.enabled is False


def test_setting_only_points_does_not_disturb_delay_or_enabled(store):
    run(store.set("t1", enabled=False, delay_minutes=45))
    run(store.set("t1", points=8))
    s = run(store.load("t1"))
    assert s.points == 8
    assert s.delay_minutes == 45
    assert s.enabled is False


def test_setting_only_enabled_does_not_disturb_delay_or_points(store):
    run(store.set("t1", delay_minutes=45, points=8))
    run(store.set("t1", enabled=False))
    s = run(store.load("t1"))
    assert s.enabled is False
    assert s.delay_minutes == 45
    assert s.points == 8


def test_calling_set_with_nothing_named_changes_nothing(store):
    run(store.set("t1", enabled=False, delay_minutes=30, points=4))
    run(store.set("t1"))
    s = run(store.load("t1"))
    assert (s.enabled, s.delay_minutes, s.points) == (False, 30, 4)


# ── validation — refuses rather than storing what would silently do nothing ─────────────────
def test_zero_delay_is_refused():
    store = RatingSettingsStore(MemoryDataStore())
    with pytest.raises(ValueError):
        run(store.set("t1", delay_minutes=0))


def test_negative_delay_is_refused():
    store = RatingSettingsStore(MemoryDataStore())
    with pytest.raises(ValueError):
        run(store.set("t1", delay_minutes=-5))


def test_a_delay_past_a_week_is_refused():
    store = RatingSettingsStore(MemoryDataStore())
    with pytest.raises(ValueError):
        run(store.set("t1", delay_minutes=MAX_DELAY_MINUTES + 1))


def test_negative_points_is_refused():
    store = RatingSettingsStore(MemoryDataStore())
    with pytest.raises(ValueError):
        run(store.set("t1", points=-1))


def test_points_past_the_ceiling_is_refused():
    store = RatingSettingsStore(MemoryDataStore())
    with pytest.raises(ValueError):
        run(store.set("t1", points=MAX_POINTS + 1))


def test_a_refused_write_leaves_the_previous_values_untouched(store):
    run(store.set("t1", delay_minutes=20, points=2))
    with pytest.raises(ValueError):
        run(store.set("t1", delay_minutes=0))
    s = run(store.load("t1"))
    assert (s.delay_minutes, s.points) == (20, 2)


def test_a_refused_points_write_does_not_partially_apply_a_delay_change_in_the_same_call(store):
    run(store.set("t1", delay_minutes=20))
    with pytest.raises(ValueError):
        run(store.set("t1", delay_minutes=999_999, points=-1))
    s = run(store.load("t1"))
    assert s.delay_minutes == 20


# ── isolation between tenants ────────────────────────────────────────────────────────────────
def test_two_tenants_never_see_each_others_settings(store):
    run(store.set("t1", enabled=False, delay_minutes=15, points=1))
    run(store.set("t2", enabled=True, delay_minutes=240, points=9))
    a, b = run(store.load("t1")), run(store.load("t2"))
    assert (a.enabled, a.delay_minutes, a.points) == (False, 15, 1)
    assert (b.enabled, b.delay_minutes, b.points) == (True, 240, 9)


def test_an_empty_tenant_string_still_returns_defaults_rather_than_raising(store):
    s = run(store.load(""))
    assert s.enabled is DEFAULT_ENABLED
