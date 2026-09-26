"""The tick — and the one-a-day guard the whole file exists for."""
from __future__ import annotations

import asyncio
from datetime import datetime

import pytest

from app.adapters.datastore.memory import MemoryDataStore
from app.core import milestone
from app.core.models import Campaign, as_row
from app.core.tick import RIYADH, Tick, same_day

DAY = 86400


def run(c):
    return asyncio.run(c)


def at(hour, day=15, month=6):
    return int(datetime(2026, month, day, hour, tzinfo=RIYADH).timestamp())


class FakeRun:
    def __init__(self, sent=1, suppressed=0, reasons=None, matched=None):
        self.sent = sent
        self.suppressed = suppressed
        self.reasons = reasons or {}
        # DEFAULTS TO `sent` — realistic for every existing test, none of which reads `matched` at
        # all; the milestone branch (`tick.py`) is the first caller that does.
        self.matched = sent if matched is None else matched


class FakeOut:
    def __init__(self, run):
        self.run = run
        self.finished = True


class Dispatcher:
    def __init__(self, sent=1, boom=False, matched=None):
        self.fired = []
        self.sent = sent
        self.matched = matched
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
        return FakeOut(FakeRun(sent=self.sent, matched=self.matched))


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
def test_a_manual_campaign_that_was_created_and_never_sent_is_rescued(st):
    """This test used to assert the opposite, and its docstring said «harmless».

    It is not harmless. The create route writes the campaign row and THEN fires inside the same
    request; a pod evicted between those two steps leaves a manual campaign at `active` having
    reached nobody. The owner's screen shows it as فعّالة so he does not press again, and this
    branch — the only thing that ever looks at it — used to count it as skipped for ever.
    """
    c = save(st, Campaign(tenant="t1", goal="announce", state="active"))
    d = Dispatcher()
    tick(st, d, at(10))
    assert len(d.fired) == 1, "a campaign he launched and that never went out must be picked up"
    assert run(st.get("campaigns", c.key))["last_evaluated"] == at(10)


def test_a_manual_campaign_that_already_ran_is_never_fired_again(st):
    """The mirror image, and the reason the rescue is keyed on `last_evaluated` rather than state.

    Re-firing a finished manual campaign would send a second copy to everyone who already got
    one — the exact damage the rescue exists to prevent, caused by the rescue itself.
    """
    save(st, Campaign(tenant="t1", goal="announce", state="active", last_evaluated=at(9)))
    d = Dispatcher()
    tick(st, d, at(10))
    assert d.fired == []


def test_a_manual_campaign_with_a_future_fire_at_is_not_rescued_early(st):
    """2026-09-12 — a future `fire_at` (any goal now, delegated to job-service) means this
    campaign is not «never sent», it is «not due yet». The manual-rescue branch must not race
    job-service's own delayed job and fire it early just because `last_evaluated == 0`."""
    c = save(st, Campaign(tenant="t1", goal="announce", state="active", fire_at=at(12)))
    d = Dispatcher()
    tick(st, d, at(10))
    assert d.fired == [], "still before its own fire_at — must wait, not rescue"
    assert run(st.get("campaigns", c.key))["last_evaluated"] == 0


def test_once_its_own_fire_at_passes_the_ordinary_rescue_still_catches_it(st):
    """The safety net job-service's own absence (or failure) falls back to — unchanged from
    before this feature existed, just for every goal now instead of only «مناسبة عميلك»."""
    c = save(st, Campaign(tenant="t1", goal="announce", state="active", fire_at=at(9)))
    d = Dispatcher()
    tick(st, d, at(10))
    assert len(d.fired) == 1
    assert run(st.get("campaigns", c.key))["last_evaluated"] == at(10)


def test_a_paused_campaign_is_not_touched(st):
    save(st, Campaign(tenant="t1", goal="win_back", state="paused"))
    d = Dispatcher()
    tick(st, d, at(10))
    assert d.fired == []


# ── milestone ─────────────────────────────────────────────────────────────────────────────────
def test_a_milestone_campaign_is_evaluated_every_tick_never_throttled_to_once_a_day(st):
    """Unlike `standing`, a shared counter can cross its threshold at any minute — repeated ticks
    inside the same hour (even the same Riyadh calendar day) must all be real passes, never
    skipped after the first the way `same_day()` throttles a standing rule."""
    save(st, Campaign(tenant="t1", goal="community_milestone", state="active",
                      milestone_threshold=100))
    d = Dispatcher(matched=0)
    for minute in range(0, 20, 5):
        tick(st, d, at(9) + minute * 60)
    assert len(d.fired) == 4, "every pass must be a real fire, not throttled like `standing`"


