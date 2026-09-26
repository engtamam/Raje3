"""The "جماعي" mechanic — a shared counter, fixed at creation, that reveals its whole earned
cohort together the moment it crosses its threshold. See `core/milestone.py`'s own docstring for
the full contract this file tests against.
"""
from __future__ import annotations

import asyncio

import pytest

from app.adapters.datastore.memory import MemoryDataStore
from app.core.audience import Candidate
from app.core.milestone import (
    MilestoneProgress,
    contribute_from_event,
    contribution_matches,
    read_progress,
    record_contribution,
    reset_progress,
    resolve_milestone,
    within_window,
)
from app.core.models import (
    MIN_MILESTONE_THRESHOLD,
    validate_milestone_recurrence,
    validate_milestone_threshold,
)


def run(c):
    return asyncio.run(c)


# ── validation ────────────────────────────────────────────────────────────────────────────────
def test_a_threshold_below_the_minimum_is_refused():
    assert validate_milestone_threshold(1) != ""
    assert validate_milestone_threshold(0) != ""
    assert validate_milestone_threshold(-5) != ""


def test_a_threshold_at_or_above_the_minimum_is_accepted():
    assert validate_milestone_threshold(MIN_MILESTONE_THRESHOLD) == ""
    assert validate_milestone_threshold(100) == ""


def test_a_non_recurring_campaign_needs_no_dates_at_all():
    assert validate_milestone_recurrence(recurring=False, fire_at=0, expires_at=0) == ""


def test_recurring_refuses_a_missing_start_or_end():
    assert validate_milestone_recurrence(recurring=True, fire_at=0, expires_at=1000) != ""
    assert validate_milestone_recurrence(recurring=True, fire_at=1000, expires_at=0) != ""
    assert validate_milestone_recurrence(recurring=True, fire_at=0, expires_at=0) != ""


def test_recurring_refuses_a_start_at_or_after_the_end():
    assert validate_milestone_recurrence(recurring=True, fire_at=1000, expires_at=1000) != ""
    assert validate_milestone_recurrence(recurring=True, fire_at=2000, expires_at=1000) != ""


def test_recurring_with_a_real_period_is_accepted():
    assert validate_milestone_recurrence(recurring=True, fire_at=1000, expires_at=2000) == ""


# ── within_window ─────────────────────────────────────────────────────────────────────────────
def test_no_dates_at_all_is_always_within_window():
    assert within_window({}, now=123456) is True


def test_before_the_start_date_is_outside_the_window():
    assert within_window({"fire_at": 2000, "expires_at": 3000}, now=1000) is False


def test_after_the_end_date_is_outside_the_window():
    assert within_window({"fire_at": 1000, "expires_at": 2000}, now=2001) is False


def test_exactly_at_the_boundaries_is_inside_the_window():
    assert within_window({"fire_at": 1000, "expires_at": 2000}, now=1000) is True
    assert within_window({"fire_at": 1000, "expires_at": 2000}, now=2000) is True


def test_a_zero_fire_at_means_started_at_creation():
    assert within_window({"fire_at": 0, "expires_at": 2000}, now=1) is True


# ── read_progress ─────────────────────────────────────────────────────────────────────────────
def test_a_campaign_never_contributed_to_reads_back_none():
    st = MemoryDataStore()
    assert run(read_progress(st, "t1", "cmp_1")) is None


def test_an_empty_tenant_or_campaign_id_reads_back_none():
    st = MemoryDataStore()
    assert run(read_progress(st, "", "cmp_1")) is None
    assert run(read_progress(st, "t1", "")) is None


# ── record_contribution: the ordinary path ───────────────────────────────────────────────────
def test_one_contribution_is_counted():
    st = MemoryDataStore()
    p = run(record_contribution(st, tenant="t1", campaign_id="cmp_1", threshold=3,
                               subject_ref="cust_1", now=1000))
    assert p.count == 1
    assert p.contributor_refs == ["cust_1"]
    assert p.fired is False


