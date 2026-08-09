"""Both paths into the scheduler — and the one that repairs the other."""
from __future__ import annotations

import asyncio

import pytest

from app.adapters.datastore.memory import MemoryDataStore
from app.core import adaptive, engagement
from app.core.ingest import Ingest
from app.core.scheduling import Scheduler
from app.core.stores import ScheduleStore
from app.ports.event_bus import Event

NOW = 1_800_000_000
CFG = {"oil": {"cycle_days": 90, "lead_days": 7, "follow_up_days": 0}}


def run(c):
    return asyncio.run(c)


class FakeVisits:
    """operations' catch-up route, paged."""

    def __init__(self, visits, page=2):
        self.visits = visits
        self.page = page
        self.calls = []

    async def since(self, *, tenant, since):
        self.calls.append(since)
        # An empty tenant means EVERY tenant — the same contract as the real route, which is what
        # makes discovery able to bootstrap.
        fresh = [v for v in self.visits
                 if v["created"] > since and (not tenant or v["tenant"] == tenant)]
        batch = fresh[:self.page]
        return {"visits": batch, "count": len(batch),
                "watermark": max([v["created"] for v in batch] + [since]),
                "more": len(fresh) > self.page}


def visit(n, tenant="t1"):
    return {"tenant": tenant, "subject_ref": f"sub_{n}", "visit_id": f"vis_{n}",
            "service_ids": ["oil"], "occurred_at": NOW, "created": NOW + n}


@pytest.fixture
def st():
    return MemoryDataStore()


@pytest.fixture
def ing(st):
    s = Scheduler(store=st, cfg=adaptive.AdaptiveConfig(),
                  eng_cfg=engagement.EngagementConfig())
    return Ingest(store=st, scheduler=s, visits_client=FakeVisits([visit(i) for i in range(1, 6)]))


def test_the_event_path_schedules_immediately(st, ing):
    run(ing.on_event(Event(type="operations.visit.recorded", payload=visit(1)),
                     now=NOW, service_config=CFG))
    assert run(ScheduleStore(st).pending_for_subject("t1", "sub_1"))


def test_a_missed_event_is_repaired_by_the_read(st, ing):
    """The bus is at-most-once: a subscriber that is restarting does not receive the event, and
    nothing records that it missed one. For this service that is a reminder that never exists."""
    out = run(ing.catch_up("t1", now=NOW, service_config=CFG))
    assert out["read"] == 5 and out["scheduled"] == 5
    for i in range(1, 6):
        assert run(ScheduleStore(st).pending_for_subject("t1", f"sub_{i}"))


def test_the_catch_up_does_not_redo_what_the_event_already_did(st, ing):
    """Both paths call the same idempotent handler, so overlap is free."""
    run(ing.on_event(Event(type="x", payload=visit(1)), now=NOW, service_config=CFG))
    out = run(ing.catch_up("t1", now=NOW, service_config=CFG))
    assert out["scheduled"] == 4


def test_the_watermark_stops_the_next_run_re_reading_everything(st, ing):
    run(ing.catch_up("t1", now=NOW, service_config=CFG))
    out = run(ing.catch_up("t1", now=NOW, service_config=CFG))
    assert out["read"] == 0
    assert ing._visits.calls[-1] == NOW + 5


def test_the_catch_up_is_bounded_and_resumes_next_run(st, ing):
    """A tenant offline for a month must not be drained in one request — progress beats
    completeness on a repair path."""
    out = run(ing.catch_up("t1", now=NOW, service_config=CFG, max_batches=1))
    assert out["batches"] == 1 and out["read"] == 2
    out2 = run(ing.catch_up("t1", now=NOW, service_config=CFG))
    assert out2["read"] == 3


def test_the_watermark_advances_only_after_the_batch_is_processed(st, ing):
    """Advancing first means a crash mid-batch skips those visits permanently — the exact failure
    this file exists to prevent."""
    class Boom(Scheduler):
        async def on_visit(self, *a, **k):
            raise RuntimeError("crash mid-batch")
    bad = Ingest(store=st, scheduler=Boom(store=st, cfg=adaptive.AdaptiveConfig(),
                                          eng_cfg=engagement.EngagementConfig()),
                 visits_client=FakeVisits([visit(1)]))
    with pytest.raises(RuntimeError):
        run(bad.catch_up("t1", now=NOW, service_config=CFG))
    assert run(bad._watermark("t1")) == 0


def test_a_broken_event_never_takes_the_subscriber_down(st):
    """The bus swallows subscriber exceptions anyway, so raising buys nothing and loses the
    telemetry — and the catch-up repairs whatever this drops."""
    class Boom(Scheduler):
        async def on_visit(self, *a, **k):
            raise RuntimeError("bad payload")
    ing = Ingest(store=st, scheduler=Boom(store=st, cfg=adaptive.AdaptiveConfig(),
                                          eng_cfg=engagement.EngagementConfig()))
    run(ing.on_event(Event(type="x", payload=visit(1)), now=NOW))


def test_catch_up_never_crosses_a_tenant(st, ing):
    ing._visits = FakeVisits([visit(1, "t1"), visit(2, "t2")])
    run(ing.catch_up("t1", now=NOW, service_config=CFG))
    assert run(ScheduleStore(st).pending_for_subject("t2", "sub_2")) == []


def test_discovery_bootstraps_a_tenant_we_have_never_heard_of(st, ing):
    """The per-tenant catch-up cannot start: the tick derives its tenant list from pending
    schedules, so an establishment whose FIRST event was missed has no schedule, is never in the
    list, and is never caught up — for ever. Found on a live cluster, not by a test: every test
    here hands the ingest a tenant name."""
    out = run(ing.discover(now=NOW, service_config=CFG))
    assert out["read"] == 5 and out["scheduled"] == 5
    assert ing._visits.calls[0] == 0


def test_the_global_cursor_does_not_collide_with_a_tenants_own(st, ing):
    run(ing.discover(now=NOW, service_config=CFG))
    assert run(ing._watermark("_all")) == NOW + 5
    assert run(ing._watermark("t1")) == 0