def test_a_milestone_campaign_not_yet_crossed_stays_active(st):
    """No progress row at all yet (nobody has contributed) — an ordinary, harmless no-op pass,
    and the campaign must not be mistaken for done."""
    c = save(st, Campaign(tenant="t1", goal="community_milestone", state="active",
                         milestone_threshold=10))
    d = Dispatcher(matched=0)
    tick(st, d, at(9))
    assert len(d.fired) == 1
    assert run(st.get("campaigns", c.key))["state"] == "active"


def test_a_milestone_campaign_still_draining_its_cohort_stays_active(st):
    """Fired, but this pass reached some of the cohort and left more for next time (a large
    cohort against a small per-pass cap) — `result.finished=True` from the dispatcher's own "did
    not hit the cap" sense, but `matched` is still non-zero, so this must NOT be marked done."""
    c = save(st, Campaign(tenant="t1", goal="community_milestone", state="active",
                         milestone_threshold=2))
    run(milestone.record_contribution(st, tenant="t1", campaign_id=c.id, threshold=2,
                                     subject_ref="a", now=at(8)))
    run(milestone.record_contribution(st, tenant="t1", campaign_id=c.id, threshold=2,
                                     subject_ref="b", now=at(8) + 1))
    d = Dispatcher(sent=2, matched=2)
    tick(st, d, at(9))
    assert len(d.fired) == 1
    assert run(st.get("campaigns", c.key))["state"] == "active"


def test_a_milestone_campaign_is_marked_done_once_its_cohort_is_fully_drained(st):
    """Fired, AND this pass matched nobody new — every contributor is already in
    `already_reached`, so the one-shot reveal is complete. This is the ONE case that transitions
    to `done`, exactly the one-shot shape a `scheduled` campaign already has."""
    c = save(st, Campaign(tenant="t1", goal="community_milestone", state="active",
                         milestone_threshold=1))
    run(milestone.record_contribution(st, tenant="t1", campaign_id=c.id, threshold=1,
                                     subject_ref="a", now=at(8)))
    d = Dispatcher(sent=0, matched=0)
    tick(st, d, at(9))
    assert len(d.fired) == 1
    assert run(st.get("campaigns", c.key))["state"] == "done"


def test_a_milestone_campaign_that_crashes_mid_fire_is_not_marked_done(st):
    """One recipient's failure (or a whole pass exploding) must not be mistaken for a completed
    reveal — the campaign stays active so the next tick can retry."""
    c = save(st, Campaign(tenant="t1", goal="community_milestone", state="active",
                         milestone_threshold=1))
    run(milestone.record_contribution(st, tenant="t1", campaign_id=c.id, threshold=1,
                                     subject_ref="a", now=at(8)))
    d = Dispatcher(boom=True)
    tick(st, d, at(9))
    assert run(st.get("campaigns", c.key))["state"] == "active"


def test_a_one_shot_milestone_that_never_crosses_expires_to_done(st):
    """The deadline passed and the threshold was never reached — a real, honest ending distinct
    from success, but still `done`: the challenge simply did not happen in time."""
    c = save(st, Campaign(tenant="t1", goal="community_milestone", state="active",
                         milestone_threshold=100, fire_at=at(1), expires_at=at(8)))
    d = Dispatcher(matched=0)
    tick(st, d, at(9))
    assert run(st.get("campaigns", c.key))["state"] == "done"


def test_a_one_shot_milestone_before_its_deadline_stays_active(st):
    c = save(st, Campaign(tenant="t1", goal="community_milestone", state="active",
                         milestone_threshold=100, fire_at=at(1), expires_at=at(20)))
    d = Dispatcher(matched=0)
    tick(st, d, at(9))
    assert run(st.get("campaigns", c.key))["state"] == "active"


def test_a_recurring_milestone_that_never_crosses_resets_for_a_fresh_round(st):
    """Never `done` at all — the deadline passing without a win simply starts the next round,
    back to back from the old deadline, same period length."""
    c = save(st, Campaign(tenant="t1", goal="community_milestone", state="active",
                         milestone_threshold=5, fire_at=at(1), expires_at=at(8),
                         milestone_recurring=True))
    run(milestone.record_contribution(st, tenant="t1", campaign_id=c.id, threshold=5,
                                     subject_ref="a", now=at(2)))
    d = Dispatcher(matched=0)
    tick(st, d, at(9))
    row = run(st.get("campaigns", c.key))
    assert row["state"] == "active"
    assert row["fire_at"] == at(8)
    # SAME PERIOD (7 hours here), STARTING FROM THE OLD DEADLINE — not from `now`, so a late tick
    # never lets drift creep into a repeating schedule.
    assert row["expires_at"] == at(8) + (at(8) - at(1))
    progress = run(milestone.read_progress(st, "t1", c.id))
    assert progress is None, "the previous round's own count/contributor must not linger"


