"""Consuming a visit — the only input this service has."""
from __future__ import annotations

import asyncio

import pytest

from app.adapters.datastore.memory import MemoryDataStore
from app.core import adaptive, engagement
from app.core.scheduling import DAY, Scheduler
from app.core.stores import EngagementStore, RuleStore, ScheduleStore

NOW = 1_800_000_000


def run(c):
    return asyncio.run(c)


@pytest.fixture
def st():
    return MemoryDataStore()


@pytest.fixture
def sch(st):
    return Scheduler(store=st, cfg=adaptive.AdaptiveConfig(),
                     eng_cfg=engagement.EngagementConfig())


def visit(**over):
    e = {"tenant": "t1", "subject_ref": "sub_a", "visit_id": "vis_1",
         "service_ids": ["oil"], "occurred_at": NOW, "created": NOW, "branch_id": "b1"}
    e.update(over)
    return e


CFG = {"oil": {"cycle_days": 90, "lead_days": 7, "follow_up_days": 0},
       "tyres": {"cycle_days": 180, "lead_days": 7, "follow_up_days": 7},
       "wash": {"cycle_days": 0, "lead_days": 0, "follow_up_days": 0},
       "major": {"cycle_days": 365, "lead_days": 7, "follow_up_days": 14}}



def service_rows(outcome):
    """What the SERVICES produced — the reminder and the follow-ups, not the confirmation.

    EVERY VISIT NOW ALSO SCHEDULES A CONFIRMATION, which is a reply to what the customer just did
    rather than a consequence of any service on the visit: a service switched off silences its
    reminder and has nothing to say about whether we acknowledge the visit at all. These tests were
    written when `scheduled` meant service rows only, and their INTENT is unchanged — this helper
    keeps them asking what they always asked.
    """
    # THE KEY IS PIPE-SEPARATED — (tenant|subject|service|kind). Filtering on a colon matched
    # nothing and the tests still failed, saying the same thing twice.
    return [k for k in outcome.scheduled if not k.endswith("|visit_confirmation")]


def stored(store, tenant="t1", subject="sub_a"):
    """The rows a visit produced FOR ITS SERVICES — the confirmation is not one of them."""
    from app.core.stores import ScheduleStore
    return [r for r in run(ScheduleStore(store).pending_for_subject(tenant, subject))
            if r["kind"] != "visit_confirmation"]

def test_a_visit_produces_a_reminder(st, sch):
    out = run(sch.on_visit(visit(), now=NOW, service_config=CFG))
    assert len(service_rows(out)) == 1
    rows = stored(st)
    assert rows[0]["service_id"] == "oil" and rows[0]["due_at"] == NOW + 83 * DAY


def test_three_services_produce_one_merged_reminder(st, sch):
    """Two rows become one delivered message and one unexplained suppression once the daily cap
    runs, and the owner reads that as a cap bug (spec 5.8: merge before counting)."""
    run(sch.on_visit(visit(service_ids=["oil", "tyres", "major"]), now=NOW, service_config=CFG))
    rows = [r for r in run(ScheduleStore(st).pending_for_subject("t1", "sub_a"))
            if r["kind"] == "reminder"]
    assert len(rows) == 1
    assert rows[0]["service_id"] == "oil"          # the earliest due, not the first listed
    assert sorted(rows[0]["also_services"]) == ["major", "tyres"]


def test_the_merged_reminder_follows_the_soonest_service_not_the_first(st, sch):
    """Otherwise the message arrives after the sooner service is already overdue."""
    run(sch.on_visit(visit(service_ids=["major", "oil"]), now=NOW, service_config=CFG))
    rows = [r for r in run(ScheduleStore(st).pending_for_subject("t1", "sub_a"))
            if r["kind"] == "reminder"]
    assert rows[0]["service_id"] == "oil"


def test_a_service_with_no_cycle_does_not_suppress_the_ones_that_have_one(st, sch):
    """A puncture repair contributes nothing to schedule and must not silence the oil change."""
    run(sch.on_visit(visit(service_ids=["wash", "oil"]), now=NOW, service_config=CFG))
    rows = [r for r in run(ScheduleStore(st).pending_for_subject("t1", "sub_a"))
            if r["kind"] == "reminder"]
    assert len(rows) == 1 and rows[0]["service_id"] == "oil"


