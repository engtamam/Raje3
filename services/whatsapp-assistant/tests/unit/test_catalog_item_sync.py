"""core/catalog_item_sync.py -- upsert/delete item calls, and the `sync_service_item`
orchestrator's readiness gate and hard edge cases. Stubbing follows
test_catalog_provisioning.py's own conventions."""
from __future__ import annotations

import asyncio
import urllib.error
from unittest.mock import patch

import pytest

from app.core.catalog_item_sync import (
    CatalogItemSyncError,
    HttpCatalogItemSyncer,
    NullCatalogItemSyncer,
    SyncItemResult,
    build,
    sync_service_item,
)
from app.core.catalog_provisioning import (
    SECRET_CATALOG_ID_NAME,
    SECRET_DISPLAY_PHONE_NAME,
    SECRET_TOKEN_NAME,
)


def run(c):
    return asyncio.run(c)


class _FakeSecrets:
    def __init__(self, values=None):
        self._v = dict(values or {})

    async def get(self, *, tenant, name, fallback=""):
        return self._v.get(f"{tenant}|{name}", fallback)

    async def set(self, *, tenant, name, value, actor_ref=""):
        self._v[f"{tenant}|{name}"] = value


class _Resp:
    def __init__(self, body=b"{}"):
        self._body = body

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def _settings(**kw):
    class S:
        pass
    s = S()
    s.CATALOG_PROVISIONING_ENABLED = kw.get("enabled", True)
    s.META_GRAPH_BASE_URL = "https://graph.facebook.com"
    s.META_GRAPH_API_VERSION = "v26.0"
    s.PEER_TIMEOUT_SECONDS = 8
    return s


def _http(**kw):
    return HttpCatalogItemSyncer(
        token="tok", graph_base_url="https://graph.facebook.com", graph_version="v26.0", **kw)


_FULL_SECRETS = {
    "t1|" + SECRET_TOKEN_NAME: "tok",
    "t1|" + SECRET_CATALOG_ID_NAME: "CAT1",
    "t1|" + SECRET_DISPLAY_PHONE_NAME: "+966 50 123 4567",
}


class _FakeSyncer:
    def __init__(self):
        self.calls = []

    async def upsert_item(self, catalog_id, item):
        self.calls.append(("upsert", catalog_id, item))
        return True

    async def delete_item(self, catalog_id, item_id):
        self.calls.append(("delete", catalog_id, item_id))
        return True


# ── HttpCatalogItemSyncer ─────────────────────────────────────────────────────────────────────

def test_upsert_item_sends_update_with_allow_upsert():
    captured = {}

    def _fake_urlopen(req, timeout=8):
        import json
        captured["body"] = json.loads(req.data)
        captured["url"] = req.full_url
        return _Resp(b'{"handles": ["h1"]}')

    with patch("urllib.request.urlopen", side_effect=_fake_urlopen):
        ok = run(_http().upsert_item("cat1", {"id": "svc1", "title": "Haircut"}))
    assert ok is True
    assert "cat1/items_batch" in captured["url"]
    assert captured["body"]["item_type"] == "PRODUCT_ITEM"
    req = captured["body"]["requests"][0]
    assert req["method"] == "UPDATE"
    assert req["allow_upsert"] is True
    assert req["data"] == {"id": "svc1", "title": "Haircut"}


def test_upsert_item_fails_closed_on_an_unrecognised_shape():
    # ci/check_absent_means_ok.py's own rule -- neither "handles" nor "success" present, so this
    # must read as failure, never a silent success.
    with patch("urllib.request.urlopen", return_value=_Resp(b"{}")):
        assert run(_http().upsert_item("cat1", {"id": "svc1"})) is False


def test_delete_item_fails_closed_on_an_unrecognised_shape():
    with patch("urllib.request.urlopen", return_value=_Resp(b"{}")):
        assert run(_http().delete_item("cat1", "svc1")) is False


def test_upsert_item_http_error_raises():
    err = urllib.error.HTTPError("url", 400, "bad request", {}, None)
    err.read = lambda: b"invalid price"
    with patch("urllib.request.urlopen", side_effect=err):
        with pytest.raises(CatalogItemSyncError):
            run(_http().upsert_item("cat1", {"id": "svc1"}))


def test_delete_item_sends_delete_method_with_only_id():
    captured = {}

    def _fake_urlopen(req, timeout=8):
        import json
        captured["body"] = json.loads(req.data)
        return _Resp(b'{"handles": ["h1"]}')

    with patch("urllib.request.urlopen", side_effect=_fake_urlopen):
        ok = run(_http().delete_item("cat1", "svc1"))
    assert ok is True
    req = captured["body"]["requests"][0]
    assert req["method"] == "DELETE"
    assert req["data"] == {"id": "svc1"}
    assert "allow_upsert" not in req


