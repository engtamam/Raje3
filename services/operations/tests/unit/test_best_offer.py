"""`core/best_offer.py::rank` — the one shared decision both `core/entitlements.py` (visits) and
`core/discount_consultation.py` (WhatsApp orders) now call, instead of each holding its own copy of
this same `max(..., key=...)` + fallback-order logic."""
from __future__ import annotations

from app.core.best_offer import OfferCandidate, rank


def _c(source: str, value) -> OfferCandidate:
    return OfferCandidate(source=source, value_minor=value, ref=f"ref_{source}",
                          text=f"text_{source}")


def test_the_highest_priced_candidate_wins_regardless_of_order():
    winner = rank([_c("a", 500), _c("b", 1000), _c("c", 10)])
    assert winner.source == "b"


def test_a_single_candidate_wins_trivially():
    assert rank([_c("a", 5)]).source == "a"


def test_no_candidates_at_all_returns_none():
    assert rank([]) is None


def test_every_candidate_unpriced_falls_back_to_the_given_order():
    winner = rank([_c("a", None), _c("b", None)], fallback_order=("b", "a"))
    assert winner.source == "b"


def test_a_zero_value_candidate_never_beats_a_positive_one():
    winner = rank([_c("a", 0), _c("b", 1)])
    assert winner.source == "b"


def test_every_candidate_at_zero_falls_back_to_the_given_order_not_an_arbitrary_zero():
    winner = rank([_c("a", 0), _c("b", 0)], fallback_order=("b", "a"))
    assert winner.source == "b"


def test_no_fallback_order_and_nothing_priced_returns_none():
    """The caller that never wants a fallback at all (`discount_consultation.best_offer_for`,
    which passes no `fallback_order`) gets a clean `None`, not an arbitrary pick."""
    assert rank([_c("a", 0), _c("b", None)]) is None


def test_a_fallback_order_naming_a_source_not_present_is_skipped_safely():
    winner = rank([_c("a", None)], fallback_order=("missing", "a"))
    assert winner.source == "a"
