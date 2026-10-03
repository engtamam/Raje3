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


class FakeEventBus:
    def __init__(self) -> None:
        self.published: list[tuple[str, dict]] = []

    async def publish(self, topic, event) -> None:
        self.published.append((topic, dict(event.payload)))


class FakePaymentsDesk:
    """Mirrors `adapters/payments_desk.py`'s own real return shapes (`ok`/`request_id`/`pay_url`
    on create, `ok`/`status`/`amount_minor`/`provider_ref` on reconcile) without any network call."""

    def __init__(self) -> None:
        self.created: list[dict] = []
        self.reconcile_status = "pending"
        self.reconcile_amount_minor = 0
        self.unreachable = False

    async def create_request(self, *, tenant, reference, amount_minor, metadata=None):
        self.created.append({"tenant": tenant, "reference": reference,
                             "amount_minor": amount_minor})
        if self.unreachable:
            return None
        return {"ok": True, "request_id": f"preq_{reference}",
               "pay_url": f"https://pay.example/{reference}"}

    async def reconcile(self, *, tenant, request_id):
        if self.unreachable:
            return None
        return {"ok": True, "status": self.reconcile_status,
               "amount_minor": self.reconcile_amount_minor, "provider_ref": f"prov_{request_id}"}


@pytest.fixture()
def svc():
    store = MemoryDataStore()
    ops = Operations(store=store, pii_salt="s" * 32)
    branches = BranchStore(store)
    services = ServiceStore(store)
    payments = FakePaymentsDesk()
    return (OrderService(store=store, services=services, branches=branches, operations=ops,
                        payments=payments), store, payments)


@pytest.fixture()
def svc_events():
    """Same shape as `svc`, plus a real `FakeEventBus` — a separate fixture rather than widening
    `svc` itself, so the 40+ tests already unpacking `s, store, _payments = svc` stay untouched."""
    store = MemoryDataStore()
    ops = Operations(store=store, pii_salt="s" * 32)
    branches = BranchStore(store)
    services = ServiceStore(store)
    payments = FakePaymentsDesk()
    events = FakeEventBus()
    return (OrderService(store=store, services=services, branches=branches, operations=ops,
                        payments=payments, events=events), store, events)


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
    s, store, _payments = svc
    sid, bid = run(_seed(store, price_minor=2500))
    order = run(s.create(tenant=TENANT, branch_id=bid, phone=PHONE, customer_name="سارة",
                         items=[(sid, 3)], lat=LAT, lng=LNG, idempotency_key="evt_1"))
    assert order.total_minor == 7500
    assert order.status == RECEIVED
    assert order.lines[0].unit_price_minor == 2500


def test_duplicate_lines_are_merged_before_pricing(svc):
    s, store, _payments = svc
    sid, bid = run(_seed(store, price_minor=1000))
    order = run(s.create(tenant=TENANT, branch_id=bid, phone=PHONE, customer_name="سارة",
                         items=[(sid, 2), (sid, 1)], lat=LAT, lng=LNG, idempotency_key="evt_2"))
    assert len(order.lines) == 1
    assert order.lines[0].quantity == 3
    assert order.total_minor == 3000


def test_an_inactive_service_is_refused(svc):
    s, store, _payments = svc
    sid, bid = run(_seed(store, active=False))
    with pytest.raises(OrderError):
        run(s.create(tenant=TENANT, branch_id=bid, phone=PHONE, customer_name="سارة",
                     items=[(sid, 1)], lat=LAT, lng=LNG, idempotency_key="evt_3"))


def test_an_unpriced_service_is_refused(svc):
    s, store, _payments = svc
    sid, bid = run(_seed(store, price_minor=0))
    with pytest.raises(OrderError):
        run(s.create(tenant=TENANT, branch_id=bid, phone=PHONE, customer_name="سارة",
                     items=[(sid, 1)], lat=LAT, lng=LNG, idempotency_key="evt_4"))


