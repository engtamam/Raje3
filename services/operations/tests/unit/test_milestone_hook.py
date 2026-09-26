"""`record_visit`'s own "جماعي" milestone hook — the single choke point every visit-recording
channel (field screen, integrated till, bookings) already reaches, extended to campaigns' shared
counter, exactly the same shape the mutual-benefit hook right beside it already has.
"""
from __future__ import annotations

import asyncio

import pytest

from app.adapters.datastore.memory import MemoryDataStore
from app.core.operations import Operations

A = "tnt_alpha"
SALT = "s" * 32


def run(coro):
    return asyncio.run(coro)


class FakePeer:
    def __init__(self, boom: bool = False):
        self.calls: list[dict] = []
        self.boom = boom

    async def on_visit_recorded(self, *, tenant, subject_ref, service_ids=None,
                                package_id="", occurred_at=0):
        if self.boom:
            raise RuntimeError("campaigns unreachable")
        self.calls.append({
            "tenant": tenant, "subject_ref": subject_ref,
            "service_ids": list(service_ids or []), "package_id": package_id,
            "occurred_at": occurred_at,
        })


@pytest.fixture()
def ops():
    return Operations(store=MemoryDataStore(), pii_salt=SALT)


def test_no_peer_wired_is_a_harmless_no_op(ops):
    """`_milestone_peer` is `None` until `with_milestone_peer` installs one — the same posture
    every other optional peer on this class takes."""
    run(ops.record_visit(tenant=A, phone="0501234567", service_ids=["srv_1"]))


def test_a_real_visit_calls_the_peer_with_the_customers_subject_ref(ops):
    peer = FakePeer()
    ops.with_milestone_peer(peer)
    res = run(ops.record_visit(tenant=A, phone="0501234567", service_ids=["srv_1", "srv_2"]))
    assert len(peer.calls) == 1
    call = peer.calls[0]
    assert call["tenant"] == A
    assert call["subject_ref"] == res.customer.subject_ref
    assert call["subject_ref"], "a real customer must always carry a real subject_ref"
    assert call["service_ids"] == ["srv_1", "srv_2"]


def test_the_packages_own_id_travels_to_the_peer_too(ops):
    peer = FakePeer()
    ops.with_milestone_peer(peer)
    run(ops.record_visit(tenant=A, phone="0501234567", service_ids=["srv_1"],
                         package_id="pkg_1"))
    assert peer.calls[0]["package_id"] == "pkg_1"


def test_a_duplicate_tap_does_not_call_the_peer_a_second_time(ops):
    """The double-tap guard returns before any of `record_visit`'s own side-effect hooks run —
    the milestone peer must not see a visit that was never actually recorded twice."""
    peer = FakePeer()
    ops.with_milestone_peer(peer)
    run(ops.record_visit(tenant=A, phone="0501234567", service_ids=["srv_1"], idempotency_key="k1"))
    run(ops.record_visit(tenant=A, phone="0501234567", service_ids=["srv_1"], idempotency_key="k1"))
    assert len(peer.calls) == 1


def test_a_peer_failure_never_fails_the_visit(ops):
    """The one fact this product cannot survive losing — swallowed here exactly like the mutual-
    benefit hook right beside it, and the peer itself already swallows its own failure too (belt
    and braces, tested separately in test_milestone_peer.py)."""
    peer = FakePeer(boom=True)
    ops.with_milestone_peer(peer)
    res = run(ops.record_visit(tenant=A, phone="0501234567", service_ids=["srv_1"]))
    assert res.visit is not None
    assert res.duplicate is False


def test_two_different_tenants_visits_are_reported_under_their_own_tenant(ops):
    peer = FakePeer()
    ops.with_milestone_peer(peer)
    run(ops.record_visit(tenant=A, phone="0501234567", service_ids=["srv_1"]))
    run(ops.record_visit(tenant="tnt_beta", phone="0509999999", service_ids=["srv_1"]))
    assert {c["tenant"] for c in peer.calls} == {A, "tnt_beta"}