def test_a_recurring_milestone_that_crosses_and_fully_drains_also_resets(st):
    """Success does not end a recurring challenge either — it just starts the next round."""
    c = save(st, Campaign(tenant="t1", goal="community_milestone", state="active",
                         milestone_threshold=1, fire_at=at(1), expires_at=at(8),
                         milestone_recurring=True))
    run(milestone.record_contribution(st, tenant="t1", campaign_id=c.id, threshold=1,
                                     subject_ref="a", now=at(2)))
    d = Dispatcher(sent=1, matched=0)   # everyone already reached this pass
    tick(st, d, at(9))
    row = run(st.get("campaigns", c.key))
    assert row["state"] == "active"
    assert row["fire_at"] == at(8)
    assert run(milestone.read_progress(st, "t1", c.id)) is None


def test_a_recurring_milestone_still_mid_round_is_untouched(st):
    c = save(st, Campaign(tenant="t1", goal="community_milestone", state="active",
                         milestone_threshold=100, fire_at=at(1), expires_at=at(20),
                         milestone_recurring=True))
    d = Dispatcher(matched=0)
    tick(st, d, at(9))
    row = run(st.get("campaigns", c.key))
    assert row["fire_at"] == at(1)
    assert row["expires_at"] == at(20)


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

    # `None`, NOT 0 (ج-3). This assertion used to read `[0]` and to explain that zero meant
    # «unknown» — which is precisely the conflation that let a fully-spent ceiling arrive at the
    # sender looking like an unread one, where it fell back to the pass batch and sent 200.
    assert d.shares == [None], "unknown is its own value; the sender keeps its own bound"
    assert len(d.fired) == 1


# ── concurrent campaigns ───────────────────────────────────────────────────────────────────────
class SlowDispatcher(Dispatcher):
    """Fires with an artificial await so overlapping campaigns actually interleave, the way a real
    dispatcher's store/sender calls would — proving the gather change isn't just sequential in
    disguise, and that the merge afterwards is still correct despite the interleaving."""

    async def fire(self, campaign, *, now, fired_by="system", daily_share=0):
        await asyncio.sleep(0)
        return await super().fire(campaign, now=now, fired_by=fired_by, daily_share=daily_share)


def test_independent_campaigns_run_concurrently_and_every_result_is_counted(st):
    """`gather` must not drop a campaign nor double-count one when several fire in the same pass —
    each gets its own TickResult, merged sequentially after every task finishes."""
    for i in range(5):
        save(st, Campaign(tenant="t1", goal="win_back", id=f"c{i}", state="active"))
    d = SlowDispatcher(sent=3)
    res = tick(st, d, at(9))
    assert len(d.fired) == 5
    assert {cid for cid, _ in d.fired} == {f"c{i}" for i in range(5)}
    assert res.fired == 5
    assert res.sent == 15


def test_one_campaigns_crash_does_not_lose_the_others_results(st):
    """A malformed campaign among several must not swallow what the healthy ones sent — the crash
    is recorded on its own local result and merged in like any other."""
    for i in range(3):
        save(st, Campaign(tenant="t1", goal="win_back", id=f"c{i}", state="active"))
    save(st, Campaign(tenant="t1", goal="win_back", id="boom", state="active"))

    class Flaky(Dispatcher):
        async def fire(self, campaign, *, now, fired_by="system", daily_share=0):
            if campaign.get("id") == "boom":
                raise RuntimeError("dispatch exploded")
            return await super().fire(campaign, now=now, fired_by=fired_by,
                                      daily_share=daily_share)

    d = Flaky(sent=2)
    res = tick(st, d, at(9))
    assert res.fired == 3
    assert res.sent == 6
    assert any("خطأ في حملة" in k for k in res.reasons)


def test_a_tenant_with_more_than_the_old_page_size_still_gets_every_campaign_ticked(st):
    """campaigns-001 (QA audit, 2026-09-12): `Tick.run` used to read at most 200 active campaigns,
    sorted oldest-first, and silently drop the returned cursor — so any campaign past the 200th
    oldest never ticked again, forever, with nothing logging the omission. 260 rows here proves the
    read is now drained rather than page-one-and-discard."""
    for i in range(260):
        save(st, Campaign(tenant="t1", goal="win_back", id=f"c{i}", state="active"))
    d = Dispatcher()
    res = tick(st, d, at(9))
    assert res.fired == 260
    assert len(d.fired) == 260
    assert {cid for cid, _ in d.fired} == {f"c{i}" for i in range(260)}
