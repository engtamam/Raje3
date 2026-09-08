"""The offer line the operator sees before he touches the service grid (§5.6.2).

AN OFFER HE CANNOT SEE BECOMES AN ARGUMENT AT THE COUNTER: the customer is holding a message from
this shop, the man in front of him knows nothing about it, and the shop either honours something it
did not plan or refuses something it did send.
"""
from __future__ import annotations

import asyncio

from app.adapters.datastore.memory import MemoryDataStore
from app.core.stores import SendLogStore

NOW = 1_800_000_000
DAY = 86400
T = "tnt_alpha"
REF = "ref-of-one-customer"


def _log(store, **kw):
    row = {"id": kw.pop("id", "snd_1"), "tenant": T, "subject_ref": REF, "cls": "marketing",
           "outcome": "sent", "at": NOW, **kw}
    asyncio.run(SendLogStore(store).append(T, row))
    return row


def test_the_offer_shown_is_the_one_that_was_SENT():
    """Not a field somebody retyped: what was not sent is not shown, and what was sent is shown in
    its own words."""
    store = MemoryDataStore()
    _log(store, offer_text="20% على قص شعر", offer_expires_at=NOW + 3 * DAY)

    got = asyncio.run(SendLogStore(store).active_offer(T, REF, used_refs=set(), now=NOW + DAY))
    assert got["offer_text"] == "20% على قص شعر"


def test_an_expired_offer_is_not_returned_at_all():
    """A screen that renders one which has run out contradicts the operator in front of the
    customer — worse than a screen that says nothing."""
    store = MemoryDataStore()
    _log(store, offer_text="خصم انتهى", offer_expires_at=NOW + DAY)

    assert asyncio.run(SendLogStore(store).active_offer(T, REF, used_refs=set(), now=NOW + 2 * DAY)) is None


def test_a_reminder_is_not_an_offer():
    """Most sends carry no offer at all, and a message without one must never furnish that line."""
    store = MemoryDataStore()
    _log(store, template_name="svc_service_reminder_brief")

    assert asyncio.run(SendLogStore(store).active_offer(T, REF, used_refs=set(), now=NOW)) is None