def test_contributions_accumulate_across_calls():
    st = MemoryDataStore()
    run(record_contribution(st, tenant="t1", campaign_id="cmp_1", threshold=5,
                           subject_ref="a", now=1))
    run(record_contribution(st, tenant="t1", campaign_id="cmp_1", threshold=5,
                           subject_ref="b", now=2))
    p = run(record_contribution(st, tenant="t1", campaign_id="cmp_1", threshold=5,
                               subject_ref="c", now=3))
    assert p.count == 3
    assert p.contributor_refs == ["a", "b", "c"]
    assert p.fired is False


def test_the_same_customer_contributing_twice_is_counted_twice():
    """Events, not unique customers — a car that comes back twice is two washes, not one, the
    same "100 سيارة" example the owner's own idea was built around."""
    st = MemoryDataStore()
    run(record_contribution(st, tenant="t1", campaign_id="cmp_1", threshold=5,
                           subject_ref="a", now=1))
    p = run(record_contribution(st, tenant="t1", campaign_id="cmp_1", threshold=5,
                               subject_ref="a", now=2))
    assert p.count == 2
    assert p.contributor_refs == ["a", "a"]


def test_crossing_the_threshold_fires_and_stamps_fired_at():
    st = MemoryDataStore()
    run(record_contribution(st, tenant="t1", campaign_id="cmp_1", threshold=2,
                           subject_ref="a", now=10))
    p = run(record_contribution(st, tenant="t1", campaign_id="cmp_1", threshold=2,
                               subject_ref="b", now=20))
    assert p.count == 2
    assert p.fired is True
    assert p.fired_at == 20


def test_a_batch_that_overshoots_the_threshold_still_fires_with_everyone_included():
    """No "exact 100th only" special-casing — the cohort is whoever contributed up to and
    including the write that crossed it, even if that write's own count ends up above the
    threshold. Contributions here are one-at-a-time (this file's own `record_contribution` is
    called once per event), so "overshoot" means the SAME contributor list simply keeps growing
    once fired — covered by the freeze test below, not a separate multi-increment batch shape."""
    st = MemoryDataStore()
    run(record_contribution(st, tenant="t1", campaign_id="cmp_1", threshold=1,
                           subject_ref="a", now=1))
    p = run(read_progress(st, "t1", "cmp_1"))
    assert p.fired is True
    assert p.count == 1


def test_the_counter_freezes_once_fired():
    st = MemoryDataStore()
    run(record_contribution(st, tenant="t1", campaign_id="cmp_1", threshold=1,
                           subject_ref="a", now=1))
    p = run(record_contribution(st, tenant="t1", campaign_id="cmp_1", threshold=1,
                               subject_ref="b", now=2))
    # "b" arrived AFTER the reveal — never counted, never added to the cohort.
    assert p.count == 1
    assert p.contributor_refs == ["a"]
    assert p.fired is True


def test_contributions_are_scoped_per_campaign_and_per_tenant():
    st = MemoryDataStore()
    run(record_contribution(st, tenant="t1", campaign_id="cmp_1", threshold=5,
                           subject_ref="a", now=1))
    run(record_contribution(st, tenant="t1", campaign_id="cmp_2", threshold=5,
                           subject_ref="b", now=1))
    run(record_contribution(st, tenant="t2", campaign_id="cmp_1", threshold=5,
                           subject_ref="c", now=1))
    assert run(read_progress(st, "t1", "cmp_1")).count == 1
    assert run(read_progress(st, "t1", "cmp_2")).count == 1
    assert run(read_progress(st, "t2", "cmp_1")).count == 1
    assert run(read_progress(st, "t1", "cmp_1")).contributor_refs == ["a"]


# ── record_contribution: edge cases ──────────────────────────────────────────────────────────
def test_an_empty_subject_ref_is_a_no_op():
    st = MemoryDataStore()
    p = run(record_contribution(st, tenant="t1", campaign_id="cmp_1", threshold=5,
                               subject_ref="", now=1))
    assert p.count == 0
    assert run(read_progress(st, "t1", "cmp_1")) is None


