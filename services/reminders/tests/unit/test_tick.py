"""The tick — where the gate, rendering, the sender and the ledger meet."""
from __future__ import annotations

import asyncio
from datetime import datetime

import pytest

from app.adapters.datastore.memory import MemoryDataStore
from app.core import engagement as E
from app.core import gate as G
from app.core.models import Preferences, Schedule, as_row
from app.core.stores import EngagementStore, PrefsStore, ScheduleStore, SendLogStore
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
    # A BASE URL, BECAUSE A DEPLOYMENT HAS ONE. It is what `{base}/p/{ref}/stop` is composed from,
    # and the gate now refuses marketing without it — no base URL means the mandatory one-tap exit
    # (§8.3) is a link that cannot be written. A test fixture that omitted it would be asserting
    # the behaviour of a misconfigured cluster; the refusal itself is proved deliberately in
    # test_marketing_needs_a_reachable_stop.
    kw.setdefault("public_base_url", "https://my.example.sa")
    return Tick(store=st, sender=sender, limits=G.Limits(), eng_cfg=ECFG, **kw)


def sched(st, **over):
    d = dict(tenant="t1", subject_ref="sub_a", service_id="oil", kind="reminder",
             due_at=at(9), cls="service", template_type="svc_service_reminder")
    d.update(over)
    s = Schedule(**d)
    run(ScheduleStore(st).upsert(s.tenant, s.key, as_row(s)))
    return s


def go(st, sender, *, now=None, choices=None, library=None, **kw):
    # `library` belongs to `run()`, not to the constructor — a test that wants a different set of
    # templates is choosing what is sendable, not how the engine is built.
    return run(tick(st, sender, **kw).run(
        "t1", now=now or at(10), library=library or LIB, service_names=NAMES,
        establishment="ورشة النخبة", customer_names={"sub_a": "أحمد"}, choices=choices))


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
    with patch.object(s, "_recipient", return_value=("+966500000000", "نورة")), \
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
    with patch.object(s, "_recipient", return_value=("+966500000000", "نورة")), \
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


# ── the ceiling, known BEFORE the send ─────────────────────────────────────────────────────────
class FakeCeiling:
    def __init__(self, limit: int):
        self.limit = limit
        self.reads = 0

    async def read(self, tenant):
        from app.core.ceiling import Ceiling

        self.reads += 1
        return Ceiling(limit=self.limit)


def many(st, n, *, template_type="svc_follow_up"):
    for i in range(n):
        sched(st, subject_ref=f"sub_{i}", service_id="oil", template_type=template_type)


def test_the_allowance_is_shared_across_the_whole_pass(st):
    """THE BUG THIS EXISTS FOR. `room` was an int decremented inside the per-row call, where the
    decrement went nowhere — so five due messages with two left would all have passed the check
    and been refused by Meta one at a time. Every existing test still passed."""
    many(st, 5)
    s = FakeSender()
    res = run(tick(st, s, quota=FakeQuota(), ceiling=FakeCeiling(2)).run(
        "t1", now=at(10), library=LIB_POLICY, service_names=NAMES,
        establishment="ورشة النخبة", customer_names={}))
    assert len(s.calls) == 2, f"sent {len(s.calls)} with room for 2"
    assert res.deferred == 3


def test_the_ceiling_is_read_once_per_tenant_not_once_per_message(st):
    """A shop with 300 due reminders must not ask notification-service 300 times for an answer
    that cannot change while the loop runs."""
    many(st, 6)
    c = FakeCeiling(10)
    run(tick(st, FakeSender(), quota=FakeQuota(), ceiling=c).run(
        "t1", now=at(10), library=LIB_POLICY, service_names=NAMES,
        establishment="ورشة النخبة", customer_names={}))
    assert c.reads == 1


def test_a_second_message_to_someone_already_reached_is_free(st):
    """The ceiling counts PEOPLE. Blocking a follow-up to a customer we already reached today
    would silence a shop for customers it had already paid to reach."""
    from app.core.reach import Reach

    run(Reach(st).record("t1", "sub_a", now=at(9)))
    sched(st, subject_ref="sub_a", template_type="svc_follow_up")
    s = FakeSender()
    run(tick(st, s, quota=FakeQuota(), ceiling=FakeCeiling(0)).run(
        "t1", now=at(10), library=LIB_POLICY, service_names=NAMES,
        establishment="ورشة النخبة", customer_names={}))
    assert len(s.calls) == 1, "an already-reached customer costs no ceiling"


def test_an_unknown_ceiling_blocks_nothing(st):
    many(st, 4)
    s = FakeSender()
    run(tick(st, s, quota=FakeQuota(), ceiling=FakeCeiling(0)).run(
        "t1", now=at(10), library=LIB_POLICY, service_names=NAMES,
        establishment="ورشة النخبة", customer_names={}))
    assert len(s.calls) == 4


def test_no_room_defers_a_follow_up_and_drops_a_confirmation(st):
    """The template decides, exactly as it does when Meta refuses (§8.4.3) — the only difference
    is that we found out before spending the send."""
    from app.core.reach import Reach

    # The ceiling is 1 and somebody else already used it — a real exhausted day. NOT a negative
    # limit: any negative reads as UNLIMITED (-1 is Meta's sentinel), so FakeCeiling(-2) said
    # "no ceiling" and the message went. My test, not the code.
    run(Reach(st).record("t1", "sub_other", now=at(9)))
    sched(st, subject_ref="sub_x", template_type="svc_visit_confirmation")
    res = run(tick(st, FakeSender(), quota=FakeQuota(), ceiling=FakeCeiling(1)).run(
        "t1", now=at(10), library=LIB_POLICY, service_names=NAMES,
        establishment="ورشة النخبة", customer_names={}))
    assert res.suppressed == 1 and res.ceiling == 1


