"""The partner stamp — the rule that decides where money goes."""
from __future__ import annotations

import asyncio

import pytest

from app.adapters.datastore.memory import MemoryDataStore
from app.core.partners import DIRECT, PartnerError, PartnerRegistry


def run(c):
    return asyncio.run(c)


@pytest.fixture
def reg():
    return PartnerRegistry(MemoryDataStore(), salt="test-salt-value")


def mk(reg, name="نظام الكاشير", rate=0.25):
    return run(reg.create(name=name, commission_rate=rate))


def test_the_first_key_stamps_and_a_later_one_never_rewrites_it(reg):
    """Last-write-wins here means money flows to whoever called most recently — a rule nobody
    would write down and every naive implementation has."""
    a, key_a = mk(reg, "شريك أ")
    b, key_b = mk(reg, "شريك ب")
    first = run(reg.stamp("shop1", key=key_a))
    assert first["partner_id"] == a["id"]
    again = run(reg.stamp("shop1", key=key_b))
    assert again["partner_id"] == a["id"]
    assert b["id"] in again["seen_also"]


def test_a_direct_signup_is_stamped_too(reg):
    """'We brought this one ourselves' is a decided fact, and it is what stops a partner who
    integrates a month later from claiming a shop our own marketing paid for."""
    row = run(reg.stamp("shop2"))
    assert row["partner_id"] == DIRECT and row["commission_rate"] == 0.0


def test_a_partner_integrating_a_direct_shop_later_earns_nothing(reg):
    p, key = mk(reg)
    run(reg.stamp("shop3"))
    after = run(reg.stamp("shop3", key=key))
    assert after["partner_id"] == DIRECT
    assert p["id"] in after["seen_also"]


def test_stamping_twice_with_the_same_key_changes_nothing(reg):
    p, key = mk(reg)
    a = run(reg.stamp("shop4", key=key))
    b = run(reg.stamp("shop4", key=key))
    assert a["stamped_at"] == b["stamped_at"] and b["seen_also"] == []


def test_an_unknown_key_is_refused_not_treated_as_direct(reg):
    """Silently downgrading it means a partner whose key was mistyped in a deployment sees its
    shops attributed to us, with no way to discover why."""
    with pytest.raises(PartnerError, match="unknown partner key"):
        run(reg.stamp("shop5", key="rj3_not_a_real_key"))
    assert run(reg.stamp_of("shop5")) is None


def test_an_inactive_partner_cannot_onboard_new_shops(reg):
    p, key = mk(reg)
    run(reg.deactivate(p["id"]))
    with pytest.raises(PartnerError, match="not active"):
        run(reg.stamp("shop6", key=key))


def test_deactivating_a_partner_does_not_unstamp_its_existing_shops(reg):
    """They came through it once, and a falling-out does not rewrite history."""
    p, key = mk(reg)
    run(reg.stamp("shop7", key=key))
    run(reg.deactivate(p["id"]))
    assert run(reg.stamp_of("shop7"))["partner_id"] == p["id"]
    assert run(reg.tenants_of(p["id"])) == ["shop7"]


def test_the_key_is_never_stored_in_the_clear(reg):
    """Anyone holding it can attribute an establishment — which is anyone holding it can direct
    money."""
    p, key = mk(reg)
    row = run(reg.get(p["id"]))
    assert key not in str(row)
    assert row["key_hash"] != key and len(row["key_hash"]) == 64
    assert row["key_prefix"] == key[:12]


def test_the_hash_never_leaves_the_registry(reg):
    """A console that can display it can leak it into a log, a screenshot, or a support ticket."""
    mk(reg)
    assert all("key_hash" not in r for r in run(reg.list()))


def test_a_rate_given_as_a_percentage_is_refused(reg):
    """30 rather than 0.3 would pay a partner thirty times the subscription."""
    with pytest.raises(PartnerError, match="fraction"):
        run(reg.create(name="x", commission_rate=30))


def test_the_partners_shops_are_read_from_the_stamps(reg):
    """A denormalised list is a second place the truth lives, and the day it disagrees is the day
    somebody is paid for a shop they did not bring."""
    p, key = mk(reg)
    for shop in ("s1", "s2", "s3"):
        run(reg.stamp(shop, key=key))
    run(reg.stamp("s4"))
    assert sorted(run(reg.tenants_of(p["id"]))) == ["s1", "s2", "s3"]
