"""The tick — and the one-a-day guard the whole file exists for."""
from __future__ import annotations

import asyncio
from datetime import datetime

import pytest

from app.adapters.datastore.memory import MemoryDataStore
from app.core.models import Campaign, as_row
from app.core.tick import RIYADH, Tick, same_day

DAY = 86400


def run(c):
    return asyncio.run(c)


def at(hour, day=15, month=6):
    return int(datetime(2026, month, day, hour, tzinfo=RIYADH).timestamp())


class FakeRun:
    def __init__(self, sent=1, suppressed=0, reasons=None):
        self.sent = sent
        self.suppressed = suppressed
        self.reasons = reasons or {}


class FakeOut:
    def __init__(self, run):
        self.run = run
        self.finished = True


class Dispatcher:
    def __init__(self, sent=1, boom=False):
        self.fired = []
        self.sent = sent
        self.boom = boom

    async def fire(self, campaign, *, now, fired_by="system"):
        if self.boom:
            raise RuntimeError("dispatch exploded")
        self.fired.append((campaign.get("id"), now))
        return FakeOut(FakeRun(sent=self.sent))


@pytest.fixture
def st():
    return MemoryDataStore()


def save(st, c):
    run(st.put("campaigns", c.key, as_row(c)))
    return c


def tick(st, d, now):
    return run(Tick(store=st, dispatcher=d).run("t1", now=now))


# ── the guard ──────────────────────────────────────────────────────────────────────────────────
def test_a_standing_rule_evaluates_once_a_day_not_once_a_tick(st):
    """The cron runs every five minutes. Without the guard that is twelve evaluations an hour, and
    a win-back campaign would reach the same customer twelve times before lunch."""
    save(st, Campaign(tenant="t1", goal="win_back", state="active"))
    d = Dispatcher()
    for minute in range(0, 60, 5):
        tick(st, d, at(9) + minute * 60)
    assert len(d.fired) == 1


def test_it_evaluates_again_the_next_day(st):
    save(st, Campaign(tenant="t1", goal="win_back", state="active"))
    d = Dispatcher()
    tick(st, d, at(9, day=15))
    tick(st, d, at(9, day=16))
    assert len(d.fired) == 2


def test_the_boundary_is_a_calendar_day_not_an_elapsed_24_hours():
    """Twenty-four hours from the last run drifts forward every day until a morning campaign is
    firing at night."""
    assert same_day(at(1), at(23))
    assert not same_day(at(23, day=15), at(1, day=16))
    assert not same_day(0, at(9))


def test_the_guard_lives_on_the_campaign_not_in_a_side_table(st):
    """A flag somewhere else is the flag that gets lost — a restore that misses it turns a daily
    rule into a five-minute one, quietly, at scale."""
    c = save(st, Campaign(tenant="t1", goal="win_back", state="active"))
    tick(st, Dispatcher(), at(9))
    row = run(st.get("campaigns", c.key))
    assert row["last_evaluated"] > 0


def test_the_stamp_is_written_before_the_send(st):
    """If the send crashes halfway the campaign is still marked evaluated today: a partial run
    repeated four more times before midnight would reach the same customers again."""
    c = save(st, Campaign(tenant="t1", goal="win_back", state="active"))
    tick(st, Dispatcher(boom=True), at(9))
    assert run(st.get("campaigns", c.key))["last_evaluated"] > 0


# ── scheduled ──────────────────────────────────────────────────────────────────────────────────
def test_a_scheduled_campaign_waits_for_its_time(st):
    save(st, Campaign(tenant="t1", goal="occasion", state="active", fire_at=at(12)))
    d = Dispatcher()
    tick(st, d, at(9))
    assert d.fired == []
    tick(st, d, at(13))
    assert len(d.fired) == 1


def test_a_scheduled_campaign_is_done_after_it_fires(st):
    """One that stayed active would fire on every tick after its time passed — the same failure as
    the standing rule with no guard at all."""
    c = save(st, Campaign(tenant="t1", goal="occasion", state="active", fire_at=at(12)))
    d = Dispatcher()
    tick(st, d, at(13))
    tick(st, d, at(14))
    assert len(d.fired) == 1
    assert run(st.get("campaigns", c.key))["state"] == "done"


def test_a_scheduled_campaign_with_no_time_never_fires(st):
    save(st, Campaign(tenant="t1", goal="occasion", state="active", fire_at=0))
    d = Dispatcher()
    tick(st, d, at(13))
    assert d.fired == []


# ── manual and paused ──────────────────────────────────────────────────────────────────────────
def test_the_tick_never_fires_a_manual_campaign(st):
    """The owner presses the button. Reaching that branch means one was left active — harmless,
    and skipped rather than fired."""
    save(st, Campaign(tenant="t1", goal="announce", state="active"))
    d = Dispatcher()
    tick(st, d, at(10))
    assert d.fired == []


def test_a_paused_campaign_is_not_touched(st):
    save(st, Campaign(tenant="t1", goal="win_back", state="paused"))
    d = Dispatcher()
    tick(st, d, at(10))
    assert d.fired == []


# ── the awareness lock ─────────────────────────────────────────────────────────────────────────
def test_awareness_locks_for_thirty_days_after_it_sends(st):
    c = save(st, Campaign(tenant="t1", goal="awareness", state="active", trigger="standing"))
    tick(st, Dispatcher(sent=3), at(10, day=1))
    row = run(st.get("campaigns", c.key))
    assert row["locked_until"] >= at(10, day=1) + 29 * DAY


def test_a_locked_campaign_does_not_fire(st):
    save(st, Campaign(tenant="t1", goal="awareness", state="active", trigger="standing",
                      locked_until=at(10, day=20)))
    d = Dispatcher()
    tick(st, d, at(10, day=10))
    assert d.fired == []


def test_a_run_that_reached_nobody_does_not_cost_the_owner_a_month(st):
    """Locking after a send that never happened takes thirty days for nothing."""
    c = save(st, Campaign(tenant="t1", goal="awareness", state="active", trigger="standing"))
    tick(st, Dispatcher(sent=0), at(10))
    assert int(run(st.get("campaigns", c.key)).get("locked_until") or 0) == 0


# ── failure isolation ──────────────────────────────────────────────────────────────────────────
def test_one_broken_campaign_does_not_freeze_the_others(st):
    """The symptom would be 'nothing sends' rather than 'one campaign is broken'."""
    save(st, Campaign(tenant="t1", goal="win_back", state="active"))
    save(st, Campaign(tenant="t1", goal="reward_loyal", state="active"))

    class Flaky(Dispatcher):
        async def fire(self, campaign, *, now, fired_by="system"):
            if campaign["goal"] == "win_back":
                raise RuntimeError("boom")
            return await Dispatcher.fire(self, campaign, now=now, fired_by=fired_by)

    d = Flaky()
    res = tick(st, d, at(10))
    assert len(d.fired) == 1 and res.reasons


def test_one_tenants_campaigns_are_invisible_to_another(st):
    save(st, Campaign(tenant="t2", goal="win_back", state="active"))
    d = Dispatcher()
    tick(st, d, at(10))
    assert d.fired == []
