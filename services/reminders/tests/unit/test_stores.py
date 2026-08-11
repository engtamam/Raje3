"""The send log as an ENTITLEMENT RECORD — which is what it is, and not only a list of messages.

An offer lives in this collection because sending it is what created the entitlement. So the rules
about spending one live here too: the four below are each a real way a customer could have
something taken from him, or a shop could honour the same thing twice.
"""
from __future__ import annotations

import pytest

from app.adapters.datastore.memory import MemoryDataStore
from app.core.stores import SendLogStore


@pytest.fixture
def store():
    return MemoryDataStore()


@pytest.mark.asyncio
async def test_an_offer_is_spent_only_when_somebody_says_so(store):
    """SILENCE NEVER SPENDS (§5.6.2). A customer who came in for something else and was silently
    charged an offer he was saving is a customer we took something from."""
    log = SendLogStore(store)
    await log.append("t1", {"id": "s1", "tenant": "t1", "subject_ref": "sub_a", "outcome": "sent",
                            "at": 100, "offer_text": "غسلة مجانية",
                            "offer_expires_at": 9_000_000, "offer_services": []})

    # Reading it changes nothing.
    assert len(await log.live_offers("t1", "sub_a", now=1000)) == 1

    row = await log.consume_offer("t1", "sub_a", visit_id="v1", service_ids=["x"], now=1000)
    assert row is not None
    # And now it is gone from what he is holding — not expired, SPENT.
    assert await log.live_offers("t1", "sub_a", now=1000) == []


@pytest.mark.asyncio
async def test_a_second_tap_on_one_visit_spends_nothing_more(store):
    """A double tap at a counter is one intention, and a screen that punished it is a screen
    people stop trusting."""
    log = SendLogStore(store)
    for i, exp in ((1, 9_000_000), (2, 9_500_000)):
        await log.append("t1", {"id": f"s{i}", "tenant": "t1", "subject_ref": "sub_a",
                                "outcome": "sent", "at": 100 + i, "offer_text": f"عرض {i}",
                                "offer_expires_at": exp, "offer_services": []})

    first = await log.consume_offer("t1", "sub_a", visit_id="v1", service_ids=[], now=1000)
    again = await log.consume_offer("t1", "sub_a", visit_id="v1", service_ids=[], now=1000)

    assert first["id"] == again["id"]
    # The second offer survives untouched — one visit spent one offer.
    assert len(await log.live_offers("t1", "sub_a", now=1000)) == 1


@pytest.mark.asyncio
async def test_the_scope_decides_and_the_soonest_to_expire_goes_first(store):
    """THE TEXT PERSUADES AND THE SCOPE APPLIES. A scoped offer is not spent by a visit that never
    touched its services — and holding two, he spends the one about to run out."""
    log = SendLogStore(store)
    await log.append("t1", {"id": "s1", "tenant": "t1", "subject_ref": "sub_a", "outcome": "sent",
                            "at": 101, "offer_text": "على الغسيل", "offer_expires_at": 9_000_000,
                            "offer_services": ["wash"]})
    await log.append("t1", {"id": "s2", "tenant": "t1", "subject_ref": "sub_a", "outcome": "sent",
                            "at": 102, "offer_text": "على كل شيء", "offer_expires_at": 8_000_000,
                            "offer_services": []})

    # A visit with neither: the scoped one must not be touched, and the open one is applicable.
    row = await log.consume_offer("t1", "sub_a", visit_id="v1", service_ids=["tyres"], now=1000)
    assert row["id"] == "s2"        # the open offer, and it expires soonest of the two

    row = await log.consume_offer("t1", "sub_a", visit_id="v2", service_ids=["wash"], now=1000)
    assert row["id"] == "s1"        # now the scoped one, because this visit carries its service


@pytest.mark.asyncio
async def test_a_visit_that_touches_nothing_scoped_spends_nothing(store):
    log = SendLogStore(store)
    await log.append("t1", {"id": "s1", "tenant": "t1", "subject_ref": "sub_a", "outcome": "sent",
                            "at": 101, "offer_text": "على الغسيل", "offer_expires_at": 9_000_000,
                            "offer_services": ["wash"]})

    assert await log.consume_offer("t1", "sub_a", visit_id="v1",
                                   service_ids=["tyres"], now=1000) is None
    assert len(await log.live_offers("t1", "sub_a", now=1000)) == 1
