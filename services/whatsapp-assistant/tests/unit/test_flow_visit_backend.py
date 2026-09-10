"""FlowVisitBackend — this service's half of visit-registration over WhatsApp (see
core/flow_visit_backend.py's own module docstring for the engine-agnostic op contract)."""
from __future__ import annotations

import asyncio
import json
from unittest.mock import patch

from app.core.flow_visit_backend import FlowVisitBackend


def run(c):
    return asyncio.run(c)


class _Service:
    def __init__(self, id_, name):
        self.id = id_
        self.name = name


class _Catalog:
    def __init__(self, services=None):
        self._services = services or [_Service("svc_1", "غسلة خارجية")]

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


def test_identify_reports_known_when_the_sender_resolves():
    b = _backend()
    out = run(b.identify(tenant="t1", customer="966500000001"))
    assert out == {"known": True}


def test_identify_reports_unknown_when_the_sender_does_not_resolve():
    b = _backend(identity=_Identity(operator_id=""))
    out = run(b.identify(tenant="t1", customer="966500000001"))
    assert out == {"known": False}


def test_options_for_service_lists_the_active_catalogue():
    b = _backend(catalog=_Catalog([_Service("svc_1", "غسلة"), _Service("svc_2", "تلميع")]))
    out = run(b.options(tenant="t1", dimension="service", chosen={}))
    assert out == [{"id": "svc_1", "title": "غسلة"}, {"id": "svc_2", "title": "تلميع"}]


def test_options_for_an_unknown_dimension_is_empty():
    b = _backend()
    assert run(b.options(tenant="t1", dimension="whatever", chosen={})) == []


def test_reserve_with_no_customer_refuses():
    b = _backend()
    out = run(b.reserve(tenant="t1", selection={"phone": "966500000002", "service": "svc_1"},
                        idempotency_key="k1", customer=""))
    assert out["ok"] is False


def test_reserve_with_no_phone_refuses():
    b = _backend()
    out = run(b.reserve(tenant="t1", selection={"service": "svc_1"}, idempotency_key="k1",
                        customer="966500000001"))
    assert out["ok"] is False


def test_reserve_with_no_service_refuses():
    b = _backend()
    out = run(b.reserve(tenant="t1", selection={"phone": "966500000002"}, idempotency_key="k1",
                        customer="966500000001"))
    assert out["ok"] is False


def test_reserve_resolves_operator_from_the_sender_never_trusts_selection():
    identity = _Identity(operator_id="op_9")
    b = _backend(identity=identity)
    seen = {}

    def _urlopen(req, timeout=0):
        seen["body"] = json.loads(req.data)
        return _Resp({"recorded": True, "visit_id": "vst_1", "duplicate": False})

    with patch("urllib.request.urlopen", _urlopen):
        out = run(b.reserve(
            tenant="t1", selection={"phone": "966500000002", "service": "svc_1",
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
        out = run(b.reserve(tenant="t1", selection={"phone": "966500000002", "service": "svc_1"},
                            idempotency_key="k1", customer="966500000001"))
    assert out == {"ok": False, "reason": "لا توجد خدمة بهذا الاسم"}


def test_an_unreachable_peer_is_reported_not_raised():
    import urllib.error

    b = _backend()
    with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("down")):
        out = run(b.reserve(tenant="t1", selection={"phone": "966500000002", "service": "svc_1"},
                            idempotency_key="k1", customer="966500000001"))
    assert out["ok"] is False
