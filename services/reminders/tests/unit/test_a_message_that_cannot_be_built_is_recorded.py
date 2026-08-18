"""A message that cannot be composed leaves a row and closes — it does not retry for ever.

THE STATE THIS WAS WRITTEN AGAINST, WHICH WAS THE LIVE STATE OF THE FLEET.

`render` refuses for permanent reasons: no approved template of this type, a numbering gap, an
owner's text that breaks a rule, or the public base being unset — which is why all 36 service
wordings currently fail while the customer page is switched off.

On the campaign path that refusal was caught. On the VISIT path — the most frequent message the
product sends — it was not, so it left `_one`, landed in the batch's generic `except Exception`
and was handed to `_fail`, which is written for a peer being briefly unavailable: back to pending,
due in an hour, for ever. Nothing was written to the send log; nothing was closed; the only number
that moved was `res.failed`, which no screen reads.

So the shop sent nothing, and no screen in the product had a row to show for it. That is the
difference this file holds in place: the owner's send log answers «لم تُرسَل، وهذا السبب» instead
of staying empty while an engine retries in the dark.
"""
from __future__ import annotations

import pytest

from app.adapters.datastore.memory import MemoryDataStore
from app.core.stores import ScheduleStore, SendLogStore

from test_tick import FakeSender, at, go, run, sched


@pytest.fixture
def st():
    # ITS OWN FIXTURE RATHER THAN THE ONE IN `test_tick`. Importing that name and then naming a
    # parameter after it shadows it in every test here — four warnings that say nothing and would
    # have to be silenced one by one.
    return MemoryDataStore()


#: THE LIVE SHAPE OF THE FAILURE, NOT A CONVENIENT ONE. The wording exists, its class is enabled
#: and the gate lets it through — and then the fourth blank is filled from `link`, the customer's
#: own page, which is composed from the public base. With the base unset that is exactly the
#: refusal killing all 36 service wordings on the fleet today.
#:
#: NOT AN EMPTY LIBRARY. A library missing the type is refused EARLIER, by the gate, with its own
#: sentence — so a test built that way would prove the gate works and never reach the renderer.
LINKED_LIB: list[dict] = [{"name": "svc_service_reminder_brief", "type": "svc_service_reminder",
                           "tone": "brief", "class": "service", "variables": [1, 2, 3, 4],
                           "fills": ["system", "system", "catalogue", "link"], "active": True}]


def test_a_render_failure_writes_one_row_to_the_send_log(st):
    sched(st)
    sender = FakeSender()
    res = go(st, sender, library=LINKED_LIB, public_base_url="")

    assert sender.calls == []
    rows = run(SendLogStore(st).since("t1", "sub_a", since=0))
    assert len(rows) == 1, "the one record that a message was owed and did not go"
    assert rows[0]["outcome"] == "suppressed"
    # THE RENDERER'S OWN SENTENCE TRAVELS. «تعذّر بناء الرسالة» alone would tell an owner nothing
    # he can act on; what follows it is whether he waits on Meta, fixes his own text, or calls us.
    assert "تعذّر بناء الرسالة" in rows[0]["reason"]
    assert res.suppressed == 1
    assert res.failed == 0, "a content refusal is not an outage"


def test_it_closes_the_schedule_instead_of_retrying_hourly_for_ever(st):
    sched(st)
    go(st, FakeSender(), library=LINKED_LIB, public_base_url="")

    row = run(ScheduleStore(st).get("t1|sub_a|oil|reminder"))
    assert row is not None
    # PENDING WITH A NEW `due_at` IS THE DEFECT. The same inputs refuse identically next hour, so
    # a retry is a tick spent to reach the same answer — for ever, once per hour, per message,
    # per shop.
    assert row["state"] == "suppressed", "a permanent refusal is a terminal state"
    assert "تعذّر بناء الرسالة" in row["reason"]


def test_a_second_tick_does_not_produce_a_second_row(st):
    sched(st)
    sender = FakeSender()
    go(st, sender, library=LINKED_LIB, public_base_url="")
    go(st, sender, now=at(11), library=LINKED_LIB, public_base_url="")

    # THE ROW IS CLOSED, SO THE SECOND PASS HAS NOTHING DUE. Without the close this asserted the
    # opposite: one more log row every hour, for ever, about the same message.
    assert len(run(SendLogStore(st).since("t1", "sub_a", since=0))) == 1
    assert sender.calls == []


def test_a_sendable_message_is_untouched_by_any_of_this(st):
    # THE GUARD MUST NOT SWALLOW THE HAPPY PATH. A try/except wide enough to catch a working
    # render would turn every message into a suppression and this file would still pass.
    sched(st)
    sender = FakeSender()
    go(st, sender)
    assert len(sender.calls) == 1
    rows = run(SendLogStore(st).since("t1", "sub_a", since=0))
    assert [r["outcome"] for r in rows] == ["sent"]
