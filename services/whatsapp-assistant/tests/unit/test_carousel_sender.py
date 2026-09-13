"""CarouselSender — fetch each card's photo, upload it as a Meta media id, then send the
assembled carousel. A card whose photo fails to fetch/upload is dropped, not fatal by itself;
fewer than two surviving cards raises SendFailed."""
from __future__ import annotations

import asyncio
import json
from unittest.mock import patch

import pytest

from app.adapters.whatsapp_sender.carousel import CarouselSender, SendFailed
from app.ports.catalog_provider import CatalogCard


def run(c):
    return asyncio.run(c)


def sender():
    return CarouselSender(
        notify_url="http://notification-service:8000",
        carousel_path="/internal/notify/whatsapp/carousel",
        media_upload_path="/internal/whatsapp/media/upload-id",
        interactive_path="/internal/notify/whatsapp/interactive",
        token="t", timeout=8)


class _Resp:
    def __init__(self, payload=None, body=b"", status=200, headers=None):
        self._body = json.dumps(payload).encode() if payload is not None else body
        self.status = status
        self.headers = headers or {}

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def _two_cards():
    return [
        CatalogCard(id="srv_1", kind="service", name="قص شعر", price_minor=5000,
                   image_url="http://operations:8000/image/1"),
        CatalogCard(id="pkg_1", kind="package", name="باقة", price_minor=12000,
                   image_url="http://operations:8000/image/2"),
    ]


def test_uploads_each_card_and_sends_the_assembled_carousel():
    calls = []

    def _urlopen(req, timeout=0):
        url = req.full_url
        calls.append(url)
        if url.startswith("http://operations:8000/image/"):
            return _Resp(body=b"\x89PNG...", headers={"Content-Type": "image/png"})
        if url.endswith("/internal/whatsapp/media/upload-id"):
            n = json.loads(req.data)["file_name"]
            return _Resp({"ok": True, "media_id": "mid_1" if "card.jpg" in n else "mid_2"})
        return _Resp({"status": "sent", "delivery_id": "dlv_1"})

    with patch("urllib.request.urlopen", _urlopen):
        delivery_id = run(sender().send_carousel(
            tenant="shop1", to="+9665", template_name="wa_catalog_carousel", language="ar",
            cards=_two_cards(), idempotency_key="k1"))

    assert delivery_id == "dlv_1"
    # two image fetches, two media uploads, one carousel send
    assert len([c for c in calls if "/image/" in c]) == 2
    assert len([c for c in calls if c.endswith("upload-id")]) == 2
    assert calls[-1] == "http://notification-service:8000/internal/notify/whatsapp/carousel"


def test_the_carousel_body_carries_media_ids_names_and_prices():
    def _urlopen(req, timeout=0):
        url = req.full_url
        if "/image/" in url:
            return _Resp(body=b"x", headers={"Content-Type": "image/jpeg"})
        if url.endswith("upload-id"):
            return _Resp({"ok": True, "media_id": "mid_x"})
        return _Resp({"status": "sent", "delivery_id": "dlv_2"},)

    seen = {}

    def _capture(req, timeout=0):
        if req.full_url.endswith("/internal/notify/whatsapp/carousel"):
            seen["body"] = json.loads(req.data)
        return _urlopen(req, timeout)

    with patch("urllib.request.urlopen", _capture):
        run(sender().send_carousel(
            tenant="shop1", to="+9665", template_name="wa_catalog_carousel", language="ar",
            cards=_two_cards(), idempotency_key="k1"))

    body = seen["body"]
    assert body["template_name"] == "wa_catalog_carousel"
    assert body["language"] == "ar"
    assert len(body["cards"]) == 2
    assert body["cards"][0]["media_id"] == "mid_x"
    assert body["cards"][0]["body_params"] == ["قص شعر", "50 ريال"]
    assert body["cards"][0]["buttons"] == [
        {"sub_type": "quick_reply", "payload": "carousel:service:srv_1"}]