def test_an_empty_campaign_id_is_a_no_op():
    st = MemoryDataStore()
    p = run(record_contribution(st, tenant="t1", campaign_id="", threshold=5,
                               subject_ref="a", now=1))
    assert p.count == 0


def test_an_empty_tenant_is_a_no_op():
    st = MemoryDataStore()
    p = run(record_contribution(st, tenant="", campaign_id="cmp_1", threshold=5,
                               subject_ref="a", now=1))
    assert p.count == 0


def test_a_zero_threshold_never_fires_no_matter_how_many_contributions():
    """`count >= threshold > 0` — a threshold of 0 could otherwise be satisfied immediately by the
    very first contribution (`1 >= 0` is true), firing a "milestone" nobody set a real target for.
    This can only happen if a campaign somehow stores `milestone_threshold=0` (validated against at
    creation, `validate_milestone_threshold`) — defended here anyway, the same "trust nothing about
    a stored value's own history" discipline `dispatch.py`'s own re-checks already follow."""
    st = MemoryDataStore()
    for i in range(10):
        p = run(record_contribution(st, tenant="t1", campaign_id="cmp_1", threshold=0,
                                   subject_ref=f"c{i}", now=i))
    assert p.count == 10
    assert p.fired is False


def test_a_default_now_falls_back_to_the_real_clock():
    st = MemoryDataStore()
    p = run(record_contribution(st, tenant="t1", campaign_id="cmp_1", threshold=100,
                               subject_ref="a"))
    assert p.count == 1


# ── concurrency: the mutex must actually serialise ───────────────────────────────────────────
class _SlowStore:
    """Same race-widening wrapper `test_goal_stats.py` already uses — stalls between `get` and
    `put` so a non-atomic read-modify-write is caught deterministically instead of needing luck."""

    def __init__(self, inner):
        self._inner = inner

    async def get(self, collection, key):
        row = await self._inner.get(collection, key)
        await asyncio.sleep(0.01)
        return row

    async def put(self, collection, key, value):
        return await self._inner.put(collection, key, value)

    async def delete(self, collection, key):
        return await self._inner.delete(collection, key)

    async def claim(self, collection, key, value, *, ttl_seconds, now):
        return await self._inner.claim(collection, key, value, ttl_seconds=ttl_seconds, now=now)


def test_two_genuinely_concurrent_contributions_never_lose_one():
    st = _SlowStore(MemoryDataStore())

    async def race():
        await asyncio.gather(
            record_contribution(st, tenant="t1", campaign_id="cmp_1", threshold=10,
                               subject_ref="a", now=1),
            record_contribution(st, tenant="t1", campaign_id="cmp_1", threshold=10,
                               subject_ref="b", now=2),
        )

    run(race())
    p = run(read_progress(st, "t1", "cmp_1"))
    assert p.count == 2
    assert sorted(p.contributor_refs) == ["a", "b"]


def test_many_concurrent_contributions_crossing_the_threshold_fire_exactly_once():
    """The real worry a shared counter exists to answer: a hundred visits arriving at once must
    not double-count, under-count, or fire twice — the mutex serialises every increment, so the
    100th (whichever one it happens to be) is the one and only write that flips `fired`."""
    st = _SlowStore(MemoryDataStore())

    async def race():
        await asyncio.gather(*(
            record_contribution(st, tenant="t1", campaign_id="cmp_1", threshold=50,
                               subject_ref=f"cust_{i}", now=i)
            for i in range(50)
        ))

    run(race())
    p = run(read_progress(st, "t1", "cmp_1"))
    assert p.count == 50
    assert len(p.contributor_refs) == 50
    assert len(set(p.contributor_refs)) == 50
    assert p.fired is True


class _NeverClaims:
    """Every `claim` call fails — simulates a mutex nobody can ever acquire, the same scenario
    `test_locks.py`/`goal_stats.py`'s own tests exercise for their own mutexes."""

    async def get(self, collection, key):
        return None

    async def put(self, collection, key, value):
        return None

    async def delete(self, collection, key):
        return True

    async def claim(self, collection, key, value, *, ttl_seconds, now):
        return False


