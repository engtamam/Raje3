"""core/frustration.py — a pure function, unit tested directly against constructed inputs, no
engine, no store, no async."""
from app.core.frustration import detect_frustration, normalize_for_duplicate_check


def test_below_both_thresholds_is_not_frustration():
    assert not detect_frustration(
        unconfirmed_proposal_attempts=1,
        recent_user_texts=["متى تفتحون؟", "كم السعر؟"],
        unconfirmed_proposals_threshold=2, duplicate_messages_threshold=3)


def test_unconfirmed_proposal_attempts_at_threshold_is_frustration():
    assert detect_frustration(
        unconfirmed_proposal_attempts=2,
        recent_user_texts=[],
        unconfirmed_proposals_threshold=2, duplicate_messages_threshold=3)


def test_unconfirmed_proposal_attempts_one_below_threshold_is_not():
    assert not detect_frustration(
        unconfirmed_proposal_attempts=1,
        recent_user_texts=[],
        unconfirmed_proposals_threshold=2, duplicate_messages_threshold=3)


def test_near_duplicate_questions_at_threshold_is_frustration():
    assert detect_frustration(
        unconfirmed_proposal_attempts=0,
        recent_user_texts=["الساعة كم؟", "الساعة كم؟", "الساعة كم؟"],
        unconfirmed_proposals_threshold=2, duplicate_messages_threshold=3)


def test_near_duplicates_normalized_by_case_and_whitespace_still_count():
    assert detect_frustration(
        unconfirmed_proposal_attempts=0,
        recent_user_texts=["Hi there", "  hi   there  ", "HI THERE"],
        unconfirmed_proposals_threshold=2, duplicate_messages_threshold=3)


def test_distinct_messages_never_trip_the_duplicate_signal():
    assert not detect_frustration(
        unconfirmed_proposal_attempts=0,
        recent_user_texts=["متى تفتحون؟", "كم السعر؟", "وين موقعكم؟", "هل تقبلون فيزا؟"],
        unconfirmed_proposals_threshold=2, duplicate_messages_threshold=3)


def test_empty_messages_are_ignored_not_counted_as_duplicates_of_each_other():
    assert not detect_frustration(
        unconfirmed_proposal_attempts=0,
        recent_user_texts=["", "   ", ""],
        unconfirmed_proposals_threshold=2, duplicate_messages_threshold=3)


def test_normalize_collapses_case_and_whitespace():
    assert normalize_for_duplicate_check("  Hi   THERE  ") == "hi there"
    assert normalize_for_duplicate_check("") == ""
