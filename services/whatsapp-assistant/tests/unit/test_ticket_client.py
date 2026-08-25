"""HttpTicketClient — POST /internal/tickets via the real X-Internal-Token peer shape (a
corrected verification: an earlier version believed no such route existed and minted its own
HS256 credential instead — see app/adapters/ticket_client.py's module docstring), preceded by an
idempotent, per-tenant-per-process-cached write-grant upsert (POST /internal/tickets/shares) —
ticket-service's own model for any writer that is not the tenant's own staff.
"""
from __future__ import annotations

import asyncio
import json
from unittest.mock import patch

import pytest

from app.adapters.ticket_client import HttpTicketClient, TicketOpenFailed


def run(c):
    return asyncio.run(c)


def client():
    return HttpTicketClient(
        url="http://ticket-service:8000", tickets_path="/internal/tickets",
        shares_path="/internal/tickets/shares", token="t", grantee="whatsapp-assistant",
        ticket_type="support", share_ttl_seconds=0, timeout=8)


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


def test_first_ticket_for_a_tenant_upserts_the_write_grant_then_opens_the_ticket():
    c = client()
    calls: list[dict] = []

    def _urlopen(req, timeout=0):
        calls.append({"url": req.full_url, "header": req.get_header("X-internal-token"),
                     "body": json.loads(req.data or b"{}")})
        if req.full_url.endswith("/tickets/shares"):
            return _Resp({"granted": True})
        return _Resp({"id": "tkt_1"}, status=201)

    with patch("urllib.request.urlopen", _urlopen):
        result = run(c.open_ticket(tenant="shop1", subject="s", body="ملخص المحادثة",
                                   ref_id="t1|sub1", contact="+9665", priority="high"))

    assert len(calls) == 2
    assert calls[0]["url"] == "http://ticket-service:8000/internal/tickets/shares"
    assert calls[0]["header"] == "t"
    assert calls[0]["body"] == {"tenant": "shop1", "grantee": "whatsapp-assistant",
                                "permissions": ["read", "write"], "scope": {}, "ttl_seconds": 0}
    assert calls[1]["url"] == "http://ticket-service:8000/internal/tickets"
    assert calls[1]["header"] == "t"
    assert calls[1]["body"]["tenant"] == "shop1"
    assert calls[1]["body"]["grantee"] == "whatsapp-assistant"
    assert calls[1]["body"]["type"] == "support"
    assert calls[1]["body"]["priority"] == "high"
    assert calls[1]["body"]["metadata"]["contact"] == "+9665"
    assert calls[1]["body"]["ref"] == {"kind": "whatsapp_conversation", "id": "t1|sub1"}
    assert result["id"] == "tkt_1"


def test_a_second_ticket_for_the_same_tenant_does_not_re_upsert_the_grant():
    c = client()
    calls: list[str] = []

    def _urlopen(req, timeout=0):
        calls.append(req.full_url)
        if req.full_url.endswith("/tickets/shares"):
            return _Resp({"granted": True})
        return _Resp({"id": "tkt_x"}, status=201)

    with patch("urllib.request.urlopen", _urlopen):
        run(c.open_ticket(tenant="shop1", subject="a", body="b", ref_id="r1"))
        run(c.open_ticket(tenant="shop1", subject="a2", body="b2", ref_id="r2"))

    assert calls.count("http://ticket-service:8000/internal/tickets/shares") == 1
    assert calls.count("http://ticket-service:8000/internal/tickets") == 2


def test_a_different_tenant_gets_its_own_grant_upsert():
    c = client()
    calls: list[str] = []

    def _urlopen(req, timeout=0):
        calls.append(req.full_url)
        if req.full_url.endswith("/tickets/shares"):
            return _Resp({"granted": True})
        return _Resp({"id": "tkt_x"}, status=201)

    with patch("urllib.request.urlopen", _urlopen):
        run(c.open_ticket(tenant="shop1", subject="a", body="b", ref_id="r1"))
        run(c.open_ticket(tenant="shop2", subject="a", body="b", ref_id="r2"))

    assert calls.count("http://ticket-service:8000/internal/tickets/shares") == 2


def test_ticket_service_unreachable_raises_ticket_open_failed_not_a_false_success():
    import urllib.error

    c = client()

    def _urlopen(req, timeout=0):
        raise urllib.error.URLError("connection refused")

    with patch("urllib.request.urlopen", _urlopen):
        with pytest.raises(TicketOpenFailed):
            run(c.open_ticket(tenant="shop1", subject="a", body="b", ref_id="r1"))