def test_delete_item_error_raises():
    err = urllib.error.HTTPError("url", 500, "server error", {}, None)
    err.read = lambda: b"oops"
    with patch("urllib.request.urlopen", side_effect=err):
        with pytest.raises(CatalogItemSyncError):
            run(_http().delete_item("cat1", "svc1"))


# ── NullCatalogItemSyncer / build() ───────────────────────────────────────────────────────────

def test_null_upsert_raises():
    with pytest.raises(CatalogItemSyncError):
        run(NullCatalogItemSyncer().upsert_item("cat1", {}))


def test_null_delete_returns_false():
    assert run(NullCatalogItemSyncer().delete_item("cat1", "svc1")) is False


def test_build_returns_null_when_disabled():
    assert isinstance(build(_settings(enabled=False)), NullCatalogItemSyncer)


def test_build_returns_http_when_enabled():
    assert isinstance(build(_settings(enabled=True)), HttpCatalogItemSyncer)


# ── sync_service_item orchestrator ────────────────────────────────────────────────────────────

def test_no_catalog_fails_named_without_any_graph_call():
    secrets = _FakeSecrets({"t1|" + SECRET_TOKEN_NAME: "tok"})  # no catalog id on file
    result = run(sync_service_item(
        tenant="t1", service_id="svc1", name="Haircut", description="", price_minor=5000,
        active=True, image_url="https://x/img.jpg", secret_store=secrets, settings=_settings()))
    assert result.ok is False
    assert result.failed_step == "no_catalog"


def test_no_token_fails_named():
    secrets = _FakeSecrets({"t1|" + SECRET_CATALOG_ID_NAME: "CAT1"})
    result = run(sync_service_item(
        tenant="t1", service_id="svc1", name="Haircut", description="", price_minor=5000,
        active=True, image_url="https://x/img.jpg", secret_store=secrets, settings=_settings()))
    assert result.ok is False
    assert result.failed_step == "no_catalog"


def test_ready_service_is_upserted_with_correct_fields():
    secrets = _FakeSecrets(dict(_FULL_SECRETS))
    fake = _FakeSyncer()

    result = run(sync_service_item(
        tenant="t1", service_id="svc1", name="Haircut", description="A trim", price_minor=5000,
        active=True, image_url="https://x/img.jpg", secret_store=secrets, settings=_settings(),
        shop_name="Raje3 Salon", syncer_factory=lambda tok: fake))

    assert result.ok is True
    assert result.synced is True
    assert result.removed is False
    assert len(fake.calls) == 1
    method, catalog_id, item = fake.calls[0]
    assert method == "upsert"
    assert catalog_id == "CAT1"
    assert item == {
        "id": "svc1", "title": "Haircut", "description": "A trim",
        "availability": "in stock", "condition": "new", "brand": "Raje3 Salon",
        "price": "50.00 SAR", "link": "https://wa.me/966501234567",
        "image": [{"url": "https://x/img.jpg"}],
    }


def test_ready_service_with_no_description_falls_back_to_name():
    secrets = _FakeSecrets(dict(_FULL_SECRETS))
    fake = _FakeSyncer()

    run(sync_service_item(
        tenant="t1", service_id="svc1", name="Haircut", description="", price_minor=5000,
        active=True, image_url="https://x/img.jpg", secret_store=secrets, settings=_settings(),
        syncer_factory=lambda tok: fake))

    assert fake.calls[0][2]["description"] == "Haircut"


def test_ready_service_with_no_shop_name_defaults_brand():
    secrets = _FakeSecrets(dict(_FULL_SECRETS))
    fake = _FakeSyncer()

    run(sync_service_item(
        tenant="t1", service_id="svc1", name="Haircut", description="", price_minor=5000,
        active=True, image_url="https://x/img.jpg", secret_store=secrets, settings=_settings(),
        syncer_factory=lambda tok: fake))

    assert fake.calls[0][2]["brand"] == "Raje3"


def test_inactive_service_is_deleted_not_upserted():
    secrets = _FakeSecrets(dict(_FULL_SECRETS))
    fake = _FakeSyncer()

    result = run(sync_service_item(
        tenant="t1", service_id="svc1", name="Haircut", description="", price_minor=5000,
        active=False, image_url="https://x/img.jpg", secret_store=secrets, settings=_settings(),
        syncer_factory=lambda tok: fake))

    assert result.ok is True
    assert result.removed is True
    assert result.synced is False
    assert fake.calls == [("delete", "CAT1", "svc1")]


