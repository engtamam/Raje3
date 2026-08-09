"""Composing a page from three peers that may not all be there."""
from __future__ import annotations

import asyncio

import pytest

from app.core.compose import CLASS_ORDER, Composer


def run(c):
    return asyncio.run(c)


class Shop:
    def __init__(self, name="ورشة النخبة", accent="#0F5F4E"):
        self.name = name
        self.branding = {"accent": accent}


class Ident:
    def __init__(self, shop=None, fail=False, slow=0.0):
        self.shop, self.fail, self.slow = shop or Shop(), fail, slow

    async def get(self, tenant):
        if self.slow:
            await asyncio.sleep(self.slow)
        if self.fail:
            raise RuntimeError("tenant-service unreachable")
        return self.shop


class Ops:
    def __init__(self, visits=None, fail=False, slow=0.0):
        self.visits, self.fail, self.slow = visits or [], fail, slow

    async def visits_for(self, tenant, subject):
        if self.slow:
            await asyncio.sleep(self.slow)
        if self.fail:
            raise RuntimeError("operations unreachable")
        return self.visits


class Rem:
    def __init__(self, prefs=None, fail=False, slow=0.0):
        self.prefs, self.fail, self.slow = prefs, fail, slow

    async def prefs_for(self, tenant, subject):
        if self.slow:
            await asyncio.sleep(self.slow)
        if self.fail:
            raise RuntimeError("reminders unreachable")
        return self.prefs if self.prefs is not None else {"stopped": {}}


def page(ident=None, ops=None, rem=None, deadline=3.0):
    c = Composer(identity=ident or Ident(), operations=ops or Ops(),
                 reminders=rem or Rem(), deadline_seconds=deadline)
    return run(c.build("tnt-alpha", "sub_abc123def456"))


def test_a_whole_page_renders_when_everything_is_up():
    p = page(ops=Ops([{"id": "v1"}]))
    assert p.has_identity and p.visits.available and p.prefs.available
    assert len(p.prefs.data) == 5


def test_operations_being_down_does_not_empty_the_page():
    """Most people opened the link for the switches; the history is the part they can live without."""
    p = page(ops=Ops(fail=True))
    assert p.has_identity and p.prefs.available
    assert not p.visits.available


def test_reminders_being_down_leaves_the_switches_honest_rather_than_broken():
    """Showing them togglable and then failing the save is worse than admitting it up front."""
    p = page(rem=Rem(fail=True))
    assert not p.prefs.available and p.has_identity


def test_the_shop_name_missing_still_renders_a_page():
    """A page saying nothing beats a 500 that says the shop is broken."""
    p = page(ident=Ident(fail=True))
    assert not p.has_identity and p.prefs.available


def test_everything_down_is_still_a_page_and_not_an_error():
    p = page(ident=Ident(fail=True), ops=Ops(fail=True), rem=Rem(fail=True))
    assert p.tenant == "tnt-alpha" and not p.visits.available


def test_one_slow_peer_does_not_hold_the_page_past_its_deadline():
    """Three calls with a five-second timeout each is a fifteen-second page, which is a page
    nobody sees. The budget belongs to the person waiting."""
    import time
    start = time.monotonic()
    p = page(ops=Ops(slow=5), deadline=0.3)
    assert time.monotonic() - start < 2
    assert not p.visits.available


def test_no_visits_and_could_not_load_visits_are_different_answers():
    """Showing 'you have no visits yet' when the truth is 'we could not load them' is a lie the
    customer has no way to detect."""
    empty = page(ops=Ops([]))
    broken = page(ops=Ops(fail=True))
    assert empty.visits.available and empty.visits.data == []
    assert not broken.visits.available


def test_the_switches_come_back_in_the_customers_order_whatever_the_peer_sent():
    p = page(rem=Rem({"stopped": {"marketing": True}}))
    assert [s["class"] for s in p.prefs.data] == list(CLASS_ORDER)
    assert {s["class"]: s["enabled"] for s in p.prefs.data}["marketing"] is False


def test_a_peer_that_grows_a_sixth_class_does_not_put_an_unlabelled_toggle_on_the_page():
    p = page(rem=Rem({"stopped": {"marketing": True, "telepathy": True}}))
    assert len(p.prefs.data) == 5
    assert all(s["label"] and s["hint"] for s in p.prefs.data)


def test_a_peer_that_drops_a_class_does_not_make_a_switch_vanish():
    """A switch disappearing from under someone about to press it is worse than one that is on."""
    p = page(rem=Rem({"stopped": {}}))
    assert len(p.prefs.data) == 5


def test_the_alternate_response_shape_is_understood_too():
    """reminders returns {'preferences': [...]}; a future version might return the list bare."""
    a = page(rem=Rem({"preferences": [{"class": "marketing", "enabled": False}]}))
    b = page(rem=Rem([{"class": "marketing", "enabled": False}]))
    for p in (a, b):
        assert {s["class"]: s["enabled"] for s in p.prefs.data}["marketing"] is False
