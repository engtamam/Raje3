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


# ── the HTTP status is not the delivery status (spec §6.6.1) ───────────────────────────────────
def test_a_two_hundred_carrying_a_failed_record_is_not_a_send():
    """THE SILENT DEFECT THIS CLOSES. /internal/notify answers 200 and returns the delivery record,
    including status:"failed" — most often because Meta has not approved the template yet, which is
    unavoidable for a shop that connected this morning. Read only the HTTP code and the reminder is
    written to the ledger as sent, the schedule is closed, and the customer is never reminded."""
    import json as _json
    from unittest.mock import patch
    from app.adapters.message_sender import HttpSender, SendFailed

    class Resp:
        status = 200

        def read(self):
            return _json.dumps({"id": "d1", "status": "failed",
                                "error": "whatsapp template not approved: pending"}).encode()

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    s = HttpSender(notify_url="http://n", notify_path="/internal/notify",
                   operations_url="http://o", recipient_path="/r", token="t")
    with patch.object(s, "_recipient", return_value="+966500000000"), \
         patch("urllib.request.urlopen", return_value=Resp()):
        with pytest.raises(SendFailed) as exc:
            asyncio.run(s.send(tenant="t", subject_ref="ref_x", template_name="svc_x_brief",
                               variables=["a"], cls="service", idempotency_key="k1"))
    assert "not approved" in str(exc.value)


def test_a_queued_delivery_counts_as_sent_and_is_not_retried():
    """The peer has taken responsibility and will drain it. Treating it as a failure sends twice."""
    import json as _json
    from unittest.mock import patch
    from app.adapters.message_sender import HttpSender

    class Resp:
        status = 200

        def read(self):
            return _json.dumps({"id": "d2", "status": "queued"}).encode()

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    s = HttpSender(notify_url="http://n", notify_path="/internal/notify",
                   operations_url="http://o", recipient_path="/r", token="t")
    with patch.object(s, "_recipient", return_value="+966500000000"), \
         patch("urllib.request.urlopen", return_value=Resp()):
        asyncio.run(s.send(tenant="t", subject_ref="ref_x", template_name="svc_x_brief",
                           variables=["a"], cls="service", idempotency_key="k2"))


# ── the message quota, where it meets the tick ─────────────────────────────────────────────────
class FakeQuota:
    """Counts, and can refuse. Idempotent, because the point of the key is that a retry is free."""

    def __init__(self, limit: int = 100) -> None:
        self.limit = limit
        self.spent: dict[str, int] = {}
        self.releases: list[str] = []

    @property
    def used(self) -> int:
        return sum(self.spent.values())

    async def consume(self, *, tenant: str, idempotency_key: str, amount: int = 1) -> None:
        from app.core.quota import QuotaError

        if idempotency_key in self.spent:
            return
        # The one refusal that survives: no live subscription. `limit` here stands in for that,
        # since the real meter no longer has a ceiling of its own.
        if self.used + amount > self.limit:
            raise QuotaError("لا يوجد اشتراك فعّال — فعّل اشتراكك لاستئناف الإرسال.")
        self.spent[idempotency_key] = amount

    async def release(self, *, tenant: str, idempotency_key: str, amount: int = 1) -> None:
        self.releases.append(idempotency_key)
        self.spent.pop(idempotency_key, None)


def test_a_sent_reminder_spends_exactly_one_message(st):
    sched(st)
    q = FakeQuota()
    go(st, FakeSender(), quota=q)
    assert q.used == 1


def test_a_suppressed_reminder_costs_nothing(st):
    """CONSUME AT THE SEND, NOT AT THE SCHEDULE. A reminder the gate refuses — a stopped class, a
    withdrawn consent, quiet hours — must not have been paid for. Counting earlier would make the
    cap punish an owner for customers we never messaged."""
    sched(st)
    run(PrefsStore(st).put("t1", "sub_a", as_row(Preferences(
        tenant="t1", subject_ref="sub_a", stopped={"service": True}))))
    q = FakeQuota()
    res = go(st, FakeSender(), quota=q)
    assert res.suppressed == 1 and q.used == 0


def test_a_deferred_reminder_costs_nothing(st):
    """It has not been sent yet — it goes out tomorrow morning, and pays then."""
    sched(st, due_at=at(23))
    q = FakeQuota()
    go(st, FakeSender(), now=at(23), quota=q)
    assert q.used == 0


def test_a_failed_send_gives_the_unit_back(st):
    """The consume must come first to be atomic, so a send that then fails leaves a unit spent.
    The commonest failure in this product is a template still in Meta's review — for a shop that
    connected this morning, that is the entire library, and it would pay for every one."""
    sched(st)
    q = FakeQuota()
    res = go(st, FakeSender(fail=True), quota=q)
    assert res.failed == 1
    assert q.used == 0 and len(q.releases) == 1


def test_a_retry_after_a_failure_spends_one_unit_in_total(st):
    """The key is stored on the row before the first attempt, so the retry consumes the same unit.
    A fresh key per attempt burns quota per redelivery with no extra message to show for it."""
    sched(st)
    q = FakeQuota()
    sender = FakeSender(fail=True)
    go(st, sender, quota=q)
    sender.fail = False
    go(st, sender, now=at(11), quota=q)
    assert q.used == 1 and len(sender.calls) == 1


def test_a_tenant_billing_refuses_does_not_send(st):
    sched(st)
    q = FakeQuota(limit=0)
    res = go(st, FakeSender(), quota=q)
    assert res.sent == 0 and res.suppressed == 1