def test_one_cards_image_fetch_failing_still_sends_with_the_rest():
    """Three cards, one bad photo — two survive, which still clears Meta's own carousel floor."""
    cards = _two_cards() + [CatalogCard(id="srv_2", kind="service", name="c", price_minor=100,
                                        image_url="http://operations:8000/image/bad")]

    def _urlopen(req, timeout=0):
        url = req.full_url
        if url.endswith("/image/bad"):
            return _Resp(status=404, body=b"")
        if "/image/" in url:
            return _Resp(body=b"x", headers={"Content-Type": "image/jpeg"})
        if url.endswith("upload-id"):
            return _Resp({"ok": True, "media_id": "mid_x"})
        return _Resp({"status": "sent", "delivery_id": "dlv_3"})

    with patch("urllib.request.urlopen", _urlopen):
        delivery_id = run(sender().send_carousel(
            tenant="shop1", to="+9665", template_name="wa_catalog_carousel", language="ar",
            cards=cards, idempotency_key="k1"))
    assert delivery_id == "dlv_3"


def test_fewer_than_two_surviving_cards_raises_send_failed():
    def _urlopen(req, timeout=0):
        url = req.full_url
        if url.endswith("/image/2"):
            return _Resp(status=404, body=b"")
        if "/image/" in url:
            return _Resp(body=b"x", headers={"Content-Type": "image/jpeg"})
        if url.endswith("upload-id"):
            return _Resp({"ok": True, "media_id": "mid_x"})
        return _Resp({"status": "sent", "delivery_id": "dlv_4"})

    with patch("urllib.request.urlopen", _urlopen):
        with pytest.raises(SendFailed):
            run(sender().send_carousel(
                tenant="shop1", to="+9665", template_name="wa_catalog_carousel", language="ar",
                cards=_two_cards(), idempotency_key="k1"))


def test_a_media_upload_failure_drops_that_card_too():
    """Every image fetch succeeds; every media-id upload fails — zero cards survive."""
    def _urlopen(req, timeout=0):
        url = req.full_url
        if "/image/" in url:
            return _Resp(body=b"x", headers={"Content-Type": "image/jpeg"})
        if url.endswith("upload-id"):
            return _Resp(status=502, body=b"")
        return _Resp({"status": "sent", "delivery_id": "dlv_5"})

    with patch("urllib.request.urlopen", _urlopen):
        with pytest.raises(SendFailed):
            run(sender().send_carousel(
                tenant="shop1", to="+9665", template_name="wa_catalog_carousel", language="ar",
                cards=_two_cards(), idempotency_key="k1"))


def test_a_non_sent_status_from_the_carousel_route_raises_send_failed():
    def _urlopen(req, timeout=0):
        url = req.full_url
        if "/image/" in url:
            return _Resp(body=b"x", headers={"Content-Type": "image/jpeg"})
        if url.endswith("upload-id"):
            return _Resp({"ok": True, "media_id": "mid_x"})
        return _Resp({"status": "queued", "delivery_id": "dlv_6"})

    with patch("urllib.request.urlopen", _urlopen):
        with pytest.raises(SendFailed, match="queued"):
            run(sender().send_carousel(
                tenant="shop1", to="+9665", template_name="wa_catalog_carousel", language="ar",
                cards=_two_cards(), idempotency_key="k1"))


# ── send_single_card — one photographed service, photo + text + one button (2026-09-13) ──────────
def _one_card():
    return CatalogCard(id="srv_1", kind="service", name="قص شعر", price_minor=5000,
                       image_url="http://operations:8000/image/1")


