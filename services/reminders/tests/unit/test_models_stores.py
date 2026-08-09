"""The model and the store — the two decisions worth a test before any logic exists."""
from __future__ import annotations

import asyncio

import pytest

from app.adapters.datastore.memory import MemoryDataStore
from app.core import models as M
from app.core import stores as S


def run(c):
    return asyncio.run(c)


@pytest.fixture
def st():
    return MemoryDataStore()


def _sched(**over):
    d = {"tenant": "t1", "subject_ref": "sub_a", "service_id": "oil", "kind": "reminder",
         "due_at": 1000}
    d.update(over)
    return M.Schedule(**d)


def test_a_second_visit_moves_the_reminder_instead_of_adding_one(st):
    """The natural key is the whole point: two rows here become one delivered message and one
    unexplained suppression once the daily cap runs."""
    store = S.ScheduleStore(st)
    a = _sched(due_at=1000)
    run(store.upsert("t1", a.key, M.as_row(a)))
    b = _sched(due_at=9000)
    run(store.upsert("t1", b.key, M.as_row(b)))
    rows = run(store.pending_for_subject("t1", "sub_a"))
    assert len(rows) == 1 and rows[0]["due_at"] == 9000


def test_a_different_kind_is_a_different_row(st):
    """A reminder and a follow-up coexist — they are different messages about the same service."""
    store = S.ScheduleStore(st)
    for k in ("reminder", "follow_up"):
        s = _sched(kind=k)
        run(store.upsert("t1", s.key, M.as_row(s)))
    assert len(run(store.pending_for_subject("t1", "sub_a"))) == 2


def test_a_visit_cancels_the_pending_follow_up(st):
    """Asking how last month's service went while the customer stands at the counter (spec 5.6)."""
    store = S.ScheduleStore(st)
    s = _sched(kind="follow_up")
    run(store.upsert("t1", s.key, M.as_row(s)))
    n = run(store.cancel_kind("t1", "sub_a", "oil", "follow_up", reason="returned", now=2000))
    assert n == 1
    assert run(store.pending_for_subject("t1", "sub_a")) == []
    row = run(store.get(s.key))
    assert row["state"] == "cancelled" and row["reason"] == "returned"


def test_one_tenant_never_sees_another(st):
    """Isolation is enforced by the store, because a handler that must remember can forget."""
    store = S.ScheduleStore(st)
    for t in ("t1", "t2"):
        s = _sched(tenant=t)
        run(store.upsert(t, s.key, M.as_row(s)))
    assert len(run(store.pending_for_subject("t1", "sub_a"))) == 1
    assert run(store.get("t1|sub_a|oil|reminder"))["tenant"] == "t1"


def test_only_due_rows_come_back(st):
    store = S.ScheduleStore(st)
    for sid, due in (("oil", 500), ("tyres", 5000)):
        s = _sched(service_id=sid, due_at=due)
        run(store.upsert("t1", s.key, M.as_row(s)))
    due = run(store.due("t1", now=1000))
    assert [r["service_id"] for r in due] == ["oil"]


def test_the_send_ledger_answers_the_cap_question(st):
    """A cap with no ledger is a wish: four a month is unenforceable unless something durable
    remembers the previous three across a restart and two replicas."""
    log = S.SendLogStore(st)
    for at in (100, 200, 300):
        run(log.append("t1", M.as_row(M.SendLog(tenant="t1", subject_ref="sub_a",
                                                cls="marketing", at=at))))
    run(log.append("t1", M.as_row(M.SendLog(tenant="t1", subject_ref="sub_a",
                                            cls="service", at=350))))
    assert len(run(log.since("t1", "sub_a", since=150, cls="marketing"))) == 2
    assert len(run(log.since("t1", "sub_a", since=0))) == 4


def test_a_suppression_is_a_row_with_its_reason(st):
    """The answer to the only question support ever gets about this service."""
    log = S.SendLogStore(st)
    run(log.append("t1", M.as_row(M.SendLog(tenant="t1", subject_ref="sub_a", cls="marketing",
                                            at=100, outcome="suppressed",
                                            reason="monthly marketing cap reached (4)"))))
    row = run(log.since("t1", "sub_a", since=0))[0]
    assert row["outcome"] == "suppressed" and "cap" in row["reason"]


def test_silence_is_consent_and_an_explicit_stop_is_absolute():
    """Deny-by-default is right for permissions and wrong here — a customer who has never spoken
    has not objected. But a stop outranks every class, including personal."""
    p = M.Preferences(tenant="t1", subject_ref="sub_a")
    assert all(p.allows(c) for c in M.CLASSES)
    p.stopped["marketing"] = True
    p.stopped["personal"] = True
    assert not p.allows("marketing") and not p.allows("personal")
    assert p.allows("service")


def test_no_identifier_ever_reaches_this_service():
    """A leak of this database must leak nobody: it holds a prediction of when each person next
    needs a service, and attached to a phone number that is a marketing list."""
    fields = set(M.Schedule.__dataclass_fields__) | set(M.SendLog.__dataclass_fields__) \
        | set(M.RuleState.__dataclass_fields__)
    for banned in ("phone", "name", "email", "plate"):
        assert banned not in fields


# ── erasure: no identifier to blank, and the erasure is still real ─────────────────────────────
from app.core.erasure import RemindersErasure


def test_erasure_removes_every_schedule_and_says_what_it_kept(st):
    """The failure mode here is not a leak — it is a message to someone who asked us to go away."""
    sched, rules = S.ScheduleStore(st), S.RuleStore(st)
    s = _sched()
    run(sched.upsert("t1", s.key, M.as_row(s)))
    r = M.RuleState(tenant="t1", subject_ref="sub_a", service_id="oil", interval_days=90)
    run(rules.upsert("t1", r.key, M.as_row(r)))
    run(S.PrefsStore(st).put("t1", "sub_a", M.as_row(M.Preferences(tenant="t1",
                                                                  subject_ref="sub_a"))))
    ack = run(RemindersErasure(store=st).erase("t1", "sub_a"))
    assert sorted(ack["erased"]) == ["prefs:1", "rules:1", "schedules:1"]
    assert ack["retained"][0]["basis"] == "communications_record"
    assert run(sched.pending_for_subject("t1", "sub_a")) == []


def test_erasing_twice_is_not_an_error(st):
    """A DSAR retries, and a 500 on the second call is investigated as a leak that is not one."""
    ack = run(RemindersErasure(store=st).erase("t1", "sub_a"))
    assert ack["already_absent"] is True and ack["erased"] == []


def test_erasure_never_crosses_a_tenant(st):
    sched = S.ScheduleStore(st)
    for t in ("t1", "t2"):
        s = _sched(tenant=t)
        run(sched.upsert(t, s.key, M.as_row(s)))
    run(RemindersErasure(store=st).erase("t1", "sub_a"))
    assert len(run(sched.pending_for_subject("t2", "sub_a"))) == 1


def test_the_send_log_survives_the_erasure(st):
    """Deleting it would leave us unable to defend the customer's own complaint — and it holds a
    pseudonym and a timestamp, never an identifier."""
    log = S.SendLogStore(st)
    run(log.append("t1", M.as_row(M.SendLog(tenant="t1", subject_ref="sub_a", cls="service",
                                            at=100))))
    run(RemindersErasure(store=st).erase("t1", "sub_a"))
    assert len(run(log.since("t1", "sub_a", since=0))) == 1
