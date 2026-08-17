"""ز-9 — the free wash happened, the points went, and no visit ever existed.

A `service` reward is two things at once: points spent, and a visit recorded so the reminder cycle
restarts from today. The second lived in a try/except that wrote a telemetry line and nothing else,
and NOTHING EVER REPLAYED IT. The receiving door was built idempotent — `source=rec.id` is stable —
so the retry was possible all along; there was simply no retrier.

    reward handed over  ->  points deducted  ->  visits.record() fails  ->  telemetry, and silence

The half-act was then permanent. Days later the reminder engine, working exactly as designed, tells
the customer it is time for the wash he already had. He reads that as a shop that does not know
him, which is the opposite of what the shop is paying us for.
"""
from __future__ import annotations

import asyncio
import types

from app.api.v1.loyalty import record_free_visit
from app.core.models import REDEMPTIONS, Redemption

TENANT = "shop"


def run(c):
    return asyncio.run(c)


class _Visits:
    """operations' door, which refuses a repeat of the same `source` — as the real one does."""

    def __init__(self, fail: bool = False):
        self.fail = fail
        self.sources: list[str] = []

    async def record(self, *, tenant, subject_ref, service_id, actor, source):
        if self.fail:
            raise RuntimeError("operations unreachable")
        if source in self.sources:
            raise RuntimeError("duplicate visit for this source")
        self.sources.append(source)


class _Store:
    def __init__(self):
        self.rows: dict[str, dict] = {}

    async def put(self, collection, key, value):
        self.rows[key] = value

    async def scan_all(self, collection, limit=1000, after=None):
        return list(self.rows.values())


class _Telemetry:
    def __init__(self):
        self.events: list[str] = []

    def event(self, name, **kw):
        self.events.append(name)

    def counter(self, name, **kw):
        return None


class _Rewards:
    async def get(self, tenant, reward_id):
        return types.SimpleNamespace(id=reward_id, service_id="svc_wash", type="service")


def _container(visits):
    store = _Store()
    return types.SimpleNamespace(
        datastore=store, visits=visits, rewards=_Rewards(), telemetry=_Telemetry(),
        redeemer=types.SimpleNamespace(store=store))


def _redemption():
    rec = Redemption(tenant=TENANT, subject_ref="sub_a", reward_id="rw_1",
                     reward_name="غسيل مجاني", reward_type="service", cost=100,
                     actor="operator", idem_key="idem-1")
    rec.id = "rdm_1"
    return rec


def test_a_visit_that_lands_is_marked_on_the_receipt():
    """The mark is what makes the repair possible at all — without it the work list is unknowable."""
    c = _container(_Visits())
    rec = _redemption()

    assert run(record_free_visit(c, TENANT, rec, "operator")) is True
    assert rec.visit_recorded is True
    assert c.datastore.rows["rdm_1"]["visit_recorded"] is True


def test_a_visit_that_fails_leaves_the_receipt_saying_so():
    """THE DEFECT'S FIRST HALF. It failed soft, correctly — the customer is holding his reward —
    but it left nothing for anybody to act on."""
    c = _container(_Visits(fail=True))
    rec = _redemption()

    assert run(record_free_visit(c, TENANT, rec, "operator")) is False
    assert rec.visit_recorded is False
    assert "loyalty_free_visit_failed" in c.telemetry.events
    assert "rdm_1" not in c.datastore.rows, "an unrecorded visit must not look recorded"


def test_the_repair_records_the_visit_the_reward_owed():
    """THE DEFECT'S SECOND HALF, and the one that made it permanent: nothing replayed it."""
    from app.api import internal as I

    visits = _Visits(fail=True)
    c = _container(visits)
    rec = _redemption()
    run(record_free_visit(c, TENANT, rec, "operator"))

    # The row is on disk with the half-act recorded on it, as the real path leaves it.
    c.datastore.rows["rdm_1"] = {**rec.to_dict(), "visit_recorded": False}
    visits.fail = False

    out = run(I.replay_free_visits(_request(c)))

    assert out["owed"] == 1 and out["recorded"] == 1 and out["failed"] == 0
    assert visits.sources == ["rdm_1"], "the visit was recorded under the redemption's own id"
    assert c.datastore.rows["rdm_1"]["visit_recorded"] is True


def test_the_repair_does_not_record_a_second_visit_for_a_reward_that_had_one():
    """A repair that double-counts is worse than the gap: the shop's own visit numbers stop being
    the shop's numbers, and the reminder cycle restarts from a day nothing happened."""
    from app.api import internal as I

    visits = _Visits()
    c = _container(visits)
    rec = _redemption()
    run(record_free_visit(c, TENANT, rec, "operator"))

    out = run(I.replay_free_visits(_request(c)))

    assert out["owed"] == 0 and out["recorded"] == 0
    assert visits.sources == ["rdm_1"]


def test_a_repair_that_still_cannot_reach_operations_says_so():
    """«0 outstanding» and «I could not ask anybody» must never print the same number."""
    from app.api import internal as I

    visits = _Visits(fail=True)
    c = _container(visits)
    rec = _redemption()
    c.datastore.rows["rdm_1"] = {**rec.to_dict(), "visit_recorded": False}

    out = run(I.replay_free_visits(_request(c)))

    assert out["owed"] == 1 and out["recorded"] == 0 and out["failed"] == 1


def test_a_discount_reward_is_not_a_visit():
    """Only a service reward IS a visit. A discount is money off, and recording one as a visit
    would restart a cycle nobody serviced anything in."""
    from app.api import internal as I

    c = _container(_Visits())
    rec = _redemption()
    row = {**rec.to_dict(), "reward_type": "discount", "visit_recorded": False}
    c.datastore.rows["rdm_1"] = row

    out = run(I.replay_free_visits(_request(c)))
    assert out["owed"] == 0


def _request(container):
    return types.SimpleNamespace(
        app=types.SimpleNamespace(state=types.SimpleNamespace(container=container)))