# ── a slot is a reservation until the message goes (ز-7) ───────────────────────────────────────
def test_a_send_that_failed_gives_its_ceiling_slot_back(st):
    """A SLOT SPENT ON NOBODY IS ROOM TAKEN FROM THE NEXT CUSTOMER.

    The slot is taken before the send, like the quota unit beside it, and every path that abandons
    the row gave the unit back and kept the slot. So a template still in Meta's review — the
    normal state of a shop that connected this morning — shrank the shop's own room by one per
    failure. Four hundred rows behind it closed the day at a ceiling nobody came near, and every
    message after them waited until tomorrow for nothing.

    Room for 2, two rows, a sender that fails: both must be ATTEMPTED. Kept unfixed, the first
    failure eats a slot the second row never gets back.
    """
    many(st, 2)
    s = FakeSender(fail=True)
    res = run(tick(st, s, quota=FakeQuota(), ceiling=FakeCeiling(1)).run(
        "t1", now=at(10), library=LIB_POLICY, service_names=NAMES,
        establishment="ورشة النخبة", customer_names={}))
    assert len(s.calls) == 0                    # FakeSender records nothing when it fails
    assert res.failed == 2, "the second row was refused room a failed send never used"
    assert res.ceiling == 0, "nothing was stopped by the ceiling — the ceiling was never reached"


def test_a_send_refused_for_the_quota_gives_its_ceiling_slot_back(st):
    """The same, by the other door: a lapsed subscription is not a full ceiling, and telling the
    rest of the pass that it is defers messages for a reason that is not true."""
    many(st, 2)
    res = run(tick(st, FakeSender(), quota=FakeQuota(limit=0), ceiling=FakeCeiling(1)).run(
        "t1", now=at(10), library=LIB_POLICY, service_names=NAMES,
        establishment="ورشة النخبة", customer_names={}))
    assert res.suppressed == 2 and res.ceiling == 0


def test_a_message_that_actually_went_keeps_its_slot(st):
    """The other half, and the one that makes the give-back safe: a slot spent on a real message
    must NOT come back, or the shared allowance stops bounding anything at all."""
    many(st, 3)
    s = FakeSender()
    res = run(tick(st, s, quota=FakeQuota(), ceiling=FakeCeiling(2)).run(
        "t1", now=at(10), library=LIB_POLICY, service_names=NAMES,
        establishment="ورشة النخبة", customer_names={}))
    assert len(s.calls) == 2 and res.deferred == 1


def test_meta_refusing_closes_the_day_rather_than_handing_the_slot_back(st):
    """`CeilingReached` IS THE CEILING ANSWERING, so our count is wrong and not the ceiling. Giving
    the slot back would walk the next row into the same refusal, and the row after that — one
    rejected API call per remaining message from a shop already at its limit, which is exactly
    what gets a number rate-limited."""
    many(st, 4)
    sender = CeilingSender()
    res = run(tick(st, sender, quota=FakeQuota(), ceiling=FakeCeiling(10)).run(
        "t1", now=at(10), library=LIB_POLICY, service_names=NAMES,
        establishment="ورشة النخبة", customer_names={}))
    assert len(sender.calls) == 1, "the pass kept asking Meta after Meta said no"
    assert res.deferred == 4


# ── the ceiling's cost, recorded once ──────────────────────────────────────────────────────────
def test_the_first_day_the_ceiling_bites_is_recorded(st):
    """The input to 'twelve customers did not get your messages' — the sentence a dashboard or a
    support call is built on."""
    from app.core.ceiling_notice import NoticeStore

    many(st, 4)
    run(tick(st, FakeSender(), quota=FakeQuota(), ceiling=FakeCeiling(2)).run(
        "t1", now=at(10), library=LIB_POLICY, service_names=NAMES,
        establishment="ورشة النخبة", customer_names={}))
    row = run(NoticeStore(st).last("t1"))
    assert row and row["missed"] == 2 and row["ceiling"] == 2


def test_a_shop_that_never_hits_its_ceiling_is_never_recorded(st):
    """A limit that has cost him nothing is not a fact about his shop yet."""
    from app.core.ceiling_notice import NoticeStore

    many(st, 2)
    run(tick(st, FakeSender(), quota=FakeQuota(), ceiling=FakeCeiling(50)).run(
        "t1", now=at(10), library=LIB_POLICY, service_names=NAMES,
        establishment="ورشة النخبة", customer_names={}))
    assert run(NoticeStore(st).told("t1")) is False


def test_it_is_recorded_once_not_once_a_day(st):
    """A shop at its ceiling is there every day until it verifies. One row per establishment."""
    from app.core.ceiling_notice import NoticeStore

    many(st, 4)
    for day in (15, 16):
        many(st, 4)
        run(tick(st, FakeSender(), quota=FakeQuota(), ceiling=FakeCeiling(1)).run(
            "t1", now=at(10, day=day), library=LIB_POLICY, service_names=NAMES,
            establishment="ورشة النخبة", customer_names={}))
    first = run(NoticeStore(st).last("t1"))
    assert first["ceiling"] == 1
    assert len(run(st.scan_all("ceiling_notice", 100))) == 1


