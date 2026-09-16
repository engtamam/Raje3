"""`core/tenant_branding.py` — a shop's own saved logo/colour, fetched from tenant-service and
decoded into something python-docx can actually embed. Owner's own instruction (2026-09-16): use
it wherever a document leaves the shop, degrade silently to no logo when anything about the peer
or the stored value is not right — never fail the export over a missing/broken picture.
"""
from __future__ import annotations

import asyncio
import base64
import types
from io import BytesIO

from app.core.tenant_branding import Branding, _decode_to_png, fetch_branding


def _webp_data_url(color=(200, 10, 10)) -> str:
    from PIL import Image
    img = Image.new("RGB", (40, 20), color)
    buf = BytesIO()
    img.save(buf, format="WEBP")
    return "data:image/webp;base64," + base64.b64encode(buf.getvalue()).decode()


def _settings(**over) -> types.SimpleNamespace:
    base = {"TENANT_SERVICE_URL": "http://tenant-service:8000", "INTERNAL_SERVICE_TOKEN": "t" * 40}
    base.update(over)
    return types.SimpleNamespace(**base)


class _Registry:
    def __init__(self, code: int, body: dict) -> None:
        self.code = code
        self.body = body
        self.calls: list[tuple] = []

    def call(self, url, *, method, body=None, internal=False):
        self.calls.append((url, method, body, internal))
        return self.code, self.body


def test_decodes_a_real_webp_logo_into_png_bytes():
    out = _decode_to_png(_webp_data_url())
    assert out is not None
    assert out[:8] == b"\x89PNG\r\n\x1a\n"   # the real PNG magic bytes


def test_a_non_data_url_degrades_to_none():
    assert _decode_to_png("https://example.com/logo.png") is None


def test_malformed_base64_degrades_to_none():
    assert _decode_to_png("data:image/webp;base64,!!!not-base64!!!") is None


def test_no_tenant_service_url_configured_degrades_to_empty_branding():
    out = asyncio.run(fetch_branding(_settings(TENANT_SERVICE_URL=""), "t1"))
    assert out == Branding()


def test_a_real_logo_and_accent_are_fetched_and_decoded(monkeypatch):
    registry = _Registry(200, {"branding": {"logo_url": _webp_data_url(), "accent": "#B08A3E"}})
    from app.core import signup as signup_module
    monkeypatch.setattr(signup_module, "Http", lambda **kw: registry)

    out = asyncio.run(fetch_branding(_settings(), "t1"))

    assert out.accent == "#B08A3E"
    assert out.logo_png is not None
    assert out.logo_png[:8] == b"\x89PNG\r\n\x1a\n"
    assert registry.calls[0][0].endswith("/internal/tenants/t1")
    assert registry.calls[0][1] == "GET"
    assert registry.calls[0][3] is True   # internal=True — the internal token is sent


def test_a_shop_with_no_logo_set_degrades_to_no_picture(monkeypatch):
    registry = _Registry(200, {"branding": {"logo_url": "", "accent": ""}})
    from app.core import signup as signup_module
    monkeypatch.setattr(signup_module, "Http", lambda **kw: registry)

    out = asyncio.run(fetch_branding(_settings(), "t1"))
    assert out == Branding()


def test_an_unreachable_peer_degrades_silently_never_raises(monkeypatch):
    registry = _Registry(0, {})
    from app.core import signup as signup_module
    monkeypatch.setattr(signup_module, "Http", lambda **kw: registry)

    out = asyncio.run(fetch_branding(_settings(), "t1"))
    assert out == Branding()
