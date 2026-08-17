"""ز-6 — the counter and the visit, and the crash between them.

`visit_count` and `last_visit` are derived numbers kept beside the customer so the recent-customers
strip is one read rather than a join per keystroke. Deriving them costs a scan; keeping them costs
a second write — and two writes are two chances to be interrupted.

WHAT THE ORDER USED TO BE. `save(customer)` then `save(visit)`. A failure on the second left a
customer whose count said nine with eight visits behind it, and a `last_visit` pointing at a visit
nobody could find — so the next reminder was scheduled from something that did not happen. The
points ledger has a reconciliation that would notice; this has none.

AND THE RETRY MADE IT WORSE. The duplicate guard reads the idempotency key off the VISIT rows. The
visit was never written, so there was no key, so the second attempt was not recognised as a retry:
it raised the counter again. One interrupted visit, counted twice, for ever.

These tests interrupt the write deliberately and then look at what a retry does.
"""
from __future__ import annotations

import asyncio

import pytest

from app.adapters.datastore.memory import MemoryDataStore
from app.core.operations import Operations

SALT = "s" * 32
T = "shop"
PHONE = "0501234567"


def run(coro):
    return asyncio.run(coro)


class Broken(Exception):
    """The datastore, at the worst possible moment."""


@pytest.fixture()
def ops():
    store = MemoryDataStore()
    return Operations(store=store, pii_salt=SALT), store


def test_the_visit_is_written_before_the_counter_moves(ops):
    """The order itself, asserted where it is decided rather than read off the source.

    A visit that exists with a counter behind it is repairable — the retry below does it. A counter
    ahead of a visit that does not exist is not: nothing can tell it from a real count.
    """
    svc, store = ops
    written: list[str] = []
    real_put = store.put

    async def watched(kind, key, row):
        written.append(kind)
        return await real_put(kind, key, row)

    store.put = watched
    run(svc.record_visit(tenant=T, phone=PHONE, service_ids=["srv_1"]))
    store.put = real_put

    assert "visits" in written and "customers" in written
    # The customer row is also written on CREATION, before any of this — so what matters is that
    # the visit lands before the LAST customer write, which is the one carrying the count.
    assert written.index("visits") < len(written) - 1 - written[::-1].index("customers")


def test_a_visit_interrupted_before_the_count_is_completed_by_the_retry(ops):
    """The crash, and the repair — this is the whole finding.

    The first attempt dies after the visit is written and before the counters are. The retry
    presents the same idempotency key, recognises the visit, and finishes the half that never
    landed. Before the fix it returned the visit and left the customer one behind for ever.
    """
    svc, store = ops
    run(svc.record_visit(tenant=T, phone=PHONE, service_ids=["srv_1"], idempotency_key="k1"))
    settled = run(svc.customer_by_phone(T, PHONE))
    assert settled.visit_count == 1

    # The second visit dies between the two writes: the visit lands, the counter never moves.
    real_put = store.put

    async def die_on_customer(kind, key, row):
        if kind == "customers":
            raise Broken("the pod went away")
        return await real_put(kind, key, row)

    store.put = die_on_customer
    with pytest.raises(Broken):
        run(svc.record_visit(tenant=T, phone=PHONE, service_ids=["srv_1"], idempotency_key="k2"))
    store.put = real_put

    stranded = run(svc.customer_by_phone(T, PHONE))
    assert stranded.visit_count == 1, "the counter must not have moved — the write failed"

    out = run(svc.record_visit(tenant=T, phone=PHONE, service_ids=["srv_1"],
                               idempotency_key="k2"))
    assert out.duplicate, "the visit is already written, so this is a retry and not a new visit"
    repaired = run(svc.customer_by_phone(T, PHONE))
    assert repaired.visit_count == 2, (
        "the retry must finish the count the crash interrupted — otherwise this customer is one "
        "visit behind for the rest of their life, silently")


def test_a_retry_of_a_visit_that_fully_succeeded_counts_nothing_twice(ops):
    """The other direction, and the reason the repair is guarded by the visit's own id.

    A repair that ran unconditionally would turn every double tap into a second count — the exact
    defect this replaced, reached from the opposite side.
    """
    svc, _ = ops
    run(svc.record_visit(tenant=T, phone=PHONE, service_ids=["srv_1"], idempotency_key="k1"))
    for _ in range(3):
        run(svc.record_visit(tenant=T, phone=PHONE, service_ids=["srv_1"], idempotency_key="k1"))
    assert run(svc.customer_by_phone(T, PHONE)).visit_count == 1
