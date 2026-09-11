"""Automatic جهات الاتصال registration over WhatsApp stays OFF until the owner opts in — writing a
customer row for every stranger who ever messages the shop's number is a real data-collection
decision, not a UI preference. See core/whatsapp_auto_register.py's own docstring.
"""
from __future__ import annotations

import asyncio

from app.core import whatsapp_auto_register as WAR


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


def test_a_shop_that_never_opted_in_stays_off():
    """Absent means off, and every shop is absent until its owner acts."""
    store = _Store()
    assert run(WAR.WhatsAppAutoRegisterFlagStore(store).enabled("t1")) is False


def test_the_owner_can_turn_it_on():
    store = _Store()
    run(WAR.WhatsAppAutoRegisterFlagStore(store).set("t1", True))
    assert run(WAR.WhatsAppAutoRegisterFlagStore(store).enabled("t1")) is True


def test_turning_it_back_off_is_a_real_answer_stored_as_one():
    store = _Store()
    run(WAR.WhatsAppAutoRegisterFlagStore(store).set("t1", True))
    run(WAR.WhatsAppAutoRegisterFlagStore(store).set("t1", False))
    assert run(WAR.WhatsAppAutoRegisterFlagStore(store).enabled("t1")) is False
    assert store.rows[(WAR.WHATSAPP_AUTO_REGISTER_FLAG, "t1")]["enabled"] is False, (
        "the row must SAY off, not vanish — the two are different facts"
    )


def test_one_shops_answer_is_not_anothers():
    store = _Store()
    run(WAR.WhatsAppAutoRegisterFlagStore(store).set("t1", True))
    assert run(WAR.WhatsAppAutoRegisterFlagStore(store).enabled("t2")) is False


def test_an_unreadable_row_fails_toward_off_never_widening_the_surface():
    """The two mistakes are not equal here more than anywhere else in this codebase: reading
    "unknown" as "on" would quietly register a stranger's phone as a real customer."""
    assert run(WAR.WhatsAppAutoRegisterFlagStore(_Unreadable()).enabled("t1")) is False


def test_a_missing_tenant_is_never_opted_in():
    assert run(WAR.WhatsAppAutoRegisterFlagStore(_Store()).enabled("")) is False
