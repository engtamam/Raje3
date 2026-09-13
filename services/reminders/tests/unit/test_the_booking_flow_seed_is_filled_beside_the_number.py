"""The booking Flow's `customer` seed — declared by the caller, filled here, held nowhere.

WHY IT CANNOT BE FILLED ANYWHERE ELSE. The Flow is keyed on the customer's own phone number (that
is the identity every op in whatsapp-assistant's FlowBookingBackend reads), and neither campaigns
nor this service holds one: the pseudonym is the whole design. The number exists for the length of
ONE call, in the sender, beside the name — so the seed is filled exactly where the greeting is,
under exactly the same rule: only over a blank, never over a value a caller supplied.

AND THE WEEKLY REPORT MUST NOT NOTICE. insights' own Flow declares no `customer` key, so the fill
has nothing to touch there — asserted below rather than assumed, because "it happens not to match"
is a property that a later key called `customer` would silently break.
"""
from __future__ import annotations

import asyncio
import json

import pytest

from app.adapters.message_sender import HttpSender

RECIPIENT = "+966500000001"


def run(c):
    return asyncio.run(c)


@pytest.fixture()
def sender(monkeypatch):
    """A real HttpSender with both peers faked: operations answers the recipient lookup, and
    notification-service records the payload it was handed."""
    s = HttpSender(notify_url="http://notify.invalid", notify_path="/internal/notify",
                   operations_url="http://ops.invalid", recipient_path="/internal/recipient",
                   token="t" * 40)
    sent: dict = {}

    def _fake_send(url, *, timeout, method, body, content_type, token):
        sent.update(json.loads(body))
        return 200, b'{"status": "sent", "delivery_id": "dlv_1"}'

    def _fake_read(url, timeout, *, method, body, content_type, token):
        return json.dumps({"recipient": RECIPIENT, "name": "محمد"}).encode()

    from app.adapters import internal_http

    monkeypatch.setattr(internal_http, "send", _fake_send)
    monkeypatch.setattr(internal_http, "read", _fake_read)
    s.sent = sent                                                     # type: ignore[attr-defined]
    return s


def _send(s, **kw):
    run(s.send(tenant="t1", subject_ref="sub_" + "a" * 24, template_name="mkt_winback_warm",
               variables=["", "مغسلة النخيل", "20%", "12 سبتمبر", "https://x"],
               cls="marketing", idempotency_key="cmp:c1:sub_a", **kw))
    return s.sent                                                     # type: ignore[attr-defined]


def test_the_declared_but_empty_seed_is_filled_with_the_resolved_number(sender):
    payload = _send(sender, flow_token="cmp:c1:sub_a", flow_action_data={"customer": ""})

    assert payload["flow_action_data"] == {"customer": RECIPIENT}, (
        "the Flow cannot say who is asking without it, and this is the only place the number "
        "exists at all")


def test_a_seed_the_caller_actually_supplied_is_never_overruled(sender):
    """Same rule as the greeting a few lines above it: this fills a blank, it does not decide."""
    payload = _send(sender, flow_token="cmp:c1:sub_a",
                    flow_action_data={"customer": "+966555555555"})

    assert payload["flow_action_data"] == {"customer": "+966555555555"}


def test_a_flow_that_declares_no_customer_key_is_left_exactly_as_it_arrived(sender):
    """A Flow with its own data shape and no `customer` key at all — nothing here may reach
    into it."""
    payload = _send(sender, flow_token="reminders:rating:t1:sub_a:2900",
                    flow_action_data={"header_text": "زيارتك", "show_visits": True})

    assert payload["flow_action_data"] == {"header_text": "زيارتك", "show_visits": True}
    assert "customer" not in payload["flow_action_data"]


def test_an_ordinary_send_grows_neither_key(sender):
    """Every message this product sends today. A `flow_token: ""` on all of them would be a wire
    field with no meaning, forever."""
    payload = _send(sender)

    assert "flow_token" not in payload and "flow_action_data" not in payload
