"""One shop's own connected WhatsApp number (platform v0.19.9): two-step PIN set/rotate,
subscribed webhook fields, business verification, and messaging-limit tier."""
from __future__ import annotations

import asyncio

from app.adapters.whatsapp_admin import WhatsAppAdmin


def run(c):
    return asyncio.run(c)


def test_unconfigured_answers_none_not_a_fabricated_success():
    adapter = WhatsAppAdmin(base_url="", token="tok")
    assert adapter.configured is False
    assert run(adapter.set_two_step_pin(tenant="t1", phone_number_id="", pin="123456")) is None
    assert run(adapter.subscribed_fields("t1")) is None
    assert run(adapter.business_verification("t1")) is None
    assert run(adapter.messaging_limit("t1")) is None


def test_unreachable_peer_answers_none_for_every_method():
    adapter = WhatsAppAdmin(base_url="http://127.0.0.1:1", token="tok", timeout=1)
    assert run(adapter.set_two_step_pin(tenant="t1", phone_number_id="p1", pin="123456")) is None
    assert run(adapter.subscribed_fields("t1")) is None
    assert run(adapter.business_verification("t1")) is None
    assert run(adapter.messaging_limit("t1")) is None
