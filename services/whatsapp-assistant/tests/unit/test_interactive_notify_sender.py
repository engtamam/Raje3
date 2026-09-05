"""InteractiveNotifySender — replaces DirectCloudApiSender's direct Meta Graph API call with a
peer call to notification-service's POST /internal/notify/whatsapp/interactive (platform v0.16.38,
commit 0c54f5e). No secret_store, no per-tenant credential — just the same X-Internal-Token idiom
as TemplateSender / HttpCustomerLookup.
"""
from __future__ import annotations

import asyncio
import json
from unittest.mock import patch

import pytest

from app.adapters.whatsapp_sender.direct import InteractiveNotifySender, SendFailed


def run(c):
    return asyncio.run(c)


def sender():
    return InteractiveNotifySender(
        notify_url="http://notification-service:8000",
        notify_path="/internal/notify/whatsapp/interactive", token="t", timeout=8)


class _Resp:
    def __init__(self, payload, status=200):
        self._p = json.dumps(payload).encode()
        self.status = status

    def read(self):
        return self._p

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def test_send_interactive_posts_to_the_interactive_route_with_internal_token():
    s = sender()
    seen: dict = {}

    def _urlopen(req, timeout=0):
        seen["url"] = req.full_url
        seen["header"] = req.get_header("X-internal-token")
        seen["body"] = json.loads(req.data or b"{}")
        return _Resp({"status": "sent", "delivery_id": "dlv_1"})

    with patch("urllib.request.urlopen", _urlopen):
        delivery_id = run(s.send_interactive(
            tenant="shop1", to="+966500000000", body="نأكد لك موعدك؟",
            buttons=[{"id": "p1:confirm", "title": "تأكيد"}, {"id": "p1:cancel", "title": "إلغاء"}],
            idempotency_key="p1"))

    assert seen["url"] == "http://notification-service:8000/internal/notify/whatsapp/interactive"
    assert seen["header"] == "t"
    assert seen["body"]["type"] == "button"
    assert seen["body"]["tenant"] == "shop1"
    assert seen["body"]["recipient"] == "+966500000000"
    assert seen["body"]["buttons"] == [{"id": "p1:confirm", "title": "تأكيد"},
                                       {"id": "p1:cancel", "title": "إلغاء"}]
    assert seen["body"]["idempotency_key"] == "p1"
    assert delivery_id == "dlv_1"


def test_send_list_shapes_one_section_of_rows():
    s = sender()
    seen: dict = {}

    def _urlopen(req, timeout=0):
        seen["body"] = json.loads(req.data or b"{}")
        return _Resp({"status": "sent", "delivery_id": "dlv_2"})

    with patch("urllib.request.urlopen", _urlopen):
        run(s.send_list(
            tenant="shop1", to="+966500000000", body="كيف نقدر نساعدك؟", button_text="اختر",
            rows=[{"id": "triage:booking", "title": "حجز موعد", "description": ""},
                  {"id": "triage:complaint", "title": "شكوى"}],
            idempotency_key="triage_1"))

    assert seen["body"]["type"] == "list"
    assert seen["body"]["button_text"] == "اختر"
    assert seen["body"]["sections"] == [{"rows": [
        {"id": "triage:booking", "title": "حجز موعد"},
        {"id": "triage:complaint", "title": "شكوى"}]}]


def test_a_422_from_the_peers_own_spec_validation_raises_send_failed():
    """notification-service builds and limit-checks the interactive object server-side — a bad
    spec (a fourth button, an over-length title) comes back as a 422, not a Meta 400. This adapter
    surfaces it as SendFailed like any other send failure rather than swallowing it."""
    import urllib.error

    s = sender()

    def _urlopen(req, timeout=0):
        raise urllib.error.HTTPError(req.full_url, 422, "spec error", {}, None)

    with patch("urllib.request.urlopen", _urlopen):
        with pytest.raises(SendFailed):
            run(s.send_interactive(tenant="shop1", to="+9665", body="x", buttons=[],
                                   idempotency_key="k"))


def test_peer_unreachable_raises_send_failed():
    import urllib.error

    s = sender()

    def _urlopen(req, timeout=0):
        raise urllib.error.URLError("connection refused")

    with patch("urllib.request.urlopen", _urlopen):
        with pytest.raises(SendFailed):
            run(s.send_interactive(tenant="shop1", to="+9665", body="x", buttons=[],
                                   idempotency_key="k"))


# ── the real response shape, not the "ok" key that never existed ────────────────────────────────
# Found by ci/check_absent_means_ok.py: notification-service's real response is
# {"delivery_id", "status", "provider", ...} — "status" one of queued/sending/sent/suppressed/
# failed/dead_letter (platform core/retry.py). The old check read a nonexistent "ok" key with a
# `True` default, so a 2xx response NEVER raised SendFailed regardless of what actually happened.
def test_a_2xx_with_status_queued_is_not_a_success():
    s = sender()

    def _urlopen(req, timeout=0):
        return _Resp({"status": "queued", "delivery_id": "dlv_3", "retry_at": 123.0})

    with patch("urllib.request.urlopen", _urlopen):
        with pytest.raises(SendFailed, match="queued"):
            run(s.send_interactive(tenant="shop1", to="+9665", body="x", buttons=[],
                                   idempotency_key="k"))


def test_a_2xx_with_status_suppressed_is_not_a_success():
    s = sender()

    def _urlopen(req, timeout=0):
        return _Resp({"status": "suppressed", "delivery_id": "dlv_4"})

    with patch("urllib.request.urlopen", _urlopen):
        with pytest.raises(SendFailed, match="suppressed"):
            run(s.send_interactive(tenant="shop1", to="+9665", body="x", buttons=[],
                                   idempotency_key="k"))


def test_a_2xx_with_status_dead_letter_raises_with_the_real_error():
    s = sender()

    def _urlopen(req, timeout=0):
        return _Resp({"status": "dead_letter", "delivery_id": "dlv_5",
                     "error": "provider rejected: invalid recipient"})

    with patch("urllib.request.urlopen", _urlopen):
        with pytest.raises(SendFailed, match="invalid recipient"):
            run(s.send_interactive(tenant="shop1", to="+9665", body="x", buttons=[],
                                   idempotency_key="k"))


def test_a_2xx_with_no_status_at_all_is_refused_not_assumed_successful():
    """The old bug's own worst case: a malformed/empty body reads as `{}`, which used to default
    straight to success."""
    s = sender()

    def _urlopen(req, timeout=0):
        return _Resp({})

    with patch("urllib.request.urlopen", _urlopen):
        with pytest.raises(SendFailed):
            run(s.send_interactive(tenant="shop1", to="+9665", body="x", buttons=[],
                                   idempotency_key="k"))