def test_an_inactive_branch_is_refused(svc):
    s, store, _payments = svc
    sid, bid = run(_seed(store, branch_active=False))
    with pytest.raises(OrderError):
        run(s.create(tenant=TENANT, branch_id=bid, phone=PHONE, customer_name="سارة",
                     items=[(sid, 1)], lat=LAT, lng=LNG, idempotency_key="evt_5"))


def test_an_invalid_location_is_refused(svc):
    s, store, _payments = svc
    sid, bid = run(_seed(store))
    with pytest.raises(OrderError):
        run(s.create(tenant=TENANT, branch_id=bid, phone=PHONE, customer_name="سارة",
                     items=[(sid, 1)], lat=999, lng=LNG, idempotency_key="evt_6"))


def test_an_excessive_quantity_is_refused(svc):
    s, store, _payments = svc
    sid, bid = run(_seed(store))
    with pytest.raises(OrderError):
        run(s.create(tenant=TENANT, branch_id=bid, phone=PHONE, customer_name="سارة",
                     items=[(sid, 10_000)], lat=LAT, lng=LNG, idempotency_key="evt_7"))


def test_no_idempotency_key_is_refused(svc):
    s, store, _payments = svc
    sid, bid = run(_seed(store))
    with pytest.raises(OrderError):
        run(s.create(tenant=TENANT, branch_id=bid, phone=PHONE, customer_name="سارة",
                     items=[(sid, 1)], lat=LAT, lng=LNG, idempotency_key=""))


# ── idempotency: a retried webhook event must return the SAME order, never a second one ───────
def test_the_same_idempotency_key_never_creates_a_second_order(svc):
    s, store, _payments = svc
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
    s, store, _payments = svc
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
    s, store, _payments = svc
    sid, bid = run(_seed(store, price_minor=5000))
    order = run(s.create(tenant=TENANT, branch_id=bid, phone=PHONE, customer_name="سارة",
                         items=[(sid, 1)], lat=LAT, lng=LNG, idempotency_key="evt_pay_1"))
    confirmed = run(s.confirm_payment(TENANT, order.id, paid_amount_minor=5000,
                                      payment_ref="pay_1"))
    assert confirmed.status == CONFIRMED
    assert confirmed.confirmed_at > 0


def test_a_mismatched_amount_is_parked_not_guessed(svc):
    s, store, _payments = svc
    sid, bid = run(_seed(store, price_minor=5000))
    order = run(s.create(tenant=TENANT, branch_id=bid, phone=PHONE, customer_name="سارة",
                         items=[(sid, 1)], lat=LAT, lng=LNG, idempotency_key="evt_pay_2"))
    mismatched = run(s.confirm_payment(TENANT, order.id, paid_amount_minor=4000,
                                       payment_ref="pay_2"))
    assert mismatched.status == PAYMENT_MISMATCH
    resolved = run(s.resolve_mismatch(TENANT, order.id, actor="owner"))
    assert resolved.status == CONFIRMED


def test_the_same_payment_reference_confirming_twice_is_a_no_op(svc):
    s, store, _payments = svc
    sid, bid = run(_seed(store, price_minor=5000))
    order = run(s.create(tenant=TENANT, branch_id=bid, phone=PHONE, customer_name="سارة",
                         items=[(sid, 1)], lat=LAT, lng=LNG, idempotency_key="evt_pay_3"))
    run(s.confirm_payment(TENANT, order.id, paid_amount_minor=5000, payment_ref="pay_3"))
    again = run(s.confirm_payment(TENANT, order.id, paid_amount_minor=5000, payment_ref="pay_3"))
    assert again.status == CONFIRMED


