"""core/catalog_provisioning.py -- catalog creation, WABA connection, cart enablement, and the
`provision_catalog` orchestrator's idempotency guarantees. Stubbing follows
test_meta_agent_provisioning.py's own conventions (fake secret store, fake urlopen response)."""
from __future__ import annotations

import asyncio
import urllib.error
from unittest.mock import patch

import pytest

from app.core.catalog_provisioning import (
    CatalogProvisioningError,
    HttpCatalogProvisioner,
    NullCatalogProvisioner,
    ProvisionCatalogResult,
    SECRET_CATALOG_ID_NAME,
    SECRET_TOKEN_NAME,
    build,
    provision_catalog,
)


def run(c):
    return asyncio.run(c)


class _FakeSecrets:
    def __init__(self, values=None):
        self._v = dict(values or {})
        self.writes = []

    async def get(self, *, tenant, name, fallback=""):
        return self._v.get(f"{tenant}|{name}", fallback)

    async def set(self, *, tenant, name, value, actor_ref=""):
        self._v[f"{tenant}|{name}"] = value
        self.writes.append((tenant, name, value))


class _Resp:
    def __init__(self, body=b"{}", status=200):
        self._body = body
        self.status = status

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
    return HttpCatalogProvisioner(
        token="tok", graph_base_url="https://graph.facebook.com", graph_version="v26.0", **kw)


# ── HttpCatalogProvisioner, one call at a time ────────────────────────────────────────────────

def test_create_catalog_returns_id():
    with patch("urllib.request.urlopen", return_value=_Resp(b'{"id": "CAT1"}')):
        assert run(_http().create_catalog("biz1", "My Shop")) == "CAT1"


def test_create_catalog_sends_commerce_vertical_and_truncated_name():
    captured = {}

    def _fake_urlopen(req, timeout=8):
        captured["body"] = req.data
        captured["url"] = req.full_url
        return _Resp(b'{"id": "CAT1"}')

    with patch("urllib.request.urlopen", side_effect=_fake_urlopen):
        run(_http().create_catalog("biz1", "x" * 500))
    assert b'"vertical": "commerce"' in captured["body"]
    assert b"biz1/owned_product_catalogs" in captured["url"].encode()
    # name truncated to 100 chars -- never sent raw and unbounded
    assert len(captured["body"]) < 500


def test_create_catalog_missing_id_raises_named_step():
    with patch("urllib.request.urlopen", return_value=_Resp(b"{}")):
        with pytest.raises(CatalogProvisioningError) as exc:
            run(_http().create_catalog("biz1", "shop"))
    assert exc.value.step == "create_catalog"


def test_create_catalog_http_error_raises():
    err = urllib.error.HTTPError("url", 400, "bad request", {}, None)
    err.read = lambda: b"duplicate name"
    with patch("urllib.request.urlopen", side_effect=err):
        with pytest.raises(CatalogProvisioningError):
            run(_http().create_catalog("biz1", "shop"))


def test_create_catalog_transport_error_raises():
    with patch("urllib.request.urlopen", side_effect=TimeoutError("timed out")):
        with pytest.raises(CatalogProvisioningError):
            run(_http().create_catalog("biz1", "shop"))


def test_connect_catalog_true_on_success():
    with patch("urllib.request.urlopen", return_value=_Resp(b'{"success": true}')):
        assert run(_http().connect_catalog("waba1", "CAT1")) is True


def test_connect_catalog_defaults_true_when_field_absent():
    # Graph often omits "success" on a 200 with no body content worth reporting -- absence must
    # not be misread as a refusal when the call itself did not raise.
    with patch("urllib.request.urlopen", return_value=_Resp(b"{}")):
        assert run(_http().connect_catalog("waba1", "CAT1")) is True


def test_connect_catalog_sends_catalog_id_in_body():
    captured = {}

    def _fake_urlopen(req, timeout=8):
        captured["body"] = req.data
        return _Resp(b'{"success": true}')

    with patch("urllib.request.urlopen", side_effect=_fake_urlopen):
        run(_http().connect_catalog("waba1", "CAT1"))
    assert b"CAT1" in captured["body"]


def test_connect_catalog_error_raises():
    err = urllib.error.HTTPError("url", 500, "server error", {}, None)
    err.read = lambda: b"oops"
    with patch("urllib.request.urlopen", side_effect=err):
        with pytest.raises(CatalogProvisioningError):
            run(_http().connect_catalog("waba1", "CAT1"))


def test_enable_cart_true_on_success():
    with patch("urllib.request.urlopen", return_value=_Resp(b'{"success": true}')):
        assert run(_http().enable_cart("phone1")) is True


