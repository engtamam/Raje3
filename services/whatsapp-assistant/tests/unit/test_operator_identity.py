"""HttpOperatorIdentity / NullOperatorIdentity — the WhatsApp-sender-to-operator resolution
visit-registration over WhatsApp needs before it may open the Flow for a staff sender."""
from __future__ import annotations

import asyncio
import json
import urllib.error
from unittest.mock import patch

from app.core.operator_identity import HttpOperatorIdentity, NullOperatorIdentity, build


def run(c):
    return asyncio.run(c)


def _resolver(page_size: int = 100):
    return HttpOperatorIdentity(
        identity_url="http://identity", members_path="/internal/tenancy/members",
        operations_url="http://operations", operator_by_person_path="/internal/operations/operator-by-person",
        token="itok", timeout=8, page_size=page_size)


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


def test_a_matching_active_member_resolves_to_the_operator():
    calls = []

    def _urlopen(req, timeout=0):
        calls.append(req.full_url)
        if "tenancy/members" in req.full_url:
            return _Resp({"tenant": "t1", "members": [
                {"person_id": "p1", "identifier": "+966500000001", "status": "active"},
            ], "next": ""})
        return _Resp({"operator_id": "op_1", "name": "سارة"})

    r = _resolver()
    with patch("urllib.request.urlopen", _urlopen):
        assert run(r.resolve(tenant="t1", from_number="966500000001")) == "op_1"
    assert len(calls) == 2


def test_punctuation_differences_between_e164_and_the_bare_inbound_number_still_match():
    def _urlopen(req, timeout=0):
        if "tenancy/members" in req.full_url:
            return _Resp({"members": [
                {"person_id": "p1", "identifier": "+966 50 000 0002", "status": "active"},
            ], "next": ""})
        return _Resp({"operator_id": "op_2", "name": "فهد"})

    with patch("urllib.request.urlopen", _urlopen):
        assert run(_resolver().resolve(tenant="t1", from_number="966500000002")) == "op_2"


def test_a_suspended_member_never_resolves():
    def _urlopen(req, timeout=0):
        return _Resp({"members": [
            {"person_id": "p1", "identifier": "+966500000003", "status": "suspended"},
        ], "next": ""})

    with patch("urllib.request.urlopen", _urlopen):
        assert run(_resolver().resolve(tenant="t1", from_number="966500000003")) == ""


def test_a_person_with_no_operator_row_resolves_to_empty():
    def _urlopen(req, timeout=0):
        if "tenancy/members" in req.full_url:
            return _Resp({"members": [
                {"person_id": "p1", "identifier": "+966500000004", "status": "active"},
            ], "next": ""})
        raise urllib.error.HTTPError("u", 404, "not found", {}, None)

    with patch("urllib.request.urlopen", _urlopen):
        assert run(_resolver().resolve(tenant="t1", from_number="966500000004")) == ""


def test_a_number_matching_nobody_resolves_to_empty():
    def _urlopen(req, timeout=0):
        return _Resp({"members": [
            {"person_id": "p1", "identifier": "+966500000005", "status": "active"},
        ], "next": ""})

    with patch("urllib.request.urlopen", _urlopen):
        assert run(_resolver().resolve(tenant="t1", from_number="966599999999")) == ""


def test_it_pages_through_the_member_directory():
    calls = []

    def _urlopen(req, timeout=0):
        calls.append(req.full_url)
        if "after=cur1" in req.full_url:
            return _Resp({"members": [
                {"person_id": "p2", "identifier": "+966500000006", "status": "active"},
            ], "next": ""})
        if "tenancy/members" in req.full_url:
            return _Resp({"members": [
                {"person_id": "p1", "identifier": "+966500000001", "status": "active"},
            ], "next": "cur1"})
        return _Resp({"operator_id": "op_6", "name": "عمر"})

    with patch("urllib.request.urlopen", _urlopen):
        assert run(_resolver(page_size=1).resolve(
            tenant="t1", from_number="966500000006")) == "op_6"
    assert len([c for c in calls if "tenancy/members" in c]) == 2


def test_an_unreachable_peer_resolves_to_empty_never_raises():
    with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("down")):
        assert run(_resolver().resolve(tenant="t1", from_number="966500000001")) == ""


def test_an_empty_tenant_or_number_resolves_to_empty_without_a_call():
    with patch("urllib.request.urlopen") as m:
        assert run(_resolver().resolve(tenant="", from_number="966500000001")) == ""
        assert run(_resolver().resolve(tenant="t1", from_number="")) == ""
        m.assert_not_called()


def test_null_operator_identity_always_resolves_to_empty():
    assert run(NullOperatorIdentity().resolve(tenant="t1", from_number="966500000001")) == ""


def test_build_falls_back_to_null_when_unconfigured():
    class _S:
        IDENTITY_SERVICE_URL = ""
        IDENTITY_TENANCY_MEMBERS_PATH = "/internal/tenancy/members"
        OPERATIONS_SERVICE_URL = ""
        OPERATIONS_OPERATOR_BY_PERSON_PATH = "/internal/operations/operator-by-person"
        INTERNAL_SERVICE_TOKEN = "itok"
        PEER_TIMEOUT_SECONDS = 8

    assert isinstance(build(_S()), NullOperatorIdentity)


def test_build_returns_the_real_adapter_when_configured():
    class _S:
        IDENTITY_SERVICE_URL = "http://identity"
        IDENTITY_TENANCY_MEMBERS_PATH = "/internal/tenancy/members"
        OPERATIONS_SERVICE_URL = "http://operations"
        OPERATIONS_OPERATOR_BY_PERSON_PATH = "/internal/operations/operator-by-person"
        INTERNAL_SERVICE_TOKEN = "itok"
        PEER_TIMEOUT_SECONDS = 8

    assert isinstance(build(_S()), HttpOperatorIdentity)
