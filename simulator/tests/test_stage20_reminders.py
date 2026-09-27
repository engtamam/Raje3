"""New app wired into the simulator: services/reminders (`apps/reminders/`) — self-contained the
same way loyalty is (no peer needed for the doors this session wires in: the customer's own
unauthenticated prefs page, and the owner's own schedule/rules reads and writes). Real HTTP against
a real, spawned services/reminders.
"""
from __future__ import annotations

import asyncio

from simulator.apps.reminders.actions import (
    GetPrefsAction, ListRulesAction, ListScheduleAction, SetPrefsAction, SetRuleAction,
)
from simulator.apps.reminders.service import spawn as spawn_reminders
from simulator.common.engine import run_one

TENANT = "sim-reminders"


def run(coro):
    return asyncio.run(coro)


def test_an_unknown_reference_reads_the_same_default_switches_as_a_known_one():
    """The route's own documented design: no 404, ever — an unknown reference must read exactly
    like a known one, so a forwarded link can never answer "is this a real customer here?"."""

    async def _go():
        async with spawn_reminders() as svc:
            return await run_one(GetPrefsAction(
                base_url=svc.base_url, tenant=TENANT, subject_ref="sub-unknown"))

    result = run(_go())
    assert result.ok, result
    classes = {p["class"] for p in result.data["preferences"]}
    assert classes == {"service", "personal", "warning", "marketing"}
    # everything opt-out defaults ON, marketing (opt-IN, PDPL) defaults OFF with no consent yet.
    enabled = {p["class"]: p["enabled"] for p in result.data["preferences"]}
    assert enabled["service"] is True
    assert enabled["marketing"] is False


def test_stopping_a_class_and_reading_it_back_holds_and_does_not_touch_the_others():
    async def _go():
        async with spawn_reminders() as svc:
            before = await run_one(GetPrefsAction(
                base_url=svc.base_url, tenant=TENANT, subject_ref="sub-stopper"))
            stopped = await run_one(SetPrefsAction(
                base_url=svc.base_url, tenant=TENANT, subject_ref="sub-stopper",
                stopped=["warning"]))
            after = await run_one(GetPrefsAction(
                base_url=svc.base_url, tenant=TENANT, subject_ref="sub-stopper"))
            return before, stopped, after

    before, stopped, after = run(_go())
    assert before.ok and stopped.ok and after.ok
    enabled_after = {p["class"]: p["enabled"] for p in after.data["preferences"]}
    assert enabled_after["warning"] is False
    assert enabled_after["service"] is True, "stopping ONE class must never silently stop another"


def test_a_fresh_tenant_reads_a_clean_empty_schedule():
    async def _go():
        async with spawn_reminders() as svc:
            return await run_one(ListScheduleAction(base_url=svc.base_url, tenant=TENANT))

    result = run(_go())
    assert result.ok, result
    assert result.data["schedule"] == []
    assert result.data["count"] == 0


def test_overriding_a_rule_that_was_never_learned_yet_is_correctly_refused():
    """`set_rule` OVERRIDES an existing, already-learned rule row (`RuleStore.get` first) — it
    never creates one from scratch, since a rule this service has no observations for is not a
    real interval to pin. A service that never had a real visit event teach it anything has no row
    to override, and this simulator wires no real visit-event bus into reminders yet (see
    `service.py`'s own module docstring) — so the correct, honest proof here is the clean 404 this
    route gives for exactly that case, and a correspondingly empty real list."""

    async def _go():
        async with spawn_reminders() as svc:
            service_id = "srv-never-learned"
            override_attempt = await run_one(SetRuleAction(
                base_url=svc.base_url, tenant=TENANT, service_id=service_id,
                interval_days=45, lead_days=5))
            listed = await run_one(ListRulesAction(
                base_url=svc.base_url, tenant=TENANT, service_id=service_id))
            return override_attempt, listed

    override_attempt, listed = run(_go())
    assert not override_attempt.ok, \
        "overriding a rule with no learned row behind it must be refused, never silently created"
    assert listed.ok, listed
    assert listed.data["rules"] == []
