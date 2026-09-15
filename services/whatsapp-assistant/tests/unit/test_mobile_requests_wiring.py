"""request_mobile_visit's own withheld-not-offered-and-refused gate (app/config.py's
llm_tool_allowlist), and app/adapters/mobile_requests::HttpMobileRequests — the one write this
whole feature ever makes, against operations' POST /internal/operations/mobile-requests."""
from __future__ import annotations

import asyncio
import json
from unittest.mock import patch

import pytest

from app.adapters.mobile_requests import HttpMobileRequests
from app.config import Settings
from app.ports.mobile_requests import CreatedMobileRequest, MobileRequestFailed


def test_the_tool_is_withheld_with_no_operations_service_url_wired():
    s = Settings(OPERATIONS_SERVICE_URL="")
    assert "request_mobile_visit" not in s.llm_tool_allowlist


def test_the_tool_is_offered_once_operations_service_url_is_wired():
    s = Settings(OPERATIONS_SERVICE_URL="http://operations-service:8000")
    assert "request_mobile_visit" in s.llm_tool_allowlist


def run(c):
    return asyncio.run(c)


def client() -> HttpMobileRequests:
    return HttpMobileRequests(
        url="http://operations-service:8000", path="/internal/operations/mobile-requests",
        hours_path="/internal/operations/mobile-visit-hours", token="t", timeout=8)


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


def test_create_posts_the_real_shape_and_returns_the_request_id():
    c = client()
    seen: dict = {}

    def _urlopen(req, timeout=0):
        seen["url"] = req.full_url
        seen["header"] = req.get_header("X-internal-token")
        seen["body"] = json.loads(req.data or b"{}")
        return _Resp({"created": True, "request_id": "mreq_abc"})

    with patch("urllib.request.urlopen", _urlopen):
        result = run(c.create(
            tenant="shop1", phone="+966500000000", customer_name="", service_ids=["svc_wash"],
            requested_time=1789376400, lat=24.7136, lng=46.6753))

    assert seen["url"] == "http://operations-service:8000/internal/operations/mobile-requests"
    assert seen["header"] == "t"
    assert seen["body"] == {"tenant": "shop1", "phone": "+966500000000", "customer_name": "",
                            "service_ids": ["svc_wash"], "requested_time": 1789376400,
                            "lat": 24.7136, "lng": 46.6753}
    assert isinstance(result, CreatedMobileRequest)
    assert result.request_id == "mreq_abc"


def test_operations_own_refusal_shape_is_surfaced_as_mobile_request_failed():
    """operations' door returns {"created": false, "reason": ...} rather than raising — this
    adapter turns that into the same exception a real peer outage raises, so the caller
    (core/conversation.py::handle_location) has exactly one failure shape to handle."""
    c = client()

    def _urlopen(req, timeout=0):
        return _Resp({"created": False, "reason": "no such service"})

    with patch("urllib.request.urlopen", _urlopen):
        with pytest.raises(MobileRequestFailed, match="no such service"):
            run(c.create(tenant="shop1", phone="+9665", customer_name="", service_ids=["x"],
                         requested_time=1789376400, lat=1.0, lng=1.0))


def test_peer_unreachable_raises_mobile_request_failed():
    import urllib.error

    c = client()

    def _urlopen(req, timeout=0):
        raise urllib.error.URLError("connection refused")

    with patch("urllib.request.urlopen", _urlopen):
        with pytest.raises(MobileRequestFailed):
            run(c.create(tenant="shop1", phone="+9665", customer_name="", service_ids=["x"],
                         requested_time=1789376400, lat=1.0, lng=1.0))


def test_hours_reads_the_shops_real_weekly_schedule():
    c = client()
    weekly = {str(d): {"closed": False, "start_minute": 540, "end_minute": 1260} for d in range(7)}
    seen: dict = {}

    def _urlopen(req, timeout=0):
        seen["url"] = req.full_url
        seen["header"] = req.get_header("X-internal-token")
        return _Resp({"weekly": weekly})

    with patch("urllib.request.urlopen", _urlopen):
        result = run(c.hours("shop1"))

    assert seen["url"] == "http://operations-service:8000/internal/operations/mobile-visit-hours?tenant=shop1"
    assert seen["header"] == "t"
    assert result == weekly


def test_hours_answers_none_when_the_peer_is_unreachable():
    import urllib.error

    c = client()

    def _urlopen(req, timeout=0):
        raise urllib.error.URLError("connection refused")

    with patch("urllib.request.urlopen", _urlopen):
        assert run(c.hours("shop1")) is None
