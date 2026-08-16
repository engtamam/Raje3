"""ك-1: the field door must not be a way around the till door's own gate.

`POST /field/visits` needs only `operations.record` — the identical capability a till's own
machine credential carries — and used to ask nothing more of it. A shop that never bought
`feature.api` had its visits refused at `/till/visits` and accepted at `/field/visits` with the
same credential, and a retry with no stable key doubled the visit there too.
"""
from __future__ import annotations

import asyncio
import types

import pytest

from app.api.v1 import field as field_routes


class _MachinePrincipal:
    def __init__(self) -> None:
        self.tenant = "t_1"
        self.subject = "svc_pos"
        self.raw: dict = {}


class _HumanPrincipal:
    def __init__(self) -> None:
        self.tenant = "t_1"
        self.subject = "usr_42"
        self.raw: dict = {}


class _RefusingLicence:
    async def allowed(self, tenant):
        return False


class _AllowingLicence:
    async def allowed(self, tenant):
        return True


def _request(*, api_licence=None):
    container = types.SimpleNamespace(api_licence=api_licence)
    state = types.SimpleNamespace(container=container)
    return types.SimpleNamespace(app=types.SimpleNamespace(state=state))


def test_a_machine_credential_without_the_licence_is_refused_here_too():
    body = field_routes.VisitIn(phone="0500000000", service_ids=["s1"],
                                idempotency_key="key-1")
    request = _request(api_licence=_RefusingLicence())
    out = asyncio.run(field_routes.record_visit(
        request, body, background=None, principal=_MachinePrincipal()))
    assert out["recorded"] is False


def test_a_machine_credential_with_no_stable_key_is_refused():
    body = field_routes.VisitIn(phone="0500000000", service_ids=["s1"])
    request = _request(api_licence=_AllowingLicence())
    out = asyncio.run(field_routes.record_visit(
        request, body, background=None, principal=_MachinePrincipal()))
    assert out["recorded"] is False
    assert "idempotency_key" in out["reason"] or "occurred_at" in out["reason"]


def test_a_human_operator_is_never_gated_by_the_machine_check():
    """`is_machine_subject` must answer False for an ordinary user token — the field screen's
    everyday traffic must not start failing because it holds no idempotency_key either."""
    from app.core.licence import is_machine_subject
    assert is_machine_subject(_HumanPrincipal().subject) is False
    assert is_machine_subject(_MachinePrincipal().subject) is True


def test_a_machine_that_sends_only_a_timestamp_is_still_refused():
    """FOUND IN REVIEW, and it is the difference between the two doors.

    `till.py` accepts `idempotency_key` OR `invoice_id` OR `occurred_at` because `_key_for` DERIVES
    a stable key from whichever arrived. This door derives nothing: `record_visit` deduplicates on
    `idempotency_key` and on nothing else. So a rule copied from the till door would have refused
    the machine that sends neither, waved through the machine whose retry doubles the visit
    regardless, and told it in writing that its retry was safe — a guard that reads as protection
    and is not.
    """
    body = field_routes.VisitIn(phone="0500000000", service_ids=["s1"], occurred_at=1_800_000_000)
    request = _request(api_licence=_AllowingLicence())

    out = asyncio.run(field_routes.record_visit(
        request, body, background=None, principal=_MachinePrincipal()))

    assert out["recorded"] is False
    assert "idempotency_key" in out["reason"]
    assert "occurred_at" not in out["reason"], "the sentence must not promise what it cannot keep"
