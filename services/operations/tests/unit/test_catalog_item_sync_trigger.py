"""core/catalog_item_sync_trigger.py — the operations-side leg that fires whatsapp-assistant's
own Meta Commerce Catalog item sync on a service create/update/image-upload."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field

from app.core.catalog_item_sync_trigger import CatalogItemSyncTrigger


def run(c):
    return asyncio.run(c)


@dataclass
class _FakeService:
    id: str = "srv1"
    name: str = "Haircut"
    description: str = "A trim"
    price_minor: int = 5000
    active: bool = True
    public_image_token: str = ""


def test_unconfigured_returns_false_never_raises():
    trigger = CatalogItemSyncTrigger(
        base_url="", path="/x", token="t", public_base_url="https://raje3.sa")
    assert trigger.configured is False
    out = run(trigger.sync(tenant="t1", service=_FakeService()))
    assert out is False


def test_configured_posts_all_fields_and_reads_ok(monkeypatch):
    calls: list[dict] = []

    def _fake_post_json(url, body, token, timeout, **_kw):
        calls.append({"url": url, "body": body, "token": token, "timeout": timeout})
        return {"ok": True, "synced": True}

    import app.core.catalog_item_sync_trigger as mod

    monkeypatch.setattr(mod.internal_http, "post_json", _fake_post_json)

    trigger = CatalogItemSyncTrigger(
        base_url="http://whatsapp-assistant:8000",
        path="/internal/whatsapp/catalog/sync-item", token="tok",
        public_base_url="https://raje3.sa")
    out = run(trigger.sync(tenant="t1", service=_FakeService(public_image_token="tok123")))

    assert out is True
    assert len(calls) == 1
    assert calls[0]["url"] == "http://whatsapp-assistant:8000/internal/whatsapp/catalog/sync-item"
    assert calls[0]["body"] == {
        "tenant": "t1", "service_id": "srv1", "name": "Haircut", "description": "A trim",
        "price_minor": 5000, "active": True,
        "image_url": "https://raje3.sa/api/v1/public_catalog/tok123",
    }
    assert calls[0]["token"] == "tok"


def test_no_public_image_token_sends_empty_image_url(monkeypatch):
    calls: list[dict] = []

    def _fake_post_json(url, body, token, timeout, **_kw):
        calls.append(body)
        return {"ok": True}

    import app.core.catalog_item_sync_trigger as mod

    monkeypatch.setattr(mod.internal_http, "post_json", _fake_post_json)

    trigger = CatalogItemSyncTrigger(
        base_url="http://whatsapp-assistant:8000", path="/x", token="t",
        public_base_url="https://raje3.sa")
    run(trigger.sync(tenant="t1", service=_FakeService(public_image_token="")))

    assert calls[0]["image_url"] == ""


def test_no_public_base_url_sends_empty_image_url_even_with_a_token(monkeypatch):
    """A deployment that never set PUBLIC_BASE_URL must never build a relative/broken URL."""
    calls: list[dict] = []

    def _fake_post_json(url, body, token, timeout, **_kw):
        calls.append(body)
        return {"ok": True}

    import app.core.catalog_item_sync_trigger as mod

    monkeypatch.setattr(mod.internal_http, "post_json", _fake_post_json)

    trigger = CatalogItemSyncTrigger(
        base_url="http://whatsapp-assistant:8000", path="/x", token="t", public_base_url="")
    run(trigger.sync(tenant="t1", service=_FakeService(public_image_token="tok123")))

    assert calls[0]["image_url"] == ""


def test_a_falsy_ok_in_the_response_reports_false():
    import app.core.catalog_item_sync_trigger as mod

    def _fake_post_json(url, body, token, timeout, **_kw):
        return {"ok": False, "failed_step": "no_catalog"}

    trigger = CatalogItemSyncTrigger(
        base_url="http://whatsapp-assistant:8000", path="/x", token="t",
        public_base_url="https://raje3.sa")
    mod.internal_http.post_json = _fake_post_json
    out = run(trigger.sync(tenant="t1", service=_FakeService()))
    assert out is False


def test_a_transport_failure_reports_false_never_raises(monkeypatch):
    import app.core.catalog_item_sync_trigger as mod

    def _raise(*_a, **_kw):
        raise RuntimeError("connection refused")

    monkeypatch.setattr(mod.internal_http, "post_json", _raise)

    trigger = CatalogItemSyncTrigger(
        base_url="http://whatsapp-assistant:8000", path="/x", token="t",
        public_base_url="https://raje3.sa")
    out = run(trigger.sync(tenant="t1", service=_FakeService()))
    assert out is False
