"""HttpSender.send_carousel — Phase 2's carousel shape (core/shape.py): one card per covered
service, its own photo turned into a Meta media id, posted to notification-service's carousel
route. Same two-step whatsapp-assistant's own CarouselSender already performs for its catalog
carousel — nothing new on either peer's side, only a second caller of the same routes.
"""
from __future__ import annotations

import asyncio
import json
import urllib.error
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
         carousel_response=None, recipient="+966500000000", top_variables=None,
         include_buttons=True, kind="service", branch_id="", carousel_shown_ok=True,
         wire_carousel_shown=True):
    """A sender whose image fetch, media upload and carousel POST all succeed by default —
    override any one to prove the graceful-degradation path around it."""
    s = sender(whatsapp_assistant_url="http://wa-assistant" if wire_carousel_shown else "",
              carousel_shown_path="/internal/carousel-shown" if wire_carousel_shown else "")
    calls: dict = {"images": [], "uploads": [], "carousel_body": None, "carousel_shown_body": None}

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
        if "/carousel" in url:
            calls["carousel_body"] = json.loads(req.data or b"{}")
            return _Resp(carousel_response or {"status": "sent", "delivery_id": "dlv_c1"})
        raise AssertionError(f"unexpected URL {url}")

    with patch.object(s, "_recipient", return_value=(recipient, "نورة")), \
         patch("urllib.request.urlopen", _urlopen):
        result = run(s.send_carousel(
            tenant="t1", subject_ref="sub_a", template_name="mkt_offer_carousel_warm",
            variables=["20%"], service_ids=list(service_ids),
            service_names={"oil": "غسيل خارجي", "tyres": "تلميع"}, idempotency_key="cmp:c1:sub_a",
            top_variables=top_variables, include_buttons=include_buttons, kind=kind,
            branch_id=branch_id))
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


# ── `include_buttons` (2026-09-13) — a button only where something would answer it ─────────────
def test_by_default_every_card_carries_its_quick_reply_button():
    _, calls = _wire()
    cards = calls["carousel_body"]["cards"]
    assert cards[0]["buttons"] == [{"sub_type": "quick_reply", "payload": "carousel:service:oil"}]
    assert cards[1]["buttons"] == [{"sub_type": "quick_reply", "payload": "carousel:service:tyres"}]


def test_include_buttons_false_omits_the_key_entirely_on_every_card():
    """Not an empty list — the key itself is absent, same "no meaningless field" rule the rest of
    this wire body already follows (flow_token, carousel)."""
    _, calls = _wire(include_buttons=False)
    for card in calls["carousel_body"]["cards"]:
        assert "buttons" not in card


def test_include_buttons_does_not_change_which_cards_survive_or_their_media():
    """The switch only ever removes the button — a shop with neither app still gets the exact
    same photo, name and count of cards, never a degraded carousel."""
    with_buttons, _ = _wire(include_buttons=True)
    without_buttons, _ = _wire(include_buttons=False)
    assert with_buttons == without_buttons


# ── `kind` (2026-09-13) — package_offer names PACKAGE ids in the same field ────────────────────
def test_kind_defaults_to_service_in_both_the_photo_fetch_and_the_button_payload():
    _, calls = _wire()
    assert all("/catalogue/service/" in u for u in calls["images"])
    cards = calls["carousel_body"]["cards"]
    assert cards[0]["buttons"][0]["payload"] == "carousel:service:oil"


def test_kind_package_reaches_both_the_photo_fetch_and_the_button_payload():
    _, calls = _wire(kind="package", service_ids=("pkg1", "pkg2"))
    assert all("/catalogue/package/" in u for u in calls["images"])
    cards = calls["carousel_body"]["cards"]
    assert cards[0]["buttons"][0]["payload"] == "carousel:package:pkg1"
    assert cards[1]["buttons"][0]["payload"] == "carousel:package:pkg2"


# ── `_register_carousel_shown` (2026-09-13) — tells the bot which cards this send just showed ──
def test_a_button_bearing_send_registers_every_surviving_card_id():
    _, calls = _wire(include_buttons=True, branch_id="br_1")
    assert calls["carousel_shown_body"] == {
        "tenant": "t1", "subject_ref": "sub_a", "item_ids": ["oil", "tyres"], "branch_id": "br_1"}


def test_a_buttonless_send_never_registers_anything():
    """Nothing to bind a tap against when there is no button to tap — the registration call would
    be pure noise."""
    _, calls = _wire(include_buttons=False)
    assert calls["carousel_shown_body"] is None


def test_not_configured_at_all_is_silently_skipped():
    """No `WHATSAPP_ASSISTANT_SERVICE_URL` wired — the ordinary case for a deployment that has
    not turned this on yet — costs the send nothing; it still ships exactly as before."""
    result, calls = _wire(include_buttons=True, wire_carousel_shown=False)
    assert result == "dlv_c1"
    assert calls["carousel_shown_body"] is None


