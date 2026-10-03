"""WhatsApp Direct Ordering — the engine only (core/orders.py). Real `MemoryDataStore` throughout
(not a fake) because the idempotency-claim race test below needs the store's own real `claim()`
atomicity, the same reason `test_hire_is_not_racy_across_tenants.py` insists on it for signup.
"""
from __future__ import annotations

import asyncio
import threading

import pytest

from app.adapters.datastore.memory import MemoryDataStore
from app.core.models import Branch, Service
from app.core.operations import Operations
from app.core.orders import (CONFIRMED, DELIVERED, OUT_FOR_DELIVERY, PAYMENT_MISMATCH, PREPARING,
                             READY, RECEIVED, OrderError, OrderService)
from app.core.stores import BranchStore, ServiceStore

CC = "966"
TENANT = "tnt_orders_1"
PHONE = "0501234567"
LAT, LNG = 24.7136, 46.6753


def run(c):
    return asyncio.run(c)


@pytest.fixture()
def svc():
    store = MemoryDataStore()
    ops = Operations(store=store, pii_salt="s" * 32)
    branches = BranchStore(store)
    services = ServiceStore(store)
    return OrderService(store=store, services=services, branches=branches, operations=ops), store


async def _seed(store, *, price_minor: int = 2500, active: bool = True,
                branch_active: bool = True) -> tuple[str, str]:
    services = ServiceStore(store)
    branches = BranchStore(store)
    sid = "svc_item"
    await services.save(Service(id=sid, tenant=TENANT, name="قهوة", price_minor=price_minor,
                                active=active))
    bid = "br_main"
    await branches.save(Branch(id=bid, tenant=TENANT, name="الفرع الرئيسي", active=branch_active))
    return sid, bid


# ── creation: pricing is always computed server-side ───────────────────────────────────────────
def test_total_is_computed_from_the_catalogue_never_trusted_from_the_caller(svc):
    s, store = svc
    sid, bid = run(_seed(store, price_minor=2500))
    order = run(s.create(tenant=TENANT, branch_id=bid, phone=PHONE, customer_name="سارة",
                         items=[(sid, 3)], lat=LAT, lng=LNG, idempotency_key="evt_1"))
    assert order.total_minor == 7500
    assert order.status == RECEIVED
    assert order.lines[0].unit_price_minor == 2500


def test_duplicate_lines_are_merged_before_pricing(svc):
    s, store = svc
    sid, bid = run(_seed(store, price_minor=1000))
    order = run(s.create(tenant=TENANT, branch_id=bid, phone=PHONE, customer_name="سارة",
                         items=[(sid, 2), (sid, 1)], lat=LAT, lng=LNG, idempotency_key="evt_2"))
    assert len(order.lines) == 1
    assert order.lines[0].quantity == 3
    assert order.total_minor == 3000


def test_an_inactive_service_is_refused(svc):
    s, store = svc
    sid, bid = run(_seed(store, active=False))
    with pytest.raises(OrderError):
        run(s.create(tenant=TENANT, branch_id=bid, phone=PHONE, customer_name="سارة",
                     items=[(sid, 1)], lat=LAT, lng=LNG, idempotency_key="evt_3"))


def test_an_unpriced_service_is_refused(svc):
    s, store = svc
    sid, bid = run(_seed(store, price_minor=0))
    with pytest.raises(OrderError):
        run(s.create(tenant=TENANT, branch_id=bid, phone=PHONE, customer_name="سارة",
                     items=[(sid, 1)], lat=LAT, lng=LNG, idempotency_key="evt_4"))


def test_an_inactive_branch_is_refused(svc):
    s, store = svc
    sid, bid = run(_seed(store, branch_active=False))
    with pytest.raises(OrderError):
        run(s.create(tenant=TENANT, branch_id=bid, phone=PHONE, customer_name="سارة",
                     items=[(sid, 1)], lat=LAT, lng=LNG, idempotency_key="evt_5"))


def test_an_invalid_location_is_refused(svc):
    s, store = svc
    sid, bid = run(_seed(store))
    with pytest.raises(OrderError):
        run(s.create(tenant=TENANT, branch_id=bid, phone=PHONE, customer_name="سارة",
                     items=[(sid, 1)], lat=999, lng=LNG, idempotency_key="evt_6"))