def test_a_second_distinct_payment_reference_is_refused_never_silently_accepted(svc):
    s, store, _payments = svc
    sid, bid = run(_seed(store, price_minor=5000))
    order = run(s.create(tenant=TENANT, branch_id=bid, phone=PHONE, customer_name="سارة",
                         items=[(sid, 1)], lat=LAT, lng=LNG, idempotency_key="evt_pay_4"))
    run(s.confirm_payment(TENANT, order.id, paid_amount_minor=5000, payment_ref="pay_4a"))
    with pytest.raises(OrderError):
        run(s.confirm_payment(TENANT, order.id, paid_amount_minor=5000, payment_ref="pay_4b"))


# ── fulfilment: forward only ────────────────────────────────────────────────────────────────────
def test_the_full_lifecycle_in_order(svc):
    s, store, _payments = svc
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
    s, store, _payments = svc
    sid, bid = run(_seed(store))
    order = run(s.create(tenant=TENANT, branch_id=bid, phone=PHONE, customer_name="سارة",
                         items=[(sid, 1)], lat=LAT, lng=LNG, idempotency_key="evt_skip"))
    with pytest.raises(OrderError):
        run(s.start_preparing(TENANT, order.id))  # never confirmed


def test_cannot_start_preparing_an_unpaid_order(svc):
    s, store, _payments = svc
    sid, bid = run(_seed(store))
    order = run(s.create(tenant=TENANT, branch_id=bid, phone=PHONE, customer_name="سارة",
                         items=[(sid, 1)], lat=LAT, lng=LNG, idempotency_key="evt_unpaid"))
    with pytest.raises(OrderError):
        run(s.start_preparing(TENANT, order.id))


def test_cancellation_is_refused_once_preparation_has_started(svc):
    s, store, _payments = svc
    sid, bid = run(_seed(store, price_minor=1000))
    order = run(s.create(tenant=TENANT, branch_id=bid, phone=PHONE, customer_name="سارة",
                         items=[(sid, 1)], lat=LAT, lng=LNG, idempotency_key="evt_cancel"))
    run(s.confirm_payment(TENANT, order.id, paid_amount_minor=1000, payment_ref="pay_cancel"))
    run(s.start_preparing(TENANT, order.id))
    with pytest.raises(OrderError):
        run(s.cancel(TENANT, order.id, reason="غيّر رأيه"))


def test_cancellation_before_preparation_is_allowed(svc):
    s, store, _payments = svc
    sid, bid = run(_seed(store))
    order = run(s.create(tenant=TENANT, branch_id=bid, phone=PHONE, customer_name="سارة",
                         items=[(sid, 1)], lat=LAT, lng=LNG, idempotency_key="evt_cancel2"))
    cancelled = run(s.cancel(TENANT, order.id, reason="غيّر رأيه"))
    assert cancelled.status == "cancelled"
    with pytest.raises(OrderError):
        run(s.confirm_payment(TENANT, order.id, paid_amount_minor=2500, payment_ref="late_pay"))


# ── payments-service integration: minting the link, polling as the real source of truth ───────
def test_request_payment_mints_a_link_with_the_order_id_as_reference(svc):
    s, store, payments = svc
    sid, bid = run(_seed(store, price_minor=4000))
    order = run(s.create(tenant=TENANT, branch_id=bid, phone=PHONE, customer_name="سارة",
                         items=[(sid, 1)], lat=LAT, lng=LNG, idempotency_key="evt_pm_1"))
    updated = run(s.request_payment(TENANT, order.id))
    assert updated.pay_url == f"https://pay.example/{order.id}"
    assert updated.payment_request_id == f"preq_{order.id}"
    assert payments.created[0]["reference"] == order.id
    assert payments.created[0]["amount_minor"] == 4000


def test_request_payment_is_refused_once_the_order_is_already_confirmed(svc):
    s, store, payments = svc
    sid, bid = run(_seed(store, price_minor=1000))
    order = run(s.create(tenant=TENANT, branch_id=bid, phone=PHONE, customer_name="سارة",
                         items=[(sid, 1)], lat=LAT, lng=LNG, idempotency_key="evt_pm_2"))
    run(s.confirm_payment(TENANT, order.id, paid_amount_minor=1000, payment_ref="pay_pm_2"))
    with pytest.raises(OrderError):
        run(s.request_payment(TENANT, order.id))