def test_a_wash_alone_schedules_nothing(st, sch):
    out = run(sch.on_visit(visit(service_ids=["wash"]), now=NOW, service_config=CFG))
    assert service_rows(out) == []


def test_a_follow_up_is_scheduled_only_where_it_is_configured(st, sch):
    """A car wash does not deserve a message asking how the wash went (spec 5.6)."""
    run(sch.on_visit(visit(service_ids=["tyres", "wash"]), now=NOW, service_config=CFG))
    kinds = {r["kind"] for r in stored(st)}
    assert kinds == {"reminder", "follow_up"}


def test_a_return_visit_cancels_the_pending_follow_up(st, sch):
    """Asking how last month's service went while the customer stands at the counter."""
    run(sch.on_visit(visit(service_ids=["tyres"]), now=NOW, service_config=CFG))
    out = run(sch.on_visit(visit(visit_id="vis_2", service_ids=["tyres"],
                                 occurred_at=NOW + 3 * DAY), now=NOW + 3 * DAY,
                           service_config=CFG))
    assert out.cancelled == 1


def test_a_second_visit_moves_the_reminder_rather_than_adding_one(st, sch):
    """And it may move it EARLIER: a customer who came back after 40 days has told us their real
    rhythm, and the first observation is trusted over the sector default."""
    run(sch.on_visit(visit(), now=NOW, service_config=CFG))
    first = run(ScheduleStore(st).pending_for_subject("t1", "sub_a"))[0]["due_at"]
    run(sch.on_visit(visit(visit_id="vis_2", occurred_at=NOW + 40 * DAY),
                     now=NOW + 40 * DAY, service_config=CFG))
    rows = [r for r in run(ScheduleStore(st).pending_for_subject("t1", "sub_a"))
            if r["kind"] == "reminder"]
    assert len(rows) == 1 and rows[0]["due_at"] != first
    assert rows[0]["due_at"] == NOW + 40 * DAY + 33 * DAY


def test_a_redelivered_event_changes_nothing(st, sch):
    """At-least-once delivery is not a failure. Double-counting would halve the customer's
    estimated cycle on a bus hiccup."""
    run(sch.on_visit(visit(), now=NOW, service_config=CFG))
    before = run(EngagementStore(st).get("t1", "sub_a"))["score"]
    out = run(sch.on_visit(visit(), now=NOW, service_config=CFG))
    assert out.duplicate is True
    assert run(EngagementStore(st).get("t1", "sub_a"))["score"] == before


def test_the_interval_is_learned_from_the_gap_before_it_is_overwritten(st, sch):
    """Learning after the update would compare a timestamp to itself and observe zero."""
    run(sch.on_visit(visit(), now=NOW, service_config=CFG))
    run(sch.on_visit(visit(visit_id="v2", occurred_at=NOW + 120 * DAY),
                     now=NOW + 120 * DAY, service_config=CFG))
    rule = run(RuleStore(st).get("t1|sub_a|oil"))
    assert rule["interval_days"] == 120 and rule["observations"] == 1


def test_an_anomalous_gap_is_counted_but_not_learned(st, sch):
    run(sch.on_visit(visit(), now=NOW, service_config=CFG))
    run(sch.on_visit(visit(visit_id="v2", occurred_at=NOW + 60 * DAY),
                     now=NOW + 60 * DAY, service_config=CFG))
    run(sch.on_visit(visit(visit_id="v3", occurred_at=NOW + 700 * DAY),
                     now=NOW + 700 * DAY, service_config=CFG))
    rule = run(RuleStore(st).get("t1|sub_a|oil"))
    assert rule["anomalies"] == 1
    # Three visits, two gaps, one of them an outlier — so ONE observation, not two. Counting the
    # anomaly would let a run of outliers graduate the estimate to "learned" while nothing was
    # actually learned from them.
    assert rule["observations"] == 1
    assert rule["interval_days"] == 60


def test_the_visit_credits_the_engagement_score(st, sch):
    run(sch.on_visit(visit(), now=NOW, service_config=CFG))
    row = run(EngagementStore(st).get("t1", "sub_a"))
    assert row["score"] == 10.0


