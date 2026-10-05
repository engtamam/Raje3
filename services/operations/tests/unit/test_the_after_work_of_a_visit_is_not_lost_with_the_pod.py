"""ز-7 — the seams run after the response, and nothing recorded whether they ran.

WHAT THE SEAMS ARE. Indexing the customer so the keypad can find them, and emitting the visit that
reminders schedules from and insights counts. They deliberately do NOT run on the request path: the
operator has a customer in front of him and the five-second budget is his, not our fan-out's.

WHAT THAT COSTS. «After the response» is also «after the process may have gone away». A pod evicted
in that window left the visit saved and none of it done — no reminder, which is the entire product,
and a customer the keypad cannot find. Nothing anywhere said so.

AND THE RETRY CLOSED THE DOOR. The route asked `if not result.duplicate`, so the second attempt —
the one attempt that could have repaired it — was precisely the one that skipped the seams.

`seams.py` promised in its own docstring that a failure «lets the sweep or the next visit repair
it». There was no sweep, and the next visit repairs nothing: it indexes its own customer and emits
its own event, neither of which schedules the reminder the lost visit owed.
"""
from __future__ import annotations

import asyncio

import pytest

from app.adapters.datastore.memory import MemoryDataStore
from app.core.operations import Operations, RecordedVisit
from app.core.seams import Seams
from app.core.stores import CustomerStore, VisitStore

SALT = "s" * 32
T = "shop"
PHONE = "0501234567"
NOW = 1_780_000_000


def run(coro):
    return asyncio.run(coro)


class FakeSearch:
    def __init__(self):
        self.docs = []

    async def index(self, **kw):
        self.docs.append(kw)


class FakeEvents:
    def __init__(self):
        self.published = []

    async def publish(self, *a, **kw):
        self.published.append((a, kw))


@pytest.fixture()
def wired():
    store = MemoryDataStore()
    search, events = FakeSearch(), FakeEvents()
    seams = Seams(search=search, events=events, visits=VisitStore(store), clock=lambda: NOW)
    return Operations(store=store, pii_salt=SALT), store, seams, search, events


def test_a_finished_visit_says_so(wired):
    """The stamp exists and is written — without it nothing below can tell the two states apart."""
    svc, store, seams, _, _ = wired
    out = run(svc.record_visit(tenant=T, phone=PHONE, service_ids=["srv_1"]))
    assert out.visit.seamed_at == 0, "not yet — the seams have not run"

    run(seams.after_visit(out))
    assert run(VisitStore(store).get(T, out.visit.id)).seamed_at == NOW


def test_a_refused_index_write_leaves_the_visit_for_the_sweep(wired):
    """The search adapter never raises — it answers False when the write did not land (search-
    service refusing under contention, seen live). That False used to be ignored AND the visit
    stamped done, so the sweep never came back and the customer stayed unfindable by the keypad
    until his next visit. Now the refusal is recorded and the visit stays unstamped."""
    svc, store, _, _, events = wired

    class RefusingSearch:
        async def index(self, **kw):
            return False

    class Telemetry:
        def __init__(self):
            self.events = []

        def event(self, name, **kw):
            self.events.append(name)

        def counter(self, name):
            pass

    telemetry = Telemetry()
    seams = Seams(search=RefusingSearch(), events=events, visits=VisitStore(store),
                  telemetry=telemetry, clock=lambda: NOW)
    out = run(svc.record_visit(tenant=T, phone=PHONE, service_ids=["srv_1"]))

    run(seams.after_visit(out))

    assert run(VisitStore(store).get(T, out.visit.id)).seamed_at == 0, "stamped done over a failed seam"
    assert "search_index_failed" in telemetry.events, "the refusal was not recorded"
    assert events.published, "the other seam still ran — one failure must not skip the rest"


def test_a_retry_runs_the_seams_the_first_attempt_never_finished(wired):
    """The whole finding: the retry must repair, and it used to be the one path that could not.

    This asserts the CONDITION the route branches on, because that is where the defect lived — the
    route asked «is this a duplicate?» when the question is «have the seams run?».
    """
    svc, _, seams, search, events = wired
    first = run(svc.record_visit(tenant=T, phone=PHONE, service_ids=["srv_1"],
                                 idempotency_key="k1"))
    # The pod dies here: the visit is durable, the seams never ran.
    assert not search.docs and not events.published

    again = run(svc.record_visit(tenant=T, phone=PHONE, service_ids=["srv_1"],
                                 idempotency_key="k1"))
    assert again.duplicate, "same key, so the visit is not recorded twice"
    assert not again.visit.seamed_at, (
        "and the after-work is still owed — this is the flag the route must branch on. Asking "
        "`not duplicate` here skips the seams on the one attempt that could repair them")

    run(seams.after_visit(again))
    assert search.docs, "the customer is indexed at last"
    assert events.published, "and the visit is finally announced — reminders can schedule it"
    assert again.visit.seamed_at == NOW


def test_a_second_pass_over_a_finished_visit_is_refused_by_the_flag(wired):
    """The other side: a visit already seamed must not be seamed again on every later retry."""
    svc, _, seams, _, _ = wired
    out = run(svc.record_visit(tenant=T, phone=PHONE, service_ids=["srv_1"],
                               idempotency_key="k1"))
    run(seams.after_visit(out))

    again = run(svc.record_visit(tenant=T, phone=PHONE, service_ids=["srv_1"],
                                 idempotency_key="k1"))
    assert again.visit.seamed_at == NOW, "the retry reads the stamp and does nothing"


def test_the_sweep_finds_the_visits_no_retry_ever_comes_for(wired):
    """Most lost visits are never retried at all — the operator moved on to the next customer.

    So the flag alone is half a fix: something has to look. The sweep's work list is exactly the
    settled visits with no stamp.
    """
    svc, store, seams, search, events = wired
    lost = run(svc.record_visit(tenant=T, phone=PHONE, service_ids=["srv_1"]))
    fresh = run(svc.record_visit(tenant=T, phone="0507654321", service_ids=["srv_1"]))
    run(seams.after_visit(fresh))

    visits = VisitStore(store)
    work = run(visits.unseamed(T, before=lost.visit.created + 1))
    assert [v.id for v in work] == [lost.visit.id], (
        "the finished one must not be picked up, and the lost one must be")

    customer = run(CustomerStore(store).get(T, lost.visit.customer_id))
    run(seams.after_visit(RecordedVisit(visit=lost.visit, customer=customer,
                                        created_customer=False, duplicate=False)))
    assert run(visits.unseamed(T, before=lost.visit.created + 1)) == []
    assert search.docs and events.published


def test_a_visit_still_in_flight_is_left_alone(wired):
    """A visit recorded seconds ago has its seams running right now; the sweep must not race it."""
    svc, store, _, _, _ = wired
    out = run(svc.record_visit(tenant=T, phone=PHONE, service_ids=["srv_1"]))
    assert run(VisitStore(store).unseamed(T, before=out.visit.created)) == []