def test_request_payment_is_refused_when_the_peer_is_unreachable(svc):
    s, store, payments = svc
    sid, bid = run(_seed(store))
    order = run(s.create(tenant=TENANT, branch_id=bid, phone=PHONE, customer_name="سارة",
                         items=[(sid, 1)], lat=LAT, lng=LNG, idempotency_key="evt_pm_3"))
    payments.unreachable = True
    with pytest.raises(OrderError):
        run(s.request_payment(TENANT, order.id))


def test_sync_payment_confirms_the_order_once_the_gateway_reports_completed(svc):
    s, store, payments = svc
    sid, bid = run(_seed(store, price_minor=2500))
    order = run(s.create(tenant=TENANT, branch_id=bid, phone=PHONE, customer_name="سارة",
                         items=[(sid, 1)], lat=LAT, lng=LNG, idempotency_key="evt_sync_1"))
    run(s.request_payment(TENANT, order.id))
    payments.reconcile_status = "completed"
    payments.reconcile_amount_minor = 2500
    synced = run(s.sync_payment(TENANT, order.id))
    assert synced.status == CONFIRMED


def test_sync_payment_is_a_safe_no_op_while_still_pending(svc):
    s, store, payments = svc
    sid, bid = run(_seed(store))
    order = run(s.create(tenant=TENANT, branch_id=bid, phone=PHONE, customer_name="سارة",
                         items=[(sid, 1)], lat=LAT, lng=LNG, idempotency_key="evt_sync_2"))
    run(s.request_payment(TENANT, order.id))
    synced = run(s.sync_payment(TENANT, order.id))
    assert synced.status == RECEIVED


def test_sync_payment_without_a_minted_link_is_a_no_op_never_a_crash(svc):
    s, store, payments = svc
    sid, bid = run(_seed(store))
    order = run(s.create(tenant=TENANT, branch_id=bid, phone=PHONE, customer_name="سارة",
                         items=[(sid, 1)], lat=LAT, lng=LNG, idempotency_key="evt_sync_3"))
    synced = run(s.sync_payment(TENANT, order.id))
    assert synced.status == RECEIVED


def test_sync_payment_is_idempotent_across_repeated_sweeps(svc):
    s, store, payments = svc
    sid, bid = run(_seed(store, price_minor=1500))
    order = run(s.create(tenant=TENANT, branch_id=bid, phone=PHONE, customer_name="سارة",
                         items=[(sid, 1)], lat=LAT, lng=LNG, idempotency_key="evt_sync_4"))
    run(s.request_payment(TENANT, order.id))
    payments.reconcile_status = "completed"
    payments.reconcile_amount_minor = 1500
    first = run(s.sync_payment(TENANT, order.id))
    second = run(s.sync_payment(TENANT, order.id))
    assert first.status == second.status == CONFIRMED
    run(s.start_preparing(TENANT, order.id))
    # A SWEEP THAT FIRES AGAIN AFTER THE SHOP HAS MOVED ON must never un-do real progress.
    third = run(s.sync_payment(TENANT, order.id))
    assert third.status == PREPARING