def test_a_lock_that_can_never_be_claimed_raises_rather_than_silently_losing_the_contribution():
    """UNLIKE `goal_stats.py`'s OWN CHOICE — this counter is load-bearing (it decides whether a
    cohort is ever promised anything), not cosmetic, so a caller must know a contribution was
    lost rather than have it silently swallowed."""
    st = _NeverClaims()
    with pytest.raises(RuntimeError):
        run(record_contribution(st, tenant="t1", campaign_id="cmp_1", threshold=5,
                               subject_ref="a", now=1))


# ── contribution_matches: who the campaign's creator scoped the goal to ──────────────────────
def test_no_scope_at_all_means_every_visit_counts():
    assert contribution_matches({}) is True
    assert contribution_matches({}, service_id="svc_1") is True
    assert contribution_matches({}, package_id="pkg_1") is True


def test_a_single_service_scope_only_matches_that_service():
    c = {"service_id": "svc_1"}
    assert contribution_matches(c, service_id="svc_1") is True
    assert contribution_matches(c, service_id="svc_2") is False
    assert contribution_matches(c) is False, "an event naming no service does not match a scoped goal"


def test_a_multi_service_scope_matches_any_one_of_them():
    c = {"scope_service_ids": ["svc_1", "svc_2", "svc_3"]}
    assert contribution_matches(c, service_id="svc_2") is True
    assert contribution_matches(c, service_id="svc_9") is False


def test_service_id_and_scope_service_ids_are_merged():
    """The same merge `audience.resolve` already does for the individual mechanic — a caller
    migrating one field at a time never loses the other's targeting."""
    c = {"service_id": "svc_1", "scope_service_ids": ["svc_2"]}
    assert contribution_matches(c, service_id="svc_1") is True
    assert contribution_matches(c, service_id="svc_2") is True
    assert contribution_matches(c, service_id="svc_3") is False


def test_a_package_scope_only_matches_that_package():
    c = {"package_id": "pkg_1"}
    assert contribution_matches(c, package_id="pkg_1") is True
    assert contribution_matches(c, package_id="pkg_2") is False
    assert contribution_matches(c) is False


def test_package_takes_priority_over_a_stray_service_scope():
    """A campaign is about one or the other, never both — the same rule
    `Campaign.package_id`'s own docstring states for the individual mechanic."""
    c = {"package_id": "pkg_1", "service_id": "svc_1"}
    assert contribution_matches(c, package_id="pkg_1") is True
    assert contribution_matches(c, service_id="svc_1") is False, \
        "package_id set means only the package counts, not the stray service_id"


def test_an_event_with_no_service_or_package_never_matches_a_scoped_goal():
    assert contribution_matches({"service_id": "svc_1"}) is False
    assert contribution_matches({"package_id": "pkg_1"}) is False


# ── contribute_from_event: the single per-event fan-out ──────────────────────────────────────
async def _save_campaign(st, **kw):
    row = {"id": "cmp_1", "tenant": "t1", "goal": "community_milestone", "state": "active",
          "milestone_threshold": 5, "service_id": "", "scope_service_ids": [], "package_id": "",
          "created": 1}
    row.update(kw)
    await st.put("campaigns", f"{row['tenant']}|{row['id']}", row)
    return row


def test_no_tenant_or_subject_is_a_safe_no_op():
    st = MemoryDataStore()
    assert run(contribute_from_event(st, tenant="", subject_ref="a")) == []
    assert run(contribute_from_event(st, tenant="t1", subject_ref="")) == []


def test_an_unscoped_active_campaign_receives_any_event():
    st = MemoryDataStore()
    run(_save_campaign(st))
    out = run(contribute_from_event(st, tenant="t1", subject_ref="cust_1"))
    assert len(out) == 1
    assert out[0].count == 1


