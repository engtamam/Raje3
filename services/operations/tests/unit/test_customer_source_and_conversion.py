"""Customer.source (stamped once, at creation, never overwritten) and
CustomerStore.conversion_by_source — insights' own `lead_conversion` indicator reads exactly this
shape. See models.py's own docstring on Customer.source and stores.py's own on
conversion_by_source.
"""
from __future__ import annotations

import asyncio

from app.adapters.datastore.memory import MemoryDataStore
from app.core.models import Customer
from app.core.stores import CustomerStore

TENANT = "tnt_conv"


def run(coro):
    return asyncio.run(coro)


def test_default_source_is_manual():
    c = Customer(id="cus1", tenant=TENANT, phone="0501", subject_ref="ref1")
    assert c.source == "manual"


def test_ensure_customer_stamps_the_caller_given_source():
    from app.core.operations import Operations

    ops = Operations(store=MemoryDataStore(), pii_salt="s" * 32)
    cust, _ = run(ops.ensure_customer(TENANT, "0501234567", source="whatsapp"))
    assert cust.source == "whatsapp"


def test_an_existing_customers_source_never_moves():
    from app.core.operations import Operations

    ops = Operations(store=MemoryDataStore(), pii_salt="s" * 32)
    first, _ = run(ops.ensure_customer(TENANT, "0501234567", source="whatsapp"))
    # A SECOND call, from a DIFFERENT channel (the console dialog, "manual" default) — must find
    # the SAME row and leave its original source exactly as it was.
    second, _ = run(ops.ensure_customer(TENANT, "0501234567"))
    assert second.id == first.id
    assert second.source == "whatsapp"


def test_conversion_by_source_counts_total_and_converted_per_channel():
    store = CustomerStore(MemoryDataStore())
    run(store.save(Customer(id="c1", tenant=TENANT, phone="1", subject_ref="r1",
                            source="whatsapp", visit_count=0)))
    run(store.save(Customer(id="c2", tenant=TENANT, phone="2", subject_ref="r2",
                            source="whatsapp", visit_count=2)))
    run(store.save(Customer(id="c3", tenant=TENANT, phone="3", subject_ref="r3",
                            source="manual", visit_count=1)))

    stats = run(store.conversion_by_source(TENANT))
    assert stats["whatsapp"] == {"total": 2, "converted": 1}
    assert stats["manual"] == {"total": 1, "converted": 1}


def test_a_row_written_before_source_existed_falls_back_to_manual():
    """A dataclass default only fills a MISSING key — the same shape every other field added to
    this row after go-live already relies on (Customer.source's own docstring)."""
    store = CustomerStore(MemoryDataStore())
    run(store._put(TENANT, "cus_old", {  # noqa: SLF001 — deliberately bypassing the dataclass
        "id": "cus_old", "tenant": TENANT, "phone": "9", "subject_ref": "r9",
        "visit_count": 1}))
    stats = run(store.conversion_by_source(TENANT))
    assert stats["manual"] == {"total": 1, "converted": 1}


def test_conversion_by_source_is_empty_for_a_tenant_with_no_customers():
    store = CustomerStore(MemoryDataStore())
    assert run(store.conversion_by_source("tnt_nobody")) == {}