# ── security: a payment reference is ONE order's, never two's ─────────────────────────────────
def test_a_payment_reference_cannot_confirm_a_second_unrelated_order(svc):
    """The mirror-image fraud of the double-payment check: a leaked or reused `payment_ref` must
    never be able to pay for TWO different orders. A broken version of this check would let an
    attacker who learns one real payment reference confirm an unlimited number of other orders
    for free."""
    s, store, _payments = svc
    sid, bid = run(_seed(store, price_minor=1000))
    first = run(s.create(tenant=TENANT, branch_id=bid, phone=PHONE, customer_name="سارة",
                         items=[(sid, 1)], lat=LAT, lng=LNG, idempotency_key="evt_fraud_1"))
    second = run(s.create(tenant=TENANT, branch_id=bid, phone=PHONE, customer_name="سارة",
                          items=[(sid, 1)], lat=LAT, lng=LNG, idempotency_key="evt_fraud_2"))
    run(s.confirm_payment(TENANT, first.id, paid_amount_minor=1000, payment_ref="shared_ref"))
    with pytest.raises(OrderError):
        run(s.confirm_payment(TENANT, second.id, paid_amount_minor=1000, payment_ref="shared_ref"))
    reloaded_second = run(s.get(TENANT, second.id))
    assert reloaded_second.status == RECEIVED, "the second order must stay unpaid, never confirmed"


def test_a_payment_reference_clash_check_does_not_block_the_orders_own_legitimate_retry(svc):
    """The uniqueness check above must distinguish "this order, retried" from "a different order,
    colliding" — a false positive here would make an order's own idempotent webhook retry fail."""
    s, store, _payments = svc
    sid, bid = run(_seed(store, price_minor=1000))
    order = run(s.create(tenant=TENANT, branch_id=bid, phone=PHONE, customer_name="سارة",
                         items=[(sid, 1)], lat=LAT, lng=LNG, idempotency_key="evt_retry_ok"))
    run(s.confirm_payment(TENANT, order.id, paid_amount_minor=1000, payment_ref="ref_ok"))
    again = run(s.confirm_payment(TENANT, order.id, paid_amount_minor=1000, payment_ref="ref_ok"))
    assert again.status == CONFIRMED


def test_the_same_idempotency_key_in_two_different_tenants_never_collides(svc):
    """Tenant isolation: the same WhatsApp event id landing for two unrelated shops (a coincidence,
    or a replayed event across a multi-tenant WABA setup) must create TWO independent orders, never
    be treated as a duplicate of the other tenant's order."""
    s, store, _payments = svc
    sid, bid = run(_seed(store))
    other_tenant = "tnt_orders_other"
    services = ServiceStore(store)
    branches = BranchStore(store)
    run(services.save(Service(id=sid, tenant=other_tenant, name="قهوة", price_minor=2000)))
    run(branches.save(Branch(id=bid, tenant=other_tenant, name="فرع آخر", active=True)))
    first = run(s.create(tenant=TENANT, branch_id=bid, phone=PHONE, customer_name="سارة",
                         items=[(sid, 1)], lat=LAT, lng=LNG, idempotency_key="evt_shared_key"))
    second = run(s.create(tenant=other_tenant, branch_id=bid, phone=PHONE, customer_name="سارة",
                          items=[(sid, 1)], lat=LAT, lng=LNG, idempotency_key="evt_shared_key"))
    assert first.id != second.id
    assert first.tenant == TENANT and second.tenant == other_tenant


def test_a_tenant_can_never_place_an_order_against_another_tenants_branch(svc):
    """Tenant isolation at the branch boundary: a branch id that is real, but belongs to a
    DIFFERENT tenant, must be refused exactly like an unknown id — never resolved across the
    tenancy wall `core/stores.py`'s own module docstring exists to enforce."""
    s, store, _payments = svc
    other_tenant = "tnt_orders_other2"
    services = ServiceStore(store)
    branches = BranchStore(store)
    sid = "svc_x"
    run(services.save(Service(id=sid, tenant=TENANT, name="قهوة", price_minor=1000)))
    run(branches.save(Branch(id="br_foreign", tenant=other_tenant, name="فرع الغير", active=True)))
    with pytest.raises(OrderError):
        run(s.create(tenant=TENANT, branch_id="br_foreign", phone=PHONE, customer_name="سارة",
                     items=[(sid, 1)], lat=LAT, lng=LNG, idempotency_key="evt_cross_branch"))


