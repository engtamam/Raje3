"""Which message a visit schedules — the plain confirmation, or the rating app's own, NEVER both.

`rating_eligible` is resolved by the caller (does this shop own feature.rating AND has it turned
on) and overrides `confirm_visits` entirely — one message per visit, always.
"""
from __future__ import annotations

import asyncio

import pytest

from app.adapters.datastore.memory import MemoryDataStore
from app.core import adaptive, engagement
from app.core.scheduling import Scheduler
from app.core.stores import ScheduleStore

NOW = 1_800_000_000


def run(c):
    return asyncio.run(c)


@pytest.fixture
def st():
    return MemoryDataStore()


@pytest.fixture
def sch(st):
    return Scheduler(store=st, cfg=adaptive.AdaptiveConfig(), eng_cfg=engagement.EngagementConfig())


def visit(**over):
    e = {"tenant": "t1", "subject_ref": "sub_a", "visit_id": "vis_1",
        "service_ids": ["wash"], "occurred_at": NOW, "created": NOW, "branch_id": "b1"}
    e.update(over)
    return e


CFG = {"wash": {"cycle_days": 0, "lead_days": 0, "follow_up_days": 0}}


def rows_for(st, kind, tenant="t1", subject="sub_a"):
    return [r for r in run(ScheduleStore(st).pending_for_subject(tenant, subject))
            if r["kind"] == kind]


def test_rating_eligible_schedules_the_rating_kind_not_the_plain_confirmation(st, sch):
    out = run(sch.on_visit(visit(), now=NOW, service_config=CFG, confirm_visits=True,
                           rating_eligible=True, rating_delay_seconds=900))
    assert rows_for(st, "rating_request")
    assert not rows_for(st, "visit_confirmation")
    assert any(k.endswith("|rating_request") for k in out.scheduled)


def test_rating_eligible_uses_the_configured_delay(st, sch):
    run(sch.on_visit(visit(), now=NOW, service_config=CFG, rating_eligible=True,
                     rating_delay_seconds=7200))
    row = rows_for(st, "rating_request")[0]
    assert row["due_at"] == NOW + 7200


def test_rating_eligible_carries_the_visit_id_and_branch(st, sch):
    run(sch.on_visit(visit(branch_id="b9"), now=NOW, service_config=CFG, rating_eligible=True))
    row = rows_for(st, "rating_request")[0]
    assert row["visit_id"] == "vis_1"
    assert row["branch_id"] == "b9"


def test_rating_eligible_uses_the_rating_requested_template_type(st, sch):
    run(sch.on_visit(visit(), now=NOW, service_config=CFG, rating_eligible=True))
    row = rows_for(st, "rating_request")[0]
    assert row["template_type"] == "svc_visit_confirmation_rating"


def test_not_rating_eligible_schedules_the_plain_confirmation_as_before(st, sch):
    run(sch.on_visit(visit(), now=NOW, service_config=CFG, confirm_visits=True,
                     rating_eligible=False))
    assert rows_for(st, "visit_confirmation")
    assert not rows_for(st, "rating_request")


def test_rating_eligible_overrides_confirm_visits_true(st, sch):
    """The shop's own rating-app decision supersedes the older plain switch — never both messages
    even when confirm_visits is still on."""
    run(sch.on_visit(visit(), now=NOW, service_config=CFG, confirm_visits=True,
                     rating_eligible=True))
    assert not rows_for(st, "visit_confirmation")


def test_rating_eligible_overrides_confirm_visits_false_too(st, sch):
    """A shop that switched off the plain confirmation still gets the rating message once the app
    is on — the rating app's own enabled flag is what decides this slot now, not the old switch."""
    run(sch.on_visit(visit(), now=NOW, service_config=CFG, confirm_visits=False,
                     rating_eligible=True))
    assert rows_for(st, "rating_request")


def test_neither_rating_nor_confirm_sends_nothing_in_this_slot(st, sch):
    run(sch.on_visit(visit(), now=NOW, service_config=CFG, confirm_visits=False,
                     rating_eligible=False))
    assert not rows_for(st, "rating_request")
    assert not rows_for(st, "visit_confirmation")


def test_default_rating_eligible_is_false_existing_callers_unaffected(st, sch):
    """A caller that has not been taught about the rating app yet (an old call site, or a test
    that predates this feature) must keep behaving exactly as before."""
    run(sch.on_visit(visit(), now=NOW, service_config=CFG, confirm_visits=True))
    assert rows_for(st, "visit_confirmation")
    assert not rows_for(st, "rating_request")


def test_two_different_tenants_are_scheduled_independently(st, sch):
    run(sch.on_visit(visit(tenant="t1", subject_ref="sub_a"), now=NOW, service_config=CFG,
                     rating_eligible=True))
    run(sch.on_visit(visit(tenant="t2", subject_ref="sub_b", visit_id="vis_2"), now=NOW,
                     service_config=CFG, rating_eligible=False, confirm_visits=True))
    assert rows_for(st, "rating_request", tenant="t1", subject="sub_a")
    assert rows_for(st, "visit_confirmation", tenant="t2", subject="sub_b")
    assert not rows_for(st, "rating_request", tenant="t2", subject="sub_b")
