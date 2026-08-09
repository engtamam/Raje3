"""The engine — and the family receipt it exists to catch."""
from __future__ import annotations

import pytest

from app.core.associations import (MIN_BASKETS, STRONG, build, classify, count_pairs,
                                   is_group_basket, lift, missed_opportunities)
from app.core.models import Pair

T = "shop"


def baskets(n, *items):
    return [list(items) for _ in range(n)]


# ── the measure ────────────────────────────────────────────────────────────────────────────────
def test_lift_of_one_is_exactly_chance():
    # a in 40, b in 20, together in 8 of 100 → 8% vs an expected 8%.
    assert lift(both=8, count_a=40, count_b=20, total=100) == pytest.approx(1.0)


def test_lift_of_two_is_twice_what_chance_explains():
    assert lift(both=16, count_a=40, count_b=20, total=100) == pytest.approx(2.0)


def test_a_popular_service_does_not_look_like_a_companion_to_everything():
    """THE REASON FOR THE DIVISION. Counting co-occurrences alone would make a wash that is in 90%
    of visits the 'companion' of every line in the catalogue, confidently."""
    # wash in 90, wax in 10, together in 9 — exactly what chance predicts for a 90% service.
    assert lift(both=9, count_a=90, count_b=10, total=100) == pytest.approx(1.0)


def test_an_absent_service_has_no_relationships_rather_than_an_error():
    assert lift(both=0, count_a=0, count_b=5, total=100) == 0.0


def test_counting_ignores_empty_baskets():
    """Counting them would inflate the denominator and drag every lift in the shop downward —
    a silent, uniform error, which is the worst kind."""
    _, _, total = count_pairs([["a", "b"], [], ["a"]])
    assert total == 2


def test_a_pair_is_counted_once_not_twice():
    _, pairs, _ = count_pairs([["b", "a"], ["a", "b"]])
    assert list(pairs) == [("a", "b")] and pairs[("a", "b")] == 2


def test_a_repeated_service_in_one_basket_counts_once():
    singles, _, _ = count_pairs([["a", "a", "b"]])
    assert singles["a"] == 1


# ── the verdicts ───────────────────────────────────────────────────────────────────────────────
def test_the_family_receipt_is_caught():
    """Together on the bill, never in one person over time — the whole reason there are two lifts."""
    assert classify(lift_basket=3.0, lift_customer=1.0) == "group"


def test_a_real_relationship_holds_on_both_axes():
    assert classify(lift_basket=2.0, lift_customer=2.2) == "real"


def test_a_relationship_across_time_is_not_a_bundle():
    assert classify(lift_basket=1.0, lift_customer=2.5) == "temporal"


def test_an_ambiguous_pair_gets_no_verdict_rather_than_a_guess():
    """Between the two thresholds is genuinely uncertain, and forcing it into a verdict would
    manufacture certainty we do not have."""
    assert classify(lift_basket=1.35, lift_customer=1.35) == "none"


# ── the group basket, detected without knowing the shop ────────────────────────────────────────
def test_two_of_the_same_item_is_a_group():
    assert is_group_basket(["coffee", "cake"], quantities={"coffee": 2}) is True


def test_an_outsized_basket_is_a_group():
    assert is_group_basket(list("abcdefghij"), median_size=2) is True


def test_an_ordinary_basket_is_not():
    assert is_group_basket(["oil", "filter"], quantities={"oil": 1}, median_size=2) is False


def test_a_slightly_large_basket_is_not_a_group():
    """Dropping honest baskets costs us the signal we are trying to find, so the bar is generous."""
    assert is_group_basket(["a", "b", "c"], median_size=2) is False


# ── end to end ─────────────────────────────────────────────────────────────────────────────────
def test_below_the_threshold_it_says_it_is_learning_rather_than_guessing():
    res = build(baskets=baskets(10, "a", "b"), sequences=[["a", "b"]], tenant=T)
    assert res["learning"] is True and res["pairs"] == []
    assert res["need"] == MIN_BASKETS and res["have"] == 10


def test_lift_is_bounded_by_how_common_the_pair_is():
    """A PROPERTY WORTH KNOWING BEFORE READING ANY NUMBER FROM THIS ENGINE.

    Two services that each appear in 60% of visits and together in 40% have a lift of only 1.11 —
    even though they co-occur constantly — because chance already predicts 36%. Lift measures
    SURPRISE, not strength, and a pair of near-ubiquitous services cannot be surprising.

    This is not a defect and it must not be "fixed" by lowering the threshold: a shop where two
    things are always bought together does not need us to tell it so. The finding it exists for is
    the pair the owner has NOT noticed.
    """
    assert lift(both=100, count_a=150, count_b=150, total=250) == pytest.approx(1.11, abs=0.01)


def test_a_real_pair_is_found_on_both_axes():
    # 400 visits: 80 have both, 60 oil only, 20 filter only, 240 neither. Oil is in 35% and the
    # filter in 25%, so chance predicts 8.75% together and the truth is 20%.
    b = (baskets(80, "oil", "filter") + baskets(60, "oil") + baskets(20, "filter")
         + baskets(240, "wash"))
    seqs = ([["oil", "filter"]] * 80) + ([["oil"]] * 60) + ([["filter"]] * 20) + ([["wash"]] * 240)
    res = build(baskets=b, sequences=seqs, tenant=T)
    pair = next(p for p in res["pairs"] if {p.a, p.b} == {"oil", "filter"})
    assert pair.verdict == "real"
    assert pair.lift_basket >= STRONG and pair.lift_customer >= STRONG


def test_the_family_receipt_is_excluded_end_to_end():
    """Burger and kids-meal on 100 receipts — but NO customer ever takes both across their own
    visits, which is what a table of three people looks like from a distance."""
    b = (baskets(100, "burger", "kidsmeal") + baskets(20, "burger") + baskets(20, "kidsmeal")
         + baskets(260, "juice"))
    # Each customer takes exactly ONE of the two across every visit they have ever made — which is
    # what a table of three people looks like once you stop reading the receipt.
    seqs = ([["burger", "juice"]] * 150) + ([["kidsmeal", "juice"]] * 150)
    res = build(baskets=b, sequences=seqs, tenant=T)
    pair = next(p for p in res["pairs"] if {p.a, p.b} == {"burger", "kidsmeal"})
    assert pair.verdict == "group"


def test_a_rare_pair_is_dropped_as_noise():
    """Two services bought together twice in a year produce a spectacular lift and mean nothing."""
    b = baskets(300, "wash") + baskets(2, "rare1", "rare2")
    res = build(baskets=b, sequences=[["wash"]] * 300, tenant=T)
    assert not [p for p in res["pairs"] if {p.a, p.b} == {"rare1", "rare2"}]


def test_missed_opportunities_need_a_rule_to_exist_at_all():
    """Without one, every service a customer has not bought is a 'missed opportunity' and the
    indicator is a re-print of the catalogue."""
    assert missed_opportunities([], {"ref1": ["oil"]}) == []


def test_missed_opportunities_are_the_inverse_of_a_rule():
    p = Pair(tenant=T, a="oil", b="filter", verdict="real")
    out = missed_opportunities([p], {"ref1": ["oil"], "ref2": ["oil", "filter"], "ref3": ["wash"]})
    assert out == [{"subject_ref": "ref1", "has": "oil", "missing": "filter", "verdict": "real"}]


def test_a_group_pair_never_becomes_a_missed_opportunity():
    p = Pair(tenant=T, a="burger", b="kidsmeal", verdict="group")
    assert missed_opportunities([p], {"ref1": ["burger"]}) == []