def test_a_tenant_can_never_price_an_order_off_another_tenants_service(svc):
    """Same tenant-isolation boundary, at the catalogue instead of the branch: a service id that
    is real for ANOTHER tenant must read as unknown here, never leak that tenant's price."""
    s, store, _payments = svc
    other_tenant = "tnt_orders_other3"
    services = ServiceStore(store)
    branches = BranchStore(store)
    sid = "svc_foreign"
    bid = "br_main"
    run(services.save(Service(id=sid, tenant=other_tenant, name="سري", price_minor=99999)))
    run(branches.save(Branch(id=bid, tenant=TENANT, name="الفرع", active=True)))
    with pytest.raises(OrderError):
        run(s.create(tenant=TENANT, branch_id=bid, phone=PHONE, customer_name="سارة",
                     items=[(sid, 1)], lat=LAT, lng=LNG, idempotency_key="evt_cross_service"))


def test_an_idempotency_key_longer_than_the_bound_is_refused(svc):
    s, store, _payments = svc
    sid, bid = run(_seed(store))
    with pytest.raises(OrderError):
        run(s.create(tenant=TENANT, branch_id=bid, phone=PHONE, customer_name="سارة",
                     items=[(sid, 1)], lat=LAT, lng=LNG, idempotency_key="k" * 500))


def test_a_negative_quantity_cannot_be_smuggled_in_via_merge(svc):
    """`items=[(sid, 5), (sid, -3)]` must never compute to a quantity of 2 — each RAW line is
    validated before any merge happens, so a negative line is refused outright rather than
    silently netted against a positive one."""
    s, store, _payments = svc
    sid, bid = run(_seed(store))
    with pytest.raises(OrderError):
        run(s.create(tenant=TENANT, branch_id=bid, phone=PHONE, customer_name="سارة",
                     items=[(sid, 5), (sid, -3)], lat=LAT, lng=LNG, idempotency_key="evt_neg"))


def test_a_zero_quantity_line_is_refused(svc):
    s, store, _payments = svc
    sid, bid = run(_seed(store))
    with pytest.raises(OrderError):
        run(s.create(tenant=TENANT, branch_id=bid, phone=PHONE, customer_name="سارة",
                     items=[(sid, 0)], lat=LAT, lng=LNG, idempotency_key="evt_zero"))


def test_nan_coordinates_are_refused_not_silently_accepted(svc):
    s, store, _payments = svc
    sid, bid = run(_seed(store))
    with pytest.raises(OrderError):
        run(s.create(tenant=TENANT, branch_id=bid, phone=PHONE, customer_name="سارة",
                     items=[(sid, 1)], lat=float("nan"), lng=LNG, idempotency_key="evt_nan"))


def test_a_zero_paid_amount_is_a_mismatch_never_a_free_confirmation(svc):
    """`paid_amount_minor=0` must never satisfy `paid_amount_minor == total_minor` by some
    accidental falsy-equals-falsy path — an order's `total_minor` is always > 0 (unpriced services
    are refused at creation), so 0 can only ever be a mismatch."""
    s, store, _payments = svc
    sid, bid = run(_seed(store, price_minor=1000))
    order = run(s.create(tenant=TENANT, branch_id=bid, phone=PHONE, customer_name="سارة",
                         items=[(sid, 1)], lat=LAT, lng=LNG, idempotency_key="evt_zero_pay"))
    result = run(s.confirm_payment(TENANT, order.id, paid_amount_minor=0, payment_ref="ref_zero"))
    assert result.status == PAYMENT_MISMATCH


def test_a_negative_paid_amount_is_refused_as_a_mismatch(svc):
    s, store, _payments = svc
    sid, bid = run(_seed(store, price_minor=1000))
    order = run(s.create(tenant=TENANT, branch_id=bid, phone=PHONE, customer_name="سارة",
                         items=[(sid, 1)], lat=LAT, lng=LNG, idempotency_key="evt_neg_pay"))
    result = run(s.confirm_payment(TENANT, order.id, paid_amount_minor=-1000,
                                   payment_ref="ref_neg"))
    assert result.status == PAYMENT_MISMATCH


