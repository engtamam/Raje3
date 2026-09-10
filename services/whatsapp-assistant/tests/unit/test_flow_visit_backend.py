"""FlowVisitBackend — this service's half of visit-registration over WhatsApp. Speaks the same
{options, reserve} shape as flow_booking_backend.py's own BookingEngine port (platform
v0.19.16/v0.19.17 — verified, no more "engine not yet built" placeholder)."""
from __future__ import annotations

import asyncio
import json
import urllib.error
from unittest.mock import patch

from app.core.flow_visit_backend import FlowVisitBackend


def run(c):
    return asyncio.run(c)


class _Catalog:
    def __init__(self, services=None):
        self._services = services or [{"id": "svc_1", "name": "غسلة خارجية"}]

    async def list_active(self, tenant):
        return self._services


class _Identity:
    def __init__(self, operator_id="op_1"):
        self._id = operator_id
        self.calls = []

    async def resolve(self, *, tenant, from_number):
        self.calls.append((tenant, from_number))
        return self._id


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


def _backend(**kw):
    return FlowVisitBackend(
        catalog=kw.get("catalog", _Catalog()), operator_identity=kw.get("identity", _Identity()),
        visits_url="http://operations", visits_path="/internal/operations/visits/from-whatsapp",
        token="itok", timeout=8)


def test_options_for_service_lists_the_active_catalogue():
    b = _backend(catalog=_Catalog([{"id": "svc_1", "name": "غسلة"}, {"id": "svc_2", "name": "تلميع"}]))
    out = run(b.options(tenant="t1", dimension="service", chosen={}))
    assert out == [{"id": "svc_1", "title": "غسلة"}, {"id": "svc_2", "title": "تلميع"}]


def test_options_for_an_unknown_dimension_is_empty():
    b = _backend()
    assert run(b.options(tenant="t1", dimension="whatever", chosen={})) == []


def test_reserve_with_no_customer_refuses():
    b = _backend()
    out = run(b.reserve(tenant="t1", selection={"phone": "966500000002", "service": ["svc_1"]},
                        idempotency_key="k1", customer=""))
    assert out["ok"] is False


def test_reserve_with_no_phone_refuses():
    b = _backend()
    out = run(b.reserve(tenant="t1", selection={"service": ["svc_1"]}, idempotency_key="k1",
                        customer="966500000001"))
    assert out["ok"] is False


def test_reserve_with_no_service_refuses():
    b = _backend()
    out = run(b.reserve(tenant="t1", selection={"phone": "966500000002"}, idempotency_key="k1",
                        customer="966500000001"))
    assert out["ok"] is False


def test_reserve_with_an_empty_service_list_refuses():
    b = _backend()
    out = run(b.reserve(tenant="t1", selection={"phone": "966500000002", "service": []},
                        idempotency_key="k1", customer="966500000001"))
    assert out["ok"] is False


def test_reserve_sends_every_chosen_service_the_multi_select_case():
    identity = _Identity(operator_id="op_9")
    b = _backend(identity=identity)
    seen = {}

    def _urlopen(req, timeout=0):
        seen["body"] = json.loads(req.data)
        return _Resp({"recorded": True, "visit_id": "vst_1", "duplicate": False})

    with patch("urllib.request.urlopen", _urlopen):
        out = run(b.reserve(
            tenant="t1", selection={"phone": "966500000002", "service": ["svc_1", "svc_2"]},
            idempotency_key="k1", customer="966500000001"))
    assert out == {"ok": True, "ref": "vst_1"}
    assert seen["body"]["service_ids"] == ["svc_1", "svc_2"]


def test_reserve_resolves_operator_from_the_sender_never_trusts_selection():
    identity = _Identity(operator_id="op_9")
    b = _backend(identity=identity)
    seen = {}

    def _urlopen(req, timeout=0):
        seen["body"] = json.loads(req.data)
        return _Resp({"recorded": True, "visit_id": "vst_1", "duplicate": False})

    with patch("urllib.request.urlopen", _urlopen):
        out = run(b.reserve(
            tenant="t1", selection={"phone": "966500000002", "service": ["svc_1"],
                                    "operator_id": "op_fake"},
            idempotency_key="k1", customer="966500000001"))
    assert out == {"ok": True, "ref": "vst_1"}
    assert seen["body"]["operator_id"] == "op_9"   # never "op_fake" from selection
    assert identity.calls == [("t1", "966500000001")]


def test_a_refused_write_is_reported_not_raised():
    b = _backend()

    def _urlopen(req, timeout=0):
        return _Resp({"recorded": False, "reason": "لا توجد خدمة بهذا الاسم"})

    with patch("urllib.request.urlopen", _urlopen):
        out = run(b.reserve(tenant="t1", selection={"phone": "966500000002", "service": ["svc_1"]},
                            idempotency_key="k1", customer="966500000001"))
    assert out == {"ok": False, "reason": "لا توجد خدمة بهذا الاسم"}


def test_an_unreachable_peer_is_reported_not_raised():
    b = _backend()
    with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("down")):
        out = run(b.reserve(tenant="t1", selection={"phone": "966500000002", "service": ["svc_1"]},
                            idempotency_key="k1", customer="966500000001"))
    assert out["ok"] is False
