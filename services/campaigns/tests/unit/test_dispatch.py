"""Firing a campaign — and the rule that this service never sends anything itself."""
from __future__ import annotations

import asyncio
import inspect

import pytest

from app.adapters.datastore.memory import MemoryDataStore
from app.core.audience import Audience, Candidate
from app.core.dispatch import Dispatcher

NOW = 1_800_000_000


def run(c):
    return asyncio.run(c)


class Sender:
    """Stands in for reminders' gate — which is the only thing that decides."""

    def __init__(self, *, refuse=None, fail=None, reason="بلغ الحد اليومي"):
        self.calls = []
        self.refuse = set(refuse or [])
        self.fail = set(fail or [])
        self.reason = reason

    async def send(self, **kw):
        if kw["subject_ref"] in self.fail:
            raise RuntimeError("notification-service unavailable")
        self.calls.append(kw)
        if kw["subject_ref"] in self.refuse:
            return {"sent": False, "reason": self.reason}
        return {"sent": True}


def resolver(*subjects, excluded=0):
    async def _r(campaign, *, already_reached, now):
        return Audience(
            candidates=[Candidate(subject_ref=s) for s in subjects
                        if s not in already_reached],
            excluded=excluded)
    return _r


CAMPAIGN = {"tenant": "t1", "id": "cmp_1", "template_type": "mkt_winback",
            "cls": "marketing", "owner_text": "خصم 20%"}


@pytest.fixture
def st():
    return MemoryDataStore()


def fire(st, sender, res, **kw):
    d = Dispatcher(store=st, sender=sender, audience_resolver=res, **kw)
    return run(d.fire(CAMPAIGN, now=NOW))


# ── this service never sends ───────────────────────────────────────────────────────────────────
def test_every_recipient_goes_through_the_sender_and_nothing_else():
    """A second send path would be a second set of rules, and the second one is always the one
    missing a check the day somebody adds one to the first."""
    src = inspect.getsource(Dispatcher)
    for forbidden in ("urllib", "httpx", "requests", "whatsapp", "notification"):
        assert forbidden not in src.lower(), f"dispatch must not reach {forbidden} itself"


def test_the_gates_refusal_reason_is_carried_verbatim(st):
    """Rewriting it here would mean two vocabularies for one refusal, and the owner would be told
    something subtly different from what happened."""
    s = Sender(refuse=["b"], reason="العميل أوقف الرسائل الدعائية")
    res = fire(st, s, resolver("a", "b"))
    assert res.run.sent == 1 and res.run.suppressed == 1
    assert "العميل أوقف الرسائل الدعائية" in res.run.reasons


# ── idempotency and resumability ───────────────────────────────────────────────────────────────
def test_the_idempotency_key_identifies_the_campaign_and_the_subject_not_the_attempt(st):
    s = Sender()
    fire(st, s, resolver("a"))
    key = s.calls[0]["idempotency_key"]
    # (CAMPAIGN, SUBJECT) — AND DELIBERATELY NOT THE RUN.
    #
    # The key used to carry `run.id`, and every pass and every retry opens a new run. So a send
    # that timed out but ARRIVED was re-sent under a fresh key the moment the campaign fired
    # again: the customer received the same offer twice and the shop paid twice against its cap.
    # A key that protects the customer from our uncertainty cannot be derived from the attempt
    # that is uncertain.
    assert key == "cmp:cmp_1:a"


def test_a_second_firing_never_reaches_the_same_person_again(st):
    """The dedup is the reached ledger, not a flag on the customer — a flag has to be cleared by
    something, and whatever clears it is the bug."""
    s = Sender()
    fire(st, s, resolver("a", "b"))
    fire(st, s, resolver("a", "b"))
    assert [c["subject_ref"] for c in s.calls] == ["a", "b"]


