"""The single-use discount for WhatsApp Direct Ordering (2026-10-04) — a flag deliberately
separate from the visit-side `active_offer`/`choose_offer` mechanism (see
`SendLogStore.find_unredeemed_discount`'s own docstring for why).
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


def test_a_live_discount_send_is_found():
    store = MemoryDataStore()
    _log(store, reward_kind="percent", reward_amount=20, offer_expires_at=NOW + 3 * DAY)

    got = asyncio.run(SendLogStore(store).find_unredeemed_discount(T, REF, now=NOW + DAY))
    assert got is not None
    assert got["reward_kind"] == "percent" and got["reward_amount"] == 20


def test_a_send_with_no_discount_is_not_returned():
    store = MemoryDataStore()
    _log(store, offer_expires_at=NOW + 3 * DAY)          # no reward_kind at all — an announcement

    assert asyncio.run(
        SendLogStore(store).find_unredeemed_discount(T, REF, now=NOW + DAY)) is None


def test_an_expired_discount_is_not_returned():
    store = MemoryDataStore()
    _log(store, reward_kind="percent", reward_amount=20, offer_expires_at=NOW + DAY)

    assert asyncio.run(
        SendLogStore(store).find_unredeemed_discount(T, REF, now=NOW + 2 * DAY)) is None


def test_redeeming_removes_it_from_the_active_lookup():
    """THE CENTRAL GUARANTEE: once marked redeemed, the same discount never shows up again — a
    second order for the same customer must not see it as still available."""
    store = MemoryDataStore()
    _log(store, reward_kind="percent", reward_amount=20, offer_expires_at=NOW + 3 * DAY)

    log = SendLogStore(store)
    ok = asyncio.run(log.mark_redeemed(T, "snd_1", redeemed_by="order:ord_1", now=NOW))
    assert ok is True

    assert asyncio.run(log.find_unredeemed_discount(T, REF, now=NOW + DAY)) is None


def test_redeeming_twice_with_the_same_consumer_is_idempotent():
    """A retried confirm-payment call (the network dropped the first response) must not be treated
    as a conflict — it is the SAME order confirming the SAME thing again."""
    store = MemoryDataStore()
    _log(store, reward_kind="percent", reward_amount=20, offer_expires_at=NOW + 3 * DAY)

    log = SendLogStore(store)
    first = asyncio.run(log.mark_redeemed(T, "snd_1", redeemed_by="order:ord_1", now=NOW))
    second = asyncio.run(log.mark_redeemed(T, "snd_1", redeemed_by="order:ord_1", now=NOW + 10))
    assert first is True and second is True


def test_a_second_different_order_cannot_redeem_the_same_row():
    """Two different consumers racing for one single-use discount — only the first wins."""
    store = MemoryDataStore()
    _log(store, reward_kind="percent", reward_amount=20, offer_expires_at=NOW + 3 * DAY)

    log = SendLogStore(store)
    first = asyncio.run(log.mark_redeemed(T, "snd_1", redeemed_by="order:ord_1", now=NOW))
    second = asyncio.run(log.mark_redeemed(T, "snd_1", redeemed_by="order:ord_2", now=NOW + 1))
    assert first is True and second is False


def test_redeeming_a_row_that_does_not_exist_fails_softly():
    store = MemoryDataStore()
    ok = asyncio.run(SendLogStore(store).mark_redeemed(T, "nope", redeemed_by="order:ord_1",
                                                       now=NOW))
    assert ok is False
