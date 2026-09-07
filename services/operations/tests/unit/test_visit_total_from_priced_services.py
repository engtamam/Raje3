"""`record_visit`'s own `total_minor` fallback — computed from the catalogue's own priced
services when no till supplied one (spec §9.3, till-integration gate retired 2026-09-08).
"""
from __future__ import annotations

import asyncio

import pytest

from app.adapters.datastore.memory import MemoryDataStore
from app.core.models import Service
from app.core.operations import Operations
from app.core.stores import ServiceStore

SALT = "s" * 32
T = "tnt_pricing"


def run(coro):
    return asyncio.run(coro)


@pytest.fixture()
def ops():
    store = MemoryDataStore()
    return Operations(store=store, pii_salt=SALT), store


async def _seed(store, sid: str, price: int) -> None:
    await ServiceStore(store).save(Service(id=sid, tenant=T, name="خدمة", price_minor=price))


def test_a_manual_visit_with_no_till_total_sums_the_priced_services(ops):
    """THE FEATURE. The field screen has never sent an amount — this is what makes «invoice»
    earning possible without a till at all."""
    svc, store = ops
    run(_seed(store, "svc_wash", 3000))
    run(_seed(store, "svc_wax", 1500))
    res = run(svc.record_visit(tenant=T, phone="0501234567",
                               service_ids=["svc_wash", "svc_wax"]))
    assert res.visit.total_minor == 4500


def test_quantities_multiply_the_price(ops):
    svc, store = ops
    run(_seed(store, "svc_oil", 8000))
    res = run(svc.record_visit(tenant=T, phone="0501234567", service_ids=["svc_oil"],
                               quantities={"svc_oil": 3}))
    assert res.visit.total_minor == 24_000


def test_an_unpriced_service_contributes_nothing_not_an_error(ops):
    """NOT AN ERROR — the same "no points configured" is not one, either (loyalty's own earn.py).
    An owner who has not priced a service yet still records the visit; he simply earns less by
    invoice until he does."""
    svc, store = ops
    run(_seed(store, "svc_priced", 2000))
    run(_seed(store, "svc_unpriced", 0))
    res = run(svc.record_visit(tenant=T, phone="0501234567",
                               service_ids=["svc_priced", "svc_unpriced"]))
    assert res.visit.total_minor == 2000


def test_a_real_till_total_is_never_overridden_by_the_catalogue_sum(ops):
    """The till's own reported total is the amount ACTUALLY PAID, which can legitimately differ
    from the catalogue's list prices — a discount, a tip, a tax line the till itself applies. The
    catalogue sum must never silently replace it."""
    svc, store = ops
    run(_seed(store, "svc_wash", 3000))
    res = run(svc.record_visit(tenant=T, phone="0501234567", service_ids=["svc_wash"],
                               total_minor=2500))  # a discounted till total, lower than list price
    assert res.visit.total_minor == 2500


def test_an_unknown_service_id_contributes_nothing_to_the_sum(ops):
    svc, store = ops
    res = run(svc.record_visit(tenant=T, phone="0501234567", service_ids=["svc_never_priced"]))
    assert res.visit.total_minor == 0