def test_a_refused_recipient_is_not_remembered_as_reached(st):
    """Otherwise a customer refused today for a temporary cap is excluded from this campaign for
    ever, silently."""
    s = Sender(refuse=["b"])
    fire(st, s, resolver("a", "b"))
    s2 = Sender()
    fire(st, s2, resolver("a", "b"))
    assert [c["subject_ref"] for c in s2.calls] == ["b"]


def test_a_pass_is_bounded_and_the_next_one_continues(st):
    """A campaign that re-sends its first four hundred recipients because the pod was evicted is
    worse than one that sends nothing."""
    s = Sender()
    res = fire(st, s, resolver("a", "b", "c", "d"), batch=2)
    assert not res.finished and res.run.sent == 2
    res2 = fire(st, s, resolver("a", "b", "c", "d"), batch=2)
    assert res2.finished and res2.run.sent == 2
    assert [c["subject_ref"] for c in s.calls] == ["a", "b", "c", "d"]


# ── failures ───────────────────────────────────────────────────────────────────────────────────
def test_one_recipients_failure_does_not_end_the_run(st):
    """One bad row stopping a campaign for every other customer shows up as 'the campaign does
    not work' rather than 'one recipient failed'."""
    s = Sender(fail=["b"])
    res = fire(st, s, resolver("a", "b", "c"))
    assert res.run.sent == 2 and res.run.failed == 1
    assert any("تعذّر الإرسال" in r for r in res.run.reasons)


def test_a_failed_recipient_is_retried_on_the_next_pass(st):
    s = Sender(fail=["b"])
    fire(st, s, resolver("a", "b"))
    s2 = Sender()
    fire(st, s2, resolver("a", "b"))
    assert [c["subject_ref"] for c in s2.calls] == ["b"]


# ── the run report ─────────────────────────────────────────────────────────────────────────────
def test_a_run_is_written_even_when_it_reaches_nobody(st):
    """A standing campaign that matched nobody for a week is information, and silence looks
    identical to a broken cron."""
    res = fire(st, Sender(), resolver())
    assert res.run.matched == 0
    rows, _ = run(st.find("campaign_runs", {"tenant": "t1"}, limit=10))
    assert len(rows) == 1


def test_the_gap_between_matched_and_sent_is_always_explained(st):
    """A report where the two numbers differ with nothing accounting for it turns every rule we
    wrote into a suspected bug."""
    s = Sender(refuse=["b"], reason="لم تمضِ 72 ساعة")
    res = fire(st, s, resolver("a", "b", "c"), )
    assert res.run.matched == 3
    assert res.run.sent + res.run.suppressed + res.run.failed == res.run.matched


def test_recipients_the_gate_would_refuse_are_counted_before_the_send(st):
    """They never reach the sender at all — the audience already excluded them, and the run says
    so rather than leaving a hole between matched and sent."""
    res = fire(st, Sender(), resolver("a", excluded=4))
    assert res.run.suppressed == 4 and res.run.sent == 1


# ── the in-process reached cache ───────────────────────────────────────────────────────────────
def test_a_reused_dispatcher_does_not_redrain_the_reached_ledger(st):
    """The container builds one Dispatcher and keeps firing it every five minutes for the life of
    a standing/scheduled campaign — the second pass on the SAME instance must not pay for another
    full drain of a ledger it already has cached."""
    s = Sender()
    d = Dispatcher(store=st, sender=s, audience_resolver=resolver("a", "b"))
    run(d.fire(CAMPAIGN, now=NOW))

    drains = []
    real_get = st.find
    async def counting_find(collection, *a, **kw):
        if collection == "campaign_reached":
            drains.append(1)
        return await real_get(collection, *a, **kw)
    st.find = counting_find

    run(d.fire(CAMPAIGN, now=NOW))
    assert drains == [], "the second pass on the same instance must use the cache, not the store"


