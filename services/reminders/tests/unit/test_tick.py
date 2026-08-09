"""The tick — where the gate, rendering, the sender and the ledger meet."""
from __future__ import annotations

import asyncio
from datetime import datetime

import pytest

from app.adapters.datastore.memory import MemoryDataStore
from app.core import engagement as E
from app.core import gate as G
from app.core.models import Preferences, Schedule, as_row
from app.core.stores import PrefsStore, ScheduleStore, SendLogStore
from app.core.tick import Tick

ECFG = E.EngagementConfig()


def run(c):
    return asyncio.run(c)


def at(hour, day=15):
    return int(datetime(2026, 6, day, hour, tzinfo=G.RIYADH).timestamp())


class FakeSender:
    def __init__(self, fail=False):
        self.calls = []
        self.fail = fail

    async def send(self, **kw):
        if self.fail:
            raise RuntimeError("notification-service unavailable")
        self.calls.append(kw)


LIB = [{"name": "svc_service_reminder_brief", "type": "svc_service_reminder", "tone": "brief",
        "class": "service", "variables": [1, 2, 3],
        "fills": ["system", "system", "catalogue"], "active": True},
       {"name": "mkt_offer_brief", "type": "mkt_offer", "tone": "brief", "class": "marketing",
        "variables": [1, 2, 3], "fills": ["system", "system", "catalogue"], "active": True}]

NAMES = {"oil": "غيار الزيت", "tyres": "الإطارات", "filters": "الفلاتر"}


@pytest.fixture
def st():
    return MemoryDataStore()


def tick(st, sender, **kw):
    return Tick(store=st, sender=sender, limits=G.Limits(), eng_cfg=ECFG, **kw)


def sched(st, **over):
    d = dict(tenant="t1", subject_ref="sub_a", service_id="oil", kind="reminder",
             due_at=at(9), cls="service", template_type="svc_service_reminder")
    d.update(over)
    s = Schedule(**d)
    run(ScheduleStore(st).upsert(s.tenant, s.key, as_row(s)))
    return s


def go(st, sender, *, now=None, **kw):
    return run(tick(st, sender, **kw).run(
        "t1", now=now or at(10), library=LIB, service_names=NAMES,
        establishment="ورشة النخبة", customer_names={"sub_a": "أحمد"}))


def test_a_due_reminder_is_sent_once(st):
    sched(st)
    s = FakeSender()
    res = go(st, s)
    assert res.sent == 1 and len(s.calls) == 1
    assert s.calls[0]["variables"] == ["أحمد", "ورشة النخبة", "غيار الزيت"]


def test_a_second_tick_does_not_send_again(st):
    """The schedule is closed, so the same reminder cannot go twice — the failure a customer
    notices immediately."""
    sched(st)
    s = FakeSender()
    go(st, s)
    res = go(st, s)
    assert res.sent == 0 and len(s.calls) == 1


def test_a_merged_reminder_names_every_service_in_one_message(st):
    sched(st, also_services=["tyres", "filters"])
    s = FakeSender()
    go(st, s)
    assert s.calls[0]["variables"][2] == "غيار الزيت، الإطارات والفلاتر"


def test_a_future_schedule_is_not_touched(st):
    sched(st, due_at=at(10, day=20))
    s = FakeSender()
    assert go(st, s).scanned == 0


def test_a_stopped_class_is_suppressed_with_its_reason_in_the_ledger(st):
    """The answer to the only question support ever gets about this service."""
    sched(st)
    run(PrefsStore(st).put("t1", "sub_a", as_row(Preferences(
        tenant="t1", subject_ref="sub_a", stopped={"service": True}))))
    s = FakeSender()
    res = go(st, s)
    assert res.suppressed == 1 and not s.calls
    row = run(SendLogStore(st).since("t1", "sub_a", since=0))[0]
    assert row["outcome"] == "suppressed" and "أوقف" in row["reason"]


def test_a_message_outside_the_window_is_deferred_not_closed(st):
    """'Wait' and 'never' are different answers, and an owner reading the log must be able to
    tell them apart."""
    sched(st, due_at=at(23))
    s = FakeSender()
    res = go(st, s, now=at(23))
    assert res.deferred == 1 and not s.calls
    row = run(ScheduleStore(st).get("t1|sub_a|oil|reminder"))
    assert row["state"] == "pending"
    assert datetime.fromtimestamp(row["due_at"], G.RIYADH).hour == 7


