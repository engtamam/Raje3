"""The customer store's lookups — one per question the product actually asks.

Not a test of the datastore adapter: that is somebody else's. These hold the SHAPE each screen
depends on, and the one below was written the day «عملائي» could not answer the third of the three
questions its own file promises.
"""
from __future__ import annotations

import asyncio

import pytest

from app.adapters.datastore.memory import MemoryDataStore
from app.core.models import Customer, Service
from app.core.stores import CustomerStore, ServiceStore

T = "tnt_alpha"


def run(coro):
    return asyncio.run(coro)


@pytest.fixture()
def store():
    return MemoryDataStore()


# ── the join «عملائي» needs for its overdue tab ────────────────────────────────────────────────
def test_customers_are_found_by_their_pseudonyms(store):
    """reminders answers the overdue question with `subject_ref` and no names — deliberately, since
    a service that does not need a customer's name must not be able to read one. The names are
    looked up here, where they already live."""
    cs = CustomerStore(store)
    a = run(cs.save(Customer(id="c1", tenant=T, phone="0501111111", subject_ref="ref-a", name="أحمد")))
    run(cs.save(Customer(id="c2", tenant=T, phone="0502222222", subject_ref="ref-b")))
    run(cs.save(Customer(id="c3", tenant=T, phone="0503333333", subject_ref="ref-c")))

    got = run(cs.by_refs(T, {"ref-a", "ref-c"}))
    assert {c.id for c in got} == {"c1", "c3"}
    assert next(c for c in got if c.id == "c1").name == a.name


def test_a_pseudonym_this_shop_does_not_hold_is_simply_absent(store):
    """Not an error to explain: an unknown ref is an erased customer or another shop's, and saying
    which would answer a question nobody should be able to ask."""
    cs = CustomerStore(store)
    run(cs.save(Customer(id="c1", tenant=T, phone="0501111111", subject_ref="ref-a")))
    assert run(cs.by_refs(T, {"ref-a", "ref-of-another-shop"})) [0].id == "c1"
    assert len(run(cs.by_refs(T, {"ref-a", "ref-of-another-shop"}))) == 1


def test_no_refs_reads_nothing_at_all(store):
    """An empty list must not fall through to "every customer" — the difference between an empty
    overdue tab and a full customer export."""
    cs = CustomerStore(store)
    run(cs.save(Customer(id="c1", tenant=T, phone="0501111111", subject_ref="ref-a")))
    assert run(cs.by_refs(T, set())) == []


# ── operations-r2-004 (QA audit round 2, 2026-09-12): `ServiceStore.list` used to hard-cap at
# 200 rows with no cursor, and callers (`by_external_id`, `invoices.resolve`) treated that page as
# the whole catalogue — a shop past 200 services got silent duplicates for any product past the
# cut, and its own «خدماتي» screen never showed the rest. Fixed to drain the whole set. ─────────
def test_the_whole_catalogue_is_read_past_the_old_200_row_cap(store):
    ss = ServiceStore(store)
    for i in range(210):
        run(ss.save(Service(id=f"svc{i}", tenant=T, name=f"خدمة {i}", active=True,
                            external_id=f"ext{i}")))

    got = run(ss.list(T, active_only=False))
    assert len(got) == 210

    # AND `by_external_id` — the auto-create path's own duplicate check — can still find the
    # 201st service, which the old `limit=200` read could never see.
    found = run(ss.by_external_id(T, "ext205"))
    assert found is not None and found.id == "svc205"