def test_the_cache_still_agrees_with_the_store_after_a_repeat_pass(st):
    """The cache is a performance shortcut, not a second source of truth — it must track what the
    same instance actually sent, exactly as a fresh drain from the store would."""
    s = Sender()
    d = Dispatcher(store=st, sender=s, audience_resolver=resolver("a", "b"))
    run(d.fire(CAMPAIGN, now=NOW))
    run(d.fire(CAMPAIGN, now=NOW))
    assert [c["subject_ref"] for c in s.calls] == ["a", "b"]

    fresh = Dispatcher(store=st, sender=Sender(), audience_resolver=resolver("a", "b"))
    run(fresh.fire(CAMPAIGN, now=NOW))
    assert fresh._sender.calls == [], "a fresh instance, draining the real store, agrees nobody is left"


def test_identical_reasons_are_counted_not_listed(st):
    """An owner needs '3 deferred for the daily cap', not three identical lines."""
    s = Sender(refuse=["a", "b", "c"], reason="بلغ الحد اليومي")
    res = fire(st, s, resolver("a", "b", "c"))
    assert res.run.reasons["بلغ الحد اليومي"] == 3


# ── package_offer — re-asking whether the package is still offerable at fire time ────────────────

class _FixedOfferable:
    def __init__(self, offerable: bool = True) -> None:
        self._offerable = offerable
        self.calls: list[tuple[str, str, int]] = []

    async def offerable(self, tenant: str, package_id: str, at: int) -> bool:
        self.calls.append((tenant, package_id, at))
        return self._offerable


PACKAGE_CAMPAIGN = {**CAMPAIGN, "goal": "package_offer", "package_id": "pkg1"}


def test_a_package_offer_still_offerable_at_fire_time_sends_normally(st):
    check = _FixedOfferable(offerable=True)
    d = Dispatcher(store=st, sender=Sender(), audience_resolver=resolver("a"),
                  package_offerable=check)
    res = run(d.fire(PACKAGE_CAMPAIGN, now=NOW))
    assert res.run.sent == 1
    assert check.calls == [("t1", "pkg1", NOW)]


def test_a_package_no_longer_offerable_refuses_the_whole_run_sending_nothing(st):
    check = _FixedOfferable(offerable=False)
    sender = Sender()
    d = Dispatcher(store=st, sender=sender, audience_resolver=resolver("a"),
                  package_offerable=check)
    res = run(d.fire(PACKAGE_CAMPAIGN, now=NOW))
    assert res.run.sent == 0
    assert sender.calls == []
    assert "الباقة لم تعد متاحة" in res.run.reasons


def test_an_ordinary_campaign_with_no_package_id_never_asks_the_offerable_check(st):
    check = _FixedOfferable(offerable=False)     # would refuse if asked — must never be asked
    res = fire(st, Sender(), resolver("a"), package_offerable=check)
    assert res.run.sent == 1
    assert check.calls == []


def test_no_offerable_peer_wired_at_all_never_blocks_a_package_campaign(st):
    """Backward compatible — a Dispatcher built before this feature (package_offerable=None, the
    default) must not suddenly refuse every package_offer campaign."""
    d = Dispatcher(store=st, sender=Sender(), audience_resolver=resolver("a"))
    res = run(d.fire(PACKAGE_CAMPAIGN, now=NOW))
    assert res.run.sent == 1


# ── the owner's own window (2026-09-12) ──────────────────────────────────────────────────────────
# NOW (1_800_000_000) is 11:00 Riyadh on a Friday (weekday 4) — see test_campaign_core.py's own
# note pinning this same fact.
def test_a_campaign_outside_its_own_window_sends_nothing_and_is_not_finished(st):
    windowed = {**CAMPAIGN, "window_start_hour": 12, "window_end_hour": 20}
    sender = Sender()
    d = Dispatcher(store=st, sender=sender, audience_resolver=resolver("a"))
    res = run(d.fire(windowed, now=NOW))
    assert res.run.sent == 0
    assert sender.calls == []
    assert "خارج نافذة الحملة" in res.run.reasons
    # NOT FINISHED, DELIBERATELY — unlike a package that stopped being offerable. The window is
    # not a permanent refusal; the campaign must stay `active` and be retried on the next pass,
    # not marked `done` the moment one pass happens to land outside it.
    assert res.finished is False