def test_a_visit_drained_from_an_offline_till_keeps_its_own_date(st, sch):
    """It happened when it happened; treating it as happening at drain time would put a week of
    visits on one day."""
    happened = NOW - 5 * DAY
    run(sch.on_visit(visit(occurred_at=happened), now=NOW, service_config=CFG))
    rule = run(RuleStore(st).get("t1|sub_a|oil"))
    assert rule["last_visit_at"] == happened


def test_a_malformed_event_is_ignored_not_crashed_on(st, sch):
    for bad in ({}, {"tenant": "t1"}, {"tenant": "t1", "subject_ref": "s", "service_ids": []}):
        assert service_rows(run(sch.on_visit(bad, now=NOW, service_config=CFG))) == []


def test_one_tenant_never_schedules_into_another(st, sch):
    run(sch.on_visit(visit(), now=NOW, service_config=CFG))
    run(sch.on_visit(visit(tenant="t2", visit_id="v9"), now=NOW, service_config=CFG))
    assert len(stored(st)) == 1


# ── the settings tree reaches the scheduler (spec §10.8.1) ─────────────────────────────────────
def test_a_service_switched_off_schedules_nothing(st, sch):
    """Checked when the schedule is CREATED, not when it is sent: a row that exists and is
    filtered later shows up under 'what is coming' for a service the owner switched off, and they
    would reasonably call that a bug."""
    cfg = dict(CFG, oil=dict(CFG["oil"], enabled=False))
    out = run(sch.on_visit(visit(), now=NOW, service_config=cfg))
    assert service_rows(out) == []


def test_switching_one_service_off_does_not_silence_the_others(st, sch):
    cfg = dict(CFG, oil=dict(CFG["oil"], enabled=False))
    run(sch.on_visit(visit(service_ids=["oil", "tyres"]), now=NOW, service_config=cfg))
    rows = [r for r in run(ScheduleStore(st).pending_for_subject("t1", "sub_a"))
            if r["kind"] == "reminder"]
    assert len(rows) == 1 and rows[0]["service_id"] == "tyres"


def test_a_switched_off_service_schedules_no_follow_up_either(st, sch):
    cfg = dict(CFG, tyres=dict(CFG["tyres"], enabled=False))
    run(sch.on_visit(visit(service_ids=["tyres"]), now=NOW, service_config=cfg))
    assert stored(st) == []


def test_a_service_with_no_setting_at_all_still_schedules(st, sch):
    """An absent entry and an empty one mean the same thing: the tree's defaults already applied."""
    out = run(sch.on_visit(visit(service_ids=["unknown_service"]), now=NOW, service_config={}))
    assert len(service_rows(out)) == 1


def test_two_cars_on_one_number_get_two_reminders(st, sch):
    """«ممكن عندي سيارتين برقمي» — and the cycle belongs to the CAR, not to the phone.

    THE NATURAL KEY DID NOT CARRY THE ASSET, so an oil change on the second car collided with the
    first car's schedule and UPDATED it. One row where there should be two: a whole vehicle fell
    out of the product silently, and the owner would have seen nothing wrong — the reminder he did
    get was correct, and the one he never got left no trace.

    The event has carried `asset_id` since the beginning. Nothing read it.
    """
    run(sch.on_visit(visit(visit_id="v1", asset_id="ast_camry"), now=NOW, service_config=CFG))
    run(sch.on_visit(visit(visit_id="v2", asset_id="ast_hilux"), now=NOW, service_config=CFG))

    rows = [r for r in run(ScheduleStore(st).pending_for_subject("t1", "sub_a"))
            if r["kind"] == "reminder"]
    assert len(rows) == 2
    assert sorted(r["asset_id"] for r in rows) == ["ast_camry", "ast_hilux"]


def test_a_sector_without_cars_keeps_the_key_it_always_had(st, sch):
    """A salon has no asset, and its schedules must not be re-keyed by this change — a new key
    shape would orphan every row already scheduled and re-send what was already sent."""
    out = run(sch.on_visit(visit(visit_id="v3"), now=NOW, service_config=CFG))
    assert service_rows(out) == ["t1|sub_a|oil|reminder"]
