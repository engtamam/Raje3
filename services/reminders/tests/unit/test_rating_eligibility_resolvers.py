"""`_rating_eligible`/`_message_delay_seconds` (api/internal.py) — two INDEPENDENT facts.
`_rating_eligible` needs app ownership AND the settings toggle; `_message_delay_seconds` is asked
of every shop regardless of ownership (product decision: one delay setting governs both variants
of the post-visit-message slot, not gated behind owning the rating app).
"""
from __future__ import annotations

import asyncio

import pytest

from app.adapters.datastore.memory import MemoryDataStore
from app.api.internal import _message_delay_seconds, _rating_eligible
from app.core.rating_settings import RatingSettingsStore


def run(c):
    return asyncio.run(c)


class _FakeEntitlement:
    def __init__(self, owned: bool | None) -> None:
        self._owned = owned

    async def allowed(self, tenant, key):
        return self._owned


class _C:
    def __init__(self, *, owned: bool | None, store=None) -> None:
        self.app_entitlement = _FakeEntitlement(owned)
        self.datastore = store or MemoryDataStore()


def test_owns_the_app_and_enabled_is_eligible():
    c = _C(owned=True)
    run(RatingSettingsStore(c.datastore).set("t1", enabled=True))
    assert run(_rating_eligible(c, "t1")) is True


def test_owns_the_app_but_disabled_is_not_eligible():
    c = _C(owned=True)
    run(RatingSettingsStore(c.datastore).set("t1", enabled=False))
    assert run(_rating_eligible(c, "t1")) is False


def test_does_not_own_the_app_is_never_eligible_even_if_settings_say_enabled():
    c = _C(owned=False)
    run(RatingSettingsStore(c.datastore).set("t1", enabled=True))
    assert run(_rating_eligible(c, "t1")) is False


def test_billing_outage_none_is_treated_as_not_eligible():
    c = _C(owned=None)
    run(RatingSettingsStore(c.datastore).set("t1", enabled=True))
    assert run(_rating_eligible(c, "t1")) is False


def test_a_shop_that_never_touched_settings_defaults_to_enabled_true():
    # rating_settings.py's own default is enabled=True — a shop that owns the app and never
    # visited its settings screen should still get the rating message, not silently the plain one.
    c = _C(owned=True)
    assert run(_rating_eligible(c, "t1")) is True


def test_empty_tenant_is_never_eligible():
    c = _C(owned=True)
    assert run(_rating_eligible(c, "")) is False


def test_delay_seconds_reflects_the_configured_minutes():
    c = _C(owned=True)
    run(RatingSettingsStore(c.datastore).set("t1", delay_minutes=45))
    assert run(_message_delay_seconds(c, "t1")) == 45 * 60


def test_delay_seconds_defaults_to_ten_minutes_like_the_platform_default():
    c = _C(owned=True)
    assert run(_message_delay_seconds(c, "t1")) == 600


def test_two_tenants_get_their_own_delay_independently():
    c = _C(owned=True)
    run(RatingSettingsStore(c.datastore).set("t1", delay_minutes=15))
    run(RatingSettingsStore(c.datastore).set("t2", delay_minutes=120))
    assert run(_message_delay_seconds(c, "t1")) == 15 * 60
    assert run(_message_delay_seconds(c, "t2")) == 120 * 60


def test_delay_is_resolved_regardless_of_app_ownership():
    """A shop that does not own (or has never bought) the rating app can still configure its own
    plain-confirmation delay — the setting is not gated behind `_rating_eligible`."""
    c = _C(owned=False)
    run(RatingSettingsStore(c.datastore).set("t1", delay_minutes=30))
    assert run(_rating_eligible(c, "t1")) is False
    assert run(_message_delay_seconds(c, "t1")) == 30 * 60