def test_a_campaign_inside_its_own_window_sends_normally(st):
    windowed = {**CAMPAIGN, "window_start_hour": 8, "window_end_hour": 20}
    d = Dispatcher(store=st, sender=Sender(), audience_resolver=resolver("a"))
    res = run(d.fire(windowed, now=NOW))
    assert res.run.sent == 1
    assert res.finished is True


def test_a_campaign_outside_its_own_weekday_sends_nothing():
    st2 = MemoryDataStore()
    # NOW is a Friday — narrowing to weekdays that exclude it must refuse, same as an hour miss.
    windowed = {**CAMPAIGN, "window_weekdays": [0, 1, 2]}
    d = Dispatcher(store=st2, sender=Sender(), audience_resolver=resolver("a"))
    res = run(d.fire(windowed, now=NOW))
    assert res.run.sent == 0
    assert "خارج نافذة الحملة" in res.run.reasons


def test_a_campaign_with_no_window_fields_at_all_is_unaffected(st):
    """Backward compatible — a stored row from before this field existed carries no
    `window_start_hour`/`window_end_hour`/`window_weekdays` keys at all, not even the defaults."""
    res = fire(st, Sender(), resolver("a"))
    assert res.run.sent == 1


# ── the rail's own "N وصلهم" (app.core.goal_stats) ──────────────────────────────────────────────
def test_a_send_is_counted_under_the_campaigns_own_goal(st):
    from app.core.goal_stats import read_goal_stats

    with_goal = {**CAMPAIGN, "goal": "win_back"}
    d = Dispatcher(store=st, sender=Sender(), audience_resolver=resolver("a", "b"))
    res = run(d.fire(with_goal, now=NOW))
    assert res.run.sent == 2
    assert run(read_goal_stats(st, "t1")) == {"win_back": {"uses": 0, "reach": 2}}


def test_a_run_that_reaches_nobody_counts_nothing(st):
    from app.core.goal_stats import read_goal_stats

    with_goal = {**CAMPAIGN, "goal": "win_back"}
    d = Dispatcher(store=st, sender=Sender(), audience_resolver=resolver())
    res = run(d.fire(with_goal, now=NOW))
    assert res.run.sent == 0
    assert run(read_goal_stats(st, "t1")) == {}


def test_a_campaign_row_with_no_goal_at_all_is_never_counted_under_a_guessed_one(st):
    """A row this old predates the field entirely — its sends are simply not attributed to any
    goal, never guessed, rather than silently counted under an empty-string bucket."""
    from app.core.goal_stats import read_goal_stats

    d = Dispatcher(store=st, sender=Sender(), audience_resolver=resolver("a"))
    res = run(d.fire(CAMPAIGN, now=NOW))
    assert res.run.sent == 1
    assert run(read_goal_stats(st, "t1")) == {}


# ── the "points" reward's own credit (occasion pilot, 2026-09-13) ──────────────────────────────
class Loyalty:
    """Stands in for loyalty's own `/internal/loyalty/award` — never raises, same as the real
    HTTP client, and reports whatever the test asks it to."""

    def __init__(self, *, earned=1):
        self.calls = []
        self._earned = earned

    async def award(self, **kw):
        self.calls.append(kw)
        return {"earned": self._earned}


def test_points_reward_awards_once_per_recipient_on_the_sends_own_key(st):
    campaign = {**CAMPAIGN, "reward_type": "points", "reward_points": 50}
    loyalty = Loyalty()
    d = Dispatcher(store=st, sender=Sender(), audience_resolver=resolver("a", "b"),
                   loyalty=loyalty)
    res = run(d.fire(campaign, now=NOW))
    assert res.run.sent == 2
    assert len(loyalty.calls) == 2
    subjects = {c["subject_ref"] for c in loyalty.calls}
    assert subjects == {"a", "b"}
    for call in loyalty.calls:
        assert call["points"] == 50
        # THE SAME KEY THE SEND ITSELF IS IDEMPOTENT ON — a retried pass must not credit twice.
        assert call["idempotency_key"] == f"cmp:{campaign['id']}:{call['subject_ref']}"


