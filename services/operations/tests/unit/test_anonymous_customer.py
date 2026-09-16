"""`record_visit(anonymous=True)` — the one placeholder customer per tenant that absorbs a TikTok
Shop order whose phone arrived masked/missing, instead of losing the sale ([[task-tiktok-app-
phases]] phase 1, `Customer.anonymous`'s own docstring for the full reasoning).
"""
from __future__ import annotations

import asyncio

import pytest

from app.adapters.datastore.memory import MemoryDataStore
from app.core.models import Service
from app.core.operations import Operations
from app.core.stores import ServiceStore

SALT = "s" * 32
T = "tnt_anon"


def run(coro):
    return asyncio.run(coro)


@pytest.fixture()
def ops():
    store = MemoryDataStore()
    return Operations(store=store, pii_salt=SALT), store


async def _seed(store, sid: str, price: int) -> None:
    await ServiceStore(store).save(Service(id=sid, tenant=T, name="خدمة", price_minor=price))


def test_a_no_phone_order_still_records_the_visit_and_the_real_money(ops):
    svc, store = ops
    run(_seed(store, "svc_wash", 3000))
    res = run(svc.record_visit(tenant=T, phone="", service_ids=["svc_wash"], anonymous=True))
    assert res.visit.total_minor == 3000
    assert res.customer.anonymous is True
    assert res.customer.phone == ""


def test_two_separate_no_phone_orders_pile_onto_the_same_one_placeholder(ops):
    svc, store = ops
    run(_seed(store, "svc_wash", 1000))
    first = run(svc.record_visit(tenant=T, phone="", service_ids=["svc_wash"], anonymous=True,
                                 idempotency_key="tt_order_1"))
    second = run(svc.record_visit(tenant=T, phone="", service_ids=["svc_wash"], anonymous=True,
                                  idempotency_key="tt_order_2"))
    assert first.customer.id == second.customer.id
    assert second.created_customer is False


def test_an_ordinary_phone_visit_never_touches_the_anonymous_placeholder(ops):
    svc, store = ops
    run(_seed(store, "svc_wash", 1000))
    run(svc.record_visit(tenant=T, phone="", service_ids=["svc_wash"], anonymous=True))
    real = run(svc.record_visit(tenant=T, phone="0501234567", service_ids=["svc_wash"]))
    assert real.customer.anonymous is False
    assert real.customer.phone == "966501234567"


def test_a_blank_phone_without_anonymous_still_refuses_same_as_before(ops):
    """The existing, unrelated caller (field screen, till) must see NO behaviour change at all —
    `anonymous` is opt-in, never inferred from an empty phone."""
    svc, store = ops
    run(_seed(store, "svc_wash", 1000))
    with pytest.raises(Exception, match="رقم الجوال مطلوب"):
        run(svc.record_visit(tenant=T, phone="", service_ids=["svc_wash"]))


def test_the_placeholder_is_scoped_per_tenant_not_shared_across_shops(ops):
    svc, store = ops
    run(_seed(store, "svc_wash", 1000))
    mine = run(svc.record_visit(tenant=T, phone="", service_ids=["svc_wash"], anonymous=True))

    async def _seed_other():
        await ServiceStore(store).save(Service(id="svc_wash", tenant="tnt_other", name="خدمة",
                                               price_minor=1000))
    run(_seed_other())
    other = run(svc.record_visit(tenant="tnt_other", phone="", service_ids=["svc_wash"],
                                 anonymous=True))
    assert mine.customer.id != other.customer.id
    assert mine.customer.tenant == T
    assert other.customer.tenant == "tnt_other"