def test_a_paused_campaign_is_never_counted():
    """`drain(..., {"state": "active", ...})` — the same "only active campaigns are ticked"
    filter `tick.py`'s own drain already applies, reused here for the same reason."""
    st = MemoryDataStore()
    run(_save_campaign(st, state="paused"))
    assert run(contribute_from_event(st, tenant="t1", subject_ref="cust_1")) == []


def test_a_non_milestone_goal_is_never_counted():
    """The drain itself is filtered to `goal="community_milestone"` — an ordinary win_back/
    reward_loyal campaign must never be mistaken for one with a shared counter."""
    st = MemoryDataStore()
    run(_save_campaign(st, goal="win_back"))
    assert run(contribute_from_event(st, tenant="t1", subject_ref="cust_1")) == []


def test_one_event_fans_out_to_every_matching_campaign():
    st = MemoryDataStore()
    run(_save_campaign(st, id="cmp_1"))
    run(_save_campaign(st, id="cmp_2", service_id="svc_wash"))
    run(_save_campaign(st, id="cmp_3", service_id="svc_oil"))
    out = run(contribute_from_event(st, tenant="t1", subject_ref="cust_1",
                                   service_ids=["svc_wash"]))
    ids = {p.campaign_id for p in out}
    assert ids == {"cmp_1", "cmp_2"}, "cmp_1 (unscoped) and cmp_2 (scoped to svc_wash) both count"


def test_an_event_matching_nothing_contributes_to_nobody():
    st = MemoryDataStore()
    run(_save_campaign(st, service_id="svc_wash"))
    out = run(contribute_from_event(st, tenant="t1", subject_ref="cust_1",
                                   service_ids=["svc_oil"]))
    assert out == []


def test_an_event_before_the_challenge_starts_is_not_counted():
    st = MemoryDataStore()
    run(_save_campaign(st, fire_at=5000, expires_at=6000))
    out = run(contribute_from_event(st, tenant="t1", subject_ref="cust_1", now=4000))
    assert out == []


def test_an_event_after_the_deadline_is_not_counted():
    st = MemoryDataStore()
    run(_save_campaign(st, fire_at=1000, expires_at=2000))
    out = run(contribute_from_event(st, tenant="t1", subject_ref="cust_1", now=2001))
    assert out == []


def test_an_event_inside_the_window_is_counted():
    st = MemoryDataStore()
    run(_save_campaign(st, fire_at=1000, expires_at=2000))
    out = run(contribute_from_event(st, tenant="t1", subject_ref="cust_1", now=1500))
    assert len(out) == 1


# ── reset_progress: recurrence ────────────────────────────────────────────────────────────────
def test_reset_progress_clears_a_finished_round_completely():
    st = MemoryDataStore()
    run(record_contribution(st, tenant="t1", campaign_id="cmp_1", threshold=2,
                           subject_ref="a", now=1))
    run(record_contribution(st, tenant="t1", campaign_id="cmp_1", threshold=2,
                           subject_ref="b", now=2))
    fired = run(read_progress(st, "t1", "cmp_1"))
    assert fired.fired is True

    run(reset_progress(st, "t1", "cmp_1"))
    assert run(read_progress(st, "t1", "cmp_1")) is None


def test_a_contribution_after_reset_starts_a_brand_new_round():
    st = MemoryDataStore()
    run(record_contribution(st, tenant="t1", campaign_id="cmp_1", threshold=1,
                           subject_ref="a", now=1))
    run(reset_progress(st, "t1", "cmp_1"))
    p = run(record_contribution(st, tenant="t1", campaign_id="cmp_1", threshold=1,
                               subject_ref="b", now=2))
    assert p.count == 1
    assert p.contributor_refs == ["b"], "the previous round's own contributor must not linger"
    assert p.fired is True


