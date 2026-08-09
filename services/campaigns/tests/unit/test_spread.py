"""Spreading a campaign across days — and the refusals that are the feature."""
from __future__ import annotations

from app.core.spread import DAY, next_batch, plan, sentence

NOW = 1_786_000_000


# ── how many days ──────────────────────────────────────────────────────────────────────────────
def test_an_audience_that_fits_goes_today():
    p = plan(audience=800, available_per_day=2000)
    assert p.ok and p.days == 1


def test_ten_thousand_against_two_thousand_is_five_days():
    p = plan(audience=10_000, available_per_day=2000)
    assert p.days == 5 and p.total == 10_000


def test_the_last_day_is_partial_rather_than_dropped():
    """9,001 against 2,000 is five days, not four and a half — and certainly not four with a
    thousand people quietly missing."""
    p = plan(audience=9001, available_per_day=2000)
    assert p.days == 5


def test_it_divides_the_available_share_not_the_whole_ceiling():
    """Available means AFTER the engine's reserve. A campaign that takes the whole ceiling
    silences the shop, and the customer who walks in after it gets nothing."""
    whole = plan(audience=10_000, available_per_day=2000).days
    after_reserve = plan(audience=10_000, available_per_day=1400).days
    assert after_reserve > whole


# ── what he is told before he presses send ─────────────────────────────────────────────────────
def test_he_is_told_how_many_days_before_he_commits():
    """An owner who expected an afternoon and got a week will say the product is broken, and he is
    right to — nothing told him."""
    s = sentence(plan(audience=10_000, available_per_day=2000))
    assert "5" in s and "10000" in s


def test_one_day_is_said_as_today():
    """'Within 1 days' is the phrasing that makes a product feel unfinished, on the last screen
    before he commits."""
    s = sentence(plan(audience=100, available_per_day=2000))
    assert "اليوم" in s and "أيام" not in s


# ── the refusals ───────────────────────────────────────────────────────────────────────────────
def test_an_expiring_offer_refuses_rather_than_spilling_past_its_deadline():
    """A customer receiving an offer that expired yesterday, from a shop that looks careless, is
    worse than a campaign that did not run."""
    p = plan(audience=10_000, available_per_day=2000, now=NOW, expires_at=NOW + 2 * DAY)
    assert not p.ok and "لن تصل" in p.refused


def test_the_refusal_names_both_remedies_because_only_he_can_choose():
    p = plan(audience=10_000, available_per_day=2000, now=NOW, expires_at=NOW + 2 * DAY)
    assert "صغّر" in p.refused and "مدّد" in p.refused
    assert "4000" in p.refused          # how many actually fit before the deadline


def test_an_offer_with_enough_time_is_not_refused():
    p = plan(audience=10_000, available_per_day=2000, now=NOW, expires_at=NOW + 9 * DAY)
    assert p.ok and p.days == 5


def test_no_room_today_is_not_a_zero_day_plan():
    """Saying '0 days' would read as 'done'."""
    p = plan(audience=500, available_per_day=0)
    assert not p.ok and "لا تتوفر" in p.refused


def test_an_empty_audience_says_so():
    assert not plan(audience=0, available_per_day=2000).ok


# ── the order is honoured across every day ─────────────────────────────────────────────────────
def test_today_is_taken_from_the_front_so_a_sorted_list_stays_sorted():
    """Whoever lands on day five waits five days. Insertion order is the shop's spreadsheet order
    and means nothing — so the caller sorts by what the campaign is FOR, and this must not
    reshuffle it."""
    pending = [f"sub_{i}" for i in range(10)]
    assert next_batch(pending=pending, available_per_day=4) == pending[:4]
    assert next_batch(pending=pending[4:], available_per_day=4) == pending[4:8]


def test_no_room_sends_nobody():
    assert next_batch(pending=["a", "b"], available_per_day=0) == []