def test_recording_it_never_sends_anything(st):
    """A notice to the owner is itself a business-initiated message — same ceiling, same bill,
    and refused at exactly the moment it would be sent."""
    many(st, 4)
    s = FakeSender()
    run(tick(st, s, quota=FakeQuota(), ceiling=FakeCeiling(2)).run(
        "t1", now=at(10), library=LIB_POLICY, service_names=NAMES,
        establishment="ورشة النخبة", customer_names={}))
    assert len(s.calls) == 2, "only the two customer messages; no notice to the owner"


# ── the cross-visit merge, through the real tick (spec §5.8.1) ─────────────────────────────────
#
# `test_merge.py` covers the decision space of the pure planner. These prove the wiring: that the
# fold happens after the gate and before the render, that the sentence the customer reads names
# both services, and that the row which rode along is closed rather than left to go out tomorrow.

def test_two_visits_days_apart_arrive_as_one_message(st):
    """Sunday's oil, Tuesday's tyres — booked two days apart, and nothing knows they are one man
    until the first goes out. He should read one sentence, not two messages in three days."""
    sched(st, service_id="oil", due_at=at(9))
    sched(st, service_id="tyres", due_at=at(9, day=17))
    s = FakeSender()

    res = go(st, s)

    assert len(s.calls) == 1, "two messages went out where one was due"
    assert s.calls[0]["variables"][2] == "غيار الزيت والإطارات"
    assert res.sent == 1 and res.merged == 1


def test_the_row_that_rode_along_is_closed_not_left_pending(st):
    """Left pending it goes out tomorrow saying what today's message already said — and the
    customer reads the merge as a system that repeats itself.

    ASSERTED ON THE ROW, NOT ON A SILENT TOMORROW. This used to assert that a second pass sent
    NOTHING, which was true only while no ladder existed: a reminder that goes out now schedules
    its next rung (§5.6.1), so "the shop sends nothing else ever" is no longer the product. The
    question this test asks is whether the MERGED row was closed — and that is what it reads.
    """
    sched(st, service_id="oil", due_at=at(9))
    sched(st, service_id="tyres", due_at=at(9, day=17))
    s = FakeSender()

    go(st, s)

    rows, _ = run(st.find("schedules", {"tenant": "t1", "service_id": "tyres"}, limit=10))
    merged = [r for r in rows if r.get("kind") == "reminder"]
    assert merged and merged[0]["state"] == "merged"
    assert merged[0]["merged_into"]


def test_a_reminder_a_week_out_is_left_for_its_own_day(st):
    """Three days is the window. Past it the two are not the same conversation, and pulling one
    forward a week teaches him that we nag."""
    sched(st, service_id="oil", due_at=at(9))
    sched(st, service_id="tyres", due_at=at(9, day=25))
    s = FakeSender()

    res = go(st, s)

    assert s.calls[0]["variables"][2] == "غيار الزيت"
    assert res.merged == 0


# ── the follow-up ladder, which starts here or nowhere (§5.6.1) ────────────────────────────────
from app.core.consent import Consent  # noqa: E402
from app.core.models import RuleState  # noqa: E402
from app.core.stores import RuleStore  # noqa: E402


def learned(st, days=90, first_rung_returns=0):
    """What the engine knows about this customer's rhythm — the ladder's only spacing input."""
    r = RuleState(tenant="t1", subject_ref="sub_a", service_id="oil", interval_days=days,
                  observations=4)
    row = as_row(r)
    row["first_rung_returns"] = first_rung_returns
    run(RuleStore(st).upsert("t1", r.key, row))


def rungs_of(st):
    rows, _ = run(st.find("schedules", {"tenant": "t1"}, limit=50))
    return sorted([r for r in rows if str(r.get("kind", "")).startswith("ladder_")],
                  key=lambda r: r["due_at"])


def test_a_sent_reminder_schedules_the_next_rung(st):
    """THE WIRE THAT WAS NOT THERE. `core/ladder.py` was written, tested and called by nothing:
    every rule was right and no customer would ever have received a second message."""
    sched(st)
    learned(st)
    go(st, FakeSender())

    assert len(rungs_of(st)) >= 1


def test_the_ladder_starts_only_after_the_message_actually_WENT(st):
    """A ladder built at schedule time would climb after a message that was suppressed, deferred or
    dropped at the ceiling — pressing a customer about something he never received."""
    sched(st)
    learned(st)
    go(st, FakeSender(fail=True))

    assert rungs_of(st) == []


def test_without_consent_there_is_no_offer_rung(st):
    """§8.5: no offer reaches him under any circumstances. `never_asked` is not a yes."""
    sched(st)
    learned(st)
    go(st, FakeSender())

    assert all(r.get("cls") != "marketing" for r in rungs_of(st))


def test_a_rung_with_no_offer_on_it_is_not_billed_as_marketing(st):
    """د-8 · THIS TEST USED TO ASSERT THE DEFECT — it required `cls == "marketing"`.

    The rung was a COPY of the reminder row with the class flipped: same template type, no
    `offer_value`, no coupon, no expiry. An ordinary service sentence was therefore charged to
    the marketing share, counted against its cap, held by its cooling rules — and dropped
    outright for every customer who never gave explicit marketing consent. The second touch
    disappeared for most people, and nothing recorded that it had.

    Marketing is what an OFFER makes it. Until something in the product can attach one, the
    rung is what its words are.
    """
    sched(st)
    learned(st)
    run(Consent(st).record("t1", "sub_a", state="granted", source="customer_page",
                           shop="ورشة النخبة"))
    go(st, FakeSender())

    rows = rungs_of(st)
    assert rows, "the ladder must still produce its rungs"
    for r in rows:
        assert not r.get("offer_value"), "the premise of this test: no rung carries an offer"
        assert r.get("cls") != "marketing", (
            "a service sentence billed as marketing is dropped for whoever never consented")