def test_enable_cart_uses_query_string_not_body():
    captured = {}

    def _fake_urlopen(req, timeout=8):
        captured["url"] = req.full_url
        captured["body"] = req.data
        return _Resp(b'{"success": true}')

    with patch("urllib.request.urlopen", side_effect=_fake_urlopen):
        run(_http().enable_cart("phone1"))
    assert "is_cart_enabled=true" in captured["url"]
    assert captured["body"] is None


def test_enable_cart_error_raises():
    err = urllib.error.HTTPError("url", 401, "unauthorized", {}, None)
    err.read = lambda: b"bad token"
    with patch("urllib.request.urlopen", side_effect=err):
        with pytest.raises(CatalogProvisioningError):
            run(_http().enable_cart("phone1"))


# ── NullCatalogProvisioner ────────────────────────────────────────────────────────────────────

def test_null_create_catalog_raises():
    with pytest.raises(CatalogProvisioningError):
        run(NullCatalogProvisioner().create_catalog("biz1", "shop"))


def test_null_connect_and_enable_return_false():
    p = NullCatalogProvisioner()
    assert run(p.connect_catalog("waba1", "cat1")) is False
    assert run(p.enable_cart("phone1")) is False


def test_build_returns_null_when_disabled():
    assert isinstance(build(_settings(enabled=False)), NullCatalogProvisioner)


def test_build_returns_http_when_enabled():
    assert isinstance(build(_settings(enabled=True)), HttpCatalogProvisioner)


# ── provision_catalog orchestrator ────────────────────────────────────────────────────────────

def test_provision_catalog_missing_ids_fails_without_any_graph_call():
    secrets = _FakeSecrets({"t1|" + SECRET_TOKEN_NAME: "tok"})
    result = run(provision_catalog(
        tenant="t1", business_id="", waba_id="waba1", phone_number_id="phone1",
        secret_store=secrets, settings=_settings()))
    assert result.ok is False
    assert result.failed_step == "validate_ids"
    assert secrets.writes == []


def test_provision_catalog_no_token_fails_cleanly():
    secrets = _FakeSecrets()
    result = run(provision_catalog(
        tenant="t1", business_id="biz1", waba_id="waba1", phone_number_id="phone1",
        secret_store=secrets, settings=_settings()))
    assert result.ok is False
    assert result.failed_step == "validate_ids"
    assert "credential" in result.error


def test_provision_catalog_happy_path_creates_connects_and_enables():
    secrets = _FakeSecrets({"t1|" + SECRET_TOKEN_NAME: "tok"})
    calls = []

    class _Fake:
        async def create_catalog(self, business_id, name):
            calls.append(("create", business_id, name))
            return "CAT1"

        async def connect_catalog(self, waba_id, catalog_id):
            calls.append(("connect", waba_id, catalog_id))
            return True

        async def enable_cart(self, phone_number_id):
            calls.append(("enable", phone_number_id))
            return True

    result = run(provision_catalog(
        tenant="t1", business_id="biz1", waba_id="waba1", phone_number_id="phone1",
        secret_store=secrets, settings=_settings(), provisioner_factory=lambda tok: _Fake()))

    assert result.ok is True
    assert result.catalog_id == "CAT1"
    assert result.catalog_created is True
    assert result.connected is True
    assert result.cart_enabled is True
    assert calls == [("create", "biz1", "Raje3 - t1"), ("connect", "waba1", "CAT1"),
                     ("enable", "phone1")]
    # WRITTEN BEFORE the function even returns -- the write-ahead guarantee.
    assert secrets._v["t1|" + SECRET_CATALOG_ID_NAME] == "CAT1"


def test_provision_catalog_reuses_existing_catalog_never_calls_create():
    secrets = _FakeSecrets({"t1|" + SECRET_TOKEN_NAME: "tok",
                           "t1|" + SECRET_CATALOG_ID_NAME: "EXISTING_CAT"})
    calls = []

    class _Fake:
        async def create_catalog(self, business_id, name):
            calls.append("create")  # must never be reached
            return "SHOULD_NOT_HAPPEN"

        async def connect_catalog(self, waba_id, catalog_id):
            calls.append(("connect", catalog_id))
            return True

        async def enable_cart(self, phone_number_id):
            calls.append("enable")
            return True

    result = run(provision_catalog(
        tenant="t1", business_id="biz1", waba_id="waba1", phone_number_id="phone1",
        secret_store=secrets, settings=_settings(), provisioner_factory=lambda tok: _Fake()))

    assert result.ok is True
    assert result.catalog_id == "EXISTING_CAT"
    assert result.catalog_created is False
    assert "create" not in calls
    assert calls == [("connect", "EXISTING_CAT"), "enable"]