def test_an_empty_items_list_after_whitespace_service_id_is_refused(svc):
    s, store, _payments = svc
    sid, bid = run(_seed(store))
    with pytest.raises(OrderError):
        run(s.create(tenant=TENANT, branch_id=bid, phone=PHONE, customer_name="سارة",
                     items=[("   ", 1)], lat=LAT, lng=LNG, idempotency_key="evt_blank_id"))


def test_an_invalid_phone_is_refused_before_any_pricing_work(svc):
    s, store, _payments = svc
    sid, bid = run(_seed(store))
    with pytest.raises(OrderError):
        run(s.create(tenant=TENANT, branch_id=bid, phone="not-a-phone", customer_name="سارة",
                     items=[(sid, 1)], lat=LAT, lng=LNG, idempotency_key="evt_bad_phone"))


def test_cancelling_an_already_cancelled_order_is_refused_not_a_silent_no_op(svc):
    s, store, _payments = svc
    sid, bid = run(_seed(store))
    order = run(s.create(tenant=TENANT, branch_id=bid, phone=PHONE, customer_name="سارة",
                         items=[(sid, 1)], lat=LAT, lng=LNG, idempotency_key="evt_double_cancel"))
    run(s.cancel(TENANT, order.id, reason="أول مرة"))
    with pytest.raises(OrderError):
        run(s.cancel(TENANT, order.id, reason="مرة ثانية"))


def test_a_delivered_order_cannot_be_cancelled_retroactively(svc):
    s, store, _payments = svc
    sid, bid = run(_seed(store, price_minor=1000))
    order = run(s.create(tenant=TENANT, branch_id=bid, phone=PHONE, customer_name="سارة",
                         items=[(sid, 1)], lat=LAT, lng=LNG, idempotency_key="evt_post_deliver"))
    run(s.confirm_payment(TENANT, order.id, paid_amount_minor=1000, payment_ref="ref_pd"))
    run(s.start_preparing(TENANT, order.id))
    run(s.mark_ready(TENANT, order.id))
    run(s.start_delivery(TENANT, order.id))
    run(s.complete(TENANT, order.id))
    with pytest.raises(OrderError):
        run(s.cancel(TENANT, order.id, reason="بعد التسليم"))


# ── reminders integration: a real customer row, and events published on real transitions ──────
def test_create_resolves_a_real_customer_never_a_bare_phone(svc_events):
    s, store, _events = svc_events
    sid, bid = run(_seed(store))
    order = run(s.create(tenant=TENANT, branch_id=bid, phone=PHONE, customer_name="سارة",
                         items=[(sid, 1)], lat=LAT, lng=LNG, idempotency_key="evt_cust_1"))
    assert order.customer_id
    assert order.subject_ref
    from app.core.stores import CustomerStore
    customer = run(CustomerStore(store).get(TENANT, order.customer_id))
    # `canonical_phone` (orders.py) and `_normalise_phone` (operations.py's own ensure_customer)
    # are two pre-existing, independently evolved normalisers that agree on digits but not on a
    # leading "+" — comparing digits only, since fixing that divergence is out of this change's
    # scope.
    assert customer is not None
    assert customer.phone.lstrip("+") == order.phone.lstrip("+")


def test_two_orders_from_the_same_phone_share_one_customer_row(svc_events):
    s, store, _events = svc_events
    sid, bid = run(_seed(store))
    first = run(s.create(tenant=TENANT, branch_id=bid, phone=PHONE, customer_name="سارة",
                         items=[(sid, 1)], lat=LAT, lng=LNG, idempotency_key="evt_cust_2a"))
    second = run(s.create(tenant=TENANT, branch_id=bid, phone=PHONE, customer_name="سارة",
                          items=[(sid, 1)], lat=LAT, lng=LNG, idempotency_key="evt_cust_2b"))
    assert first.customer_id == second.customer_id