def test_one_locked_out_campaign_does_not_stop_the_others():
    """A lock-claim failure on ONE campaign (a genuinely never-claimable mutex) must not prevent
    the same real event from still being counted toward every other campaign it also matches."""
    st = MemoryDataStore()
    run(_save_campaign(st, id="cmp_1"))
    run(_save_campaign(st, id="cmp_2"))

    real_claim = st.claim

    async def _boom_for_cmp_1(collection, key, value, *, ttl_seconds, now):
        if key == "t1|cmp_1":
            return False
        return await real_claim(collection, key, value, ttl_seconds=ttl_seconds, now=now)

    st.claim = _boom_for_cmp_1
    # `record_contribution` retries 150 times at 10ms — patch the sleep away so this test does
    # not actually wait ~1.5s for cmp_1's lock to exhaust its own retry budget.
    import app.core.milestone as _m
    orig_attempts = _m._MUTEX_RETRY_ATTEMPTS
    _m._MUTEX_RETRY_ATTEMPTS = 2
    try:
        out = run(contribute_from_event(st, tenant="t1", subject_ref="cust_1"))
    finally:
        _m._MUTEX_RETRY_ATTEMPTS = orig_attempts
    assert [p.campaign_id for p in out] == ["cmp_2"]


# ── resolve_milestone: the resolver contract every mechanic shares ───────────────────────────
class _FakeAudience:
    """A minimal stand-in for the container's own `_AudienceFacade` — only `gate_check` matters
    to `resolve_milestone`. `denied` is the set of subjects the gate refuses, mirroring an
    opted-out or stopped-class customer."""

    def __init__(self, denied: set[str] | None = None):
        self.denied = denied or set()
        self.calls: list[tuple[str, str, str]] = []

    async def gate_check(self, tenant, subject, cls):
        self.calls.append((tenant, subject, cls))
        return subject not in self.denied


def test_before_the_threshold_is_crossed_the_resolver_returns_nobody():
    st = MemoryDataStore()
    run(record_contribution(st, tenant="t1", campaign_id="cmp_1", threshold=10,
                           subject_ref="a", now=1))
    audience = run(resolve_milestone(
        {"tenant": "t1", "id": "cmp_1", "cls": "marketing"},
        already_reached=set(), now=100, audience=_FakeAudience(), store=st))
    assert audience.count == 0


def test_a_campaign_never_contributed_to_at_all_returns_nobody():
    st = MemoryDataStore()
    audience = run(resolve_milestone(
        {"tenant": "t1", "id": "cmp_1", "cls": "marketing"},
        already_reached=set(), now=100, audience=_FakeAudience(), store=st))
    assert audience.count == 0


def test_once_fired_the_resolver_returns_the_whole_cohort():
    st = MemoryDataStore()
    run(record_contribution(st, tenant="t1", campaign_id="cmp_1", threshold=2,
                           subject_ref="a", now=1))
    run(record_contribution(st, tenant="t1", campaign_id="cmp_1", threshold=2,
                           subject_ref="b", now=2))
    audience = run(resolve_milestone(
        {"tenant": "t1", "id": "cmp_1", "cls": "marketing"},
        already_reached=set(), now=100, audience=_FakeAudience(), store=st))
    assert audience.count == 2
    assert {c.subject_ref for c in audience.candidates} == {"a", "b"}
    assert all(c.why for c in audience.candidates)


def test_already_reached_subjects_are_excluded_so_a_resumed_pass_never_double_sends():
    """The dispatcher's own resumability, unchanged — a pass that already sent to "a" must not
    see "a" again on the next tick, exactly like every other goal's `already_reached` set."""
    st = MemoryDataStore()
    run(record_contribution(st, tenant="t1", campaign_id="cmp_1", threshold=2,
                           subject_ref="a", now=1))
    run(record_contribution(st, tenant="t1", campaign_id="cmp_1", threshold=2,
                           subject_ref="b", now=2))
    audience = run(resolve_milestone(
        {"tenant": "t1", "id": "cmp_1", "cls": "marketing"},
        already_reached={"a"}, now=100, audience=_FakeAudience(), store=st))
    assert audience.count == 1
    assert audience.candidates[0].subject_ref == "b"


