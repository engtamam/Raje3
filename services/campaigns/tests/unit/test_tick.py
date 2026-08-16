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

    async def fire(self, campaign, *, now, fired_by="system", daily_share=0):
        # `daily_share` IS PART OF THE CONTRACT NOW: a pass is bounded by the shop's slice of the
        # day's ceiling, and the tick must hand it over on the cron path exactly as the API does on
        # the press path. Recorded so a test can assert it travelled rather than assume it.
        if self.boom:
            raise RuntimeError("dispatch exploded")
        self.fired.append((campaign.get("id"), now))
        self.shares = getattr(self, "shares", [])
        self.shares.append(daily_share)
        return FakeOut(FakeRun(sent=self.sent))


@pytest.fixture
def st():
    return MemoryDataStore()


def save(st, c):
    run(st.put("campaigns", c.key, as_row(c)))
    return c


def tick(st, d, now, licence=None):
    return run(Tick(store=st, dispatcher=d, licence=licence).run("t1", now=now))


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
        async def fire(self, campaign, *, now, fired_by="system", daily_share=0):
            if campaign["goal"] == "win_back":
                raise RuntimeError("boom")
            return await Dispatcher.fire(self, campaign, now=now, fired_by=fired_by,
                                         daily_share=daily_share)

    d = Flaky()
    res = tick(st, d, at(10))
    assert len(d.fired) == 1 and res.reasons


def test_one_tenants_campaigns_are_invisible_to_another(st):
    save(st, Campaign(tenant="t2", goal="win_back", state="active"))
    d = Dispatcher()
    tick(st, d, at(10))
    assert d.fired == []


# ── the app the shop did not buy ───────────────────────────────────────────────────────────────
class _Licence:
    """Answers what billing would, and counts how often it is asked."""

    def __init__(self, allowed):
        self._allowed = allowed
        self.asked = 0

    async def allowed(self, tenant):
        self.asked += 1
        return self._allowed


def test_a_shop_without_the_app_sends_nothing_from_the_standing_rules(st):
    """THE HALF NOBODY PRESSES. «رجّع اللي غابوا» and «كافئ المخلصين» run by themselves every day,
    so a lapsed subscription would keep sending marketing for ever — the create route is not on
    that path at all."""
    save(st, Campaign(tenant="t1", goal="win_back", state="active"))
    d = Dispatcher()
    res = tick(st, d, at(9), licence=_Licence(False))

    assert d.fired == [] and res.evaluated == 0
    # AND IT SAYS WHY, in the reasons an operator reads — not silence.
    assert "الحملات ليست في اشتراكك" in res.reasons


def test_a_shop_with_the_app_is_asked_once_for_the_whole_pass(st):
    """One question per tenant, not one per campaign: the answer cannot change mid-pass, and a
    shop with twenty rules would otherwise make twenty billing calls a tick."""
    save(st, Campaign(tenant="t1", goal="win_back", state="active"))
    save(st, Campaign(tenant="t1", goal="reward_loyal", state="active"))
    d = Dispatcher()
    licence = _Licence(True)
    tick(st, d, at(9), licence=licence)

    assert licence.asked == 1 and len(d.fired) == 2


def test_a_deployment_with_no_licence_client_still_runs(st):
    """`None` is "nothing wired" — tests and local runs. Production is refused at boot instead,
    because a tick that silently stopped sending would look exactly like an empty audience."""
    save(st, Campaign(tenant="t1", goal="win_back", state="active"))
    d = Dispatcher()
    tick(st, d, at(9), licence=None)
    assert len(d.fired) == 1


# ── the pass that did not finish ───────────────────────────────────────────────────────────────
def test_a_scheduled_campaign_that_did_not_finish_stays_open(st):
    """THE DEFECT, AND IT WAS SILENT IN THE WORST WAY.

    A pass is bounded by the shop's slice of the day's ceiling, so a campaign to eight hundred
    people reaches two hundred and returns `finished=False`. The tick closed it anyway: the owner
    read a run report saying it had gone out, and the other six hundred were never contacted by
    anything, ever. The flag existed, was returned, and nothing read it.
    """
    class Partial(Dispatcher):
        async def fire(self, campaign, *, now, fired_by="system", daily_share=0):
            out = await Dispatcher.fire(self, campaign, now=now, fired_by=fired_by,
                                        daily_share=daily_share)
            out.finished = False
            return out

    c = save(st, Campaign(tenant="t1", goal="occasion", state="active", fire_at=at(12)))
    d = Partial()
    tick(st, d, at(13))

    assert run(st.get("campaigns", c.key))["state"] == "active", (
        "closing it here is how six hundred people were dropped without a trace")


def test_and_the_next_tick_continues_it(st):
    class Partial(Dispatcher):
        async def fire(self, campaign, *, now, fired_by="system", daily_share=0):
            out = await Dispatcher.fire(self, campaign, now=now, fired_by=fired_by,
                                        daily_share=daily_share)
            out.finished = False
            return out

    save(st, Campaign(tenant="t1", goal="occasion", state="active", fire_at=at(12)))
    d = Partial()
    tick(st, d, at(13))
    tick(st, d, at(14))

    assert len(d.fired) == 2, "an unfinished campaign must be picked up again"


def test_a_finished_scheduled_campaign_is_still_closed(st):
    """The other half — the guard that stopped it firing for ever must survive the fix."""
    c = save(st, Campaign(tenant="t1", goal="occasion", state="active", fire_at=at(12)))
    d = Dispatcher()
    tick(st, d, at(13))
    tick(st, d, at(14))

    assert len(d.fired) == 1
    assert run(st.get("campaigns", c.key))["state"] == "done"


def test_the_cron_path_hands_over_the_shops_share_of_the_day(st):
    """A campaign fired by the clock spends from the same ceiling as one fired by a press.
    Honouring the reserve on only one of the two paths is the same bug with better odds."""
    save(st, Campaign(tenant="t1", goal="win_back", state="active"))
    d = Dispatcher()

    async def reader(tenant):
        return 40

    run(Tick(store=st, dispatcher=d, licence=None, share_reader=reader).run("t1", now=at(10)))

    assert d.shares == [40]


def test_an_unreadable_ceiling_does_not_stop_the_campaign(st):
    """Unknown is not zero. A campaign refusing to run because we could not read a number would be
    our outage wearing the provider's ceiling."""
    save(st, Campaign(tenant="t1", goal="win_back", state="active"))
    d = Dispatcher()

    async def reader(tenant):
        raise RuntimeError("ceiling unreadable")

    run(Tick(store=st, dispatcher=d, licence=None, share_reader=reader).run("t1", now=at(10)))

    assert d.shares == [0], "0 means «unknown», and the dispatcher falls back to its pass batch"
    assert len(d.fired) == 1
