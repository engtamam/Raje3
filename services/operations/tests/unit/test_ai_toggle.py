"""The owner's own kill switch for the WhatsApp AI assistant — separate from the subscription
(`feature.whatsapp`), enforced on whatsapp-assistant's own side by wrapping its licence check
(core/licence.py::ToggleGatedLicence there). This file covers only the store this service owns:
absent means on, and a written value round-trips per tenant.
"""
from __future__ import annotations

import asyncio

from app.core import ai_toggle as AT


def run(coro):
    return asyncio.run(coro)


class _Store:
    def __init__(self, rows=None):
        self.rows = dict(rows or {})

    async def get(self, collection, key):
        return self.rows.get((collection, key))

    async def put(self, collection, key, row):
        self.rows[(collection, key)] = row


class _Unreadable(_Store):
    async def get(self, collection, key):
        raise RuntimeError("the datastore is down")


def test_a_shop_that_never_touched_it_reads_back_enabled():
    assert run(AT.AiToggleStore(_Store()).get("t1")) is True


def test_switching_off_then_reading_round_trips():
    store = _Store()
    run(AT.AiToggleStore(store).set("t1", False))
    assert run(AT.AiToggleStore(store).get("t1")) is False


def test_switching_it_back_on_round_trips_too_no_one_way_ratchet():
    store = _Store()
    run(AT.AiToggleStore(store).set("t1", False))
    run(AT.AiToggleStore(store).set("t1", True))
    assert run(AT.AiToggleStore(store).get("t1")) is True


def test_one_shops_switch_is_not_another_shops():
    store = _Store()
    run(AT.AiToggleStore(store).set("t1", False))
    assert run(AT.AiToggleStore(store).get("t2")) is True


def test_an_unreadable_row_reads_back_enabled_rather_than_silently_going_off():
    """Fail open — the SAME asymmetry `AiNotesStore.get` takes in the other direction: an outage
    must not silently switch a shop's assistant off underneath it."""
    assert run(AT.AiToggleStore(_Unreadable()).get("t1")) is True


def test_a_missing_tenant_reads_back_enabled():
    assert run(AT.AiToggleStore(_Store()).get("")) is True