def test_the_rungs_are_separate_rows_not_one_that_overwrites_the_other(st):
    """The schedule's natural key is (tenant, customer, service, kind). Two rungs sharing a kind
    would be ONE row, and the second would silently replace the first."""
    sched(st)
    learned(st)
    run(Consent(st).record("t1", "sub_a", state="granted", source="customer_page",
                           shop="ورشة النخبة"))
    go(st, FakeSender())

    rows = rungs_of(st)
    assert len({r["kind"] for r in rows}) == len(rows)


def test_the_spacing_comes_from_HIS_cycle(st):
    """15% of ninety days is not 15% of ten — a fixed delay makes a car wash nag and a workshop
    forget."""
    sched(st)
    learned(st, days=90)
    go(st, FakeSender(), now=at(10))
    long_gap = rungs_of(st)[0]["due_at"] - at(10)

    assert long_gap == int(90 * 0.15 * 86400)


def test_a_follow_up_has_no_ladder(st):
    """A ladder answers one question — "he did not come" — and a follow-up is not that question."""
    sched(st, kind="follow_up", template_type="svc_service_reminder")
    learned(st)
    go(st, FakeSender())

    assert rungs_of(st) == []


# ── the switch the owner throws ────────────────────────────────────────────────────────────────
def test_a_reason_the_shop_switched_off_sends_nothing_and_does_not_come_back(st):
    """CLOSED, NOT LEFT PENDING. A schedule that stays pending is retried on every tick for ever,
    and «رسائلي» would show a queue that never drains for a switch he deliberately threw."""
    from app.core.reason_choices import ChoiceStore
    sched(st)
    store = ChoiceStore(st)
    run(store.set("t1", "service_due", on=False))
    choices = run(store.load("t1"))

    s = FakeSender()
    res = go(st, s, choices=choices)
    assert s.calls == [] and res.sent == 0 and res.suppressed == 1

    # And a second pass finds nothing to do — the row was closed, not deferred.
    res2 = go(st, FakeSender(), choices=choices)
    assert res2.scanned == 0


def test_the_switch_is_read_per_reason_not_per_template(st):
    """The cycle reminder and the ladder rung share a template type. Switching the ladder off must
    not silence the reminder that produces it."""
    from app.core.reason_choices import ChoiceStore
    sched(st)
    store = ChoiceStore(st)
    run(store.set("t1", "no_response", on=False))

    s = FakeSender()
    assert go(st, s, choices=run(store.load("t1"))).sent == 1


# ── the branch travels from the visit to the ledger ───────────────────────────────────────────
def test_a_sent_message_carries_the_branch_its_visit_happened_at(st):
    """«كم رسالة خرجت باسم فرع جدة» had no answer, and could never be given one later: this log
    is the only record that a message existed, and a row written without a branch cannot be
    labelled after the fact."""
    sched(st, branch_id="brn-jeddah")
    go(st, FakeSender())
    rows, _ = run(SendLogStore(st)._find("t1", {"outcome": "sent"}, limit=10))
    assert [r["branch_id"] for r in rows] == ["brn-jeddah"]


def test_a_suppression_carries_it_too(st):
    """The suppressions are the point of this ledger — a refusal that cannot be attributed to a
    place is a refusal an owner with three branches cannot act on."""
    sched(st, branch_id="brn-jeddah")
    run(PrefsStore(st).put("t1", "sub_a", as_row(Preferences(
        tenant="t1", subject_ref="sub_a", stopped={"service": True}))))
    go(st, FakeSender())
    rows, _ = run(SendLogStore(st)._find("t1", {"outcome": "suppressed"}, limit=10))
    assert rows and all(r["branch_id"] == "brn-jeddah" for r in rows)


def test_a_message_with_no_branch_behind_it_stays_empty(st):
    """EMPTY IS A REAL VALUE. A shop that labels nothing, and a campaign with no visit behind it,
    are «غير محدَّد» — inventing a branch for them would put numbers under a place nobody claimed."""
    sched(st)
    go(st, FakeSender())
    rows, _ = run(SendLogStore(st)._find("t1", {"outcome": "sent"}, limit=10))
    assert rows[0]["branch_id"] == ""


# ── أ-4 · the words travel with the offer, not only into the message ───────────────────────────
def test_the_send_log_keeps_the_service_names_the_message_was_rendered_with(st):
    """THE FIRST LINK. `send_one` is handed the names — the caller owns the catalogue and sends
    the words — renders «خصم على غيار الزيت» with them, and used to drop them on the floor. The
    customer's page is read days later, when nobody holds that map any more, and it printed our
    identifiers to him: «على: oil».
    """
    from app.core.consent import Consent

    # A CUSTOMER THE SHOP HAS SEEN. Marketing to somebody who has not been near the place for
    # months is paused by the engagement rule, which is a different guard and not this one's
    # subject.
    run(EngagementStore(st).put("t1", "sub_a", {"score": 100.0, "scored_at": at(9)}))
    # MARKETING NEEDS AN EXPLICIT YES — «لم يرفض» is not consent, and the gate says so.
    run(Consent(st).record("t1", "sub_a", state="granted", source="customer_page",
                           shop="ورشة النخبة"))
    sender = FakeSender()
    row = {"tenant": "t1", "subject_ref": "sub_a", "cls": "marketing",
           "template_type": "mkt_offer", "service_id": "_campaign", "kind": "campaign",
           "owner_text": "خصم 20%", "idempotency_key": "idem_x", "id": "idem_x",
           "offer_text": "خصم 20%", "offer_expires_at": at(10, day=20),
           "offer_services": ["oil", "tyres"]}

    out = run(tick(st, sender).send_one("t1", row, now=at(10), library=LIB,
                                        service_names=NAMES, establishment="ورشة النخبة"))
    assert out["sent"] is True, out

    logged = run(SendLogStore(st).live_offers("t1", "sub_a", used_refs=set(), now=at(10)))
    assert logged, "the offer was sent, so it is on the log"
    assert logged[0]["offer_service_names"] == ["غيار الزيت", "الإطارات"]
    assert logged[0]["offer_code"], "and the coupon it was rendered with is kept beside them"


