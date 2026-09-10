"""`app/core/features.py` — the app-store card's own content."""
from __future__ import annotations

import pytest

from app.core.features import CAMPAIGNS_FEATURES, TONES, Feature, public_features


def test_every_feature_has_a_stable_unique_id():
    ids = [f.id for f in CAMPAIGNS_FEATURES]
    assert len(ids) == len(set(ids))
    assert all(ids)


def test_every_feature_carries_a_short_plain_sentence():
    for f in CAMPAIGNS_FEATURES:
        assert f.title.strip() and f.detail.strip()
        assert len(f.title) <= 40, f"{f.id}'s title reads like a sentence, not a value line"


def test_every_feature_uses_a_declared_tone():
    for f in CAMPAIGNS_FEATURES:
        assert f.tone in TONES


def test_an_unknown_tone_is_refused_at_construction():
    with pytest.raises(ValueError):
        Feature(id="x", title="t", detail="d", icon="i", tone="chartreuse")


def test_nothing_here_claims_holdout_testing_or_return_measurement():
    """Both are checked-directly exclusions (see this module's own docstring): holdout is
    reminders' own code, and "who came back because of this" is insights' own code. Pinned so
    neither can silently get claimed here later."""
    ids = {f.id for f in CAMPAIGNS_FEATURES}
    assert not any("holdout" in i for i in ids)
    assert not any("return" in i or "measure" in i for i in ids)


def test_public_features_drops_no_field_the_wire_contract_promises():
    out = public_features()
    assert len(out) == len(CAMPAIGNS_FEATURES)
    for row in out:
        assert set(row) == {"id", "title", "detail", "icon", "tone", "shared_with", "owned_by"}
        assert isinstance(row["shared_with"], list)
