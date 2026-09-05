"""Ingest threads rating_eligible/rating_delay_seconds through BOTH paths, resolved per tenant —
same discipline confirm_visits/service_config already have (ج-5): a single answer computed once
for a multi-tenant catch-up would apply one shop's rating settings to another shop's customer.
"""
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
CFG = {"wash": {"cycle_days": 0, "lead_days": 0, "follow_up_days": 0}}


def run(c):
    return asyncio.run(c)


class FakeVisits:
    def __init__(self, visits):
        self.visits = visits

    async def since(self, *, tenant, since):
        fresh = [v for v in self.visits
                if v["created"] > since and (not tenant or v["tenant"] == tenant)]
        return {"visits": fresh, "count": len(fresh),
                "watermark": max([v["created"] for v in fresh] + [since]), "more": False}


def visit(n, tenant="t1"):
    return {"tenant": tenant, "subject_ref": f"sub_{n}", "visit_id": f"vis_{n}",
           "service_ids": ["wash"], "occurred_at": NOW, "created": NOW + n}


@pytest.fixture
def st():
    return MemoryDataStore()


def _ing(st, visits):
    s = Scheduler(store=st, cfg=adaptive.AdaptiveConfig(), eng_cfg=engagement.EngagementConfig())
    return Ingest(store=st, scheduler=s, visits_client=FakeVisits(visits))


def rows_for(st, kind, tenant, subject):
    return [r for r in run(ScheduleStore(st).pending_for_subject(tenant, subject))
           if r["kind"] == kind]


# ── on_event (the bus fast path) ──────────────────────────────────────────────────────────────
def test_on_event_with_a_plain_true_schedules_the_rating_kind(st):
    ing = _ing(st, [])
    run(ing.on_event(Event(type="operations.visit.recorded", payload=visit(1)), now=NOW,
                     service_config=CFG, rating_eligible=True, rating_delay_seconds=900))
    rows = rows_for(st, "rating_request", "t1", "sub_1")
    assert rows and rows[0]["due_at"] == NOW + 900


def test_on_event_with_a_resolver_asks_it_with_the_events_own_tenant(st):
    seen = []

    async def resolver(t):
        seen.append(t)
        return True

    ing = _ing(st, [])
    run(ing.on_event(Event(type="operations.visit.recorded", payload=visit(1, tenant="t9")),
                     now=NOW, service_config=CFG, rating_eligible=resolver))
    assert seen == ["t9"]
    assert rows_for(st, "rating_request", "t9", "sub_1")


def test_on_event_default_rating_eligible_is_false(st):
    ing = _ing(st, [])
    run(ing.on_event(Event(type="operations.visit.recorded", payload=visit(1)), now=NOW,
                     service_config=CFG, confirm_visits=True))
    assert rows_for(st, "visit_confirmation", "t1", "sub_1")
    assert not rows_for(st, "rating_request", "t1", "sub_1")


# ── catch_up (the tick's repair path) — per-VISIT tenant, not per-call ────────────────────────
def test_catch_up_resolves_rating_eligibility_per_visits_own_tenant(st):
    calls = []

    async def resolver(t):
        calls.append(t)
        return t == "t_rating_on"          # only ONE of the two tenants owns/enabled the app

    ing = _ing(st, [visit(1, tenant="t_rating_on"), visit(2, tenant="t_rating_off")])
    run(ing.catch_up("", now=NOW, service_config=CFG, rating_eligible=resolver))

    assert set(calls) == {"t_rating_on", "t_rating_off"}
    assert rows_for(st, "rating_request", "t_rating_on", "sub_1")
    assert not rows_for(st, "rating_request", "t_rating_off", "sub_2")
    assert rows_for(st, "visit_confirmation", "t_rating_off", "sub_2")


def test_catch_up_resolves_each_tenants_own_delay(st):
    async def delay_for(t):
        return {"t_a": 900, "t_b": 7200}[t]

    ing = _ing(st, [visit(1, tenant="t_a"), visit(2, tenant="t_b")])
    run(ing.catch_up("", now=NOW, service_config=CFG, rating_eligible=True,
                     rating_delay_seconds=delay_for))

    a = rows_for(st, "rating_request", "t_a", "sub_1")[0]
    b = rows_for(st, "rating_request", "t_b", "sub_2")[0]
    assert a["due_at"] == NOW + 900
    assert b["due_at"] == NOW + 7200


def test_a_plain_bool_still_works_for_the_single_tenant_path(st):
    ing = _ing(st, [visit(1)])
    run(ing.catch_up("t1", now=NOW, service_config=CFG, rating_eligible=True,
                     rating_delay_seconds=1200))
    row = rows_for(st, "rating_request", "t1", "sub_1")[0]
    assert row["due_at"] == NOW + 1200


def test_discover_forwards_rating_params_to_catch_up(st):
    seen = []

    async def resolver(t):
        seen.append(t)
        return True

    ing = _ing(st, [visit(1, tenant="t1")])
    run(ing.discover(now=NOW, service_config=CFG, rating_eligible=resolver))
    assert seen == ["t1"]
    assert rows_for(st, "rating_request", "t1", "sub_1")