def test_zero_price_service_is_deleted():
    """THE REAL GATE -- a service with no price set (0, our own deliberate 'optional price'
    convention) must never appear in a real commerce catalog."""
    secrets = _FakeSecrets(dict(_FULL_SECRETS))
    fake = _FakeSyncer()

    result = run(sync_service_item(
        tenant="t1", service_id="svc1", name="Haircut", description="", price_minor=0,
        active=True, image_url="https://x/img.jpg", secret_store=secrets, settings=_settings(),
        syncer_factory=lambda tok: fake))

    assert result.ok is True
    assert result.removed is True
    assert fake.calls == [("delete", "CAT1", "svc1")]


def test_no_image_service_is_deleted():
    secrets = _FakeSecrets(dict(_FULL_SECRETS))
    fake = _FakeSyncer()

    result = run(sync_service_item(
        tenant="t1", service_id="svc1", name="Haircut", description="", price_minor=5000,
        active=True, image_url="", secret_store=secrets, settings=_settings(),
        syncer_factory=lambda tok: fake))

    assert result.ok is True
    assert result.removed is True
    assert fake.calls == [("delete", "CAT1", "svc1")]


def test_ready_but_no_display_phone_refuses_rather_than_publish_a_dead_link():
    """THE EDGE CASE: a tenant finished catalog provisioning but phone resolution genuinely never
    landed (a best-effort step in catalog_provisioning.py). Must refuse named, never push a
    broken wa.me link live."""
    secrets = _FakeSecrets({
        "t1|" + SECRET_TOKEN_NAME: "tok", "t1|" + SECRET_CATALOG_ID_NAME: "CAT1"})
    fake = _FakeSyncer()

    result = run(sync_service_item(
        tenant="t1", service_id="svc1", name="Haircut", description="", price_minor=5000,
        active=True, image_url="https://x/img.jpg", secret_store=secrets, settings=_settings(),
        syncer_factory=lambda tok: fake))

    assert result.ok is False
    assert result.failed_step == "no_display_phone"
    assert fake.calls == []


def test_display_phone_digits_are_stripped_of_plus_and_spaces():
    secrets = _FakeSecrets({
        "t1|" + SECRET_TOKEN_NAME: "tok", "t1|" + SECRET_CATALOG_ID_NAME: "CAT1",
        "t1|" + SECRET_DISPLAY_PHONE_NAME: "+1 (555) 123-4567"})
    fake = _FakeSyncer()

    run(sync_service_item(
        tenant="t1", service_id="svc1", name="Haircut", description="", price_minor=5000,
        active=True, image_url="https://x/img.jpg", secret_store=secrets, settings=_settings(),
        syncer_factory=lambda tok: fake))

    assert fake.calls[0][2]["link"] == "https://wa.me/15551234567"


def test_upsert_failure_reports_named_step():
    secrets = _FakeSecrets(dict(_FULL_SECRETS))

    class _Fail:
        async def upsert_item(self, catalog_id, item):
            raise CatalogItemSyncError("upsert_item", "price malformed")

    result = run(sync_service_item(
        tenant="t1", service_id="svc1", name="Haircut", description="", price_minor=5000,
        active=True, image_url="https://x/img.jpg", secret_store=secrets, settings=_settings(),
        syncer_factory=lambda tok: _Fail()))

    assert result.ok is False
    assert result.failed_step == "upsert_item"


def test_delete_failure_reports_named_step():
    secrets = _FakeSecrets(dict(_FULL_SECRETS))

    class _Fail:
        async def delete_item(self, catalog_id, item_id):
            raise CatalogItemSyncError("delete_item", "unreachable")

    result = run(sync_service_item(
        tenant="t1", service_id="svc1", name="Haircut", description="", price_minor=0,
        active=True, image_url="https://x/img.jpg", secret_store=secrets, settings=_settings(),
        syncer_factory=lambda tok: _Fail()))

    assert result.ok is False
    assert result.failed_step == "delete_item"


def test_long_fields_are_truncated_to_metas_own_limits():
    secrets = _FakeSecrets(dict(_FULL_SECRETS))
    fake = _FakeSyncer()

    run(sync_service_item(
        tenant="t1", service_id="svc1", name="x" * 500, description="y" * 6000, price_minor=5000,
        active=True, image_url="https://x/img.jpg", secret_store=secrets, settings=_settings(),
        shop_name="z" * 500, syncer_factory=lambda tok: fake))

    item = fake.calls[0][2]
    assert len(item["title"]) == 100
    assert len(item["description"]) == 5000
    assert len(item["brand"]) == 100