def test_uploads_the_one_photo_and_sends_an_interactive_button_message():
    calls = []

    def _urlopen(req, timeout=0):
        url = req.full_url
        calls.append(url)
        if url.startswith("http://operations:8000/image/"):
            return _Resp(body=b"\x89PNG...", headers={"Content-Type": "image/png"})
        if url.endswith("/internal/whatsapp/media/upload-id"):
            return _Resp({"ok": True, "media_id": "mid_1"})
        return _Resp({"status": "sent", "delivery_id": "dlv_9"})

    with patch("urllib.request.urlopen", _urlopen):
        delivery_id = run(sender().send_single_card(
            tenant="shop1", to="+9665", card=_one_card(), idempotency_key="k1"))

    assert delivery_id == "dlv_9"
    assert calls[-1] == "http://notification-service:8000/internal/notify/whatsapp/interactive"


def test_the_single_card_body_carries_the_media_id_and_one_button():
    def _urlopen(req, timeout=0):
        url = req.full_url
        if "/image/" in url:
            return _Resp(body=b"x", headers={"Content-Type": "image/jpeg"})
        if url.endswith("upload-id"):
            return _Resp({"ok": True, "media_id": "mid_x"})
        return _Resp({"status": "sent", "delivery_id": "dlv_10"})

    seen = {}

    def _capture(req, timeout=0):
        if req.full_url.endswith("/internal/notify/whatsapp/interactive"):
            seen["body"] = json.loads(req.data)
        return _urlopen(req, timeout)

    with patch("urllib.request.urlopen", _capture):
        run(sender().send_single_card(
            tenant="shop1", to="+9665", card=_one_card(), idempotency_key="k1"))

    body = seen["body"]
    assert body["type"] == "button"
    assert body["header_media_id"] == "mid_x"
    assert body["header_media_type"] == "image"
    assert "قص شعر" in body["body"] and "50 ريال" in body["body"]
    assert body["buttons"] == [{"id": "carousel:service:srv_1", "title": "احجز الآن"}]


def test_the_cards_own_image_failing_to_fetch_raises_send_failed():
    def _urlopen(req, timeout=0):
        if "/image/" in req.full_url:
            return _Resp(status=404, body=b"")
        return _Resp({"status": "sent", "delivery_id": "dlv_11"})

    with patch("urllib.request.urlopen", _urlopen):
        with pytest.raises(SendFailed):
            run(sender().send_single_card(
                tenant="shop1", to="+9665", card=_one_card(), idempotency_key="k1"))


def test_the_media_upload_failing_raises_send_failed():
    def _urlopen(req, timeout=0):
        url = req.full_url
        if "/image/" in url:
            return _Resp(body=b"x", headers={"Content-Type": "image/jpeg"})
        if url.endswith("upload-id"):
            return _Resp(status=502, body=b"")
        return _Resp({"status": "sent", "delivery_id": "dlv_12"})

    with patch("urllib.request.urlopen", _urlopen):
        with pytest.raises(SendFailed):
            run(sender().send_single_card(
                tenant="shop1", to="+9665", card=_one_card(), idempotency_key="k1"))


def test_a_non_sent_status_on_the_single_card_route_raises_send_failed():
    def _urlopen(req, timeout=0):
        url = req.full_url
        if "/image/" in url:
            return _Resp(body=b"x", headers={"Content-Type": "image/jpeg"})
        if url.endswith("upload-id"):
            return _Resp({"ok": True, "media_id": "mid_x"})
        return _Resp({"status": "queued", "delivery_id": "dlv_13"})

    with patch("urllib.request.urlopen", _urlopen):
        with pytest.raises(SendFailed, match="queued"):
            run(sender().send_single_card(
                tenant="shop1", to="+9665", card=_one_card(), idempotency_key="k1"))


def test_send_single_card_without_an_interactive_path_configured_raises_send_failed():
    """A caller that never wires interactive_path (a test double, an older config) must fail
    loudly rather than silently POST to an empty URL."""
    no_interactive = CarouselSender(
        notify_url="http://notification-service:8000",
        carousel_path="/internal/notify/whatsapp/carousel",
        media_upload_path="/internal/whatsapp/media/upload-id",
        token="t", timeout=8)
    with pytest.raises(SendFailed):
        run(no_interactive.send_single_card(
            tenant="shop1", to="+9665", card=_one_card(), idempotency_key="k1"))
