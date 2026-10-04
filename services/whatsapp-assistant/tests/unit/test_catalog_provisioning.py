"""core/catalog_provisioning.py -- page resolution, catalog creation, WABA connection, cart
enablement, and the `provision_catalog` orchestrator's idempotency guarantees. Stubbing follows
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
    SECRET_DISPLAY_PHONE_NAME,
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


class _FullFake:
    """A provisioner that succeeds at every step, recording calls in order."""

    def __init__(self, page_id="PAGE1", catalog_id="CAT1", display_phone="+966 50 123 4567"):
        self.calls = []
        self._page_id = page_id
        self._catalog_id = catalog_id
        self._display_phone = display_phone

    async def resolve_page_id(self, business_id):
        self.calls.append(("resolve_page_id", business_id))
        return self._page_id

    async def create_catalog(self, business_id, page_id, name):
        self.calls.append(("create_catalog", business_id, page_id, name))
        return self._catalog_id

    async def connect_catalog(self, waba_id, catalog_id):
        self.calls.append(("connect_catalog", waba_id, catalog_id))
        return True

    async def enable_cart(self, phone_number_id):
        self.calls.append(("enable_cart", phone_number_id))
        return True

    async def resolve_display_phone(self, phone_number_id):
        self.calls.append(("resolve_display_phone", phone_number_id))
        return self._display_phone


# ── HttpCatalogProvisioner, one call at a time ────────────────────────────────────────────────

def test_resolve_page_id_returns_first_page():
    with patch("urllib.request.urlopen",
              return_value=_Resp(b'{"data": [{"id": "PAGE1"}, {"id": "PAGE2"}]}')):
        assert run(_http().resolve_page_id("biz1")) == "PAGE1"


def test_resolve_page_id_empty_when_no_pages():
    with patch("urllib.request.urlopen", return_value=_Resp(b'{"data": []}')):
        assert run(_http().resolve_page_id("biz1")) == ""


def test_resolve_page_id_calls_owned_pages_edge():
    captured = {}

    def _fake_urlopen(req, timeout=8):
        captured["url"] = req.full_url
        captured["method"] = req.get_method()
        return _Resp(b'{"data": [{"id": "PAGE1"}]}')

    with patch("urllib.request.urlopen", side_effect=_fake_urlopen):
        run(_http().resolve_page_id("biz1"))
    assert "biz1/owned_pages" in captured["url"]
    assert captured["method"] == "GET"


def test_resolve_page_id_http_error_raises():
    err = urllib.error.HTTPError("url", 403, "forbidden", {}, None)
    err.read = lambda: b"no permission"
    with patch("urllib.request.urlopen", side_effect=err):
        with pytest.raises(CatalogProvisioningError):
            run(_http().resolve_page_id("biz1"))


def test_create_catalog_returns_id():
    with patch("urllib.request.urlopen", return_value=_Resp(b'{"id": "CAT1"}')):
        assert run(_http().create_catalog("biz1", "PAGE1", "My Shop")) == "CAT1"


def test_create_catalog_sends_page_id_vertical_and_truncated_name():
    captured = {}

    def _fake_urlopen(req, timeout=8):
        captured["body"] = req.data
        captured["url"] = req.full_url
        return _Resp(b'{"id": "CAT1"}')

    with patch("urllib.request.urlopen", side_effect=_fake_urlopen):
        run(_http().create_catalog("biz1", "PAGE1", "x" * 500))
    assert b'"vertical": "commerce"' in captured["body"]
    assert b'"page_id": "PAGE1"' in captured["body"]
    assert b"biz1/owned_product_catalogs" in captured["url"].encode()
    # name truncated to 100 chars -- never sent raw and unbounded
    assert len(captured["body"]) < 500


def test_create_catalog_missing_id_raises_named_step():
    with patch("urllib.request.urlopen", return_value=_Resp(b"{}")):
        with pytest.raises(CatalogProvisioningError) as exc:
            run(_http().create_catalog("biz1", "PAGE1", "shop"))
    assert exc.value.step == "create_catalog"


def test_create_catalog_http_error_raises():
    err = urllib.error.HTTPError("url", 400, "bad request", {}, None)
    err.read = lambda: b"duplicate name"
    with patch("urllib.request.urlopen", side_effect=err):
        with pytest.raises(CatalogProvisioningError):
            run(_http().create_catalog("biz1", "PAGE1", "shop"))


def test_create_catalog_transport_error_raises():
    with patch("urllib.request.urlopen", side_effect=TimeoutError("timed out")):
        with pytest.raises(CatalogProvisioningError):
            run(_http().create_catalog("biz1", "PAGE1", "shop"))


def test_connect_catalog_true_on_success():
    with patch("urllib.request.urlopen", return_value=_Resp(b'{"success": true}')):
        assert run(_http().connect_catalog("waba1", "CAT1")) is True


def test_connect_catalog_fails_closed_when_field_absent():
    # ci/check_absent_means_ok.py's own rule: a peer that answers 200 with no recognisable
    # outcome field has not told us it worked -- reading that silence as success is the exact
    # defect that gate exists to catch. False here is retry-safe, never a crash.
    with patch("urllib.request.urlopen", return_value=_Resp(b"{}")):
        assert run(_http().connect_catalog("waba1", "CAT1")) is False


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


def test_enable_cart_fails_closed_when_field_absent():
    with patch("urllib.request.urlopen", return_value=_Resp(b"{}")):
        assert run(_http().enable_cart("phone1")) is False


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

def test_null_resolve_page_id_raises():
    with pytest.raises(CatalogProvisioningError):
        run(NullCatalogProvisioner().resolve_page_id("biz1"))


def test_null_create_catalog_raises():
    with pytest.raises(CatalogProvisioningError):
        run(NullCatalogProvisioner().create_catalog("biz1", "page1", "shop"))


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


def test_provision_catalog_happy_path_resolves_page_creates_connects_and_enables():
    secrets = _FakeSecrets({"t1|" + SECRET_TOKEN_NAME: "tok"})
    fake = _FullFake(page_id="PAGE1", catalog_id="CAT1")

    result = run(provision_catalog(
        tenant="t1", business_id="biz1", waba_id="waba1", phone_number_id="phone1",
        secret_store=secrets, settings=_settings(), provisioner_factory=lambda tok: fake))

    assert result.ok is True
    assert result.page_id == "PAGE1"
    assert result.catalog_id == "CAT1"
    assert result.catalog_created is True
    assert result.connected is True
    assert result.cart_enabled is True
    assert fake.calls == [
        ("resolve_page_id", "biz1"),
        ("create_catalog", "biz1", "PAGE1", "Raje3 - t1"),
        ("connect_catalog", "waba1", "CAT1"),
        ("enable_cart", "phone1"),
        ("resolve_display_phone", "phone1"),
    ]
    # WRITTEN BEFORE the function even returns -- the write-ahead guarantee.
    assert secrets._v["t1|" + SECRET_CATALOG_ID_NAME] == "CAT1"
    assert secrets._v["t1|" + SECRET_DISPLAY_PHONE_NAME] == "+966 50 123 4567"


def test_provision_catalog_no_facebook_page_fails_named_and_writes_nothing():
    """THE REAL PRECONDITION THIS MODULE CANNOT MANUFACTURE AROUND: a business with no Facebook
    Page cannot get a Commerce Catalog. Must fail loudly and specifically, never silently skip."""
    secrets = _FakeSecrets({"t1|" + SECRET_TOKEN_NAME: "tok"})

    class _NoPage:
        async def resolve_page_id(self, business_id):
            return ""

        async def create_catalog(self, business_id, page_id, name):
            raise AssertionError("must not be reached")

        async def connect_catalog(self, waba_id, catalog_id):
            raise AssertionError("must not be reached")

        async def enable_cart(self, phone_number_id):
            raise AssertionError("must not be reached")

    result = run(provision_catalog(
        tenant="t1", business_id="biz1", waba_id="waba1", phone_number_id="phone1",
        secret_store=secrets, settings=_settings(), provisioner_factory=lambda tok: _NoPage()))

    assert result.ok is False
    assert result.failed_step == "resolve_page_id"
    assert "Facebook Page" in result.error
    assert secrets.writes == []


def test_provision_catalog_resolve_page_id_error_fails_named():
    secrets = _FakeSecrets({"t1|" + SECRET_TOKEN_NAME: "tok"})

    class _Fail:
        async def resolve_page_id(self, business_id):
            raise CatalogProvisioningError("resolve_page_id", "permission denied")

        async def create_catalog(self, business_id, page_id, name):
            raise AssertionError("must not be reached")

        async def connect_catalog(self, waba_id, catalog_id):
            raise AssertionError("must not be reached")

        async def enable_cart(self, phone_number_id):
            raise AssertionError("must not be reached")

    result = run(provision_catalog(
        tenant="t1", business_id="biz1", waba_id="waba1", phone_number_id="phone1",
        secret_store=secrets, settings=_settings(), provisioner_factory=lambda tok: _Fail()))

    assert result.ok is False
    assert result.failed_step == "resolve_page_id"


def test_provision_catalog_reuses_existing_catalog_never_resolves_page_or_creates():
    secrets = _FakeSecrets({"t1|" + SECRET_TOKEN_NAME: "tok",
                           "t1|" + SECRET_CATALOG_ID_NAME: "EXISTING_CAT"})
    fake = _FullFake()

    result = run(provision_catalog(
        tenant="t1", business_id="biz1", waba_id="waba1", phone_number_id="phone1",
        secret_store=secrets, settings=_settings(), provisioner_factory=lambda tok: fake))

    assert result.ok is True
    assert result.catalog_id == "EXISTING_CAT"
    assert result.catalog_created is False
    assert result.page_id == ""  # never resolved -- creation was skipped entirely
    assert fake.calls == [("connect_catalog", "waba1", "EXISTING_CAT"), ("enable_cart", "phone1"),
                         ("resolve_display_phone", "phone1")]


def test_provision_catalog_retry_on_a_second_phone_number_reuses_same_catalog():
    """A shop with two branches connects a second number under the same tenant -- the SECOND
    connect must reuse the first catalog, never mint a branch-scoped duplicate."""
    secrets = _FakeSecrets({"t1|" + SECRET_TOKEN_NAME: "tok"})

    first = run(provision_catalog(
        tenant="t1", business_id="biz1", waba_id="waba1", phone_number_id="phone1",
        secret_store=secrets, settings=_settings(),
        provisioner_factory=lambda tok: _FullFake()))
    second = run(provision_catalog(
        tenant="t1", business_id="biz1", waba_id="waba2", phone_number_id="phone2",
        secret_store=secrets, settings=_settings(),
        provisioner_factory=lambda tok: _FullFake()))

    assert first.catalog_created is True
    assert second.catalog_created is False
    assert second.catalog_id == "CAT1"


def test_provision_catalog_create_failure_writes_nothing():
    secrets = _FakeSecrets({"t1|" + SECRET_TOKEN_NAME: "tok"})

    class _FailCreate:
        async def resolve_page_id(self, business_id):
            return "PAGE1"

        async def create_catalog(self, business_id, page_id, name):
            raise CatalogProvisioningError("create_catalog", "boom")

        async def connect_catalog(self, waba_id, catalog_id):
            raise AssertionError("must not be reached")

        async def enable_cart(self, phone_number_id):
            raise AssertionError("must not be reached")

    result = run(provision_catalog(
        tenant="t1", business_id="biz1", waba_id="waba1", phone_number_id="phone1",
        secret_store=secrets, settings=_settings(),
        provisioner_factory=lambda tok: _FailCreate()))

    assert result.ok is False
    assert result.failed_step == "create_catalog"
    assert secrets.writes == []


def test_provision_catalog_connect_failure_after_create_keeps_catalog_id_written():
    """THE HARD CASE: catalog creation succeeds, connecting to the WABA fails. A retry must NOT
    recreate the catalog (or re-resolve the page) -- it must find the one just written and only
    retry the failed step."""
    secrets = _FakeSecrets({"t1|" + SECRET_TOKEN_NAME: "tok"})

    class _FailConnect:
        async def resolve_page_id(self, business_id):
            return "PAGE1"

        async def create_catalog(self, business_id, page_id, name):
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

    retry = run(provision_catalog(
        tenant="t1", business_id="biz1", waba_id="waba1", phone_number_id="phone1",
        secret_store=secrets, settings=_settings(),
        provisioner_factory=lambda tok: _FullFake(catalog_id="SHOULD_NOT_BE_USED")))

    assert retry.ok is True
    assert retry.catalog_id == "CAT1"
    assert retry.catalog_created is False
    assert retry.page_id == ""  # resolve/create skipped entirely on the retry


def test_provision_catalog_enable_cart_failure_reports_named_step():
    secrets = _FakeSecrets({"t1|" + SECRET_TOKEN_NAME: "tok"})

    class _FailEnable:
        async def resolve_page_id(self, business_id):
            return "PAGE1"

        async def create_catalog(self, business_id, page_id, name):
            return "CAT1"

        async def connect_catalog(self, waba_id, catalog_id):
            return True

        async def enable_cart(self, phone_number_id):
            raise CatalogProvisioningError("enable_cart", "phone not registered")

    result = run(provision_catalog(
        tenant="t1", business_id="biz1", waba_id="waba1", phone_number_id="phone1",
        secret_store=secrets, settings=_settings(),
        provisioner_factory=lambda tok: _FailEnable()))

    assert result.ok is False
    assert result.failed_step == "enable_cart"
    assert result.connected is True
    # The catalog is still on file -- not lost because the LAST step failed.
    assert secrets._v["t1|" + SECRET_CATALOG_ID_NAME] == "CAT1"


# ── resolve_display_phone ─────────────────────────────────────────────────────────────────────

def test_http_resolve_display_phone_returns_graph_field():
    with patch("urllib.request.urlopen",
              return_value=_Resp(b'{"display_phone_number": "+966 50 123 4567"}')):
        assert run(_http().resolve_display_phone("phone1")) == "+966 50 123 4567"


def test_http_resolve_display_phone_empty_when_field_absent():
    with patch("urllib.request.urlopen", return_value=_Resp(b"{}")):
        assert run(_http().resolve_display_phone("phone1")) == ""


def test_null_resolve_display_phone_raises():
    with pytest.raises(CatalogProvisioningError):
        run(NullCatalogProvisioner().resolve_display_phone("phone1"))


def test_provision_catalog_writes_display_phone_only_once():
    """A reconnect (or a second branch number) must not overwrite the first-resolved number --
    same reuse-before-call discipline as the catalog id."""
    secrets = _FakeSecrets({"t1|" + SECRET_TOKEN_NAME: "tok"})

    first = run(provision_catalog(
        tenant="t1", business_id="biz1", waba_id="waba1", phone_number_id="phone1",
        secret_store=secrets, settings=_settings(),
        provisioner_factory=lambda tok: _FullFake(display_phone="+966 50 000 0001")))
    assert first.ok is True
    assert secrets._v["t1|" + SECRET_DISPLAY_PHONE_NAME] == "+966 50 000 0001"

    second = run(provision_catalog(
        tenant="t1", business_id="biz1", waba_id="waba2", phone_number_id="phone2",
        secret_store=secrets, settings=_settings(),
        provisioner_factory=lambda tok: _FullFake(display_phone="+966 50 999 9999")))
    assert second.ok is True
    # STILL THE FIRST NUMBER -- never overwritten by the second branch's own.
    assert secrets._v["t1|" + SECRET_DISPLAY_PHONE_NAME] == "+966 50 000 0001"


def test_provision_catalog_display_phone_failure_does_not_fail_the_whole_result():
    """Best-effort: Step 2 (catalog_item_sync.py) degrades to 'no link' cleanly on its own if this
    is missing -- it must never block Step 1's own success."""
    secrets = _FakeSecrets({"t1|" + SECRET_TOKEN_NAME: "tok"})

    class _FailPhone(_FullFake):
        async def resolve_display_phone(self, phone_number_id):
            raise CatalogProvisioningError("resolve_display_phone", "unreachable")

    result = run(provision_catalog(
        tenant="t1", business_id="biz1", waba_id="waba1", phone_number_id="phone1",
        secret_store=secrets, settings=_settings(),
        provisioner_factory=lambda tok: _FailPhone()))

    assert result.ok is True
    assert ("t1|" + SECRET_DISPLAY_PHONE_NAME) not in secrets._v
