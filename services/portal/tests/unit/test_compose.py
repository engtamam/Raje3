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
    def __init__(self, prefs=None, fail=False, slow=0.0, offers=None, offers_fail=False):
        self.prefs, self.fail, self.slow = prefs, fail, slow
        self.offers, self.offers_fail = offers, offers_fail

    async def prefs_for(self, tenant, subject):
        if self.slow:
            await asyncio.sleep(self.slow)
        if self.fail:
            raise RuntimeError("reminders unreachable")
        # THE SHAPE reminders SERVES. Its default answer names every class, because the
        # marketing switch is drawn from a consent record and not from an absence.
        return self.prefs if self.prefs is not None else {"preferences": [
            {"class": c, "enabled": c != "marketing"} for c in CLASS_ORDER]}

    async def offers_for(self, tenant, subject):
        if self.slow:
            await asyncio.sleep(self.slow)
        if self.offers_fail:
            raise RuntimeError("reminders unreachable")
        return {"offers": self.offers or []}


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
    p = page(rem=Rem({"preferences": [{"class": c, "enabled": c != "marketing"}
                                      for c in CLASS_ORDER]}))
    assert [s["class"] for s in p.prefs.data] == list(CLASS_ORDER)
    assert {s["class"]: s["enabled"] for s in p.prefs.data}["marketing"] is False


def test_a_peer_that_grows_a_sixth_class_does_not_put_an_unlabelled_toggle_on_the_page():
    p = page(rem=Rem({"preferences": [{"class": "marketing", "enabled": False},
                                      {"class": "telepathy", "enabled": True}]}))
    assert len(p.prefs.data) == 5
    assert all(s["label"] and s["hint"] for s in p.prefs.data)


def test_a_peer_that_drops_a_class_does_not_make_a_switch_vanish():
    """A switch disappearing from under someone about to press it is worse than one that is on."""
    p = page(rem=Rem({"preferences": [{"class": "service", "enabled": True}]}))
    assert len(p.prefs.data) == 5


# ── the one switch that is not an opt-out (هـ-6) ───────────────────────────────────────────────
def test_a_class_the_peer_did_not_mention_stays_on_because_it_is_an_opt_out():
    """Service, personal, awareness and warning run until the customer stops them (§8.4.2). A
    dropped class must not read as a refusal he never made."""
    p = page(rem=Rem({"preferences": [{"class": "marketing", "enabled": True}]}))
    on = {s["class"]: s["enabled"] for s in p.prefs.data}
    assert on["service"] is True and on["warning"] is True


def test_marketing_is_off_when_the_peer_did_not_say_he_agreed():
    """THE ONE THAT IS OPT-IN. «لم يرفض» is not consent — §8.5 and the PDPL — and the sending gate
    refuses `never_asked` exactly as it refuses `withdrawn`. This page drew every switch from the
    absence of a stop, so «العروض والخصومات» rendered TICKED to a customer who had granted
    nothing: a permission described on his screen that we would refuse to act on."""
    p = page(rem=Rem({"preferences": [{"class": "service", "enabled": True}]}))
    assert {s["class"]: s["enabled"] for s in p.prefs.data}["marketing"] is False


def test_the_alternate_response_shape_is_understood_too():
    """reminders returns {'preferences': [...]}; a future version might return the list bare."""
    a = page(rem=Rem({"preferences": [{"class": "awareness", "enabled": False}]}))
    b = page(rem=Rem([{"class": "awareness", "enabled": False}]))
    for p in (a, b):
        assert {s["class"]: s["enabled"] for s in p.prefs.data}["awareness"] is False


# ── his offers, as a section like any other ────────────────────────────────────────────────────
import time  # noqa: E402

SOON = int(time.time()) + 3 * 86400
GONE = int(time.time()) - 60


def test_the_offers_arrive_and_carry_their_end():
    p = page(rem=Rem(offers=[{"text": "20% على غيار الزيت", "expires_at": SOON,
                              "sent_at": SOON - 86400, "services": ["srv_1"]}]))
    assert p.offers.available
    assert p.offers.data[0]["expires_at"] == SOON
    assert p.offers.data[0]["services"] == ["srv_1"]


def test_an_expired_offer_is_dropped_here_too():
    """The peer already drops them, and this drops them again — not from distrust but because of
    WHEN the page is read: a link sits in a chat for days, and the second reading can fall on the
    other side of an expiry the first did not."""
    p = page(rem=Rem(offers=[{"text": "خصم انتهى", "expires_at": GONE}]))
    assert p.offers.available
    assert p.offers.data == []


def test_an_offer_with_no_end_is_not_an_offer():
    """Nothing can count down to a deadline that does not exist, and a discount with no end is a
    price change nobody decided on."""
    p = page(rem=Rem(offers=[{"text": "خصم أبدي", "expires_at": 0}]))
    assert p.offers.data == []


def test_offers_failing_does_not_empty_the_page():
    """A customer who came to read an offer and found a 500 concludes the shop's message was a
    trick. The section says it is unavailable; it does not pretend he has none."""
    p = page(rem=Rem(offers_fail=True))
    assert p.has_identity and p.prefs.available
    assert not p.offers.available


def test_soonest_to_expire_comes_first():
    """The order he needs to act in — not the order they arrived, which is an order only we care
    about."""
    later = SOON + 86400
    p = page(rem=Rem(offers=[{"text": "لاحق", "expires_at": later},
                             {"text": "أقرب", "expires_at": SOON}]))
    assert [o["text"] for o in p.offers.data] == ["أقرب", "لاحق"]


class _Loyalty:
    def __init__(self, payload):
        self.payload = payload

    async def balance_for(self, tenant, subject_ref):
        return self.payload


@pytest.mark.asyncio
async def test_his_points_reach_his_own_page():
    """THE ONE NUMBER HE CANNOT GET ANYWHERE ELSE. A balance he never sees does not bring him
    back, and a reward he does not know he can afford is never asked for."""
    c = Composer(identity=Ident(), operations=Ops(), reminders=Rem(),
                 loyalty=_Loyalty({"has_programme": True, "points": 140,
                                   "rewards": [{"id": "r1", "name": "غسلة", "cost": 100}],
                                   "to_next_reward": 0}))
    page = await c.build("t1", "sub_a")

    assert page.points.available is True
    assert page.points.data["points"] == 140


@pytest.mark.asyncio
async def test_a_shop_with_no_programme_shows_no_points_section():
    """Not a zero — an ABSENCE. A points card reading zero on the page of a shop that runs no
    loyalty is a promise nobody made, and he would ask about it at the counter.

    THE PAYLOAD IS LOYALTY'S REAL ONE. This used to pass `{}`, which loyalty has never returned
    for any shop: every key it serves has a value, so the emptiness test that guarded this was
    true for every customer of every shop and the card was shown to all of them (هـ-1)."""
    c = Composer(identity=Ident(), operations=Ops(), reminders=Rem(),
                 loyalty=_Loyalty({"has_programme": False, "points": 0, "manager_threshold": 0,
                                   "rewards": [], "to_next_reward": 0, "expires_at": 0}))
    page = await c.build("t1", "sub_a")

    assert page.points.available is False


@pytest.mark.asyncio
async def test_the_page_survives_loyalty_being_absent_entirely():
    """A deployment without the service composes four sections rather than failing — the same rule
    every other peer here follows."""
    page = await Composer(identity=Ident(), operations=Ops(),
                          reminders=Rem()).build("t1", "sub_a")

    assert page.points.available is False
    assert page.visits.available is True
