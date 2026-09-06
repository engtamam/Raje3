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
