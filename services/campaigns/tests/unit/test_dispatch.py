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