# ── the report Flow's own button (rating-app-feature.md phase 6b) ─────────────────────────────
def test_send_one_passes_flow_token_and_flow_action_data_to_the_sender(st):
    """The schedule row is the ONLY place `send_one` (the campaigns/insights path) can read a
    Flow button from — it has no visit of its own to derive a token from, unlike the scheduled
    rating-request send. Absent on every existing caller, so this is additive."""
    from app.core.consent import Consent

    run(EngagementStore(st).put("t1", "sub_a", {"score": 100.0, "scored_at": at(9)}))
    run(Consent(st).record("t1", "sub_a", state="granted", source="customer_page",
                           shop="ورشة النخبة"))
    sender = FakeSender()
    row = {"tenant": "t1", "subject_ref": "sub_a", "cls": "marketing",
          "template_type": "mkt_offer", "service_id": "_campaign", "kind": "campaign",
          "owner_text": "خصم 20%", "idempotency_key": "idem_flow", "id": "idem_flow",
          "offer_text": "خصم 20%", "offer_expires_at": at(10, day=20),
          "offer_services": ["oil"],
          "flow_token": "insights:digest:t1:sub_a:2900",
          "flow_action_data": {"header_text": "أسبوعك في ورشة النخبة", "show_visits": True,
                               "visits_text": "120 (+15)"}}

    out = run(tick(st, sender).send_one("t1", row, now=at(10), library=LIB,
                                        service_names=NAMES, establishment="ورشة النخبة"))
    assert out["sent"] is True, out
    assert sender.calls[0]["flow_token"] == "insights:digest:t1:sub_a:2900"
    assert sender.calls[0]["flow_action_data"]["show_visits"] is True


def test_send_one_with_no_flow_fields_on_the_row_passes_them_through_empty(st):
    """Every existing caller (a plain campaign) never set these — `send_one` must not invent a
    token or a data payload for a send that carries none."""
    from app.core.consent import Consent

    run(EngagementStore(st).put("t1", "sub_a", {"score": 100.0, "scored_at": at(9)}))
    run(Consent(st).record("t1", "sub_a", state="granted", source="customer_page",
                           shop="ورشة النخبة"))
    sender = FakeSender()
    row = {"tenant": "t1", "subject_ref": "sub_a", "cls": "marketing",
          "template_type": "mkt_offer", "service_id": "_campaign", "kind": "campaign",
          "owner_text": "خصم 20%", "idempotency_key": "idem_noflow", "id": "idem_noflow",
          "offer_text": "خصم 20%", "offer_expires_at": at(10, day=20), "offer_services": ["oil"]}

    out = run(tick(st, sender).send_one("t1", row, now=at(10), library=LIB,
                                        service_names=NAMES, establishment="ورشة النخبة"))
    assert out["sent"] is True, out
    assert sender.calls[0]["flow_token"] == ""
    assert sender.calls[0]["flow_action_data"] is None


def test_a_structured_offer_with_no_free_line_is_still_an_entitlement(st):
    """أ-6 · END OF THE CHAIN. The campaign route composes the entitlement now, so a send whose
    template has no `owner` fill still leaves something the till and his page can find. The row is
    what those readers filter on: `if r.get("offer_text")` — and a blank one is invisible to all
    of them while the message sits in the customer's phone.
    """
    from app.core.consent import Consent
    from app.core.offer_text import compose

    run(EngagementStore(st).put("t1", "sub_a", {"score": 100.0, "scored_at": at(9)}))
    run(Consent(st).record("t1", "sub_a", state="granted", source="customer_page",
                           shop="ورشة النخبة"))
    sender = FakeSender()
    row = {"tenant": "t1", "subject_ref": "sub_a", "cls": "marketing",
           "template_type": "mkt_offer", "service_id": "_campaign", "kind": "campaign",
           # NO `owner_text` — which is the whole point: the three offer templates never ask for
           # one, so this is the ordinary case rather than an edge one.
           "owner_text": "", "idempotency_key": "idem_y", "id": "idem_y",
           "offer_text": compose(value="20%", service_names=["غيار الزيت"], has_expiry=True),
           "offer_expires_at": at(10, day=20), "offer_value": "20%",
           "offer_services": ["oil"]}

    out = run(tick(st, sender).send_one("t1", row, now=at(10), library=LIB,
                                        service_names=NAMES, establishment="ورشة النخبة"))
    assert out["sent"] is True, out

    live = run(SendLogStore(st).live_offers("t1", "sub_a", used_refs=set(), now=at(10)))
    assert live, "a campaign that sent an offer and left nothing to honour is the defect"
    assert live[0]["offer_text"] == "خصم 20% على غيار الزيت"


