"""`app/core/features.py` — the app-store card's own content."""
from __future__ import annotations

import pytest

from app.core.features import INSIGHTS_FEATURES, TONES, Feature, public_features


def test_every_feature_has_a_stable_unique_id():
    ids = [f.id for f in INSIGHTS_FEATURES]
    assert len(ids) == len(set(ids))
    assert all(ids)


def test_every_feature_carries_a_short_plain_sentence():
    for f in INSIGHTS_FEATURES:
        assert f.title.strip() and f.detail.strip()
        assert len(f.title) <= 40, f"{f.id}'s title reads like a sentence, not a value line"


def test_every_feature_uses_a_declared_tone():
    for f in INSIGHTS_FEATURES:
        assert f.tone in TONES


def test_an_unknown_tone_is_refused_at_construction():
    with pytest.raises(ValueError):
        Feature(id="x", title="t", detail="d", icon="i", tone="chartreuse")


def test_public_features_drops_no_field_the_wire_contract_promises():
    out = public_features()
    assert len(out) == len(INSIGHTS_FEATURES)
    for row in out:
        assert set(row) == {"id", "title", "detail", "icon", "tone", "shared_with", "owned_by"}
        assert isinstance(row["shared_with"], list)