def test_an_excessive_quantity_is_refused(svc):
    s, store = svc
    sid, bid = run(_seed(store))
    with pytest.raises(OrderError):
        run(s.create(tenant=TENANT, branch_id=bid, phone=PHONE, customer_name="سارة",
                     items=[(sid, 10_000)], lat=LAT, lng=LNG, idempotency_key="evt_7"))


def test_no_idempotency_key_is_refused(svc):
    s, store = svc
    sid, bid = run(_seed(store))
    with pytest.raises(OrderError):
        run(s.create(tenant=TENANT, branch_id=bid, phone=PHONE, customer_name="سارة",
                     items=[(sid, 1)], lat=LAT, lng=LNG, idempotency_key=""))


# ── idempotency: a retried webhook event must return the SAME order, never a second one ───────
def test_the_same_idempotency_key_never_creates_a_second_order(svc):
    s, store = svc
    sid, bid = run(_seed(store))
    first = run(s.create(tenant=TENANT, branch_id=bid, phone=PHONE, customer_name="سارة",
                         items=[(sid, 1)], lat=LAT, lng=LNG, idempotency_key="evt_dup"))
    second = run(s.create(tenant=TENANT, branch_id=bid, phone=PHONE, customer_name="سارة",
                          items=[(sid, 1)], lat=LAT, lng=LNG, idempotency_key="evt_dup"))
    assert first.id == second.id
    rows = run(s.list(TENANT))
    assert len(rows) == 1


def test_two_concurrent_deliveries_of_the_same_webhook_event_never_both_create_an_order(svc):
    """The real race a WhatsApp webhook retry produces: two calls for the SAME event, overlapping
    in time, not one-after-another. Forces the interleaving with a real threading.Event the same
    way `test_hire_is_not_racy_across_tenants.py` does for signup's own claim lane."""
    s, store = svc
    sid, bid = run(_seed(store))
    gate = threading.Event()
    first_in_flight = threading.Event()

    real_claim = store.claim

    async def gated_claim(*args, **kwargs):
        won = await real_claim(*args, **kwargs)
        if won and not first_in_flight.is_set():
            first_in_flight.set()
            await asyncio.get_event_loop().run_in_executor(None, gate.wait, 5)
        return won

    store.claim = gated_claim

    async def scenario():
        first = asyncio.ensure_future(
            s.create(tenant=TENANT, branch_id=bid, phone=PHONE, customer_name="سارة",
                     items=[(sid, 1)], lat=LAT, lng=LNG, idempotency_key="evt_race"))
        while not first_in_flight.is_set():
            await asyncio.sleep(0)
        second_refused = False
        try:
            await s.create(tenant=TENANT, branch_id=bid, phone=PHONE, customer_name="سارة",
                           items=[(sid, 1)], lat=LAT, lng=LNG, idempotency_key="evt_race")
        except OrderError:
            second_refused = True
        gate.set()
        first_order = await first
        return first_order, second_refused

    first_order, second_refused = run(scenario())
    assert first_order.id
    assert second_refused, "the second concurrent delivery must be refused, not create a duplicate"
    rows = run(s.list(TENANT))
    assert len(rows) == 1


# ── payment: amount-checked, never trust-the-webhook ───────────────────────────────────────────
def test_exact_payment_confirms_the_order(svc):
    s, store = svc
    sid, bid = run(_seed(store, price_minor=5000))
    order = run(s.create(tenant=TENANT, branch_id=bid, phone=PHONE, customer_name="سارة",
                         items=[(sid, 1)], lat=LAT, lng=LNG, idempotency_key="evt_pay_1"))
    confirmed = run(s.confirm_payment(TENANT, order.id, paid_amount_minor=5000,
                                      payment_ref="pay_1"))
    assert confirmed.status == CONFIRMED
    assert confirmed.confirmed_at > 0


def test_a_mismatched_amount_is_parked_not_guessed(svc):
    s, store = svc
    sid, bid = run(_seed(store, price_minor=5000))
    order = run(s.create(tenant=TENANT, branch_id=bid, phone=PHONE, customer_name="سارة",
                         items=[(sid, 1)], lat=LAT, lng=LNG, idempotency_key="evt_pay_2"))
    mismatched = run(s.confirm_payment(TENANT, order.id, paid_amount_minor=4000,
                                       payment_ref="pay_2"))
    assert mismatched.status == PAYMENT_MISMATCH
    resolved = run(s.resolve_mismatch(TENANT, order.id, actor="owner"))
    assert resolved.status == CONFIRMED


