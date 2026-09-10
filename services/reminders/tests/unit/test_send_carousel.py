"""HttpSender.send_carousel — Phase 2's carousel shape (core/shape.py): one card per covered
service, its own photo turned into a Meta media id, posted to notification-service's carousel
route. Same two-step whatsapp-assistant's own CarouselSender already performs for its catalog
carousel — nothing new on either peer's side, only a second caller of the same routes.
"""
from __future__ import annotations

import asyncio
import json
from unittest.mock import patch

import pytest

from app.adapters.message_sender import (CarouselUnavailable, CeilingReached, HttpSender,
                                         NullSender, SendFailed, Unsendable)


def run(c):
    return asyncio.run(c)


def sender(**over):
    kwargs = dict(notify_url="http://notify", notify_path="/internal/notify",
                  operations_url="http://ops", recipient_path="/internal/recipient", token="t",
                  carousel_send_path="/internal/notify/whatsapp/carousel",
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


def _wire(*, service_ids=("oil", "tyres"), image_ok=True, upload_ok=True,
         carousel_response=None, recipient="+966500000000"):
    """A sender whose image fetch, media upload and carousel POST all succeed by default —
    override any one to prove the graceful-degradation path around it."""
    s = sender()
    calls: dict = {"images": [], "uploads": [], "carousel_body": None}

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
        if "/carousel" in url:
            calls["carousel_body"] = json.loads(req.data or b"{}")
            return _Resp(carousel_response or {"status": "sent", "delivery_id": "dlv_c1"})
        raise AssertionError(f"unexpected URL {url}")

    with patch.object(s, "_recipient", return_value=(recipient, "نورة")), \
         patch("urllib.request.urlopen", _urlopen):
        result = run(s.send_carousel(
            tenant="t1", subject_ref="sub_a", template_name="mkt_offer_carousel_warm",
            variables=["20%"], service_ids=list(service_ids),
            service_names={"oil": "غسيل خارجي", "tyres": "تلميع"}, idempotency_key="cmp:c1:sub_a"))
    return result, calls


# ── the happy path ─────────────────────────────────────────────────────────────────────────────
def test_builds_one_card_per_service_with_a_real_media_id():
    result, calls = _wire()
    assert result == "dlv_c1"
    body = calls["carousel_body"]
    assert body["recipient"] == "+966500000000"
    assert body["template_name"] == "mkt_offer_carousel_warm"
    assert len(body["cards"]) == 2
    assert body["cards"][0]["media_id"] == "mid_1"
    assert body["cards"][0]["media_type"] == "image"


def test_each_card_carries_its_own_service_name_then_the_shared_variables():
    _, calls = _wire()
    names = [c["body_params"] for c in calls["carousel_body"]["cards"]]
    assert names == [["غسيل خارجي", "20%"], ["تلميع", "20%"]]


def test_the_top_level_body_carries_no_variables():
    """The carousel row's own top-level caption is static — see the seed's `mkt_offer_carousel_*`
    rows — so nothing here needs a customer-name substitution the flat `send()` performs."""
    _, calls = _wire()
    assert calls["carousel_body"]["variables"] == []


def test_idempotency_key_rides_both_the_key_and_the_callback_data():
    _, calls = _wire()
    assert calls["carousel_body"]["idempotency_key"] == "cmp:c1:sub_a"
    assert calls["carousel_body"]["biz_opaque_callback_data"] == "cmp:c1:sub_a"


# ── graceful degradation — a missing photo drops the card, never the send ────────────────────
def test_a_service_with_no_photo_is_dropped_not_fatal():
    _, calls = _wire(service_ids=("oil", "tyres", "filters"), image_ok=True)
    # `filters` has no NAMES entry either, but that alone does not drop it — only a failed fetch
    # does. All three fetch fine here, so all three cards survive.
    assert len(calls["carousel_body"]["cards"]) == 3


def test_fewer_than_two_surviving_cards_raises_carousel_unavailable_not_sendfailed():
    s = sender()
    with patch.object(s, "_recipient", return_value=("+966500000000", "")), \
         patch("urllib.request.urlopen", return_value=_Resp(status=404)):
        with pytest.raises(CarouselUnavailable):
            run(s.send_carousel(tenant="t1", subject_ref="sub_a", template_name="x",
                                variables=[], service_ids=["oil", "tyres"],
                                service_names={}, idempotency_key="k1"))


def test_no_services_at_all_raises_carousel_unavailable():
    s = sender()
    with patch.object(s, "_recipient", return_value=("+966500000000", "")):
        with pytest.raises(CarouselUnavailable):
            run(s.send_carousel(tenant="t1", subject_ref="sub_a", template_name="x",
                                variables=[], service_ids=[], service_names={},
                                idempotency_key="k1"))


def test_an_upload_failure_drops_that_card_alone():
    """Two of three uploads succeed — still >= Meta's own carousel minimum, so the send goes out
    with the two surviving cards rather than being refused over the one that failed."""
    s = sender()
    uploads = {"n": 0}

    def _urlopen(req, timeout=0):
        url = req.full_url
        if "/catalogue/" in url:
            return _Resp(data=b"fakejpeg")
        if "/media/upload-id" in url:
            uploads["n"] += 1
            if uploads["n"] == 1:
                return _Resp({"detail": "nope"}, status=400)
            return _Resp({"media_id": "mid_ok"})
        return _Resp({"status": "sent", "delivery_id": "dlv_c1"})

    with patch.object(s, "_recipient", return_value=("+966500000000", "")), \
         patch("urllib.request.urlopen", _urlopen):
        result = run(s.send_carousel(tenant="t1", subject_ref="sub_a", template_name="x",
                                     variables=[], service_ids=["oil", "tyres", "filters"],
                                     service_names={}, idempotency_key="k1"))
    assert result == "dlv_c1"


# ── recipient resolution and configuration — same rules as send()/send_flow() ─────────────────
def test_an_erased_or_unknown_customer_raises_unsendable():
    s = sender()
    with patch.object(s, "_recipient", return_value=("", "")):
        with pytest.raises(Unsendable):
            run(s.send_carousel(tenant="t1", subject_ref="gone", template_name="x",
                                variables=[], service_ids=["oil", "tyres"], service_names={},
                                idempotency_key="k1"))


def test_not_configured_at_all_refuses_before_any_call():
    s = sender(carousel_send_path="", media_upload_id_path="", catalogue_image_path="")
    with patch("urllib.request.urlopen") as m:
        with pytest.raises(CarouselUnavailable):
            run(s.send_carousel(tenant="t1", subject_ref="sub_a", template_name="x",
                                variables=[], service_ids=["oil", "tyres"], service_names={},
                                idempotency_key="k1"))
        m.assert_not_called()


def test_a_ceiling_code_is_ceilingreached():
    with pytest.raises(CeilingReached):
        _wire(carousel_response={"status": "failed", "error_code": "130429"})


def test_a_delivery_status_of_failed_is_sendfailed():
    with pytest.raises(SendFailed):
        _wire(carousel_response={"status": "failed", "error": "template not approved"})


# ── the null sender ────────────────────────────────────────────────────────────────────────────
def test_null_sender_records_the_carousel_call_and_returns_a_stable_handle():
    s = NullSender()
    result = run(s.send_carousel(tenant="t1", subject_ref="sub_a",
                                 template_name="mkt_offer_carousel_warm", variables=["20%"],
                                 service_ids=["oil"], service_names={"oil": "غسيل"},
                                 idempotency_key="k1"))
    assert result == "dlv_k1"
    assert s.sent[0]["type"] == "carousel"
    assert s.sent[0]["service_ids"] == ["oil"]