def test_provision_catalog_retry_on_a_second_phone_number_reuses_same_catalog():
    """A shop with two branches connects a second number under the same tenant -- the SECOND
    connect must reuse the first catalog, never mint a branch-scoped duplicate."""
    secrets = _FakeSecrets({"t1|" + SECRET_TOKEN_NAME: "tok"})
    create_calls = []

    class _Fake:
        async def create_catalog(self, business_id, name):
            create_calls.append(name)
            return "CAT1"

        async def connect_catalog(self, waba_id, catalog_id):
            return True

        async def enable_cart(self, phone_number_id):
            return True

    first = run(provision_catalog(
        tenant="t1", business_id="biz1", waba_id="waba1", phone_number_id="phone1",
        secret_store=secrets, settings=_settings(), provisioner_factory=lambda tok: _Fake()))
    second = run(provision_catalog(
        tenant="t1", business_id="biz1", waba_id="waba2", phone_number_id="phone2",
        secret_store=secrets, settings=_settings(), provisioner_factory=lambda tok: _Fake()))

    assert first.catalog_created is True
    assert second.catalog_created is False
    assert second.catalog_id == "CAT1"
    assert len(create_calls) == 1


def test_provision_catalog_create_failure_writes_nothing():
    secrets = _FakeSecrets({"t1|" + SECRET_TOKEN_NAME: "tok"})

    class _Fake:
        async def create_catalog(self, business_id, name):
            raise CatalogProvisioningError("create_catalog", "boom")

        async def connect_catalog(self, waba_id, catalog_id):
            raise AssertionError("must not be reached")

        async def enable_cart(self, phone_number_id):
            raise AssertionError("must not be reached")

    result = run(provision_catalog(
        tenant="t1", business_id="biz1", waba_id="waba1", phone_number_id="phone1",
        secret_store=secrets, settings=_settings(), provisioner_factory=lambda tok: _Fake()))

    assert result.ok is False
    assert result.failed_step == "create_catalog"
    assert secrets.writes == []


def test_provision_catalog_connect_failure_after_create_keeps_catalog_id_written():
    """THE HARD CASE: catalog creation succeeds, connecting to the WABA fails. A retry must NOT
    recreate the catalog -- it must find the one just written and only retry the failed step."""
    secrets = _FakeSecrets({"t1|" + SECRET_TOKEN_NAME: "tok"})

    class _FailConnect:
        async def create_catalog(self, business_id, name):
            return "CAT1"

        async def connect_catalog(self, waba_id, catalog_id):
            raise CatalogProvisioningError("connect_catalog", "waba unreachable")

        async def enable_cart(self, phone_number_id):
            raise AssertionError("must not be reached")

    first = run(provision_catalog(
        tenant="t1", business_id="biz1", waba_id="waba1", phone_number_id="phone1",
        secret_store=secrets, settings=_settings(),
        provisioner_factory=lambda tok: _FailConnect()))
    assert first.ok is False
    assert first.failed_step == "connect_catalog"
    # THE WRITE-AHEAD ALREADY HAPPENED, despite the overall call failing.
    assert secrets._v["t1|" + SECRET_CATALOG_ID_NAME] == "CAT1"

    retry_calls = []

    class _NowSucceeds:
        async def create_catalog(self, business_id, name):
            retry_calls.append("create")  # must never run on the retry
            return "SHOULD_NOT_HAPPEN"

        async def connect_catalog(self, waba_id, catalog_id):
            retry_calls.append(("connect", catalog_id))
            return True

        async def enable_cart(self, phone_number_id):
            retry_calls.append("enable")
            return True

    retry = run(provision_catalog(
        tenant="t1", business_id="biz1", waba_id="waba1", phone_number_id="phone1",
        secret_store=secrets, settings=_settings(),
        provisioner_factory=lambda tok: _NowSucceeds()))

    assert retry.ok is True
    assert retry.catalog_id == "CAT1"
    assert retry.catalog_created is False
    assert "create" not in retry_calls
    assert retry_calls == [("connect", "CAT1"), "enable"]


def test_provision_catalog_enable_cart_failure_reports_named_step():
    secrets = _FakeSecrets({"t1|" + SECRET_TOKEN_NAME: "tok"})

    class _Fake:
        async def create_catalog(self, business_id, name):
            return "CAT1"

        async def connect_catalog(self, waba_id, catalog_id):
            return True

        async def enable_cart(self, phone_number_id):
            raise CatalogProvisioningError("enable_cart", "phone not registered")

    result = run(provision_catalog(
        tenant="t1", business_id="biz1", waba_id="waba1", phone_number_id="phone1",
        secret_store=secrets, settings=_settings(), provisioner_factory=lambda tok: _Fake()))

    assert result.ok is False
    assert result.failed_step == "enable_cart"
    assert result.connected is True
    # The catalog is still on file -- not lost because the LAST step failed.
    assert secrets._v["t1|" + SECRET_CATALOG_ID_NAME] == "CAT1"