# ── د-11 · `drop` means drop at BOTH gates ─────────────────────────────────────────────────────
def test_a_drop_template_caught_by_quiet_hours_is_dropped_not_held_until_morning(st):
    """«سجّلنا زيارتك» at seven the next morning is not a late confirmation — it is a strange one.

    The template says `deferral: drop` for exactly that reason, and the CEILING branch has always
    read it. The quiet-hours branch did not: a visit recorded at eleven at night was pushed a full
    day forward and arrived after the customer had long gone home. The policy existed, was correct,
    and was consulted at one of the two doors that can delay a message.
    """
    # A REMINDER, NOT A CONFIRMATION. The confirmation is deliberately EXEMPT from quiet hours —
    # somebody who visits at eleven at night is not served by silence — so it is the one template
    # this branch never sees. The policy belongs to the template, not to the class, and a shop can
    # mark any of them `drop`.
    drop_lib = [{**t, "deferral": "drop"} if t["type"] == "svc_service_reminder" else t
                for t in LIB] + [{"name": "svc_service_reminder_drop",
                                  "type": "svc_service_reminder", "tone": "brief",
                                  "class": "service", "variables": [1, 2, 3],
                                  "fills": ["system", "system", "catalogue"],
                                  "active": True, "deferral": "drop"}]
    row = sched(st, due_at=at(23))
    s = FakeSender()

    res = run(tick(st, s).run("t1", now=at(23), library=drop_lib, service_names=NAMES,
                              establishment="ورشة النخبة", customer_names={"sub_a": "أحمد"}))

    assert not s.calls, "nothing goes out during quiet hours either way"
    assert res.deferred == 0, "a `drop` template must not be carried to tomorrow"
    assert res.suppressed == 1
    assert run(ScheduleStore(st).get(row.key))["state"] == "suppressed"


def test_a_defer_template_caught_by_quiet_hours_is_still_held_until_morning(st):
    """The other direction, and the one that must not break: nothing about a follow-up spoils
    overnight, and dropping it would lose a message the shop wanted sent."""
    row = sched(st, due_at=at(23))
    s = FakeSender()

    res = run(tick(st, s).run("t1", now=at(23), library=LIB, service_names=NAMES,
                              establishment="ورشة النخبة", customer_names={"sub_a": "أحمد"}))

    assert res.deferred == 1 and res.suppressed == 0
    fresh = run(ScheduleStore(st).get(row.key))
    assert fresh["state"] == "pending"


# --- د-7 · the rung's voice reaches the sender ---------------------------------------------------

_TWO_TONES = LIB + [{"name": "svc_service_reminder_warm", "type": "svc_service_reminder",
                     "tone": "warm", "class": "service", "variables": [1, 2, 3],
                     "fills": ["system", "system", "catalogue"], "active": True}]


def _send_template(st, *, tone_index):
    sched(st, kind="ladder_1", tone_index=tone_index, due_at=at(9))
    s = FakeSender()
    run(tick(st, s).run("t1", now=at(10), library=_TWO_TONES, service_names=NAMES,
                        establishment="ورشة النخبة", customer_names={"sub_a": "أحمد"}))
    assert s.calls, "the rung must go out"
    return s.calls[0]["template_name"]


def test_the_rungs_index_reaches_the_template_choice(st):
    """د-7 · the whole wire, from the row `_ladder` stamped to the name on the wire.

    Proving it in `choose` alone would leave the defect exactly where it was: the parameter existed
    and nothing passed it.
    """
    first = _send_template(st, tone_index=1)
    second = _send_template(MemoryDataStore(), tone_index=2)

    assert first != second, "the second rung must not repeat the first word for word"


# ── the claim that was abandoned mid-send ──────────────────────────────────────────────────────
#
# WHAT THESE LOCK DOWN, AND IT WAS COMPLETELY SILENT. `_claim` moves a row to `sending` before it
# calls anything external. If the process dies between that write and the one that follows — a
# deploy, an eviction, an OOM — the row stayed `sending` for ever: never selected by `due()`, which
# reads `pending`; never reported, because it is not `sent` or `failed`. The reminder simply never
# happened and nobody found out.
#
# `_fail()` already returns a row to `pending` rather than closing it, with a comment saying a
# closed schedule is a reminder that silently never happens. That covers an exception being RAISED.
# Process death raises nothing, and it is the commonest event during a deploy.
def test_a_claim_abandoned_mid_send_is_swept_back_and_delivered(st):
    from app.core.stores import CLAIM_LEASE_SECONDS

    s = sched(st)
    store = ScheduleStore(st)

    # A worker claimed it and never came back — this is exactly what the row looks like afterwards.
    row = run(store.get(s.key))
    row["state"] = "sending"
    row["claimed_at"] = at(10) - CLAIM_LEASE_SECONDS - 60
    run(store.upsert("t1", s.key, row))

    sender = FakeSender()
    go(st, sender, now=at(10))

    assert sender.calls, "the abandoned reminder was never re-sent — the customer lost it"
    assert run(store.get(s.key)).get("state") != "sending"


def test_a_claim_still_inside_its_lease_is_left_alone(st):
    """Reclaiming a slow send would deliver the message twice. The lease is the whole guard."""
    s = sched(st)
    store = ScheduleStore(st)

    row = run(store.get(s.key))
    row["state"] = "sending"
    row["claimed_at"] = at(10) - 30          # claimed half a minute ago; its owner is alive
    run(store.upsert("t1", s.key, row))

    sender = FakeSender()
    go(st, sender, now=at(10))

    assert not sender.calls, "a live claim was stolen — the customer would get two messages"