def test_the_resolver_is_fully_idempotent_across_repeated_calls():
    """A crash between resolving and sending must not change what the NEXT resolve returns —
    calling this twice with the same inputs gives the same cohort, every time."""
    st = MemoryDataStore()
    run(record_contribution(st, tenant="t1", campaign_id="cmp_1", threshold=3,
                           subject_ref="a", now=1))
    run(record_contribution(st, tenant="t1", campaign_id="cmp_1", threshold=3,
                           subject_ref="b", now=2))
    run(record_contribution(st, tenant="t1", campaign_id="cmp_1", threshold=3,
                           subject_ref="c", now=3))
    first = run(resolve_milestone({"tenant": "t1", "id": "cmp_1", "cls": "marketing"},
                                  already_reached=set(), now=100,
                                  audience=_FakeAudience(), store=st))
    second = run(resolve_milestone({"tenant": "t1", "id": "cmp_1", "cls": "marketing"},
                                   already_reached=set(), now=200,
                                   audience=_FakeAudience(), store=st))
    assert {c.subject_ref for c in first.candidates} == {c.subject_ref for c in second.candidates}


def test_a_gate_denied_subject_is_excluded_but_counted_never_hidden():
    """Matched but refused — the same "the preview says the honest number" discipline
    `core/audience.py::resolve` already documents for the individual mechanic. An opted-out
    contributor still helped cross the threshold; they simply do not receive the reveal."""
    st = MemoryDataStore()
    run(record_contribution(st, tenant="t1", campaign_id="cmp_1", threshold=2,
                           subject_ref="a", now=1))
    run(record_contribution(st, tenant="t1", campaign_id="cmp_1", threshold=2,
                           subject_ref="b", now=2))
    audience = run(resolve_milestone(
        {"tenant": "t1", "id": "cmp_1", "cls": "marketing"},
        already_reached=set(), now=100, audience=_FakeAudience(denied={"a"}), store=st))
    assert audience.count == 1
    assert audience.candidates[0].subject_ref == "b"
    assert audience.excluded == 1


def test_a_contributor_appearing_twice_before_the_reveal_is_only_messaged_once():
    """The counter counts EVENTS (asserted above); the reveal counts PEOPLE — a customer who
    contributed twice must receive exactly one message, never two, the same "count of PEOPLE is
    what an owner is deciding about" discipline `preview.py` already states for the individual
    mechanic."""
    st = MemoryDataStore()
    run(record_contribution(st, tenant="t1", campaign_id="cmp_1", threshold=2,
                           subject_ref="a", now=1))
    run(record_contribution(st, tenant="t1", campaign_id="cmp_1", threshold=2,
                           subject_ref="a", now=2))
    audience = run(resolve_milestone(
        {"tenant": "t1", "id": "cmp_1", "cls": "marketing"},
        already_reached=set(), now=100, audience=_FakeAudience(), store=st))
    assert audience.count == 1
    assert audience.candidates[0].subject_ref == "a"


def test_no_store_at_all_is_a_safe_no_op_not_a_crash():
    """A resolver call built without a real store (a stray manual construction, a future caller
    that forgot the kwarg) must degrade to "nobody", never raise — the same fail-safe posture
    every other optional peer in this service already takes."""
    audience = run(resolve_milestone(
        {"tenant": "t1", "id": "cmp_1", "cls": "marketing"},
        already_reached=set(), now=100, audience=_FakeAudience(), store=None))
    assert audience.count == 0


def test_gate_check_is_called_with_the_campaigns_own_class_not_a_hardcoded_one():
    st = MemoryDataStore()
    run(record_contribution(st, tenant="t1", campaign_id="cmp_1", threshold=1,
                           subject_ref="a", now=1))
    fake = _FakeAudience()
    run(resolve_milestone({"tenant": "t1", "id": "cmp_1", "cls": "marketing"},
                         already_reached=set(), now=100, audience=fake, store=st))
    assert fake.calls == [("t1", "a", "marketing")]
