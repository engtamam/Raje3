"""Operations.customer_success_flags — the two real, checkable "this shop may be stalling" signals.

Both bounded existence checks (has_any_active / has_any), never a scan or a count — see the
method's own docstring for why. These tests prove the boundary conditions: a fresh signup with no
services is not flagged before the stall window passes, a shop with services and at least one
visit is never flagged, and the two flags never both fire for the same tenant.
"""
from __future__ import annotations

import asyncio

from app.adapters.datastore.memory import MemoryDataStore
from app.core.models import Service, Visit
from app.core.operations import Operations
from app.core.stores import ServiceStore, VisitStore

SALT = "s" * 32
A = "tnt_alpha"
DAY = 86400


def run(coro):
    return asyncio.run(coro)


def test_a_fresh_signup_with_no_services_is_not_flagged_before_the_stall_window():
    store = MemoryDataStore()
    ops = Operations(store=store, pii_salt=SALT)
    now = 1_000_000.0
    flags = run(ops.customer_success_flags(A, created_at=now - DAY, now=now, stall_seconds=3 * DAY))
    assert flags == {"no_services_after_stall": False, "has_services_no_visits": False}


def test_a_signup_with_no_services_past_the_stall_window_is_flagged():
    store = MemoryDataStore()
    ops = Operations(store=store, pii_salt=SALT)
    now = 1_000_000.0
    flags = run(ops.customer_success_flags(A, created_at=now - 4 * DAY, now=now, stall_seconds=3 * DAY))
    assert flags["no_services_after_stall"] is True
    assert flags["has_services_no_visits"] is False   # never both — see the method's own docstring


def test_a_shop_with_services_but_zero_visits_is_flagged_regardless_of_age():
    store = MemoryDataStore()
    ops = Operations(store=store, pii_salt=SALT)
    run(ServiceStore(store).save(Service(id="svc_1", tenant=A, name="قص شعر", price_minor=1000)))
    now = 1_000_000.0
    # Old enough that the no-services stall would have fired if it still had none.
    flags = run(ops.customer_success_flags(A, created_at=now - 30 * DAY, now=now, stall_seconds=3 * DAY))
    assert flags == {"no_services_after_stall": False, "has_services_no_visits": True}


def test_a_shop_with_services_and_at_least_one_visit_is_never_flagged():
    store = MemoryDataStore()
    ops = Operations(store=store, pii_salt=SALT)
    run(ServiceStore(store).save(Service(id="svc_1", tenant=A, name="قص شعر", price_minor=1000)))
    run(VisitStore(store).save(Visit(id="v1", tenant=A, customer_id="cus_1", service_ids=["svc_1"])))
    now = 1_000_000.0
    flags = run(ops.customer_success_flags(A, created_at=now - 30 * DAY, now=now, stall_seconds=3 * DAY))
    assert flags == {"no_services_after_stall": False, "has_services_no_visits": False}