def test_a_billing_refusal_is_recorded_as_suppressed_not_failed(st):
    """It is a decision, not an outage — an establishment with no live subscription. Retrying it
    hourly for the rest of the month would bury the peer failures the reason counts exist to
    surface, and the ledger has to be able to tell an owner why a message did not go."""
    row_key = sched(st).key
    q = FakeQuota(limit=0)
    go(st, FakeSender(), quota=q)
    row = run(SendLogStore(st).since("t1", "sub_a", since=0))[0]
    assert row["outcome"] == "suppressed" and "اشتراك" in row["reason"]
    assert run(ScheduleStore(st).get(row_key))["state"] == "suppressed"


# ── the WhatsApp ceiling, and the three answers to it ──────────────────────────────────────────
class CeilingSender:
    """Refuses with a real Meta code, the way notification-service surfaces one."""

    def __init__(self, code: str = "131064"):
        self.code = code
        self.calls = []

    async def send(self, **kw):
        from app.adapters.message_sender import CeilingReached

        self.calls.append(kw)
        raise CeilingReached(self.code, f"{self.code}: messaging limit reached")


LIB_POLICY = [
    {"name": "svc_visit_confirmation_brief", "type": "svc_visit_confirmation", "tone": "brief",
     "class": "service", "variables": [1, 2, 3], "fills": ["system", "system", "catalogue"],
     "active": True, "deferral": "drop"},
    {"name": "svc_follow_up_brief", "type": "svc_follow_up", "tone": "brief", "class": "service",
     "variables": [1, 2, 3], "fills": ["system", "system", "catalogue"], "active": True,
     "deferral": "defer"},
]


def go_policy(st, sender, *, template_type, **kw):
    return run(tick(st, sender, **kw).run(
        "t1", now=at(10), library=LIB_POLICY, service_names=NAMES,
        establishment="ورشة النخبة", customer_names={"sub_a": "أحمد"}))


def test_a_visit_confirmation_is_dropped_when_the_ceiling_is_hit(st):
    """'We recorded your visit' arriving 18 hours later is not a late message, it is a STRANGE
    one. The shop is better served by silence than by tomorrow."""
    row = sched(st, template_type="svc_visit_confirmation")
    q = FakeQuota()
    res = go_policy(st, CeilingSender(), template_type="svc_visit_confirmation", quota=q)
    assert res.suppressed == 1 and res.ceiling == 1
    assert run(ScheduleStore(st).get(row.key))["state"] == "suppressed"


def test_a_follow_up_is_deferred_rather_than_dropped(st):
    """Nothing spoils overnight and the customer notices no difference."""
    row = sched(st, template_type="svc_follow_up")
    res = go_policy(st, CeilingSender(), template_type="svc_follow_up", quota=FakeQuota())
    assert res.deferred == 1 and res.ceiling == 1
    fresh = run(ScheduleStore(st).get(row.key))
    assert fresh["state"] == "pending" and fresh["due_at"] > at(10)


def test_the_ceiling_costs_the_shop_nothing(st):
    """It never left. Counting it would make his own report disagree with his Meta bill."""
    sched(st, template_type="svc_follow_up")
    q = FakeQuota()
    go_policy(st, CeilingSender(), template_type="svc_follow_up", quota=q)
    assert q.used == 0 and len(q.releases) == 1


def test_the_ceiling_is_counted_apart_from_a_peer_failure(st):
    """The reason counts are how an operator sees a real notification-service outage. Burying a
    daily, expected, self-resolving condition in them destroys the signal they carry — and this is
    also the number that moves an owner to verify his business."""
    sched(st, template_type="svc_follow_up")
    res = go_policy(st, CeilingSender(), template_type="svc_follow_up", quota=FakeQuota())
    assert res.ceiling == 1 and res.failed == 0


def test_a_deferred_message_keeps_its_key_so_tomorrow_costs_one_unit(st):
    """Tomorrow's attempt is the SAME message. Billing must count it once however many days it
    waits for the ceiling to open."""
    row = sched(st, template_type="svc_follow_up")
    go_policy(st, CeilingSender(), template_type="svc_follow_up", quota=FakeQuota())
    first = run(ScheduleStore(st).get(row.key))["idempotency_key"]
    assert first
    q = FakeQuota()
    sender = FakeSender()
    run(tick(st, sender, quota=q).run("t1", now=at(10, day=16), library=LIB_POLICY,
                                      service_names=NAMES, establishment="ورشة النخبة",
                                      customer_names={"sub_a": "أحمد"}))
    assert sender.calls and sender.calls[0]["idempotency_key"] == first
    assert q.used == 1


# ── the reach window, wired into the tick ──────────────────────────────────────────────────────
def test_a_sent_reminder_records_the_person_reached(st):
    from app.core.reach import Reach

    sched(st)
    go(st, FakeSender(), quota=FakeQuota())
    assert run(Reach(st).count("t1", now=at(10))) == 1


def test_a_message_that_failed_reaches_nobody_and_counts_as_nobody(st):
    """Counting it would push the shop toward a ceiling it never touched, and then we would hold
    back a send WhatsApp would have accepted."""
    from app.core.reach import Reach

    sched(st)
    go(st, FakeSender(fail=True), quota=FakeQuota())
    assert run(Reach(st).count("t1", now=at(10))) == 0


def test_a_message_stopped_at_the_ceiling_reaches_nobody(st):
    from app.core.reach import Reach

    sched(st, template_type="svc_follow_up")
    go_policy(st, CeilingSender(), template_type="svc_follow_up", quota=FakeQuota())
    assert run(Reach(st).count("t1", now=at(10))) == 0