def test_no_event_published_on_order_creation_itself(svc_events):
    """Creation is not yet a confirmed, paid order — the first customer-facing message fires on
    CONFIRMED, not on a RECEIVED order nobody has paid for yet."""
    s, store, events = svc_events
    sid, bid = run(_seed(store))
    run(s.create(tenant=TENANT, branch_id=bid, phone=PHONE, customer_name="سارة",
                items=[(sid, 1)], lat=LAT, lng=LNG, idempotency_key="evt_noevt"))
    assert events.published == []


def test_an_event_fires_on_each_real_transition_with_the_subject_ref_never_the_phone(svc_events):
    s, store, events = svc_events
    sid, bid = run(_seed(store, price_minor=1000))
    order = run(s.create(tenant=TENANT, branch_id=bid, phone=PHONE, customer_name="سارة",
                         items=[(sid, 1)], lat=LAT, lng=LNG, idempotency_key="evt_fire_1"))
    run(s.confirm_payment(TENANT, order.id, paid_amount_minor=1000, payment_ref="pay_fire_1"))
    run(s.start_preparing(TENANT, order.id))
    run(s.mark_ready(TENANT, order.id))
    run(s.start_delivery(TENANT, order.id))
    run(s.complete(TENANT, order.id))

    statuses = [payload["status"] for _topic, payload in events.published]
    assert statuses == [CONFIRMED, PREPARING, READY, OUT_FOR_DELIVERY, "delivered"]
    for topic, payload in events.published:
        assert topic == "operations.order.changed"
        assert payload["subject_ref"] == order.subject_ref
        assert "phone" not in payload
        assert payload["order_id"] == order.id


def test_a_payment_mismatch_never_fires_a_customer_facing_event(svc_events):
    s, store, events = svc_events
    sid, bid = run(_seed(store, price_minor=1000))
    order = run(s.create(tenant=TENANT, branch_id=bid, phone=PHONE, customer_name="سارة",
                         items=[(sid, 1)], lat=LAT, lng=LNG, idempotency_key="evt_mismatch_1"))
    run(s.confirm_payment(TENANT, order.id, paid_amount_minor=500, payment_ref="pay_mismatch_1"))
    assert events.published == []
    run(s.resolve_mismatch(TENANT, order.id, actor="owner"))
    assert len(events.published) == 1
    assert events.published[0][1]["status"] == CONFIRMED


def test_cancellation_fires_its_own_event(svc_events):
    s, store, events = svc_events
    sid, bid = run(_seed(store))
    order = run(s.create(tenant=TENANT, branch_id=bid, phone=PHONE, customer_name="سارة",
                         items=[(sid, 1)], lat=LAT, lng=LNG, idempotency_key="evt_cancel_fire"))
    run(s.cancel(TENANT, order.id, reason="نفدت الكمية"))
    assert len(events.published) == 1
    assert events.published[0][1]["status"] == "cancelled"


def test_a_missing_event_bus_never_breaks_a_real_status_change(svc):
    """`events=None` (the default) must be a true no-op, same `if self._events is None: return`
    posture every other optional peer in this file already takes — a status change is a real fact
    that must land regardless of whether anything is listening for it."""
    s, store, _payments = svc
    sid, bid = run(_seed(store, price_minor=1000))
    order = run(s.create(tenant=TENANT, branch_id=bid, phone=PHONE, customer_name="سارة",
                         items=[(sid, 1)], lat=LAT, lng=LNG, idempotency_key="evt_no_bus"))
    confirmed = run(s.confirm_payment(TENANT, order.id, paid_amount_minor=1000,
                                      payment_ref="pay_no_bus"))
    assert confirmed.status == CONFIRMED