def test_a_discount_or_gift_campaign_never_calls_award_at_all(st):
    loyalty = Loyalty()
    d = Dispatcher(store=st, sender=Sender(), audience_resolver=resolver("a"),
                   loyalty=loyalty)
    run(d.fire({**CAMPAIGN, "reward_type": "discount"}, now=NOW))
    run(d.fire({**CAMPAIGN, "id": "cmp_2", "reward_type": "gift"}, now=NOW))
    assert loyalty.calls == []


def test_a_lapsed_or_unreachable_award_never_cancels_the_send(st):
    """loyalty's own route sends nothing itself — this caller does — so a courtesy credit that
    could not be made (`earned: 0`) must not silently withhold a message the audience resolver
    already counted and the owner already paid for."""
    campaign = {**CAMPAIGN, "reward_type": "points", "reward_points": 50}
    sender = Sender()
    loyalty = Loyalty(earned=0)
    d = Dispatcher(store=st, sender=sender, audience_resolver=resolver("a"), loyalty=loyalty)
    res = run(d.fire(campaign, now=NOW))
    assert res.run.sent == 1
    assert len(sender.calls) == 1
    assert len(loyalty.calls) == 1


def test_points_reward_with_no_loyalty_peer_wired_still_sends(st):
    """OPTIONAL, like every other peer here — a deployment that never wired one must not refuse
    every points campaign for a capability nothing has asked it to provide yet."""
    campaign = {**CAMPAIGN, "reward_type": "points", "reward_points": 50}
    d = Dispatcher(store=st, sender=Sender(), audience_resolver=resolver("a"))
    res = run(d.fire(campaign, now=NOW))
    assert res.run.sent == 1


def test_the_sender_receives_the_rewards_own_fields(st):
    sender = Sender()
    campaign = {**CAMPAIGN, "reward_type": "gift", "reward_points": 0}
    d = Dispatcher(store=st, sender=sender, audience_resolver=resolver("a"))
    run(d.fire(campaign, now=NOW))
    assert sender.calls[0]["reward_type"] == "gift"
    assert sender.calls[0]["reward_points"] == 0


# ── the spread refusal never applies to a "جماعي" (milestone) reveal ─────────────────────────
def test_an_ordinary_goal_refuses_when_it_cannot_finish_before_its_own_expiry(st):
    """Baseline, unchanged — ten recipients against a per-pass share of one, with an offer that
    ends before day ten could possibly arrive, is refused rather than partially sent."""
    subjects = [f"c{i}" for i in range(10)]
    campaign = {**CAMPAIGN, "expires_at": NOW + 86400}   # one day left, ten days needed
    d = Dispatcher(store=st, sender=Sender(), audience_resolver=resolver(*subjects), batch=1)
    res = run(d.fire(campaign, now=NOW))
    assert res.run.sent == 0
    assert res.run.reasons


def test_a_milestone_reveal_is_never_refused_by_the_same_spread_check(st):
    """The exact same shape (a large cohort, a tight per-pass cap, an `expires_at` already at or
    past `now`) — but `trigger="milestone"` means `expires_at` is the deadline to CROSS the
    threshold, already happened by the time this fires, not a deadline to finish notifying the
    cohort. Refusing here would tell a shop that just won its own challenge that the win could
    not be announced."""
    subjects = [f"c{i}" for i in range(10)]
    campaign = {**CAMPAIGN, "trigger": "milestone", "expires_at": NOW - 1}
    d = Dispatcher(store=st, sender=Sender(), audience_resolver=resolver(*subjects), batch=1)
    res = run(d.fire(campaign, now=NOW))
    assert res.run.sent == 1   # bounded by batch=1, same as any other goal — just not REFUSED
    assert not res.run.reasons
