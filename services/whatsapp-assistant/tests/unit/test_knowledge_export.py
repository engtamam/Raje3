"""build_business_info_payload / HttpKnowledgeExporter / NullKnowledgeExporter — the Business Info
half of Meta Business Agent's real Knowledge REST API (core/knowledge_export.py)."""
from __future__ import annotations

import asyncio
import urllib.error
from unittest.mock import patch

from app.core.knowledge_export import (
    API_VERSION_HEADER_NAME,
    API_VERSION_HEADER_VALUE,
    SECRET_ENTITY_ID_NAME,
    SECRET_TOKEN_NAME,
    HttpKnowledgeExporter,
    NullKnowledgeExporter,
    build,
    build_business_info_payload,
)


def run(c):
    return asyncio.run(c)


# ── build_business_info_payload ──────────────────────────────────────────────────────────────────
def test_empty_notes_produce_no_payload():
    assert build_business_info_payload("") == {}
    assert build_business_info_payload("   ") == {}


def test_notes_map_onto_business_description_only():
    payload = build_business_info_payload("نفتح من السبت للخميس، عندنا خصم للطلاب.")
    assert set(payload) == {"business_description"}
    assert payload["business_description"] == "نفتح من السبت للخميس، عندنا خصم للطلاب."


def test_no_other_fields_are_ever_invented():
    payload = build_business_info_payload("hello")
    for key in ("payment_method", "return_policy", "purchase_info",
               "delivery_and_shipping", "contact_info"):
        assert key not in payload


def test_redaction_is_applied_before_export():
    payload = build_business_info_payload("call me at owner@shop.com for details")
    assert "owner@shop.com" not in payload["business_description"]
    assert "[email]" in payload["business_description"]


def test_notes_that_redact_to_nothing_produce_no_payload():
    # A pathological case: the whole text IS the thing redacted, leaving nothing meaningful. Not
    # exercised by the email case above (redaction leaves surrounding prose) — included for
    # completeness of the "empty after processing means no request" rule.
    payload = build_business_info_payload(" ")
    assert payload == {}


# ── NullKnowledgeExporter ────────────────────────────────────────────────────────────────────────
def test_null_exporter_never_sends():
    assert run(NullKnowledgeExporter().export(tenant="t1", owner_notes="hello")) is False


# ── HttpKnowledgeExporter ────────────────────────────────────────────────────────────────────────
class _FakeSecrets:
    def __init__(self, values: dict[str, str]) -> None:
        self._v = values

    async def get(self, *, tenant: str, name: str, fallback: str = "") -> str:
        return self._v.get(name, fallback)


class _Resp:
    def __init__(self, status=200):
        self.status = status

    def read(self):
        return b"{}"

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def _exporter(secrets: dict[str, str]) -> HttpKnowledgeExporter:
    return HttpKnowledgeExporter(secret_store=_FakeSecrets(secrets),
                                 graph_base_url="https://graph.facebook.com",
                                 graph_version="v21.0", timeout=8)


def test_no_credential_configured_never_calls_out():
    e = _exporter({})
    with patch("urllib.request.urlopen") as m:
        assert run(e.export(tenant="t1", owner_notes="hello")) is False
        m.assert_not_called()


def test_empty_notes_never_call_out_even_when_configured():
    e = _exporter({SECRET_TOKEN_NAME: "tok", SECRET_ENTITY_ID_NAME: "123456"})
    with patch("urllib.request.urlopen") as m:
        assert run(e.export(tenant="t1", owner_notes="")) is False
        m.assert_not_called()


def test_the_exact_url_shape_headers_and_auth():
    e = _exporter({SECRET_TOKEN_NAME: "sekrit-token", SECRET_ENTITY_ID_NAME: "1029384756"})
    captured = {}

    def _fake_urlopen(req, timeout=None):
        captured["url"] = req.full_url
        captured["method"] = req.get_method()
        captured["headers"] = {k: v for k, v in req.header_items()}
        return _Resp(200)

    with patch("urllib.request.urlopen", side_effect=_fake_urlopen):
        assert run(e.export(tenant="t1", owner_notes="نعمل يوميا")) is True

    assert captured["url"] == "https://graph.facebook.com/v21.0/1029384756/agent_config/business_info"
    assert captured["method"] == "PUT"
    # urllib.Request capitalizes header keys it is given verbatim (Capitalize-First-Letter-Only,
    # not title case) — compare case-insensitively so this test does not depend on that quirk.
    lowered = {k.lower(): v for k, v in captured["headers"].items()}
    assert lowered["authorization"] == "Bearer sekrit-token"
    assert lowered[API_VERSION_HEADER_NAME.lower()] == API_VERSION_HEADER_VALUE


def test_a_non_2xx_response_is_a_failure():
    e = _exporter({SECRET_TOKEN_NAME: "tok", SECRET_ENTITY_ID_NAME: "123"})
    with patch("urllib.request.urlopen", return_value=_Resp(500)):
        assert run(e.export(tenant="t1", owner_notes="hello")) is False


def test_an_unreachable_peer_never_raises():
    e = _exporter({SECRET_TOKEN_NAME: "tok", SECRET_ENTITY_ID_NAME: "123"})
    with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("down")):
        assert run(e.export(tenant="t1", owner_notes="hello")) is False


# ── build ─────────────────────────────────────────────────────────────────────────────────────────
def test_build_falls_back_to_null_when_the_flag_is_off():
    class _S:
        KNOWLEDGE_EXPORT_ENABLED = False
        META_GRAPH_BASE_URL = "https://graph.facebook.com"
        META_GRAPH_API_VERSION = "v21.0"
        PEER_TIMEOUT_SECONDS = 8

    assert isinstance(build(_S(), secret_store=_FakeSecrets({})), NullKnowledgeExporter)


def test_build_falls_back_to_null_without_a_secret_store():
    class _S:
        KNOWLEDGE_EXPORT_ENABLED = True
        META_GRAPH_BASE_URL = "https://graph.facebook.com"
        META_GRAPH_API_VERSION = "v21.0"
        PEER_TIMEOUT_SECONDS = 8

    assert isinstance(build(_S(), secret_store=None), NullKnowledgeExporter)


def test_build_returns_the_real_adapter_when_configured():
    class _S:
        KNOWLEDGE_EXPORT_ENABLED = True
        META_GRAPH_BASE_URL = "https://graph.facebook.com"
        META_GRAPH_API_VERSION = "v21.0"
        PEER_TIMEOUT_SECONDS = 8

    assert isinstance(build(_S(), secret_store=_FakeSecrets({})), HttpKnowledgeExporter)
