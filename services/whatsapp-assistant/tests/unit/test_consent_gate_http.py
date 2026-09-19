"""HttpConsentGate.record() — the subject's own live consent write, confirmed live against
compliance-service v0.25.13 (2026-09-19). check() already has coverage through
tests/integration/test_consent_gate.py's scripted-gate flow; this file is the direct, isolated
coverage for the HTTP adapter itself, same convention as test_held_apps.py's own HttpHeldApps
coverage.
"""
from __future__ import annotations

import json
from unittest.mock import patch

from app.adapters.consent_gate.http import HttpConsentGate


def _gate():
    return HttpConsentGate(url="http://compliance", token="t" * 10)


async def test_record_posts_the_agreed_body_shape_with_the_internal_token():
    captured: dict = {}

    def _fake_urlopen(req, timeout=0):
        captured["url"] = req.full_url
        captured["method"] = req.get_method()
        captured["headers"] = dict(req.header_items())
        captured["body"] = json.loads(req.data)

        class _Resp:
            status = 200

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False
        return _Resp()

    with patch("urllib.request.urlopen", _fake_urlopen):
        ok = await _gate().record(
            tenant="shop1", subject="+966500000000", purpose="whatsapp_ai_assistant", granted=True)

    assert ok is True
    assert captured["method"] == "POST"
    assert captured["url"] == "http://compliance/internal/compliance/consent/record"
    assert captured["headers"].get("X-internal-token") == "t" * 10
    assert captured["body"] == {
        "tenant": "shop1", "subject": "+966500000000", "purpose": "whatsapp_ai_assistant",
        "granted": True, "method": "whatsapp_interactive"}


async def test_record_reports_a_withdrawal_the_same_shape():
    def _fake_urlopen(req, timeout=0):
        body = json.loads(req.data)
        assert body["granted"] is False

        class _Resp:
            status = 200

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False
        return _Resp()

    with patch("urllib.request.urlopen", _fake_urlopen):
        ok = await _gate().record(
            tenant="shop1", subject="+966500000000", purpose="whatsapp_ai_assistant", granted=False)
    assert ok is True


async def test_record_returns_false_never_raises_on_an_unreachable_service():
    import urllib.error

    def _boom(req, timeout=0):
        raise urllib.error.URLError("down")

    with patch("urllib.request.urlopen", _boom):
        ok = await _gate().record(
            tenant="shop1", subject="+966500000000", purpose="whatsapp_ai_assistant", granted=True)
    assert ok is False


async def test_record_returns_false_on_a_non_2xx_status():
    def _fake_urlopen(req, timeout=0):
        class _Resp:
            status = 500

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False
        return _Resp()

    with patch("urllib.request.urlopen", _fake_urlopen):
        ok = await _gate().record(
            tenant="shop1", subject="+966500000000", purpose="whatsapp_ai_assistant", granted=True)
    assert ok is False
