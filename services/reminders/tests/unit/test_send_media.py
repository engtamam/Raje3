"""HttpSender.send_media — the "one item, no carousel" shape (2026-09-13). Meta's own carousel
minimum is two cards (core/shape.py's own note), so a single covered service/package gets its own
real photo as a plain template's header instead of a card — the same fetch-photo -> upload -> send
two-step `send_carousel` already performs per card, here for the message's own single header.
"""
from __future__ import annotations

import asyncio
import json
import urllib.error
from unittest.mock import patch

import pytest

from app.adapters.message_sender import HttpSender, SendFailed, Unsendable


def run(c):
    return asyncio.run(c)


def sender(**over):
    kwargs = dict(notify_url="http://notify", notify_path="/internal/notify",
                  operations_url="http://ops", recipient_path="/internal/recipient", token="t",
                  media_upload_id_path="/internal/whatsapp/media/upload-id",
                  catalogue_image_path="/internal/operations/catalogue/{}/{}/image")
    kwargs.update(over)
    return HttpSender(**kwargs)


class _Resp:
    def __init__(self, payload=None, status=200, data=b"fakejpeg", headers=None):
        self._p = json.dumps(payload).encode() if payload is not None else data
        self.status = status
        self.headers = headers or {"Content-Type": "image/jpeg"}

    def read(self):
        return self._p

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def _wire(*, header_item_id="oil", header_kind="service", image_ok=True, upload_ok=True,
         notify_response=None, recipient="+966500000000", button_item_id="",
         button_kind="service", branch_id="", carousel_shown_ok=True, wire_carousel_shown=True,
         variables=None):
    s = sender(whatsapp_assistant_url="http://wa-assistant" if wire_carousel_shown else "",
              carousel_shown_path="/internal/carousel-shown" if wire_carousel_shown else "")
    calls: dict = {"images": [], "uploads": [], "notify_body": None, "carousel_shown_body": None}

    def _urlopen(req, timeout=0):
        url = req.full_url
        if "/catalogue/" in url:
            calls["images"].append(url)
            if not image_ok:
                return _Resp(status=404)
            return _Resp(data=b"\xff\xd8\xff\xe0fakejpeg")
        if "/media/upload-id" in url:
            body = json.loads(req.data or b"{}")
            calls["uploads"].append(body)
            if not upload_ok:
                return _Resp({"detail": "upload failed"}, status=400)
            return _Resp({"media_id": f"mid_{len(calls['uploads'])}"})
        if "/carousel-shown" in url:
            if not carousel_shown_ok:
                raise urllib.error.URLError("carousel-shown peer is down")
            calls["carousel_shown_body"] = json.loads(req.data or b"{}")
            return _Resp({"ok": True})
        if "/notify" in url:
            calls["notify_body"] = json.loads(req.data or b"{}")
            return _Resp(notify_response or {"status": "sent", "delivery_id": "dlv_m1"})
        raise AssertionError(f"unexpected URL {url}")

    with patch.object(s, "_recipient", return_value=(recipient, "نورة")), \
         patch("urllib.request.urlopen", _urlopen):
        result = run(s.send_media(
            tenant="t1", subject_ref="sub_a", template_name="mkt_offer_media_warm",
            variables=variables if variables is not None else ["", "20%"], cls="marketing",
            idempotency_key="cmp:c1:sub_a", header_item_id=header_item_id,
            header_kind=header_kind, button_item_id=button_item_id, button_kind=button_kind,
            branch_id=branch_id))
    return result, calls


# ── the happy path ─────────────────────────────────────────────────────────────────────────────
def test_sends_with_the_items_own_photo_as_a_real_media_id():
    result, calls = _wire()
    assert result == "dlv_m1"
    body = calls["notify_body"]
    assert body["recipient"] == "+966500000000"
    assert body["template_key"] == "mkt_offer_media_warm"
    assert body["header_media_id"] == "mid_1"


def test_a_missing_photo_falls_back_to_the_neutral_placeholder_not_a_refusal():
    """No uploaded photo for this item is not a reason to refuse the send — same rule the
    carousel's own placeholder follows."""
    result, calls = _wire(image_ok=False)
    assert result == "dlv_m1"
    assert calls["notify_body"]["header_media_id"] == "mid_1"


def test_a_failed_upload_refuses_the_send():
    with pytest.raises(SendFailed, match="media upload failed"):
        _wire(upload_ok=False)


def test_no_recipient_is_unsendable_not_a_retry():
    with pytest.raises(Unsendable):
        _wire(recipient="")


# ── the greeting fill, same rule send() follows ──────────────────────────────────────────────
def test_the_customers_own_name_fills_an_empty_first_slot():
    _, calls = _wire(variables=["", "20%"])
    assert calls["notify_body"]["variables"]["1"] == "نورة"


# ── kind (service vs package) ─────────────────────────────────────────────────────────────────
def test_kind_defaults_to_service_for_the_photo_fetch():
    _, calls = _wire()
    assert all("/catalogue/service/" in u for u in calls["images"])


def test_kind_package_reaches_the_photo_fetch():
    _, calls = _wire(header_kind="package", header_item_id="pkg1")
    assert all("/catalogue/package/" in u for u in calls["images"])


# ── the unified booking button (2026-09-13) ──────────────────────────────────────────────────
def test_no_button_item_id_means_no_button_payload_key_at_all():
    _, calls = _wire()
    assert "button_payload" not in calls["notify_body"]
    assert calls["carousel_shown_body"] is None


def test_a_button_item_id_carries_the_unified_payload_and_registers_it_shown():
    _, calls = _wire(button_item_id="oil", button_kind="service", branch_id="br1")
    assert calls["notify_body"]["button_payload"] == "carousel:service:oil"
    assert calls["carousel_shown_body"] == {
        "tenant": "t1", "subject_ref": "sub_a", "item_ids": ["oil"], "branch_id": "br1"}


def test_a_registration_failure_never_fails_the_send_itself():
    result, _ = _wire(button_item_id="oil", carousel_shown_ok=False)
    assert result == "dlv_m1"


def test_not_configured_at_all_is_silently_skipped():
    result, calls = _wire(button_item_id="oil", wire_carousel_shown=False)
    assert result == "dlv_m1"
    assert calls["carousel_shown_body"] is None
