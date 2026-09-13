"""HttpSender.send's own button_item_id/button_kind (2026-09-13) — the unified real-booking button,
the same "carousel:{kind}:{id}" quick-reply payload a carousel card's own button carries, now
available on a plain (non-carousel, non-media) send too.
"""
from __future__ import annotations

import asyncio
import json
import urllib.error
from unittest.mock import patch

from app.adapters.message_sender import HttpSender, NullSender


def run(c):
    return asyncio.run(c)


class _Resp:
    def __init__(self, payload, status=200):
        self._p = json.dumps(payload).encode()
        self.status = status

    def read(self):
        return self._p

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def _call(*, wire_carousel_shown=True, carousel_shown_ok=True, **over):
    s = HttpSender(notify_url="http://notify", notify_path="/internal/notify",
                   operations_url="http://ops", recipient_path="/internal/recipient", token="t",
                   whatsapp_assistant_url="http://wa-assistant" if wire_carousel_shown else "",
                   carousel_shown_path="/internal/carousel-shown" if wire_carousel_shown else "")
    calls: dict = {"notify_body": None, "carousel_shown_body": None}

    def _urlopen(req, timeout=0):
        url = req.full_url
        if "/carousel-shown" in url:
            if not carousel_shown_ok:
                raise urllib.error.URLError("carousel-shown peer is down")
            calls["carousel_shown_body"] = json.loads(req.data or b"{}")
            return _Resp({"ok": True})
        calls["notify_body"] = json.loads(req.data or b"{}")
        return _Resp({"status": "sent", "delivery_id": "dlv_1"})

    kwargs = dict(tenant="t1", subject_ref="sub_a", template_name="mkt_offer_warm",
                 variables=["أحمد", "20%"], cls="marketing", idempotency_key="k1")
    kwargs.update(over)
    with patch.object(s, "_recipient", return_value=("+966500000000", "أحمد")), \
         patch("urllib.request.urlopen", _urlopen):
        run(s.send(**kwargs))
    return calls


def test_no_button_item_id_means_no_button_payload_key_at_all():
    calls = _call()
    assert "button_payload" not in calls["notify_body"]
    assert calls["carousel_shown_body"] is None


def test_a_button_item_id_carries_the_unified_payload():
    calls = _call(button_item_id="svc1", button_kind="service")
    assert calls["notify_body"]["button_payload"] == "carousel:service:svc1"


def test_button_kind_package_is_carried_too():
    calls = _call(button_item_id="pkg1", button_kind="package")
    assert calls["notify_body"]["button_payload"] == "carousel:package:pkg1"


def test_a_button_item_id_registers_the_id_as_shown():
    calls = _call(button_item_id="svc1", branch_id="br1")
    assert calls["carousel_shown_body"] == {
        "tenant": "t1", "subject_ref": "sub_a", "item_ids": ["svc1"], "branch_id": "br1"}


def test_a_registration_failure_never_fails_the_send_itself():
    calls = _call(button_item_id="svc1", carousel_shown_ok=False)
    assert calls["notify_body"]["button_payload"] == "carousel:service:svc1"


def test_not_configured_at_all_is_silently_skipped():
    calls = _call(button_item_id="svc1", wire_carousel_shown=False)
    assert calls["carousel_shown_body"] is None


def test_null_sender_records_the_button_fields_too():
    s = NullSender()
    run(s.send(tenant="t1", subject_ref="sub_a", template_name="x", variables=[], cls="service",
              idempotency_key="k1", button_item_id="svc1", button_kind="package",
              branch_id="br1"))
    assert s.sent[0]["button_item_id"] == "svc1"
    assert s.sent[0]["button_kind"] == "package"
    assert s.sent[0]["branch_id"] == "br1"


def test_null_sender_defaults_to_no_button():
    s = NullSender()
    run(s.send(tenant="t1", subject_ref="sub_a", template_name="x", variables=[], cls="service",
              idempotency_key="k1"))
    assert s.sent[0]["button_item_id"] == ""
    assert s.sent[0]["button_kind"] == "service"
    assert s.sent[0]["branch_id"] == ""