def test_the_claim_is_stamped_so_it_can_ever_be_reclaimed(st):
    """Without `claimed_at`, a stranded row is indistinguishable from one claimed a second ago."""
    sched(st)
    sender = FakeSender()
    go(st, sender, now=at(10))

    row = run(ScheduleStore(st).get("t1|sub_a|oil|reminder"))
    assert int(row.get("claimed_at") or 0) > 0, "nothing stamped the claim"


def test_two_replicas_racing_over_one_send_agree_on_the_idempotency_key(st):
    """ز-2 — the key is the crossing guard, and it used to be absent on the first crossing.

    A row that has never been sent carries no key. The line that minted one called `uuid4()`, so
    two replicas of the tick that both won the claim in the same second sent two messages carrying
    two unrelated keys — and the quota, the notifier and the send log all recognise a repeat BY
    the key. Every layer saw two different sends because that is what it was handed. The customer
    read the same reminder twice in the same minute and the shop paid for both.

    TWO STORES, NOT ONE, and that is the whole point: replicas that can see each other's writes
    would agree by accident. These cannot, so agreeing is a property of the key itself.
    """
    other = MemoryDataStore()
    for store in (st, other):
        s = Schedule(tenant="t1", subject_ref="sub_a", service_id="oil", kind="reminder",
                     due_at=at(9), cls="service", template_type="svc_service_reminder")
        run(ScheduleStore(store).upsert(s.tenant, s.key, as_row(s)))

    first, second = FakeSender(), FakeSender()
    go(st, first)
    run(tick(other, second).run(
        "t1", now=at(10), library=LIB, service_names=NAMES,
        establishment="ورشة النخبة", customer_names={"sub_a": "أحمد"}, choices=None))

    assert first.calls and second.calls, "both replicas must have attempted the send"
    assert first.calls[0]["idempotency_key"] == second.calls[0]["idempotency_key"], (
        "two replicas sending the same reminder must present the same key — otherwise the "
        "duplicate barrier sees two unrelated messages and the customer gets both")


def test_a_later_send_of_the_same_reminder_gets_its_own_key(st):
    """The other half, and without it the fix above is satisfiable by a constant.

    A key that never changes would make every send of this reminder look like a repeat of the
    first — the customer would be reminded once and never again, and the failure would be silent.
    What separates one occasion from the next is `due_at`: a deferral moves it, and a recurring
    cycle earns a new one.
    """
    from app.core.tick import _send_key

    row = {"tenant": "t1", "subject_ref": "sub_a", "service_id": "oil", "kind": "reminder",
           "due_at": at(9)}
    later = dict(row, due_at=at(9, day=20))
    assert _send_key(row) == _send_key(dict(row)), "the same occasion is the same key"
    assert _send_key(row) != _send_key(later), "a later send is a different occasion"


# ── the mandatory exit must EXIST before any marketing goes out (§8.3) ────────────────────────
def test_marketing_needs_a_reachable_stop(st):
    """WITHOUT A BASE URL THERE IS NO STOP LINK, so there is no one-tap exit to put in the
    message — and marketing with no working opt-out breaches the regulation and Meta's policy for
    the category both.

    THE GUARD USED TO BE A PARAMETER defaulting to True. Every caller in the product therefore
    asserted «the stop link works» without anything checking, which is a guard that has never once
    said no. It is derived from `public_base_url` now — the same value the link is composed from,
    so the refusal and the link cannot disagree.
    """
    from app.core.consent import Consent

    run(EngagementStore(st).put("t1", "sub_a", {"score": 100.0, "scored_at": at(9)}))
    run(Consent(st).record("t1", "sub_a", state="granted", source="customer_page",
                           shop="ورشة النخبة"))
    row = {"tenant": "t1", "subject_ref": "sub_a", "cls": "marketing",
           "template_type": "mkt_offer", "service_id": "_campaign", "kind": "campaign",
           "owner_text": "خصم 20%", "idempotency_key": "idem_z", "id": "idem_z",
           "offer_text": "خصم 20%", "offer_expires_at": at(10, day=20),
           "offer_services": ["oil"]}

    blind = run(tick(st, FakeSender(), public_base_url="").send_one(
        "t1", dict(row), now=at(10), library=LIB, service_names=NAMES,
        establishment="ورشة النخبة"))
    assert blind["sent"] is False, "marketing left with no way for the customer to stop it"
    assert "رابط الإيقاف" in str(blind.get("reason") or blind)

    # AND THE GUARD MUST NOT EAT THE ORDINARY CASE — a refusal that fires on a correctly
    # configured deployment is a guard nobody keeps.
    ok = run(tick(st, FakeSender()).send_one(
        "t1", dict(row), now=at(10), library=LIB, service_names=NAMES,
        establishment="ورشة النخبة"))
    assert ok["sent"] is True, ok


def test_a_service_message_still_goes_out_with_no_base_url(st):
    """ONLY MARKETING NEEDS THE EXIT. A confirmation that his car is ready is not direct
    marketing, and refusing it because a link is unroutable would take the product down to
    protect a rule that does not apply to it."""
    sched(st)

    out = run(tick(st, FakeSender(), public_base_url="").run(
        "t1", now=at(10), library=LIB, service_names=NAMES, establishment="ورشة النخبة",
        customer_names={"sub_a": "أحمد"}))

    assert out.sent == 1, out


# ── the invitation, which is the only way consent can ever be given ───────────────────────────
LIB_INVITE = [{"name": "svc_service_reminder_brief", "type": "svc_service_reminder",
               "tone": "brief", "class": "service", "variables": [1, 2, 3, 4],
               "fills": ["system", "system", "catalogue", "invite"], "active": True}]