def test_the_same_payment_reference_confirming_twice_is_a_no_op(svc):
    s, store = svc
    sid, bid = run(_seed(store, price_minor=5000))
    order = run(s.create(tenant=TENANT, branch_id=bid, phone=PHONE, customer_name="سارة",
                         items=[(sid, 1)], lat=LAT, lng=LNG, idempotency_key="evt_pay_3"))
    run(s.confirm_payment(TENANT, order.id, paid_amount_minor=5000, payment_ref="pay_3"))
    again = run(s.confirm_payment(TENANT, order.id, paid_amount_minor=5000, payment_ref="pay_3"))
    assert again.status == CONFIRMED


def test_a_second_distinct_payment_reference_is_refused_never_silently_accepted(svc):
    s, store = svc
    sid, bid = run(_seed(store, price_minor=5000))
    order = run(s.create(tenant=TENANT, branch_id=bid, phone=PHONE, customer_name="سارة",
                         items=[(sid, 1)], lat=LAT, lng=LNG, idempotency_key="evt_pay_4"))
    run(s.confirm_payment(TENANT, order.id, paid_amount_minor=5000, payment_ref="pay_4a"))
    with pytest.raises(OrderError):
        run(s.confirm_payment(TENANT, order.id, paid_amount_minor=5000, payment_ref="pay_4b"))


# ── fulfilment: forward only ────────────────────────────────────────────────────────────────────
def test_the_full_lifecycle_in_order(svc):
    s, store = svc
    sid, bid = run(_seed(store, price_minor=3000))
    order = run(s.create(tenant=TENANT, branch_id=bid, phone=PHONE, customer_name="سارة",
                         items=[(sid, 2)], lat=LAT, lng=LNG, idempotency_key="evt_life"))
    run(s.confirm_payment(TENANT, order.id, paid_amount_minor=6000, payment_ref="pay_life"))
    run(s.start_preparing(TENANT, order.id))
    run(s.mark_ready(TENANT, order.id))
    run(s.start_delivery(TENANT, order.id))
    done = run(s.complete(TENANT, order.id))
    assert done.status == DELIVERED
    assert done.visit_id


def test_skipping_a_stage_is_refused(svc):
    s, store = svc
    sid, bid = run(_seed(store))
    order = run(s.create(tenant=TENANT, branch_id=bid, phone=PHONE, customer_name="سارة",
                         items=[(sid, 1)], lat=LAT, lng=LNG, idempotency_key="evt_skip"))
    with pytest.raises(OrderError):
        run(s.start_preparing(TENANT, order.id))  # never confirmed


def test_cannot_start_preparing_an_unpaid_order(svc):
    s, store = svc
    sid, bid = run(_seed(store))
    order = run(s.create(tenant=TENANT, branch_id=bid, phone=PHONE, customer_name="سارة",
                         items=[(sid, 1)], lat=LAT, lng=LNG, idempotency_key="evt_unpaid"))
    with pytest.raises(OrderError):
        run(s.start_preparing(TENANT, order.id))


def test_cancellation_is_refused_once_preparation_has_started(svc):
    s, store = svc
    sid, bid = run(_seed(store, price_minor=1000))
    order = run(s.create(tenant=TENANT, branch_id=bid, phone=PHONE, customer_name="سارة",
                         items=[(sid, 1)], lat=LAT, lng=LNG, idempotency_key="evt_cancel"))
    run(s.confirm_payment(TENANT, order.id, paid_amount_minor=1000, payment_ref="pay_cancel"))
    run(s.start_preparing(TENANT, order.id))
    with pytest.raises(OrderError):
        run(s.cancel(TENANT, order.id, reason="غيّر رأيه"))


def test_cancellation_before_preparation_is_allowed(svc):
    s, store = svc
    sid, bid = run(_seed(store))
    order = run(s.create(tenant=TENANT, branch_id=bid, phone=PHONE, customer_name="سارة",
                         items=[(sid, 1)], lat=LAT, lng=LNG, idempotency_key="evt_cancel2"))
    cancelled = run(s.cancel(TENANT, order.id, reason="غيّر رأيه"))
    assert cancelled.status == "cancelled"
    with pytest.raises(OrderError):
        run(s.confirm_payment(TENANT, order.id, paid_amount_minor=2500, payment_ref="late_pay"))
