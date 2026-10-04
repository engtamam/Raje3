"""`core/shop_info.py` — the public portal's own branding read. Every case here is a case the
peer call CAN actually hit in production (tenant-service down, slow, returning garbage, or simply
never configured) and none of them may ever raise — the portal's header must still render."""
from __future__ import annotations

import asyncio
import json
import socket
import urllib.error

from app.core import shop_info as shop_info_module
from app.core.shop_info import ShopInfo, fetch_shop_info


def _run(coro):
    return asyncio.run(coro)


class _FakeSettings:
    def __init__(self, *, url="http://tenant-service:8000", token="tkn", timeout=5):
        self.TENANT_SERVICE_URL = url
        self.INTERNAL_SERVICE_TOKEN = token
        self.SIGNUP_TIMEOUT_SECONDS = timeout


class _FakeResponse:
    def __init__(self, payload: bytes):
        self._payload = payload

    def read(self):
        return self._payload

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def test_no_tenant_service_url_configured_returns_defaults_without_a_call(monkeypatch):
    def _boom(*a, **k):
        raise AssertionError("must never attempt a call with no URL configured")

    monkeypatch.setattr(shop_info_module.urllib.request, "urlopen", _boom)
    out = _run(fetch_shop_info(_FakeSettings(url=""), "shopA"))
    assert out == ShopInfo()


def test_empty_tenant_returns_defaults_without_a_call(monkeypatch):
    def _boom(*a, **k):
        raise AssertionError("must never attempt a call with no tenant")

    monkeypatch.setattr(shop_info_module.urllib.request, "urlopen", _boom)
    out = _run(fetch_shop_info(_FakeSettings(), ""))
    assert out == ShopInfo()


def test_happy_path_reads_name_logo_and_accent(monkeypatch):
    body = json.dumps({"name": "مغسلة الفخامة",
                       "branding": {"logo_url": "https://x/logo.webp", "accent": "#123abc"}}).encode()

    def _fake_urlopen(req, timeout=None):
        assert req.full_url == "http://tenant-service:8000/internal/tenants/shopA"
        assert req.headers.get("X-internal-token") == "tkn"
        return _FakeResponse(body)

    monkeypatch.setattr(shop_info_module.urllib.request, "urlopen", _fake_urlopen)
    out = _run(fetch_shop_info(_FakeSettings(), "shopA"))
    assert out == ShopInfo(name="مغسلة الفخامة", logo_url="https://x/logo.webp", accent="#123abc")


def test_missing_branding_key_entirely_still_returns_the_name(monkeypatch):
    body = json.dumps({"name": "شوب بلا براند"}).encode()
    monkeypatch.setattr(shop_info_module.urllib.request, "urlopen",
                        lambda req, timeout=None: _FakeResponse(body))
    out = _run(fetch_shop_info(_FakeSettings(), "shopA"))
    assert out == ShopInfo(name="شوب بلا براند", logo_url="", accent="")


def test_branding_present_but_null_fields_degrades_to_empty_strings(monkeypatch):
    body = json.dumps({"name": "x", "branding": {"logo_url": None, "accent": None}}).encode()
    monkeypatch.setattr(shop_info_module.urllib.request, "urlopen",
                        lambda req, timeout=None: _FakeResponse(body))
    out = _run(fetch_shop_info(_FakeSettings(), "shopA"))
    assert out.logo_url == ""
    assert out.accent == ""


def test_top_level_body_not_even_a_dict_degrades_silently(monkeypatch):
    monkeypatch.setattr(shop_info_module.urllib.request, "urlopen",
                        lambda req, timeout=None: _FakeResponse(b"[1, 2, 3]"))
    out = _run(fetch_shop_info(_FakeSettings(), "shopA"))
    assert out == ShopInfo()


def test_branding_key_present_but_not_a_dict_degrades_silently(monkeypatch):
    """`branding.get(...)` on a non-dict raises — caught by `fetch_shop_info`'s own outer
    `except Exception`, so a malformed `branding` field loses the whole read rather than crashing
    the portal's header (same "never raise" contract every other case here proves)."""
    body = json.dumps({"name": "x", "branding": "not-a-dict"}).encode()
    monkeypatch.setattr(shop_info_module.urllib.request, "urlopen",
                        lambda req, timeout=None: _FakeResponse(body))
    out = _run(fetch_shop_info(_FakeSettings(), "shopA"))
    assert out == ShopInfo()


def test_malformed_json_body_degrades_silently(monkeypatch):
    monkeypatch.setattr(shop_info_module.urllib.request, "urlopen",
                        lambda req, timeout=None: _FakeResponse(b"not json at all {{{"))
    out = _run(fetch_shop_info(_FakeSettings(), "shopA"))
    assert out == ShopInfo()