def test_a_service_message_carries_the_invitation_for_somebody_who_has_not_agreed(st):
    """THE DEFECT THIS CLOSES, AND IT DISABLED A WHOLE PRODUCT LINE.

    Marketing is opt-IN, so with no way to grant, no promotional message may ever lawfully leave.
    There was no way: the library declared a `button` on sixty of sixty-six templates, nothing
    submits buttons to Meta, and notification-service has no notion of one. The campaigns engine —
    complete, and sold as an app — could not send for the life of the product, and nothing said so.
    """
    sched(st)
    s = FakeSender()

    go(st, s, library=LIB_INVITE)

    assert s.calls, "nothing was sent"
    last = s.calls[0]["variables"][-1]
    assert "/allow" in last, f"no grant link in the invitation: {last}"
    assert "tnt" not in last or "." in last, "the reference must be the one portal reads"


def test_somebody_who_already_agreed_is_not_invited_again(st):
    """AND HE IS NOT SENT TO A CLOSED PAGE EITHER. The line he gets carries no link at all: the
    customer page is shut for this release, so an invitation to open it would break a promise in
    the first sentence of the message."""
    from app.core.consent import Consent

    sched(st)
    run(Consent(st).record("t1", "sub_a", state="granted", source="customer_page", shop="ورشة"))
    s = FakeSender()

    go(st, s, library=LIB_INVITE)

    assert s.calls
    last = s.calls[0]["variables"][-1]
    assert "http" not in last, f"a granted customer was sent a link to a closed page: {last}"
    assert last.strip(), "Meta refuses an empty variable"


def test_the_invitation_steps_back_rather_than_taking_the_message_with_it(st):
    """A message that invites somebody to tap nothing is worse than one that invites nobody — but
    it is not worse than SILENCE, which is what this used to cost.

    THE CORRECTION, FROM COUNTING THE LIBRARY. Thirty-six wordings carry the `invite` fill and they
    are service, personal, awareness and warning; not one service wording has ever carried a stop
    link. So refusing to render without a base was killing the shop's ordinary traffic — every
    visit confirmation, every reminder — to protect the perfection of a marketing opt-in offer.

    The invitation is now a line that promises nothing when there is nothing to promise. The exit
    from marketing still refuses, and must: see test_marketing_needs_a_reachable_stop.
    """
    sched(st)
    s = FakeSender()

    res = go(st, s, library=LIB_INVITE, public_base_url="")

    assert res.sent == 1, res
    last = s.calls[0]["variables"][-1]
    assert "http" not in last, f"an invitation to nowhere still went out: {last}"
    assert last.strip(), "Meta refuses an empty variable"



def test_somebody_who_stopped_the_offers_is_never_invited_back(st):
    """§8.5 IN ITS OWN WORDS: «إعادة دعوة من رفض ملاحقة، لا تسويق».

    The first version of this carried a boolean, which made a withdrawal indistinguishable from
    silence — so every service message a shop sent would have re-asked a customer who had already
    said no, forever. He gets a neutral line: no invitation, no link, and not empty either, because
    Meta refuses a blank variable.
    """
    from app.core.consent import Consent

    sched(st)
    run(Consent(st).record("t1", "sub_a", state="withdrawn", source="customer_page"))
    s_ = FakeSender()

    go(st, s_, library=LIB_INVITE)

    assert s_.calls
    last = s_.calls[0]["variables"][-1]
    assert "/allow" not in last, f"a customer who refused was invited again: {last}"
    assert "http" not in last
    assert last.strip(), "Meta refuses an empty variable"


# ── reach pruning is global, not per-tenant (perf) ─────────────────────────────────────────────
def test_run_no_longer_prunes_reach_itself(st):
    """`Tick.run()` used to call `Reach.prune()` (a full, unscoped `reached_24h` scan) once per
    tenant with due work. That is now `Tick.prune_reach()`, called once per tick invocation by the
    caller — never from inside `run()`. Proved by counting `scan_all` calls against the reach
    collection across several tenants' `run()` calls: it must stay at zero."""
    calls = {"n": 0}
    real_scan_all = st.scan_all

    async def counting_scan_all(collection, limit, **kw):
        if collection == "reached_24h":
            calls["n"] += 1
        return await real_scan_all(collection, limit, **kw)

    st.scan_all = counting_scan_all

    t = tick(st, FakeSender())
    for tenant in ("t1", "t2", "t3"):
        sched(st, tenant=tenant)
        run(t.run(tenant, now=at(10), library=LIB, service_names=NAMES,
                  establishment="ورشة النخبة", customer_names={}))

    assert calls["n"] == 0, "run() re-introduced a per-tenant reach scan"


def test_prune_reach_does_the_one_global_scan(st):
    """`Tick.prune_reach()` is the one place that still scans `reached_24h` — proved by calling it
    once and observing exactly one `scan_all` against that collection, regardless of how many
    tenants' rows are in it."""
    from app.core.reach import Reach

    calls = {"n": 0}
    real_scan_all = st.scan_all

    async def counting_scan_all(collection, limit, **kw):
        if collection == "reached_24h":
            calls["n"] += 1
        return await real_scan_all(collection, limit, **kw)

    st.scan_all = counting_scan_all

    reach = Reach(st)
    for tenant in ("t1", "t2", "t3"):
        run(reach.record(tenant, "sub_a", now=at(9)))

    t = tick(st, FakeSender())
    gone = run(t.prune_reach(now=at(9) + 25 * 3600))

    assert calls["n"] == 1
    assert gone == 3