def test_a_registration_failure_never_fails_the_carousel_send_itself():
    result, calls = _wire(include_buttons=True, carousel_shown_ok=False)
    assert result == "dlv_c1"
    assert len(calls["carousel_body"]["cards"]) == 2
    for card in calls["carousel_body"]["cards"]:
        assert "buttons" in card


def test_the_top_level_body_carries_whatever_the_caller_rendered():
    """The shared intro (name/shop/end-date/stop-link, seeded 2026-09-12) is rendered by the
    CALLER (tick.py, through the same `render()` the flat message uses) and handed down as
    `top_variables` — this adapter only carries it, it does not compose it. A caller that never
    resolved one (or a template that declares none, like `wa_catalog_carousel`) still gets `[]`."""
    _, calls = _wire()
    assert calls["carousel_body"]["variables"] == []

    _, calls_with_top = _wire(top_variables=["محمد", "مغسلة النخيل", "12 سبتمبر", "https://x/stop"])
    assert calls_with_top["carousel_body"]["variables"] == [
        "محمد", "مغسلة النخيل", "12 سبتمبر", "https://x/stop"]


def test_idempotency_key_rides_both_the_key_and_the_callback_data():
    _, calls = _wire()
    assert calls["carousel_body"]["idempotency_key"] == "cmp:c1:sub_a"
    assert calls["carousel_body"]["biz_opaque_callback_data"] == "cmp:c1:sub_a"


# ── graceful degradation — a missing photo gets the placeholder, never drops the card ─────────
def test_a_service_with_no_photo_still_gets_a_card_via_the_placeholder():
    _, calls = _wire(service_ids=("oil", "tyres", "filters"), image_ok=False)
    # None of the three has a real photo — every one still becomes a card, uploaded like any
    # other, because `_fetch_service_image` returning None now means "use the placeholder", not
    # "drop the card".
    assert len(calls["carousel_body"]["cards"]) == 3


def test_a_mix_of_real_and_missing_photos_all_survive():
    s = sender()
    calls: dict = {"uploads": []}

    def _urlopen(req, timeout=0):
        url = req.full_url
        if "/catalogue/" in url:
            # only "oil" has a real photo — "tyres" and "filters" both 404
            return _Resp(data=b"realjpeg") if "oil" in url else _Resp(status=404)
        if "/media/upload-id" in url:
            body = json.loads(req.data or b"{}")
            calls["uploads"].append(body)
            return _Resp({"media_id": f"mid_{len(calls['uploads'])}"})
        return _Resp({"status": "sent", "delivery_id": "dlv_c1"})

    with patch.object(s, "_recipient", return_value=("+966500000000", "")), \
         patch("urllib.request.urlopen", _urlopen):
        result = run(s.send_carousel(tenant="t1", subject_ref="sub_a", template_name="x",
                                     variables=[], service_ids=["oil", "tyres", "filters"],
                                     service_names={}, idempotency_key="k1"))
    assert result == "dlv_c1"
    assert len(calls["uploads"]) == 3
    # the two placeholder cards uploaded the exact same base64 payload — not a per-card asset
    assert calls["uploads"][1]["data_base64"] == calls["uploads"][2]["data_base64"]
    assert calls["uploads"][0]["data_base64"] != calls["uploads"][1]["data_base64"]


def test_no_services_at_all_raises_carousel_unavailable():
    s = sender()
    with patch.object(s, "_recipient", return_value=("+966500000000", "")):
        with pytest.raises(CarouselUnavailable):
            run(s.send_carousel(tenant="t1", subject_ref="sub_a", template_name="x",
                                variables=[], service_ids=[], service_names={},
                                idempotency_key="k1"))


def test_an_upload_failure_drops_that_card_alone_even_for_a_real_photo():
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


def test_fewer_than_two_surviving_uploads_raises_carousel_unavailable_not_sendfailed():
    """Missing photos no longer threaten the floor — a run of upload failures still can."""
    s = sender()
    with patch.object(s, "_recipient", return_value=("+966500000000", "")), \
         patch("urllib.request.urlopen") as m:
        def _urlopen(req, timeout=0):
            url = req.full_url
            if "/catalogue/" in url:
                return _Resp(status=404)
            if "/media/upload-id" in url:
                return _Resp({"detail": "nope"}, status=400)
            raise AssertionError(f"unexpected URL {url}")
        m.side_effect = _urlopen
        with pytest.raises(CarouselUnavailable):
            run(s.send_carousel(tenant="t1", subject_ref="sub_a", template_name="x",
                                variables=[], service_ids=["oil", "tyres"],
                                service_names={}, idempotency_key="k1"))


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
    assert s.sent[0]["include_buttons"] is True
