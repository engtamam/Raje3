"""The establishment's name — the one blank that must stop a send."""
from __future__ import annotations

import asyncio

from app.adapters.identity import Establishment, HttpIdentity, NullIdentity


def run(c):
    return asyncio.run(c)


def test_a_blank_name_is_not_usable():
    """A message reading 'your appointment at  is due' is accepted by Meta, read by the customer,
    and apologised for by the owner."""
    assert not Establishment(tenant="t1").usable
    assert not Establishment(tenant="t1", name="   ").usable
    assert Establishment(tenant="t1", name="ورشة النخبة").usable


def test_everything_except_the_name_degrades():
    """A missing tone falls back to warm; a missing colour is only a page's problem."""
    e = Establishment(tenant="t1", name="ورشة النخبة")
    assert e.usable and e.tone == "warm" and e.branding == {}


def test_the_null_driver_is_honest_about_answering_nothing():
    assert not run(NullIdentity().get("t1")).usable


def test_a_stale_name_is_preferred_over_an_empty_one():
    """If tenant-service is down at 3am, yesterday's correct name is right and a blank is not."""
    ident = HttpIdentity(url="http://unreachable.invalid", path="/internal/tenants/{id}",
                         token="x", timeout=1)
    ident._cache["t1"] = Establishment(tenant="t1", name="ورشة النخبة", fetched_at=0)
    got = run(ident.get("t1"))
    assert got.name == "ورشة النخبة"


def test_with_no_cache_and_an_unreachable_peer_it_is_unusable_rather_than_blank():
    """The caller defers instead of sending — see the tick."""
    ident = HttpIdentity(url="http://unreachable.invalid", path="/internal/tenants/{id}",
                         token="x", timeout=1)
    assert not run(ident.get("t1")).usable


def test_the_shop_has_exactly_one_name():
    """A shop has one name — the registry's — and the owner changes it from «حسابي». Nothing
    here ranks two candidates, because there is only ever one."""
    ident = HttpIdentity(url="http://x", path="/p/{id}", token="x")
    ident._fetch = lambda tenant, now: Establishment(
        tenant=tenant, name="ورشة النخبة", tone="warm", fetched_at=now)
    got = run(ident.get("t1"))
    assert got.name == "ورشة النخبة" and got.tone == "warm"