def test_a_deferred_message_goes_out_the_next_morning(st):
    sched(st, due_at=at(23))
    s = FakeSender()
    go(st, s, now=at(23))
    res = go(st, s, now=at(8, day=16))
    assert res.sent == 1


def test_higher_priority_wins_the_daily_slot(st):
    """Two messages competing must resolve the same way every time, and the loser must be the
    lower-priority one — not whichever the datastore returned first."""
    sched(st, service_id="oil", cls="marketing", template_type="mkt_offer", due_at=at(9))
    sched(st, service_id="tyres", cls="service", template_type="svc_service_reminder",
          due_at=at(9))
    s = FakeSender()
    res = go(st, s)
    assert res.sent == 1
    assert s.calls[0]["template_name"] == "svc_service_reminder_brief"
    assert res.suppressed + res.deferred == 1


def test_one_bad_row_does_not_stop_the_batch(st):
    """One malformed schedule must not stop every reminder for that establishment indefinitely."""
    sched(st, service_id="oil", template_type="does_not_exist")
    sched(st, service_id="tyres")
    s = FakeSender()
    res = go(st, s)
    assert res.sent == 1 and (res.failed + res.suppressed) == 1


def test_a_peer_failure_retries_rather_than_losing_the_reminder(st):
    """Most failures are a peer being briefly unavailable, and a schedule closed as failed is a
    reminder that silently never happens."""
    sched(st)
    res = go(st, FakeSender(fail=True))
    assert res.failed == 1
    row = run(ScheduleStore(st).get("t1|sub_a|oil|reminder"))
    assert row["state"] == "pending" and row["due_at"] > at(10)
    good = FakeSender()
    assert go(st, good, now=at(12)).sent == 1


def test_the_idempotency_key_survives_a_retry(st):
    """A timeout is not evidence that nothing was sent, and the customer must not pay for our
    uncertainty."""
    sched(st)
    go(st, FakeSender(fail=True))
    row = run(ScheduleStore(st).get("t1|sub_a|oil|reminder"))
    first = row.get("idempotency_key")
    s = FakeSender()
    go(st, s, now=at(12))
    assert first and s.calls[0]["idempotency_key"] == first


def test_suppression_reasons_are_counted_for_the_operator(st):
    """'312 suppressed' is an alarm; '312 suppressed, all outside the window' is a working
    system doing its job."""
    for sid in ("oil", "tyres"):
        sched(st, service_id=sid)
    run(PrefsStore(st).put("t1", "sub_a", as_row(Preferences(
        tenant="t1", subject_ref="sub_a", stopped={"service": True}))))
    res = go(st, FakeSender())
    assert sum(res.reasons.values()) == 2 and len(res.reasons) == 1


def test_the_batch_is_bounded(st):
    """An unbounded sweep is how a slow query becomes a day of reminders that never went out."""
    for i in range(10):
        sched(st, service_id=f"svc{i}")
    res = go(st, FakeSender(), batch=3)
    assert res.scanned == 3


def test_a_tick_for_one_tenant_never_touches_another(st):
    sched(st)
    other = Schedule(tenant="t2", subject_ref="sub_a", service_id="oil", kind="reminder",
                     due_at=at(9), template_type="svc_service_reminder")
    run(ScheduleStore(st).upsert("t2", other.key, as_row(other)))
    s = FakeSender()
    go(st, s)
    assert len(s.calls) == 1 and s.calls[0]["tenant"] == "t1"
    assert run(ScheduleStore(st).get("t2|sub_a|oil|reminder"))["state"] == "pending"


# ── the seam that only appeared when the two sides were called in sequence ─────────────────────
from app.adapters.message_sender import NullSender, Unsendable


class ErasedSender:
    async def send(self, **kw):
        raise Unsendable("no recipient for sub_a — erased or unknown")


def test_an_erased_customer_is_closed_not_retried_forever(st):
    """Retrying would ask operations about a forgotten customer on every tick, forever — useless,
    and the opposite of what they asked for."""
    sched(st)
    res = go(st, ErasedSender())
    assert res.suppressed == 1 and res.failed == 0
    assert run(ScheduleStore(st).get("t1|sub_a|oil|reminder"))["state"] == "suppressed"


def test_the_null_sender_records_what_it_would_have_sent(st):
    sched(st)
    s = NullSender()
    go(st, s)
    assert s.sent[0]["template_name"] == "svc_service_reminder_brief"