def test_empty_body_degrades_silently(monkeypatch):
    monkeypatch.setattr(shop_info_module.urllib.request, "urlopen",
                        lambda req, timeout=None: _FakeResponse(b""))
    out = _run(fetch_shop_info(_FakeSettings(), "shopA"))
    assert out == ShopInfo()


def test_http_404_degrades_silently(monkeypatch):
    def _raise(req, timeout=None):
        raise urllib.error.HTTPError("url", 404, "not found", {}, None)

    monkeypatch.setattr(shop_info_module.urllib.request, "urlopen", _raise)
    out = _run(fetch_shop_info(_FakeSettings(), "shopA"))
    assert out == ShopInfo()


def test_http_500_degrades_silently(monkeypatch):
    def _raise(req, timeout=None):
        raise urllib.error.HTTPError("url", 500, "server error", {}, None)

    monkeypatch.setattr(shop_info_module.urllib.request, "urlopen", _raise)
    out = _run(fetch_shop_info(_FakeSettings(), "shopA"))
    assert out == ShopInfo()


def test_connection_refused_degrades_silently(monkeypatch):
    def _raise(req, timeout=None):
        raise urllib.error.URLError(ConnectionRefusedError())

    monkeypatch.setattr(shop_info_module.urllib.request, "urlopen", _raise)
    out = _run(fetch_shop_info(_FakeSettings(), "shopA"))
    assert out == ShopInfo()


def test_socket_timeout_degrades_silently(monkeypatch):
    def _raise(req, timeout=None):
        raise socket.timeout()

    monkeypatch.setattr(shop_info_module.urllib.request, "urlopen", _raise)
    out = _run(fetch_shop_info(_FakeSettings(), "shopA"))
    assert out == ShopInfo()


def test_generic_timeout_error_degrades_silently(monkeypatch):
    def _raise(req, timeout=None):
        raise TimeoutError()

    monkeypatch.setattr(shop_info_module.urllib.request, "urlopen", _raise)
    out = _run(fetch_shop_info(_FakeSettings(), "shopA"))
    assert out == ShopInfo()


def test_a_completely_unexpected_exception_still_never_escapes(monkeypatch):
    """`fetch_shop_info`'s own outer `except Exception` is the last line of defence — even a bug
    in a future change to this module (say, a bad attribute access) must not take the portal's
    header down with it."""
    def _raise(req, timeout=None):
        raise RuntimeError("something nobody anticipated")

    monkeypatch.setattr(shop_info_module.urllib.request, "urlopen", _raise)
    out = _run(fetch_shop_info(_FakeSettings(), "shopA"))
    assert out == ShopInfo()


def test_trailing_slash_on_configured_base_url_is_stripped(monkeypatch):
    seen = {}

    def _fake_urlopen(req, timeout=None):
        seen["url"] = req.full_url
        return _FakeResponse(b"{}")

    monkeypatch.setattr(shop_info_module.urllib.request, "urlopen", _fake_urlopen)
    _run(fetch_shop_info(_FakeSettings(url="http://tenant-service:8000/"), "shopA"))
    assert seen["url"] == "http://tenant-service:8000/internal/tenants/shopA"


def test_no_internal_token_configured_sends_empty_header_not_a_crash(monkeypatch):
    seen = {}

    def _fake_urlopen(req, timeout=None):
        seen["token"] = req.headers.get("X-internal-token")
        return _FakeResponse(b"{}")

    monkeypatch.setattr(shop_info_module.urllib.request, "urlopen", _fake_urlopen)
    _run(fetch_shop_info(_FakeSettings(token=""), "shopA"))
    assert seen["token"] == ""


def test_a_tenant_containing_special_characters_is_url_safe():
    """Not encoded by this module at all — `f"{base}/internal/tenants/{tenant}"` trusts the caller
    (the public route's own `tenant` path param, already a single URL segment FastAPI itself
    decoded) never to hand this a value containing a literal `/`. Documented by proving the one
    thing that DOES matter: a tenant id with the ordinary punctuation real tenant ids use
    (hyphens/underscores) round-trips unmodified."""
    import asyncio as _asyncio

    seen = {}

    def _fake_urlopen(req, timeout=None):
        seen["url"] = req.full_url
        return _FakeResponse(b"{}")

    async def go():
        import unittest.mock as mock

        with mock.patch.object(shop_info_module.urllib.request, "urlopen", _fake_urlopen):
            return await fetch_shop_info(_FakeSettings(), "shop-A_1")

    _asyncio.run(go())
    assert seen["url"] == "http://tenant-service:8000/internal/tenants/shop-A_1"
