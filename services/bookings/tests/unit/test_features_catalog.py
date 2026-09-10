"""`app/core/features.py` — the app-store card's own content, and the shape it promises callers.

WHAT THIS PINS. Every entry is real, marketing-safe content, keyed and toned consistently — the
same discipline `plans.json`'s own tests hold its price list to.
"""
from __future__ import annotations

from app.core.features import BOOKINGS_FEATURES, TONES, Feature, public_features


def test_every_feature_has_a_stable_unique_id():
    ids = [f.id for f in BOOKINGS_FEATURES]
    assert len(ids) == len(set(ids)), "two features share one id — the console cannot key a list on it"
    assert all(ids), "an empty id cannot be referenced from another app's own catalog"


def test_every_feature_carries_a_short_plain_sentence():
    for f in BOOKINGS_FEATURES:
        assert f.title.strip(), f"{f.id} has no title"
        assert f.detail.strip(), f"{f.id} has no detail"
        # SHORT, ON PURPOSE (2026-09-11 product decision) — a title reading like a paragraph is a
        # mechanism description wearing a marketing font, not a value sentence.
        assert len(f.title) <= 40, f"{f.id}'s title reads like a sentence, not a value line"


def test_every_feature_uses_a_declared_tone():
    for f in BOOKINGS_FEATURES:
        assert f.tone in TONES, f"{f.id} carries an unknown tone {f.tone!r}"


def test_an_unknown_tone_is_refused_at_construction():
    import pytest

    with pytest.raises(ValueError):
        Feature(id="x", title="t", detail="d", icon="i", tone="chartreuse")


def test_the_shared_reminders_feature_names_its_real_owner():
    """`reminders.learns_each_customer` is not this service's own code — see its own docstring.
    Pinned explicitly so a future edit cannot quietly turn it into an unattributed bookings claim."""
    shared = next(f for f in BOOKINGS_FEATURES if f.id == "reminders.learns_each_customer")
    assert shared.owned_by == "reminders"
    assert "visit" in shared.shared_with


def test_public_features_drops_no_field_the_wire_contract_promises():
    out = public_features()
    assert len(out) == len(BOOKINGS_FEATURES)
    for row in out:
        assert set(row) == {"id", "title", "detail", "icon", "tone", "shared_with", "owned_by"}
        assert isinstance(row["shared_with"], list)
